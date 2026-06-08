"""
DATA-AI 企业级 — SLA 监控 + 状态页

企业痛点:
- 客户问: 你们 99.9% 可用性承诺是真的吗? (SLA)
- 出问题: 哪个组件最先挂? (MTTR 关键)
- 告警: SLO 异常 (5xx 率 > 1%, p99 延迟 > 2s)
- 公开: 客户能查 status.data-ai.example.com
- 历史: 30 天/90 天可用性报表

设计:
- SLO: 服务等级目标 (availability / latency / error_rate)
- SLI: 当前指标值 (基于 audit 实时计算)
- Incident: 事件记录 (start/end/severity/affected_components)
- StatusReport: 状态页快照 (overall + per-component)
- SLOReport: 月度/季度报表 (uptime%, MTTR, 事件统计)
"""

from __future__ import annotations

import json
import statistics
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class IncidentSeverity(str, Enum):
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"


class ComponentStatus(str, Enum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    PARTIAL_OUTAGE = "partial_outage"
    MAJOR_OUTAGE = "major_outage"
    MAINTENANCE = "maintenance"


@dataclass
class Component:
    """被监控的组件"""

    id: str = field(default_factory=lambda: f"comp-{uuid.uuid4().hex[:8]}")
    name: str = ""  # e.g. "LLM Inference", "RAG Pipeline", "API Gateway"
    description: str = ""
    status: ComponentStatus = ComponentStatus.OPERATIONAL
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Component:
        d2 = dict(d)
        if "status" in d2:
            d2["status"] = ComponentStatus(d2["status"])
        return cls(**d2)


@dataclass
class SLO:
    """服务等级目标"""

    id: str = field(default_factory=lambda: f"slo-{uuid.uuid4().hex[:8]}")
    name: str = ""
    component_id: str = ""
    # 目标: 99.9% 可用 OR p99 < 2s
    sli_type: Literal["availability", "error_rate", "latency_p99", "latency_p95", "throughput"] = "availability"
    target_value: float = 99.9  # 可用率 %
    # 延迟类: 毫秒
    error_budget_window_days: int = 30
    description: str = ""
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SLO:
        return cls(**d)


@dataclass
class Incident:
    """故障事件"""

    id: str = field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:8]}")
    title: str = ""
    severity: IncidentSeverity = IncidentSeverity.MINOR
    status: IncidentStatus = IncidentStatus.INVESTIGATING
    affected_components: list[str] = field(default_factory=list)  # component ids
    started_at: float = field(default_factory=time.time)
    resolved_at: float = 0.0
    updates: list[dict[str, Any]] = field(default_factory=list)  # [{at, status, message, by}]
    root_cause: str = ""
    resolution: str = ""

    def duration_seconds(self) -> float:
        end = self.resolved_at if self.resolved_at > 0 else time.time()
        return end - self.started_at

    def is_open(self) -> bool:
        return self.status != IncidentStatus.RESOLVED

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Incident:
        d2 = dict(d)
        d2["severity"] = IncidentSeverity(d2.get("severity", "minor"))
        d2["status"] = IncidentStatus(d2.get("status", "investigating"))
        return cls(**d2)


# ---------- SLI 实时指标 (从 Audit / 健康检查喂入) ----------


@dataclass
class SLIProbe:
    """一次 SLI 探测结果"""

    component_id: str = ""
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    latency_ms: float = 0.0
    error_code: int = 200


