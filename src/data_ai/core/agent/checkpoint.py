"""
Agent 持久化 Checkpoint(P1-1)

解决问题:
- Agent 长任务中途崩溃/重启后,messages / tool_call_log / reflection_log / iteration_count
  全部丢失,需要重头开始
- 用户主动暂停后想从中断点继续
- 多 Agent 协作时,子 Agent 状态可被父 Agent 检阅

设计:
- AgentCheckpoint dataclass 序列化为 JSON(gzip 压缩)
- AgentCheckpointStore 抽象 + FileCheckpointStore 实现(进程内 + 磁盘)
- 默认存到 ~/.data_ai/checkpoints/{run_id}.json.gz
- BaseAgent.run() 接收外部 run_id,每轮 iteration 结束自动保存
- BaseAgent.resume(run_id) 从 checkpoint 恢复 state,继续 run

P1-1 跟 P1-2 (Human-in-the-Loop) 配合:
- Human approval 暂停时,AgentCheckpoint.status = "awaiting_approval"
- HTTP 端点 /v1/agents/runs/{id}/approve 后调 resume() 继续
"""
from __future__ import annotations

import abc
import asyncio
import gzip
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentCheckpoint:
    """
    Agent 完整可恢复快照

    包含:
    - run_id: 唯一运行 ID
    - created_at / updated_at: 时间戳
    - status: running / awaiting_approval / awaiting_tool_approval / paused / finished / error
    - messages: ChatMessage 列表(系统+用户+助手+tool)
    - iteration_count / reflection_count
    - reflection_log / tool_call_log
    - pending_approval: 待人工审批的 tool_call
    - metadata: 业务元信息(preset_role / preset_name / model)
    """

    run_id: str
    created_at: float
    updated_at: float
    status: str = "running"
    messages: list[dict[str, Any]] = field(default_factory=list)
    iteration_count: int = 0
    reflection_count: int = 0
    reflection_log: list[dict[str, Any]] = field(default_factory=list)
    tool_call_log: list[dict[str, Any]] = field(default_factory=list)
    pending_approval: dict[str, Any] | None = None
    final_content: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AgentCheckpoint:
        # 兼容旧 checkpoint: 缺字段用 default
        return cls(
            run_id=d.get("run_id") or str(uuid.uuid4()),
            created_at=d.get("created_at") or time.time(),
            updated_at=d.get("updated_at") or time.time(),
            status=d.get("status") or "running",
            messages=d.get("messages") or [],
            iteration_count=int(d.get("iteration_count") or 0),
            reflection_count=int(d.get("reflection_count") or 0),
            reflection_log=d.get("reflection_log") or [],
            tool_call_log=d.get("tool_call_log") or [],
            pending_approval=d.get("pending_approval"),
            final_content=d.get("final_content"),
            error=d.get("error"),
            metadata=d.get("metadata") or {},
        )


class AgentCheckpointStore(abc.ABC):
    """Checkpoint 存储抽象"""

    @abc.abstractmethod
    async def save(self, checkpoint: AgentCheckpoint) -> None: ...

    @abc.abstractmethod
    async def load(self, run_id: str) -> AgentCheckpoint | None: ...

    @abc.abstractmethod
    async def delete(self, run_id: str) -> bool: ...

    @abc.abstractmethod
    async def list_runs(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AgentCheckpoint]: ...


