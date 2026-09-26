from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from code_parser import ParsedFile, ParsedSymbol


@dataclass
class ChunkingConfig:
    """
    Configuration for code-aware chunking.

    Logical symbols are kept together whenever possible.
    The recursive splitter is used only when a symbol or module
    exceeds the configured chunk size.
    """

    chunk_size: int = 1200
    chunk_overlap: int = 150


class CodePreprocessor:
    """
    Convert parsed source-code structures into LangChain Documents.

    The preprocessing strategy is:

        ParsedFile
            ↓
        ParsedSymbol
            ↓
        Logical code chunk
            ↓
        Recursive fallback splitting
            ↓
        LangChain Document + metadata
    """

    def __init__(
        self,
        config: ChunkingConfig | None = None,
    ):
        self.config = config or ChunkingConfig()

        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                "    ",
                "    ",
                " ",
                "",
            ],
        )

    def process(
        self,
        parsed_files: Iterable[ParsedFile],
    ) -> list[Document]:
        """
        Convert parsed files into LangChain Documents.
        """
        documents: list[Document] = []

        for parsed_file in parsed_files:
            documents.extend(
                self._process_file(parsed_file)
            )

        return documents

    def _process_file(
        self,
        parsed_file: ParsedFile,
    ) -> list[Document]:
        documents: list[Document] = []

        if not parsed_file.symbols:
            documents.append(
                self._create_file_document(
                    parsed_file
                )
            )

            return documents

        for symbol in parsed_file.symbols:
            documents.extend(
                self._process_symbol(
                    parsed_file,
                    symbol,
                )
            )

        return documents

    def _process_symbol(
        self,
        parsed_file: ParsedFile,
        symbol: ParsedSymbol,
    ) -> list[Document]:
        content = symbol.content.strip()

        if not content:
            return []

        metadata = self._build_metadata(
            parsed_file,
            symbol,
        )

        # Preserve meaningful functions/classes/modules as a single
        # logical chunk when they fit within the configured size.
        if len(content) <= self.config.chunk_size:
            return [
                Document(
                    page_content=content,
                    metadata=metadata,
                )
            ]

        # Large logical structures are split recursively.
        split_documents = self.fallback_splitter.create_documents(
            [content],
            metadatas=[metadata],
        )

        for index, document in enumerate(
            split_documents,
            start=1,
        ):
            document.metadata["chunk_number"] = index
            document.metadata["chunk_count"] = len(
                split_documents
            )

        return split_documents

    def _create_file_document(
        self,
        parsed_file: ParsedFile,
    ) -> Document:
        metadata = {
            "source": parsed_file.source,
            "file_name": parsed_file.file_name,
            "language": parsed_file.language,
            "module": parsed_file.module,
            "file_type": parsed_file.language,
            "symbol": parsed_file.file_name,
            "symbol_type": "file",
        }

        return Document(
            page_content=parsed_file.content,
            metadata=metadata,
        )

    def _build_metadata(
        self,
        parsed_file: ParsedFile,
        symbol: ParsedSymbol,
    ) -> dict:
        metadata = {
            "source": symbol.source,
            "file_name": symbol.file_name,
            "language": symbol.language,
            "module": symbol.module,
            "file_type": parsed_file.language,
            "symbol": symbol.name,
            "symbol_type": symbol.symbol_type,
            "signature": symbol.signature,
            "parameters": ", ".join(symbol.parameters),
            "parent": symbol.parent or "",
            "start_line": symbol.start_line or 0,
            "end_line": symbol.end_line or 0,
        }

        if symbol.docstring:
            metadata["docstring"] = symbol.docstring

        if symbol.route:
            metadata["route"] = symbol.route

        if symbol.http_method:
            metadata["http_method"] = symbol.http_method

        if symbol.imports:
            metadata["imports"] = ", ".join(symbol.imports)

        return metadata


def create_code_documents(
    parsed_files: list[ParsedFile],
    config: ChunkingConfig | None = None,
) -> list[Document]:
    """
    Convenience function for converting parsed source files
    into LangChain Documents.
    """
    preprocessor = CodePreprocessor(config)
    return preprocessor.process(parsed_files)