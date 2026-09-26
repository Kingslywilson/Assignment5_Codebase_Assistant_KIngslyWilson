from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document

from vector_store import CodeVectorStore


@dataclass
class RetrievedCode:
    """Represent one retrieved code chunk."""

    content: str
    source: str
    language: str
    symbol: str
    symbol_type: str
    start_line: int | None
    end_line: int | None
    metadata: dict[str, Any]


class CodeRetriever:
    """
    LangChain-based semantic retriever for source code.

    Retrieval is performed against the FAISS vector store and
    returns source-code chunks together with their metadata.
    """

    def __init__(
        self,
        vector_store: CodeVectorStore,
        top_k: int = 5,
    ):
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        self.vector_store = vector_store
        self.top_k = top_k

        self.retriever = vector_store.as_retriever(
            k=top_k
        )

    def retrieve(
        self,
        query: str,
    ) -> list[RetrievedCode]:
        """
        Retrieve the most relevant code chunks for a query.
        """
        if not query or not query.strip():
            raise ValueError(
                "Retrieval query cannot be empty."
            )

        documents = self.retriever.invoke(
            query.strip()
        )

        return [
            self._convert_document(document)
            for document in documents
        ]

    def retrieve_documents(
        self,
        query: str,
    ) -> list[Document]:
        """
        Return raw LangChain Documents from the retriever.
        """
        if not query or not query.strip():
            raise ValueError(
                "Retrieval query cannot be empty."
            )

        return self.retriever.invoke(
            query.strip()
        )

    def _convert_document(
        self,
        document: Document,
    ) -> RetrievedCode:
        """
        Convert a LangChain Document into a structured
        RetrievedCode object.
        """
        metadata = document.metadata or {}

        return RetrievedCode(
            content=document.page_content,
            source=str(
                metadata.get("source", "unknown")
            ),
            language=str(
                metadata.get("language", "unknown")
            ),
            symbol=str(
                metadata.get("symbol", "unknown")
            ),
            symbol_type=str(
                metadata.get("symbol_type", "unknown")
            ),
            start_line=self._optional_int(
                metadata.get("start_line")
            ),
            end_line=self._optional_int(
                metadata.get("end_line")
            ),
            metadata=metadata,
        )

    @staticmethod
    def _optional_int(
        value: Any,
    ) -> int | None:
        """
        Safely convert metadata values to integers.
        """
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def format_context(
        self,
        results: list[RetrievedCode],
    ) -> str:
        """
        Format retrieved code into grounded context for the LLM.
        """
        if not results:
            return ""

        sections = []

        for index, result in enumerate(
            results,
            start=1,
        ):
            location = result.source

            if (
                result.start_line is not None
                and result.end_line is not None
            ):
                location += (
                    f":{result.start_line}"
                    f"-{result.end_line}"
                )

            sections.append(
                "\n".join(
                    [
                        f"--- SOURCE {index} ---",
                        f"File: {location}",
                        f"Language: {result.language}",
                        f"Symbol: {result.symbol}",
                        f"Symbol Type: {result.symbol_type}",
                        "",
                        result.content,
                        "",
                        f"--- END SOURCE {index} ---",
                    ]
                )
            )

        return "\n\n".join(sections)

    def retrieve_context(
        self,
        query: str,
    ) -> tuple[list[RetrievedCode], str]:
        """
        Retrieve code and return both structured results
        and formatted LLM context.
        """
        results = self.retrieve(query)

        context = self.format_context(
            results
        )

        return results, context


def create_retriever(
    vector_store: CodeVectorStore,
    top_k: int = 5,
) -> CodeRetriever:
    """
    Convenience function for creating a CodeRetriever.
    """
    return CodeRetriever(
        vector_store=vector_store,
        top_k=top_k,
    )