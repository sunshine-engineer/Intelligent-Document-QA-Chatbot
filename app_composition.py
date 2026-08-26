"""Provider and service composition with no Streamlit dependency."""

from typing import Any, Callable

from app_services import IndexConfig, IndexService
from query_services import ConversationalQueryService
from settings import Settings


def create_llm(settings: Settings) -> Any | None:
    if not settings.groq_api_key:
        return None
    from langchain_groq import ChatGroq

    return ChatGroq(groq_api_key=settings.groq_api_key, model=settings.llm_model)


def create_embedding_factory(settings: Settings) -> Callable[[], Any]:
    from langchain_ollama import OllamaEmbeddings

    return lambda: OllamaEmbeddings(
        model=settings.embedding_model, base_url=settings.ollama_url
    )


def build_index_service(
    settings: Settings, embedding_factory: Callable[[], Any]
) -> IndexService:
    from langchain_community.document_loaders import PyPDFDirectoryLoader
    from langchain_community.vectorstores import FAISS
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return IndexService(
        IndexConfig(
            pdf_directory=str(settings.pdf_directory),
            index_directory=str(settings.index_directory),
            embedding_provider="ollama",
            embedding_model=settings.embedding_model,
        ),
        embedding_factory=embedding_factory,
        loader_factory=PyPDFDirectoryLoader,
        splitter_factory=lambda: RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        ),
        faiss_loader=FAISS.load_local,
        faiss_factory=FAISS.from_documents,
    )


def build_query_service(vectors: Any, llm: Any, settings: Settings, top_k: int):
    from langchain_classic.chains.combine_documents import create_stuff_documents_chain
    from langchain_core.prompts import ChatPromptTemplate

    prompt = ChatPromptTemplate.from_template(
        "Use only the retrieved context. If evidence is missing, say so.\n"
        "History: {history}\nContext: {context}\nQuestion: {input}"
    )
    retriever = vectors.as_retriever(search_kwargs={"k": top_k})
    chain = create_stuff_documents_chain(llm, prompt) if llm else None

    def retrieve(query: str):
        return retriever.vectorstore.similarity_search_with_relevance_scores(
            query, k=top_k
        )

    return ConversationalQueryService(
        retriever=retrieve,
        rewriter=None,
        answerer=lambda question, history, documents: chain.invoke(
            {"input": question, "history": history, "context": documents}
        ),
        answer_streamer=(
            (
                lambda question, history, documents: chain.stream(
                    {"input": question, "history": history, "context": documents}
                )
            )
            if chain
            else None
        ),
        relevance_threshold=settings.relevance_threshold,
        max_results=top_k,
    )
