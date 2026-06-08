"""
进度管理模块。

本模块提供：
- :class:`ProgressTracker` 多阶段进度跟踪
- 估算剩余时间（ETA）
- 线程安全的状态访问
- 进度回调

主要类:
- ProgressTracker: 进度跟踪器
- StageProgress: 单阶段进度（已定义在 :mod:`types`）
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

from .types import ProgressInfo, StageProgress

ProgressCallback = Callable[[ProgressInfo], None]
"""进度回调签名。"""


class ProgressTracker:
    """
    线程安全的多阶段进度跟踪器。

    使用方式::

        tracker = ProgressTracker()
        tracker.start(total_steps=100, name="loading")
        for i in range(100):
            tracker.update(step=i + 1, message=f"step {i}")
        tracker.finish()

    或者多阶段::

        tracker = ProgressTracker()
        tracker.start(total_steps=3, name="pipeline")
        tracker.start_stage("download", total=10)
        for i in range(10):
            tracker.update(step=i + 1, message="...")
            tracker.update_stage("download", i + 1)
        tracker.finish_stage("download")
        ...
    """

    __slots__ = (
        "_lock",
        "_info",
        "_stages",
        "_current_stage",
        "_started",
        "_finished",
        "_callbacks",
        "_start_perf",
    )

    def __init__(self) -> None:
        self._lock: threading.RLock = threading.RLock()
        self._info: ProgressInfo = ProgressInfo()
        self._stages: dict[str, StageProgress] = {}
        self._current_stage: str | None = None
        self._started: bool = False
        self._finished: bool = False
        self._callbacks: list[ProgressCallback] = []
        self._start_perf: float = 0.0

    # ------------------------------------------------------------------ 回调

    def on_update(self, callback: ProgressCallback) -> None:
        """注册进度更新回调。"""
        with self._lock:
            self._callbacks.append(callback)

    def clear_callbacks(self) -> None:
        """清空回调。"""
        with self._lock:
            self._callbacks.clear()

    # ------------------------------------------------------------------ 生命周期

    def start(
        self,
        total_steps: int = 0,
        name: str = "default",
    ) -> None:
        """
        启动一个新的跟踪会话。

        Args:
            total_steps: 总步数（0 表示未知）
            name: 当前阶段名称
        """
        with self._lock:
            self._info = ProgressInfo(
                stage=name,
                current_step=0,
                total_steps=max(0, int(total_steps)),
                percentage=0.0,
                message="",
                elapsed_ms=0.0,
                eta_ms=0.0,
                stages=list(self._stages.values()),
            )
            self._stages.clear()
            self._current_stage = None
            self._started = True
            self._finished = False
            self._start_perf = time.perf_counter()
        self._emit()

    def finish(self) -> None:
        """标记跟踪结束。"""
        with self._lock:
            if not self._started:
                return
            self._finished = True
            if self._current_stage is not None and self._current_stage in self._stages:
                stage = self._stages[self._current_stage]
                if not stage.finished:
                    stage.finished = True
                    stage.finished_at = time.perf_counter()
                    stage.current = stage.total or stage.current
            if self._info.total_steps > 0:
                self._info.current_step = self._info.total_steps
                self._info.percentage = 100.0
            else:
                self._info.percentage = 100.0
            self._info.elapsed_ms = self._compute_elapsed()
            self._info.eta_ms = 0.0
            self._info.stages = list(self._stages.values())
        self._emit()

    def reset(self) -> None:
        """完全重置跟踪器。"""
        with self._lock:
            self._info = ProgressInfo()
            self._stages.clear()
            self._current_stage = None
            self._started = False
            self._finished = False
            self._start_perf = 0.0

    # ------------------------------------------------------------------ 阶段

    def start_stage(
        self,
        name: str,
        total: int = 0,
        message: str = "",
    ) -> StageProgress:
        """
        开始一个新阶段。

        Args:
            name: 阶段名
            total: 该阶段总步数（0 表示未知）
            message: 阶段消息

        Returns:
            创建的 :class:`StageProgress`
        """
        with self._lock:
            stage = self._stages.get(name)
            if stage is None:
                stage = StageProgress(name=name, total=max(0, int(total)), message=message)
                self._stages[name] = stage
            else:
                stage.total = max(0, int(total))
                stage.message = message
                stage.started_at = time.perf_counter()
                stage.finished = False
                stage.finished_at = 0.0
            self._current_stage = name
            self._info.stage = name
        self._emit()
        return stage

    def update_stage(
        self,
        name: str,
        current: int,
        message: str | None = None,
    ) -> None:
        """更新指定阶段的进度。"""
        with self._lock:
            stage = self._stages.get(name)
            if stage is None:
                stage = self.start_stage(name=name, total=current)
            stage.current = max(0, int(current))
            if message is not None:
                stage.message = message
        self._emit()

    def finish_stage(self, name: str, message: str | None = None) -> None:
        """完成指定阶段。"""
        with self._lock:
            stage = self._stages.get(name)
            if stage is None:
                return
            stage.finished = True
            stage.finished_at = time.perf_counter()
            stage.current = stage.total or stage.current
            if message is not None:
                stage.message = message
            if self._current_stage == name:
                self._current_stage = None
        self._emit()

    # ------------------------------------------------------------------ 更新

    def update(
        self,
        step: int | None = None,
        message: str | None = None,
        delta: int = 0,
    ) -> None:
        """
        更新整体进度。

        Args:
            step: 直接设置当前步数（与 ``delta`` 二选一）
            message: 进度消息
            delta: 增量步数
        """
        with self._lock:
            if not self._started:
                self.start()
            if step is not None:
                self._info.current_step = max(0, int(step))
            else:
                self._info.current_step = max(0, self._info.current_step + int(delta))
            if message is not None:
                self._info.message = message
            self._info.elapsed_ms = self._compute_elapsed()
            self._info.percentage = self._compute_percentage()
            self._info.eta_ms = self._compute_eta()
            self._info.stages = list(self._stages.values())
            # 同步当前阶段
            if self._current_stage and self._current_stage in self._stages:
                self._info.stage = self._current_stage
        self._emit()

    # ------------------------------------------------------------------ 状态

    def get_progress(self) -> ProgressInfo:
        """获取当前进度快照。"""
        with self._lock:
            self._info.elapsed_ms = self._compute_elapsed()
            self._info.eta_ms = self._compute_eta()
            self._info.percentage = self._compute_percentage()
            self._info.stages = list(self._stages.values())
            return ProgressInfo(
                stage=self._info.stage,
                current_step=self._info.current_step,
                total_steps=self._info.total_steps,
                percentage=self._info.percentage,
                message=self._info.message,
                elapsed_ms=self._info.elapsed_ms,
                eta_ms=self._info.eta_ms,
                stages=[
                    StageProgress(
                        name=s.name,
                        current=s.current,
                        total=s.total,
                        message=s.message,
                        started_at=s.started_at,
                        finished_at=s.finished_at,
                        finished=s.finished,
                    )
                    for s in self._stages.values()
                ],
            )

    @property
    def is_started(self) -> bool:
        return self._started

    @property
    def is_finished(self) -> bool:
        return self._finished

    @property
    def stages(self) -> list[StageProgress]:
        with self._lock:
            return list(self._stages.values())

    @property
    def percentage(self) -> float:
        with self._lock:
            return self._compute_percentage()

    @property
    def eta_ms(self) -> float:
        with self._lock:
            return self._compute_eta()

    @property
    def elapsed_ms(self) -> float:
        with self._lock:
            return self._compute_elapsed()

    # ------------------------------------------------------------------ 内部

    def _compute_percentage(self) -> float:
        if self._info.total_steps <= 0:
            return 0.0
        return min(100.0, (self._info.current_step / self._info.total_steps) * 100.0)

    def _compute_elapsed(self) -> float:
        if self._start_perf <= 0.0:
            return 0.0
        return max(0.0, (time.perf_counter() - self._start_perf) * 1000.0)

    def _compute_eta(self) -> float:
        if self._info.total_steps <= 0 or self._info.current_step <= 0:
            return 0.0
        elapsed = self._compute_elapsed()
        if elapsed <= 0.0:
            return 0.0
        rate = self._info.current_step / (elapsed / 1000.0)
        if rate <= 0:
            return 0.0
        remaining = self._info.total_steps - self._info.current_step
        if remaining <= 0:
            return 0.0
        return (remaining / rate) * 1000.0

    def _emit(self) -> None:
        snapshot = self.get_progress()
        callbacks: list[ProgressCallback]
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(snapshot)
            except Exception:
                pass

    def __enter__(self) -> ProgressTracker:
        if not self._started:
            self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if not self._finished:
            self.finish()
