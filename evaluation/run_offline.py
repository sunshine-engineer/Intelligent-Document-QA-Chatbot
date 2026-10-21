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
    CLARIFICATION_RESPONSE,
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
        expected_pairs = set(
            zip(case["expected_sources"], case["expected_pages"], strict=True)
        )
        actual_pairs = set(zip(sources, pages, strict=True))
        clarification_expected = case.get("clarification_expected", False)
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
                    len(expected_sources & set(sources)) / len(expected_sources)
                    if expected_sources
                    else None
                ),
                "reciprocal_rank": 1 / first_rank if first_rank else 0,
                "citation_correct": (
                    len(expected_pairs & actual_pairs) / len(actual_pairs)
                    if actual_pairs
                    else (0.0 if expected_pairs else 1.0)
                ),
                "refusal_correct": (
                    result.answer == CLARIFICATION_RESPONSE
                    if clarification_expected
                    else (
                        result.answer not in (REFUSAL_RESPONSE, CLARIFICATION_RESPONSE)
                        if case["answerable"]
                        else result.answer == REFUSAL_RESPONSE
                    )
                ),
                "rewrite_decision": result.rewrite_decision,
                "clarification_correct": (
                    result.answer == CLARIFICATION_RESPONSE
                    if clarification_expected
                    else None
                ),
                "latency_ms": round(latency_ms, 3),
            }
        )

    answerable = [outcome for outcome in outcomes if outcome["recall"] is not None]
    clarifications = [o for o in outcomes if o["clarification_correct"] is not None]

    def mean(items, field):
        return sum(item[field] for item in items) / len(items) if items else 0.0

    return {
        "dataset_version": dataset["version"],
        "case_count": len(outcomes),
        "retrieval_case_count": len(answerable),
        "clarification_case_count": len(clarifications),
        "recall_at_k": mean(answerable, "recall"),
        "mrr": mean(answerable, "reciprocal_rank"),
        "citation_correctness": mean(answerable, "citation_correct"),
        "refusal_accuracy": mean(outcomes, "refusal_correct"),
        "clarification_accuracy": mean(clarifications, "clarification_correct"),
        "mean_latency_ms": round(mean(outcomes, "latency_ms"), 3),
        "outcomes": outcomes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset", type=Path, default=Path("evaluation/dataset.v2.json")
    )
    parser.add_argument("--output", type=Path, default=Path("evaluation-results.json"))
    for metric in (
        "recall_at_k",
        "mrr",
        "citation_correctness",
        "refusal_accuracy",
        "clarification_accuracy",
    ):
        parser.add_argument(
            f"--min-{metric.replace('_', '-')}", type=float, default=1.0
        )
    args = parser.parse_args()
    result = evaluate(load_dataset(args.dataset))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    failed = [
        metric
        for metric in (
            "recall_at_k",
            "mrr",
            "citation_correctness",
            "refusal_accuracy",
            "clarification_accuracy",
        )
        if result[metric] < getattr(args, f"min_{metric}")
    ]
    if failed:
        print("Evaluation thresholds failed: " + ", ".join(failed), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
