"""
DATA-AI 命名上下文存储(ContextStore)

将任意长文本(草稿/笔记/中间结果/项目资产)以"名字+命名空间"形式持久化到 JSON 文件。
与 Memory 系统的区别:
  - Memory:  LLM 短期/长期记忆(消息级别)
  - Context: 人和 Agent 共享的"项目资产"(文档级别)

存储位置: {base_dir}/{namespace}/{name}.json
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)


# ─── 数据类 ──────────────────────────────────────────────


@dataclass
class Context:
    """一条命名上下文"""

    name: str
    namespace: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "namespace": self.namespace,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "history": self.history,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Context:
        return cls(
            name=data["name"],
            namespace=data["namespace"],
            content=data["content"],
            tags=data.get("tags", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            version=data.get("version", 1),
            history=data.get("history", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ContextMeta:
    """上下文元数据(列表用,不含 content)"""

    name: str
    namespace: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    version: int
    size: int  # 字节


# ─── 存储类 ──────────────────────────────────────────────


class ContextStore:
    """
    命名上下文存储

    用法:
        store = ContextStore(base_dir=Path("/workspace/.data-ai/contexts"))
        store.save("main_character", "陈默,28岁...", namespace="novel_red_blue", tags=["character"])
        ctx = store.load("main_character", namespace="novel_red_blue")
        for meta in store.list(namespace="novel_red_blue"):
            print(meta.name)
    """

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            base_dir = Path.home() / ".data-ai" / "contexts"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"ContextStore 初始化: {self.base_dir}")

    # ── 路径解析 ──

    def _file_path(self, name: str, namespace: str) -> Path:
        ns_dir = self.base_dir / _safe(namespace)
        return ns_dir / f"{_safe(name)}.json"

    def _ns_dir(self, namespace: str) -> Path:
        ns_dir = self.base_dir / _safe(namespace)
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir

    # ── CRUD ──

    def save(
        self,
        name: str,
        content: str,
        *,
        namespace: str = "default",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        versioned: bool = True,
    ) -> Context:
        """
        保存/更新上下文。如果已存在,自动追加版本历史。

        Args:
            name: 上下文名
            content: 内容
            namespace: 命名空间(类似文件夹)
            tags: 标签列表
            metadata: 任意附加元数据
            versioned: 是否保留旧版本到 history

        Returns:
            保存后的 Context
        """
        path = self._file_path(name, namespace)
        now = datetime.now()

        if path.exists():
            old = self._read(path)
            ctx = Context.from_dict(old)
            if versioned and ctx.content != content:
                ctx.history.append(
                    {
                        "version": ctx.version,
                        "content": ctx.content,
                        "tags": ctx.tags,
                        "metadata": ctx.metadata,
                        "ts": ctx.updated_at.isoformat(),
                    }
                )
            ctx.content = content
            ctx.tags = tags or ctx.tags
            if metadata:
                ctx.metadata.update(metadata)
            ctx.updated_at = now
            ctx.version += 1
        else:
            ctx = Context(
                name=name,
                namespace=namespace,
                content=content,
                tags=tags or [],
                created_at=now,
                updated_at=now,
                version=1,
                metadata=metadata or {},
            )

        self._write(ctx)
        logger.info(
            f"Context 已保存: {namespace}/{name}",
            namespace=namespace,
            name=name,
            version=ctx.version,
            size=len(content),
        )
        return ctx

    def load(self, name: str, *, namespace: str = "default") -> Context | None:
        """加载上下文,不存在返回 None"""
        path = self._file_path(name, namespace)
        if not path.exists():
            return None
        return Context.from_dict(self._read(path))

    def list(
        self,
        *,
        namespace: str | None = None,
        tag: str | None = None,
    ) -> list[ContextMeta]:
        """列出所有上下文(可按命名空间/标签过滤)"""
        results: list[ContextMeta] = []
        ns_dirs = (
            [self.base_dir / _safe(namespace)] if namespace else list(self.base_dir.iterdir())
        )

        for ns_dir in ns_dirs:
            if not ns_dir.is_dir():
                continue
            for f in ns_dir.glob("*.json"):
                try:
                    ctx = Context.from_dict(self._read(f))
                except Exception as e:
                    logger.warning(f"读取失败: {f}", error=str(e))
                    continue
                if tag and tag not in ctx.tags:
                    continue
                results.append(
                    ContextMeta(
                        name=ctx.name,
                        namespace=ctx.namespace,
                        tags=ctx.tags,
                        created_at=ctx.created_at,
                        updated_at=ctx.updated_at,
                        version=ctx.version,
                        size=len(ctx.content.encode("utf-8")),
                    )
                )

        return sorted(results, key=lambda m: m.updated_at, reverse=True)

    def delete(self, name: str, *, namespace: str = "default") -> bool:
        """删除上下文,返回是否成功"""
        path = self._file_path(name, namespace)
        if path.exists():
            path.unlink()
            logger.info(f"Context 已删除: {namespace}/{name}")
            return True
        return False

    def search(self, query: str, *, namespace: str | None = None) -> list[Context]:
        """
        简单关键字搜索(精确匹配,大小写不敏感)
        注意: 大量数据时应改用 RAG 向量检索,本方法适合中小规模(<1000 条)
        """
        results: list[Context] = []
        query_lower = query.lower()
        for meta in self.list(namespace=namespace):
            ctx = self.load(meta.name, namespace=meta.namespace)
            if ctx and (
                query_lower in ctx.content.lower()
                or query_lower in ctx.name.lower()
                or any(query_lower in t.lower() for t in ctx.tags)
            ):
                results.append(ctx)
        return results

    def history(self, name: str, *, namespace: str = "default") -> list[dict[str, Any]]:
        """获取版本历史(从新到旧)"""
        ctx = self.load(name, namespace=namespace)
        if not ctx:
            return []
        return list(reversed(ctx.history))

    def namespaces(self) -> list[str]:
        """列出所有命名空间"""
        return sorted(d.name for d in self.base_dir.iterdir() if d.is_dir())

    # ── 内部 ──

    def _write(self, ctx: Context) -> None:
        path = self._file_path(ctx.name, ctx.namespace)
        self._ns_dir(ctx.namespace)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ctx.to_dict(), f, ensure_ascii=False, indent=2)

    def _read(self, path: Path) -> dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)


# ─── 工具函数 ────────────────────────────────────────────


def _safe(name: str) -> str:
    """文件系统安全名(替换 / 等特殊字符)"""
    return re.sub(r"[^\w\-\.]", "_", name)


# ─── 全局实例 ────────────────────────────────────────────


_default_store: ContextStore | None = None


def get_context_store(base_dir: Path | str | None = None) -> ContextStore:
    """获取默认 ContextStore(单例)"""
    global _default_store
    if _default_store is None:
        _default_store = ContextStore(base_dir)
    return _default_store
