"""
使用统计模块。

本模块实现线程安全的使用量跟踪与聚合分析。

主要类:
- UsageTracker: 使用量跟踪器
"""

from __future__ import annotations

import csv
import io
import threading
from collections import defaultdict
from datetime import date, datetime
from typing import Any

from .types import UsageRecord, UsageStats


class UsageTracker:
    """
    线程安全的使用量跟踪器。

    支持:
    - 按模型聚合 token 用量
    - 按日期聚合（每日 / 每月）
    - 按请求 ID 检索
    - CSV 导出
    - 全部清空

    Example:
        >>> tracker = UsageTracker()
        >>> tracker.record("gpt-4", prompt_tokens=100, completion_tokens=50, request_id="r1")
        >>> total = tracker.get_total()
        >>> total.prompt_tokens
        100
        >>> csv_text = tracker.export_csv()
    """

    __slots__ = (
        "_records",
        "_lock",
        "_by_model",
        "_by_request",
        "_by_day",
        "_by_month",
    )

    def __init__(self) -> None:
        self._records: list[UsageRecord] = []
        self._lock: threading.RLock = threading.RLock()
        # 索引
        self._by_model: dict[str, list[UsageRecord]] = defaultdict(list)
        self._by_request: dict[str, list[UsageRecord]] = defaultdict(list)
        self._by_day: dict[str, list[UsageRecord]] = defaultdict(list)
        self._by_month: dict[str, list[UsageRecord]] = defaultdict(list)

    # ------------------------------------------------------------------ 记录

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        request_id: str | None = None,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageRecord:
        """
        记录一次 token 使用。

        Args:
            model: 模型名称
            prompt_tokens: 提示 token 数
            completion_tokens: 完成 token 数
            request_id: 请求 ID（可选）
            timestamp: 记录时间（默认 ``datetime.now()``）
            metadata: 附加元数据

        Returns:
            新增的 :class:`UsageRecord`
        """
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts must be non-negative")

        record = UsageRecord(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            request_id=request_id,
            timestamp=timestamp or datetime.now(),
            metadata=dict(metadata) if metadata else {},
        )

        with self._lock:
            self._records.append(record)
            self._by_model[model].append(record)
            if request_id is not None:
                self._by_request[request_id].append(record)
            day_key = record.timestamp.date().isoformat()
            month_key = record.timestamp.strftime("%Y-%m")
            self._by_day[day_key].append(record)
            self._by_month[month_key].append(record)

        return record

    # ------------------------------------------------------------------ 查询

    def get_total(self, model: str | None = None) -> UsageStats:
        """
        获取累计统计。

        Args:
            model: 可选，按模型过滤

        Returns:
            :class:`UsageStats`
        """
        with self._lock:
            records = self._records if model is None else list(self._by_model.get(model, []))
            return self._aggregate(records)

    def get_daily(
        self,
        day: str | date | datetime,
        model: str | None = None,
    ) -> UsageStats:
        """
        获取某一天的使用统计。

        Args:
            day: 日期（字符串 ``"YYYY-MM-DD"``、:class:`date` 或 :class:`datetime`）
            model: 可选，按模型过滤

        Returns:
            :class:`UsageStats`
        """
        key = self._normalize_day(day)
        with self._lock:
            records = list(self._by_day.get(key, []))
        if model is not None:
            records = [r for r in records if r.model == model]
        return self._aggregate(records)

    def get_monthly(
        self,
        month: str | date | datetime,
        model: str | None = None,
    ) -> UsageStats:
        """
        获取某个月的使用统计。

        Args:
            month: 月份（字符串 ``"YYYY-MM"``、:class:`date` 或 :class:`datetime`）
            model: 可选，按模型过滤

        Returns:
            :class:`UsageStats`
        """
        key = self._normalize_month(month)
        with self._lock:
            records = list(self._by_month.get(key, []))
        if model is not None:
            records = [r for r in records if r.model == model]
        return self._aggregate(records)

    def get_by_request(self, request_id: str) -> UsageStats:
        """根据请求 ID 聚合。"""
        with self._lock:
            records = list(self._by_request.get(request_id, []))
        return self._aggregate(records)

    def get_all_records(self) -> list[UsageRecord]:
        """获取所有记录的浅拷贝。"""
        with self._lock:
            return list(self._records)

    def get_records_for_model(self, model: str) -> list[UsageRecord]:
        """获取某模型的所有记录。"""
        with self._lock:
            return list(self._by_model.get(model, []))

    # ------------------------------------------------------------------ 导出

    def export_csv(self) -> str:
        """
        导出所有记录为 CSV 字符串。

        列：``timestamp, model, request_id, prompt_tokens, completion_tokens, total_tokens``
        """
        with self._lock:
            records = list(self._records)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "timestamp",
                "model",
                "request_id",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r.timestamp.isoformat(),
                    r.model,
                    r.request_id or "",
                    r.prompt_tokens,
                    r.completion_tokens,
                    r.total_tokens,
                ]
            )
        return buf.getvalue()

    # ------------------------------------------------------------------ 重置

    def reset(self) -> None:
        """清空所有记录。"""
        with self._lock:
            self._records.clear()
            self._by_model.clear()
            self._by_request.clear()
            self._by_day.clear()
            self._by_month.clear()

    # ------------------------------------------------------------------ 工具

    @property
    def record_count(self) -> int:
        """记录条数。"""
        with self._lock:
            return len(self._records)

    @property
    def models(self) -> list[str]:
        """所有出现过的模型列表。"""
        with self._lock:
            return list(self._by_model.keys())

    def _aggregate(self, records: list[UsageRecord]) -> UsageStats:
        stats = UsageStats()
        stats.request_count = len(records)
        for r in records:
            stats.prompt_tokens += r.prompt_tokens
            stats.completion_tokens += r.completion_tokens
            bucket = stats.models.setdefault(r.model, {"prompt": 0, "completion": 0})
            bucket["prompt"] += r.prompt_tokens
            bucket["completion"] += r.completion_tokens
        stats.total_tokens = stats.prompt_tokens + stats.completion_tokens
        return stats

    @staticmethod
    def _normalize_day(value: str | date | datetime) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            # 接受 "YYYY-MM-DD" 或 "YYYY-MM-DDTHH:MM:SS"
            if "T" in value:
                value = value.split("T", 1)[0]
            return value
        raise TypeError(f"unsupported date type: {type(value).__name__}")

    @staticmethod
    def _normalize_month(value: str | date | datetime) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m")
        if isinstance(value, date):
            return value.strftime("%Y-%m")
        if isinstance(value, str):
            if len(value) >= 7:
                return value[:7]
            raise ValueError(f"invalid month string: {value!r}")
        raise TypeError(f"unsupported month type: {type(value).__name__}")
