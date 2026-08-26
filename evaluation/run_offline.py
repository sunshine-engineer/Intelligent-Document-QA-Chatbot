"""Run deterministic offline retrieval evaluation without live providers."""

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from query_services import (  # noqa: E402
    ConversationalQueryService,
    REFUSAL_RESPONSE,
)


def load_dataset(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_document(record):
    return SimpleNamespace(
        metadata={
            "source": record["source"],
            "page": record["page"],
            "chunk_id": record["chunk_id"],
        },
        page_content=record["content"],
    )


def evaluate(dataset):
    documents = [make_document(record) for record in dataset["documents"]]
    outcomes = []

    for case in dataset["cases"]:

        def retrieve(query):
            query_words = set(query.lower().split())
            matches = []
            for document in documents:
                content_words = set(document.page_content.lower().split())
                score = len(query_words & content_words) / max(len(query_words), 1)
                if score:
                    matches.append((document, score))
            return sorted(matches, key=lambda result: result[1], reverse=True)

        def rewriter(history, question):
            if history and "condition" in question.lower():
                return "large language models context output"
            return question

        service = ConversationalQueryService(
            retriever=retrieve,
            rewriter=rewriter,
            answerer=lambda question, history, evidence: evidence[0].page_content,
            relevance_threshold=0.1,
        )
        started_at = time.perf_counter()
        result = service.ask(case["question"], case.get("history", ""))
        latency_ms = (time.perf_counter() - started_at) * 1000
        sources = [citation.document for citation in result.citations]
        pages = [citation.page for citation in result.citations]
        expected_sources = set(case["expected_sources"])
        expected_pages = set(case["expected_pages"])
        first_rank = next(
            (
                index + 1
                for index, source in enumerate(sources)
                if source in expected_sources
            ),
            None,
        )
        outcomes.append(
            {
                "id": case["id"],
                "answerable": case["answerable"],
                "recall": (
                    bool(expected_sources & set(sources)) if expected_sources else True
                ),
                "reciprocal_rank": 1 / first_rank if first_rank else 0,
                "citation_correct": (
                    bool(expected_sources & set(sources))
                    and bool(expected_pages & set(pages))
                    if expected_sources
                    else not sources
                ),
                "refusal_correct": (
                    (result.answer != REFUSAL_RESPONSE)
                    if case["answerable"]
                    else result.answer == REFUSAL_RESPONSE
                ),
                "rewrite_decision": result.rewrite_decision,
                "clarification_correct": (
                    "clarify" in result.answer.lower()
                    if case["id"] == "ambiguous-follow-up"
                    else True
                ),
                "latency_ms": round(latency_ms, 3),
            }
        )

    answerable = [outcome for outcome in outcomes if outcome["answerable"]]
    return {
        "dataset_version": dataset["version"],
        "case_count": len(outcomes),
        "recall_at_k": sum(item["recall"] for item in answerable) / len(answerable),
        "mrr": sum(item["reciprocal_rank"] for item in answerable) / len(answerable),
        "citation_correctness": sum(item["citation_correct"] for item in answerable)
        / len(answerable),
        "refusal_accuracy": sum(item["refusal_correct"] for item in outcomes)
        / len(outcomes),
        "clarification_accuracy": sum(
            item["clarification_correct"] for item in outcomes
        )
        / len(outcomes),
        "mean_latency_ms": round(
            sum(item["latency_ms"] for item in outcomes) / len(outcomes), 3
        ),
        "outcomes": outcomes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("evaluation/dataset.v1.json")
    )
    parser.add_argument("--output", type=Path, default=Path("evaluation-results.json"))
    args = parser.parse_args()
    result = evaluate(load_dataset(args.dataset))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
