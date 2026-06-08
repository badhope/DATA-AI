"""
DATA-AI 工具注册表

管理工具定义、注册和执行。支持 OpenAI 格式的 tool schema。
"""

from __future__ import annotations

import asyncio
import inspect
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ...utils.exceptions import ToolExecutionError, ToolPermanentError, ToolRetryableError
from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    required: list[str] = field(default_factory=list)
    function: Callable | None = None
    is_async: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


@dataclass
class ToolParameter:
    """工具参数定义"""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[Any] | None = None


@dataclass
class ToolResult:
    """工具执行结果"""

    success: bool
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_string(self) -> str:
        if not self.success:
            return f"Error: {self.error or 'unknown error'}"
        if isinstance(self.result, str):
            return self.result
        try:
            import json

            return json.dumps(self.result, ensure_ascii=False, indent=2)
        except Exception:
            return str(self.result)


class BaseTool:
    """工具基类，子类需实现 name/description/parameters 与 run()"""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict) if False else {}  # type: ignore[assignment]
    category: str = "uncategorized"

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_definition(self) -> ToolDefinition:
        # 决定实际执行的函数：优先 run()，否则 execute()（兼容旧 API）
        # 排除 BaseTool 默认的 raise NotImplementedError
        run_fn = getattr(self, "run", None)
        if run_fn is None or getattr(run_fn, "__isabstractmethod__", False):
            run_fn = None
        else:
            # 绑定方法的 __func__ 是被包装的函数；BaseTool.run.__func__ == BaseTool.run
            underlying = getattr(run_fn, "__func__", run_fn)
            if underlying is BaseTool.run:
                run_fn = None
        exec_fn = getattr(self, "execute", None)
        fn = run_fn if run_fn is not None else exec_fn
        # parameters 可能是 dict 或是 ToolParameter 列表
        raw_params = self.parameters or {}
        if isinstance(raw_params, dict):
            params_dict: dict[str, Any] = raw_params
            required: list[str] = list(raw_params.get("required", []))
        else:
            params_dict = {}
            required = []
            for p in raw_params:
                params_dict[p.name] = {
                    "type": p.type,
                    "description": p.description,
                }
                if p.enum is not None:
                    params_dict[p.name]["enum"] = p.enum
                if p.default is not None:
                    params_dict[p.name]["default"] = p.default
                if p.required:
                    required.append(p.name)
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=params_dict,
            required=required,
            function=fn,
            is_async=inspect.iscoroutinefunction(fn) if fn else False,
            metadata={"category": self.category} if self.category else {},
        )

    def run(self, *args, **kwargs) -> Any:  # pragma: no cover - 子类覆盖
        raise NotImplementedError(f"Tool {self.name} must implement run()")


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._execution_count: dict[str, int] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        required: list[str] | None = None,
        function: Callable | None = None,
        **kwargs,
    ) -> None:
        if name in self._tools:
            logger.warning(f"Tool already registered, overwriting: {name}")

        # 兼容把 category 作为单独字段传入
        category = kwargs.pop("category", None)
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or {},
            required=required or [],
            function=function,
            is_async=inspect.iscoroutinefunction(function) if function else False,
            metadata={**kwargs, **({"category": category} if category else {})},
        )
        self._execution_count[name] = 0
        logger.info(f"Tool registered: {name}")

    def register_function(
        self,
        func: Callable,
        name: str | None = None,
        description: str | None = None,
        parameters: dict[str, Any] | None = None,
        required: list[str] | None = None,
    ) -> None:
        tool_name = name or func.__name__

        if parameters is not None:
            params = parameters.get("properties", {})
            req = required or parameters.get("required", [])
        else:
            params = {}
            req = []
            sig = inspect.signature(func)
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue
                param_type = "string"
                if param.annotation is not inspect.Parameter.empty:
                    if param.annotation is int:
                        param_type = "integer"
                    elif param.annotation is float:
                        param_type = "number"
                    elif param.annotation is bool:
                        param_type = "boolean"
                    elif param.annotation is list:
                        param_type = "array"

                params[param_name] = {"type": param_type, "description": f"Parameter: {param_name}"}
                if param.default is inspect.Parameter.empty:
                    req.append(param_name)

        self.register(
            name=tool_name,
            description=description or func.__doc__ or f"Execute {tool_name}",
            parameters=params,
            required=req,
            function=func,
            is_async=inspect.iscoroutinefunction(func),
        )

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        self._execution_count.pop(name, None)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_tool_count(self) -> int:
        return len(self._tools)

    def get_openai_tool_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_openai_tool() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self._tools.get(name)
        if not tool:
            raise ToolExecutionError(
                tool=name,
                message=f"Tool not found: {name}",
            )

        if not tool.function:
            raise ToolExecutionError(
                tool=name,
                message=f"Tool '{name}' has no function implementation",
            )

        try:
            if tool.is_async:
                result = await tool.function(**arguments)
            else:
                result = tool.function(**arguments)

            self._execution_count[name] = self._execution_count.get(name, 0) + 1
            return result

        except Exception as e:
            if isinstance(e, ToolExecutionError):
                raise
            # P1-4: 包成 ToolExecutionError 时保留 cause, 让 execute_with_retry 能识别 transient
            wrapped = ToolExecutionError(
                tool=name,
                message=f"Tool '{name}' execution failed: {e}",
            )
            wrapped.cause = e
            raise wrapped

    def get_execution_stats(self) -> dict[str, int]:
        return dict(self._execution_count)

    # ── P1-4: Tool Retry ─────────────────────────────────────

    # 默认 retry_on: 这些异常都视为 transient,重试大概率会成功
    DEFAULT_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
        ToolRetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        OSError,  # 网络层失败 (ConnectionResetError, BrokenPipeError 等都是 OSError 子类)
    )

    # ToolExecutionError 包过的 transient cause 也算 retryable
    # (因为 ToolRegistry.execute() 会把内部异常包成 ToolExecutionError)
    _WRAPPED_TRANSIENT_CAUSE: tuple[type[BaseException], ...] = (
        ToolRetryableError,
        asyncio.TimeoutError,
        ConnectionError,
        OSError,
    )

    async def execute_with_retry(
        self,
        name: str,
        arguments: dict[str, Any],
        max_retries: int = 3,
        retry_on: tuple[type[BaseException], ...] | None = None,
        permanent_on: tuple[type[BaseException], ...] | None = None,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        jitter: float = 0.3,
    ) -> Any:
        """
        P1-4: 带 retry 的工具执行 — 对 transient 错误自动重试,permanent 错误立即抛。

        设计:
        - 退避: exponential backoff `delay = base_delay * 2^attempt`,封顶 max_delay
        - jitter: ±jitter% 随机抖动,避免 thundering herd(很多并发同时重试)
        - 默认 max_retries=3 次,共 4 次尝试
        - 异常分类:
          - retry_on (默认 ToolRetryableError / TimeoutError / ConnectionError / OSError)
            → 退避后重试
          - permanent_on (默认 ToolPermanentError) → 立即抛
          - 其它 → 立即抛(用户输入参数错,重试无意义)
        - 日志: 每次 retry 都 logger.warning

        Args:
            name: 工具名
            arguments: 工具参数
            max_retries: 最多重试次数(不含首次)
            retry_on: 自定义重试异常类元组
            permanent_on: 自定义永久异常类元组
            base_delay: 初始退避秒
            max_delay: 单次退避上限秒
            jitter: 抖动比例 0.0~1.0

        Returns:
            tool 执行结果
        """
        retry_on = retry_on or self.DEFAULT_RETRY_EXCEPTIONS
        permanent_on = permanent_on or (ToolPermanentError,)

        def _is_retryable(exc: BaseException) -> bool:
            """判断一个异常是否 transient (可重试)。

            - 直接是 retry_on 之一(ToolRetryableError / Timeout / Connection / OSError)
            - ToolExecutionError(被 execute() 包装过)且 cause 是 transient
            """
            # 1) 直接是 transient 类型
            for cls in retry_on:
                if cls is ToolExecutionError:
                    continue  # ToolExecutionError 单独走 cause 判断
                if isinstance(exc, cls):
                    return True
            # 2) ToolExecutionError 且 cause 是 transient
            #    检查 (默认 transient + 自定义 retry_on 里的) cause
            if isinstance(exc, ToolExecutionError) and not isinstance(exc, ToolRetryableError):
                cause = getattr(exc, "cause", None)
                if cause is not None:
                    # 2a) cause 在默认 transient 集合
                    if isinstance(cause, self._WRAPPED_TRANSIENT_CAUSE):
                        return True
                    # 2b) cause 匹配用户自定义 retry_on
                    for cls in retry_on:
                        if isinstance(cause, cls):
                            return True
            return False

        last_exc: BaseException | None = None
        for attempt in range(max_retries + 1):  # 0, 1, ..., max_retries
            try:
                return await self.execute(name, arguments)
            except Exception as exc:
                # 1) permanent: 立即抛
                if isinstance(exc, permanent_on):
                    logger.warning(
                        f"[tool-retry] permanent error, no retry: tool={name} err={exc!r}"
                    )
                    raise
                # 2) retryable: 重试
                if _is_retryable(exc) and attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    if jitter > 0:
                        delay = delay * (1.0 + random.uniform(-jitter, jitter))
                        delay = max(0.0, delay)
                    logger.warning(
                        f"[tool-retry] attempt {attempt + 1}/{max_retries + 1} failed: "
                        f"tool={name} err={exc!r}; sleeping {delay:.2f}s"
                    )
                    last_exc = exc
                    await asyncio.sleep(delay)
                    continue
                # 3) 其它: 立即抛(不重试)
                logger.error(
                    f"[tool-retry] non-retryable error: tool={name} err={exc!r}"
                )
                raise
        # 不该到这里,只是给 type-checker 看
        assert last_exc is not None
        raise last_exc

    def clear(self) -> None:
        self._tools = {}
        self._execution_count = {}

    def register_builtin_tools(self) -> None:
        def get_current_time() -> str:
            from datetime import datetime

            return datetime.now().isoformat()

        self.register(
            name="get_current_time",
            description="Get the current date and time in ISO format",
            parameters={"format": {"type": "string", "description": "Time format (iso or unix)"}},
            function=get_current_time,
        )

        def calculate(expression: str) -> str:
            allowed = set("0123456789+-*/().%^ ")
            if not all(c in allowed for c in expression):
                raise ValueError(f"Expression contains disallowed characters: {expression}")
            result = eval(expression, {"__builtins__": {}}, {"pow": pow, "abs": abs, "round": round})
            return str(result)

        self.register(
            name="calculate",
            description="Evaluate a mathematical expression. Supports: +, -, *, /, %, ^, parentheses",
            parameters={"expression": {"type": "string", "description": "Mathematical expression to evaluate"}},
            required=["expression"],
            function=calculate,
        )

        def read_text_file(path: str) -> str:
            from pathlib import Path

            file_path = Path(path).expanduser().resolve()
            if not file_path.exists():
                return f"File not found: {path}"
            if file_path.stat().st_size > 1_000_000:
                return f"File too large: {file_path.stat().st_size} bytes"
            return file_path.read_text(encoding="utf-8", errors="replace")

        self.register(
            name="read_file",
            description="Read a text file from the filesystem",
            parameters={"path": {"type": "string", "description": "Path to the file"}},
            required=["path"],
            function=read_text_file,
        )

        def write_text_file(path: str, content: str) -> str:
            from pathlib import Path

            file_path = Path(path).expanduser().resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"File written: {path}"

        self.register(
            name="write_file",
            description="Write content to a text file",
            parameters={
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            required=["path", "content"],
            function=write_text_file,
        )

        def list_directory(path: str) -> str:
            from pathlib import Path

            dir_path = Path(path).expanduser().resolve()
            if not dir_path.exists():
                return f"Directory not found: {path}"
            if not dir_path.is_dir():
                return f"Not a directory: {path}"
            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁" if item.is_dir() else "📄"
                items.append(f"{prefix} {item.name}")
            return "\n".join(items[:200])

        self.register(
            name="list_directory",
            description="List files and directories in a path",
            parameters={"path": {"type": "string", "description": "Directory path"}},
            required=["path"],
            function=list_directory,
        )

        logger.info(f"Builtin tools registered: {len(self._tools)}")


_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    return _tool_registry


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, Any] | None = None,
    required: list[str] | None = None,
    function: Callable | None = None,
    **kwargs,
) -> None:
    _tool_registry.register(name, description, parameters, required, function, **kwargs)
