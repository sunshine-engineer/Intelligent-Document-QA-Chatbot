"""Retrieve, filter and cite evidence for synchronous and streamed document answers.

File: query_services.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator

from app_logging import log_event, new_correlation_id

REFUSAL_RESPONSE = "I couldn't find that information in the uploaded documents."
CLARIFICATION_RESPONSE = (
    "Please clarify what you are referring to in the earlier conversation."
)


@dataclass(frozen=True)
class CitationRecord:
    """Retrieved evidence identity, one-based page, excerpt and relevance score;
    not semantic verification.

    Attributes:
        document: Source filename or path identifying the retrieved passage.
        page: One-based displayed page, or None when source page metadata is
            absent.
        chunk_id: Stable identifier for a retrieved evidence chunk.
        excerpt: First 500 characters retained for evidence inspection.
        retrieval_score: Retriever relevance score; not a confidence
            probability.
    """

    document: str
    page: int | None
    chunk_id: str
    excerpt: str
    retrieval_score: float


@dataclass(frozen=True)
class QueryResult:
    """Completed synchronous answer with retrieval context, citations, decision and
    millisecond timings.

    Attributes:
        answer: Completed generated answer or fixed refusal/clarification text.
        retrieval_query: Lookup string actually supplied to the retriever.
        citations: Ordered unique evidence records, not semantic claim
            verification.
        retrieval_latency_ms: Evidence retrieval duration in milliseconds.
        generation_latency_ms: Generation/stream consumption duration in
            milliseconds.
        total_latency_ms: Elapsed request duration in milliseconds.
        rewrite_decision: Standalone, contextual or ambiguous follow-up
            classification.
    """

    answer: str
    retrieval_query: str
    citations: tuple[CitationRecord, ...]
    retrieval_latency_ms: float = 0.0
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    rewrite_decision: str = "standalone"


@dataclass
class StreamTimings:
    """Mutable millisecond measurements finalized while a response stream is
    consumed.

    Attributes:
        retrieval_latency_ms: Evidence retrieval duration in milliseconds.
        first_token_latency_ms: Milliseconds to first nonempty fragment; None
            before emission.
        generation_latency_ms: Generation/stream consumption duration in
            milliseconds.
        total_latency_ms: Elapsed request duration in milliseconds.
    """

    retrieval_latency_ms: float = 0.0
    first_token_latency_ms: float | None = None
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass(frozen=True)
class StreamingQueryResult:
    """Lazy answer stream and its evidence; consume stream before reading final
    timing values.

    Attributes:
        retrieval_query: Lookup string actually supplied to the retriever.
        citations: Ordered unique evidence records, not semantic claim
            verification.
        stream: Lazy iterator yielding provider or refusal text fragments.
        timings: Shared mutable timing record updated while stream is consumed.
        rewrite_decision: Standalone, contextual or ambiguous follow-up
            classification.
    """

    retrieval_query: str
    citations: tuple[CitationRecord, ...]
    stream: Iterator[str]
    timings: StreamTimings
    rewrite_decision: str = "standalone"


class ConversationalQueryService:
    """History-aware retrieval, evidence filtering and provider-independent answer
    orchestration.
    """

    def __init__(
        self,
        retriever: Callable[[str], Iterable[tuple[Any, float]]],
        answerer: Callable[[str, str, list[Any]], str],
        answer_streamer: Callable[[str, str, list[Any]], Iterable[Any]] | None = None,
        rewriter: Callable[[str, str], str] | None = None,
        relevance_threshold: float = 0.35,
        max_results: int = 4,
    ):
        """Initialize injected adapters and state without performing provider
        requests.

        Args:
            retriever: Callable returning ordered (document, relevance-score)
                pairs.
            answerer: Callable producing an answer from question, history and
                retrieved documents.
            answer_streamer: Optional callable yielding generation fragments
                lazily.
            rewriter: Optional callable expanding a contextual question using
                history.
            relevance_threshold: Minimum relevance score retained as evidence.
            max_results: Maximum number of unique retained evidence chunks.
        """
        self.retriever = retriever
        self.answerer = answerer
        self.answer_streamer = answer_streamer
        self.rewriter = rewriter
        self.relevance_threshold = relevance_threshold
        self.max_results = max_results

    def ask(
        self, question: str, history: str = "", correlation_id: str | None = None
    ) -> QueryResult:
        """Retrieve unique evidence and return a supported answer, refusal or
        clarification.

        Args:
            question: Original user question; generation preserves its wording.
            history: Recent conversation text; generation/rewrite composition
                applies configured caps.
            correlation_id: Optional opaque reference linking request and
                diagnostic events.

        Returns:
            QueryResult with answer text, retrieval query, citations, decision
            and timings.

        Raises:
            Exception: Retrieval, rewriting or generation callbacks fail.
        """
        correlation_id = correlation_id or new_correlation_id()
        started_at = time.perf_counter()
        log_event(
            logging.INFO,
            "query_started",
            correlation_id=correlation_id,
            category="retrieval",
            history_present=bool(history.strip()),
            question_length=len(question),
        )
        rewrite_decision, retrieval_query = self._rewrite_decision(question, history)
        log_event(
            logging.INFO,
            "rewrite_decision",
            correlation_id=correlation_id,
            category="retrieval",
            decision=rewrite_decision,
        )
        if rewrite_decision == "contextual":
            assert self.rewriter is not None
            retrieval_query = self.rewriter(history, question).strip() or question
        if rewrite_decision == "ambiguous":
            return QueryResult(
                CLARIFICATION_RESPONSE, question, (), rewrite_decision=rewrite_decision
            )

        retrieval_started_at = time.perf_counter()
        retrieved = []
        seen = set()
        for document, score in self.retriever(retrieval_query):
            if score < self.relevance_threshold:
                continue
            metadata = getattr(document, "metadata", {}) or {}
            content = getattr(document, "page_content", "")
            chunk_id = str(
                metadata.get("chunk_id") or self._fallback_chunk_id(metadata, content)
            )
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            retrieved.append((document, float(score), chunk_id))
            if len(retrieved) >= self.max_results:
                break

        retrieval_latency_ms = (time.perf_counter() - retrieval_started_at) * 1000
        log_event(
            logging.INFO,
            "retrieval_completed",
            correlation_id=correlation_id,
            category="retrieval",
            candidates=len(retrieved),
            latency_ms=round(retrieval_latency_ms, 2),
        )
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
            log_event(
                logging.INFO,
                "query_refused_no_evidence",
                correlation_id=correlation_id,
                category="retrieval",
                latency_ms=round(total, 2),
            )
            return QueryResult(
                REFUSAL_RESPONSE,
                retrieval_query,
                citations,
                retrieval_latency_ms,
                0.0,
                total,
                rewrite_decision,
            )

        generation_started_at = time.perf_counter()
        answer = self.answerer(question, history, [item for item, _, _ in retrieved])
        generation_latency_ms = (time.perf_counter() - generation_started_at) * 1000
        total = (time.perf_counter() - started_at) * 1000
        log_event(
            logging.INFO,
            "generation_completed",
            correlation_id=correlation_id,
            category="provider",
            answer_length=len(answer),
            latency_ms=round(generation_latency_ms, 2),
            total_ms=round(total, 2),
        )
        return QueryResult(
            answer,
            retrieval_query,
            citations,
            retrieval_latency_ms,
            generation_latency_ms,
            total,
            rewrite_decision,
        )

    def ask_stream(
        self,
        question: str,
        history: str = "",
        correlation_id: str | None = None,
    ) -> StreamingQueryResult:
        """Prepare evidence and return a lazy answer stream with mutable timing
        measurements.

        Args:
            question: Original user question; generation preserves its wording.
            history: Recent conversation text; generation/rewrite composition
                applies configured caps.
            correlation_id: Optional opaque reference linking request and
                diagnostic events.

        Returns:
            StreamingQueryResult; consume its stream to complete timing
            measurements.

        Raises:
            RuntimeError: Streaming has not been configured.
            Exception: Retrieval fails, or provider iteration fails when the
                stream is consumed.

        Example:
            result = service.ask_stream("Explain attention")
            answer = "".join(result.stream)
            elapsed_ms = result.timings.total_latency_ms
        """
        if self.answer_streamer is None:
            raise RuntimeError("Provider streaming is not configured")
        streamer = self.answer_streamer

        correlation_id = correlation_id or new_correlation_id()
        started_at = time.perf_counter()
        (
            retrieval_query,
            retrieved,
            citations,
            retrieval_latency_ms,
            rewrite_decision,
        ) = self._retrieve(question, history, correlation_id)
        timings = StreamTimings(retrieval_latency_ms=retrieval_latency_ms)

        if not retrieved:

            def refusal_stream():
                """Yield the fixed refusal or clarification and populate its timing
                record.

                Yields:
                    Nonempty response text fragments in provider order.
                """
                timings.first_token_latency_ms = (
                    time.perf_counter() - started_at
                ) * 1000
                yield (
                    CLARIFICATION_RESPONSE
                    if rewrite_decision == "ambiguous"
                    else REFUSAL_RESPONSE
                )
                timings.total_latency_ms = (time.perf_counter() - started_at) * 1000

            return StreamingQueryResult(
                retrieval_query, citations, refusal_stream(), timings, rewrite_decision
            )

        documents = [item for item, _, _ in retrieved]

        def provider_stream():
            """Yield nonempty provider fragments and finalize timings on completion
            or failure.

            Yields:
                Nonempty response text fragments in provider order.

            Raises:
                Exception: The provider fails while yielding fragments; timings
                    are still finalized.
            """
            generation_started_at = time.perf_counter()
            failed = False
            try:
                for chunk in streamer(question, history, documents):
                    text = (
                        chunk
                        if isinstance(chunk, str)
                        else getattr(chunk, "content", "")
                    )
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
            retrieval_query, citations, provider_stream(), timings, rewrite_decision
        )

    def _retrieve(self, question, history, correlation_id):
        """Apply contextual lookup, score filtering and deduplication for the
        streaming path.

        Args:
            question: Original user question; generation preserves its wording.
            history: Recent conversation text; generation/rewrite composition
                applies configured caps.
            correlation_id: Optional opaque reference linking request and
                diagnostic events.

        Returns:
            Lookup text, scored unique documents, citations, retrieval latency
            and decision.
        """
        rewrite_decision, retrieval_query = self._rewrite_decision(question, history)
        log_event(
            logging.INFO,
            "rewrite_decision",
            correlation_id=correlation_id,
            category="retrieval",
            decision=rewrite_decision,
        )
        if rewrite_decision == "contextual":
            assert self.rewriter is not None
            retrieval_query = self.rewriter(history, question).strip() or question
        if rewrite_decision == "ambiguous":
            return question, [], (), 0.0, rewrite_decision
        retrieval_started_at = time.perf_counter()
        retrieved = []
        seen = set()
        for document, score in self.retriever(retrieval_query):
            if score < self.relevance_threshold:
                continue
            metadata = getattr(document, "metadata", {}) or {}
            content = getattr(document, "page_content", "")
            chunk_id = str(
                metadata.get("chunk_id") or self._fallback_chunk_id(metadata, content)
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
        return (
            retrieval_query,
            retrieved,
            citations,
            retrieval_latency_ms,
            rewrite_decision,
        )

    def _rewrite_decision(self, question, history):
        """Classify supported pronoun follow-ups as standalone, contextual or
        ambiguous.

        Args:
            question: Original user question; generation preserves its wording.
            history: Recent conversation text; generation/rewrite composition
                applies configured caps.

        Returns:
            Decision label and the original question before optional rewriting.
        """
        if not history.strip() or self.rewriter is None:
            return "standalone", question
        words = question.lower().replace("?", "").split()
        references = {"it", "this", "that", "they", "them", "those", "these"}
        if not references.intersection(words):
            return "standalone", question
        if len(words) <= 2:
            return "ambiguous", question
        return "contextual", question

    @staticmethod
    def _page(metadata):
        """Convert an integer zero-based source page to a one-based display page.

        Args:
            metadata: Document metadata mapping containing source and optional
                zero- based page.

        Returns:
            One-based page integer, or None when no integer page is present.
        """
        page = metadata.get("page")
        return page + 1 if isinstance(page, int) else None

    @staticmethod
    def _fallback_chunk_id(metadata, content):
        """Derive a deterministic fallback identity from source, page and full
        chunk content.

        Args:
            metadata: Document metadata mapping containing source and optional
                zero- based page.
            content: Chunk text used to derive an identity, or fixture bytes for
                a fake index.

        Returns:
            Source, page and full-content composite identity string.
        """
        return f"{metadata.get('source', '')}:{metadata.get('page', '')}:{content}"
