import unittest
from types import SimpleNamespace

from query_services import ConversationalQueryService, REFUSAL_RESPONSE


def document(source, page, chunk_id, text):
    return SimpleNamespace(
        metadata={"source": source, "page": page, "chunk_id": chunk_id},
        page_content=text,
    )


class ConversationalQueryTests(unittest.TestCase):
    def test_follow_up_is_rewritten_and_citations_are_ordered_and_unique(self):
        first = document("paper.pdf", 0, "a", "first evidence")
        duplicate = document("paper.pdf", 0, "a", "first evidence")
        second = document("paper.pdf", 2, "b", "second evidence")
        queries = []

        service = ConversationalQueryService(
            retriever=lambda query: (queries.append(query) or [(first, .9), (duplicate, .8), (second, .7)]),
            rewriter=lambda history, question: "standalone rewritten query",
            answerer=lambda question, history, docs: "supported answer",
        )

        result = service.ask("What about it?", "User: Explain the paper.")

        self.assertEqual(queries, ["standalone rewritten query"])
        self.assertEqual(result.answer, "supported answer")
        self.assertEqual([citation.chunk_id for citation in result.citations], ["a", "b"])
        self.assertEqual(result.citations[0].page, 1)

    def test_standalone_question_does_not_rewrite(self):
        service = ConversationalQueryService(
            retriever=lambda query: [(document("paper.pdf", 1, "a", "evidence"), .9)],
            rewriter=lambda *_: self.fail("rewriter should not be called"),
            answerer=lambda *_: "answer",
        )
        self.assertEqual(service.ask("What is attention?").retrieval_query, "What is attention?")

    def test_empty_or_low_score_evidence_returns_refusal(self):
        service = ConversationalQueryService(
            retriever=lambda _: [(document("paper.pdf", 0, "a", "weak"), .2)],
            answerer=lambda *_: self.fail("answerer should not be called"),
            relevance_threshold=.35,
        )
        result = service.ask("Unsupported question")
        self.assertEqual(result.answer, REFUSAL_RESPONSE)
        self.assertEqual(result.citations, ())


if __name__ == "__main__":
    unittest.main()
