"""
DATA-AI 日志调试系统

提供执行追踪、日志回放和调试分析能力。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .logging import get_logger

logger = get_logger(__name__)


class LogLevel(Enum):
    """日志级别枚举

    定义日志记录的不同级别。
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class TraceEventType(Enum):
    """追踪事件类型枚举

    定义可追踪的事件类型。
    """

    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    USER_INPUT = "user_input"
    SYSTEM_ERROR = "system_error"
    CUSTOM = "custom"


@dataclass
class TraceEvent:
    """追踪事件"""

    id: str
    timestamp: float
    event_type: TraceEventType
    agent_name: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    parent_id: str | None = None
    session_id: str = ""
    level: LogLevel = LogLevel.INFO

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "event_type": self.event_type.value,
            "agent_name": self.agent_name,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "parent_id": self.parent_id,
            "session_id": self.session_id,
            "level": self.level.value,
        }


@dataclass
class TraceSpan:
    """追踪跨度（一组相关事件）"""

    id: str
    name: str
    start_time: float
    end_time: float | None = None
    events: list[TraceEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return (time.time() - self.start_time) * 1000

    def add_event(self, event: TraceEvent) -> None:
        self.events.append(event)

    def finish(self) -> None:
        self.end_time = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "events": [e.to_dict() for e in self.events],
            "metadata": self.metadata,
        }


