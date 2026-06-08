"""
DATA-AI 系统工具集

提供系统级操作能力：
- 系统信息查询
- 环境变量管理
- Git 操作
- HTTP 请求
"""

from __future__ import annotations

import asyncio
import os
import platform

from ...utils.logging import get_logger

logger = get_logger(__name__)


async def system_info(detail_level: str = "basic") -> dict:
    import shutil

    info = {
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "hostname": platform.node(),
            "python_version": platform.python_version(),
        },
    }

    if detail_level == "full":
        try:
            cpu_count = os.cpu_count()
            info["cpu"] = {"count": cpu_count}
        except Exception:
            pass

        try:
            if platform.system() == "Linux":
                with open("/proc/meminfo") as f:
                    meminfo = {}
                    for line in f:
                        parts = line.split()
                        if len(parts) >= 2:
                            key = parts[0].rstrip(":")
                            value = int(parts[1])
                            meminfo[key] = value
                    total_kb = meminfo.get("MemTotal", 0)
                    available_kb = meminfo.get("MemAvailable", 0)
                    info["memory"] = {
                        "total_mb": round(total_kb / 1024),
                        "available_mb": round(available_kb / 1024),
                        "used_mb": round((total_kb - available_kb) / 1024),
                        "usage_percent": round((1 - available_kb / total_kb) * 100, 1) if total_kb > 0 else 0,
                    }
            elif platform.system() == "Darwin":
                import subprocess

                result = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
                total_bytes = int(result.stdout.strip()) if result.returncode == 0 else 0
                info["memory"] = {"total_mb": round(total_bytes / 1024 / 1024)}
        except Exception:
            pass

        try:
            total, used, free = shutil.disk_usage("/")
            info["disk"] = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "usage_percent": round(used / total * 100, 1) if total > 0 else 0,
            }
        except Exception:
            pass

    return {"success": True, "info": info}


async def env_var(
    action: str,
    name: str | None = None,
    value: str | None = None,
    pattern: str | None = None,
) -> dict:
    if action == "get":
        if not name:
            return {"success": False, "error": "Variable name required for get action"}
        val = os.environ.get(name)
        if val is None:
            return {"success": False, "error": f"Variable not found: {name}"}
        return {"success": True, "name": name, "value": val}

    elif action == "set":
        if not name:
            return {"success": False, "error": "Variable name required for set action"}
        os.environ[name] = value or ""
        return {"success": True, "name": name, "value": value, "action": "set"}

    elif action == "delete":
        if not name:
            return {"success": False, "error": "Variable name required for delete action"}
        if name in os.environ:
            del os.environ[name]
            return {"success": True, "name": name, "action": "deleted"}
        return {"success": False, "error": f"Variable not found: {name}"}

    elif action == "list":
        env_vars = dict(os.environ)
        if pattern:
            env_vars = {k: v for k, v in env_vars.items() if pattern.upper() in k.upper()}

        safe_vars = {}
        for k, v in env_vars.items():
            if any(s in k.upper() for s in ["KEY", "SECRET", "TOKEN", "PASSWORD", "CREDENTIAL"]):
                safe_vars[k] = "***REDACTED***"
            else:
                safe_vars[k] = v

        return {
            "success": True,
            "variables": safe_vars,
            "count": len(safe_vars),
            "pattern": pattern,
        }

    return {"success": False, "error": f"Unknown action: {action}"}


async def git(
    command: str,
    args: str = "",
    working_dir: str = ".",
) -> dict:
    allowed_commands = [
        "status",
        "log",
        "diff",
        "add",
        "commit",
        "branch",
        "checkout",
        "stash",
        "pull",
        "push",
        "remote",
        "tag",
    ]

    if command not in allowed_commands:
        return {
            "success": False,
            "error": f"Command not allowed: {command}. Allowed: {', '.join(allowed_commands)}",
        }

    git_cmd = f"git {command} {args}".strip()

    proc = await asyncio.create_subprocess_shell(
        git_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=working_dir,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        return {"success": False, "error": "Git command timed out"}

    return {
        "success": proc.returncode == 0,
        "command": git_cmd,
        "stdout": stdout.decode("utf-8", errors="replace").strip(),
        "stderr": stderr.decode("utf-8", errors="replace").strip(),
        "returncode": proc.returncode,
    }


async def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout: int = 15,
) -> dict:
    try:
        import httpx
    except ImportError:
        return {"success": False, "error": "httpx not installed. Run: pip install httpx"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                content=body,
            )

            try:
                response_body = response.json()
            except Exception:
                response_body = response.text[:5000]

            return {
                "success": True,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response_body,
                "url": str(response.url),
            }
    except httpx.TimeoutException:
        return {"success": False, "error": f"Request timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def register_system_tools() -> None:
    from data_ai.core.tool.registry import get_tool_registry

    registry = get_tool_registry()

    registry.register_function(
        name="system_info",
        func=system_info,
        description="Get system information (OS, CPU, memory, disk, network)",
        parameters={
            "type": "object",
            "properties": {
                "detail_level": {"type": "string", "description": "Detail level: basic, full"},
            },
            "required": [],
        },
    )

    registry.register_function(
        name="env_var",
        func=env_var,
        description="Get, set, or delete environment variables",
        parameters={
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action: get, set, delete, list"},
                "name": {"type": "string", "description": "Variable name"},
                "value": {"type": "string", "description": "Variable value (for set action)"},
                "pattern": {"type": "string", "description": "Filter pattern for list (e.g., PATH, HOME)"},
            },
            "required": ["action"],
        },
    )

    registry.register_function(
        name="git",
        func=git,
        description="Execute Git operations (status, log, diff, add, commit, branch)",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Git sub-command (status, log, diff, add, commit, branch, checkout)",
                },
                "args": {"type": "string", "description": "Additional arguments"},
                "working_dir": {"type": "string", "description": "Repository path"},
            },
            "required": ["command"],
        },
    )

    registry.register_function(
        name="http_request",
        func=http_request,
        description="Make HTTP requests (GET, POST, PUT, DELETE)",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Request URL"},
                "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)"},
                "headers": {"type": "object", "description": "Request headers as JSON object"},
                "body": {"type": "string", "description": "Request body (for POST/PUT)"},
                "timeout": {"type": "integer", "description": "Request timeout in seconds"},
            },
            "required": ["url"],
        },
    )

    logger.info(f"已注册 {4} 个系统工具")