class SLAMonitor:
    """SLA 监控 + 状态页主引擎"""

    def __init__(self, persist_path: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._components: dict[str, Component] = {}
        self._slos: dict[str, SLO] = {}
        self._incidents: dict[str, Incident] = {}
        self._probes: list[SLIProbe] = []  # 滑动窗口
        self._max_probes = 100_000
        self._persist_path = persist_path
        self._bootstrap_components()
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _bootstrap_components(self) -> None:
        """初始化核心组件"""
        defaults = [
            ("API Gateway", "对外 HTTP 入口"),
            ("LLM Inference", "大模型推理服务"),
            ("RAG Pipeline", "检索增强生成"),
            ("Memory Store", "记忆与向量存储"),
            ("Agent Runtime", "Agent 执行引擎"),
            ("MCP Servers", "MCP 协议网关"),
            ("Webhooks", "事件投递服务"),
            ("Audit Log", "审计与合规"),
        ]
        for name, desc in defaults:
            c = Component(name=name, description=desc)
            self._components[c.id] = c

    # ---------- 组件 ----------
    def register_component(self, name: str, description: str = "") -> Component:
        with self._lock:
            c = Component(name=name, description=description)
            self._components[c.id] = c
            return c

    def list_components(self) -> list[Component]:
        with self._lock:
            return list(self._components.values())

    def update_component_status(self, component_id: str, status: ComponentStatus) -> Component | None:
        with self._lock:
            c = self._components.get(component_id)
            if not c:
                return None
            c.status = status
            c.updated_at = time.time()
            return c

    def get_component(self, component_id: str) -> Component | None:
        return self._components.get(component_id)

    # ---------- SLO ----------
    def create_slo(self, slo: SLO) -> SLO:
        with self._lock:
            self._slos[slo.id] = slo
            return slo

    def list_slos(self) -> list[SLO]:
        with self._lock:
            return list(self._slos.values())

    def evaluate_slo(self, slo: SLO, window_sec: float = 86400) -> dict[str, Any]:
        """评估 SLO 当前达成情况"""
        with self._lock:
            now = time.time()
            cutoff = now - window_sec
            probes = [p for p in self._probes if p.component_id == slo.component_id and p.timestamp >= cutoff]
            if not probes:
                return {
                    "slo_id": slo.id,
                    "name": slo.name,
                    "type": slo.sli_type,
                    "current_value": None,
                    "target": slo.target_value,
                    "status": "no_data",
                    "sample_size": 0,
                }
            if slo.sli_type == "availability":
                ok = sum(1 for p in probes if p.success)
                cur = (ok / len(probes)) * 100
            elif slo.sli_type == "error_rate":
                err = sum(1 for p in probes if not p.success or p.error_code >= 500)
                cur = (err / len(probes)) * 100
            elif slo.sli_type in ("latency_p99", "latency_p95"):
                lats = sorted(p.latency_ms for p in probes)
                idx = int(len(lats) * 0.99) if slo.sli_type == "latency_p99" else int(len(lats) * 0.95)
                cur = lats[min(idx, len(lats) - 1)]
            elif slo.sli_type == "throughput":
                cur = len(probes) / (window_sec / 60.0)  # per minute
            else:
                cur = 0.0

            # 状态判定
            if slo.sli_type in ("availability", "throughput"):
                status = "ok" if cur >= slo.target_value else "breach"
            else:  # error_rate, latency: 越低越好
                status = "ok" if cur <= slo.target_value else "breach"

            return {
                "slo_id": slo.id,
                "name": slo.name,
                "type": slo.sli_type,
                "current_value": round(cur, 4),
                "target": slo.target_value,
                "status": status,
                "sample_size": len(probes),
                "window_sec": window_sec,
            }

    def evaluate_all_slos(self) -> list[dict[str, Any]]:
        return [self.evaluate_slo(s) for s in self.list_slos()]

    # ---------- 探测 ----------
    def record_probe(
        self, component_id: str, success: bool, latency_ms: float = 0.0, error_code: int = 200
    ) -> SLIProbe:
        with self._lock:
            p = SLIProbe(component_id=component_id, success=success, latency_ms=latency_ms, error_code=error_code)
            self._probes.append(p)
            if len(self._probes) > self._max_probes:
                self._probes = self._probes[-self._max_probes :]
            return p

    def feed_from_audit(
        self, audit_entries: list[dict[str, Any]], path_to_component: Callable[[str], str] | None = None
    ) -> int:
        """从审计日志喂入 SLI 数据
        path_to_component: 把 URL path 映射到 component_id,默认按前缀分桶
        """
        with self._lock:
            count = 0
            for e in audit_entries:
                path = e.get("path", "")
                if not path_to_component:
                    cid = self._default_path_to_component(path)
                else:
                    cid = path_to_component(path)
                if not cid:
                    continue
                p = SLIProbe(
                    component_id=cid,
                    success=e.get("status_code", 500) < 500,
                    latency_ms=e.get("duration_ms", 0),
                    error_code=e.get("status_code", 200),
                    timestamp=e.get("timestamp", time.time()),
                )
                self._probes.append(p)
                count += 1
            if len(self._probes) > self._max_probes:
                self._probes = self._probes[-self._max_probes :]
            return count

    def _default_path_to_component(self, path: str) -> str:
        if "/v1/chat" in path or "/v1/llm" in path:
            return self._find_by_name("LLM Inference")
        if "/v1/rag" in path:
            return self._find_by_name("RAG Pipeline")
        if "/v1/memory" in path:
            return self._find_by_name("Memory Store")
        if "/v1/agents" in path or "/v1/teams" in path:
            return self._find_by_name("Agent Runtime")
        if "/v1/mcp" in path:
            return self._find_by_name("MCP Servers")
        if "/v1/webhooks" in path:
            return self._find_by_name("Webhooks")
        if "/v1/audit" in path:
            return self._find_by_name("Audit Log")
        if path.startswith("/v1"):
            return self._find_by_name("API Gateway")
        return ""

    def _find_by_name(self, name: str) -> str:
        for c in self._components.values():
            if c.name == name:
                return c.id
        return ""

    # ---------- 事件 ----------
    def open_incident(
        self, title: str, severity: IncidentSeverity, affected_components: list[str], message: str = ""
    ) -> Incident:
        with self._lock:
            inc = Incident(
                title=title,
                severity=severity,
                affected_components=affected_components,
                updates=[{"at": time.time(), "status": IncidentStatus.INVESTIGATING.value, "message": message}]
                if message
                else [],
            )
            self._incidents[inc.id] = inc
            # 联动:受影响组件降级
            for cid in affected_components:
                self.update_component_status(
                    cid,
                    ComponentStatus.MAJOR_OUTAGE
                    if severity == IncidentSeverity.CRITICAL
                    else ComponentStatus.PARTIAL_OUTAGE,
                )
            return inc

    def update_incident(
        self, incident_id: str, status: IncidentStatus, message: str = "", by: str = ""
    ) -> Incident | None:
        with self._lock:
            inc = self._incidents.get(incident_id)
            if not inc:
                return None
            inc.status = status
            inc.updates.append({"at": time.time(), "status": status.value, "message": message, "by": by})
            if status == IncidentStatus.RESOLVED:
                inc.resolved_at = time.time()
                for cid in inc.affected_components:
                    self.update_component_status(cid, ComponentStatus.OPERATIONAL)
            return inc

    def list_incidents(self, status: IncidentStatus | None = None, limit: int = 50) -> list[Incident]:
        with self._lock:
            out = list(self._incidents.values())
            if status:
                out = [i for i in out if i.status == status]
            out.sort(key=lambda i: i.started_at, reverse=True)
            return out[:limit]

    def get_incident(self, incident_id: str) -> Incident | None:
        return self._incidents.get(incident_id)

    # ---------- 状态页 ----------
    def status_page(self) -> dict[str, Any]:
        """生成 status.data-ai.example.com 公开快照"""
        with self._lock:
            components = []
            for c in self._components.values():
                components.append(
                    {
                        "id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "status": c.status.value,
                        "updated_at": c.updated_at,
                    }
                )
            open_incs = [i.to_dict() for i in self._incidents.values() if i.is_open()]
            overall = "operational"
            for c in self._components.values():
                if c.status == ComponentStatus.MAJOR_OUTAGE:
                    overall = "major_outage"
                    break
                if c.status in (ComponentStatus.PARTIAL_OUTAGE, ComponentStatus.DEGRADED):
                    overall = "degraded"
            return {
                "overall": overall,
                "components": components,
                "active_incidents": open_incs,
                "generated_at": time.time(),
            }

    # ---------- 月度报表 ----------
    def monthly_report(self, year: int, month: int) -> dict[str, Any]:
        """月度 SLA 报表"""
        with self._lock:
            start = datetime(year, month, 1).timestamp()
            end = (datetime(year, month, 1) + timedelta(days=32)).replace(day=1).timestamp()
            incidents = [i for i in self._incidents.values() if i.started_at >= start and i.started_at < end]
            # 事件统计
            severity_counts: dict[str, int] = {}
            total_downtime = 0.0
            for i in incidents:
                severity_counts[i.severity.value] = severity_counts.get(i.severity.value, 0) + 1
                if i.resolved_at > 0:
                    total_downtime += i.resolved_at - i.started_at
            # SLO 报表
            slo_reports = [self.evaluate_slo(s, window_sec=(end - start)) for s in self._slos.values()]
            # 计算综合可用率
            availability_slos = [
                r for r in slo_reports if r["type"] == "availability" and r["current_value"] is not None
            ]
            avg_avail = statistics.mean([r["current_value"] for r in availability_slos]) if availability_slos else None
            return {
                "year": year,
                "month": month,
                "period": {"start": start, "end": end},
                "incident_count": len(incidents),
                "severity_breakdown": severity_counts,
                "total_downtime_sec": round(total_downtime, 2),
                "total_downtime_human": _humanize_duration(total_downtime),
                "mttr_sec": round(total_downtime / len(incidents), 2) if incidents else 0,
                "availability_pct": round(avg_avail, 4) if avg_avail is not None else None,
                "slo_reports": slo_reports,
                "incidents": [i.to_dict() for i in incidents],
            }

    # ---------- 持久化 ----------
    def _write_persist(self, rec_type: str, data: dict[str, Any]) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"type": rec_type, "data": data}, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            with self._persist_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    t = rec.get("type")
                    d = rec.get("data", {})
                    if t == "incident":
                        inc = Incident.from_dict(d)
                        self._incidents[inc.id] = inc
                    elif t == "slo":
                        self._slos[d["id"]] = SLO.from_dict(d)
                    elif t == "component":
                        # 不覆盖 bootstrap
                        if d.get("id") not in self._components:
                            self._components[d["id"]] = Component.from_dict(d)
        except Exception:
            pass


def _humanize_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    if seconds < 86400:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"
    d = int(seconds // 86400)
    h = int((seconds % 86400) // 3600)
    return f"{d}d {h}h"


# ============================================================================
# 全局单例
# ============================================================================

_GLOBAL_MONITOR: SLAMonitor | None = None
_GLOBAL_LOCK = threading.Lock()


def get_sla_monitor(persist_path: Path | None = None) -> SLAMonitor:
    global _GLOBAL_MONITOR
    with _GLOBAL_LOCK:
        if _GLOBAL_MONITOR is None:
            _GLOBAL_MONITOR = SLAMonitor(persist_path=persist_path)
        return _GLOBAL_MONITOR


def reset_sla_monitor() -> None:
    global _GLOBAL_MONITOR
    with _GLOBAL_LOCK:
        _GLOBAL_MONITOR = None
