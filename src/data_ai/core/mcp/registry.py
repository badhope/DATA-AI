"""
MCP ServerRegistry

管理:
- 用户注册的 server 列表(增删改查、启停)
- builtin 预置 server(只读)
- 工具 / 资源缓存
- 调用分发到对应 server proxy
"""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from typing import Any

from ...utils.logging import get_logger
from .types import (
    MCPHealth,
    MCPInvokeRequest,
    MCPInvokeResult,
    MCPResource,
    MCPServerConfig,
    MCPServerStatus,
    MCPServerType,
    MCPTool,
)

logger = get_logger("mcp.registry")


class MCPRegistry:
    """线程安全的进程内 MCP server 注册表"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._servers: dict[str, MCPServerConfig] = {}
        self._builtin_ids: set[str] = set()  # 标记 builtin,只读
        # server_id -> [MCPTool]
        self._tools_cache: dict[str, list[MCPTool]] = {}
        # server_id -> [MCPResource]
        self._resources_cache: dict[str, list[MCPResource]] = {}

    # ── Server CRUD ─────────────────────────────────────

    def list_servers(self) -> list[MCPServerConfig]:
        with self._lock:
            return list(self._servers.values())

    def get_server(self, server_id: str) -> MCPServerConfig | None:
        with self._lock:
            return self._servers.get(server_id)

    def add_server(self, cfg: MCPServerConfig, builtin: bool = False) -> MCPServerConfig:
        if not cfg.id:
            cfg.id = f"mcp-{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._servers[cfg.id] = cfg
            if builtin:
                self._builtin_ids.add(cfg.id)
        logger.info(f"MCP server added: id={cfg.id} name={cfg.name} type={cfg.type.value} builtin={builtin}")
        return cfg

    def update_server(self, server_id: str, patch: dict[str, Any]) -> MCPServerConfig | None:
        with self._lock:
            cfg = self._servers.get(server_id)
            if cfg is None:
                return None
            if server_id in self._builtin_ids:
                # builtin 允许切换 enabled/status 但不允许改 command/args/env
                allowed = {"enabled", "status", "last_error", "last_check_at"}
                patch = {k: v for k, v in patch.items() if k in allowed}
            for k, v in patch.items():
                if hasattr(cfg, k):
                    if k == "type" and isinstance(v, str):
                        cfg.type = MCPServerType(v)
                    elif k == "status" and isinstance(v, str):
                        cfg.status = MCPServerStatus(v)
                    else:
                        setattr(cfg, k, v)
            cfg.updated_at = int(time.time() * 1000)
            # 清掉工具缓存(配置变了,工具列表可能变)
            self._tools_cache.pop(server_id, None)
            return cfg

    def remove_server(self, server_id: str) -> bool:
        with self._lock:
            if server_id not in self._servers:
                return False
            if server_id in self._builtin_ids:
                logger.warning(f"refuse to remove builtin server {server_id}")
                return False
            del self._servers[server_id]
            self._tools_cache.pop(server_id, None)
            self._resources_cache.pop(server_id, None)
        return True

    def is_builtin(self, server_id: str) -> bool:
        with self._lock:
            return server_id in self._builtin_ids

    # ── Tool / Resource 缓存 ─────────────────────────────

    def cache_tools(self, server_id: str, tools: list[MCPTool]) -> None:
        with self._lock:
            self._tools_cache[server_id] = tools

    def get_cached_tools(self, server_id: str) -> list[MCPTool]:
        with self._lock:
            return list(self._tools_cache.get(server_id, []))

    def list_all_tools(self) -> list[MCPTool]:
        with self._lock:
            out: list[MCPTool] = []
            for sid, tools in self._tools_cache.items():
                cfg = self._servers.get(sid)
                if cfg and cfg.enabled and cfg.status == MCPServerStatus.ACTIVE:
                    out.extend(tools)
            return out

    def cache_resources(self, server_id: str, resources: list[MCPResource]) -> None:
        with self._lock:
            self._resources_cache[server_id] = resources

    def list_all_resources(self) -> list[MCPResource]:
        with self._lock:
            out: list[MCPResource] = []
            for sid, resources in self._resources_cache.items():
                cfg = self._servers.get(sid)
                if cfg and cfg.enabled and cfg.status == MCPServerStatus.ACTIVE:
                    out.extend(resources)
            return out

    # ── Tool 调用 ──────────────────────────────────────

    async def invoke(self, req: MCPInvokeRequest) -> MCPInvokeResult:
        started = time.time()
        trace_id = uuid.uuid4().hex[:12]
        with self._lock:
            cfg = self._servers.get(req.server_id)
        if cfg is None:
            return MCPInvokeResult(
                success=False,
                error=f"server not found: {req.server_id}",
                error_class="ServerNotFound",
                duration_ms=int((time.time() - started) * 1000),
                trace_id=trace_id,
                server_id=req.server_id,
                tool_name=req.tool_name,
            )
        if not cfg.enabled:
            return MCPInvokeResult(
                success=False,
                error=f"server is disabled: {req.server_id}",
                error_class="ServerDisabled",
                duration_ms=int((time.time() - started) * 1000),
                trace_id=trace_id,
                server_id=req.server_id,
                tool_name=req.tool_name,
            )

        try:
            content = await asyncio.wait_for(
                self._dispatch(cfg, req),
                timeout=req.timeout,
            )
            return MCPInvokeResult(
                success=True,
                content=content,
                duration_ms=int((time.time() - started) * 1000),
                trace_id=trace_id,
                server_id=req.server_id,
                tool_name=req.tool_name,
            )
        except asyncio.TimeoutError:
            return MCPInvokeResult(
                success=False,
                error=f"invoke timeout after {req.timeout}s",
                error_class="TimeoutError",
                duration_ms=int((time.time() - started) * 1000),
                trace_id=trace_id,
                server_id=req.server_id,
                tool_name=req.tool_name,
            )
        except Exception as e:
            logger.error(f"MCP invoke failed: server={req.server_id} tool={req.tool_name} err={e!r}")
            return MCPInvokeResult(
                success=False,
                error=f"{type(e).__name__}: {e}"[:500],
                error_class=type(e).__name__,
                duration_ms=int((time.time() - started) * 1000),
                trace_id=trace_id,
                server_id=req.server_id,
                tool_name=req.tool_name,
            )

    async def _dispatch(self, cfg: MCPServerConfig, req: MCPInvokeRequest) -> Any:
        """根据 server.type / 标识 派发到具体 proxy

        - in-process (id='mcp-in-process' 或 url='in-process://...') → 进程内置
        - stdio / http / sse → MCPServerProxy
        """
        if cfg.id == "mcp-in-process" or cfg.url.startswith("in-process://"):
            from .client import get_in_process_server

            return await get_in_process_server().call_tool(req.tool_name, req.arguments)
        from .client import MCPServerProxy

        proxy = MCPServerProxy(cfg)
        return await proxy.invoke_tool(req.tool_name, req.arguments)

    # ── Health ──────────────────────────────────────────

    def health(self) -> MCPHealth:
        with self._lock:
            servers = list(self._servers.values())
            total = len(servers)
            active = sum(1 for s in servers if s.status == MCPServerStatus.ACTIVE and s.enabled)
            errors = sum(1 for s in servers if s.status == MCPServerStatus.ERROR)
            builtin = sum(1 for s in servers if s.id in self._builtin_ids)
            user = total - builtin
            total_tools = sum(len(self._tools_cache.get(s.id, [])) for s in servers)

        fixes: list[str] = []
        if total == 0:
            fixes.append("暂无 MCP server,可通过 /v1/mcp/presets 安装 builtin 或 POST /v1/mcp/servers 自定义")
        if errors > 0:
            fixes.append(f"有 {errors} 个 server 处于 error 状态,检查 last_error 字段")
        if active == 0 and total > 0:
            fixes.append("所有 server 都未激活,确认 command/url 可达,或调用 /v1/mcp/check 主动检查")

        return MCPHealth(
            status="ok" if errors == 0 else "degraded",
            total_servers=total,
            active_servers=active,
            error_servers=errors,
            total_tools=total_tools,
            builtin_servers=builtin,
            user_servers=user,
            checks={
                "servers_total": {"ok": True, "value": total},
                "servers_active": {"ok": active > 0, "value": active},
                "servers_error": {"ok": errors == 0, "value": errors},
                "tools_total": {"ok": total_tools >= 0, "value": total_tools},
            },
            fixes=fixes,
        )

    def clear_user_servers(self) -> int:
        """清空所有非 builtin server(测试/重置用)"""
        with self._lock:
            to_del = [s for s in self._servers if s not in self._builtin_ids]
            for sid in to_del:
                del self._servers[sid]
                self._tools_cache.pop(sid, None)
                self._resources_cache.pop(sid, None)
        return len(to_del)


# ── 单例 ─────────────────────────────────────

_mcp_registry: MCPRegistry | None = None
_mcp_registry_lock = threading.Lock()


def get_mcp_registry() -> MCPRegistry:
    global _mcp_registry
    with _mcp_registry_lock:
        if _mcp_registry is None:
            _mcp_registry = MCPRegistry()
    return _mcp_registry
