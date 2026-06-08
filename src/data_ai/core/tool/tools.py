"""
DATA-AI 内置工具集

提供核心工具实现：
- 文件操作工具
- 代码执行工具
- 搜索工具
- 浏览器工具
"""

from __future__ import annotations

import os
from pathlib import Path

from ...utils.exceptions import ToolException
from ...utils.logging import get_logger
from .registry import BaseTool, ToolParameter

logger = get_logger(__name__)


class FileReadTool(BaseTool):
    """文件读取工具"""

    name = "file_read"
    description = "Read the contents of a file. Supports both `limit` and the more intuitive `max_lines` alias."
    category = "file"
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file to read",
            required=True,
        ),
        ToolParameter(
            name="offset",
            type="integer",
            description="Line number to start reading from (1-indexed)",
            required=False,
            default=1,
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of lines to read (alias: max_lines). Default 100.",
            required=False,
            default=100,
        ),
        ToolParameter(
            name="max_lines",
            type="integer",
            description="(Alias for `limit`) Maximum number of lines to read. Default 100.",
            required=False,
            default=100,
        ),
    ]

    async def execute(
        self,
        path: str,
        offset: int = 1,
        limit: int = 100,
        max_lines: int | None = None,
    ) -> dict:
        # P0-4: max_lines 是 limit 的语义化别名,优先使用
        if max_lines is not None:
            limit = int(max_lines)
        elif limit is not None:
            limit = int(limit)
        else:
            limit = 100
        try:
            file_path = Path(path)

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            if not file_path.is_file():
                raise ValueError(f"Path is not a file: {path}")

            with open(file_path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            start = max(0, offset - 1)
            end = min(len(lines), start + limit)
            selected_lines = lines[start:end]

            return {
                "path": str(file_path.absolute()),
                "content": "".join(selected_lines),
                "total_lines": len(lines),
                "read_lines": len(selected_lines),
                "offset": offset,
                "limit": limit,
                "truncated": end < len(lines),
            }
        except ToolException:
            raise
        except FileNotFoundError as e:
            raise ToolException(f"文件不存在: {e}")
        except ValueError as e:
            raise ToolException(f"参数错误: {e}")
        except Exception as e:
            raise ToolException(f"工具执行失败: {e}")


class FileWriteTool(BaseTool):
    """文件写入工具"""

    name = "file_write"
    description = "Write content to a file"
    category = "file"
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file to write",
            required=True,
        ),
        ToolParameter(
            name="content",
            type="string",
            description="Content to write",
            required=True,
        ),
        ToolParameter(
            name="append",
            type="boolean",
            description="Append to file instead of overwriting",
            required=False,
            default=False,
        ),
    ]

    async def execute(self, path: str, content: str, append: bool = False) -> dict:
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            return {
                "path": str(file_path.absolute()),
                "bytes_written": len(content.encode("utf-8")),
                "operation": "append" if append else "write",
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"工具执行失败: {e}")


class StrReplaceEditorTool(BaseTool):
    """字符串替换编辑器工具"""

    name = "str_replace_editor"
    description = "Replace a string in a file with another string"
    category = "file"
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to the file",
            required=True,
        ),
        ToolParameter(
            name="old_string",
            type="string",
            description="String to replace",
            required=True,
        ),
        ToolParameter(
            name="new_string",
            type="string",
            description="Replacement string",
            required=True,
        ),
    ]

    async def execute(self, path: str, old_string: str, new_string: str) -> dict:
        try:
            file_path = Path(path)

            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {path}")

            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if old_string not in content:
                raise ValueError(f"String not found in file: {old_string[:50]}...")

            new_content = content.replace(old_string, new_string, 1)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {
                "path": str(file_path.absolute()),
                "replacements": 1,
                "old_length": len(old_string),
                "new_length": len(new_string),
            }
        except ToolException:
            raise
        except FileNotFoundError as e:
            raise ToolException(f"文件不存在: {e}")
        except ValueError as e:
            raise ToolException(f"参数错误: {e}")
        except Exception as e:
            raise ToolException(f"工具执行失败: {e}")


