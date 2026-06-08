"""
DATA-AI 企业级 — 灾难恢复 (备份/恢复/演练)

企业痛点:
- 数据丢了能恢复吗? (RPO / RTO)
- 谁来定备份策略? (保留期 / 频率)
- 备份能不能用, 多久没演练了?
- 误删能回滚吗? (PIT restore)
- 合规要求: SOC2 / ISO27001 / GDPR right-to-erasure vs backup retention

设计:
- BackupSchedule: 备份计划 (cron + 保留策略 + 目标存储)
- BackupRecord: 单次备份快照 (size, checksum, status)
- RestorePoint: 可恢复点 (snapshot + PIT)
- RestoreJob: 恢复任务 (source → target, 进度)
- DRDrill: 灾备演练 (不破坏数据, 验证可恢复)
- RetentionPolicy: 合规保留 (per_regulation, hold_until)
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class BackupType(str, Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SNAPSHOT = "snapshot"


class BackupStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    EXPIRED = "expired"
    CORRUPTED = "corrupted"


class RestoreStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class DrillResult(str, Enum):
    PASS = "pass"
    PASS_WITH_ISSUES = "pass_with_issues"
    FAIL = "fail"


@dataclass
class BackupSchedule:
    """备份计划"""

    id: str = field(default_factory=lambda: f"bs-{uuid.uuid4().hex[:8]}")
    name: str = ""
    resource_type: str = "all"  # agent / team / memory / rag / all
    backup_type: BackupType = BackupType.FULL
    cron_expr: str = "0 2 * * *"  # 每天凌晨2点
    retention_days: int = 30
    target_regions: list[str] = field(default_factory=lambda: ["cn-east"])
    storage_class: str = "standard"  # standard / cold / archive
    encryption: bool = True
    enabled: bool = True
    next_run_at: float = 0.0
    last_run_at: float = 0.0
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["backup_type"] = self.backup_type.value
        return d


@dataclass
class BackupRecord:
    """单次备份记录"""

    id: str = field(default_factory=lambda: f"bk-{uuid.uuid4().hex[:8]}")
    schedule_id: str = ""
    resource_type: str = "all"
    backup_type: BackupType = BackupType.FULL
    status: BackupStatus = BackupStatus.PENDING
    size_bytes: int = 0
    record_count: int = 0
    checksum: str = ""
    target_region: str = ""
    storage_path: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    duration_sec: float = 0.0
    expires_at: float = 0.0
    error: str = ""
    encrypted: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["backup_type"] = self.backup_type.value
        d["status"] = self.status.value
        return d

    @property
    def is_usable(self) -> bool:
        return self.status == BackupStatus.SUCCESS and self.checksum and not self.error


@dataclass
class RestoreJob:
    """恢复任务"""

    id: str = field(default_factory=lambda: f"rj-{uuid.uuid4().hex[:8]}")
    backup_id: str = ""
    target_region: str = ""
    target_resource: str = ""
    status: RestoreStatus = RestoreStatus.PENDING
    progress_pct: float = 0.0
    records_restored: int = 0
    requested_by: str = ""
    reason: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    duration_sec: float = 0.0
    validation_passed: bool = False
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class DRDrill:
    """灾备演练"""

    id: str = field(default_factory=lambda: f"dr-{uuid.uuid4().hex[:8]}")
    name: str = ""
    schedule_id: str = ""
    backup_id: str = ""
    target_region: str = ""
    result: DrillResult = DrillResult.PASS
    rto_actual_sec: float = 0.0  # 实际恢复时间
    rpo_actual_sec: float = 0.0  # 实际数据丢失窗口
    rto_target_sec: float = 3600.0  # 目标 RTO
    rpo_target_sec: float = 300.0  # 目标 RPO
    records_verified: int = 0
    records_mismatch: int = 0
    issues: list[str] = field(default_factory=list)
    conducted_by: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["result"] = self.result.value
        return d

    @property
    def rto_met(self) -> bool:
        return self.rto_actual_sec <= self.rto_target_sec

    @property
    def rpo_met(self) -> bool:
        return self.rpo_actual_sec <= self.rpo_target_sec


@dataclass
class RetentionHold:
    """合规保留锁定 (legal hold / GDPR right-to-erasure 等)"""

    id: str = field(default_factory=lambda: f"rh-{uuid.uuid4().hex[:8]}")
    resource_id: str = ""
    regulation: str = ""  # gdpr / hipaa / sox / iso27001 / legal_hold
    action: Literal["preserve", "erase"] = "preserve"
    hold_until: float = 0.0
    reason: str = ""
    requested_by: str = ""
    created_at: float = field(default_factory=time.time)
    released_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecoveryEngine:
    """灾备恢复引擎"""

    def __init__(self, persist_path: str | None = None) -> None:
        self._lock = threading.RLock()
        self._schedules: dict[str, BackupSchedule] = {}
        self._backups: dict[str, BackupRecord] = {}
        self._restores: dict[str, RestoreJob] = {}
        self._drills: dict[str, DRDrill] = {}
        self._holds: dict[str, RetentionHold] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path:
            self._load()

    # ---- schedule ----

    def create_schedule(
        self,
        name: str,
        resource_type: str = "all",
        backup_type: BackupType = BackupType.FULL,
        cron_expr: str = "0 2 * * *",
        retention_days: int = 30,
        target_regions: list[str] | None = None,
        storage_class: str = "standard",
        encryption: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> BackupSchedule:
        with self._lock:
            s = BackupSchedule(
                name=name,
                resource_type=resource_type,
                backup_type=backup_type,
                cron_expr=cron_expr,
                retention_days=retention_days,
                target_regions=list(target_regions or ["cn-east"]),
                storage_class=storage_class,
                encryption=encryption,
                metadata=dict(metadata or {}),
            )
            s.next_run_at = _next_cron_time(cron_expr, time.time())
            self._schedules[s.id] = s
            self._persist()
            return s

    def list_schedules(self, enabled: bool | None = None) -> list[BackupSchedule]:
        with self._lock:
            out: list[BackupSchedule] = []
            for s in self._schedules.values():
                if enabled is not None and s.enabled != enabled:
                    continue
                out.append(s)
            return out

    def get_schedule(self, schedule_id: str) -> BackupSchedule | None:
        return self._schedules.get(schedule_id)

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._lock:
            if schedule_id in self._schedules:
                del self._schedules[schedule_id]
                self._persist()
                return True
            return False

    def set_schedule_enabled(self, schedule_id: str, enabled: bool) -> BackupSchedule | None:
        with self._lock:
            s = self._schedules.get(schedule_id)
            if not s:
                return None
            s.enabled = enabled
            self._persist()
            return s

    # ---- backup execution ----

    def trigger_backup(
        self,
        schedule_id: str,
        record_count: int = 0,
        target_region: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BackupRecord:
        """手动触发一次备份 (用于测试或即时备份)"""
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if not schedule:
                raise ValueError(f"schedule not found: {schedule_id}")
            region = target_region or (schedule.target_regions[0] if schedule.target_regions else "cn-east")
            # 模拟备份内容
            content = f"backup-{schedule_id}-{time.time()}-{record_count}".encode()
            checksum = hashlib.sha256(content).hexdigest()
            backup = BackupRecord(
                schedule_id=schedule_id,
                resource_type=schedule.resource_type,
                backup_type=schedule.backup_type,
                status=BackupStatus.SUCCESS,
                size_bytes=len(content),
                record_count=record_count,
                checksum=checksum,
                target_region=region,
                storage_path=f"/backups/{region}/{schedule_id}/{checksum[:12]}.bak",
                started_at=time.time(),
                completed_at=time.time(),
                duration_sec=0.001,
                expires_at=time.time() + schedule.retention_days * 86400,
                encrypted=schedule.encryption,
                metadata=dict(metadata or {}),
            )
            self._backups[backup.id] = backup
            schedule.last_run_at = backup.completed_at
            schedule.next_run_at = _next_cron_time(schedule.cron_expr, time.time())
            self._persist()
            return backup

    def list_backups(
        self,
        schedule_id: str = "",
        status: BackupStatus | None = None,
        region: str = "",
        limit: int = 100,
    ) -> list[BackupRecord]:
        with self._lock:
            out: list[BackupRecord] = []
            for b in self._backups.values():
                if schedule_id and b.schedule_id != schedule_id:
                    continue
                if status is not None and b.status != status:
                    continue
                if region and b.target_region != region:
                    continue
                out.append(b)
            out.sort(key=lambda b: b.started_at, reverse=True)
            return out[:limit]

    def get_backup(self, backup_id: str) -> BackupRecord | None:
        return self._backups.get(backup_id)

    def verify_backup(self, backup_id: str) -> dict[str, Any]:
        """校验备份完整性"""
        with self._lock:
            b = self._backups.get(backup_id)
            if not b:
                return {"ok": False, "error": "backup_not_found"}
            if b.status != BackupStatus.SUCCESS:
                return {"ok": False, "error": "backup_not_success", "status": b.status.value}
            if time.time() > b.expires_at:
                return {"ok": False, "error": "backup_expired"}
            return {
                "ok": True,
                "backup_id": backup_id,
                "checksum": b.checksum,
                "size_bytes": b.size_bytes,
                "record_count": b.record_count,
                "age_days": (time.time() - b.started_at) / 86400,
            }

    def expire_old_backups(self) -> int:
        """清理过期备份"""
        with self._lock:
            now = time.time()
            count = 0
            for b in self._backups.values():
                if b.status == BackupStatus.SUCCESS and now > b.expires_at:
                    b.status = BackupStatus.EXPIRED
                    count += 1
            if count:
                self._persist()
            return count

    # ---- restore ----

    def create_restore(
        self,
        backup_id: str,
        target_region: str = "",
        target_resource: str = "",
        requested_by: str = "",
        reason: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RestoreJob:
        with self._lock:
            backup = self._backups.get(backup_id)
            if not backup:
                raise ValueError(f"backup not found: {backup_id}")
            if not backup.is_usable:
                raise ValueError(f"backup not usable: status={backup.status.value}, error={backup.error}")
            region = target_region or backup.target_region
            job = RestoreJob(
                backup_id=backup_id,
                target_region=region,
                target_resource=target_resource,
                status=RestoreStatus.PENDING,
                requested_by=requested_by,
                reason=reason,
                metadata=dict(metadata or {}),
            )
            self._restores[job.id] = job
            self._persist()
            return job

    def advance_restore(
        self,
        restore_id: str,
        status: RestoreStatus,
        progress_pct: float | None = None,
        records_restored: int | None = None,
        error: str = "",
        validation_passed: bool | None = None,
    ) -> RestoreJob:
        with self._lock:
            job = self._restores.get(restore_id)
            if not job:
                raise ValueError(f"restore not found: {restore_id}")
            job.status = status
            if progress_pct is not None:
                job.progress_pct = max(0.0, min(100.0, progress_pct))
            if records_restored is not None:
                job.records_restored = records_restored
            if error:
                job.error = error
            if validation_passed is not None:
                job.validation_passed = validation_passed
            if status in (RestoreStatus.SUCCESS, RestoreStatus.FAILED, RestoreStatus.ROLLED_BACK):
                job.completed_at = time.time()
                job.duration_sec = job.completed_at - job.started_at
            self._persist()
            return job

    def list_restores(
        self,
        backup_id: str = "",
        status: RestoreStatus | None = None,
        limit: int = 100,
    ) -> list[RestoreJob]:
        with self._lock:
            out: list[RestoreJob] = []
            for j in self._restores.values():
                if backup_id and j.backup_id != backup_id:
                    continue
                if status is not None and j.status != status:
                    continue
                out.append(j)
            out.sort(key=lambda j: j.started_at, reverse=True)
            return out[:limit]

    def get_restore(self, restore_id: str) -> RestoreJob | None:
        return self._restores.get(restore_id)

    # ---- DR drill ----

    def run_drill(
        self,
        name: str,
        schedule_id: str = "",
        backup_id: str = "",
        target_region: str = "",
        rto_target_sec: float = 3600.0,
        rpo_target_sec: float = 300.0,
        conducted_by: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> DRDrill:
        """执行一次灾备演练"""
        with self._lock:
            # 优先用 backup_id; 否则从 schedule 找最近一次成功备份
            if not backup_id:
                backups = self.list_backups(schedule_id=schedule_id, status=BackupStatus.SUCCESS, limit=1)
                if not backups:
                    raise ValueError("no usable backup found for drill")
                backup_id = backups[0].id
            backup = self._backups.get(backup_id)
            if not backup:
                raise ValueError(f"backup not found: {backup_id}")
            started = time.time()
            # 模拟恢复耗时 (备份大小 / 100MB/s)
            rto_actual = max(0.1, backup.size_bytes / (100 * 1024 * 1024))
            rpo_actual = max(0.0, started - backup.completed_at)
            records_verified = backup.record_count
            records_mismatch = 0
            issues: list[str] = []
            # 判断 RTO/RPO 是否达成
            rto_ok = rto_actual <= rto_target_sec
            rpo_ok = rpo_actual <= rpo_target_sec
            if rto_ok and rpo_ok and records_mismatch == 0:
                result = DrillResult.PASS
            elif records_mismatch == 0:
                result = DrillResult.PASS_WITH_ISSUES
                if not rto_ok:
                    issues.append(f"RTO exceeded: {rto_actual:.1f}s > target {rto_target_sec:.1f}s")
                if not rpo_ok:
                    issues.append(f"RPO exceeded: {rpo_actual:.1f}s > target {rpo_target_sec:.1f}s")
            else:
                result = DrillResult.FAIL
                issues.append(f"records mismatch: {records_mismatch}/{records_verified}")
            drill = DRDrill(
                name=name,
                schedule_id=schedule_id,
                backup_id=backup_id,
                target_region=target_region or backup.target_region,
                result=result,
                rto_actual_sec=rto_actual,
                rpo_actual_sec=rpo_actual,
                rto_target_sec=rto_target_sec,
                rpo_target_sec=rpo_target_sec,
                records_verified=records_verified,
                records_mismatch=records_mismatch,
                issues=issues,
                conducted_by=conducted_by,
                started_at=started,
                completed_at=time.time(),
                notes=notes,
                metadata=dict(metadata or {}),
            )
            self._drills[drill.id] = drill
            self._persist()
            return drill

    def list_drills(self, result: DrillResult | None = None, limit: int = 50) -> list[DRDrill]:
        with self._lock:
            out: list[DRDrill] = []
            for d in self._drills.values():
                if result is not None and d.result != result:
                    continue
                out.append(d)
            out.sort(key=lambda d: d.started_at, reverse=True)
            return out[:limit]

    # ---- retention hold ----

    def create_hold(
        self,
        resource_id: str,
        regulation: str,
        action: Literal["preserve", "erase"] = "preserve",
        hold_until: float = 0.0,
        reason: str = "",
        requested_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> RetentionHold:
        with self._lock:
            h = RetentionHold(
                resource_id=resource_id,
                regulation=regulation,
                action=action,
                hold_until=hold_until,
                reason=reason,
                requested_by=requested_by,
                metadata=dict(metadata or {}),
            )
            self._holds[h.id] = h
            self._persist()
            return h

    def release_hold(self, hold_id: str) -> RetentionHold | None:
        with self._lock:
            h = self._holds.get(hold_id)
            if not h:
                return None
            h.released_at = time.time()
            self._persist()
            return h

    def list_holds(
        self,
        resource_id: str = "",
        regulation: str = "",
        active_only: bool = False,
    ) -> list[RetentionHold]:
        with self._lock:
            out: list[RetentionHold] = []
            for h in self._holds.values():
                if resource_id and h.resource_id != resource_id:
                    continue
                if regulation and h.regulation != regulation:
                    continue
                if active_only and h.released_at > 0:
                    continue
                out.append(h)
            return out

    def check_resource_action(self, resource_id: str, action: Literal["delete", "modify"]) -> dict[str, Any]:
        """检查资源是否被合规锁定了"""
        with self._lock:
            holds = [h for h in self._holds.values() if h.resource_id == resource_id and h.released_at == 0]
            if not holds:
                return {"blocked": False, "holds": []}
            # 如果 hold 要求 erase, 允许 delete; 否则阻止
            blocked = any(h.action == "preserve" and action == "delete" for h in holds)
            return {
                "blocked": blocked,
                "holds": [h.to_dict() for h in holds],
                "message": "resource is under retention hold" if blocked else "hold requires erasure, action allowed",
            }

    # ---- stats ----

    def stats(self) -> dict[str, Any]:
        with self._lock:
            backup_status: dict[str, int] = {}
            for b in self._backups.values():
                k = b.status.value
                backup_status[k] = backup_status.get(k, 0) + 1
            drill_results: dict[str, int] = {}
            for d in self._drills.values():
                k = d.result.value
                drill_results[k] = drill_results.get(k, 0) + 1
            total_size = sum(b.size_bytes for b in self._backups.values() if b.status == BackupStatus.SUCCESS)
            return {
                "total_schedules": len(self._schedules),
                "total_backups": len(self._backups),
                "total_restores": len(self._restores),
                "total_drills": len(self._drills),
                "total_holds": len(self._holds),
                "active_holds": sum(1 for h in self._holds.values() if h.released_at == 0),
                "backup_status": backup_status,
                "drill_results": drill_results,
                "total_backup_size_bytes": total_size,
            }

    # ---- persistence ----

    def _persist(self) -> None:
        if not self._persist_path:
            return
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "schedules": {k: v.to_dict() for k, v in self._schedules.items()},
                "backups": {k: v.to_dict() for k, v in self._backups.items()},
                "restores": {k: v.to_dict() for k, v in self._restores.items()},
                "drills": {k: v.to_dict() for k, v in self._drills.items()},
                "holds": {k: v.to_dict() for k, v in self._holds.items()},
            }
            self._persist_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            for k, v in data.get("schedules", {}).items():
                s = BackupSchedule(
                    name=v["name"],
                    resource_type=v.get("resource_type", "all"),
                    backup_type=BackupType(v.get("backup_type", "full")),
                    cron_expr=v.get("cron_expr", "0 2 * * *"),
                    retention_days=v.get("retention_days", 30),
                    target_regions=v.get("target_regions", []),
                    storage_class=v.get("storage_class", "standard"),
                    encryption=v.get("encryption", True),
                    enabled=v.get("enabled", True),
                    next_run_at=v.get("next_run_at", 0.0),
                    last_run_at=v.get("last_run_at", 0.0),
                    metadata=v.get("metadata", {}),
                )
                s.id = v.get("id", k)
                s.created_at = v.get("created_at", time.time())
                self._schedules[k] = s
            for k, v in data.get("backups", {}).items():
                b = BackupRecord(
                    schedule_id=v.get("schedule_id", ""),
                    resource_type=v.get("resource_type", "all"),
                    backup_type=BackupType(v.get("backup_type", "full")),
                    status=BackupStatus(v.get("status", "pending")),
                    size_bytes=v.get("size_bytes", 0),
                    record_count=v.get("record_count", 0),
                    checksum=v.get("checksum", ""),
                    target_region=v.get("target_region", ""),
                    storage_path=v.get("storage_path", ""),
                    started_at=v.get("started_at", time.time()),
                    completed_at=v.get("completed_at", 0.0),
                    duration_sec=v.get("duration_sec", 0.0),
                    expires_at=v.get("expires_at", 0.0),
                    error=v.get("error", ""),
                    encrypted=v.get("encrypted", True),
                    metadata=v.get("metadata", {}),
                )
                b.id = v.get("id", k)
                self._backups[k] = b
            for k, v in data.get("restores", {}).items():
                j = RestoreJob(
                    backup_id=v.get("backup_id", ""),
                    target_region=v.get("target_region", ""),
                    target_resource=v.get("target_resource", ""),
                    status=RestoreStatus(v.get("status", "pending")),
                    progress_pct=v.get("progress_pct", 0.0),
                    records_restored=v.get("records_restored", 0),
                    requested_by=v.get("requested_by", ""),
                    reason=v.get("reason", ""),
                    started_at=v.get("started_at", time.time()),
                    completed_at=v.get("completed_at", 0.0),
                    duration_sec=v.get("duration_sec", 0.0),
                    validation_passed=v.get("validation_passed", False),
                    error=v.get("error", ""),
                    metadata=v.get("metadata", {}),
                )
                j.id = v.get("id", k)
                self._restores[k] = j
            for k, v in data.get("drills", {}).items():
                d = DRDrill(
                    name=v["name"],
                    schedule_id=v.get("schedule_id", ""),
                    backup_id=v.get("backup_id", ""),
                    target_region=v.get("target_region", ""),
                    result=DrillResult(v.get("result", "pass")),
                    rto_actual_sec=v.get("rto_actual_sec", 0.0),
                    rpo_actual_sec=v.get("rpo_actual_sec", 0.0),
                    rto_target_sec=v.get("rto_target_sec", 3600.0),
                    rpo_target_sec=v.get("rpo_target_sec", 300.0),
                    records_verified=v.get("records_verified", 0),
                    records_mismatch=v.get("records_mismatch", 0),
                    issues=v.get("issues", []),
                    conducted_by=v.get("conducted_by", ""),
                    started_at=v.get("started_at", time.time()),
                    completed_at=v.get("completed_at", 0.0),
                    notes=v.get("notes", ""),
                    metadata=v.get("metadata", {}),
                )
                d.id = v.get("id", k)
                self._drills[k] = d
            for k, v in data.get("holds", {}).items():
                h = RetentionHold(
                    resource_id=v.get("resource_id", ""),
                    regulation=v.get("regulation", ""),
                    action=v.get("action", "preserve"),
                    hold_until=v.get("hold_until", 0.0),
                    reason=v.get("reason", ""),
                    requested_by=v.get("requested_by", ""),
                    created_at=v.get("created_at", time.time()),
                    released_at=v.get("released_at", 0.0),
                    metadata=v.get("metadata", {}),
                )
                h.id = v.get("id", k)
                self._holds[k] = h
        except Exception:
            pass


# ---- helpers ----


def _next_cron_time(expr: str, from_ts: float) -> float:
    """简化版: 不解析完整 cron,只支持预设 '0 2 * * *' (每天2点) 等"""
    # 简单实现: 如果 cron 解析失败, 返回 from + 86400 (明天)
    try:
        parts = expr.split()
        if len(parts) != 5:
            return from_ts + 86400
        minute, hour = parts[0], parts[1]
        if minute == "*" or hour == "*":
            return from_ts + 3600
        from datetime import datetime, timedelta

        dt = datetime.fromtimestamp(from_ts)
        target = dt.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
        if target.timestamp() <= from_ts:
            target += timedelta(days=1)
        return target.timestamp()
    except Exception:
        return from_ts + 86400


_engine: RecoveryEngine | None = None


def get_recovery_engine() -> RecoveryEngine:
    global _engine
    if _engine is None:
        _engine = RecoveryEngine()
    return _engine


def reset_recovery_engine() -> None:
    global _engine
    _engine = None
