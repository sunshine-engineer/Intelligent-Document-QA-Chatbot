"""Render the single-user Streamlit document-QA interface and safe recovery controls.

File: app.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import logging
import os
from dataclasses import asdict
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from app_composition import (
    build_index_service,
    build_query_service,
    create_embedding_factory,
    create_llm,
)
from app_logging import configure_logging, log_exception, new_correlation_id
from app_runtime import KnowledgeBase, synchronize_index
from settings import Settings, provider_guidance


def safe_error(error, category):
    """Display safe provider guidance and log a correlation reference.

    Args:
        error: Exception to classify or report without exposing its raw payload.
        category: Application error category used for safe display or correlated
            logging.

    Returns:
        None.
    """
    reference = new_correlation_id()
    log_exception(reference, category, error)
    st.error(f"{provider_guidance(error)} Reference: {reference}.")


def render_answer_metadata(message, number):
    """Render stored timing, download and retrieved-evidence controls for one
    answer.

    Args:
        message: Stored assistant answer with optional citation and timing
            records.
        number: Stable zero-based chat position used to create unique widget
            keys.

    Returns:
        None.
    """
    timings = message.get("timings")
    if timings:
        st.caption(
            f"Retrieval: {timings['retrieval_latency_ms']:.0f} ms · "
            f"First token: {timings['first_token_latency_ms'] or 0:.0f} ms · "
            f"Total: {timings['total_latency_ms']:.0f} ms"
        )
    st.download_button(
        "📥 Download Response",
        message["content"],
        file_name="rag_response.txt",
        mime="text/plain",
        key=f"download-{number}",
    )
    citations = message.get("citations", [])
    if citations:
        with st.expander(f"📚 Retrieved Sources ({len(citations)})"):
            st.caption(
                "Retrieved evidence is shown for inspection; source references "
                "do not automatically prove every generated claim."
            )
            for source_id, citation in enumerate(citations, 1):
                st.write(
                    f"[S{source_id}] {os.path.basename(citation['document'])} · "
                    f"Page: {citation['page'] or 'Unknown'}"
                )
                st.code(citation["excerpt"], language=None)
                st.caption(f"Score: {citation['retrieval_score']:.3f}")


def main():
    """Run the Streamlit UI after validating settings, with guarded indexing and
    answer streaming.

    Returns:
        None.
    """
    st.set_page_config(page_title="Local RAG Assistant", page_icon="🤖", layout="wide")
    style_path = Path(__file__).parent / ".streamlit" / "style.css"
    if style_path.is_file():
        st.markdown(f"<style>{style_path.read_text()}</style>", unsafe_allow_html=True)
    load_dotenv()
    settings = Settings.from_env()
    errors = settings.validate()
    if errors:
        st.error("Invalid application configuration:")
        for error in errors:
            st.write(f"- {error}")
        st.stop()
    try:
        configure_logging(
            settings.log_directory,
            max_bytes=settings.log_max_bytes,
            backup_count=settings.log_backup_count,
        )
    except OSError:
        # A read-only log directory must not prevent the UI reporting service errors.
        logging.getLogger("rag_assistant").addHandler(logging.NullHandler())
    for key, value in {"messages": [], "knowledge_base": KnowledgeBase()}.items():
        if key not in st.session_state:
            st.session_state[key] = value
    llm = None
    try:
        llm = create_llm(settings)
    except Exception as error:
        safe_error(error, "configuration")
    st.title("🤖 Local RAG Assistant")
    st.caption("Ask questions about a local collection of text-based PDFs.")
    st.caption(
        "Privacy: embeddings run in Ollama; questions, recent history, and retrieved "
        "document text are sent to Groq for answers. Use documents you may share."
    )
    with st.sidebar:
        st.title("⚙️ Dashboard")
        if settings.max_top_k == 1:
            top_k = 1
            st.caption("Top K Chunks: 1")
        else:
            top_k = st.slider(
                "Top K Chunks", 1, settings.max_top_k, settings.default_top_k
            )
        if st.button("🗑 Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
        refresh = st.button("🔄 Refresh Knowledge Base", use_container_width=True)
        load_saved = st.button("📂 Load Saved Index", use_container_width=True)
        st.caption(f"LLM: {settings.llm_model}")
        st.caption(f"Embeddings: {settings.embedding_model}")
        with st.expander("Effective configuration"):
            st.json(settings.redacted_summary())
        if llm is None:
            st.warning("Configure GROQ_API_KEY in .env to enable answers.")
    index_ready = False
    try:
        embedding_factory = create_embedding_factory(settings)
        index_service = build_index_service(settings, embedding_factory)
        previous = None if load_saved else st.session_state.knowledge_base
        with st.spinner("Checking knowledge base..."):
            knowledge_base = synchronize_index(index_service, previous, force=refresh)
        st.session_state.knowledge_base = knowledge_base
        index_ready = knowledge_base.vectors is not None
    except Exception as error:
        safe_error(error, "indexing")
        st.warning(
            "Indexing or discovery failed. Check PDF permissions, PDF validity and "
            "Ollama, then use Refresh Knowledge Base. The last saved index is retained."
        )
    knowledge_base = st.session_state.knowledge_base
    with st.sidebar:
        st.write("Knowledge Base Ready" if index_ready else "Knowledge Base Not Loaded")
        if index_ready and knowledge_base.metrics:
            st.metric("Documents", knowledge_base.metrics["document_count"])
            st.metric("Chunks", knowledge_base.metrics["chunk_count"])
            st.caption(f"Last indexed: {knowledge_base.metrics['indexed_at']}")
    if not index_ready:
        st.info(
            f"Place text-based PDFs in {settings.pdf_directory}/ and select "
            "Refresh Knowledge Base. Scanned/image-only PDFs require OCR elsewhere."
        )
    for number, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                render_answer_metadata(message, number)
    question = st.chat_input(
        "Ask something about your documents...", disabled=not index_ready or llm is None
    )
    if question:
        if len(question) > settings.max_question_characters:
            st.error(
                f"Keep questions within {settings.max_question_characters:,} "
                "characters."
            )
            st.stop()
        history = "\n".join(
            f"{message['role'].capitalize()}: {message['content']}"
            for message in st.session_state.messages[-settings.max_history_messages :]
        )[-settings.max_history_characters :]
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                result = build_query_service(
                    knowledge_base.vectors, llm, settings, top_k
                ).ask_stream(question, history)
                answer = st.write_stream(result.stream)
            except Exception as error:
                safe_error(error, "provider")
                st.info("The response was not saved. Retry the question when ready.")
                st.stop()
            assistant_message = {
                "role": "assistant",
                "content": answer,
                "citations": [asdict(citation) for citation in result.citations],
                "timings": asdict(result.timings),
            }
            number = len(st.session_state.messages) + 1
            render_answer_metadata(assistant_message, number)
        # Commit the turn only after the stream completed successfully.
        st.session_state.messages.extend(
            [{"role": "user", "content": question}, assistant_message]
        )


if __name__ == "__main__":
    main()
