"""
流式处理系统模块。

本模块汇总流式处理相关的核心组件:
- 类型定义 (:mod:`types`)
- 流式处理器 (:mod:`processor`)
- 进度管理 (:mod:`progress`)
- 取消机制 (:mod:`cancellation`)
- 使用统计 (:mod:`usage`)

Example:
    >>> from data_ai.core.streaming import StreamingProcessor, ChatChunk
    >>>
    >>> async def gen():
    ...     for w in ["Hello", " ", "world"]:
    ...         yield ChatChunk(content=w)
    ...
    >>> processor = StreamingProcessor(model="gpt-4", request_id="r1")
    >>> response = await processor.process_stream(gen())
    >>> response.content
    'Hello world'
"""

from .cancellation import CancellationHandler
from .processor import StreamingProcessor
from .progress import ProgressTracker
from .types import (
    AsyncChunkCallback,
    ChatChunk,
    ChatResponse,
    ChunkCallback,
    ProgressCallback,
    ProgressInfo,
    StageProgress,
    StreamingMetrics,
    ToolCallData,
    UsageRecord,
    UsageStats,
)
from .usage import UsageTracker

# 向后兼容：保留旧的 dataclass 别名（如果外部代码仍然引用）
try:
    from .types import CancellationReason, CancellationToken
except ImportError:  # pragma: no cover
    CancellationReason = None  # type: ignore
    CancellationToken = None  # type: ignore


__all__ = [
    # 类型
    "ChatChunk",
    "ChatResponse",
    "ToolCallData",
    "StreamingMetrics",
    "ProgressInfo",
    "StageProgress",
    "UsageRecord",
    "UsageStats",
    "CancellationToken",
    "CancellationReason",
    "ChunkCallback",
    "AsyncChunkCallback",
    "ProgressCallback",
    # 组件
    "StreamingProcessor",
    "ProgressTracker",
    "CancellationHandler",
    "UsageTracker",
]


__version__ = "2.0.0"
