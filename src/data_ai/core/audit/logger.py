"""
DATA-AI 企业级 — 审计日志模块

核心能力:
- 全 API 调用自动埋点 (who/what/when/result)
- 按 actor / resource / action / time 范围查询
- 持久化到 JSONL 文件 (审计证据) + 内存索引
- 导出 (JSON / CSV) 给合规/审计员

合规场景:
- SOX: 谁在何时改了某个 Agent / Skill / 数据
- GDPR: 个人数据访问/修改/删除全留痕
- 内部安全: 异常调用模式分析 (大模型 cost 异常飙升)
"""

from __future__ import annotations

import csv
import io
import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass
class AuditEntry:
    """单条审计记录"""

    id: str = field(default_factory=lambda: f"aud-{uuid.uuid4().hex[:12]}")
    timestamp: float = field(default_factory=time.time)
    actor: str = "system"  # api-key hash / "system" / "anonymous"
    actor_type: Literal["api_key", "user", "system", "anonymous"] = "system"
    action: str = ""  # e.g. "agent.create", "memory.delete", "rag.upload"
    resource_type: str = ""  # e.g. "agent", "memory", "rag_document"
    resource_id: str = ""
    method: str = ""  # HTTP method
    path: str = ""  # HTTP path
    status_code: int = 200
    duration_ms: float = 0.0
    ip: str = ""
    user_agent: str = ""
    request_body: dict[str, Any] | None = None  # 红敏后(脱敏)
    response_summary: str = ""  # 截断后的响应摘要
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AuditEntry:
        return cls(**d)


