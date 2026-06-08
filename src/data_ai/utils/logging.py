"""
DATA-AI 结构化日志系统 - 增强版

使用 structlog 实现统一日志输出，支持：
- 开发环境：彩色控制台输出
- 生产环境：JSON 格式输出
- 上下文绑定：自动注入 session_id、agent_id 等上下文信息
- 多端输出：控制台 + 文件 + 网络
- 详细溯源：记录源文件、行号、操作上下文
- 异常追踪：完整的异常信息和堆栈
"""

from __future__ import annotations

import inspect
import logging
import sys
import traceback
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Literal

import structlog
from structlog.typing import EventDict, WrappedLogger

# ─── 日志级别映射 ────────────────────────────────────────────────────────────

LOG_LEVEL = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# ─── 调用信息提取 ────────────────────────────────────────────────────────────


def _get_caller_info(skip_frames: int = 2) -> dict[str, Any]:
    """
    获取调用者信息（源文件、行号、函数名）

    Args:
        skip_frames: 跳过的帧数

    Returns:
        包含 source_file, source_line, function_name 的字典
    """
    try:
        frame = inspect.currentframe()
        for _ in range(skip_frames):
            if frame is None:
                break
            frame = frame.f_back

        if frame is not None:
            filename = frame.f_code.co_filename
            # 转换为相对路径
            try:
                rel_path = Path(filename).relative_to(Path.cwd())
                filename = str(rel_path)
            except ValueError:
                pass

            return {
                "source_file": filename,
                "source_line": frame.f_lineno,
                "function_name": frame.f_code.co_name,
            }
    except Exception:
        pass

    return {
        "source_file": "unknown",
        "source_line": 0,
        "function_name": "unknown",
    }


# ─── 处理器工厂 ──────────────────────────────────────────────────────────────


