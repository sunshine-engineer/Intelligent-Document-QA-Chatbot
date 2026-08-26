import os
import time
import logging
from json import JSONDecodeError

import streamlit as st
from dotenv import load_dotenv
from index_metadata import (
    build_index_manifest,
    build_index_metrics,
    compare_document_manifests,
    discard_persisted_index,
    get_pdf_files,
    get_document_manifest,
    get_pdf_state,
    is_valid_index_metrics,
    load_index_manifest,
    load_metadata,
    save_faiss_index_atomically,
    save_index_manifest,
    save_metadata,
    verify_index_manifest,
)
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_classic.chains.combine_documents import (
    create_stuff_documents_chain,
)
from langchain_classic.chains import create_retrieval_chain
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app_services import IndexConfig, IndexService
from query_services import ConversationalQueryService
from settings import Settings
from app_errors import ErrorCategory, user_message
from app_logging import configure_logging, log_event, log_exception, new_correlation_id

# ==========================================================
# Page Configuration
# ==========================================================

st.set_page_config(
    page_title="Local RAG Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css():
    with open(".streamlit/style.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True,
        )

load_css()

# ==========================================================
# Load Environment Variables
# ==========================================================

load_dotenv()
configure_logging()

settings = Settings.from_env()
configuration_errors = settings.validate()
log_event(logging.INFO, "application_configuration_loaded", category="configuration",
          llm_model=settings.llm_model, embedding_model=settings.embedding_model,
          pdf_directory=settings.pdf_directory, index_directory=settings.index_directory,
          default_top_k=settings.default_top_k)

# ==========================================================
# Constants
# ==========================================================

EMBEDDING_PROVIDER = "ollama"
PDF_DIRECTORY = str(settings.pdf_directory)
FAISS_INDEX_PATH = str(settings.index_directory)
EMBEDDING_MODEL = settings.embedding_model

# ==========================================================
# LLM
# ==========================================================

llm = (
    ChatGroq(
        groq_api_key=settings.groq_api_key,
        model=settings.llm_model,
    )
    if settings.groq_api_key
    else None
)

# ==========================================================
# Load Existing FAISS Index
# ==========================================================


def load_vector_store(show_error=True):

    try:
        vectors, metrics = index_service.load()
        st.session_state.vectors = vectors
        st.session_state.index_metrics = metrics
        return True
    except Exception:
        if show_error:
            st.error("Saved FAISS index could not be loaded. Rebuild the index.")
        st.session_state.vectors = None
        st.session_state.index_metrics = None
        return False

    if not verify_index_manifest(
        FAISS_INDEX_PATH,
        EMBEDDING_PROVIDER,
        EMBEDDING_MODEL,
    ):
        if show_error:
            st.error("Saved FAISS index verification failed. Rebuild the index.")
        return False

    embeddings = get_embedding_model()

    if not os.path.exists(FAISS_INDEX_PATH):
        return False

    try:

        st.session_state.vectors = FAISS.load_local(
            FAISS_INDEX_PATH,
            embeddings,
            allow_dangerous_deserialization=True,
        )

        manifest = load_index_manifest()
        if manifest and manifest.get("vector_dimension") != getattr(
            st.session_state.vectors.index, "d", None
        ):
            st.session_state.vectors = None
            if show_error:
                st.error("Saved FAISS index dimension verification failed.")
            return False

        metadata = load_metadata()
        metrics = metadata.get("metrics") if isinstance(metadata, dict) else None
        if not is_valid_index_metrics(metrics):
            if show_error:
                st.error("Saved index metrics are unavailable. Rebuild the index.")
            st.session_state.index_metrics = None
            return False
        st.session_state.index_metrics = metrics

        return True

    except Exception:

        if show_error:
            st.error("Saved FAISS index could not be loaded. Rebuild the index.")

    return False

# ==========================================================
# Embedding Model
# ==========================================================

def get_embedding_model():

    if st.session_state.embeddings is None:

        st.session_state.embeddings = OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.ollama_url,
        )

    return st.session_state.embeddings

# ==========================================================
# Build Embeddings
# ==========================================================

index_service = IndexService(
    IndexConfig(
        pdf_directory=PDF_DIRECTORY,
        index_directory=FAISS_INDEX_PATH,
        embedding_provider=EMBEDDING_PROVIDER,
        embedding_model=EMBEDDING_MODEL,
    ),
    embedding_factory=get_embedding_model,
    loader_factory=PyPDFDirectoryLoader,
    splitter_factory=lambda: RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    ),
    faiss_loader=FAISS.load_local,
)

