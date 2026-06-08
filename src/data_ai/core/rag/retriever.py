"""
检索器

提供多种检索策略。
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Any

from ...utils.logging import get_logger
from .loader import Document
from .store import VectorStore

logger = get_logger(__name__)


class Retriever(ABC):
    """检索器基类"""

    @abstractmethod
    def retrieve(self, query: str, query_embedding: list[float], top_k: int = 5) -> list[Document]:
        """检索相关文档"""
        pass


class SimilarityRetriever(Retriever):
    """相似度检索器

    P0-4 修复:
    1. 检索后按 score 降序排序,再截 top_k(之前完全没排序,等于随机)
    2. score_threshold 默认改为 -1.0(cosine similarity 范围 [-1,1])
    """

    def __init__(self, store: VectorStore, score_threshold: float = -1.0):
        self.store = store
        self.score_threshold = score_threshold

    def retrieve(
        self, query: str, query_embedding: list[float], top_k: int = 5, k: int | None = None
    ) -> list[Document]:
        """检索相关文档

        Args:
            query: 查询文本
            query_embedding: 查询向量
            top_k: 返回数量（优先使用）
            k: 兼容性别名
        """
        top_k = k if k is not None else top_k
        results = self.store.search(query_embedding, top_k)

        # P0-4 修复: 按 score 降序排
        ranked: list[tuple[float, Any, Any]] = []
        for doc_id, score, metadata in results:
            if score >= self.score_threshold:
                ranked.append((score, doc_id, metadata))
        ranked.sort(key=lambda x: x[0], reverse=True)
        ranked = ranked[:top_k]

        docs = []
        for score, doc_id, metadata in ranked:
            entry = self.store.get(doc_id) if hasattr(self.store, "get") else None
            content = entry.content if entry else ""
            doc = Document(content=content, metadata=dict(metadata or {}))
            # 把 score 透传到 metadata,调用方可读
            doc.metadata = dict(doc.metadata)
            doc.metadata["_score"] = float(score)
            docs.append(doc)

        return docs


class MMRRetriever(Retriever):
    """最大边际相关性检索器（MMR）

    P0-4 修复:
    1. 真用 MMR score 排序选 top_k(之前计算了 score 但没使用)
    2. 用入参 top_k(之前用 self.top_k 永远不变)
    """

    def __init__(self, store: VectorStore, lambda_mult: float = 0.5, top_k: int = 5):
        self.store = store
        self.lambda_mult = lambda_mult
        self.top_k = top_k

    def retrieve(self, query: str, query_embedding: list[float], top_k: int = 5) -> list[Document]:
        # P0-4 修复: 用入参 top_k 而不是 self.top_k
        k = int(top_k or self.top_k)
        # 获取更多候选结果
        candidates = self.store.search(query_embedding, k * 3)

        if not candidates:
            return []

        scored: list[tuple[float, Document]] = []
        for doc_id, _score, metadata in candidates:
            entry = self.store.get(doc_id) if hasattr(self.store, "get") else None
            if not entry:
                continue

            entry_emb = entry.embedding
            if not entry_emb:
                # 没向量的也保留,只是 MMR=0
                doc = Document(content=entry.content, metadata=dict(metadata or {}))
                scored.append((0.0, doc))
                continue

            # 计算 MMR 分数
            relevance = self._cosine_similarity(query_embedding, entry_emb)

            if scored:
                max_similarity = max(
                    self._cosine_similarity(entry_emb, sel_doc.metadata.get("_emb") or [])
                    for _, sel_doc in scored
                )
                diversity = 1 - max_similarity
            else:
                diversity = 0

            # P0-4 修复: 真用这个 mmr_score(之前漏写赋值,代码无效)
            mmr_score = self.lambda_mult * relevance - (1 - self.lambda_mult) * diversity

            doc = Document(content=entry.content, metadata=dict(metadata or {}))
            doc.metadata["_mmr_score"] = float(mmr_score)
            doc.metadata["_relevance"] = float(relevance)
            doc.metadata["_emb"] = entry_emb  # 给下一轮 MMR 用
            scored.append((mmr_score, doc))

        # 按 mmr_score 降序选 top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [doc for _, doc in scored[:k]]

        # 清理 _emb 避免泄漏
        for doc in selected:
            doc.metadata.pop("_emb", None)

        return selected

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
