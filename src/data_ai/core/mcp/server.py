"""
MCP server 模块

提供:
- 进程内 InProcessMCPServer (默认 / 不需要外部进程)
- builtin 预置 server 配置(从 mcp_schema.json 加载)
- 把 builtin 配置注册到 MCPRegistry 的辅助函数

注: 完整的 stdio / SSE / HTTP 真实外部 server 调用在 client.py::MCPServerProxy;
本文件聚焦"配置层"。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger
from .client import InProcessMCPServer, get_in_process_server
from .types import MCPServerConfig, MCPServerStatus, MCPServerType

logger = get_logger("mcp.server")

# 重新导出 client 中的类,供外部用 ``from data_ai.core.mcp.server import MCPServerStdio``
# 保持向后兼容(mcp_server_reference 字符串路径)
MCPServerStdio = InProcessMCPServer  # type: ignore[misc,assignment]
MCPServerHTTP = InProcessMCPServer  # type: ignore[misc,assignment]


# ── 加载 builtin 预置(对齐 mcp_schema.json::builtin_servers) ──

BUILTIN_MCP_SERVERS: list[dict[str, Any]] = [
    {
        "id": "mcp-in-process",
        "name": "DATA-AI 内置工具集",
        "description": "进程内 MCP server,提供 echo/get_current_time/list_directory/read_text_file/calculate/word_count 6 个工具,无需外部依赖。",
        "type": "http",  # 占位,实际调用走 in-process 代理
        "icon": "🧰",
        "url": "in-process://data-ai/builtin",
        "enabled": True,
        "is_builtin": True,
        "tools": [
            "echo", "get_current_time", "list_directory",
            "read_text_file", "calculate", "word_count",
        ],
    },
    {
        "id": "mcp-filesystem",
        "name": "Local Filesystem",
        "description": "Read and operate local files via @modelcontextprotocol/server-filesystem (requires npx + node).",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/"],
        "icon": "📁",
        "enabled": False,  # 默认不启用,需用户确认
        "is_builtin": True,
    },
    {
        "id": "mcp-github",
        "name": "GitHub",
        "description": "Access GitHub repositories and API (requires GITHUB_PERSONAL_ACCESS_TOKEN).",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "icon": "🐙",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-postgres",
        "name": "PostgreSQL",
        "description": "Access PostgreSQL database via MCP.",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"],
        "icon": "🐘",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-slack",
        "name": "Slack",
        "description": "Access Slack workspace via MCP.",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "icon": "💬",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-brave-search",
        "name": "Brave Search",
        "description": "Web search via Brave Search API (requires BRAVE_API_KEY).",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "icon": "🔍",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-web-playwright",
        "name": "Web Playwright",
        "description": "Browser automation via Playwright MCP server.",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-web-playwright"],
        "icon": "🌐",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-gmail",
        "name": "Gmail",
        "description": "Access Gmail messages via MCP (requires Google OAuth).",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-gmail"],
        "icon": "📧",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-google-drive",
        "name": "Google Drive",
        "description": "Access Google Drive files via MCP (requires Google OAuth).",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-google-drive"],
        "icon": "📁",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-notion",
        "name": "Notion",
        "description": "Access Notion workspace via MCP (requires Notion API key).",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-notion"],
        "icon": "📝",
        "enabled": False,
        "is_builtin": True,
    },
    {
        "id": "mcp-sequential-thinking",
        "name": "Sequential Thinking",
        "description": "Sequential thinking / chain-of-thought tool via MCP.",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"],
        "icon": "🧠",
        "enabled": False,
        "is_builtin": True,
    },
]


def load_builtin_servers(registry) -> list[MCPServerConfig]:
    """把 BUILTIN_MCP_SERVERS 注册到给定的 MCPRegistry

    约定: 名为 "DATA-AI 内置工具集" 的特殊 in-process server 总是 active,
    其它的 stdio server 默认 inactive(用户确认环境后才 enable)。
    """
    registered: list[MCPServerConfig] = []
    for entry in BUILTIN_MCP_SERVERS:
        try:
            t = MCPServerType(entry.get("type", "stdio"))
        except ValueError:
            t = MCPServerType.STDIO
        cfg = MCPServerConfig(
            id=entry["id"],
            name=entry["name"],
            type=t,
            command=entry.get("command", ""),
            args=list(entry.get("args", []) or []),
            url=entry.get("url", ""),
            env=dict(entry.get("env", {}) or {}),
            description=entry.get("description", ""),
            icon=entry.get("icon", "🔌"),
            enabled=bool(entry.get("enabled", False)),
            status=MCPServerStatus.ACTIVE if entry.get("id") == "mcp-in-process" else MCPServerStatus.INACTIVE,
        )
        registry.add_server(cfg, builtin=True)
        registered.append(cfg)

    # 立即把 in-process server 的工具缓存到 registry
    in_proc = get_in_process_server()
    in_proc_tools = in_proc.to_mcp_tools(server_id="mcp-in-process", server_name="DATA-AI 内置工具集")
    registry.cache_tools("mcp-in-process", in_proc_tools)

    logger.info(f"loaded {len(registered)} builtin MCP servers (in-process active: 1)")
    return registered


def patch_builtin_servers_from_schema(schema_path: str | Path) -> int:
    """从 mcp_schema.json 动态加载 builtin_servers 段(用于配置覆盖)

    返回被更新的 server 数。
    """
    p = Path(schema_path)
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"failed to read mcp_schema.json: {e!r}")
        return 0
    builtin = data.get("builtin_servers", {}) or {}
    count = 0
    for sid, meta in builtin.items():
        idx = next((i for i, s in enumerate(BUILTIN_MCP_SERVERS) if s["id"] == f"mcp-{sid}"), -1)
        if idx < 0:
            continue
        BUILTIN_MCP_SERVERS[idx].update({
            "name": meta.get("name", BUILTIN_MCP_SERVERS[idx]["name"]),
            "description": meta.get("description", BUILTIN_MCP_SERVERS[idx]["description"]),
            "type": meta.get("type", BUILTIN_MCP_SERVERS[idx]["type"]),
            "command": meta.get("command", BUILTIN_MCP_SERVERS[idx]["command"]),
            "args": meta.get("args", BUILTIN_MCP_SERVERS[idx]["args"]),
            "icon": meta.get("icon", BUILTIN_MCP_SERVERS[idx].get("icon", "🔌")),
        })
        count += 1
    return count