def create_vector_embedding(document_changes=None):

    try:
        vectors, metrics, docs, final_documents = index_service.build(
            document_changes,
            st.session_state.vectors,
        )
        st.session_state.docs = docs
        st.session_state.final_documents = final_documents
        st.session_state.vectors = vectors
        st.session_state.index_metrics = metrics
        st.session_state.startup_message = None
        return True
    except Exception:
        raise

    embeddings = get_embedding_model()

    loader = PyPDFDirectoryLoader(PDF_DIRECTORY)

    docs = loader.load()

    if not docs:
        st.session_state.docs = []
        st.session_state.final_documents = []
        st.session_state.vectors = None
        return False

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    vectors = st.session_state.vectors
    documents_to_embed = docs

    if document_changes and vectors is not None:
        changed_paths = set(document_changes["added"]) | set(
            document_changes["changed"]
        )
        removed_paths = set(document_changes["removed"])
        ids_to_delete = []

        for document_id in vectors.index_to_docstore_id.values():
            document = vectors.docstore.search(document_id)
            source = document.metadata.get("source", "") if document else ""
            source_name = os.path.basename(source)
            if source_name in changed_paths or source_name in removed_paths:
                ids_to_delete.append(document_id)

        if ids_to_delete:
            vectors.delete(ids_to_delete)

        documents_to_embed = [
            document
            for document in docs
            if os.path.basename(document.metadata.get("source", ""))
            in changed_paths
        ]
    else:
        vectors = None

    final_documents = splitter.split_documents(documents_to_embed)

    if vectors is None:
        vectors = FAISS.from_documents(final_documents, embeddings)
    elif final_documents:
        vectors.add_documents(final_documents)

    save_faiss_index_atomically(vectors, FAISS_INDEX_PATH)
    document_manifest = get_document_manifest(PDF_DIRECTORY)
    for document in document_manifest["documents"].values():
        document["status"] = "indexed"
    metrics = build_index_metrics(vectors, document_manifest)
    save_index_manifest(
        build_index_manifest(
            FAISS_INDEX_PATH,
            EMBEDDING_PROVIDER,
            EMBEDDING_MODEL,
            getattr(vectors.index, "d", None),
        )
    )
    save_metadata(
        get_pdf_state(PDF_DIRECTORY),
        document_manifest,
        metrics,
    )

    st.session_state.docs = docs
    st.session_state.final_documents = final_documents
    st.session_state.vectors = vectors
    st.session_state.startup_message = None
    return True


# ==========================================================
# Session State Initialization
# ==========================================================