class FileCheckpointStore(AgentCheckpointStore):
    """
    文件系统 Checkpoint 存储(默认 ~/.data_ai/checkpoints/*.json.gz)

    P1-1 整改:
    - gzip 压缩(Agent messages 大量 system 指令,压缩比通常 5-10x)
    - 进程内 LRU 缓存(避免同一 run 反复读盘)
    - list_runs 走 mtime 倒序,O(1) 文件名取 run_id
    """

    def __init__(self, base_dir: str | None = None, compress: bool = True):
        self.base_dir = Path(base_dir or os.path.expanduser("~/.data_ai/checkpoints"))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.compress = compress
        self._cache: dict[str, AgentCheckpoint] = {}
        self._cache_lock = asyncio.Lock()
        logger.info(f"FileCheckpointStore 初始化: dir={self.base_dir} compress={compress}")

    def _path(self, run_id: str) -> Path:
        # 防 path traversal: 只允许 [a-zA-Z0-9_-]
        safe = "".join(c for c in run_id if c.isalnum() or c in ("_", "-"))
        if not safe:
            raise ValueError(f"invalid run_id: {run_id!r}")
        ext = ".json.gz" if self.compress else ".json"
        return self.base_dir / f"{safe}{ext}"

    async def save(self, checkpoint: AgentCheckpoint) -> None:
        checkpoint.updated_at = time.time()
        data = json.dumps(checkpoint.to_dict(), ensure_ascii=False, default=str)
        path = self._path(checkpoint.run_id)
        loop = asyncio.get_event_loop()
        # 写盘是 IO 密集,丢到默认 executor
        def _write():
            if self.compress:
                with gzip.open(path, "wt", encoding="utf-8") as f:
                    f.write(data)
            else:
                path.write_text(data, encoding="utf-8")

        await loop.run_in_executor(None, _write)
        async with self._cache_lock:
            self._cache[checkpoint.run_id] = checkpoint
        logger.debug(f"checkpoint saved: run_id={checkpoint.run_id} status={checkpoint.status} bytes={len(data)}")

    async def load(self, run_id: str) -> AgentCheckpoint | None:
        async with self._cache_lock:
            cached = self._cache.get(run_id)
        if cached is not None:
            return cached
        path = self._path(run_id)
        if not path.exists():
            return None
        loop = asyncio.get_event_loop()

        def _read() -> str:
            if self.compress:
                with gzip.open(path, "rt", encoding="utf-8") as f:
                    return f.read()
            return path.read_text(encoding="utf-8")

        raw = await loop.run_in_executor(None, _read)
        d = json.loads(raw)
        cp = AgentCheckpoint.from_dict(d)
        async with self._cache_lock:
            self._cache[run_id] = cp
        return cp

    async def delete(self, run_id: str) -> bool:
        path = self._path(run_id)
        async with self._cache_lock:
            self._cache.pop(run_id, None)
        if not path.exists():
            return False
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, path.unlink)
        return True

    async def list_runs(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[AgentCheckpoint]:
        loop = asyncio.get_event_loop()

        def _scan() -> list[tuple[float, Path]]:
            files = list(self.base_dir.glob("*.json*"))
            return sorted(((p.stat().st_mtime, p) for p in files), key=lambda x: x[0], reverse=True)

        results = await loop.run_in_executor(None, _scan)
        out: list[AgentCheckpoint] = []
        for _mtime, path in results[: max(limit * 3, 100)]:
            try:
                if path.suffix == ".gz":
                    with gzip.open(path, "rt", encoding="utf-8") as f:
                        d = json.loads(f.read())
                else:
                    d = json.loads(path.read_text(encoding="utf-8"))
                cp = AgentCheckpoint.from_dict(d)
                if status and cp.status != status:
                    continue
                out.append(cp)
                if len(out) >= limit:
                    break
            except Exception as exc:  # pragma: no cover
                logger.warning(f"checkpoint 损坏: path={path} err={exc!r}")
                continue
        return out


# ── 模块级默认实例(单例) ───────────────────────────────
_default_store: AgentCheckpointStore | None = None
_store_lock = asyncio.Lock()


def get_checkpoint_store() -> AgentCheckpointStore:
    """获取默认 checkpoint store(单例)"""
    global _default_store
    if _default_store is None:
        _default_store = FileCheckpointStore()
    return _default_store


def set_checkpoint_store(store: AgentCheckpointStore) -> None:
    """覆盖默认 checkpoint store(测试时换内存实现)"""
    global _default_store
    _default_store = store


__all__ = [
    "AgentCheckpoint",
    "AgentCheckpointStore",
    "FileCheckpointStore",
    "get_checkpoint_store",
    "set_checkpoint_store",
]
