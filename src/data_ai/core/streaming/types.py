"""
流式处理核心类型定义模块。

本模块定义了流式处理系统所需的所有核心数据结构和类型，
所有 dataclass 使用 ``slots=True`` 以提升性能与内存效率。

主要类型:
- ChatChunk: 流式输出的单块数据（兼容类 OpenAI chunk 结构）
- ChatResponse: 完整累积后的响应
- ToolCallData: 工具调用数据
- StreamingMetrics: 流式处理指标
- ProgressInfo: 进度信息
- StageProgress: 单阶段进度
- UsageRecord: 单次使用记录
- UsageStats: 聚合使用统计
- CancellationToken: 取消令牌
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# 基础块 / 响应模型
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ToolCallData:
    """
    工具调用数据。

    Attributes:
        id: 工具调用唯一标识
        name: 工具名称
        arguments: 工具参数（字符串形式的 JSON 片段，可分块累积）
    """

    id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass(slots=True)
class ChatChunk:
    """
    流式响应块。

    用于表示来自 LLM 的单个流式块，结构尽量兼容 OpenAI 风格。

    Attributes:
        content: 文本内容片段
        role: 角色（system / user / assistant / tool）
        tool_calls: 工具调用列表
        finish_reason: 结束原因（stop / length / tool_calls / None）
        model: 模型名称
        prompt_tokens: 提示 token 计数（通常仅在最终块出现）
        completion_tokens: 完成 token 计数
        total_tokens: 总 token 计数
        is_final: 是否为最后一块
        metadata: 任意附加元数据
    """

    content: str = ""
    role: str = "assistant"
    tool_calls: list[ToolCallData] = field(default_factory=list)
    finish_reason: str | None = None
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    is_final: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse:
    """
    累积完成后的完整响应。

    Attributes:
        content: 完整文本内容
        role: 角色
        tool_calls: 工具调用列表（按 id 聚合后的最终结果）
        finish_reason: 结束原因
        model: 模型名称
        prompt_tokens: 提示 token 数
        completion_tokens: 完成 token 数
        total_tokens: 总 token 数
        chunk_count: 处理的块数
        elapsed_ms: 总耗时（毫秒）
        started_at: 起始时间
        finished_at: 完成时间
        metadata: 任意附加元数据
    """

    content: str = ""
    role: str = "assistant"
    tool_calls: list[ToolCallData] = field(default_factory=list)
    finish_reason: str | None = None
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    chunk_count: int = 0
    elapsed_ms: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "content": self.content,
            "role": self.role,
            "tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
                for tc in self.tool_calls
            ],
            "finish_reason": self.finish_reason,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "chunk_count": self.chunk_count,
            "elapsed_ms": self.elapsed_ms,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# 指标 / 进度
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StreamingMetrics:
    """
    流式处理指标。

    Attributes:
        chunk_count: 处理的块数
        total_tokens: 累计 token 数
        prompt_tokens: 提示 token 数（取最后一次块上报的值）
        completion_tokens: 完成 token 数
        elapsed_ms: 总耗时（毫秒）
        tokens_per_second: 平均吞吐
        first_chunk_latency_ms: 首块延迟（毫秒）
        cancelled: 是否被取消
        completed: 是否正常完成
        errors: 错误数
    """

    chunk_count: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    elapsed_ms: float = 0.0
    tokens_per_second: float = 0.0
    first_chunk_latency_ms: float = 0.0
    cancelled: bool = False
    completed: bool = False
    errors: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_count": self.chunk_count,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "elapsed_ms": self.elapsed_ms,
            "tokens_per_second": round(self.tokens_per_second, 3),
            "first_chunk_latency_ms": round(self.first_chunk_latency_ms, 3),
            "cancelled": self.cancelled,
            "completed": self.completed,
            "errors": self.errors,
        }


@dataclass(slots=True)
class StageProgress:
    """
    单个阶段的进度。

    Attributes:
        name: 阶段名称
        current: 阶段当前步
        total: 阶段总步数
        message: 阶段消息
        started_at: 阶段开始时间戳
        finished_at: 阶段结束时间戳
        finished: 是否已完成
    """

    name: str
    current: int = 0
    total: int = 0
    message: str = ""
    started_at: float = field(default_factory=time.perf_counter)
    finished_at: float = 0.0
    finished: bool = False

    @property
    def percentage(self) -> float:
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.current / self.total) * 100.0)

    @property
    def elapsed_ms(self) -> float:
        end = self.finished_at if self.finished else time.perf_counter()
        return max(0.0, (end - self.started_at) * 1000.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "percentage": self.percentage,
            "elapsed_ms": self.elapsed_ms,
            "finished": self.finished,
        }


@dataclass(slots=True)
class ProgressInfo:
    """
    总体进度信息。

    Attributes:
        stage: 当前阶段名称
        current_step: 当前步骤
        total_steps: 总步骤数
        percentage: 完成百分比 0-100
        message: 进度消息
        elapsed_ms: 已用时间（毫秒）
        eta_ms: 预计剩余时间（毫秒）
        stages: 各子阶段进度
    """

    stage: str = "idle"
    current_step: int = 0
    total_steps: int = 0
    percentage: float = 0.0
    message: str = ""
    elapsed_ms: float = 0.0
    eta_ms: float = 0.0
    stages: list[StageProgress] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "percentage": self.percentage,
            "message": self.message,
            "elapsed_ms": self.elapsed_ms,
            "eta_ms": self.eta_ms,
            "stages": [s.to_dict() for s in self.stages],
        }


# ---------------------------------------------------------------------------
# 使用统计
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class UsageRecord:
    """
    单次使用记录。

    Attributes:
        model: 模型名称
        prompt_tokens: 提示 token
        completion_tokens: 完成 token
        total_tokens: 总 token
        request_id: 请求 ID
        timestamp: 记录时间
        metadata: 任意附加元数据
    """

    model: str
    prompt_tokens: int
    completion_tokens: int
    request_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class UsageStats:
    """
    聚合使用统计。

    Attributes:
        prompt_tokens: 提示 token 总数
        completion_tokens: 完成 token 总数
        total_tokens: 总 token 数
        request_count: 请求次数
        models: 各模型 token 统计（model -> (prompt, completion)）
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0
    models: dict[str, dict[str, int]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "request_count": self.request_count,
            "models": {
                m: {"prompt": v["prompt"], "completion": v["completion"], "total": v["prompt"] + v["completion"]}
                for m, v in self.models.items()
            },
        }