def initialize_session_state():

    defaults = {
        "messages": [],
        "docs": [],
        "final_documents": [],
        "vectors": None,
        "embeddings": None,
        "startup_message": None,
        "index_metrics": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



initialize_session_state()

if configuration_errors:
    log_event(logging.ERROR, "invalid_configuration", category="configuration",
              error_count=len(configuration_errors))
    st.error("Invalid application configuration:")
    for configuration_error in configuration_errors:
        st.write(f"- {configuration_error}")
    st.stop()

current_state = get_pdf_state(PDF_DIRECTORY)
pdf_files = get_pdf_files(PDF_DIRECTORY)
current_document_manifest = get_document_manifest(PDF_DIRECTORY)

try:
    saved = load_metadata()
except (OSError, JSONDecodeError):
    saved = None

needs_rebuild = (
    not isinstance(saved, dict)
    or saved.get("pdf_state") != current_state
    or not isinstance(saved.get("document_manifest"), dict)
    or not os.path.exists(FAISS_INDEX_PATH)
)
document_changes = compare_document_manifests(
    saved.get("document_manifest") if isinstance(saved, dict) else None,
    current_document_manifest,
)
needs_rebuild = needs_rebuild or any(
    document_changes[key] for key in ("added", "changed", "removed")
)

if not pdf_files:
    log_event(logging.INFO, "knowledge_base_empty", category="ingestion")
    st.session_state.vectors = None
    if (
        isinstance(saved, dict)
        and saved.get("document_manifest", {}).get("documents")
    ):
        discard_persisted_index(FAISS_INDEX_PATH)
        empty_metrics = {
            "schema_version": 1,
            "document_count": 0,
            "chunk_count": 0,
            "per_document_chunk_counts": {},
            "indexed_at": None,
        }
        st.session_state.index_metrics = empty_metrics
        save_metadata(current_state, current_document_manifest, empty_metrics)
    st.session_state.startup_message = (
        "Add at least one PDF to research_papers/ to build the knowledge base."
    )
elif needs_rebuild:
    log_event(logging.INFO, "knowledge_base_rebuild_required", category="indexing",
              added=len(document_changes["added"]), changed=len(document_changes["changed"]),
              removed=len(document_changes["removed"]))

    with st.spinner("Indexing research papers..."):

        try:
            if not load_vector_store(show_error=False):
                st.session_state.vectors = None
            create_vector_embedding(document_changes)
        except Exception as error:
            correlation_id = new_correlation_id()
            log_exception(correlation_id, ErrorCategory.INDEXING.value, error)
            st.session_state.vectors = None
            st.session_state.startup_message = (
                "Knowledge-base indexing failed. Check the PDF files and "
                f"embedding service, then use Refresh Knowledge Base. "
                f"Reference: {correlation_id}."
            )
else:
    log_event(logging.INFO, "saved_index_reload_required", category="indexing")
    if not load_vector_store(show_error=False):
        with st.spinner("Recovering the knowledge base..."):
            try:
                create_vector_embedding()
            except Exception as error:
                correlation_id = new_correlation_id()
                log_exception(correlation_id, ErrorCategory.INDEXING.value, error)
                st.session_state.vectors = None
                st.session_state.startup_message = (
                    "The saved index could not be loaded or rebuilt. "
                    "Use Refresh Knowledge Base after checking the services. "
                    f"Reference: {correlation_id}."
                )


# ==========================================================
# Sidebar
# ==========================================================

with st.sidebar:

    st.title("⚙️ Dashboard")

    st.divider()
    st.subheader("Retrieval Settings")

    top_k = st.slider(
        "Top K Chunks",
        min_value=1,
        max_value=settings.max_top_k,
        value=settings.default_top_k,
    )
    if st.button(
            "🗑 Clear Chat",
            use_container_width=True,
        ):

        st.session_state.messages.clear()
        st.toast("Conversation cleared")
        time.sleep(0.5)
        st.rerun()

    st.subheader("System")

    if llm is None:
        st.warning(
            "GROQ_API_KEY is not configured. Indexing is available, but answers "
            "remain unavailable until the credential is added to .env."
        )

    st.write(f"**LLM**")
    st.caption(settings.llm_model)

    st.write("**Embeddings**")
    st.caption("nomic-embed-text")

    st.write("**Vector Store**")
    st.caption("FAISS")

    st.divider()

    if st.session_state.vectors is not None:

        st.success("Knowledge Base Ready")

    else:

        st.warning("Knowledge Base Not Loaded")

    st.metric(
        "Documents",
        (
            st.session_state.index_metrics.get("document_count", "Unavailable")
            if st.session_state.index_metrics
            else "Unavailable"
        ),
    )

    st.metric(
        "Chunks",
        (
            st.session_state.index_metrics.get("chunk_count", "Unavailable")
            if st.session_state.index_metrics
            else "Unavailable"
        ),
    )

    if st.session_state.index_metrics:
        st.caption(
            f"Last indexed: {st.session_state.index_metrics.get('indexed_at', 'Unavailable')}"
        )

    st.divider()

    if st.button(
        "🔄 Refresh Knowledge Base",
        use_container_width=True,
    ):

        with st.spinner("Refreshing embeddings..."):

            start = time.perf_counter()

            create_vector_embedding()

            elapsed = time.perf_counter() - start

        st.success(
            f"Knowledge Base created in {elapsed:.2f} sec"
        )

    if st.button(
        "📂 Load Saved Index",
        use_container_width=True,
    ):

        with st.spinner("Loading FAISS index..."):

            loaded = load_vector_store()

        if loaded:
            st.success("FAISS index loaded.")

        else:
            st.warning("No saved index found.")


# ==========================================================
# Conversation History Helper
# ==========================================================

def build_chat_history():

    history = ""

    # Exclude the current user message
    previous_messages = st.session_state.messages[:-1]

    for message in previous_messages[-10:]:

        history += (
            f"{message['role'].capitalize()}: "
            f"{message['content']}\n"
        )

    return history

# ==========================================================
# Prompt
# ==========================================================

prompt = ChatPromptTemplate.from_template(
    """
You are a helpful AI Research Assistant.

Use ONLY the retrieved context to answer the question.

If the answer is not present inside the context, say:

"I couldn't find that information in the uploaded documents."

Previous Conversation:

{history}

Retrieved Context:

{context}

Question:

{input}

Instructions:

- Use only the retrieved context.
- If information is missing, clearly say so.
- Never make up facts.
- Quote important values exactly.
- format the output so that its easier to read
- Use bullet points when appropriate.
"""
)


def build_query_service(top_k):
    retriever = st.session_state.vectors.as_retriever(
        search_kwargs={"k": top_k}
    )

    def retrieve(query):
        return retriever.vectorstore.similarity_search_with_relevance_scores(
            query, k=top_k
        )

    def rewrite(history, question):
        rewrite_prompt = ChatPromptTemplate.from_template(
            "Rewrite the follow-up as a standalone search query.\n"
            "Conversation:\n{history}\nFollow-up:\n{question}"
        )
        return llm.invoke(rewrite_prompt.format_messages(
            history=history, question=question
        )).content

    def answer(question, history, documents):
        chain = create_stuff_documents_chain(llm, prompt)
        return chain.invoke({
            "input": question,
            "history": history,
            "context": documents,
        })

    return ConversationalQueryService(
        retriever=retrieve,
        rewriter=rewrite if llm is not None else None,
        answerer=answer,
        relevance_threshold=settings.relevance_threshold,
        max_results=top_k,
    )

# ==========================================================
# Main UI
# ==========================================================

st.title("🤖 Local RAG Assistant")

st.caption(
    "Ask questions about your research papers using Retrieval-Augmented Generation."
)

st.divider()

# ==========================================================
# Welcome Screen
# ==========================================================

if st.session_state.vectors is None:

    if st.session_state.startup_message:
        st.warning(st.session_state.startup_message)

    st.info(
        """
### 👋 Welcome!

This application lets you query your local research papers using a Retrieval-Augmented Generation (RAG) pipeline.

### Current Stack

- Groq Llama 3.1
- Ollama Embeddings
- FAISS Vector Database
- LangChain
- Streamlit

### Getting Started

1. Place PDFs inside:
research_papers/

2. Click **📚 Build Knowledge Base**

3. Wait for embeddings to finish

4. Start chatting with your documents

---
"""
    )

else:
    st.success("✅ Knowledge Base Ready")

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Documents",
            st.session_state.index_metrics.get("document_count", "Unavailable")
        )
    
    with col2:
        st.metric(
            "Chunks",
            st.session_state.index_metrics.get("chunk_count", "Unavailable")
        )
    
    with col3:
        st.metric(
            "Top-K",
            top_k
        )
    
    st.divider()
    
    # ----------------------------
    # Display previous messages
    # ----------------------------

    for message in st.session_state.messages:

        with st.chat_message(message["role"]):

            st.markdown(message["content"])

    user_prompt = st.chat_input(
        "Ask something about your documents..."
    )

    if user_prompt:

        if llm is None:
            st.error("Configure GROQ_API_KEY before asking a question.")
            st.stop()

        # ----------------------------
        # Save user message
        # ----------------------------

        st.session_state.messages.append(
            {
                "role": "user",
                "content": user_prompt,
            }
        )

        with st.chat_message("user",
                             avatar="👤",):

            st.markdown(user_prompt)

        # ----------------------------
        # Build RAG
        # ----------------------------

        history = build_chat_history()

        with st.chat_message("assistant",
                             avatar="🤖",):

            with st.spinner("Searching documents..."):

                correlation_id = new_correlation_id()
                try:
                    query_result = build_query_service(top_k).ask(
                        user_prompt, history, correlation_id
                    )
                except Exception as e:
                    log_exception(correlation_id, ErrorCategory.PROVIDER.value, e)
                    st.error(
                        f"{user_message(e)} Reference: {correlation_id}."
                    )
                    st.stop()
                    
                
                st.session_state.last_citations = query_result.citations

            answer = query_result.answer

            # ----------------------------
            # Render the completed provider response
            # ----------------------------

            st.markdown(answer)

            st.caption(
                f"⏱ Retrieval: {query_result.retrieval_latency_ms:.0f} ms · "
                f"Generation: {query_result.generation_latency_ms:.0f} ms · "
                f"Total: {query_result.total_latency_ms:.0f} ms"
            )

            st.download_button(
                label="📥 Download Response",
                data=answer,
                file_name="rag_response.txt",
                mime="text/plain",
                use_container_width=True,
            )

        # ----------------------------
        # Save assistant message
        # ----------------------------

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        # ----------------------------
        # Sources
        # ----------------------------
        
        if "last_citations" in st.session_state:
            with st.expander(
                f"📚 Retrieved Sources ({len(query_result.citations)})",
                expanded=False,
            ):
            
                for i, citation in enumerate(query_result.citations, start=1):
            
                    st.markdown(f"### 📄 Source {i}")
            
                    col1, col2 = st.columns([3,1])
            
                    with col1:
                        st.write(
                            f"**File:** {os.path.basename(citation.document)}"
                        )
            
                    with col2:
                        if citation.page is not None:
                            st.write(f"**Page:** {citation.page}")
            
                    st.code(
                        citation.excerpt,
                        language=None,
                    )
                    st.caption(
                        f"Chunk: {citation.chunk_id} · Score: {citation.retrieval_score:.3f}"
                    )
            
                    st.divider()

