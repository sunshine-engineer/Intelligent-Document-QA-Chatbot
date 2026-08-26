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
            retriever=lambda query: (
                queries.append(query) or [(first, 0.9), (duplicate, 0.8), (second, 0.7)]
            ),
            rewriter=lambda history, question: "standalone rewritten query",
            answerer=lambda question, history, docs: "supported answer",
        )

        result = service.ask("What about it?", "User: Explain the paper.")

        self.assertEqual(queries, ["standalone rewritten query"])
        self.assertEqual(result.answer, "supported answer")
        self.assertEqual(
            [citation.chunk_id for citation in result.citations], ["a", "b"]
        )
        self.assertEqual(result.citations[0].page, 1)

    def test_standalone_question_does_not_rewrite(self):
        service = ConversationalQueryService(
            retriever=lambda query: [(document("paper.pdf", 1, "a", "evidence"), 0.9)],
            rewriter=lambda *_: self.fail("rewriter should not be called"),
            answerer=lambda *_: "answer",
        )
        self.assertEqual(
            service.ask("What is attention?").retrieval_query, "What is attention?"
        )

    def test_topic_change_with_history_does_not_rewrite(self):
        service = ConversationalQueryService(
            retriever=lambda query: [(document("paper.pdf", 1, "a", query), 0.9)],
            rewriter=lambda *_: self.fail("rewriter should not be called"),
            answerer=lambda *_: "answer",
        )
        result = service.ask("What is attention?", "User: Explain databases.")
        self.assertEqual(result.rewrite_decision, "standalone")
        self.assertEqual(result.retrieval_query, "What is attention?")

    def test_ambiguous_follow_up_clarifies_in_sync_and_streaming_modes(self):
        service = ConversationalQueryService(
            retriever=lambda _: self.fail("retriever should not be called"),
            rewriter=lambda *_: self.fail("rewriter should not be called"),
            answerer=lambda *_: self.fail("answerer should not be called"),
            answer_streamer=lambda *_: (),
        )
        result = service.ask("It?", "User: Explain two papers.")
        self.assertEqual(result.rewrite_decision, "ambiguous")
        self.assertIn("clarify", result.answer.lower())
        stream = service.ask_stream("It?", "User: Explain two papers.")
        self.assertEqual(stream.rewrite_decision, "ambiguous")
        self.assertIn("clarify", "".join(stream.stream).lower())

    def test_empty_or_low_score_evidence_returns_refusal(self):
        service = ConversationalQueryService(
            retriever=lambda _: [(document("paper.pdf", 0, "a", "weak"), 0.2)],
            answerer=lambda *_: self.fail("answerer should not be called"),
            relevance_threshold=0.35,
        )
        result = service.ask("Unsupported question")
        self.assertEqual(result.answer, REFUSAL_RESPONSE)
        self.assertEqual(result.citations, ())

    def test_streaming_yields_provider_chunks_before_completion(self):
        events = []

        def stream_answer(*_):
            events.append("started")
            yield "first "
            events.append("continued")
            yield "second"

        service = ConversationalQueryService(
            retriever=lambda _: [(document("paper.pdf", 0, "a", "evidence"), 0.9)],
            answerer=lambda *_: "unused",
            answer_streamer=stream_answer,
        )
        result = service.ask_stream("Question")
        self.assertEqual(events, [])
        self.assertEqual(next(result.stream), "first ")
        self.assertEqual(events, ["started"])
        self.assertEqual("".join(result.stream), "second")
        self.assertIsNotNone(result.timings.first_token_latency_ms)

    def test_mid_stream_failure_is_propagated(self):
        def failing_stream(*_):
            yield "partial"
            raise TimeoutError("provider timeout")

        service = ConversationalQueryService(
            retriever=lambda _: [(document("paper.pdf", 0, "a", "evidence"), 0.9)],
            answerer=lambda *_: "unused",
            answer_streamer=failing_stream,
        )
        result = service.ask_stream("Question")
        self.assertEqual(next(result.stream), "partial")
        with self.assertRaises(TimeoutError):
            next(result.stream)


if __name__ == "__main__":
    unittest.main()
