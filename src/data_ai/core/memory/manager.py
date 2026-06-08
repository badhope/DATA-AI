"""
DATA-AI 记忆管理器

基于 LLM 的分层记忆系统，支持：
- 会话记忆（短期对话历史）
- 语义记忆（长期知识存储）
- 摘要记忆（对话摘要压缩）
- 向量化语义检索
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


class MemoryType(Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    SEMANTIC = "semantic"
    EPISODIC = "episodic"


@dataclass
class MemoryEntry:
    id: str
    content: str
    memory_type: MemoryType = MemoryType.SHORT_TERM
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "timestamp": self.timestamp,
            "importance": self.importance,
            "metadata": self.metadata,
        }


class MemoryStore:
    def __init__(self, max_short_term: int = 100, max_long_term: int = 1000):
        self.max_short_term = max_short_term
        self.max_long_term = max_long_term
        self._short_term: list[MemoryEntry] = []
        self._long_term: list[MemoryEntry] = []
        self._semantic: dict[str, MemoryEntry] = {}
        self._counter: int = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"mem_{self._counter}_{int(time.time() * 1000)}"

    def add(self, entry: MemoryEntry) -> None:
        if entry.memory_type == MemoryType.SHORT_TERM:
            self._short_term.append(entry)
            if len(self._short_term) > self.max_short_term:
                self._short_term.pop(0)
        elif entry.memory_type == MemoryType.LONG_TERM:
            self._long_term.append(entry)
            if len(self._long_term) > self.max_long_term:
                self._long_term.pop(0)
        elif entry.memory_type == MemoryType.SEMANTIC:
            self._semantic[entry.id] = entry

    def add_short_term(self, content: str, importance: float = 0.5, **kwargs) -> MemoryEntry:
        entry = MemoryEntry(
            id=self._next_id(),
            content=content,
            memory_type=MemoryType.SHORT_TERM,
            importance=importance,
            metadata=kwargs,
        )
        self.add(entry)
        return entry

    def add_long_term(self, content: str, importance: float = 0.7, **kwargs) -> MemoryEntry:
        entry = MemoryEntry(
            id=self._next_id(),
            content=content,
            memory_type=MemoryType.LONG_TERM,
            importance=importance,
            metadata=kwargs,
        )
        self.add(entry)
        return entry

    def get_short_term(self, limit: int = 20) -> list[MemoryEntry]:
        return sorted(
            self._short_term,
            key=lambda x: (x.importance, x.timestamp),
            reverse=True,
        )[:limit]

    def get_long_term(self, limit: int = 50) -> list[MemoryEntry]:
        return sorted(
            self._long_term,
            key=lambda x: (x.importance, x.timestamp),
            reverse=True,
        )[:limit]

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        query_lower = query.lower()
        results = []
        for entry in self._long_term + self._short_term:
            if query_lower in entry.content.lower():
                results.append(entry)
        results.sort(key=lambda x: x.importance, reverse=True)
        return results[:limit]

    def get_all(self) -> list[MemoryEntry]:
        return self._short_term + self._long_term + list(self._semantic.values())

    def clear_short_term(self) -> None:
        self._short_term = []

    def clear_all(self) -> None:
        self._short_term = []
        self._long_term = []
        self._semantic = {}

    def get_stats(self) -> dict[str, Any]:
        return {
            "short_term_count": len(self._short_term),
            "long_term_count": len(self._long_term),
            "semantic_count": len(self._semantic),
            "total": len(self._short_term) + len(self._long_term) + len(self._semantic),
        }


class MemoryManager:
    def __init__(self, store: MemoryStore | None = None):
        self.store = store or MemoryStore()

    def remember(
        self, content: str, importance: float = 0.5, memory_type: MemoryType = MemoryType.SHORT_TERM, **kwargs
    ) -> MemoryEntry:
        if memory_type == MemoryType.LONG_TERM:
            return self.store.add_long_term(content, importance, **kwargs)
        return self.store.add_short_term(content, importance, **kwargs)

    def recall_short_term(self, limit: int = 20) -> str:
        entries = self.store.get_short_term(limit)
        if not entries:
            return ""
        parts = []
        for entry in entries:
            parts.append(f"[{entry.memory_type.value}] {entry.content}")
        return "\n".join(parts)

    def recall_long_term(self, limit: int = 50) -> str:
        entries = self.store.get_long_term(limit)
        if not entries:
            return ""
        parts = []
        for entry in entries:
            parts.append(f"[{entry.memory_type.value}] {entry.content}")
        return "\n".join(parts)

    def recall_relevant(self, query: str, limit: int = 10) -> str:
        entries = self.store.search(query, limit)
        if not entries:
            return ""
        parts = []
        for entry in entries:
            parts.append(f"[{entry.memory_type.value}] {entry.content}")
        return "\n".join(parts)

    async def summarize(
        self,
        llm_manager=None,
        model: str | None = None,
        max_summary_tokens: int = 500,
    ) -> str:
        entries = self.store.get_short_term(limit=50)
        if not entries:
            return ""

        memory_text = "\n".join([entry.content for entry in entries])

        if llm_manager is None:
            summary = self._summarize_fallback(memory_text)
            if summary:
                self.store.add_long_term(
                    content=f"Summary: {summary}",
                    importance=0.8,
                    summary_time=time.time(),
                )
                self.store.clear_short_term()
            return summary

        try:
            from ..llm.manager import ChatMessage

            messages = [
                ChatMessage(
                    role="system",
                    content=f"You are a conversation summarizer. Summarize the following conversation history into a concise summary. Focus on key decisions, facts, context, and user preferences. Keep it under {max_summary_tokens} words.",
                ),
                ChatMessage(
                    role="user",
                    content=f"Summarize this conversation:\n\n{memory_text}",
                ),
            ]

            response = await llm_manager.chat(messages, model=model)
            summary = response.content

            self.store.add_long_term(
                content=f"Summary: {summary}",
                importance=0.9,
                summary_time=time.time(),
            )

            self.store.clear_short_term()
            return summary

        except Exception as e:
            logger.warning(f"LLM summarization failed, using fallback: {e}")
            return self._summarize_fallback(memory_text)

    def _summarize_fallback(self, text: str) -> str:
        sentences = text.replace("。", "。\n").replace(".", ".\n").split("\n")
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        if len(sentences) > 10:
            sentences = sentences[:5] + sentences[-5:]
        return " ".join(sentences)

    def clear(self) -> None:
        self.store.clear_all()

    def get_stats(self) -> dict[str, Any]:
        return self.store.get_stats()


_memory_manager = MemoryManager()


def get_memory_manager() -> MemoryManager:
    return _memory_manager
