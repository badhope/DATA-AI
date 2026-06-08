"""
MCP 类型定义

对齐 config/schema/mcp_schema.json v1.0.0 / 协议 2024-11-05。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MCPServerType(str, Enum):
    """MCP server 连接类型"""

    STDIO = "stdio"  # 本地子进程
    SSE = "sse"  # Server-Sent Events 长连接
    HTTP = "http"  # HTTP 一次性调用


class MCPServerStatus(str, Enum):
    """Server 状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class MCPServerConfig:
    """MCP server 配置

    与 mcp_schema.json::schemas.MCPServerConfig 一一对应。
    """

    id: str
    name: str
    type: MCPServerType = MCPServerType.STDIO
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    env: dict[str, str] = field(default_factory=dict)
    status: MCPServerStatus = MCPServerStatus.INACTIVE
    enabled: bool = True
    description: str = ""
    icon: str = "🔌"
    created_at: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at: int = field(default_factory=lambda: int(time.time() * 1000))
    last_error: str | None = None
    last_check_at: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "command": self.command,
            "args": list(self.args),
            "url": self.url,
            "env": dict(self.env),
            "status": self.status.value,
            "enabled": self.enabled,
            "description": self.description,
            "icon": self.icon,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_error": self.last_error,
            "last_check_at": self.last_check_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPServerConfig:
        return cls(
            id=data.get("id") or f"mcp-{uuid.uuid4().hex[:12]}",
            name=data.get("name") or "unnamed",
            type=MCPServerType(data.get("type", "stdio")),
            command=data.get("command", ""),
            args=list(data.get("args", []) or []),
            url=data.get("url", ""),
            env=dict(data.get("env", {}) or {}),
            status=MCPServerStatus(data.get("status", "inactive")),
            enabled=bool(data.get("enabled", True)),
            description=data.get("description", ""),
            icon=data.get("icon", "🔌"),
            created_at=int(data.get("created_at", 0) or time.time() * 1000),
            updated_at=int(data.get("updated_at", 0) or time.time() * 1000),
            last_error=data.get("last_error"),
            last_check_at=data.get("last_check_at"),
        )


@dataclass
class MCPTool:
    """MCP 工具定义

    对齐 mcp_schema.json::schemas.MCPTool。
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    server_id: str = ""
    server_name: str = ""

    def to_openai_tool(self) -> dict[str, Any]:
        """转为 OpenAI 兼容的 tool schema,便于 LLM 调用"""
        return {
            "type": "function",
            "function": {
                "name": f"mcp_{self.server_id}_{self.name}".replace("-", "_") if self.server_id else f"mcp_{self.name}",
                "description": f"[MCP:{self.server_name}] {self.description}",
                "parameters": self.input_schema,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "server_id": self.server_id,
            "server_name": self.server_name,
        }


@dataclass
class MCPResource:
    """MCP 资源定义(可选,RAG/document 来源)"""

    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"
    server_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
            "server_id": self.server_id,
        }


@dataclass
class MCPInvokeRequest:
    """MCP 工具调用请求"""

    server_id: str
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    timeout: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "server_id": self.server_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "timeout": self.timeout,
        }


@dataclass
class MCPInvokeResult:
    """MCP 工具调用结果"""

    success: bool
    content: Any = None
    error: str | None = None
    error_class: str | None = None
    duration_ms: int = 0
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    server_id: str = ""
    tool_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "error_class": self.error_class,
            "duration_ms": self.duration_ms,
            "trace_id": self.trace_id,
            "server_id": self.server_id,
            "tool_name": self.tool_name,
        }


@dataclass
class MCPHealth:
    """MCP 整体健康度"""

    status: str = "ok"
    total_servers: int = 0
    active_servers: int = 0
    error_servers: int = 0
    total_tools: int = 0
    builtin_servers: int = 0
    user_servers: int = 0
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)
    fixes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "total_servers": self.total_servers,
            "active_servers": self.active_servers,
            "error_servers": self.error_servers,
            "total_tools": self.total_tools,
            "builtin_servers": self.builtin_servers,
            "user_servers": self.user_servers,
            "trace_id": self.trace_id,
            "checks": self.checks,
            "fixes": self.fixes,
        }
