"""Testable conversational retrieval and citation services."""

from dataclasses import dataclass
from typing import Any, Callable, Iterable


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


class ConversationalQueryService:
    """Rewrite, retrieve, deduplicate, and answer a user question."""

    def __init__(
        self,
        retriever: Callable[[str], Iterable[tuple[Any, float]]],
        answerer: Callable[[str, str, list[Any]], str],
        rewriter: Callable[[str, str], str] | None = None,
        relevance_threshold: float = 0.35,
        max_results: int = 4,
    ):
        self.retriever = retriever
        self.answerer = answerer
        self.rewriter = rewriter
        self.relevance_threshold = relevance_threshold
        self.max_results = max_results

    def ask(self, question: str, history: str = "") -> QueryResult:
        retrieval_query = question
        if history.strip() and self.rewriter is not None:
            retrieval_query = self.rewriter(history, question).strip() or question

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
            return QueryResult(REFUSAL_RESPONSE, retrieval_query, citations)

        answer = self.answerer(question, history, [item for item, _, _ in retrieved])
        return QueryResult(answer, retrieval_query, citations)

    @staticmethod
    def _page(metadata):
        page = metadata.get("page")
        return page + 1 if isinstance(page, int) else None

    @staticmethod
    def _fallback_chunk_id(metadata, content):
        return f"{metadata.get('source', '')}:{metadata.get('page', '')}:{content}"