# ---------------------------------------------------------------------------
# 取消令牌
# ---------------------------------------------------------------------------


class CancellationReason(str, Enum):
    """取消原因枚举。"""

    USER_REQUEST = "user_request"
    TIMEOUT = "timeout"
    PARENT_CANCELLED = "parent_cancelled"
    ERROR = "error"
    SHUTDOWN = "shutdown"
    CUSTOM = "custom"


@dataclass(slots=True)
class CancellationToken:
    """
    取消令牌（不可变快照视图）。

    Attributes:
        cancelled: 是否已取消
        reason: 取消原因
        message: 取消消息
        cancelled_at: 取消时间
    """

    cancelled: bool = False
    reason: CancellationReason = CancellationReason.CUSTOM
    message: str = ""
    cancelled_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cancelled": self.cancelled,
            "reason": self.reason.value if isinstance(self.reason, CancellationReason) else str(self.reason),
            "message": self.message,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
        }


# ---------------------------------------------------------------------------
# 类型别名
# ---------------------------------------------------------------------------

ChunkCallback = Callable[[ChatChunk], None]
"""同步块回调。"""

AsyncChunkCallback = Callable[[ChatChunk], "Any"]
"""异步块回调（支持 awaitable 返回值）。"""

ProgressCallback = Callable[[ProgressInfo], None]
"""进度回调。"""
