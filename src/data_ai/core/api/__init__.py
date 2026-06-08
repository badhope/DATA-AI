"""
DATA-AI API 模块

提供标准化的API连接机制和服务端，支持：
- 统一的API客户端基类
- 自动重试和错误处理
- 请求/响应日志记录
- 连接池管理
- 认证管理
- REST API 服务端（FastAPI）
"""

from .auth import APIKeyAuth, AuthProvider, BearerTokenAuth
from .client import APIClient, APIError, APIResponse
from .registry import APIRegistry, get_api_client, register_api

# 服务端相关（可选导入，避免 FastAPI 依赖问题）
try:
    from .server import (
        ChatCompletionRequest,
        ChatCompletionResponse,
        ChatCompletionStreamResponse,
        # Pydantic Models
        ChatMessageModel,
        CompletionRequest,
        CompletionResponse,
        HealthResponse,
        ModelInfo,
        ModelsResponse,
        ToolExecuteRequest,
        ToolExecuteResponse,
        ToolInfo,
        ToolsResponse,
        app,
        create_server,
        run_server,
    )

    SERVER_AVAILABLE = True
except ImportError:
    SERVER_AVAILABLE = False

__all__ = [
    # 客户端
    "APIClient",
    "APIResponse",
    "APIError",
    "AuthProvider",
    "APIKeyAuth",
    "BearerTokenAuth",
    "APIRegistry",
    "register_api",
    "get_api_client",
    # 服务端
    "app",
    "create_server",
    "run_server",
    "SERVER_AVAILABLE",
    # 模型
    "ChatMessageModel",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatCompletionStreamResponse",
    "CompletionRequest",
    "CompletionResponse",
    "ModelInfo",
    "ModelsResponse",
    "ToolInfo",
    "ToolsResponse",
    "ToolExecuteRequest",
    "ToolExecuteResponse",
    "HealthResponse",
]
