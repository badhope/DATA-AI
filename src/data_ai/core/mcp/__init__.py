"""
DATA-AI MCP (Model Context Protocol) 模块

提供:
- 类型定义 (types)
- ServerRegistry 注册表 (registry)
- ServerProxy 进程间调用代理 (client)
- 进程内置轻量 MCP server (server)
- 与 ToolRegistry 互通

完全自包含,不需要安装 ``mcp`` 官方 SDK;遵循 mcp_schema.json 描述的协议形态。
"""

from __future__ import annotations

from .registry import MCPRegistry, get_mcp_registry
from .server import (
    BUILTIN_MCP_SERVERS,
    MCPServerHTTP,
    MCPServerStdio,
    load_builtin_servers,
)
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

__all__ = [
    "MCPServerConfig",
    "MCPServerStatus",
    "MCPServerType",
    "MCPTool",
    "MCPResource",
    "MCPInvokeRequest",
    "MCPInvokeResult",
    "MCPHealth",
    "MCPRegistry",
    "get_mcp_registry",
    "BUILTIN_MCP_SERVERS",
    "load_builtin_servers",
    "MCPServerStdio",
    "MCPServerHTTP",
]
