"""
DATA-AI Utils - 工具函数模块

提供配置、日志、异常等基础设施
"""

from data_ai.utils.config import (
    LLMConfig,
    MemoryConfig,
    SandboxConfig,
    SearchConfig,
    Settings,
    VectorConfig,
    VisionConfig,
    get_settings,
    reload_settings,
)
from data_ai.utils.exceptions import (
    AgentContextOverflowError,
    # Agent 异常
    AgentException,
    AgentExecutionError,
    AgentMaxIterationsError,
    AgentTimeoutError,
    AgentToolCallFailedError,
    APIAuthenticationError,
    APIConnectionError,
    # API 异常
    APIException,
    APIMethodNotAllowedError,
    APINotFoundError,
    APIRateLimitError,
    APIResponseError,
    APITimeoutError,
    APIValidationError,
    ConfigEnvMissingError,
    # 配置异常
    ConfigException,
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    # 基础异常
    DataAIException,
    # 错误码
    ErrorCode,
    LLMAuthError,
    LLMConfigError,
    LLMConnectionError,
    LLMContentFilterError,
    LLMContextLengthExceededError,
    # LLM 异常
    LLMException,
    LLMInvalidResponseError,
    LLMModelNotFoundError,
    LLMRateLimitError,
    LLMTimeoutError,
    MemoryAccessError,
    MemoryCompressionError,
    MemoryCorruptionError,
    # 记忆异常
    MemoryException,
    MemoryInitError,
    MemoryStorageError,
    # 插件异常
    PluginException,
    PluginHookError,
    PluginIncompatibleError,
    PluginLoadError,
    PluginNotFoundError,
    RAGDocumentParseError,
    RAGEmbeddingError,
    # RAG 异常
    RAGException,
    RAGIndexError,
    RAGQueryError,
    RAGVectorStoreError,
    # 沙箱异常
    SandboxException,
    SandboxExecutionError,
    SandboxImageNotFoundError,
    SandboxInitError,
    SandboxNetworkError,
    SandboxResourceExceededError,
    SandboxResourceLimitError,
    SandboxSecurityError,
    SandboxTimeoutError,
    SearchEngineNotFoundError,
    # 搜索异常
    SearchException,
    SearchRateLimitError,
    # 会话异常
    SessionException,
    SessionNotFoundError,
    # 工具异常
    ToolException,
    ToolExecutionError,
    ToolInvalidArgumentsError,
    ToolNotFoundError,
    ToolOutputParseError,
    ToolPermissionDeniedError,
    ToolTimeoutError,
    # 工具函数
    validate_api_key,
)
from data_ai.utils.logging import (
    bind_context,
    clear_context,
    configure_logging,
    default_logger,
    get_logger,
    set_log_level,
)

__all__ = [
    # 错误码
    "ErrorCode",
    # 基础异常
    "DataAIException",
    # 配置异常
    "ConfigException",
    "ConfigNotFoundError",
    "ConfigValidationError",
    "ConfigParseError",
    "ConfigEnvMissingError",
    # LLM 异常
    "LLMException",
    "LLMConnectionError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMContentFilterError",
    "LLMModelNotFoundError",
    "LLMContextLengthExceededError",
    "LLMInvalidResponseError",
    "LLMConfigError",
    # Agent 异常
    "AgentException",
    "AgentTimeoutError",
    "AgentExecutionError",
    "AgentMaxIterationsError",
    "AgentToolCallFailedError",
    "AgentContextOverflowError",
    # 工具异常
    "ToolException",
    "ToolNotFoundError",
    "ToolExecutionError",
    "ToolTimeoutError",
    "ToolPermissionDeniedError",
    "ToolInvalidArgumentsError",
    "ToolOutputParseError",
    # 搜索异常
    "SearchException",
    "SearchEngineNotFoundError",
    "SearchRateLimitError",
    # 会话异常
    "SessionException",
    "SessionNotFoundError",
    # 沙箱异常
    "SandboxException",
    "SandboxInitError",
    "SandboxExecutionError",
    "SandboxTimeoutError",
    "SandboxResourceLimitError",
    "SandboxSecurityError",
    "SandboxResourceExceededError",
    "SandboxNetworkError",
    "SandboxImageNotFoundError",
    # 记忆异常
    "MemoryException",
    "MemoryInitError",
    "MemoryAccessError",
    "MemoryStorageError",
    "MemoryCorruptionError",
    "MemoryCompressionError",
    # RAG 异常
    "RAGException",
    "RAGIndexError",
    "RAGQueryError",
    "RAGEmbeddingError",
    "RAGDocumentParseError",
    "RAGVectorStoreError",
    # 插件异常
    "PluginException",
    "PluginLoadError",
    "PluginNotFoundError",
    "PluginIncompatibleError",
    "PluginHookError",
    # API 异常
    "APIException",
    "APIConnectionError",
    "APIResponseError",
    "APITimeoutError",
    "APIAuthenticationError",
    "APINotFoundError",
    "APIMethodNotAllowedError",
    "APIValidationError",
    "APIRateLimitError",
    # 日志
    "configure_logging",
    "get_logger",
    "bind_context",
    "clear_context",
    "set_log_level",
    "default_logger",
    # 配置
    "Settings",
    "LLMConfig",
    "VisionConfig",
    "SearchConfig",
    "SandboxConfig",
    "MemoryConfig",
    "VectorConfig",
    "get_settings",
    "reload_settings",
    "validate_api_key",
]
