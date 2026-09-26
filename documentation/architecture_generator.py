from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from retriever import CodeRetriever


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"

DEFAULT_MODEL = "openai/gpt-oss-120b"


class ArchitectureGenerator:
    """Generate an architecture summary from indexed code."""

    def __init__(
        self,
        retriever: CodeRetriever,
        model_name: str = DEFAULT_MODEL,
    ):
        self.retriever = retriever

        self.llm = ChatGroq(
            model=model_name,
            temperature=0.0,
        )

        self.prompt = self._load_prompt(
            "architecture_documentation_prompt.txt"
        )

    def generate(self) -> str:
        """Generate architecture documentation."""

        documents = self.retriever.retrieve_documents(
            "software architecture modules layers "
            "components dependencies imports data flow "
            "entry points services routes"
        )

        context = self._format_documents(
            documents
        )

        if not context:
            raise ValueError(
                "No indexed code is available for architecture generation."
            )

        messages = [
            SystemMessage(
                content=self.prompt
            ),
            HumanMessage(
                content=(
                    "Generate an architecture summary using "
                    "only the retrieved source code below.\n\n"
                    f"{context}"
                )
            ),
        ]

        response = self.llm.invoke(messages)

        return self._extract_text(response)

    @staticmethod
    def _format_documents(documents) -> str:
        sections = []

        for document in documents:
            metadata = document.metadata or {}

            sections.append(
                "\n".join(
                    [
                        f"File: {metadata.get('source', 'unknown')}",
                        f"Language: {metadata.get('language', 'unknown')}",
                        f"Module: {metadata.get('module', 'unknown')}",
                        f"Symbol: {metadata.get('symbol', 'unknown')}",
                        f"Imports: {metadata.get('imports', '')}",
                        "",
                        document.page_content,
                    ]
                )
            )

        return "\n\n".join(sections)

    @staticmethod
    def _extract_text(response) -> str:
        content = getattr(
            response,
            "content",
            response,
        )

        return (
            content
            if isinstance(content, str)
            else str(content)
        )

    @staticmethod
    def _load_prompt(filename: str) -> str:
        path = PROMPTS_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {path}"
            )

        return path.read_text(
            encoding="utf-8"
        ).strip()