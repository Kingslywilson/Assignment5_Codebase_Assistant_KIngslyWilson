from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from code_loader import CodebaseLoader
from code_parser import CodeParser
from preprocess import CodePreprocessor
from vector_store import CodeVectorStore
from retriever import CodeRetriever
from memory import ConversationMemory
from qa_chain import CodeQAChain
from monitoring import (
    configure_langsmith,
    create_usage_tracker,
    extract_token_usage,
)
from documentation.readme_generator import READMEGenerator
from documentation.api_doc_generator import (
    APIDocumentationGenerator,
)
from documentation.architecture_generator import (
    ArchitectureGenerator,
)


BASE_DIR = Path(__file__).resolve().parent

VECTOR_DB_DIR = BASE_DIR / "vector_db"

load_dotenv()

configure_langsmith()


st.set_page_config(
    page_title="Codebase Assistant",
    page_icon="💻",
    layout="wide",
)


def initialize_state() -> None:
    """Initialize Streamlit session state."""

    defaults = {
        "project_loaded": False,
        "project_path": None,
        "source_files": [],
        "parsed_files": [],
        "documents": [],
        "vector_store": None,
        "retriever": None,
        "memory": ConversationMemory(
            max_turns=10
        ),
        "qa_chain": None,
        "usage_tracker": create_usage_tracker(),
        "project_stats": {},
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_application() -> None:
    """Reset the current project and conversation."""

    st.session_state.project_loaded = False
    st.session_state.project_path = None
    st.session_state.source_files = []
    st.session_state.parsed_files = []
    st.session_state.documents = []
    st.session_state.vector_store = None
    st.session_state.retriever = None
    st.session_state.qa_chain = None
    st.session_state.memory = ConversationMemory(
        max_turns=10
    )
    st.session_state.usage_tracker = create_usage_tracker()
    st.session_state.project_stats = {}

    if VECTOR_DB_DIR.exists():
        for file in VECTOR_DB_DIR.iterdir():
            if file.is_file():
                file.unlink()


def ingest_project(project_path: str) -> None:
    """
    Load, parse, preprocess, embed, and index a project.
    """

    path = Path(project_path)

    if not path.exists():
        raise ValueError(
            f"Project directory does not exist: {project_path}"
        )

    if not path.is_dir():
        raise ValueError(
            "The selected path must be a project directory."
        )

    loader = CodebaseLoader()
    parser = CodeParser()
    preprocessor = CodePreprocessor()
    
    source_files = loader.load_project(
        path
    )

    if not source_files:
        raise ValueError(
            "No supported source files were found "
            "in the selected project."
        )

    parsed_files = parser.parse_many(
        source_files
    )

    documents = preprocessor.create_code_documents(
        parsed_files
    )

    if not documents:
        raise ValueError(
            "No code documents could be created "
            "from the project."
        )

    vector_store = CodeVectorStore()

    vector_store.create(
        documents
    )

    VECTOR_DB_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    vector_store.save(
        VECTOR_DB_DIR
    )

    retriever = CodeRetriever(
        vector_store=vector_store,
        top_k=5,
    )

    memory = ConversationMemory(
        max_turns=10
    )
    usage_tracker = create_usage_tracker()
    
    qa_chain = CodeQAChain(
    retriever=retriever,
    memory=memory,
    usage_tracker=usage_tracker,
)

    st.session_state.project_loaded = True
    st.session_state.project_path = str(path)
    st.session_state.source_files = source_files
    st.session_state.parsed_files = parsed_files
    st.session_state.documents = documents
    st.session_state.vector_store = vector_store
    st.session_state.retriever = retriever
    st.session_state.memory = memory
    st.session_state.qa_chain = qa_chain

    st.session_state.project_stats = {
        "source_files": len(source_files),
        "parsed_files": len(parsed_files),
        "documents": len(documents),
        "vectors": vector_store.document_count,
    }


def get_source_reference(source) -> str:
    """Create a readable source reference."""

    location = source.source

    if (
        source.start_line is not None
        and source.end_line is not None
    ):
        location += (
            f":{source.start_line}"
            f"-{source.end_line}"
        )

    if source.symbol:
        return (
            f"{location} — "
            f"{source.symbol}"
        )

    return location


def render_sources(sources) -> None:
    """Display retrieved source references."""

    if not sources:
        return

    with st.expander(
        f"Sources ({len(sources)})"
    ):
        seen = set()

        for source in sources:
            reference = get_source_reference(
                source
            )

            if reference in seen:
                continue

            seen.add(reference)

            st.markdown(
                f"- `{reference}`"
            )


def sidebar() -> None:
    """Render project controls."""

    with st.sidebar:
        st.header("Codebase Assistant")

        st.markdown(
            "Index a Python or JavaScript project "
            "and ask grounded questions about its code."
        )

        st.divider()

        project_path = st.text_input(
            "Project folder",
            value=(
                st.session_state.project_path
                or ""
            ),
            placeholder=(
                r"F:\assignment gradious\23\sample_projects\python_project"
            ),
        )

        if st.button(
            "Index Project",
            type="primary",
            use_container_width=True,
        ):
            if not project_path.strip():
                st.error(
                    "Please enter a project folder."
                )
            else:
                try:
                    with st.spinner(
                        "Loading and indexing project..."
                    ):
                        ingest_project(
                            project_path.strip()
                        )

                    st.success(
                        "Project indexed successfully."
                    )

                except Exception as exc:
                    st.error(
                        f"Indexing failed: {exc}"
                    )

        if st.session_state.project_loaded:
            st.divider()

            stats = (
                st.session_state.project_stats
            )

            st.subheader("Project Statistics")

            st.metric(
                "Source Files",
                stats.get(
                    "source_files",
                    0,
                ),
            )

            st.metric(
                "Parsed Files",
                stats.get(
                    "parsed_files",
                    0,
                ),
            )

            st.metric(
                "Code Chunks",
                stats.get(
                    "documents",
                    0,
                ),
            )

            st.metric(
                "Vectors",
                stats.get(
                    "vectors",
                    0,
                ),
            )

            st.divider()

            if st.button(
                "Reset",
                use_container_width=True,
            ):
                reset_application()
                st.rerun()

            st.divider()

            st.subheader("Monitoring")

            usage = (
                st.session_state
                .usage_tracker
                .summary()
            )

            st.write(
                f"Requests: {usage['requests']}"
            )

            st.write(
                f"Input tokens: "
                f"{usage['input_tokens']}"
            )

            st.write(
                f"Output tokens: "
                f"{usage['output_tokens']}"
            )

            st.write(
                f"Total tokens: "
                f"{usage['total_tokens']}"
            )


def chat_tab() -> None:
    """Render the conversational QA interface."""

    if not st.session_state.project_loaded:
        st.info(
            "Index a project from the sidebar to start."
        )
        return

    st.subheader("Ask About Your Code")

    for turn in (
        st.session_state.memory.turns
    ):
        with st.chat_message("user"):
            st.write(turn.user)

        with st.chat_message("assistant"):
            st.write(turn.assistant)

    question = st.chat_input(
        "Ask a question about the indexed code..."
    )

    if not question:
        return

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        answer_placeholder = st.empty()
        collected = []

        try:
            for chunk in (
                st.session_state
                .qa_chain
                .stream(question)
            ):
                collected.append(chunk)

                answer_placeholder.markdown(
                    "".join(collected)
                )

            answer = "".join(
                collected
            ).strip()

            if not answer:
                answer = (
                    "This information is not "
                    "available in the indexed codebase."
                )

            answer_placeholder.markdown(
                answer
            )

            results = (
                st.session_state
                .retriever
                .retrieve(question)
            )

            render_sources(results)

        except Exception as exc:
            st.error(
                f"Unable to answer the question: {exc}"
            )


def analysis_tab() -> None:
    """Render specialized code analysis tools."""

    if not st.session_state.project_loaded:
        st.info(
            "Index a project first."
        )
        return

    st.subheader("Code Intelligence")

    analysis_type = st.selectbox(
        "Analysis type",
        [
            "Code Explanation",
            "Bug Analysis",
            "Architecture Analysis",
        ],
    )

    query = st.text_area(
        "Describe what you want to analyze",
        placeholder=(
            "Example: Trace the login flow from "
            "the application entry point."
        ),
    )

    if st.button(
        "Analyze",
        type="primary",
    ):
        if not query.strip():
            st.warning(
                "Please enter an analysis request."
            )
            return

        try:
            with st.spinner(
                "Analyzing indexed code..."
            ):
                if analysis_type == "Code Explanation":
                    response = (
                        st.session_state
                        .qa_chain
                        .explain_code(query)
                    )

                elif analysis_type == "Bug Analysis":
                    response = (
                        st.session_state
                        .qa_chain
                        .analyze_bug(query)
                    )

                else:
                    response = (
                        st.session_state
                        .qa_chain
                        .analyze_architecture(query)
                    )

            st.markdown(
                response.answer
            )

            render_sources(
                response.sources
            )

        except Exception as exc:
            st.error(
                f"Analysis failed: {exc}"
            )


def documentation_tab() -> None:
    """Render documentation generation tools."""

    if not st.session_state.project_loaded:
        st.info(
            "Index a project first."
        )
        return

    st.subheader(
        "Generate Documentation"
    )

    documentation_type = st.selectbox(
        "Documentation type",
        [
            "README",
            "API Documentation",
            "Architecture Summary",
        ],
    )

    if st.button(
        "Generate Documentation",
        type="primary",
    ):
        try:
            with st.spinner(
                "Generating documentation..."
            ):
                retriever = (
                    st.session_state
                    .retriever
                )

                if documentation_type == "README":
                    generator = READMEGenerator(
                        retriever
                    )
                    output_name = (
                        "generated_README.md"
                    )

                elif (
                    documentation_type
                    == "API Documentation"
                ):
                    generator = (
                        APIDocumentationGenerator(
                            retriever
                        )
                    )
                    output_name = (
                        "api_documentation.md"
                    )

                else:
                    generator = (
                        ArchitectureGenerator(
                            retriever
                        )
                    )
                    output_name = (
                        "architecture_summary.md"
                    )

                content = generator.generate()

            output_dir = (
                BASE_DIR / "outputs"
            )

            output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            output_path = (
                output_dir / output_name
            )

            output_path.write_text(
                content,
                encoding="utf-8",
            )

            st.success(
                f"Generated: {output_name}"
            )

            st.download_button(
                label=f"Download {output_name}",
                data=content,
                file_name=output_name,
                mime="text/markdown",
            )

            st.markdown(
                content
            )

        except Exception as exc:
            st.error(
                f"Documentation generation failed: {exc}"
            )


def project_files_tab() -> None:
    """Display indexed source files."""

    if not st.session_state.project_loaded:
        st.info(
            "Index a project first."
        )
        return

    st.subheader(
        "Indexed Source Files"
    )

    for source_file in (
        st.session_state.source_files
    ):
        st.markdown(
            f"- `{source_file.relative_path}` "
            f"({source_file.language})"
        )


def main() -> None:
    """Run the Streamlit application."""

    initialize_state()

    sidebar()

    st.title(
        "💻 Conversational Codebase Assistant"
    )

    st.caption(
        "LangChain + FAISS + Hugging Face + Groq"
    )

    tabs = st.tabs(
        [
            "💬 Chat",
            "🔍 Code Intelligence",
            "📚 Documentation",
            "📁 Project Files",
        ]
    )

    with tabs[0]:
        chat_tab()

    with tabs[1]:
        analysis_tab()

    with tabs[2]:
        documentation_tab()

    with tabs[3]:
        project_files_tab()


if __name__ == "__main__":
    main()