class DebugTracer:
    """
    调试追踪器

    记录 Agent 执行过程中的所有事件，支持：
    - 执行追踪：记录每个步骤的详细信息
    - 日志回放：重新加载和回放执行过程
    - 性能分析：统计各阶段耗时
    - 错误诊断：定位问题根源
    """

    def __init__(self, storage_dir: str | None = None, enabled: bool = True):
        self._storage_dir = Path(storage_dir or os.path.expanduser("~/.data-ai/debug"))
        self._enabled = enabled
        self._spans: dict[str, TraceSpan] = {}
        self._current_span_id: str | None = None
        self._session_id = str(uuid.uuid4())[:8]
        self._event_buffer: list[TraceEvent] = []
        self._buffer_size = 1000
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def start_span(self, name: str, metadata: dict | None = None) -> str:
        """开始一个新的追踪跨度"""
        span_id = str(uuid.uuid4())[:12]
        span = TraceSpan(
            id=span_id,
            name=name,
            start_time=time.time(),
            metadata=metadata or {},
        )
        self._spans[span_id] = span
        self._current_span_id = span_id

        # 记录开始事件
        self.record_event(
            TraceEventType.CUSTOM,
            data={"action": "span_start", "name": name},
        )

        return span_id

    def end_span(self, span_id: str | None = None) -> TraceSpan | None:
        """结束追踪跨度"""
        sid = span_id or self._current_span_id
        if not sid or sid not in self._spans:
            return None

        span = self._spans[sid]
        span.finish()

        if self._current_span_id == sid:
            self._current_span_id = None

        return span

    def record_event(
        self,
        event_type: TraceEventType,
        agent_name: str = "",
        data: dict | None = None,
        duration_ms: float = 0.0,
        level: LogLevel = LogLevel.INFO,
    ) -> TraceEvent | None:
        """记录追踪事件"""
        if not self._enabled:
            return None

        event = TraceEvent(
            id=str(uuid.uuid4())[:8],
            timestamp=time.time(),
            event_type=event_type,
            agent_name=agent_name,
            data=data or {},
            duration_ms=duration_ms,
            parent_id=self._current_span_id,
            session_id=self._session_id,
            level=level,
        )

        # 添加到当前跨度
        if self._current_span_id and self._current_span_id in self._spans:
            self._spans[self._current_span_id].add_event(event)

        # 添加到缓冲区
        self._event_buffer.append(event)
        if len(self._event_buffer) > self._buffer_size:
            self._event_buffer = self._event_buffer[-self._buffer_size :]

        return event

    def trace_llm_call(
        self,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        latency_ms: float = 0,
        success: bool = True,
        error: str = "",
    ) -> None:
        """追踪 LLM 调用"""
        self.record_event(
            TraceEventType.LLM_REQUEST if success else TraceEventType.SYSTEM_ERROR,
            data={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "latency_ms": latency_ms,
                "success": success,
                "error": error,
            },
            duration_ms=latency_ms,
        )

    def trace_tool_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any = None,
        duration_ms: float = 0,
        success: bool = True,
        error: str = "",
    ) -> None:
        """追踪工具调用"""
        self.record_event(
            TraceEventType.TOOL_CALL if success else TraceEventType.SYSTEM_ERROR,
            data={
                "tool_name": tool_name,
                "args": args,
                "result_preview": str(result)[:500] if result else None,
                "success": success,
                "error": error,
            },
            duration_ms=duration_ms,
        )

    def trace_agent_step(
        self,
        agent_name: str,
        step_number: int,
        thought: str = "",
        action: str = "",
        observation: str = "",
    ) -> None:
        """追踪 Agent 步骤"""
        self.record_event(
            TraceEventType.CUSTOM,
            agent_name=agent_name,
            data={
                "action": "agent_step",
                "step_number": step_number,
                "thought": thought[:500],
                "action_input": action[:200],
                "observation": observation[:500],
            },
        )

    def get_current_span(self) -> TraceSpan | None:
        """获取当前活跃的跨度"""
        if self._current_span_id and self._current_span_id in self._spans:
            return self._spans[self._current_span_id]
        return None

    def get_span(self, span_id: str) -> TraceSpan | None:
        """获取指定跨度"""
        return self._spans.get(span_id)

    def get_all_spans(self) -> list[TraceSpan]:
        """获取所有跨度"""
        return list(self._spans.values())

    def get_events(
        self,
        event_type: TraceEventType | None = None,
        agent_name: str | None = None,
        limit: int = 100,
    ) -> list[TraceEvent]:
        """获取事件"""
        events = self._event_buffer

        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if agent_name:
            events = [e for e in events if e.agent_name == agent_name]

        return events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """获取追踪统计"""
        total_events = len(self._event_buffer)

        # 按类型统计
        type_counts = {}
        for event in self._event_buffer:
            key = event.event_type.value
            type_counts[key] = type_counts.get(key, 0) + 1

        # LLM 调用统计
        llm_events = [e for e in self._event_buffer if e.event_type == TraceEventType.LLM_REQUEST]
        total_tokens = sum(e.data.get("total_tokens", 0) for e in llm_events)
        total_latency = sum(e.data.get("latency_ms", 0) for e in llm_events)

        # 工具调用统计
        tool_events = [e for e in self._event_buffer if e.event_type == TraceEventType.TOOL_CALL]
        tool_names = {}
        for e in tool_events:
            name = e.data.get("tool_name", "unknown")
            tool_names[name] = tool_names.get(name, 0) + 1

        return {
            "session_id": self._session_id,
            "total_events": total_events,
            "total_spans": len(self._spans),
            "event_types": type_counts,
            "llm_calls": len(llm_events),
            "total_tokens": total_tokens,
            "avg_llm_latency_ms": total_latency / len(llm_events) if llm_events else 0,
            "tool_calls": len(tool_events),
            "tool_distribution": tool_names,
        }

    def save_trace(self, trace_id: str | None = None) -> str:
        """保存追踪记录到文件"""
        trace_id = trace_id or f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self._session_id}"

        data = {
            "trace_id": trace_id,
            "session_id": self._session_id,
            "saved_at": datetime.now().isoformat(),
            "spans": [s.to_dict() for s in self._spans.values()],
            "events": [e.to_dict() for e in self._event_buffer],
            "stats": self.get_stats(),
        }

        file_path = self._storage_dir / f"{trace_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"追踪记录已保存: {file_path}")
        return str(file_path)

    def load_trace(self, file_path: str) -> dict[str, Any]:
        """加载追踪记录"""
        path = Path(file_path)
        if not path.exists():
            # 尝试在存储目录中查找
            path = self._storage_dir / file_path
            if not path.exists():
                raise FileNotFoundError(f"追踪记录不存在: {file_path}")

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        return data

    def replay_trace(self, file_path: str) -> list[dict[str, Any]]:
        """回放追踪记录"""
        data = self.load_trace(file_path)
        events = data.get("events", [])

        replay = []
        for event in events:
            replay.append(
                {
                    "time": event.get("datetime", ""),
                    "type": event.get("event_type", ""),
                    "agent": event.get("agent_name", ""),
                    "data": event.get("data", {}),
                    "duration_ms": event.get("duration_ms", 0),
                }
            )

        return replay

    def clear(self) -> None:
        """清除所有追踪数据"""
        self._spans.clear()
        self._event_buffer.clear()
        self._current_span_id = None

    def list_traces(self) -> list[dict[str, str]]:
        """列出所有保存的追踪记录"""
        traces = []
        for file_path in self._storage_dir.glob("trace_*.json"):
            try:
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                traces.append(
                    {
                        "file": file_path.name,
                        "trace_id": data.get("trace_id", ""),
                        "session_id": data.get("session_id", ""),
                        "saved_at": data.get("saved_at", ""),
                        "events": data.get("stats", {}).get("total_events", 0),
                    }
                )
            except Exception:
                pass

        return sorted(traces, key=lambda x: x.get("saved_at", ""), reverse=True)


# 全局追踪器实例
_global_tracer: DebugTracer | None = None


def get_tracer() -> DebugTracer:
    """获取全局追踪器"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = DebugTracer()
    return _global_tracer
