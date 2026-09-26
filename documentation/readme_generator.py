from __future__ import annotations

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from retriever import CodeRetriever


BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"

DEFAULT_MODEL = "llama-3.3-70b-versatile"


class READMEGenerator:
    """Generate a README from indexed project code."""

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
            "readme_prompt.txt"
        )

    def generate(self) -> str:
        """Generate README content."""

        documents = self.retriever.retrieve_documents(
            "project overview architecture features setup "
            "dependencies modules entry points usage"
        )

        context = self._format_documents(
            documents
        )

        if not context:
            raise ValueError(
                "No indexed code is available for README generation."
            )

        messages = [
            SystemMessage(
                content=self.prompt
            ),
            HumanMessage(
                content=(
                    "Generate a README using only the "
                    "retrieved project code below.\n\n"
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
                        f"Symbol: {metadata.get('symbol', 'unknown')}",
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