class PythonExecuteTool(BaseTool):
    """Python 代码执行工具"""

    name = "python_execute"
    description = "Execute Python code and return the result"
    category = "code"
    parameters = [
        ToolParameter(
            name="code",
            type="string",
            description="Python code to execute",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Execution timeout in seconds",
            required=False,
            default=30,
        ),
    ]

    async def execute(self, code: str, timeout: int = 30) -> dict:
        import asyncio
        import tempfile

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_file = f.name

        try:
            try:
                # 执行代码
                proc = await asyncio.create_subprocess_exec(
                    "python",
                    temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    raise TimeoutError(f"Code execution timed out after {timeout}s")

                return {
                    "stdout": stdout.decode("utf-8", errors="ignore"),
                    "stderr": stderr.decode("utf-8", errors="ignore"),
                    "returncode": proc.returncode,
                    "success": proc.returncode == 0,
                }
            except ToolException:
                raise
            except Exception as e:
                raise ToolException(f"工具执行失败: {e}")
        finally:
            os.unlink(temp_file)


class BashTool(BaseTool):
    """Bash 命令执行工具"""

    name = "bash"
    description = "Execute bash commands"
    category = "code"
    parameters = [
        ToolParameter(
            name="command",
            type="string",
            description="Bash command to execute",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            type="integer",
            description="Execution timeout in seconds",
            required=False,
            default=30,
        ),
        ToolParameter(
            name="working_dir",
            type="string",
            description="Working directory for command execution",
            required=False,
        ),
    ]

    async def execute(
        self,
        command: str,
        timeout: int = 30,
        working_dir: str | None = None,
    ) -> dict:
        try:
            import asyncio

            cwd = Path(working_dir) if working_dir else None

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                raise TimeoutError(f"Command timed out after {timeout}s")

            return {
                "stdout": stdout.decode("utf-8", errors="ignore"),
                "stderr": stderr.decode("utf-8", errors="ignore"),
                "returncode": proc.returncode,
                "success": proc.returncode == 0,
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"工具执行失败: {e}")


class WebSearchTool(BaseTool):
    """网页搜索工具 - 支持多搜索引擎"""

    name = "web_search"
    description = "Search the web for information using multiple search engines"
    category = "search"
    parameters = [
        ToolParameter(
            name="query",
            type="string",
            description="Search query",
            required=True,
        ),
        ToolParameter(
            name="num_results",
            type="integer",
            description="Number of results to return",
            required=False,
            default=5,
        ),
        ToolParameter(
            name="engine",
            type="string",
            description="Search engine to use (duckduckgo, google, baidu, bing, serpapi)",
            required=False,
            default="duckduckgo",
        ),
    ]

    async def execute(
        self,
        query: str,
        num_results: int = 5,
        engine: str = "duckduckgo",
    ) -> dict:
        try:
            from ..search import get_search_manager

            manager = get_search_manager()

            # 检查引擎是否可用
            available_engines = manager.get_available_engines()
            if engine not in available_engines:
                return {
                    "query": query,
                    "engine": engine,
                    "results": [],
                    "error": f"搜索引擎 '{engine}' 不可用。可用引擎: {', '.join(available_engines)}",
                    "count": 0,
                }

            # 执行搜索
            response = await manager.search(query, engine=engine, num_results=num_results)

            # 转换结果
            results = []
            for r in response.results:
                results.append(
                    {
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "source": r.source,
                        "rank": r.rank,
                    }
                )

            return {
                "query": query,
                "engine": response.engine,
                "results": results,
                "count": len(results),
                "execution_time_ms": response.execution_time_ms,
                "error": response.error,
            }
        except ToolException:
            raise
        except Exception as e:
            raise ToolException(f"工具执行失败: {e}")


class ViewTool(BaseTool):
    """目录/文件查看工具"""

    name = "view"
    description = "View the contents of a directory or file"
    category = "file"
    parameters = [
        ToolParameter(
            name="path",
            type="string",
            description="Path to view",
            required=True,
        ),
        ToolParameter(
            name="view_range",
            type="array",
            description="Line range to view [start, end] for files",
            required=False,
        ),
    ]

    async def execute(
        self,
        path: str,
        view_range: list[int] | None = None,
    ) -> dict:
        try:
            target_path = Path(path)

            if not target_path.exists():
                raise FileNotFoundError(f"Path not found: {path}")

            if target_path.is_dir():
                # 列出目录内容
                items = []
                for item in sorted(target_path.iterdir()):
                    item_type = "directory" if item.is_dir() else "file"
                    items.append(
                        {
                            "name": item.name,
                            "type": item_type,
                            "size": item.stat().st_size if item.is_file() else None,
                        }
                    )

                return {
                    "path": str(target_path.absolute()),
                    "type": "directory",
                    "items": items,
                    "count": len(items),
                }

            else:
                # 读取文件
                with open(target_path, encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()

                if view_range and len(view_range) == 2:
                    start = max(0, view_range[0] - 1)
                    end = min(len(lines), view_range[1])
                    lines = lines[start:end]

                return {
                    "path": str(target_path.absolute()),
                    "type": "file",
                    "content": "".join(lines),
                    "total_lines": len(lines),
                }
        except ToolException:
            raise
        except FileNotFoundError as e:
            raise ToolException(f"文件不存在: {e}")
        except Exception as e:
            raise ToolException(f"工具执行失败: {e}")


def register_builtin_tools() -> None:
    """注册所有内置工具"""
    from .registry import get_tool_registry

    registry = get_tool_registry()

    tools = [
        FileReadTool(),
        FileWriteTool(),
        StrReplaceEditorTool(),
        PythonExecuteTool(),
        BashTool(),
        WebSearchTool(),
        ViewTool(),
    ]

    for tool in tools:
        if hasattr(tool, "to_definition"):
            d = tool.to_definition()
            registry.register(
                name=d.name,
                description=d.description,
                parameters=d.parameters,
                required=d.required,
                function=d.function,
                category=getattr(tool, "category", "uncategorized"),
            )
        else:
            registry.register(
                name=getattr(tool, "name", type(tool).__name__),
                description=getattr(tool, "description", ""),
                parameters=getattr(tool, "parameters", {}),
                function=getattr(tool, "run", None),
            )

    logger.info(f"已注册 {len(tools)} 个内置工具")
