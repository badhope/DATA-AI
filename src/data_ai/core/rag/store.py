"""
向量存储

提供多种向量存储后端。
"""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger
from .loader import Document

logger = get_logger(__name__)


@dataclass
class VectorEntry:
    """向量条目"""

    id: str
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """向量存储基类"""

    @abstractmethod
    def add(self, documents: list[Document], embeddings: list[list[float]]) -> list[str]:
        """添加文档和对应的嵌入向量"""
        pass

    @abstractmethod
    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[str, float, dict]]:
        """搜索最相似的文档，返回 [(doc_id, score, metadata), ...]"""
        pass

    @abstractmethod
    def delete(self, ids: list[str]) -> bool:
        """删除文档"""
        pass

    @abstractmethod
    def count(self) -> int:
        """获取文档数量"""
        pass


class InMemoryStore(VectorStore):
    """内存向量存储

    使用内存字典存储向量数据，适合小规模数据集。
    """

    def __init__(self):
        self._entries: dict[str, VectorEntry] = {}
        self._documents: dict[str, Document] = {}

    def add(self, documents: list[Document], embeddings: list[list[float]]) -> list[str]:
        """添加文档到向量存储

        Args:
            documents: 文档列表
            embeddings: 对应的嵌入向量列表

        Returns:
            添加的文档ID列表
        """
        ids = []
        for doc, emb in zip(documents, embeddings):
            doc_id = hashlib.md5(doc.content.encode()).hexdigest()[:12]
            self._entries[doc_id] = VectorEntry(
                id=doc_id,
                content=doc.content,
                embedding=emb,
                metadata=doc.metadata,
            )
            self._documents[doc_id] = doc
            ids.append(doc_id)
        return ids

    # 兼容性别名
    def add_documents(self, documents: list[Document], embeddings: list[list[float]]) -> list[str]:
        """添加文档（兼容性别名）"""
        return self.add(documents, embeddings)

    def similarity_search(self, query_embedding: list[float], top_k: int = 5, k: int | None = None) -> list[Document]:
        """相似度搜索（兼容性别名）

        Args:
            query_embedding: 查询向量
            top_k: 返回数量（优先使用）
            k: 兼容性别名
        """
        top_k = k if k is not None else top_k
        results = self.search(query_embedding, top_k)
        return [self._documents.get(doc_id) for doc_id, _, _ in results if doc_id in self._documents]

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[str, float, dict]]:
        results = []
        for entry in self._entries.values():
            score = self._cosine_similarity(query_embedding, entry.embedding)
            results.append((entry.id, score, entry.metadata))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete(self, ids: list[str]) -> bool:
        for doc_id in ids:
            self._entries.pop(doc_id, None)
        return True

    @property
    def count(self) -> int:
        """返回文档数量"""
        return len(self._entries)

    def get(self, doc_id: str) -> VectorEntry | None:
        return self._entries.get(doc_id)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class FAISSStore(VectorStore):
    """FAISS 向量存储"""

    def __init__(self, index_path: str | None = None, dimension: int = 1536):
        self._index_path = index_path
        self._dimension = dimension
        self._index = None
        self._entries: dict[str, VectorEntry] = {}
        self._id_list: list[str] = []

    def _ensure_index(self):
        if self._index is not None:
            return
        try:
            import faiss

            self._index = faiss.IndexFlatIP(self._dimension)
            # 如果有已保存的索引，加载它
            if self._index_path and Path(self._index_path).exists():
                self._load_index()
        except ImportError:
            raise ImportError("FAISS 存储需要 faiss-cpu: pip install faiss-cpu")

    def add(self, documents: list[Document], embeddings: list[list[float]]) -> list[str]:
        self._ensure_index()
        import faiss
        import numpy as np

        ids = []
        vectors = []

        for doc, emb in zip(documents, embeddings):
            doc_id = hashlib.md5(doc.content.encode()).hexdigest()[:12]
            self._entries[doc_id] = VectorEntry(
                id=doc_id,
                content=doc.content,
                embedding=emb,
                metadata=doc.metadata,
            )
            self._id_list.append(doc_id)
            vectors.append(emb)
            ids.append(doc_id)

        if vectors:
            arr = np.array(vectors, dtype=np.float32)
            # FAISS IndexFlatIP 需要归一化向量
            faiss.normalize_L2(arr)
            self._index.add(arr)

        return ids

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[str, float, dict]]:
        self._ensure_index()
        import faiss
        import numpy as np

        if self._index.ntotal == 0:
            return []

        query = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query)

        scores, indices = self._index.search(query, min(top_k, self._index.ntotal))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._id_list):
                doc_id = self._id_list[idx]
                entry = self._entries.get(doc_id)
                if entry:
                    results.append((doc_id, float(score), entry.metadata))

        return results

    def delete(self, ids: list[str]) -> bool:
        # FAISS 不支持直接删除，需要重建索引
        for doc_id in ids:
            self._entries.pop(doc_id, None)
            if doc_id in self._id_list:
                self._id_list.remove(doc_id)
        return True

    def count(self) -> int:
        return len(self._entries)

    def save(self, path: str | None = None):
        """保存索引到文件"""
        import faiss

        save_path = path or self._index_path
        if not save_path:
            return

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, save_path)

        # 保存元数据
        meta_path = save_path + ".meta.json"
        meta = {
            "id_list": self._id_list,
            "entries": {k: {"content": v.content, "metadata": v.metadata} for k, v in self._entries.items()},
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)

    def _load_index(self):
        """加载已保存的索引"""
        import faiss

        self._index = faiss.read_index(self._index_path)

        meta_path = self._index_path + ".meta.json"
        if Path(meta_path).exists():
            with open(meta_path, encoding="utf-8") as f:
                meta = json.load(f)
            self._id_list = meta["id_list"]
            for k, v in meta["entries"].items():
                self._entries[k] = VectorEntry(
                    id=k,
                    content=v["content"],
                    embedding=[],
                    metadata=v.get("metadata", {}),
                )


class ChromaStore(VectorStore):
    """Chroma 向量存储"""

    def __init__(self, collection_name: str = "data_ai", persist_directory: str | None = None):
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._client = None
        self._collection = None

    def _ensure_client(self):
        if self._collection is not None:
            return
        try:
            import chromadb

            if self._persist_directory:
                self._client = chromadb.PersistentClient(path=self._persist_directory)
            else:
                self._client = chromadb.Client()
            self._collection = self._client.get_or_create_collection(self._collection_name)
        except ImportError:
            raise ImportError("Chroma 存储需要 chromadb: pip install chromadb")

    def add(self, documents: list[Document], embeddings: list[list[float]]) -> list[str]:
        self._ensure_client()

        ids = [hashlib.md5(doc.content.encode()).hexdigest()[:12] for doc in documents]
        self._collection.add(
            ids=ids,
            documents=[doc.content for doc in documents],
            embeddings=embeddings,
            metadatas=[doc.metadata for doc in documents],
        )
        return ids

    def search(self, query_embedding: list[float], top_k: int = 5) -> list[tuple[str, float, dict]]:
        self._ensure_client()

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, self._collection.count()),
        )

        output = []
        if results["ids"] and results["ids"][0]:
            for doc_id, distance, metadata in zip(
                results["ids"][0],
                results["distances"][0],
                results["metadatas"][0],
            ):
                output.append((doc_id, 1.0 - distance, metadata))

        return output

    def delete(self, ids: list[str]) -> bool:
        self._ensure_client()
        self._collection.delete(ids=ids)
        return True

    def count(self) -> int:
        self._ensure_client()
        return self._collection.count()
