"""
流式处理器模块。

本模块提供对异步流（``AsyncIterator[ChatChunk]``）的累积、
回调分发、取消、指标收集与进度跟踪等核心能力。

主要类:
- StreamingProcessor: 流式处理器
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from typing import (
    Any,
)

from .cancellation import CancellationHandler
from .progress import ProgressTracker
from .types import (
    AsyncChunkCallback,
    ChatChunk,
    ChatResponse,
    ProgressInfo,
    StreamingMetrics,
    ToolCallData,
)
from .usage import UsageTracker

ChunkSource = AsyncIterator[ChatChunk]
SyncChunkSource = Any  # 同步可迭代对象（list/iter 等），将被自动包装


class StreamingProcessor:
    """
    流式处理器。

    接受异步迭代的 :class:`ChatChunk`，完成以下职责：
    - 累积 ``content``、``tool_calls``、token 用量
    - 触发进度回调
    - 支持通过 :class:`CancellationHandler` 取消
    - 收集性能指标
    - 可选地通过 :class:`UsageTracker` 上报使用量

    Example:
        >>> async def gen():
        ...     for word in ["Hello", " ", "world"]:
        ...         yield ChatChunk(content=word)
        ...
        >>> processor = StreamingProcessor(model="gpt-4", request_id="r1")
        >>> response = await processor.process_stream(gen())
        >>> response.content
        'Hello world'
        >>> response.chunk_count
        3
    """

    __slots__ = (
        "model",
        "request_id",
        "_tracker",
        "_usage",
        "_cancellation",
        "_metrics",
        "_progress_callbacks",
        "_chunk_callbacks",
        "_buffer",
        "_tool_call_map",
        "_is_running",
        "_last_error",
    )

    def __init__(
        self,
        model: str | None = None,
        request_id: str | None = None,
        cancellation: CancellationHandler | None = None,
        usage_tracker: UsageTracker | None = None,
        progress_tracker: ProgressTracker | None = None,
        buffer_size: int = 1024,
    ) -> None:
        """
        初始化流式处理器。

        Args:
            model: 模型名称（用于 usage 统计）
            request_id: 请求 ID（用于 usage 统计）
            cancellation: 取消处理器实例
            usage_tracker: 用量跟踪器
            progress_tracker: 进度跟踪器
            buffer_size: 内部 ``deque`` 最大长度
        """
        self.model: str | None = model
        self.request_id: str | None = request_id
        self._tracker: ProgressTracker = progress_tracker or ProgressTracker()
        self._usage: UsageTracker | None = usage_tracker
        self._cancellation: CancellationHandler = cancellation or CancellationHandler()
        self._metrics: StreamingMetrics = StreamingMetrics()
        self._progress_callbacks: list[Callable[[ProgressInfo], None]] = []
        self._chunk_callbacks: list[Callable[[ChatChunk], None]] = []
        self._buffer: deque[ChatChunk] = deque(maxlen=max(1, int(buffer_size)))
        self._tool_call_map: dict[str, ToolCallData] = {}
        self._is_running: bool = False
        self._last_error: BaseException | None = None

    # ------------------------------------------------------------------ 配置

    def on_chunk(self, callback: Callable[[ChatChunk], None]) -> None:
        """注册同步块回调。"""
        self._chunk_callbacks.append(callback)

    def on_progress(self, callback: Callable[[ProgressInfo], None]) -> None:
        """注册进度回调。"""
        self._progress_callbacks.append(callback)

    def set_usage_tracker(self, tracker: UsageTracker) -> None:
        """设置用量跟踪器（可在运行前/后调用）。"""
        self._usage = tracker

    @property
    def cancellation(self) -> CancellationHandler:
        """当前取消处理器。"""
        return self._cancellation

    @property
    def progress_tracker(self) -> ProgressTracker:
        """当前进度跟踪器。"""
        return self._tracker

    # ------------------------------------------------------------------ 状态

    def cancel(self, reason: Any = None, message: str = "") -> None:
        """取消正在进行的流处理。"""
        self._cancellation.cancel(reason=reason, message=message)

    def is_cancelled(self) -> bool:
        """是否已取消。"""
        return self._cancellation.is_cancelled()

    def get_metrics(self) -> StreamingMetrics:
        """获取当前指标快照。"""
        m = self._metrics
        elapsed = (m.finished_at - m.started_at) if m.finished_at > m.started_at and m.started_at else 0.0
        if m.elapsed_ms <= 0 and elapsed > 0:
            m.elapsed_ms = elapsed * 1000.0
        if m.elapsed_ms > 0:
            m.tokens_per_second = m.total_tokens / (m.elapsed_ms / 1000.0)
        return m

    def get_progress(self) -> ProgressInfo:
        """获取当前进度快照。"""
        return self._tracker.get_progress()

    @property
    def last_error(self) -> BaseException | None:
        return self._last_error

    # ------------------------------------------------------------------ 处理

    async def process_stream(
        self,
        source: ChunkSource | SyncChunkSource | list[ChatChunk],
        total: int = 0,
    ) -> ChatResponse:
        """
        完整消费输入流并返回累积后的 :class:`ChatResponse`。

        Args:
            source: 异步迭代器、同步可迭代对象或 :class:`ChatChunk` 列表
            total: 已知总块数（0 表示未知，会在流结束时按实际计数）

        Returns:
            :class:`ChatResponse`
        """
        response = ChatResponse(model=self.model)
        started = time.perf_counter()
        self._metrics = StreamingMetrics(started_at=started)
        self._tool_call_map.clear()
        self._buffer.clear()
        self._is_running = True
        self._last_error = None
        chunk_count = 0
        response.started_at = self._now()
        self._tracker.start(total_steps=max(0, int(total)), name="streaming")

        iterator = self._normalize_source(source)
        try:
            while True:
                self._cancellation.check_and_raise()
                try:
                    chunk = await iterator.__anext__()
                except StopAsyncIteration:
                    break
                except asyncio.CancelledError:
                    self._metrics.cancelled = True
                    raise
                except Exception as exc:
                    self._metrics.errors += 1
                    self._last_error = exc
                    raise

                chunk_count += 1
                self._consume_chunk(chunk, response)
                self._buffer.append(chunk)
                self._metrics.chunk_count = chunk_count

                # 进度
                if total > 0:
                    self._tracker.update(step=chunk_count, message="streaming")
                else:
                    self._tracker.update(delta=1, message="streaming")

                # 块回调（异步）
                await self._dispatch_chunk(chunk)
        finally:
            self._is_running = False
            finished = time.perf_counter()
            self._metrics.finished_at = finished
            self._metrics.elapsed_ms = (finished - started) * 1000.0
            if self._metrics.elapsed_ms > 0:
                self._metrics.tokens_per_second = self._metrics.total_tokens / (self._metrics.elapsed_ms / 1000.0)
            self._metrics.completed = not self._metrics.cancelled and self._metrics.errors == 0
            response.chunk_count = chunk_count
            response.elapsed_ms = self._metrics.elapsed_ms
            response.finished_at = self._now()
            if not self._tracker.is_finished:
                self._tracker.finish()
            self._report_usage(response)

        return response

    async def process_with_callback(
        self,
        source: ChunkSource | SyncChunkSource | list[ChatChunk],
        on_chunk: AsyncChunkCallback,
        total: int = 0,
    ) -> ChatResponse:
        """
        流式处理并对每个块调用 ``on_chunk``。

        ``on_chunk`` 可以是同步函数或协程。

        Args:
            source: 输入流
            on_chunk: 块回调
            total: 已知总块数

        Returns:
            :class:`ChatResponse`
        """

        async def _wrapper(chunk: ChatChunk) -> None:
            try:
                result = on_chunk(chunk)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                # 回调异常不应该中断流处理
                pass

        # 包装为列表避免迭代器被消费两次
        chunks: list[ChatChunk] = []
        original_chunk_callbacks = list(self._chunk_callbacks)
        self._chunk_callbacks.append(_wrapper)
        try:
            if not self._is_async_source(source):
                # 同步源：物化一次避免二次消费
                for c in source:  # type: ignore[union-iter]
                    chunks.append(c)
                response = await self.process_stream(chunks, total=total)
            else:
                response = await self.process_stream(source, total=total)
        finally:
            self._chunk_callbacks = original_chunk_callbacks
        return response

    # ------------------------------------------------------------------ 内部

    def _consume_chunk(self, chunk: ChatChunk, response: ChatResponse) -> None:
        # 内容
        if chunk.content:
            response.content += chunk.content
        # 模型
        if chunk.model and not response.model:
            response.model = chunk.model
        if chunk.role and response.role == "assistant" and chunk.role != response.role:
            response.role = chunk.role
        # finish_reason
        if chunk.finish_reason:
            response.finish_reason = chunk.finish_reason
        # token
        if chunk.prompt_tokens:
            response.prompt_tokens = chunk.prompt_tokens
            self._metrics.prompt_tokens = chunk.prompt_tokens
        if chunk.completion_tokens:
            response.completion_tokens = chunk.completion_tokens
            self._metrics.completion_tokens = chunk.completion_tokens
        if chunk.total_tokens:
            response.total_tokens = chunk.total_tokens
            self._metrics.total_tokens = chunk.total_tokens
        else:
            # 估算增量 token
            if chunk.content:
                inc = self._estimate_tokens(chunk.content)
                self._metrics.total_tokens += inc
                self._metrics.completion_tokens += inc
                response.completion_tokens = self._metrics.completion_tokens

        # 工具调用聚合
        if chunk.tool_calls:
            for tc in chunk.tool_calls:
                existing = self._tool_call_map.get(tc.id)
                if existing is None:
                    self._tool_call_map[tc.id] = ToolCallData(id=tc.id, name=tc.name, arguments=tc.arguments)
                else:
                    if not existing.name and tc.name:
                        existing.name = tc.name
                    if tc.arguments:
                        existing.arguments += tc.arguments
        response.tool_calls = list(self._tool_call_map.values())

        # 首块延迟
        if self._metrics.chunk_count == 0 and self._metrics.started_at > 0:
            self._metrics.first_chunk_latency_ms = (time.perf_counter() - self._metrics.started_at) * 1000.0

        # 元数据合并
        if chunk.metadata:
            for k, v in chunk.metadata.items():
                response.metadata.setdefault(k, v)

    async def _dispatch_chunk(self, chunk: ChatChunk) -> None:
        for cb in self._chunk_callbacks:
            try:
                result = cb(chunk)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                pass
        for cb in self._progress_callbacks:
            try:
                cb(self.get_progress())
            except Exception:
                pass

    def _report_usage(self, response: ChatResponse) -> None:
        if self._usage is None:
            return
        prompt = response.prompt_tokens or self._metrics.prompt_tokens
        completion = response.completion_tokens or self._metrics.completion_tokens
        model = response.model or self.model or "unknown"
        self._usage.record(
            model=model,
            prompt_tokens=prompt,
            completion_tokens=completion,
            request_id=self.request_id,
            metadata={"chunk_count": response.chunk_count, "elapsed_ms": response.elapsed_ms},
        )

    @staticmethod
    def _normalize_source(
        source: ChunkSource | SyncChunkSource | list[ChatChunk],
    ) -> _AsyncIteratorWrapper:
        if isinstance(source, _AsyncIteratorWrapper):
            return source
        if hasattr(source, "__aiter__"):
            return _AsyncIteratorWrapper(source)  # type: ignore[arg-type]
        return _AsyncIteratorWrapper(_SyncToAsyncIterator(source))  # type: ignore[arg-type]

    @staticmethod
    def _is_async_source(source: Any) -> bool:
        return hasattr(source, "__aiter__")

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        if not text:
            return 0
        # 启发式：英文 1 token ~ 4 字符；中文 1 token ~ 1.5 字符
        cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other = len(text) - cjk
        return max(1, cjk // 2 + other // 4)

    @staticmethod
    def _now() -> Any:
        from datetime import datetime

        return datetime.now()


# ---------------------------------------------------------------------------
# 内部辅助：同步转异步迭代器
# ---------------------------------------------------------------------------


class _AsyncIteratorWrapper:
    """统一的 ``__aiter__`` / ``__anext__`` 包装。"""

    __slots__ = ("_iter",)

    def __init__(self, iterable: Any) -> None:
        if hasattr(iterable, "__aiter__"):
            self._iter = iterable.__aiter__()
        else:
            self._iter = iterable.__iter__()

    def __aiter__(self) -> _AsyncIteratorWrapper:
        return self

    async def __anext__(self) -> ChatChunk:
        try:
            if hasattr(self._iter, "__anext__"):
                return await self._iter.__anext__()
            return next(self._iter)
        except StopIteration as e:
            raise StopAsyncIteration() from e
        except StopAsyncIteration:
            raise


class _SyncToAsyncIterator:
    """把同步可迭代对象包装为支持 ``__anext__`` 的对象。"""

    __slots__ = ("_iter",)

    def __init__(self, iterable: Any) -> None:
        self._iter = iter(iterable)

    def __aiter__(self) -> _SyncToAsyncIterator:
        return self

    async def __anext__(self) -> ChatChunk:
        try:
            return next(self._iter)
        except StopIteration as e:
            raise StopAsyncIteration() from e
