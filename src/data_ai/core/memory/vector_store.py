"""
语义向量记忆存储

基于向量相似度的长期记忆存储，支持语义检索。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryEntry:
    """记忆条目"""

    id: str
    content: str
    embedding: list[float]
    category: str = "general"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    access_count: int = 0
    importance: float = 0.5  # 0-1, 重要程度


class SemanticMemoryStore:
    """
    语义记忆存储

    基于向量相似度的记忆存储，支持：
    - 语义相似度检索
    - 时间衰减
    - 重要性排序
    - 持久化存储
    """

    def __init__(
        self,
        storage_dir: str | None = None,
        dimensions: int = 1536,
        decay_factor: float = 0.99,
        max_memories: int = 10000,
    ):
        self._storage_dir = Path(storage_dir or os.path.expanduser("~/.data-ai/memory/semantic"))
        self._dimensions = dimensions
        self._decay_factor = decay_factor
        self._max_memories = max_memories
        self._memories: dict[str, MemoryEntry] = {}
        self._embed_fn: callable | None = None
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def set_embed_fn(self, fn: callable) -> None:
        """设置嵌入函数"""
        self._embed_fn = fn

    def _get_embedding(self, text: str) -> list[float]:
        """获取文本嵌入向量"""
        if self._embed_fn:
            return self._embed_fn(text)
        # 默认伪嵌入
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        emb = [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(self._dimensions)]
        norm = math.sqrt(sum(x * x for x in emb))
        return [x / norm for x in emb] if norm > 0 else emb

    def store(
        self,
        content: str,
        category: str = "general",
        metadata: dict | None = None,
        importance: float = 0.5,
    ) -> str:
        """存储记忆"""
        memory_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12]
        embedding = self._get_embedding(content)

        entry = MemoryEntry(
            id=memory_id,
            content=content,
            embedding=embedding,
            category=category,
            metadata=metadata or {},
            importance=importance,
        )

        self._memories[memory_id] = entry

        # 超过上限时淘汰低重要性的记忆
        if len(self._memories) > self._max_memories:
            self._evict()

        self._save()
        return memory_id

    def recall(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryEntry, float]]:
        """检索记忆"""
        query_emb = self._get_embedding(query)

        scored = []
        for entry in self._memories.values():
            # 类别过滤
            if category and entry.category != category:
                continue

            # 计算相似度
            similarity = self._cosine_similarity(query_emb, entry.embedding)

            # 时间衰减
            age_hours = (time.time() - entry.timestamp) / 3600
            time_decay = self._decay_factor**age_hours

            # 综合分数 = 相似度 * 时间衰减 * 重要性
            score = similarity * time_decay * entry.importance

            if score >= min_score:
                scored.append((entry, score))
                entry.access_count += 1

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search(self, keyword: str, category: str | None = None) -> list[MemoryEntry]:
        """关键词搜索"""
        results = []
        keyword_lower = keyword.lower()

        for entry in self._memories.values():
            if category and entry.category != category:
                continue
            if keyword_lower in entry.content.lower():
                results.append(entry)

        return results

    def delete(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self._memories:
            del self._memories[memory_id]
            self._save()
            return True
        return False

    def update_importance(self, memory_id: str, delta: float) -> bool:
        """更新记忆重要性"""
        entry = self._memories.get(memory_id)
        if entry:
            entry.importance = max(0.0, min(1.0, entry.importance + delta))
            return True
        return False

    def learn_from_interaction(
        self,
        query: str,
        response: str,
        success: bool = True,
    ) -> str:
        """从交互中学习"""
        content = f"Q: {query}\nA: {response}"
        category = "successful_interaction" if success else "failed_interaction"
        importance = 0.7 if success else 0.3

        return self.store(
            content=content,
            category=category,
            metadata={"type": "interaction", "success": success},
            importance=importance,
        )

    def learn_from_error(self, error: str, context: str = "") -> str:
        """从错误中学习"""
        content = f"错误: {error}\n上下文: {context}"
        return self.store(
            content=content,
            category="error",
            metadata={"type": "error"},
            importance=0.6,
        )

    def learn_preference(self, preference: str, category: str = "user_preference") -> str:
        """学习用户偏好"""
        return self.store(
            content=preference,
            category=category,
            metadata={"type": "preference"},
            importance=0.8,
        )

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        categories = {}
        for entry in self._memories.values():
            categories[entry.category] = categories.get(entry.category, 0) + 1

        return {
            "total_memories": len(self._memories),
            "categories": categories,
            "storage_dir": str(self._storage_dir),
        }

    def _evict(self) -> None:
        """淘汰低重要性记忆"""
        if len(self._memories) <= self._max_memories:
            return

        sorted_entries = sorted(
            self._memories.values(),
            key=lambda e: e.importance * (0.5 + 0.5 * (e.access_count / max(e.access_count, 1))),
        )

        to_remove = len(self._memories) - self._max_memories
        for entry in sorted_entries[:to_remove]:
            del self._memories[entry.id]

    def _save(self) -> None:
        """保存到文件"""
        data = {}
        for mid, entry in self._memories.items():
            data[mid] = {
                "content": entry.content,
                "category": entry.category,
                "metadata": entry.metadata,
                "timestamp": entry.timestamp,
                "access_count": entry.access_count,
                "importance": entry.importance,
            }

        file_path = self._storage_dir / "memories.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """从文件加载"""
        file_path = self._storage_dir / "memories.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            for mid, info in data.items():
                entry = MemoryEntry(
                    id=mid,
                    content=info["content"],
                    embedding=self._get_embedding(info["content"]),
                    category=info.get("category", "general"),
                    metadata=info.get("metadata", {}),
                    timestamp=info.get("timestamp", time.time()),
                    access_count=info.get("access_count", 0),
                    importance=info.get("importance", 0.5),
                )
                self._memories[mid] = entry

            logger.info(f"已加载 {len(self._memories)} 条记忆")
        except Exception as e:
            logger.warning(f"加载记忆失败: {e}")

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