class AuditStore:
    """审计日志存储 (内存索引 + JSONL 持久化)"""

    def __init__(self, persist_path: Path | None = None, max_memory: int = 5000) -> None:
        self._lock = threading.RLock()
        self._entries: list[AuditEntry] = []
        self._max_memory = max_memory
        self._persist_path: Path | None = persist_path
        if persist_path:
            persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    # ---------- 写 ----------
    def append(self, entry: AuditEntry) -> None:
        with self._lock:
            self._entries.append(entry)
            # 内存超限 → 老化最早的
            if len(self._entries) > self._max_memory:
                self._entries = self._entries[-self._max_memory :]
            if self._persist_path:
                self._write_line(entry)

    # ---------- 读 ----------
    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        status_code: int | None = None,
        since: float | None = None,
        until: float | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        with self._lock:
            results: list[dict[str, Any]] = []
            # 倒序遍历:最新优先
            for entry in reversed(self._entries):
                if actor and entry.actor != actor:
                    continue
                if action and entry.action != action:
                    continue
                if resource_type and entry.resource_type != resource_type:
                    continue
                if resource_id and entry.resource_id != resource_id:
                    continue
                if status_code is not None and entry.status_code != status_code:
                    continue
                if since is not None and entry.timestamp < since:
                    continue
                if until is not None and entry.timestamp > until:
                    continue
                results.append(entry.to_dict())
            return results[offset : offset + limit]

    def count(
        self,
        actor: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
    ) -> int:
        with self._lock:
            n = 0
            for e in self._entries:
                if actor and e.actor != actor:
                    continue
                if action and e.action != action:
                    continue
                if resource_type and e.resource_type != resource_type:
                    continue
                n += 1
            return n

    def stats(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._entries)
            by_status: dict[str, int] = {}
            by_action: dict[str, int] = {}
            for e in self._entries:
                by_status[str(e.status_code)] = by_status.get(str(e.status_code), 0) + 1
                by_action[e.action] = by_action.get(e.action, 0) + 1
            top_actions = sorted(by_action.items(), key=lambda x: x[1], reverse=True)[:10]
            return {
                "total": total,
                "by_status": by_status,
                "top_actions": [{"action": a, "count": c} for a, c in top_actions],
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            if self._persist_path and self._persist_path.exists():
                self._persist_path.unlink()

    # ---------- 导出 ----------
    def export_json(self, entries: list[dict[str, Any]] | None = None) -> str:
        data = entries if entries is not None else [e.to_dict() for e in self._entries]
        return json.dumps(data, ensure_ascii=False, indent=2)

    def export_csv(self, entries: list[dict[str, Any]] | None = None) -> str:
        data = entries if entries is not None else [e.to_dict() for e in self._entries]
        if not data:
            return ""
        buf = io.StringIO()
        fields = list(data[0].keys())
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        for row in data:
            # 复杂字段 → JSON 字符串
            row_flat = {
                k: (json.dumps(v, ensure_ascii=False) if isinstance(v, dict | list) else v) for k, v in row.items()
            }
            writer.writerow(row_flat)
        return buf.getvalue()

    # ---------- 持久化 ----------
    def _write_line(self, entry: AuditEntry) -> None:
        if not self._persist_path:
            return
        try:
            with self._persist_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            # 审计失败不能影响主流程,但要打 log
            from data_ai.utils.logging import get_logger

            get_logger("audit").error(f"audit persist failed: {e}")

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
                        d = json.loads(line)
                        self._entries.append(AuditEntry.from_dict(d))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:  # noqa: BLE001
            from data_ai.utils.logging import get_logger

            get_logger("audit").error(f"audit load failed: {e}")


# ============================================================================
# 全局单例 + 上下文装饰器
# ============================================================================

_GLOBAL_STORE: AuditStore | None = None
_GLOBAL_LOCK = threading.Lock()


def get_audit_store(persist_path: Path | None = None) -> AuditStore:
    """获取全局审计存储 (单例)"""
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        if _GLOBAL_STORE is None:
            _GLOBAL_STORE = AuditStore(persist_path=persist_path)
        return _GLOBAL_STORE


def reset_audit_store() -> None:
    """重置全局审计存储 (测试用)"""
    global _GLOBAL_STORE
    with _GLOBAL_LOCK:
        _GLOBAL_STORE = None


# ---------- FastAPI 中间件 (自动埋点) ----------


def _redact(value: Any, depth: int = 0) -> Any:
    """脱敏:api_key / password / token 字段替换为 ***"""
    if depth > 4:
        return "..."
    if isinstance(value, dict):
        return {
            k: (
                "***REDACTED***"
                if any(s in k.lower() for s in ("password", "token", "api_key", "secret"))
                else _redact(v, depth + 1)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v, depth + 1) for v in value[:50]]
    return value


def _classify_resource(path: str) -> tuple[str, str]:
    """从 URL 路径推断 resource_type / resource_id"""
    # /v1/agents/abc-123 → ("agent", "abc-123")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3 and parts[0] == "v1":
        rt = parts[1].rstrip("s")  # agents→agent
        rid = parts[2] if len(parts) >= 3 and parts[2] not in ("run", "runs", "delegate-many", "presets") else ""
        return rt, rid
    return "", ""


def install_audit_middleware(app: Any, store: AuditStore | None = None) -> None:
    """给 FastAPI app 装上自动审计中间件"""
    from fastapi import Request

    audit_store = store or get_audit_store()

    @app.middleware("http")
    async def _audit_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        if not request.url.path.startswith("/v1") and request.url.path not in ("/health", "/v1/extensions/health"):
            return await call_next(request)

        start = time.time()
        # 读 body (限制大小,避免巨大 payload)
        body_bytes = await request.body()
        try:
            body_json = json.loads(body_bytes) if body_bytes else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            body_json = None

        # 重新塞回去给后续 handler
        async def _receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request._receive = _receive  # type: ignore[attr-defined]

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:  # noqa: BLE001
            status_code = 500
            response = None
            raise e
        finally:
            duration = (time.time() - start) * 1000
            rt, rid = _classify_resource(request.url.path)
            entry = AuditEntry(
                actor=request.headers.get("X-Actor", "anonymous"),
                actor_type="api_key" if "Authorization" in request.headers else "anonymous",
                action=f"{request.method.lower()}.{rt or 'unknown'}",
                resource_type=rt,
                resource_id=rid,
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                duration_ms=round(duration, 2),
                ip=request.client.host if request.client else "",
                user_agent=request.headers.get("user-agent", ""),
                request_body=_redact(body_json) if isinstance(body_json, dict) else None,
            )
            audit_store.append(entry)

        return response
