"""Exercise the real LangChain composition with local deterministic providers."""

import unittest
from types import SimpleNamespace

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from app_composition import build_query_service
from settings import Settings


class CompositionTests(unittest.TestCase):
    def test_real_factory_expands_follow_up_and_supplies_citation_ids(self):
        queries = []
        prompts = []

        class Vectors:
            def as_retriever(self, **kwargs):
                return SimpleNamespace(vectorstore=self)

            def similarity_search_with_relevance_scores(self, query, k):
                queries.append(query)
                return [
                    (
                        Document(
                            page_content="Attention weighs tokens.",
                            metadata={"source": "paper.pdf", "page": 0},
                        ),
                        0.9,
                    )
                ]

        def answer(prompt):
            prompts.append(prompt.to_string())
            return "Attention weighs tokens [S1]."

        service = build_query_service(
            Vectors(), RunnableLambda(answer), Settings.from_env({}), 4
        )
        result = service.ask_stream("How does it work?", "User: Explain attention.")
        self.assertEqual("".join(result.stream), "Attention weighs tokens [S1].")
        self.assertIn("Explain attention", queries[0])
        self.assertIn("How does it work?", queries[0])
        self.assertIn("[S1] Attention", prompts[0])
        self.assertIn("untrusted", prompts[0])
        self.assertEqual(result.citations[0].page, 1)
        clarification = service.ask_stream("It?", "User: Compare two papers.")
        self.assertIn("clarify", "".join(clarification.stream))
        self.assertEqual(len(queries), 1)

    def test_real_faiss_round_trip_with_deterministic_embeddings(self):
        import tempfile
        from langchain_core.embeddings import Embeddings
        from langchain_community.vectorstores import FAISS
        from app_services import IndexConfig, IndexService

        class LocalEmbeddings(Embeddings):
            def embed_documents(self, texts):
                return [self.embed_query(text) for text in texts]

            def embed_query(self, text):
                return [1.0, 0.0] if "attention" in text.lower() else [0.0, 1.0]

        embeddings = LocalEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            docs = [
                Document(
                    page_content="Attention weighs tokens",
                    metadata={"source": "a.pdf", "page": 0},
                ),
                Document(
                    page_content="Databases store records",
                    metadata={"source": "b.pdf", "page": 0},
                ),
            ]
            vectors = FAISS.from_documents(docs, embeddings)
            from index_metadata import save_index_snapshot_atomically

            config = IndexConfig("unused", directory + "/index", "test", "local")
            save_index_snapshot_atomically(
                vectors,
                config.index_directory,
                "test",
                "local",
                {"documents": {"a.pdf": {}, "b.pdf": {}}},
                docs,
                indexing_config=config.indexing_config(),
            )
            service = IndexService(
                config, lambda: embeddings, None, None, FAISS.load_local
            )
            loaded, _ = service.load()
            self.assertEqual(
                loaded.similarity_search("attention", k=1)[0].metadata["source"],
                "a.pdf",
            )


class ProviderConfigurationTests(unittest.TestCase):
    def test_provider_objects_construct_with_explicit_limits_without_requests(self):
        from app_composition import create_llm, create_embedding_factory

        settings = Settings.from_env({"GROQ_API_KEY": "synthetic-not-a-real-key"})
        llm = create_llm(settings)
        self.assertEqual(llm.max_retries, 2)
        self.assertEqual(llm.max_tokens, 1024)
        self.assertEqual(llm.request_timeout, 30)
        embeddings = create_embedding_factory(settings)()
        self.assertEqual(embeddings.client_kwargs, {"timeout": 60})

    def test_missing_generation_provider_is_rejected_explicitly(self):
        with self.assertRaisesRegex(ValueError, "not configured"):
            build_query_service(None, None, Settings.from_env({}), 4)
