"""
JSON 文件记忆存储（JSONMemory）

将记忆条目序列化到单个 JSON 文件，提供线程安全的 CRUD 与简单关键词检索。
返回的记忆条目使用 :class:`data_ai.core.memory.manager.MemoryEntry`，
便于在 Agent / 工具 / RAG 之间传递。

- :class:`JSONMemory`: 独立可用的记忆后端
- :class:`JSONMemoryPlugin`: 兼容旧插件系统的 BasePlugin 包装
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from ...core.memory.manager import MemoryEntry, MemoryType
from ...utils.logging import get_logger
from .. import BasePlugin, PluginInfo

logger = get_logger(__name__)


# ─── 主类 ──────────────────────────────────────────────────────────────────


class JSONMemory:
    """
    基于 JSON 文件的记忆存储。

    数据以列表形式保存在 ``file_path`` 指定的文件中。每次 ``remember`` /
    ``delete`` / ``clear`` 操作后立即写盘，并通过 :class:`threading.RLock`
    保护并发访问。

    Example:
        >>> import tempfile, os
        >>> from pathlib import Path
        >>> with tempfile.TemporaryDirectory() as tmp:
        ...     mem = JSONMemory(os.path.join(tmp, "memory.json"))
        ...     entry = mem.remember("hello world")
        ...     results = mem.recall("hello")
        ...     len(results) >= 1
        True
    """

    def __init__(self, file_path: str, *, auto_create: bool = True) -> None:
        """
        Args:
            file_path: JSON 文件路径。首次写入时若不存在会自动创建。
            auto_create: 是否在构造时就确保父目录与文件存在。
        """
        self._file_path: Path = Path(file_path).expanduser()
        self._lock = threading.RLock()
        self._entries: list[MemoryEntry] = []
        if auto_create:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ─── 属性 ───────────────────────────────────────────────────────

    @property
    def file_path(self) -> Path:
        return self._file_path

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    # ─── 写入 ───────────────────────────────────────────────────────

    def remember(
        self,
        content: str,
        importance: float = 0.5,
        source: str = "user",
        memory_type: MemoryType = MemoryType.LONG_TERM,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryEntry:
        """
        写入一条记忆。

        Args:
            content: 记忆内容。
            importance: 重要性，范围 0.0 - 1.0。
            source: 来源标识，例如 ``"user"``、``"agent"``。
            memory_type: 记忆类型。
            metadata: 附加元数据。

        Returns:
            新建的 :class:`MemoryEntry` 实例。
        """
        if not isinstance(content, str):
            content = str(content)
        importance = max(0.0, min(1.0, float(importance)))

        entry = MemoryEntry(
            id=self._next_id(),
            content=content,
            memory_type=memory_type,
            importance=importance,
            timestamp=time.time(),
            metadata={"source": source, **(metadata or {})},
        )
        with self._lock:
            self._entries.append(entry)
            self._persist()
        return entry

    # ─── 查询 ───────────────────────────────────────────────────────

    def recall(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """
        简单关键词相关度检索。

        评分字段：content 命中 1.0 分 / token，metadata.source 命中 0.3 分 / token。
        """
        if not query or not query.strip():
            return []
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        with self._lock:
            entries_snapshot = list(self._entries)

        scored: list[tuple[MemoryEntry, float]] = []
        for entry in entries_snapshot:
            score = self._score_entry(entry, query_tokens)
            if score > 0:
                scored.append((entry, score))

        scored.sort(key=lambda pair: (pair[1], pair[0].importance, pair[0].timestamp), reverse=True)
        return [entry for entry, _ in scored[: max(0, top_k)]]

    def get_all(self) -> list[MemoryEntry]:
        """获取全部记忆（最新追加的在末尾）。"""
        with self._lock:
            return list(self._entries)

    def get_by_id(self, entry_id: str) -> MemoryEntry | None:
        """按 ID 获取记忆。"""
        with self._lock:
            for entry in self._entries:
                if entry.id == entry_id:
                    return entry
        return None

    # ─── 删除 ───────────────────────────────────────────────────────

    def delete_by_content(self, content: str) -> bool:
        """
        删除第一条内容完全匹配 ``content`` 的记忆。

        Returns:
            是否至少删除了一条。
        """
        with self._lock:
            for idx, entry in enumerate(self._entries):
                if entry.content == content:
                    del self._entries[idx]
                    self._persist()
                    return True
        return False

    def delete_by_id(self, entry_id: str) -> bool:
        """按 ID 删除记忆。"""
        with self._lock:
            for idx, entry in enumerate(self._entries):
                if entry.id == entry_id:
                    del self._entries[idx]
                    self._persist()
                    return True
        return False

    def clear(self) -> None:
        """清空所有记忆（同时清空磁盘文件内容）。"""
        with self._lock:
            self._entries.clear()
            self._persist()

    # ─── 持久化 / 加载 ──────────────────────────────────────────────

    def _load(self) -> None:
        if not self._file_path.exists():
            # 文件不存在时保持空状态，构造时不主动创建空文件
            return
        try:
            with self._file_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            logger.warning(f"记忆文件 JSON 解析失败 {self._file_path}: {exc}")
            return
        except OSError as exc:
            logger.warning(f"读取记忆文件失败 {self._file_path}: {exc}")
            return

        entries: list[MemoryEntry] = []
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    entries.append(self._dict_to_entry(item))
        elif isinstance(raw, dict):
            # 兼容 { "entries": [...] } 这种格式
            for item in raw.get("entries", []) or []:
                if isinstance(item, dict):
                    entries.append(self._dict_to_entry(item))
        with self._lock:
            self._entries = entries

    def _persist(self) -> None:
        """将内存中的条目写回磁盘。"""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            payload = [self._entry_to_dict(e) for e in self._entries]
            # 原子写入：先写到临时文件，再 rename
            tmp_path = self._file_path.with_suffix(self._file_path.suffix + ".tmp")
            with tmp_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._file_path)
        except OSError as exc:
            logger.error(f"写入记忆文件失败 {self._file_path}: {exc}")

    # ─── 评分 / 工具 ────────────────────────────────────────────────

    _STOPWORDS = {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "of",
        "to",
        "in",
        "on",
        "and",
        "or",
        "for",
        "with",
        "as",
        "by",
        "at",
        "from",
        "的",
        "了",
        "是",
        "在",
        "和",
        "与",
        "或",
        "把",
        "被",
        "对",
        "我",
        "你",
        "他",
    }

    @classmethod
    def _tokenize(cls, text: str) -> list[str]:
        if not text:
            return []
        tokens: list[str] = []
        current = []
        for ch in text:
            if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
                current.append(ch)
            else:
                if current:
                    token = "".join(current).lower()
                    if token and token not in cls._STOPWORDS and len(token) > 1:
                        tokens.append(token)
                    current = []
        if current:
            token = "".join(current).lower()
            if token and token not in cls._STOPWORDS and len(token) > 1:
                tokens.append(token)
        return tokens

    @classmethod
    def _score_entry(cls, entry: MemoryEntry, query_tokens: list[str]) -> float:
        content_tokens = set(cls._tokenize(entry.content))
        metadata = entry.metadata or {}
        source = str(metadata.get("source", "")).lower()

        score = 0.0
        for token in query_tokens:
            if token in content_tokens:
                score += 1.0
            if token and token in entry.content.lower():
                score += 0.3
            if source and token in source:
                score += 0.3
        if entry.importance:
            score *= 0.5 + 0.5 * entry.importance
        return score

    @staticmethod
    def _next_id() -> str:
        return f"mem_{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _entry_to_dict(entry: MemoryEntry) -> dict[str, Any]:
        return {
            "id": entry.id,
            "content": entry.content,
            "memory_type": entry.memory_type.value
            if isinstance(entry.memory_type, MemoryType)
            else str(entry.memory_type),
            "importance": entry.importance,
            "timestamp": entry.timestamp,
            "metadata": dict(entry.metadata or {}),
        }

    @staticmethod
    def _dict_to_entry(data: dict[str, Any]) -> MemoryEntry:
        try:
            mem_type = MemoryType(data.get("memory_type", MemoryType.LONG_TERM.value))
        except ValueError:
            mem_type = MemoryType.LONG_TERM
        return MemoryEntry(
            id=str(data.get("id", "")) or JSONMemory._next_id(),
            content=str(data.get("content", "")),
            memory_type=mem_type,
            importance=float(data.get("importance", 0.5) or 0.0),
            timestamp=float(data.get("timestamp", time.time())),
            metadata=dict(data.get("metadata", {}) or {}),
        )

    def get_stats(self) -> dict[str, Any]:
        """获取记忆统计信息。"""
        with self._lock:
            type_counter: dict[str, int] = {}
            for entry in self._entries:
                key = entry.memory_type.value
                type_counter[key] = type_counter.get(key, 0) + 1
            return {
                "file_path": str(self._file_path),
                "total": len(self._entries),
                "by_type": type_counter,
                "oldest": min((e.timestamp for e in self._entries), default=None),
                "newest": max((e.timestamp for e in self._entries), default=None),
            }


# ─── 兼容旧版 BasePlugin 包装 ─────────────────────────────────────────────


class JSONMemoryPlugin(BasePlugin):
    """
    JSON 文件记忆存储插件（BasePlugin 风格）。

    旧 API 保持可用，但内部使用 :class:`JSONMemory` 实现，并尽量返回
    :class:`MemoryEntry` 兼容对象。
    """

    info = PluginInfo(
        name="json_memory",
        version="0.2.0",
        description="基于 JSON 文件的记忆存储插件",
        author="DATA-AI",
        plugin_type="memory",
    )

    def __init__(self, storage_dir: str | None = None) -> None:
        super().__init__()
        if storage_dir:
            self._memory = JSONMemory(os.path.join(storage_dir, "memory.json"))
        else:
            default_dir = Path.home() / ".data-ai" / "memory"
            default_dir.mkdir(parents=True, exist_ok=True)
            self._memory = JSONMemory(str(default_dir / "memory.json"))

    @property
    def memory(self) -> JSONMemory:
        return self._memory

    async def initialize(self) -> None:
        self._initialized = True
        self.logger.info(f"JSON 记忆插件初始化完成, 文件: {self._memory.file_path}")

    async def cleanup(self) -> None:
        self._initialized = False
        self.logger.info("JSON 记忆插件已清理")

    async def store(
        self,
        category: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = self._memory.remember(
            content=content,
            importance=0.5,
            source=category,
            metadata=metadata,
        )
        return {
            "category": category,
            "id": entry.id,
            "index": len(self._memory) - 1,
            "success": True,
        }

    async def recall(self, category: str, limit: int = 10) -> list[dict[str, Any]]:
        all_entries = self._memory.get_all()
        filtered = [e for e in all_entries if (e.metadata or {}).get("source") == category]
        sliced = filtered[-limit:] if limit > 0 else filtered
        return [
            {
                "category": category,
                "id": e.id,
                "content": e.content,
                "metadata": e.metadata,
                "timestamp": e.timestamp,
            }
            for e in sliced
        ]

    async def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        results = self._memory.recall(query, top_k=limit)
        if category:
            results = [e for e in results if (e.metadata or {}).get("source") == category]
        return [
            {
                "id": e.id,
                "content": e.content,
                "metadata": e.metadata,
                "timestamp": e.timestamp,
            }
            for e in results
        ]

    async def delete(self, category: str, index: int) -> bool:
        entries = [e for e in self._memory.get_all() if (e.metadata or {}).get("source") == category]
        if 0 <= index < len(entries):
            return self._memory.delete_by_id(entries[index].id)
        return False

    def get_stats(self) -> dict[str, int]:
        stats = self._memory.get_stats()
        return {"total": stats["total"], "by_type": stats.get("by_type", {})}


__all__ = ["JSONMemory", "JSONMemoryPlugin"]
