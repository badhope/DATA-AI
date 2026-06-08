"""
DATA-AI 企业级 — 跨区域复制 + 灾备切换

企业痛点:
- 主区挂了怎么办? (RTO/RPO)
- 多区数据一致性如何保证? (同步 vs 异步)
- 跨区复制延迟能否可视化?
- 业务能不能一键切到备用区?
- 网络分区 / 脑裂如何防护?

设计:
- ReplicationPolicy: 复制策略 (源区 → 目标区, 同步/异步, 资源类型)
- ReplicaStream: 单条复制流 (state, lag, throughput, last_error)
- FailoverManager: 灾备切换 (预演 + 执行 + 回滚)
- NetworkPartitionGuard: 网络分区防护 (quorum 写入, 自动降级)
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ReplicationMode(str, Enum):
    SYNC = "sync"  # 同步复制: 强一致, RPO=0, 但延迟敏感
    ASYNC = "async"  # 异步复制: 最终一致, RPO > 0
    SEMI_SYNC = "semi_sync"  # 半同步: 至少一个副本确认


class StreamState(str, Enum):
    HEALTHY = "healthy"
    LAGGING = "lagging"  # 延迟超阈值
    DEGRADED = "degraded"  # 多次失败,降级为 async
    PAUSED = "paused"  # 主动暂停
    FAILED = "failed"  # 连续失败,需要人工介入


class FailoverMode(str, Enum):
    PLANNED = "planned"  # 计划内切换 (低风险,可回滚)
    EMERGENCY = "emergency"  # 紧急切换 (高风险,可能丢数据)
    DRILL = "drill"  # 灾备演练 (不实际切换)


class FailoverState(str, Enum):
    INITIATED = "initiated"
    DRAINING = "draining"
    PROMOTING = "promoting"
    SWITCHED = "switched"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class ReplicationPolicy:
    """复制策略: 描述源区到目标区的数据复制规则"""

    id: str = field(default_factory=lambda: f"rp-{uuid.uuid4().hex[:8]}")
    name: str = ""
    source_region: str = ""
    target_region: str = ""
    mode: ReplicationMode = ReplicationMode.ASYNC
    resource_types: list[str] = field(default_factory=list)  # 空 = 全部
    max_lag_sec: float = 30.0  # 异步模式最大可接受延迟
    encryption: bool = True
    compression: bool = True
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        return d


@dataclass
class ReplicaStream:
    """单条复制流的运行时状态"""

    id: str = field(default_factory=lambda: f"rs-{uuid.uuid4().hex[:8]}")
    policy_id: str = ""
    source_region: str = ""
    target_region: str = ""
    state: StreamState = StreamState.HEALTHY
    lag_sec: float = 0.0
    bytes_sent: int = 0
    records_sent: int = 0
    bytes_failed: int = 0
    records_failed: int = 0
    last_error: str = ""
    last_error_at: float = 0.0
    last_sync_at: float = 0.0
    consecutive_failures: int = 0
    started_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @property
    def is_healthy(self) -> bool:
        return self.state == StreamState.HEALTHY


@dataclass
class FailoverEvent:
    """灾备切换事件"""

    id: str = field(default_factory=lambda: f"fo-{uuid.uuid4().hex[:8]}")
    mode: FailoverMode = FailoverMode.PLANNED
    state: FailoverState = FailoverState.INITIATED
    from_region: str = ""
    to_region: str = ""
    initiated_by: str = ""
    reason: str = ""
    affected_resources: list[str] = field(default_factory=list)
    duration_sec: float = 0.0
    data_loss_records: int = 0
    rollback_supported: bool = True
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["mode"] = self.mode.value
        d["state"] = self.state.value
        return d


class ReplicationEngine:
    """跨区域复制引擎"""

    def __init__(self, persist_path: str | None = None) -> None:
        self._lock = threading.RLock()
        self._policies: dict[str, ReplicationPolicy] = {}
        self._streams: dict[str, ReplicaStream] = {}
        self._failovers: dict[str, FailoverEvent] = {}
        self._active_region: str = "cn-east"  # 当前主区
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path:
            self._load()

    # ---- policy management ----

    def create_policy(
        self,
        name: str,
        source_region: str,
        target_region: str,
        mode: ReplicationMode = ReplicationMode.ASYNC,
        resource_types: list[str] | None = None,
        max_lag_sec: float = 30.0,
        encryption: bool = True,
        compression: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ReplicationPolicy:
        with self._lock:
            p = ReplicationPolicy(
                name=name,
                source_region=source_region,
                target_region=target_region,
                mode=mode,
                resource_types=list(resource_types or []),
                max_lag_sec=max_lag_sec,
                encryption=encryption,
                compression=compression,
                metadata=dict(metadata or {}),
            )
            self._policies[p.id] = p
            # 启动一个 stream
            stream = ReplicaStream(
                policy_id=p.id,
                source_region=source_region,
                target_region=target_region,
                state=StreamState.HEALTHY,
            )
            self._streams[stream.id] = stream
            self._persist()
            return p

    def get_policy(self, policy_id: str) -> ReplicationPolicy | None:
        return self._policies.get(policy_id)

    def list_policies(
        self, source_region: str = "", target_region: str = "", enabled: bool | None = None
    ) -> list[ReplicationPolicy]:
        with self._lock:
            out: list[ReplicationPolicy] = []
            for p in self._policies.values():
                if source_region and p.source_region != source_region:
                    continue
                if target_region and p.target_region != target_region:
                    continue
                if enabled is not None and p.enabled != enabled:
                    continue
                out.append(p)
            return out

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._policies:
                del self._policies[policy_id]
                # 同步清理 stream
                for s in list(self._streams.values()):
                    if s.policy_id == policy_id:
                        del self._streams[s.id]
                self._persist()
                return True
            return False

    # ---- stream operations ----

    def list_streams(self, policy_id: str = "", state: StreamState | None = None) -> list[ReplicaStream]:
        with self._lock:
            out: list[ReplicaStream] = []
            for s in self._streams.values():
                if policy_id and s.policy_id != policy_id:
                    continue
                if state is not None and s.state != state:
                    continue
                out.append(s)
            return out

    def get_stream(self, stream_id: str) -> ReplicaStream | None:
        return self._streams.get(stream_id)

    def record_sync(self, stream_id: str, records: int, bytes_sent: int, lag_sec: float = 0.0) -> ReplicaStream:
        """记录一次成功的同步"""
        with self._lock:
            s = self._streams.get(stream_id)
            if not s:
                raise ValueError(f"stream not found: {stream_id}")
            s.records_sent += records
            s.bytes_sent += bytes_sent
            s.lag_sec = lag_sec
            s.last_sync_at = time.time()
            s.consecutive_failures = 0
            # 状态机
            policy = self._policies.get(s.policy_id)
            max_lag = policy.max_lag_sec if policy else 30.0
            if lag_sec > max_lag:
                s.state = StreamState.LAGGING
            elif s.state == StreamState.LAGGING:
                s.state = StreamState.HEALTHY
            elif s.state == StreamState.DEGRADED:
                s.state = StreamState.HEALTHY
            self._persist()
            return s

    def record_failure(self, stream_id: str, error: str, records_lost: int = 0) -> ReplicaStream:
        """记录一次复制失败"""
        with self._lock:
            s = self._streams.get(stream_id)
            if not s:
                raise ValueError(f"stream not found: {stream_id}")
            s.records_failed += records_lost
            s.consecutive_failures += 1
            s.last_error = error
            s.last_error_at = time.time()
            if s.consecutive_failures >= 10:
                s.state = StreamState.FAILED
            elif s.consecutive_failures >= 3:
                s.state = StreamState.DEGRADED
            self._persist()
            return s

    def pause_stream(self, stream_id: str) -> ReplicaStream:
        with self._lock:
            s = self._streams.get(stream_id)
            if not s:
                raise ValueError(f"stream not found: {stream_id}")
            s.state = StreamState.PAUSED
            self._persist()
            return s

    def resume_stream(self, stream_id: str) -> ReplicaStream:
        with self._lock:
            s = self._streams.get(stream_id)
            if not s:
                raise ValueError(f"stream not found: {stream_id}")
            s.state = StreamState.HEALTHY
            s.consecutive_failures = 0
            s.last_error = ""
            self._persist()
            return s

    # ---- failover ----

    def initiate_failover(
        self,
        from_region: str,
        to_region: str,
        mode: FailoverMode = FailoverMode.PLANNED,
        initiated_by: str = "",
        reason: str = "",
        affected_resources: list[str] | None = None,
    ) -> FailoverEvent:
        """启动一次灾备切换"""
        with self._lock:
            event = FailoverEvent(
                mode=mode,
                from_region=from_region,
                to_region=to_region,
                initiated_by=initiated_by,
                reason=reason,
                affected_resources=list(affected_resources or []),
                rollback_supported=(mode != FailoverMode.EMERGENCY),
            )
            self._failovers[event.id] = event
            self._persist()
            return event

    def advance_failover(self, failover_id: str, new_state: FailoverState, notes: str = "") -> FailoverEvent:
        """推进灾备切换状态"""
        with self._lock:
            ev = self._failovers.get(failover_id)
            if not ev:
                raise ValueError(f"failover not found: {failover_id}")
            ev.state = new_state
            if notes:
                ev.notes = (ev.notes + " | " + notes) if ev.notes else notes
            if new_state in (FailoverState.SWITCHED, FailoverState.ROLLED_BACK, FailoverState.FAILED):
                ev.completed_at = time.time()
                ev.duration_sec = ev.completed_at - ev.started_at
                if new_state == FailoverState.SWITCHED and ev.mode != FailoverMode.DRILL:
                    self._active_region = ev.to_region
            self._persist()
            return ev

    def complete_failover(
        self,
        failover_id: str,
        success: bool,
        data_loss_records: int = 0,
        notes: str = "",
    ) -> FailoverEvent:
        with self._lock:
            ev = self._failovers.get(failover_id)
            if not ev:
                raise ValueError(f"failover not found: {failover_id}")
            if success:
                ev.state = FailoverState.SWITCHED
                if ev.mode != FailoverMode.DRILL:
                    self._active_region = ev.to_region
            else:
                ev.state = FailoverState.FAILED
            ev.data_loss_records = data_loss_records
            ev.completed_at = time.time()
            ev.duration_sec = ev.completed_at - ev.started_at
            if notes:
                ev.notes = (ev.notes + " | " + notes) if ev.notes else notes
            self._persist()
            return ev

    def rollback_failover(self, failover_id: str, notes: str = "") -> FailoverEvent:
        with self._lock:
            ev = self._failovers.get(failover_id)
            if not ev:
                raise ValueError(f"failover not found: {failover_id}")
            if not ev.rollback_supported:
                raise ValueError("emergency failover cannot be rolled back")
            ev.state = FailoverState.ROLLED_BACK
            ev.completed_at = time.time()
            ev.duration_sec = ev.completed_at - ev.started_at
            if ev.mode != FailoverMode.DRILL:
                self._active_region = ev.from_region
            if notes:
                ev.notes = (ev.notes + " | " + notes) if ev.notes else notes
            self._persist()
            return ev

    def list_failovers(
        self, mode: FailoverMode | None = None, state: FailoverState | None = None, limit: int = 100
    ) -> list[FailoverEvent]:
        with self._lock:
            out: list[FailoverEvent] = []
            for ev in self._failovers.values():
                if mode is not None and ev.mode != mode:
                    continue
                if state is not None and ev.state != state:
                    continue
                out.append(ev)
            out.sort(key=lambda e: e.started_at, reverse=True)
            return out[:limit]

    def get_failover(self, failover_id: str) -> FailoverEvent | None:
        return self._failovers.get(failover_id)

    # ---- network partition guard ----

    def check_quorum(self, region: str, total_replicas: int, reachable_replicas: int) -> dict[str, Any]:
        """Quorum 检查: 防止脑裂写入"""
        if total_replicas <= 0:
            return {"ok": False, "reason": "no_replicas_configured", "can_write": False}
        ratio = reachable_replicas / total_replicas
        # 严格多数 (>50%)
        can_write = ratio > 0.5
        return {
            "ok": can_write,
            "region": region,
            "total_replicas": total_replicas,
            "reachable_replicas": reachable_replicas,
            "ratio": ratio,
            "can_write": can_write,
            "recommendation": "accept_writes" if can_write else "switch_to_read_only",
        }

    # ---- stats ----

    def stats(self) -> dict[str, Any]:
        with self._lock:
            stream_states: dict[str, int] = {}
            for s in self._streams.values():
                k = s.state.value
                stream_states[k] = stream_states.get(k, 0) + 1
            total_lag = sum(s.lag_sec for s in self._streams.values())
            max_lag = max((s.lag_sec for s in self._streams.values()), default=0.0)
            return {
                "total_policies": len(self._policies),
                "total_streams": len(self._streams),
                "total_failovers": len(self._failovers),
                "active_region": self._active_region,
                "stream_states": stream_states,
                "total_records_replicated": sum(s.records_sent for s in self._streams.values()),
                "total_bytes_replicated": sum(s.bytes_sent for s in self._streams.values()),
                "total_records_failed": sum(s.records_failed for s in self._streams.values()),
                "avg_lag_sec": (total_lag / len(self._streams)) if self._streams else 0.0,
                "max_lag_sec": max_lag,
            }

    # ---- persistence ----

    def _persist(self) -> None:
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "active_region": self._active_region,
                "policies": {k: v.to_dict() for k, v in self._policies.items()},
                "streams": {k: v.to_dict() for k, v in self._streams.items()},
                "failovers": {k: v.to_dict() for k, v in self._failovers.items()},
            }
            self._persist_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            self._active_region = data.get("active_region", "cn-east")
            for k, v in data.get("policies", {}).items():
                p = ReplicationPolicy(
                    name=v["name"],
                    source_region=v["source_region"],
                    target_region=v["target_region"],
                    mode=ReplicationMode(v.get("mode", "async")),
                    resource_types=v.get("resource_types", []),
                    max_lag_sec=v.get("max_lag_sec", 30.0),
                    encryption=v.get("encryption", True),
                    compression=v.get("compression", True),
                    enabled=v.get("enabled", True),
                    metadata=v.get("metadata", {}),
                )
                p.id = v.get("id", k)
                p.created_at = v.get("created_at", time.time())
                self._policies[k] = p
            for k, v in data.get("streams", {}).items():
                s = ReplicaStream(
                    policy_id=v.get("policy_id", ""),
                    source_region=v.get("source_region", ""),
                    target_region=v.get("target_region", ""),
                    state=StreamState(v.get("state", "healthy")),
                    lag_sec=v.get("lag_sec", 0.0),
                    bytes_sent=v.get("bytes_sent", 0),
                    records_sent=v.get("records_sent", 0),
                    bytes_failed=v.get("bytes_failed", 0),
                    records_failed=v.get("records_failed", 0),
                    last_error=v.get("last_error", ""),
                    last_error_at=v.get("last_error_at", 0.0),
                    last_sync_at=v.get("last_sync_at", 0.0),
                    consecutive_failures=v.get("consecutive_failures", 0),
                    started_at=v.get("started_at", time.time()),
                    metadata=v.get("metadata", {}),
                )
                s.id = v.get("id", k)
                self._streams[k] = s
            for k, v in data.get("failovers", {}).items():
                ev = FailoverEvent(
                    mode=FailoverMode(v.get("mode", "planned")),
                    state=FailoverState(v.get("state", "initiated")),
                    from_region=v.get("from_region", ""),
                    to_region=v.get("to_region", ""),
                    initiated_by=v.get("initiated_by", ""),
                    reason=v.get("reason", ""),
                    affected_resources=v.get("affected_resources", []),
                    duration_sec=v.get("duration_sec", 0.0),
                    data_loss_records=v.get("data_loss_records", 0),
                    rollback_supported=v.get("rollback_supported", True),
                    started_at=v.get("started_at", time.time()),
                    completed_at=v.get("completed_at", 0.0),
                    notes=v.get("notes", ""),
                    metadata=v.get("metadata", {}),
                )
                ev.id = v.get("id", k)
                self._failovers[k] = ev
        except Exception:
            pass


_engine: ReplicationEngine | None = None


def get_replication_engine() -> ReplicationEngine:
    global _engine
    if _engine is None:
        _engine = ReplicationEngine()
    return _engine


def reset_replication_engine() -> None:
    global _engine
    _engine = None
