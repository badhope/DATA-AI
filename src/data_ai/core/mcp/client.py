"""
MCP Server 代理层

负责把 invoke 实际派发到:
- stdio: 启动子进程,JSON-RPC over stdin/stdout
- sse:   长连接 (本实现用 stdlib HTTP/SSE 解析,可选 httpx)
- http:  HTTP 一次性请求 (POST tool invoke)

设计原则:
- 不强依赖 mcp 官方 SDK;任何子进程只要遵守 {"jsonrpc": "2.0", "method": ..., "params": ...} 协议即可
- subprocess 启动失败/超时/无 npx 时,优雅降级而不是崩
- 真实环境 (npx/node 可用) 下能真连;沙箱/CI 环境返回明确错误说明
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from typing import Any

from ...utils.logging import get_logger
from .types import MCPResource, MCPServerConfig, MCPServerType, MCPTool

logger = get_logger("mcp.client")


class MCPServerProxy:
    """MCP server 调用的统一代理

    用法:
        proxy = MCPServerProxy(cfg)
        result = await proxy.invoke_tool("tool_name", {"key": "value"})
        tools = await proxy.list_tools()
    """

    def __init__(self, cfg: MCPServerConfig) -> None:
        self.cfg = cfg
        self._proc: asyncio.subprocess.Process | None = None
        self._proc_lock = asyncio.Lock()

    async def list_tools(self) -> list[MCPTool]:
        """调用 server 的 tools/list,失败时返回空列表"""
        try:
            resp = await self._request("tools/list", {})
        except Exception as e:
            logger.warning(f"MCP list_tools failed: server={self.cfg.id} err={e!r}")
            return []
        tools_raw = resp.get("tools", []) if isinstance(resp, dict) else []
        out: list[MCPTool] = []
        for t in tools_raw:
            if not isinstance(t, dict):
                continue
            out.append(
                MCPTool(
                    name=t.get("name", ""),
                    description=t.get("description", ""),
                    input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
                    server_id=self.cfg.id,
                    server_name=self.cfg.name,
                )
            )
        return out

    async def list_resources(self) -> list[MCPResource]:
        try:
            resp = await self._request("resources/list", {})
        except Exception as e:
            logger.warning(f"MCP list_resources failed: server={self.cfg.id} err={e!r}")
            return []
        out: list[MCPResource] = []
        for r in resp.get("resources", []) if isinstance(resp, dict) else []:
            if not isinstance(r, dict):
                continue
            out.append(
                MCPResource(
                    uri=r.get("uri", ""),
                    name=r.get("name", ""),
                    description=r.get("description", ""),
                    mime_type=r.get("mimeType", "text/plain"),
                    server_id=self.cfg.id,
                )
            )
        return out

    async def invoke_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """调用 tools/call"""
        resp = await self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
        )
        return resp

    # ── 内部:按 type 路由 ────────────────────────────

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        if self.cfg.type == MCPServerType.STDIO:
            return await self._request_stdio(method, params)
        if self.cfg.type == MCPServerType.HTTP:
            return await self._request_http(method, params)
        if self.cfg.type == MCPServerType.SSE:
            return await self._request_sse(method, params)
        raise NotImplementedError(f"MCP transport {self.cfg.type} not supported")

    # ── stdio ─────────────────────────────────────────

    async def _request_stdio(self, method: str, params: dict[str, Any]) -> Any:
        if not self.cfg.command:
            raise RuntimeError(
                f"stdio server '{self.cfg.name}' has no command configured. "
                "Set 'command' + 'args' in the server config."
            )
        # 检查 command 是否可执行
        cmd_path = shutil.which(self.cfg.command) or self.cfg.command
        if not os.path.exists(cmd_path) and not shutil.which(self.cfg.command):
            # 提供明确错误
            raise RuntimeError(
                f"Command not found: {self.cfg.command}. "
                f"Install it (e.g. `npm i -g {self.cfg.command}`) or update server config."
            )

        async with self._proc_lock:
            # 启动子进程
            env = {**os.environ, **self.cfg.env}
            try:
                proc = await asyncio.create_subprocess_exec(
                    cmd_path,
                    *self.cfg.args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            except FileNotFoundError as e:
                raise RuntimeError(
                    f"Failed to spawn {self.cfg.command}: {e}. "
                    "Check that the command is installed and on PATH."
                )
            except Exception as e:
                raise RuntimeError(f"Failed to spawn MCP server: {e!r}")

            try:
                request = {
                    "jsonrpc": "2.0",
                    "id": int(time.time() * 1000) % 100000,
                    "method": method,
                    "params": params,
                }
                proc.stdin.write((json.dumps(request) + "\n").encode("utf-8"))
                await proc.stdin.drain()

                # 读 1 行响应
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=10.0)
                if not line:
                    err = await proc.stderr.read()
                    raise RuntimeError(
                        f"MCP server '{self.cfg.name}' closed stdout; stderr={err.decode(errors='ignore')[:300]}"
                    )
                try:
                    resp = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError as e:
                    raise RuntimeError(
                        f"MCP server returned invalid JSON: {line[:200]!r} (err={e})"
                    )
                if "error" in resp and resp["error"]:
                    raise RuntimeError(f"MCP error: {resp['error']}")
                return resp.get("result", {})
            finally:
                # 关闭子进程
                try:
                    proc.stdin.close()
                except Exception:
                    pass
                try:
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=2.0)
                except (ProcessLookupError, asyncio.TimeoutError):
                    try:
                        proc.kill()
                    except ProcessLookupError:
                        pass

    # ── http ──────────────────────────────────────────

    async def _request_http(self, method: str, params: dict[str, Any]) -> Any:
        if not self.cfg.url:
            raise RuntimeError(f"http server '{self.cfg.name}' has no url configured")
        try:
            import aiohttp  # type: ignore
        except ImportError:
            raise RuntimeError("aiohttp not installed; run `pip install aiohttp` to use HTTP MCP servers")
        timeout = aiohttp.ClientTimeout(total=20.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
            async with session.post(self.cfg.url, json=payload) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(f"HTTP {resp.status}: {body[:300]}")
                try:
                    data = json.loads(body)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Invalid JSON response: {body[:200]} (err={e})")
                if "error" in data and data["error"]:
                    raise RuntimeError(f"MCP error: {data['error']}")
                return data.get("result", {})

    # ── sse ──────────────────────────────────────────

    async def _request_sse(self, method: str, params: dict[str, Any]) -> Any:
        # SSE 简化为: GET url 拿 stream,POST url 触发;这里只做最简形式
        # 实际生产建议用 mcp 官方 SDK 或专门的 SSE 客户端
        try:
            import aiohttp  # type: ignore
        except ImportError:
            raise RuntimeError("aiohttp not installed; run `pip install aiohttp` to use SSE MCP servers")
        if not self.cfg.url:
            raise RuntimeError(f"sse server '{self.cfg.name}' has no url configured")
        timeout = aiohttp.ClientTimeout(total=20.0)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # POST 触发,响应是 SSE 流
            payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
            async with session.post(self.cfg.url, json=payload) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise RuntimeError(f"HTTP {resp.status}: {body[:300]}")
                # 读 SSE 事件
                result: dict[str, Any] | None = None
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="ignore").rstrip("\r\n")
                    if not line or not line.startswith("data:"):
                        continue
                    payload_str = line[5:].strip()
                    if not payload_str or payload_str == "[DONE]":
                        continue
                    try:
                        data = json.loads(payload_str)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(data, dict) and "result" in data:
                        result = data["result"]
                        break
                    if isinstance(data, dict) and "error" in data and data["error"]:
                        raise RuntimeError(f"MCP error: {data['error']}")
                if result is None:
                    raise RuntimeError("SSE stream ended without result")
                return result


# ── 内置 in-process MCP server (不依赖外部进程) ──────────


class InProcessMCPServer:
    """完全在进程内运行的 MCP server,自带 5 个常用 tool

    目的: 让 DATA-AI 在没有 npx/node 的环境也能"接通"MCP,
    且工具名/参数严格遵循 MCP 协议 schema,方便后续替换为真外部 server。
    """

    def __init__(self, name: str = "in-process", description: str = "") -> None:
        self.name = name
        self.description = description
        self._tools: dict[str, dict[str, Any]] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        self._tools["echo"] = {
            "description": "Echo back the input text (useful for testing MCP wiring)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to echo back"},
                },
                "required": ["text"],
            },
            "handler": self._echo,
        }
        self._tools["get_current_time"] = {
            "description": "Return current local time in ISO 8601 format",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "Optional IANA timezone (e.g. Asia/Shanghai)"},
                },
            },
            "handler": self._now,
        }
        self._tools["list_directory"] = {
            "description": "List files in a local directory (read-only MCP-style)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default '.')"},
                    "max_items": {"type": "integer", "description": "Max items to return (default 50)"},
                },
            },
            "handler": self._list_dir,
        }
        self._tools["read_text_file"] = {
            "description": "Read a text file from local filesystem (max 1MB)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"},
                },
                "required": ["path"],
            },
            "handler": self._read_file,
        }
        self._tools["calculate"] = {
            "description": "Evaluate a basic math expression (+ - * / ^ % parentheses)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression to evaluate"},
                },
                "required": ["expression"],
            },
            "handler": self._calc,
        }
        self._tools["word_count"] = {
            "description": "Count words and characters in a text",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to analyze"},
                },
                "required": ["text"],
            },
            "handler": self._word_count,
        }

    # ── handlers ─────────────────────────────────────

    async def _echo(self, text: str) -> dict[str, Any]:
        return {"echo": text, "length": len(text or "")}

    async def _now(self, timezone: str = "") -> dict[str, Any]:
        from datetime import datetime

        now = datetime.now().isoformat(timespec="seconds")
        return {"iso": now, "timezone": timezone or "local"}

    async def _list_dir(self, path: str = ".", max_items: int = 50) -> dict[str, Any]:
        from pathlib import Path

        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_dir():
            return {"error": f"directory not found: {path}"}
        items = []
        for child in sorted(p.iterdir())[: int(max_items)]:
            try:
                st = child.stat()
                items.append({
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": st.st_size if child.is_file() else None,
                })
            except (PermissionError, FileNotFoundError):
                continue
        return {"path": str(p), "count": len(items), "items": items}

    async def _read_file(self, path: str) -> dict[str, Any]:
        from pathlib import Path

        p = Path(path).expanduser().resolve()
        if not p.exists() or not p.is_file():
            return {"error": f"file not found: {path}"}
        if p.stat().st_size > 1_000_000:
            return {"error": "file too large (>1MB); use a real filesystem MCP server for big files"}
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {"error": f"read failed: {e!r}"}
        return {"path": str(p), "size": len(content), "content": content}

    async def _calc(self, expression: str) -> dict[str, Any]:
        allowed = set("0123456789+-*/().%^ ")
        if not all(c in allowed for c in expression):
            return {"error": "expression contains disallowed characters"}
        try:
            result = eval(expression, {"__builtins__": {}}, {"pow": pow, "abs": abs, "round": round})
        except Exception as e:
            return {"error": f"eval failed: {e!r}"}
        return {"expression": expression, "result": str(result)}

    async def _word_count(self, text: str) -> dict[str, Any]:
        if not text:
            return {"chars": 0, "words": 0, "lines": 0}
        words = [w for w in text.split() if w]
        return {
            "chars": len(text),
            "words": len(words),
            "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
        }

    # ── 公共 API ─────────────────────────────────────

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": name, "description": meta["description"], "inputSchema": meta["inputSchema"]}
            for name, meta in self._tools.items()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if name not in self._tools:
            return {"error": f"tool not found: {name}"}
        handler = self._tools[name]["handler"]
        try:
            return await handler(**(arguments or {}))
        except TypeError as e:
            return {"error": f"bad arguments: {e!r}"}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e!r}"}

    def to_mcp_tools(self, server_id: str = "in-process", server_name: str = "in-process") -> list[MCPTool]:
        return [
            MCPTool(
                name=name,
                description=meta["description"],
                input_schema=meta["inputSchema"],
                server_id=server_id,
                server_name=server_name,
            )
            for name, meta in self._tools.items()
        ]


# 单例
_in_process_server: InProcessMCPServer | None = None


def get_in_process_server() -> InProcessMCPServer:
    global _in_process_server
    if _in_process_server is None:
        _in_process_server = InProcessMCPServer()
    return _in_process_server
