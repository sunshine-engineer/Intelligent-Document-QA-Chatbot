"""Testable conversational retrieval and citation services."""

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator
import time
import logging

from app_logging import log_event, new_correlation_id


REFUSAL_RESPONSE = "I couldn't find that information in the uploaded documents."


@dataclass(frozen=True)
class CitationRecord:
    document: str
    page: int | None
    chunk_id: str
    excerpt: str
    retrieval_score: float


@dataclass(frozen=True)
class QueryResult:
    answer: str
    retrieval_query: str
    citations: tuple[CitationRecord, ...]
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass
class StreamTimings:
    retrieval_latency_ms: float = 0.0
    first_token_latency_ms: float | None = None
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass(frozen=True)
class StreamingQueryResult:
    retrieval_query: str
    citations: tuple[CitationRecord, ...]
    stream: Iterator[str]
    timings: StreamTimings


class ConversationalQueryService:
    """Rewrite, retrieve, deduplicate, and answer a user question."""

    def __init__(
        self,
        retriever: Callable[[str], Iterable[tuple[Any, float]]],
        answerer: Callable[[str, str, list[Any]], str],
        answer_streamer: Callable[[str, str, list[Any]], Iterable[Any]] | None = None,
        rewriter: Callable[[str, str], str] | None = None,
        relevance_threshold: float = 0.35,
        max_results: int = 4,
    ):
        self.retriever = retriever
        self.answerer = answerer
        self.answer_streamer = answer_streamer
        self.rewriter = rewriter
        self.relevance_threshold = relevance_threshold
        self.max_results = max_results

    def ask(self, question: str, history: str = "", correlation_id: str | None = None) -> QueryResult:
        correlation_id = correlation_id or new_correlation_id()
        started_at = time.perf_counter()
        log_event(logging.INFO, "query_started", correlation_id=correlation_id,
                  category="retrieval", history_present=bool(history.strip()),
                  question_length=len(question))
        retrieval_query = question
        if history.strip() and self.rewriter is not None:
            retrieval_query = self.rewriter(history, question).strip() or question
            log_event(logging.INFO, "query_rewritten", correlation_id=correlation_id,
                      category="retrieval", query_length=len(retrieval_query))

        retrieval_started_at = time.perf_counter()
        retrieved = []
        seen = set()
        for document, score in self.retriever(retrieval_query):
            if score < self.relevance_threshold:
                continue
            metadata = getattr(document, "metadata", {}) or {}
            content = getattr(document, "page_content", "")
            chunk_id = str(metadata.get("chunk_id") or self._fallback_chunk_id(metadata, content))
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            retrieved.append((document, float(score), chunk_id))
            if len(retrieved) >= self.max_results:
                break

        retrieval_latency_ms = (time.perf_counter() - retrieval_started_at) * 1000
        log_event(logging.INFO, "retrieval_completed", correlation_id=correlation_id,
                  category="retrieval", candidates=len(retrieved),
                  latency_ms=round(retrieval_latency_ms, 2))
        citations = tuple(
            CitationRecord(
                document=str(item.metadata.get("source", "Unknown")),
                page=self._page(item.metadata),
                chunk_id=chunk_id,
                excerpt=str(getattr(item, "page_content", ""))[:500],
                retrieval_score=score,
            )
            for item, score, chunk_id in retrieved
        )
        if not retrieved:
            total = (time.perf_counter() - started_at) * 1000
            log_event(logging.INFO, "query_refused_no_evidence", correlation_id=correlation_id,
                      category="retrieval", latency_ms=round(total, 2))
            return QueryResult(
                REFUSAL_RESPONSE, retrieval_query, citations,
                retrieval_latency_ms, 0.0, total,
            )

        generation_started_at = time.perf_counter()
        answer = self.answerer(question, history, [item for item, _, _ in retrieved])
        generation_latency_ms = (time.perf_counter() - generation_started_at) * 1000
        total = (time.perf_counter() - started_at) * 1000
        log_event(logging.INFO, "generation_completed", correlation_id=correlation_id,
                  category="provider", answer_length=len(answer),
                  latency_ms=round(generation_latency_ms, 2), total_ms=round(total, 2))
        return QueryResult(
            answer, retrieval_query, citations,
            retrieval_latency_ms, generation_latency_ms, total,
        )

    def ask_stream(
        self,
        question: str,
        history: str = "",
        correlation_id: str | None = None,
    ) -> StreamingQueryResult:
        if self.answer_streamer is None:
            raise RuntimeError("Provider streaming is not configured")

        correlation_id = correlation_id or new_correlation_id()
        started_at = time.perf_counter()
        retrieval_query, retrieved, citations, retrieval_latency_ms = (
            self._retrieve(question, history, correlation_id)
        )
        timings = StreamTimings(retrieval_latency_ms=retrieval_latency_ms)

        if not retrieved:
            def refusal_stream():
                timings.first_token_latency_ms = (
                    time.perf_counter() - started_at
                ) * 1000
                yield REFUSAL_RESPONSE
                timings.total_latency_ms = (time.perf_counter() - started_at) * 1000

            return StreamingQueryResult(
                retrieval_query, citations, refusal_stream(), timings
            )

        documents = [item for item, _, _ in retrieved]

        def provider_stream():
            generation_started_at = time.perf_counter()
            failed = False
            try:
                for chunk in self.answer_streamer(question, history, documents):
                    text = chunk if isinstance(chunk, str) else getattr(chunk, "content", "")
                    if not text:
                        continue
                    if timings.first_token_latency_ms is None:
                        timings.first_token_latency_ms = (
                            time.perf_counter() - started_at
                        ) * 1000
                    yield text
            except Exception as error:
                failed = True
                log_event(
                    logging.ERROR,
                    "stream_failed",
                    correlation_id=correlation_id,
                    category="provider",
                    error_type=type(error).__name__,
                )
                raise
            finally:
                timings.generation_latency_ms = (
                    time.perf_counter() - generation_started_at
                ) * 1000
                timings.total_latency_ms = (time.perf_counter() - started_at) * 1000
                log_event(
                    logging.INFO,
                    "stream_terminated" if failed else "stream_completed",
                    correlation_id=correlation_id,
                    category="provider",
                    first_token_ms=round(timings.first_token_latency_ms or 0, 2),
                    generation_ms=round(timings.generation_latency_ms, 2),
                    total_ms=round(timings.total_latency_ms, 2),
                )

        return StreamingQueryResult(
            retrieval_query, citations, provider_stream(), timings
        )

    def _retrieve(self, question, history, correlation_id):
        retrieval_query = question
        if history.strip() and self.rewriter is not None:
            retrieval_query = self.rewriter(history, question).strip() or question
        retrieval_started_at = time.perf_counter()
        retrieved = []
        seen = set()
        for document, score in self.retriever(retrieval_query):
            if score < self.relevance_threshold:
                continue
            metadata = getattr(document, "metadata", {}) or {}
            content = getattr(document, "page_content", "")
            chunk_id = str(
                metadata.get("chunk_id")
                or self._fallback_chunk_id(metadata, content)
            )
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            retrieved.append((document, float(score), chunk_id))
            if len(retrieved) >= self.max_results:
                break
        retrieval_latency_ms = (time.perf_counter() - retrieval_started_at) * 1000
        citations = tuple(
            CitationRecord(
                document=str(item.metadata.get("source", "Unknown")),
                page=self._page(item.metadata),
                chunk_id=chunk_id,
                excerpt=str(getattr(item, "page_content", ""))[:500],
                retrieval_score=score,
            )
            for item, score, chunk_id in retrieved
        )
        log_event(
            logging.INFO,
            "stream_retrieval_completed",
            correlation_id=correlation_id,
            category="retrieval",
            evidence_count=len(retrieved),
            latency_ms=round(retrieval_latency_ms, 2),
        )
        return retrieval_query, retrieved, citations, retrieval_latency_ms

    @staticmethod
    def _page(metadata):
        page = metadata.get("page")
        return page + 1 if isinstance(page, int) else None

    @staticmethod
    def _fallback_chunk_id(metadata, content):
        return f"{metadata.get('source', '')}:{metadata.get('page', '')}:{content}"
