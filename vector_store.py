from __future__ import annotations

import os
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings


DEFAULT_EMBEDDING_MODEL = (
    "sentence-transformers/all-MiniLM-L6-v2"
)


class CodeVectorStore:
    """
    Manage embeddings and the FAISS vector database.

    Source-code chunks are embedded using a Hugging Face
    sentence-transformer model and stored in FAISS together
    with their LangChain metadata.
    """

    def __init__(
        self,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ):
        self.embedding_model_name = embedding_model

        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={
                "device": "cpu",
            },
            encode_kwargs={
                "normalize_embeddings": True,
            },
        )

        self.vector_store: FAISS | None = None

    def create(
        self,
        documents: list[Document],
    ) -> FAISS:
        """
        Create a FAISS index from code documents.
        """
        if not documents:
            raise ValueError(
                "Cannot create a vector database from an empty "
                "document collection."
            )

        self.vector_store = FAISS.from_documents(
            documents,
            self.embeddings,
        )

        return self.vector_store

    def add_documents(
        self,
        documents: list[Document],
    ) -> None:
        """
        Add additional code documents to an existing FAISS index.
        """
        if not documents:
            return

        if self.vector_store is None:
            self.create(documents)
            return

        self.vector_store.add_documents(documents)

    def save(
        self,
        directory: str | Path,
    ) -> None:
        """
        Save the FAISS index locally.
        """
        if self.vector_store is None:
            raise ValueError(
                "No FAISS vector store has been created."
            )

        path = Path(directory)
        path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.vector_store.save_local(
            str(path)
        )

    def load(
        self,
        directory: str | Path,
    ) -> FAISS:
        """
        Load a previously saved FAISS index.

        The index is loaded with the same embedding model that
        was configured for this instance.
        """
        path = Path(directory)

        if not path.exists():
            raise FileNotFoundError(
                f"FAISS directory does not exist: {directory}"
            )

        self.vector_store = FAISS.load_local(
            str(path),
            self.embeddings,
            allow_dangerous_deserialization=True,
        )

        return self.vector_store

    def similarity_search(
        self,
        query: str,
        k: int = 5,
    ) -> list[Document]:
        """
        Perform semantic similarity search.
        """
        if self.vector_store is None:
            raise ValueError(
                "FAISS vector store has not been created."
            )

        if not query.strip():
            raise ValueError(
                "Search query cannot be empty."
            )

        return self.vector_store.similarity_search(
            query,
            k=k,
        )

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
    ) -> list[tuple[Document, float]]:
        """
        Perform semantic search and return similarity scores.
        """
        if self.vector_store is None:
            raise ValueError(
                "FAISS vector store has not been created."
            )

        if not query.strip():
            raise ValueError(
                "Search query cannot be empty."
            )

        return self.vector_store.similarity_search_with_score(
            query,
            k=k,
        )

    def as_retriever(
        self,
        k: int = 5,
    ):
        """
        Return the FAISS vector store as a LangChain retriever.
        """
        if self.vector_store is None:
            raise ValueError(
                "FAISS vector store has not been created."
            )

        return self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={
                "k": k,
            },
        )

    @property
    def document_count(self) -> int:
        """Return the number of indexed vectors."""
        if self.vector_store is None:
            return 0

        return self.vector_store.index.ntotal


def create_vector_store(
    documents: list[Document],
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
) -> CodeVectorStore:
    """
    Convenience function for creating and populating
    a CodeVectorStore.
    """
    store = CodeVectorStore(
        embedding_model=embedding_model,
    )

    store.create(documents)

    return store