def _add_log_level(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加日志级别到事件字典"""
    if method_name == "warn":
        method_name = "warning"
    event_dict["level"] = method_name.upper()
    return event_dict


def _add_timestamp(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加 ISO 格式时间戳"""
    event_dict["timestamp"] = datetime.now().isoformat(timespec="milliseconds")
    return event_dict


def _add_logger_name_safe(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """安全添加日志记录器名称（兼容 PrintLogger）"""
    logger_name = getattr(logger, "name", None) or getattr(logger, "_logger", None)
    if logger_name:
        name = getattr(logger_name, "name", None)
        if name:
            event_dict["logger"] = name
    return event_dict


def _add_service_name(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加服务名称"""
    event_dict["service"] = "data-ai"
    return event_dict


def _add_caller_info(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加调用者信息（源文件、行号、函数名）"""
    # 如果已经手动设置了这些信息，则不再覆盖
    if "source_file" not in event_dict:
        caller_info = _get_caller_info(skip_frames=4)
        event_dict.update(caller_info)
    return event_dict


def _add_trace_id(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """添加追踪 ID 用于关联日志"""
    import uuid

    if "trace_id" not in event_dict:
        event_dict["trace_id"] = str(uuid.uuid4())[:8]
    return event_dict


def _rename_event_key(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """将 'event' 键重命名为 'message'"""
    event_dict.setdefault("message", event_dict.pop("event", ""))
    return event_dict


def _filter_secrets(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """过滤日志中的敏感信息"""
    import re

    secret_patterns = [
        (re.compile(r"(api[_-]?key['\"]?\s*[:=]\s*)['\"][^'\"]{8,}['\"]", re.I), r"\1'***SECRET***'"),
        (re.compile(r"(password['\"]?\s*[:=]\s*)['\"][^'\"]{4,}['\"]", re.I), r"\1'***SECRET***'"),
        (re.compile(r"(bearer['\"]?\s*[:=]\s*)['\"][^'\"]{8,}['\"]", re.I), r"\1'***SECRET***'"),
        (re.compile(r"(sk-[a-zA-Z0-9]{20,})", re.I), r"sk-***SECRET***"),
        (re.compile(r"(sk-ant-[a-zA-Z0-9]{20,})", re.I), r"sk-ant-***SECRET***"),
        (re.compile(r"(AIzaSy[a-zA-Z0-9_-]{33})", re.I), r"AIzaSy***SECRET***"),
    ]

    if "message" in event_dict:
        msg = str(event_dict["message"])
        for pattern, replacement in secret_patterns:
            msg = pattern.sub(replacement, msg)
        event_dict["message"] = msg

    return event_dict


def _format_exception(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """格式化异常信息"""
    if "exc_info" in event_dict and event_dict["exc_info"]:
        exc_info = event_dict["exc_info"]
        if isinstance(exc_info, bool):
            exc_info = sys.exc_info()

        if exc_info[0] is not None:
            event_dict["exception_type"] = exc_info[0].__name__
            event_dict["exception_message"] = str(exc_info[1])
            event_dict["stack_trace"] = traceback.format_exception(*exc_info)

    return event_dict


class _StdlibWriter:
    """structlog 与标准库 logging 的桥接"""

    def __init__(self, level: int = logging.INFO):
        self._logger = logging.getLogger("data_ai")
        self._logger.setLevel(level)
        self._handler = logging.StreamHandler(sys.stdout)
        self._handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._handler.setFormatter(formatter)
        self._logger.addHandler(self._handler)

    def write(self, message: str) -> None:
        if message.strip():
            self._logger.info(message.rstrip())


# ─── 核心配置函数 ────────────────────────────────────────────────────────────


def configure_logging(
    level: str = "INFO",
    *,
    log_file: str | None = None,
    json_output: bool = False,
    json_indent: int = 2,
    colorize: bool = True,
    include_caller_info: bool = True,
) -> None:
    """
    配置 structlog 日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 可选，输出到文件路径
        json_output: 生产环境使用 JSON 格式
        json_indent: JSON 缩进空格数
        colorize: 开发环境使用彩色输出
        include_caller_info: 是否包含调用者信息（源文件、行号）
    """
    # 确定处理器
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _add_logger_name_safe,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        _add_service_name,
        _add_trace_id,
        _filter_secrets,
    ]

    # 添加调用者信息处理器
    if include_caller_info:
        processors.append(_add_caller_info)

    processors.extend(
        [
            _format_exception,
            _rename_event_key,
        ]
    )

    if json_output:
        processors.append(structlog.processors.JSONRenderer(indent=json_indent))
    elif colorize and sys.stdout.isatty():
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
                level_colors={
                    "DEBUG": "<fg #6C6>",
                    "INFO": "<fg #6AF>",
                    "WARNING": "<fg #FB3>",
                    "ERROR": "<fg #F23>",
                    "CRITICAL": "<fg #F22> <bold>",
                },
            )
        )
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=False,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    # 配置 structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 配置标准库 logging
    numeric_level = LOG_LEVELS.get(level.upper(), logging.INFO)

    # 控制台
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root_logger = logging.getLogger("data_ai")
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)

    # 文件输出
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(file_handler)

    # 第三方库日志控制
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    获取结构化日志记录器

    Args:
        name: 日志记录器名称，通常使用模块名

    Returns:
        配置好的 structlog logger 实例
    """
    return structlog.get_logger(name)


# ─── 上下文绑定 ─────────────────────────────────────────────────────────────


def bind_context(**kwargs: object) -> None:
    """绑定上下文变量到当前线程的日志记录器"""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """清除所有绑定的上下文变量"""
    structlog.contextvars.clear_contextvars()


def set_log_level(level: str) -> None:
    """动态设置日志级别"""
    numeric_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logging.getLogger("data_ai").setLevel(numeric_level)
    for handler in logging.getLogger("data_ai").handlers:
        handler.setLevel(numeric_level)


# ─── 日志装饰器 ─────────────────────────────────────────────────────────────


def log_operation(
    operation_name: str | None = None,
    log_args: bool = False,
    log_result: bool = False,
    log_exception: bool = True,
) -> Callable:
    """
    操作日志装饰器 - 自动记录函数调用信息

    Args:
        operation_name: 操作名称，默认为函数名
        log_args: 是否记录参数
        log_result: 是否记录返回值
        log_exception: 是否记录异常

    Example:
        @log_operation(operation_name="用户登录", log_args=True)
        def login(username: str, password: str) -> bool:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            op_name = operation_name or func.__name__

            # 构建上下文
            context = {
                "operation": op_name,
                "function": func.__name__,
                "module": func.__module__,
            }

            if log_args:
                # 过滤敏感参数
                safe_kwargs = {
                    k: v
                    for k, v in kwargs.items()
                    if not any(s in k.lower() for s in ["password", "secret", "key", "token"])
                }
                context["args_count"] = len(args)
                context["kwargs_keys"] = list(safe_kwargs.keys())

            # 记录开始
            logger.info(f"操作开始: {op_name}", **context)

            try:
                result = func(*args, **kwargs)

                # 记录成功
                success_context = {"status": "success", "duration_ms": 0}
                if log_result:
                    success_context["result_type"] = type(result).__name__

                logger.info(f"操作成功: {op_name}", **{**context, **success_context})
                return result

            except Exception as e:
                # 记录异常
                if log_exception:
                    logger.error(
                        f"操作失败: {op_name}",
                        **{
                            **context,
                            "status": "failed",
                            "error_type": type(e).__name__,
                            "error_message": str(e),
                        },
                        exc_info=True,
                    )
                raise

        return wrapper

    return decorator


# ─── 便捷日志实例 ───────────────────────────────────────────────────────────

# 默认 logger，在模块导入时使用
default_logger = structlog.get_logger("data_ai")
