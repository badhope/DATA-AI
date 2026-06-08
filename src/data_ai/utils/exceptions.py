"""
DATA-AI 统一异常体系 - 扩展版

覆盖所有可能的错误场景，每个异常都有明确的错误码和上下文信息
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(Enum):
    """错误码枚举"""

    # 配置错误 1xxx
    CONFIG_ERROR = "1000"
    CONFIG_NOT_FOUND = "1001"
    CONFIG_VALIDATION_ERROR = "1002"
    CONFIG_PARSE_ERROR = "1003"
    CONFIG_ENV_MISSING = "1004"

    # LLM 错误 2xxx
    LLM_ERROR = "2000"
    LLM_CONNECTION_ERROR = "2001"
    LLM_AUTH_ERROR = "2002"
    LLM_RATE_LIMIT = "2003"
    LLM_TIMEOUT = "2004"
    LLM_CONTENT_FILTER = "2005"
    LLM_MODEL_NOT_FOUND = "2006"
    LLM_CONTEXT_LENGTH_EXCEEDED = "2007"
    LLM_INVALID_RESPONSE = "2008"
    LLM_API_DEPRECATED = "2009"

    # Agent 错误 3xxx
    AGENT_ERROR = "3000"
    AGENT_TIMEOUT = "3001"
    AGENT_EXECUTION_ERROR = "3002"
    AGENT_MAX_ITERATIONS = "3003"
    AGENT_INVALID_STATE = "3004"
    AGENT_TOOL_CALL_FAILED = "3005"
    AGENT_CONTEXT_OVERFLOW = "3006"

    # 工具错误 4xxx
    TOOL_ERROR = "4000"
    TOOL_NOT_FOUND = "4001"
    TOOL_EXECUTION_ERROR = "4002"
    TOOL_TIMEOUT = "4003"
    TOOL_PERMISSION_DENIED = "4004"
    TOOL_INVALID_ARGUMENTS = "4005"
    TOOL_OUTPUT_PARSE_ERROR = "4006"

    # 沙箱错误 5xxx
    SANDBOX_ERROR = "5000"
    SANDBOX_INIT_ERROR = "5001"
    SANDBOX_EXECUTION_ERROR = "5002"
    SANDBOX_SECURITY_ERROR = "5003"
    SANDBOX_RESOURCE_EXCEEDED = "5004"
    SANDBOX_NETWORK_ERROR = "5005"
    SANDBOX_IMAGE_NOT_FOUND = "5006"
    SANDBOX_CONTAINER_ERROR = "5007"

    # 记忆错误 6xxx
    MEMORY_ERROR = "6000"
    MEMORY_INIT_ERROR = "6001"
    MEMORY_ACCESS_ERROR = "6002"
    MEMORY_STORAGE_ERROR = "6003"
    MEMORY_CORRUPTION = "6004"
    MEMORY_COMPRESSION_ERROR = "6005"

    # RAG 错误 7xxx
    RAG_ERROR = "7000"
    RAG_INDEX_ERROR = "7001"
    RAG_QUERY_ERROR = "7002"
    RAG_EMBEDDING_ERROR = "7003"
    RAG_DOCUMENT_PARSE_ERROR = "7004"
    RAG_VECTOR_STORE_ERROR = "7005"

    # 插件错误 8xxx
    PLUGIN_ERROR = "8000"
    PLUGIN_LOAD_ERROR = "8001"
    PLUGIN_NOT_FOUND = "8002"
    PLUGIN_INCOMPATIBLE = "8003"
    PLUGIN_HOOK_ERROR = "8004"

    # API 错误 9xxx
    API_ERROR = "9000"
    API_CONNECTION_ERROR = "9001"
    API_RESPONSE_ERROR = "9002"
    API_TIMEOUT = "9003"
    API_AUTHENTICATION_ERROR = "9004"
    API_NOT_FOUND = "9005"
    API_METHOD_NOT_ALLOWED = "9006"
    API_VALIDATION_ERROR = "9007"
    API_RATE_LIMIT = "9008"


class DataAIException(Exception):
    """
    DATA-AI 所有异常的基类

    提供详细的错误信息、错误码、上下文和溯源信息
    """

    CODE = ErrorCode.CONFIG_ERROR

    def __init__(
        self,
        message: str = "",
        *,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
        source_file: str | None = None,
        source_line: int | None = None,
        operation: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = self.CODE
        self.details: dict[str, Any] = details or {}
        self.cause: Exception | None = cause
        self.source_file = source_file
        self.source_line = source_line
        self.operation = operation
        self.timestamp = __import__("time").time()

    def __repr__(self) -> str:
        parts = [
            f"{self.__class__.__name__}",
            f"code={self.code.value}",
        ]
        if self.message:
            parts.append(f"message={self.message!r}")
        if self.operation:
            parts.append(f"operation={self.operation!r}")
        return f"<{' '.join(parts)}>"

    def __str__(self) -> str:
        parts = [f"[{self.code.value}] {self.message}"]
        if self.operation:
            parts.append(f"(operation: {self.operation})")
        if self.source_file:
            location = f"{self.source_file}:{self.source_line}" if self.source_line else self.source_file
            parts.append(f"at {location}")
        return " ".join(parts)

    def with_context(self, **kwargs: Any) -> DataAIException:
        """添加上下文信息"""
        self.details.update(kwargs)
        return self

    def with_cause(self, cause: Exception) -> DataAIException:
        """设置导致原因"""
        self.cause = cause
        return self

    def with_source(self, file: str, line: int | None = None) -> DataAIException:
        """设置源代码位置"""
        self.source_file = file
        self.source_line = line
        return self

    def to_dict(self) -> dict[str, Any]:
        """转换为字典（用于日志和序列化）"""
        return {
            "error_code": self.code.value,
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "operation": self.operation,
            "timestamp": self.timestamp,
            "cause": str(self.cause) if self.cause else None,
        }


# ─── 配置异常 ────────────────────────────────────────────────────────────────


class ConfigException(DataAIException):
    """配置相关异常"""

    CODE = ErrorCode.CONFIG_ERROR


class ConfigNotFoundError(ConfigException):
    """配置文件不存在"""

    CODE = ErrorCode.CONFIG_NOT_FOUND

    def __init__(self, path: str, **kwargs):
        super().__init__(
            f"Configuration file not found: {path}",
            details={"path": path, **kwargs},
        )


class ConfigValidationError(ConfigException):
    """配置验证失败"""

    CODE = ErrorCode.CONFIG_VALIDATION_ERROR

    def __init__(self, message: str, field: str | None = None, **kwargs):
        super().__init__(
            message,
            details={"field": field, **kwargs},
        )


class ConfigParseError(ConfigException):
    """配置解析错误"""

    CODE = ErrorCode.CONFIG_PARSE_ERROR

    def __init__(self, path: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to parse config file {path}: {reason}",
            details={"path": path, "reason": reason, **kwargs},
        )


class ConfigEnvMissingError(ConfigException):
    """环境变量缺失"""

    CODE = ErrorCode.CONFIG_ENV_MISSING

    def __init__(self, env_var: str, **kwargs):
        super().__init__(
            f"Required environment variable not set: {env_var}",
            details={"env_var": env_var, **kwargs},
        )


# ─── LLM 异常 ──────────────────────────────────────────────────────────────


class LLMException(DataAIException):
    """LLM 模型相关异常"""

    CODE = ErrorCode.LLM_ERROR

    def __init__(self, message: str = "", *, model: str | None = None, provider: str | None = None, **kwargs):
        super().__init__(
            message,
            details={"model": model, "provider": provider, **kwargs},
        )


class LLMConnectionError(LLMException):
    """LLM 连接失败"""

    CODE = ErrorCode.LLM_CONNECTION_ERROR

    def __init__(self, message: str, url: str | None = None, **kwargs):
        super().__init__(
            message,
            details={"url": url, **kwargs},
        )


class LLMAuthError(LLMException):
    """LLM 认证失败"""

    CODE = ErrorCode.LLM_AUTH_ERROR

    def __init__(self, message: str = "LLM authentication failed", provider: str | None = None, **kwargs):
        super().__init__(
            message,
            provider=provider,
            details={**kwargs},
        )


class LLMRateLimitError(LLMException):
    """LLM 速率限制"""

    CODE = ErrorCode.LLM_RATE_LIMIT

    def __init__(self, message: str = "LLM rate limit exceeded", retry_after: int | None = None, **kwargs):
        super().__init__(
            message,
            details={"retry_after": retry_after, **kwargs},
        )


class LLMTimeoutError(LLMException):
    """LLM 请求超时"""

    CODE = ErrorCode.LLM_TIMEOUT

    def __init__(self, timeout: float, **kwargs):
        super().__init__(
            f"LLM request timed out after {timeout}s",
            details={"timeout": timeout, **kwargs},
        )


class LLMContentFilterError(LLMException):
    """内容被过滤"""

    CODE = ErrorCode.LLM_CONTENT_FILTER

    def __init__(self, reason: str = "Content filtered by safety system", **kwargs):
        super().__init__(
            f"Content blocked: {reason}",
            details={"reason": reason, **kwargs},
        )


class LLMModelNotFoundError(LLMException):
    """模型不存在"""

    CODE = ErrorCode.LLM_MODEL_NOT_FOUND

    def __init__(self, model: str, provider: str | None = None, **kwargs):
        super().__init__(
            f"Model '{model}' not found" + (f" on {provider}" if provider else ""),
            model=model,
            provider=provider,
            details={**kwargs},
        )


class LLMContextLengthExceededError(LLMException):
    """上下文长度超限"""

    CODE = ErrorCode.LLM_CONTEXT_LENGTH_EXCEEDED

    def __init__(self, current: int, max_length: int, **kwargs):
        super().__init__(
            f"Context length {current} exceeds maximum {max_length}",
            details={"current": current, "max_length": max_length, **kwargs},
        )


class LLMInvalidResponseError(LLMException):
    """无效响应"""

    CODE = ErrorCode.LLM_INVALID_RESPONSE

    def __init__(self, reason: str, raw_response: str | None = None, **kwargs):
        super().__init__(
            f"Invalid LLM response: {reason}",
            details={"raw_response": raw_response, **kwargs},
        )


class LLMConfigError(LLMException):
    """LLM 配置错误"""

    CODE = ErrorCode.LLM_ERROR

    def __init__(self, message: str = "LLM configuration error", **kwargs):
        super().__init__(
            message,
            details={**kwargs},
        )


# ─── Agent 异常 ─────────────────────────────────────────────────────────────


class AgentConfigException(DataAIException):
    """Agent 配置相关异常"""

    CODE = ErrorCode.CONFIG_ERROR

    def __init__(self, message: str = "", **kwargs):
        super().__init__(message, details={**kwargs})


class AgentException(DataAIException):
    """Agent 执行相关异常"""

    CODE = ErrorCode.AGENT_ERROR

    def __init__(self, message: str = "", *, agent: str | None = None, **kwargs):
        super().__init__(
            message,
            details={"agent": agent, **kwargs},
        )


class AgentTimeoutError(AgentException):
    """Agent 执行超时"""

    CODE = ErrorCode.AGENT_TIMEOUT

    def __init__(self, agent: str, timeout: float, **kwargs):
        super().__init__(
            f"Agent '{agent}' execution timed out after {timeout}s",
            agent=agent,
            details={"timeout": timeout, **kwargs},
        )


class AgentExecutionError(AgentException):
    """Agent 执行错误"""

    CODE = ErrorCode.AGENT_EXECUTION_ERROR

    def __init__(self, agent: str, message: str, step: int | None = None, **kwargs):
        super().__init__(
            message,
            agent=agent,
            details={"step": step, **kwargs},
        )


class AgentMaxIterationsError(AgentException):
    """达到最大迭代次数"""

    CODE = ErrorCode.AGENT_MAX_ITERATIONS

    def __init__(self, agent: str, max_iterations: int, **kwargs):
        super().__init__(
            f"Agent '{agent}' reached maximum iterations ({max_iterations})",
            agent=agent,
            details={"max_iterations": max_iterations, **kwargs},
        )


class AgentToolCallFailedError(AgentException):
    """工具调用失败"""

    CODE = ErrorCode.AGENT_TOOL_CALL_FAILED

    def __init__(self, agent: str, tool: str, reason: str, **kwargs):
        super().__init__(
            f"Agent '{agent}' failed to call tool '{tool}': {reason}",
            agent=agent,
            details={"tool": tool, "reason": reason, **kwargs},
        )


class AgentContextOverflowError(AgentException):
    """Agent 上下文溢出"""

    CODE = ErrorCode.AGENT_CONTEXT_OVERFLOW

    def __init__(self, agent: str, current_tokens: int, max_tokens: int, **kwargs):
        super().__init__(
            f"Agent '{agent}' context overflow: {current_tokens}/{max_tokens} tokens",
            agent=agent,
            details={"current_tokens": current_tokens, "max_tokens": max_tokens, **kwargs},
        )


# ─── 工具异常 ───────────────────────────────────────────────────────────────


class ToolException(DataAIException):
    """工具执行相关异常"""

    CODE = ErrorCode.TOOL_ERROR

    def __init__(self, message: str = "", *, tool: str | None = None, **kwargs):
        super().__init__(
            message,
            details={"tool": tool, **kwargs},
        )


class ToolNotFoundError(ToolException):
    """工具不存在"""

    CODE = ErrorCode.TOOL_NOT_FOUND

    def __init__(self, tool: str, available: list | None = None, **kwargs):
        super().__init__(
            f"Tool not found: {tool}",
            tool=tool,
            details={"available_tools": available, **kwargs},
        )


class ToolExecutionError(ToolException):
    """工具执行错误"""

    CODE = ErrorCode.TOOL_EXECUTION_ERROR

    def __init__(self, tool: str, message: str, exit_code: int | None = None, **kwargs):
        super().__init__(
            message,
            tool=tool,
            details={"exit_code": exit_code, **kwargs},
        )


class ToolTimeoutError(ToolException):
    """工具执行超时"""

    CODE = ErrorCode.TOOL_TIMEOUT

    def __init__(self, tool: str, timeout: float, **kwargs):
        super().__init__(
            f"Tool '{tool}' execution timed out after {timeout}s",
            tool=tool,
            details={"timeout": timeout, **kwargs},
        )


class ToolPermissionDeniedError(ToolException):
    """工具权限不足"""

    CODE = ErrorCode.TOOL_PERMISSION_DENIED

    def __init__(self, tool: str, required: str, **kwargs):
        super().__init__(
            f"Permission denied for tool '{tool}': requires {required}",
            tool=tool,
            details={"required_permission": required, **kwargs},
        )


class ToolInvalidArgumentsError(ToolException):
    """工具参数无效"""

    CODE = ErrorCode.TOOL_INVALID_ARGUMENTS

    def __init__(self, tool: str, param: str, reason: str, **kwargs):
        super().__init__(
            f"Invalid arguments for tool '{tool}': {param} - {reason}",
            tool=tool,
            details={"param": param, "reason": reason, **kwargs},
        )


class ToolOutputParseError(ToolException):
    """工具输出解析错误"""

    CODE = ErrorCode.TOOL_OUTPUT_PARSE_ERROR

    def __init__(self, tool: str, output: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to parse output from tool '{tool}': {reason}",
            tool=tool,
            details={"output_preview": output[:200], "reason": reason, **kwargs},
        )


# ─── P1-4: Tool Retry ───────────────────────────────────────────────


class ToolRetryableError(ToolExecutionError):
    """P1-4: 可重试的工具执行错误 (transient, 如 timeout / 5xx / network).

    跟 ToolExecutionError 区别:
    - ToolExecutionError 是兜底(permanet)
    - ToolRetryableError 表示下次重试大概率会成功
    """

    retryable: bool = True

    def __init__(self, tool: str, message: str, **kwargs):
        super().__init__(tool, message, **kwargs)
        self.details.setdefault("retryable", True)


class ToolPermanentError(ToolExecutionError):
    """P1-4: 永久错误(参数错 / 权限不够 / 资源不存在),重试无意义.

    execute_with_retry 看到 ToolPermanentError 立即抛出,不再重试。
    """

    retryable: bool = False

    def __init__(self, tool: str, message: str, **kwargs):
        super().__init__(tool, message, **kwargs)
        self.details.setdefault("retryable", False)


# ─── 搜索异常 ───────────────────────────────────────────────────────────────


class SearchException(DataAIException):
    """搜索相关异常"""

    CODE = ErrorCode.TOOL_ERROR

    def __init__(self, message: str = "", *, engine: str | None = None, query: str | None = None, **kwargs):
        super().__init__(
            message,
            details={"engine": engine, "query": query, **kwargs},
        )


class SearchEngineNotFoundError(SearchException):
    """搜索引擎不存在"""

    def __init__(self, engine: str, available: list[str], **kwargs):
        super().__init__(
            f"Search engine '{engine}' not found. Available: {', '.join(available)}",
            engine=engine,
            details={"available": available, **kwargs},
        )


class SearchRateLimitError(SearchException):
    """搜索速率限制"""

    def __init__(self, engine: str, retry_after: int | None = None, **kwargs):
        super().__init__(
            f"Search rate limit exceeded for '{engine}'",
            engine=engine,
            details={"retry_after": retry_after, **kwargs},
        )


# ─── 会话异常 ───────────────────────────────────────────────────────────────


class SessionException(DataAIException):
    """会话相关异常"""

    CODE = ErrorCode.CONFIG_ERROR

    def __init__(self, message: str = "", *, session_id: str | None = None, **kwargs):
        super().__init__(
            message,
            details={"session_id": session_id, **kwargs},
        )


class SessionNotFoundError(SessionException):
    """会话不存在"""

    def __init__(self, session_id: str, **kwargs):
        super().__init__(
            f"Session not found: {session_id}",
            session_id=session_id,
            **kwargs,
        )


# ─── 沙箱异常 ───────────────────────────────────────────────────────────────


class SandboxException(DataAIException):
    """沙箱执行相关异常"""

    CODE = ErrorCode.SANDBOX_ERROR


class SandboxInitError(SandboxException):
    """沙箱初始化失败"""

    CODE = ErrorCode.SANDBOX_INIT_ERROR

    def __init__(self, sandbox_type: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to initialize {sandbox_type} sandbox: {reason}",
            details={"sandbox_type": sandbox_type, "reason": reason, **kwargs},
        )


class SandboxExecutionError(SandboxException):
    """沙箱代码执行错误"""

    CODE = ErrorCode.SANDBOX_EXECUTION_ERROR

    def __init__(self, message: str, language: str | None = None, exit_code: int | None = None, **kwargs):
        super().__init__(
            message,
            details={"language": language, "exit_code": exit_code, **kwargs},
        )


class SandboxTimeoutError(SandboxException):
    """沙箱执行超时"""

    CODE = ErrorCode.SANDBOX_EXECUTION_ERROR

    def __init__(self, message: str = "Sandbox execution timed out", timeout: int | None = None, **kwargs):
        super().__init__(
            message,
            details={"timeout": timeout, **kwargs},
        )


class SandboxResourceLimitError(SandboxException):
    """沙箱资源限制"""

    CODE = ErrorCode.SANDBOX_RESOURCE_EXCEEDED

    def __init__(self, message: str = "Sandbox resource limit exceeded", **kwargs):
        super().__init__(message, **kwargs)


class SandboxSecurityError(SandboxException):
    """沙箱安全违规"""

    CODE = ErrorCode.SANDBOX_SECURITY_ERROR

    def __init__(self, violation_type: str, details: str, **kwargs):
        super().__init__(
            f"Security violation: {violation_type} - {details}",
            details={"violation_type": violation_type, "violation_details": details, **kwargs},
        )


class SandboxResourceExceededError(SandboxException):
    """沙箱资源超限"""

    CODE = ErrorCode.SANDBOX_RESOURCE_EXCEEDED

    def __init__(self, resource: str, limit: str, used: str, **kwargs):
        super().__init__(
            f"Resource limit exceeded: {resource} (used {used}, limit {limit})",
            details={"resource": resource, "limit": limit, "used": used, **kwargs},
        )


class SandboxNetworkError(SandboxException):
    """沙箱网络错误"""

    CODE = ErrorCode.SANDBOX_NETWORK_ERROR

    def __init__(self, url: str, reason: str, **kwargs):
        super().__init__(
            f"Sandbox network error accessing {url}: {reason}",
            details={"url": url, "reason": reason, **kwargs},
        )


class SandboxImageNotFoundError(SandboxException):
    """Docker 镜像不存在"""

    CODE = ErrorCode.SANDBOX_IMAGE_NOT_FOUND

    def __init__(self, image: str, **kwargs):
        super().__init__(
            f"Docker image not found: {image}",
            details={"image": image, **kwargs},
        )


# ─── 记忆异常 ───────────────────────────────────────────────────────────────


class MemoryException(DataAIException):
    """记忆系统相关异常"""

    CODE = ErrorCode.MEMORY_ERROR


class MemoryInitError(MemoryException):
    """记忆系统初始化失败"""

    CODE = ErrorCode.MEMORY_INIT_ERROR

    def __init__(self, reason: str, **kwargs):
        super().__init__(
            f"Failed to initialize memory system: {reason}",
            details={"reason": reason, **kwargs},
        )


class MemoryAccessError(MemoryException):
    """记忆访问错误"""

    CODE = ErrorCode.MEMORY_ACCESS_ERROR

    def __init__(self, session_id: str, reason: str, **kwargs):
        super().__init__(
            f"Memory access error for session '{session_id}': {reason}",
            details={"session_id": session_id, "reason": reason, **kwargs},
        )


class MemoryStorageError(MemoryException):
    """记忆存储错误"""

    CODE = ErrorCode.MEMORY_STORAGE_ERROR

    def __init__(self, path: str, operation: str, reason: str, **kwargs):
        super().__init__(
            f"Memory storage error ({operation}) at {path}: {reason}",
            details={"path": path, "operation": operation, "reason": reason, **kwargs},
        )


class MemoryCorruptionError(MemoryException):
    """记忆数据损坏"""

    CODE = ErrorCode.MEMORY_CORRUPTION

    def __init__(self, session_id: str, details: str, **kwargs):
        super().__init__(
            f"Memory corruption detected in session '{session_id}': {details}",
            details={"session_id": session_id, "corruption_details": details, **kwargs},
        )


class MemoryCompressionError(MemoryException):
    """记忆压缩错误"""

    CODE = ErrorCode.MEMORY_COMPRESSION_ERROR

    def __init__(self, strategy: str, reason: str, **kwargs):
        super().__init__(
            f"Memory compression failed ({strategy}): {reason}",
            details={"strategy": strategy, "reason": reason, **kwargs},
        )


# ─── RAG 异常 ───────────────────────────────────────────────────────────────


class RAGException(DataAIException):
    """RAG 系统相关异常"""

    CODE = ErrorCode.RAG_ERROR


class RAGIndexError(RAGException):
    """RAG 索引错误"""

    CODE = ErrorCode.RAG_INDEX_ERROR

    def __init__(self, document_id: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to index document '{document_id}': {reason}",
            details={"document_id": document_id, "reason": reason, **kwargs},
        )


class RAGQueryError(RAGException):
    """RAG 查询错误"""

    CODE = ErrorCode.RAG_QUERY_ERROR

    def __init__(self, query: str, reason: str, **kwargs):
        super().__init__(
            f"RAG query failed for '{query[:50]}...': {reason}",
            details={"query": query, "reason": reason, **kwargs},
        )


class RAGEmbeddingError(RAGException):
    """嵌入生成错误"""

    CODE = ErrorCode.RAG_EMBEDDING_ERROR

    def __init__(self, text: str, model: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to generate embedding with {model}: {reason}",
            details={"text_preview": text[:100], "model": model, "reason": reason, **kwargs},
        )


class RAGDocumentParseError(RAGException):
    """文档解析错误"""

    CODE = ErrorCode.RAG_DOCUMENT_PARSE_ERROR

    def __init__(self, path: str, format: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to parse {format} document '{path}': {reason}",
            details={"path": path, "format": format, "reason": reason, **kwargs},
        )


class RAGVectorStoreError(RAGException):
    """向量存储错误"""

    CODE = ErrorCode.RAG_VECTOR_STORE_ERROR

    def __init__(self, store_type: str, operation: str, reason: str, **kwargs):
        super().__init__(
            f"Vector store error ({store_type}/{operation}): {reason}",
            details={"store_type": store_type, "operation": operation, "reason": reason, **kwargs},
        )


# ─── 插件异常 ───────────────────────────────────────────────────────────────


class PluginException(DataAIException):
    """插件系统相关异常"""

    CODE = ErrorCode.PLUGIN_ERROR


class PluginLoadError(PluginException):
    """插件加载失败"""

    CODE = ErrorCode.PLUGIN_LOAD_ERROR

    def __init__(self, plugin: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to load plugin '{plugin}': {reason}",
            details={"plugin": plugin, "reason": reason, **kwargs},
        )


class PluginNotFoundError(PluginException):
    """插件不存在"""

    CODE = ErrorCode.PLUGIN_NOT_FOUND

    def __init__(self, plugin: str, search_paths: list | None = None, **kwargs):
        super().__init__(
            f"Plugin not found: {plugin}",
            details={"plugin": plugin, "search_paths": search_paths, **kwargs},
        )


class PluginIncompatibleError(PluginException):
    """插件不兼容"""

    CODE = ErrorCode.PLUGIN_INCOMPATIBLE

    def __init__(self, plugin: str, required: str, current: str, **kwargs):
        super().__init__(
            f"Plugin '{plugin}' incompatible: requires {required}, current {current}",
            details={"plugin": plugin, "required_version": required, "current_version": current, **kwargs},
        )


class PluginHookError(PluginException):
    """插件钩子错误"""

    CODE = ErrorCode.PLUGIN_HOOK_ERROR

    def __init__(self, plugin: str, hook: str, reason: str, **kwargs):
        super().__init__(
            f"Plugin '{plugin}' hook '{hook}' error: {reason}",
            details={"plugin": plugin, "hook": hook, "reason": reason, **kwargs},
        )


# ─── API 异常 ────────────────────────────────────────────────────────────────


class APIException(DataAIException):
    """API 接口相关异常"""

    CODE = ErrorCode.API_ERROR

    def __init__(self, message: str = "", *, status_code: int | None = None, **kwargs):
        super().__init__(
            message,
            details={"status_code": status_code, **kwargs},
        )


class APIConnectionError(APIException):
    """API 连接错误"""

    CODE = ErrorCode.API_CONNECTION_ERROR

    def __init__(self, url: str, reason: str, **kwargs):
        super().__init__(
            f"Failed to connect to {url}: {reason}",
            details={"url": url, "reason": reason, **kwargs},
        )


class APIResponseError(APIException):
    """API 响应错误"""

    CODE = ErrorCode.API_RESPONSE_ERROR

    def __init__(self, status_code: int, message: str, response_body: str | None = None, **kwargs):
        super().__init__(
            f"API error {status_code}: {message}",
            status_code=status_code,
            details={"response_body": response_body, **kwargs},
        )


class APITimeoutError(APIException):
    """API 超时"""

    CODE = ErrorCode.API_TIMEOUT

    def __init__(self, url: str, timeout: float, **kwargs):
        super().__init__(
            f"API request to {url} timed out after {timeout}s",
            details={"url": url, "timeout": timeout, **kwargs},
        )


class APIAuthenticationError(APIException):
    """API 认证错误"""

    CODE = ErrorCode.API_AUTHENTICATION_ERROR

    def __init__(self, url: str, reason: str = "Invalid credentials", **kwargs):
        super().__init__(
            f"API authentication failed for {url}: {reason}",
            details={"url": url, "reason": reason, **kwargs},
        )


class APINotFoundError(APIException):
    """API 端点不存在"""

    CODE = ErrorCode.API_NOT_FOUND

    def __init__(self, path: str, method: str | None = None, **kwargs):
        super().__init__(
            f"API endpoint not found: {method + ' ' if method else ''}{path}",
            status_code=404,
            details={"path": path, "method": method, **kwargs},
        )


class APIMethodNotAllowedError(APIException):
    """API 方法不允许"""

    CODE = ErrorCode.API_METHOD_NOT_ALLOWED

    def __init__(self, path: str, method: str, allowed: list, **kwargs):
        super().__init__(
            f"Method {method} not allowed for {path}",
            status_code=405,
            details={"path": path, "method": method, "allowed_methods": allowed, **kwargs},
        )


class APIValidationError(APIException):
    """API 请求验证错误"""

    CODE = ErrorCode.API_VALIDATION_ERROR

    def __init__(self, field: str, reason: str, **kwargs):
        super().__init__(
            f"Request validation failed: {field} - {reason}",
            status_code=422,
            details={"field": field, "reason": reason, **kwargs},
        )


class APIRateLimitError(APIException):
    """API 速率限制"""

    CODE = ErrorCode.API_RATE_LIMIT

    def __init__(self, limit: int, window: str, retry_after: int | None = None, **kwargs):
        super().__init__(
            f"API rate limit exceeded: {limit} requests per {window}",
            status_code=429,
            details={"limit": limit, "window": window, "retry_after": retry_after, **kwargs},
        )


# 便捷函数：验证 API 密钥
def validate_api_key(api_key: str | None, provider: str) -> str:
    """验证 API 密钥是否已配置"""
    if not api_key or str(api_key).startswith("YOUR_") or api_key == "sk-xxx":
        raise ConfigValidationError(
            f"{provider} API key not configured. "
            f"Please set DATA_AI_API_KEY environment variable "
            f"or configure in config.toml.",
            field="llm.api_key",
        )
    return api_key


# ─── 兼容性别名 (v2.0) ──────────────────────────────────────────────────────

AgentConfigError = AgentConfigException
AgentMaxIterationsExceededError = AgentMaxIterationsError
MemoryConfigError = MemoryInitError
ReasoningException = AgentException


class RAGConfigError(RAGException):
    """RAG 配置异常（兼容性别名）"""

    CODE = ErrorCode.CONFIG_ERROR

    def __init__(self, message: str = "", **kwargs):
        super().__init__(message, **kwargs)
