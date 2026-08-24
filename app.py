import os
import time
from json import JSONDecodeError

import streamlit as st
from dotenv import load_dotenv
from index_metadata import (
    build_index_manifest,
    compare_document_manifests,
    discard_persisted_index,
    get_pdf_files,
    get_document_manifest,
    get_pdf_state,
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

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

# ==========================================================
# Constants
# ==========================================================

PDF_DIRECTORY = "research_papers"
FAISS_INDEX_PATH = "faiss_index"
EMBEDDING_PROVIDER = "ollama"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")

# ==========================================================
# LLM
# ==========================================================

llm = (
    ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model=LLM_MODEL,
    )
    if GROQ_API_KEY
    else None
)

# ==========================================================
# Load Existing FAISS Index
# ==========================================================


def load_vector_store(show_error=True):

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
            model="nomic-embed-text:latest",
            base_url=OLLAMA_HOST,
        )

    return st.session_state.embeddings

# ==========================================================
# Build Embeddings
# ==========================================================

def create_vector_embedding(document_changes=None):

    embeddings = get_embedding_model()

    loader = PyPDFDirectoryLoader(PDF_DIRECTORY)

    docs = loader.load()

    if not docs:
        st.session_state.docs = []
        st.session_state.final_documents = []
        st.session_state.vectors = None
        return False

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
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
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



initialize_session_state()

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
    st.session_state.vectors = None
    if (
        isinstance(saved, dict)
        and saved.get("document_manifest", {}).get("documents")
    ):
        discard_persisted_index(FAISS_INDEX_PATH)
        save_metadata(current_state, current_document_manifest)
    st.session_state.startup_message = (
        "Add at least one PDF to research_papers/ to build the knowledge base."
    )
elif needs_rebuild:

    with st.spinner("Indexing research papers..."):

        try:
            if not load_vector_store(show_error=False):
                st.session_state.vectors = None
            create_vector_embedding(document_changes)
        except Exception:
            st.session_state.vectors = None
            st.session_state.startup_message = (
                "Knowledge-base indexing failed. Check the PDF files and "
                "embedding service, then use Refresh Knowledge Base."
            )
else:
    if not load_vector_store(show_error=False):
        with st.spinner("Recovering the knowledge base..."):
            try:
                create_vector_embedding()
            except Exception:
                st.session_state.vectors = None
                st.session_state.startup_message = (
                    "The saved index could not be loaded or rebuilt. "
                    "Use Refresh Knowledge Base after checking the services."
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
        max_value=10,
        value=4,
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
        st.warning("GROQ_API_KEY is not configured. Answers are unavailable.")

    st.write(f"**LLM**")
    st.caption(LLM_MODEL)

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
        len(st.session_state.docs),
    )

    st.metric(
        "Chunks",
        len(st.session_state.final_documents),
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
            len(st.session_state.docs)
        )
    
    with col2:
        st.metric(
            "Chunks",
            len(st.session_state.final_documents)
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

        retriever = st.session_state.vectors.as_retriever(
            search_kwargs={"k": top_k}
        )

        document_chain = create_stuff_documents_chain(
            llm,
            prompt,
        )

        retrieval_chain = create_retrieval_chain(
            retriever,
            document_chain,
        )

        history = build_chat_history()

        with st.chat_message("assistant",
                             avatar="🤖",):

            with st.spinner("Searching documents..."):

                start = time.perf_counter()
                try:
                    response = retrieval_chain.invoke(
                        {
                            "input": user_prompt,
                            "history": history,
                        }
                    )
                except Exception as e:
                    st.error(f"Error while generating response:\n\n{e}")
                    st.stop()
                    
                
                st.session_state.last_sources = response["context"]

                elapsed = time.perf_counter() - start

            answer = response["answer"]

            # ----------------------------
            # Streaming animation
            # ----------------------------

            placeholder = st.empty()

            text = ""

            for word in answer.split():

                text += word + " "

                placeholder.markdown(text)

                time.sleep(0.02)

            st.caption(
                f"⏱ Response Time: {elapsed:.2f} sec"
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
        
        if "last_sources" in st.session_state:
            with st.expander(
                f"📚 Retrieved Sources ({len(response['context'])})",
                expanded=False,
            ):
            
                for i, doc in enumerate(response["context"], start=1):
            
                    st.markdown(f"### 📄 Source {i}")
            
                    col1, col2 = st.columns([3,1])
            
                    with col1:
                        st.write(
                            f"**File:** {os.path.basename(doc.metadata.get('source','Unknown'))}"
                        )
            
                    with col2:
                        if "page" in doc.metadata:
                            st.write(f"**Page:** {doc.metadata['page']+1}")
            
                    st.code(
                        doc.page_content,
                        language=None,
                    )
            
                    st.divider()

