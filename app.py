from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

from code_loader import CodebaseLoader
from code_parser import CodeParser
from preprocess import CodePreprocessor
from vector_store import CodeVectorStore
from retriever import CodeRetriever
from memory import ConversationMemory
from qa_chain import CodeQAChain
from monitoring import configure_langsmith, create_usage_tracker
from documentation.readme_generator import READMEGenerator
from documentation.api_doc_generator import APIDocumentationGenerator
from documentation.architecture_generator import ArchitectureGenerator


BASE_DIR = Path(__file__).resolve().parent
VECTOR_DB_DIR = BASE_DIR / "vector_db"
OUTPUT_DIR = BASE_DIR / "outputs"


class CodebaseAssistantApp:
    """Normal Python CLI application for the conversational codebase assistant."""

    def __init__(self) -> None:
        self.project_loaded = False
        self.project_path: Path | None = None
        self.source_files = []
        self.parsed_files = []
        self.documents = []
        self.vector_store: CodeVectorStore | None = None
        self.retriever: CodeRetriever | None = None
        self.memory = ConversationMemory(max_turns=10)
        self.usage_tracker = create_usage_tracker()
        self.qa_chain: CodeQAChain | None = None

    def index_project(self, project_path: str) -> None:
        """Load, parse, preprocess, embed, and index a project."""
        path = Path(project_path).expanduser().resolve()

        if not path.exists():
            raise ValueError(f"Project directory does not exist: {path}")
        if not path.is_dir():
            raise ValueError("The selected path must be a project directory.")

        print("\n[1/6] Discovering source files...")
        loader = CodebaseLoader()
        parser = CodeParser()
        preprocessor = CodePreprocessor()

        source_files = loader.load_project(path)
        if not source_files:
            raise ValueError("No supported source files were found in the selected project.")
        print(f"      Found {len(source_files)} supported source files.")

        print("[2/6] Parsing source code...")
        parsed_files = parser.parse_many(source_files)
        print(f"      Parsed {len(parsed_files)} files.")

        print("[3/6] Creating code-aware chunks...")
        documents = preprocessor.process(parsed_files)
        if not documents:
            raise ValueError("No code documents could be created from the project.")
        print(f"      Created {len(documents)} code chunks.")

        print("[4/6] Generating embeddings and creating FAISS index...")
        vector_store = CodeVectorStore()
        vector_store.create(documents)

        print("[5/6] Saving FAISS index...")
        VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        vector_store.save(VECTOR_DB_DIR)

        print("[6/6] Creating semantic retriever and QA chain...")
        retriever = CodeRetriever(vector_store=vector_store, top_k=5)
        memory = ConversationMemory(max_turns=10)
        usage_tracker = create_usage_tracker()
        qa_chain = CodeQAChain(
            retriever=retriever,
            memory=memory,
            usage_tracker=usage_tracker,
        )

        self.project_loaded = True
        self.project_path = path
        self.source_files = source_files
        self.parsed_files = parsed_files
        self.documents = documents
        self.vector_store = vector_store
        self.retriever = retriever
        self.memory = memory
        self.usage_tracker = usage_tracker
        self.qa_chain = qa_chain

        print("\nProject indexed successfully.")
        print(f"  Project: {path}")
        print(f"  Source files: {len(source_files)}")
        print(f"  Parsed files: {len(parsed_files)}")
        print(f"  Code chunks: {len(documents)}")
        print(f"  Vectors: {vector_store.document_count}")

    def require_project(self) -> None:
        if not self.project_loaded or self.qa_chain is None or self.retriever is None:
            raise RuntimeError("Index a project first.")

    @staticmethod
    def print_sources(sources) -> None:
        if not sources:
            return

        print("\nSources:")
        seen = set()
        for source in sources:
            location = source.source
            if source.start_line is not None and source.end_line is not None:
                location += f":{source.start_line}-{source.end_line}"
            reference = f"{location} — {source.symbol}" if source.symbol else location
            if reference not in seen:
                print(f"  - {reference}")
                seen.add(reference)

    def ask(self, question: str, stream: bool = True) -> None:
        self.require_project()
        assert self.qa_chain is not None

        print("\nAssistant:")
        if stream:
            print("  ", end="", flush=True)
            chunks = []
            for chunk in self.qa_chain.stream(question):
                chunks.append(chunk)
                print(chunk, end="", flush=True)
            print()
            # Retrieve sources after streaming, matching the same query.
            results = self.retriever.retrieve(question)  # type: ignore[union-attr]
            self.print_sources(results)
        else:
            response = self.qa_chain.ask(question)
            print(response.answer)
            self.print_sources(response.sources)

    def specialized(self, mode: str, question: str) -> None:
        self.require_project()
        assert self.qa_chain is not None

        methods = {
            "explain": self.qa_chain.explain_code,
            "bug": self.qa_chain.analyze_bug,
            "architecture": self.qa_chain.analyze_architecture,
        }
        response = methods[mode](question)
        print("\nAssistant:")
        print(response.answer)
        self.print_sources(response.sources)

    def generate_documentation(self, doc_type: str) -> Path:
        self.require_project()
        assert self.retriever is not None

        generators = {
            "readme": (READMEGenerator, "generated_README.md"),
            "api": (APIDocumentationGenerator, "api_documentation.md"),
            "architecture": (ArchitectureGenerator, "architecture_summary.md"),
        }
        generator_class, filename = generators[doc_type]
        print(f"\nGenerating {doc_type} documentation...")
        content = generator_class(self.retriever).generate()

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / filename
        output_path.write_text(content, encoding="utf-8")

        print(f"Generated: {output_path}")
        return output_path

    def show_stats(self) -> None:
        self.require_project()
        print("\nProject Statistics")
        print(f"  Project: {self.project_path}")
        print(f"  Source files: {len(self.source_files)}")
        print(f"  Parsed files: {len(self.parsed_files)}")
        print(f"  Code chunks: {len(self.documents)}")
        print(f"  Vectors: {self.vector_store.document_count if self.vector_store else 0}")
        usage = self.usage_tracker.summary()
        print(f"  LLM requests: {usage['requests']}")
        print(f"  Input tokens: {usage['input_tokens']}")
        print(f"  Output tokens: {usage['output_tokens']}")
        print(f"  Total tokens: {usage['total_tokens']}")
        print(f"  Conversation turns: {self.memory.turn_count}")

    def list_files(self) -> None:
        self.require_project()
        print("\nIndexed Source Files:")
        for source_file in self.source_files:
            print(f"  - {source_file.relative_path} ({source_file.language})")

    def reset(self) -> None:
        self.project_loaded = False
        self.project_path = None
        self.source_files = []
        self.parsed_files = []
        self.documents = []
        self.vector_store = None
        self.retriever = None
        self.memory = ConversationMemory(max_turns=10)
        self.usage_tracker = create_usage_tracker()
        self.qa_chain = None

        if VECTOR_DB_DIR.exists():
            shutil.rmtree(VECTOR_DB_DIR)

        print("Application state reset.")

    def interactive(self) -> None:
        print("=" * 70)
        print("Conversational Codebase Assistant")
        print("Python + LangChain + FAISS + Hugging Face + Groq")
        print("=" * 70)
        print("Type 'help' to see commands. Type 'exit' to quit.")

        while True:
            try:
                command = input("\ncodebase> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not command:
                continue

            if command.lower() in {"exit", "quit", "q"}:
                print("Goodbye.")
                break

            try:
                self.handle_command(command)
            except Exception as exc:
                print(f"Error: {exc}")

    def handle_command(self, command: str) -> None:
        parts = command.split(maxsplit=1)
        action = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if action == "help":
            print(
                "\nCommands:\n"
                "  index <project-folder>       Index a Python/JavaScript project\n"
                "  ask <question>               Ask a grounded codebase question\n"
                "  explain <question>           Explain code\n"
                "  bug <question>               Investigate a possible bug\n"
                "  architecture <question>     Analyze architecture\n"
                "  docs readme                  Generate README\n"
                "  docs api                     Generate API documentation\n"
                "  docs architecture            Generate architecture summary\n"
                "  files                        List indexed source files\n"
                "  stats                        Show project and token statistics\n"
                "  reset                        Clear the current project and memory\n"
                "  exit                         Quit the application"
            )
            return

        if action == "index":
            if not argument:
                raise ValueError("Usage: index <project-folder>")
            self.index_project(argument)
            return

        if action == "ask":
            if not argument:
                raise ValueError("Usage: ask <question>")
            self.ask(argument, stream=True)
            return

        if action in {"explain", "bug", "architecture"}:
            if not argument:
                raise ValueError(f"Usage: {action} <question>")
            self.specialized(action, argument)
            return

        if action == "docs":
            if argument.lower() not in {"readme", "api", "architecture"}:
                raise ValueError("Usage: docs readme|api|architecture")
            self.generate_documentation(argument.lower())
            return

        if action == "files":
            self.list_files()
            return

        if action == "stats":
            self.show_stats()
            return

        if action == "reset":
            self.reset()
            return

        raise ValueError("Unknown command. Type 'help' for available commands.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Conversational Codebase Assistant using Python and LangChain."
    )
    parser.add_argument(
        "--project",
        help="Project folder to index before entering interactive mode.",
    )
    parser.add_argument(
        "--question",
        help="Ask one question after indexing the project and exit.",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming for --question.",
    )
    return parser


def main() -> None:
    """Run the normal Python command-line application."""
    load_dotenv()
    configure_langsmith()

    parser = build_parser()
    args = parser.parse_args()

    app = CodebaseAssistantApp()

    if args.project:
        app.index_project(args.project)

        if args.question:
            app.ask(args.question, stream=not args.no_stream)
            return

    app.interactive()


if __name__ == "__main__":
    main()
