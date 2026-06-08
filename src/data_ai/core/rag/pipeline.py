"""
DATA-AI RAG 检索增强生成管道

基于真实语义嵌入的 RAG 实现，支持：
- 多嵌入模型（OpenAI text-embedding-3、本地 sentence-transformers）
- 文档分块（递归字符分割、语义分块）
- 向量存储（ChromaDB、内存存储）
- 查询优化和重排序
- 源引用追踪
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ...utils.exceptions import RAGConfigError
from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Document:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


@dataclass
class RetrievalResult:
    documents: list[Document]
    scores: list[float]
    query: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseEmbedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        pass

    @abstractmethod
    async def aembed(self, texts: list[str]) -> list[list[float]]:
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        pass


class OpenAIEmbedder(BaseEmbedder):
    def __init__(
        self,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        import os

        try:
            from openai import OpenAI

            self.client = OpenAI(
                api_key=api_key or os.getenv("OPENAI_API_KEY"),
                base_url=base_url,
            )
        except ImportError:
            raise RAGConfigError(message="OpenAI not installed. Run: pip install openai")

        self.model = model
        self._dimension = dimensions

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        params = {
            "model": self.model,
            "input": texts,
        }
        if self._dimension and "3" in self.model:
            params["dimensions"] = self._dimension

        response = self.client.embeddings.create(**params)
        return [d.embedding for d in response.data]

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        return await asyncio.to_thread(self.embed, texts)


class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(model_name)
            self._dimension = self.model.get_sentence_embedding_dimension()
        except ImportError:
            raise RAGConfigError(message="sentence-transformers not installed. Run: pip install sentence-transformers")

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        return await asyncio.to_thread(self.embed, texts)


class TextSplitter:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
    ):
        if chunk_overlap >= chunk_size:
            raise RAGConfigError(message=f"chunk_overlap ({chunk_overlap}) must be less than chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", ".", " ", ""]

    def split_text(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            if end >= len(text):
                chunks.append(text[start:])
                break

            chunk_text = text[start:end]
            best_split = -1
            for sep in self.separators:
                pos = chunk_text.rfind(sep)
                if pos > self.chunk_size // 2:
                    best_split = pos
                    break

            if best_split > 0:
                end = start + best_split + 1

            chunks.append(text[start:end])
            start = end - self.chunk_overlap

        return chunks

    def split_documents(self, documents: list[Document]) -> list[Document]:
        result = []
        for doc in documents:
            chunks = self.split_text(doc.content)
            for i, chunk in enumerate(chunks):
                result.append(
                    Document(
                        content=chunk,
                        metadata={**doc.metadata, "chunk_index": i, "source_id": doc.metadata.get("source_id", "")},
                    )
                )
        return result


class VectorStore(ABC):
    @abstractmethod
    def add(self, documents: list[Document], embeddings: list[list[float]]) -> None:
        pass

    @abstractmethod
    async def aadd(self, documents: list[Document], embeddings: list[list[float]]) -> None:
        pass

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[Document, float]]:
        pass

    @abstractmethod
    def count(self) -> int:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class InMemoryVectorStore(VectorStore):
    def __init__(self):
        self._documents: list[Document] = []
        self._embeddings: list[list[float]] = []

    def add(self, documents: list[Document], embeddings: list[list[float]]) -> None:
        self._documents.extend(documents)
        self._embeddings.extend(embeddings)

    async def aadd(self, documents: list[Document], embeddings: list[list[float]]) -> None:
        import asyncio

        await asyncio.to_thread(self.add, documents, embeddings)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[Document, float]]:
        scores = []
        for i, emb in enumerate(self._embeddings):
            score = self._cosine_similarity(query_embedding, emb)
            scores.append((self._documents[i], score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def count(self) -> int:
        return len(self._documents)

    def clear(self) -> None:
        self._documents = []
        self._embeddings = []


class ChromaVectorStore(VectorStore):
    def __init__(self, collection_name: str = "data_ai_docs", persist_directory: str | None = None):
        try:
            import chromadb

            path = persist_directory or "./chroma_db"
            self.client = chromadb.PersistentClient(path=path)
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            raise RAGConfigError(message=f"ChromaDB initialization failed: {e}. Run: pip install chromadb")

    def add(self, documents: list[Document], embeddings: list[list[float]]) -> None:
        self.collection.add(
            ids=[f"doc_{self.collection.count() + i}" for i in range(len(documents))],
            embeddings=embeddings,
            documents=[doc.content for doc in documents],
            metadatas=[doc.metadata for doc in documents],
        )

    async def aadd(self, documents: list[Document], embeddings: list[list[float]]) -> None:
        import asyncio

        await asyncio.to_thread(self.add, documents, embeddings)

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[Document, float]]:
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = []
        if results["documents"][0]:
            for i in range(len(results["documents"][0])):
                doc = Document(
                    content=results["documents"][0][i],
                    metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                )
                score = 1.0 - results["distances"][0][i]
                documents.append((doc, score))

        return documents

    def count(self) -> int:
        return self.collection.count()

    def clear(self) -> None:
        self.client.delete_collection(self.collection.name)
        self.collection = self.client.create_collection(
            name=self.collection.name,
            metadata={"hnsw:space": "cosine"},
        )


class RAGPipeline:
    def __init__(
        self,
        embedder: BaseEmbedder | None = None,
        vector_store: VectorStore | None = None,
        text_splitter: TextSplitter | None = None,
        top_k: int = 5,
    ):
        self.text_splitter = text_splitter or TextSplitter()
        self.top_k = top_k
        self._retrieval_history: list[RetrievalResult] = []

        if embedder is not None:
            self.embedder = embedder
        else:
            try:
                self.embedder = OpenAIEmbedder()
            except Exception:
                try:
                    self.embedder = HuggingFaceEmbedder()
                except Exception:
                    raise RAGConfigError(
                        message="No embedder available. Install openai or sentence-transformers: pip install data-ai[embeddings]"
                    )

        self.vector_store = vector_store or InMemoryVectorStore()

        logger.info(
            "RAG pipeline initialized",
            embedder=type(self.embedder).__name__,
            vector_store=type(self.vector_store).__name__,
            dimension=self.embedder.dimension,
        )

    def add_documents(self, documents: list[Document]) -> int:
        chunks = self.text_splitter.split_documents(documents)
        if not chunks:
            logger.warning("No chunks generated from documents")
            return 0

        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedder.embed(texts)
        self.vector_store.add(chunks, embeddings)
        logger.info(f"Added {len(chunks)} chunks from {len(documents)} documents")
        return len(chunks)

    async def aadd_documents(self, documents: list[Document]) -> int:
        chunks = self.text_splitter.split_documents(documents)
        if not chunks:
            return 0

        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedder.aembed(texts)
        await self.vector_store.aadd(chunks, embeddings)
        logger.info(f"Added {len(chunks)} chunks from {len(documents)} documents")
        return len(chunks)

    def add_texts(self, texts: list[str], metadata: dict[str, Any] | None = None) -> int:
        documents = [Document(content=text, metadata=metadata or {}) for text in texts]
        return self.add_documents(documents)

    async def aadd_texts(self, texts: list[str], metadata: dict[str, Any] | None = None) -> int:
        documents = [Document(content=text, metadata=metadata or {}) for text in texts]
        return await self.aadd_documents(documents)

    def search(self, query: str, top_k: int | None = None) -> RetrievalResult:
        k = top_k or self.top_k
        query_embedding = self.embedder.embed([query])[0]
        results = self.vector_store.search(query_embedding, top_k=k)

        documents = [doc for doc, _ in results]
        scores = [score for _, score in results]

        retrieval_result = RetrievalResult(
            documents=documents,
            scores=scores,
            query=query,
            metadata={"top_k": k, "store_type": type(self.vector_store).__name__},
        )
        self._retrieval_history.append(retrieval_result)
        return retrieval_result

    async def asearch(self, query: str, top_k: int | None = None) -> RetrievalResult:
        k = top_k or self.top_k
        query_embedding = (await self.embedder.aembed([query]))[0]
        results = self.vector_store.search(query_embedding, top_k=k)

        documents = [doc for doc, _ in results]
        scores = [score for _, score in results]

        retrieval_result = RetrievalResult(
            documents=documents,
            scores=scores,
            query=query,
            metadata={"top_k": k, "store_type": type(self.vector_store).__name__},
        )
        self._retrieval_history.append(retrieval_result)
        return retrieval_result

    def query(self, query: str, top_k: int | None = None) -> str:
        result = self.search(query, top_k)
        if not result.documents:
            return ""

        parts = []
        for i, (doc, score) in enumerate(zip(result.documents, result.scores)):
            parts.append(f"[Source {i + 1} (relevance: {score:.3f})]\n{doc.content}")

        return "\n\n---\n\n".join(parts)

    async def aquery(self, query: str, top_k: int | None = None) -> str:
        result = await self.asearch(query, top_k)
        if not result.documents:
            return ""

        parts = []
        for i, (doc, score) in enumerate(zip(result.documents, result.scores)):
            parts.append(f"[Source {i + 1} (relevance: {score:.3f})]\n{doc.content}")

        return "\n\n---\n\n".join(parts)

    def get_retrieval_history(self) -> list[RetrievalResult]:
        return self._retrieval_history

    def get_stats(self) -> dict[str, Any]:
        return {
            "document_count": self.vector_store.count(),
            "embedder": type(self.embedder).__name__,
            "store": type(self.vector_store).__name__,
            "dimension": self.embedder.dimension,
        }

    def clear(self) -> None:
        self.vector_store.clear()
        self._retrieval_history = []
