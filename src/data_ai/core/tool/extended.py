"""
DATA-AI 扩展文件工具集

提供完整的文件操作能力：
- 目录创建/删除/树展示
- 文件移动/复制/删除/重命名
- Glob 模式搜索
- 文件元数据查询
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ...utils.logging import get_logger

logger = get_logger(__name__)


async def directory_create(path: str, exist_ok: bool = True) -> dict:
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=exist_ok)
    return {"success": True, "path": str(dir_path.absolute()), "created": not dir_path.exists() or exist_ok}


async def directory_delete(path: str, recursive: bool = False) -> dict:
    dir_path = Path(path)
    if not dir_path.exists():
        return {"success": False, "error": f"Directory not found: {path}"}
    if not dir_path.is_dir():
        return {"success": False, "error": f"Path is not a directory: {path}"}

    if recursive:
        shutil.rmtree(dir_path)
    else:
        dir_path.rmdir()

    return {"success": True, "path": str(dir_path.absolute()), "deleted": True}


async def directory_tree(path: str, max_depth: int = 3, show_hidden: bool = False) -> dict:
    root = Path(path)
    if not root.exists():
        return {"success": False, "error": f"Path not found: {path}"}

    tree_lines = []

    def _build_tree(current: Path, prefix: str = "", depth: int = 0):
        if depth > max_depth:
            return
        try:
            items = sorted(current.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            if not show_hidden:
                items = [i for i in items if not i.name.startswith(".")]
        except PermissionError:
            return

        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            tree_lines.append(
                f"{prefix}{connector}{item.name}/" if item.is_dir() else f"{prefix}{connector}{item.name}"
            )

            if item.is_dir():
                extension = "    " if is_last else "│   "
                _build_tree(item, prefix + extension, depth + 1)

    tree_lines.append(str(root) + "/")
    _build_tree(root)

    return {
        "success": True,
        "path": str(root.absolute()),
        "tree": "\n".join(tree_lines),
        "total_lines": len(tree_lines),
    }


async def file_move(source: str, destination: str) -> dict:
    src = Path(source)
    dst = Path(destination)
    if not src.exists():
        return {"success": False, "error": f"Source not found: {source}"}

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))

    return {"success": True, "source": str(src), "destination": str(dst.absolute())}


async def file_copy(source: str, destination: str) -> dict:
    src = Path(source)
    dst = Path(destination)
    if not src.exists():
        return {"success": False, "error": f"Source not found: {source}"}

    dst.parent.mkdir(parents=True, exist_ok=True)

    if src.is_dir():
        shutil.copytree(str(src), str(dst))
    else:
        shutil.copy2(str(src), str(dst))

    return {"success": True, "source": str(src), "destination": str(dst.absolute())}


async def file_delete(path: str) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {"success": False, "error": f"File not found: {path}"}
    if not file_path.is_file():
        return {"success": False, "error": f"Path is not a file: {path}"}

    size = file_path.stat().st_size
    file_path.unlink()

    return {"success": True, "path": str(file_path), "deleted_size": size}


async def glob_search(
    pattern: str,
    path: str = ".",
    exclude_patterns: list[str] | None = None,
) -> dict:
    root = Path(path)
    if not root.exists():
        return {"success": False, "error": f"Path not found: {path}"}

    matches = sorted(root.glob(pattern))

    if exclude_patterns:
        filtered = []
        for m in matches:
            exclude = False
            for ep in exclude_patterns:
                if m.match(ep) or any(p in str(m) for p in [ep]):
                    exclude = True
                    break
            if not exclude:
                filtered.append(m)
        matches = filtered

    results = []
    for m in matches:
        try:
            stat = m.stat()
            results.append(
                {
                    "path": str(m),
                    "name": m.name,
                    "type": "directory" if m.is_dir() else "file",
                    "size": stat.st_size if m.is_file() else None,
                }
            )
        except (OSError, PermissionError):
            results.append({"path": str(m), "name": m.name, "type": "unknown", "size": None})

    return {
        "success": True,
        "pattern": pattern,
        "root": str(root.absolute()),
        "matches": results,
        "count": len(results),
    }


async def file_metadata(path: str) -> dict:
    target = Path(path)
    if not target.exists():
        return {"success": False, "error": f"Path not found: {path}"}

    stat = target.stat()

    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    return {
        "success": True,
        "path": str(target.absolute()),
        "name": target.name,
        "type": "directory" if target.is_dir() else "file",
        "size_bytes": stat.st_size,
        "size_human": _human_size(stat.st_size),
        "created": stat.st_ctime,
        "modified": stat.st_mtime,
        "accessed": stat.st_atime,
        "is_symlink": target.is_symlink(),
        "permissions": oct(stat.st_mode)[-3:],
    }


async def node_execute(code: str, timeout: int = 30) -> dict:
    import asyncio
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(code)
        temp_file = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "node",
            temp_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"Node.js execution timed out after {timeout}s")

        return {
            "stdout": stdout.decode("utf-8", errors="ignore"),
            "stderr": stderr.decode("utf-8", errors="ignore"),
            "returncode": proc.returncode,
            "success": proc.returncode == 0,
        }
    finally:
        os.unlink(temp_file)


def register_extended_tools() -> None:
    from data_ai.core.tool.registry import get_tool_registry

    registry = get_tool_registry()

    registry.register_function(
        name="directory_create",
        func=directory_create,
        description="Create a directory (including parent directories)",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to create"},
                "exist_ok": {"type": "boolean", "description": "Don't error if already exists"},
            },
            "required": ["path"],
        },
    )

    registry.register_function(
        name="directory_delete",
        func=directory_delete,
        description="Delete a directory (optionally recursively)",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to delete"},
                "recursive": {"type": "boolean", "description": "Delete recursively"},
            },
            "required": ["path"],
        },
    )

    registry.register_function(
        name="directory_tree",
        func=directory_tree,
        description="Display directory tree structure",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Root directory path"},
                "max_depth": {"type": "integer", "description": "Maximum depth to display"},
                "show_hidden": {"type": "boolean", "description": "Show hidden files"},
            },
            "required": ["path"],
        },
    )

    registry.register_function(
        name="file_move",
        func=file_move,
        description="Move or rename a file or directory",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"},
            },
            "required": ["source", "destination"],
        },
    )

    registry.register_function(
        name="file_copy",
        func=file_copy,
        description="Copy a file or directory",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path"},
                "destination": {"type": "string", "description": "Destination path"},
            },
            "required": ["source", "destination"],
        },
    )

    registry.register_function(
        name="file_delete",
        func=file_delete,
        description="Delete a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to delete"},
            },
            "required": ["path"],
        },
    )

    registry.register_function(
        name="glob_search",
        func=glob_search,
        description="Search files using glob patterns (e.g., **/*.py, src/**/*.ts)",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g., **/*.py)"},
                "path": {"type": "string", "description": "Root directory to search in"},
                "exclude_patterns": {"type": "array", "description": "Patterns to exclude"},
            },
            "required": ["pattern"],
        },
    )

    registry.register_function(
        name="file_metadata",
        func=file_metadata,
        description="Get detailed metadata for a file or directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File or directory path"},
            },
            "required": ["path"],
        },
    )

    registry.register_function(
        name="node_execute",
        func=node_execute,
        description="Execute JavaScript/Node.js code and return the result",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "JavaScript/Node.js code to execute"},
                "timeout": {"type": "integer", "description": "Execution timeout in seconds"},
            },
            "required": ["code"],
        },
    )

    logger.info(f"已注册 {9} 个扩展工具")
