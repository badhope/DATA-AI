"""
取消机制模块。

本模块提供流式处理的取消控制，支持：
- 事件（flag）取消
- 超时取消
- 链式取消（父取消自动传播至子）
- 异步上下文管理器
- 回调注册

主要类:
- CancellationHandler: 取消处理器
- _TimeoutContext: 超时异步上下文管理器
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from .types import CancellationReason, CancellationToken

CancelCallback = Callable[["CancellationHandler"], None]
"""取消回调签名。"""


class CancellationHandler:
    """
    取消处理器。

    支持以下模式：
    - 显式调用 ``cancel()`` 触发取消
    - 通过 ``with_timeout(seconds)`` 设置超时自动取消
    - 父子链式：父取消时所有子自动取消
    - 注册回调 ``on_cancel``
    - 异步迭代中抛出 ``asyncio.CancelledError``

    Example:
        >>> handler = CancellationHandler()
        >>> handler.on_cancel(lambda h: print("cancelled!"))
        >>> handler.cancel()
        >>> assert handler.is_cancelled()
        >>>
        >>> # 父子链
        >>> parent = CancellationHandler()
        >>> child = parent.create_child()
        >>> parent.cancel()
        >>> assert child.is_cancelled()
        >>>
        >>> # 超时
        >>> async with handler.with_timeout(0.05):
        ...     await asyncio.sleep(1.0)  # 会抛出 asyncio.TimeoutError
    """

    __slots__ = (
        "_cancelled",
        "_reason",
        "_message",
        "_cancelled_at",
        "_lock",
        "_callbacks",
        "_parent",
        "_children",
        "_timeout_task",
        "_loop",
    )

    def __init__(
        self,
        parent: CancellationHandler | None = None,
        reason: CancellationReason = CancellationReason.CUSTOM,
    ) -> None:
        """
        初始化取消处理器。

        Args:
            parent: 父处理器，父取消时本处理器也会自动取消
            reason: 默认取消原因
        """
        self._cancelled: bool = False
        self._reason: CancellationReason = reason
        self._message: str = ""
        self._cancelled_at: datetime | None = None
        self._lock: threading.RLock = threading.RLock()
        self._callbacks: list[CancelCallback] = []
        self._parent: CancellationHandler | None = parent
        self._children: set[CancellationHandler] = set()
        self._timeout_task: asyncio.Task[Any] | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

        if parent is not None:
            with parent._lock:
                parent._children.add(self)
            parent.on_cancel(self._on_parent_cancelled)

    # ------------------------------------------------------------------ 状态

    def is_cancelled(self) -> bool:
        """是否已取消。"""
        return self._cancelled

    @property
    def cancelled(self) -> bool:
        """是否已取消（属性形式）。"""
        return self._cancelled

    def token(self) -> CancellationToken:
        """获取当前不可变令牌快照。"""
        with self._lock:
            return CancellationToken(
                cancelled=self._cancelled,
                reason=self._reason,
                message=self._message,
                cancelled_at=self._cancelled_at,
            )

    # ------------------------------------------------------------------ 触发

    def cancel(
        self,
        reason: CancellationReason | str | None = None,
        message: str = "",
    ) -> None:
        """
        触发取消。

        该方法是幂等的：多次调用只有第一次生效。

        Args:
            reason: 取消原因
            message: 取消消息
        """
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            if reason is not None:
                if isinstance(reason, CancellationReason):
                    self._reason = reason
                else:
                    self._reason = CancellationReason.CUSTOM
                    self._message = str(reason) if not message else message
            if message:
                self._message = message
            self._cancelled_at = datetime.now()

            callbacks = list(self._callbacks)
            children = list(self._children)
            timeout_task = self._timeout_task

        if timeout_task is not None:
            try:
                timeout_task.cancel()
            except Exception:
                pass

        for cb in callbacks:
            try:
                cb(self)
            except Exception:
                pass

        for child in children:
            try:
                child.cancel(
                    reason=CancellationReason.PARENT_CANCELLED,
                    message=message or "parent cancelled",
                )
            except Exception:
                pass

    def _on_parent_cancelled(self, _parent: CancellationHandler) -> None:
        """父处理器被取消时调用。"""
        self.cancel(
            reason=CancellationReason.PARENT_CANCELLED,
            message="parent cancelled",
        )

    # ------------------------------------------------------------------ 检查

    def check_and_raise(self) -> None:
        """
        检查并抛出 ``asyncio.CancelledError``（如果已取消）。

        Raises:
            asyncio.CancelledError: 已取消时
        """
        if self._cancelled:
            raise asyncio.CancelledError(self._message or "operation cancelled")

    def raise_if_cancelled(self) -> None:
        """同 :meth:`check_and_raise`。"""
        self.check_and_raise()

    # ------------------------------------------------------------------ 回调

    def on_cancel(self, callback: CancelCallback) -> None:
        """
        注册取消回调。

        如果当前已处于取消状态，回调会立即执行。

        Args:
            callback: 回调函数，签名 ``(handler) -> None``
        """
        with self._lock:
            if self._cancelled:
                try:
                    callback(self)
                except Exception:
                    pass
                return
            self._callbacks.append(callback)

    # ------------------------------------------------------------------ 父子

    def create_child(
        self,
        reason: CancellationReason = CancellationReason.CUSTOM,
    ) -> CancellationHandler:
        """
        创建子处理器。

        Args:
            reason: 子处理器默认取消原因

        Returns:
            子 ``CancellationHandler`` 实例
        """
        return CancellationHandler(parent=self, reason=reason)

    @property
    def parent(self) -> CancellationHandler | None:
        """父处理器。"""
        return self._parent

    @property
    def children(self) -> list[CancellationHandler]:
        """所有当前活跃的子处理器快照。"""
        with self._lock:
            return list(self._children)

    # ------------------------------------------------------------------ 超时

    @asynccontextmanager
    async def with_timeout(self, seconds: float) -> AsyncIterator[CancellationHandler]:
        """
        在 ``seconds`` 秒后自动取消当前处理器的异步上下文管理器。

        用法::

            async with handler.with_timeout(5.0):
                await do_long_work()

        超时后会同时：
        1. 标记 handler 取消（``is_cancelled()`` 返回 ``True``）
        2. 取消执行上下文中的当前 asyncio 任务，使任何 ``await`` 中断并抛出
           :class:`asyncio.CancelledError`

        Args:
            seconds: 超时秒数（必须 > 0）
        """
        if seconds <= 0:
            yield self
            return

        current_task: asyncio.Task[Any] | None = None
        try:
            current_task = asyncio.current_task()
        except RuntimeError:
            current_task = None

        async def _fire() -> None:
            try:
                await asyncio.sleep(seconds)
            except asyncio.CancelledError:
                return
            self.cancel(
                reason=CancellationReason.TIMEOUT,
                message=f"timeout after {seconds}s",
            )
            if current_task is not None and not current_task.done():
                current_task.cancel()

        timeout_task = asyncio.create_task(_fire())
        try:
            yield self
        finally:
            if not timeout_task.done():
                timeout_task.cancel()
                try:
                    await timeout_task
                except (asyncio.CancelledError, Exception):
                    pass
            self._timeout_task = None

    # ------------------------------------------------------------------ 等待

    async def wait(self) -> None:
        """异步等待取消事件。"""
        if self._cancelled:
            return
        loop = asyncio.get_running_loop()
        event = asyncio.Event()

        def _trigger(_h: CancellationHandler) -> None:
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                event.set()

        self.on_cancel(_trigger)
        if not self._cancelled:
            await event.wait()

    # ------------------------------------------------------------------ 工具

    def reset(self) -> None:
        """
        重置处理器状态。

        会清空所有回调、子处理器引用、超时任务。仅在确认安全时使用，
        一般不建议在生产中调用。
        """
        with self._lock:
            self._cancelled = False
            self._reason = CancellationReason.CUSTOM
            self._message = ""
            self._cancelled_at = None
            self._callbacks.clear()
            self._children.clear()
            task = self._timeout_task
            self._timeout_task = None
        if task is not None:
            try:
                task.cancel()
            except Exception:
                pass

    def __enter__(self) -> CancellationHandler:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self._cancelled:
            self.cancel(message="context exited")

    async def __aenter__(self) -> CancellationHandler:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self._cancelled:
            self.cancel(message="async context exited")

    def __repr__(self) -> str:
        with self._lock:
            state = "cancelled" if self._cancelled else "active"
            return f"<CancellationHandler {state} reason={self._reason.value}>"
