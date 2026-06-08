"""
DATA-AI API 认证模块

客户端：
- API Key 认证
- Bearer Token 认证
- 自定义认证

服务端（FastAPI 依赖）：
- ``verify_api_key`` 检查 ``Authorization: Bearer <key>`` 或 ``X-Api-Key: <key>``
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


class AuthProvider(ABC):
    """
    认证提供者基类

    所有认证方式都需要实现此接口
    """

    @abstractmethod
    def get_headers(self) -> dict[str, str]:
        """获取认证相关的请求头"""
        pass

    @abstractmethod
    def get_params(self) -> dict[str, str]:
        """获取认证相关的查询参数"""
        pass


@dataclass
class APIKeyAuth(AuthProvider):
    """
    API Key 认证

    支持多种 API Key 传递方式：
    - Header: X-API-Key: <key>
    - Query: ?api_key=<key>
    - Bearer: Authorization: Bearer <key>

    Example:
        ```python
        # Header 方式
        auth = APIKeyAuth("your-api-key", header_name="X-API-Key")

        # Query 方式
        auth = APIKeyAuth("your-api-key", in_query=True, param_name="api_key")

        # Bearer 方式
        auth = APIKeyAuth("your-api-key", as_bearer=True)
        ```
    """

    api_key: str
    header_name: str = "X-API-Key"
    in_query: bool = False
    param_name: str = "api_key"
    as_bearer: bool = False

    def get_headers(self) -> dict[str, str]:
        """获取认证请求头"""
        if self.as_bearer:
            return {"Authorization": f"Bearer {self.api_key}"}
        elif not self.in_query:
            return {self.header_name: self.api_key}
        return {}

    def get_params(self) -> dict[str, str]:
        """获取认证查询参数"""
        if self.in_query:
            return {self.param_name: self.api_key}
        return {}


@dataclass
class BearerTokenAuth(AuthProvider):
    """
    Bearer Token 认证

    标准的 OAuth2 Bearer Token 认证方式

    Example:
        ```python
        auth = BearerTokenAuth("your-access-token")
        ```
    """

    token: str

    def get_headers(self) -> dict[str, str]:
        """获取认证请求头"""
        return {"Authorization": f"Bearer {self.token}"}

    def get_params(self) -> dict[str, str]:
        """获取认证查询参数"""
        return {}


# ============================================================================
# 服务端：FastAPI 依赖
# ============================================================================


async def verify_api_key(
    authorization: str | None = None,
    x_api_key: str | None = None,
) -> str:
    """
    验证 API Key（服务端 FastAPI 依赖）

    支持两种认证方式:
    1. Authorization: Bearer <api_key>
    2. X-Api-Key: <api_key>

    默认拒绝未认证请求（401）。可通过环境变量 ``DATA_AI_DEV_MODE=true``
    或显式 ``DATA_AI_API_KEYS="key1,key2"`` 配置：
    - 未设置 ``DATA_AI_API_KEYS`` 且 ``DATA_AI_DEV_MODE=true`` → 放行所有
      （dev/staging 友好，**生产绝不能开**）
    - 设置了 ``DATA_AI_API_KEYS`` → 仅放行列表内的 key
    """
    # 延迟 import FastAPI（避免在 client-only 场景下强依赖 fastapi）
    from fastapi import HTTPException, status

    # 当作为 FastAPI 依赖使用时，参数由 FastAPI 注入（Header）。
    # 当手动调用（带 position args）时也支持。
    configured = os.environ.get("DATA_AI_API_KEYS", "").strip()
    dev_mode = os.environ.get("DATA_AI_DEV_MODE", "").lower() in ("1", "true", "yes")

    api_key = None

    if authorization:
        if authorization.lower().startswith("bearer "):
            api_key = authorization[7:].strip()
        else:
            api_key = authorization.strip()

    if not api_key and x_api_key:
        api_key = x_api_key.strip()

    # dev mode 优先：显式开 dev_mode 时放行所有请求，
    # 这样在本地/测试/CI 同时配置 ``DATA_AI_API_KEYS`` 与 ``DATA_AI_DEV_MODE``
    # 时不需要每次都传 key。
    if dev_mode:
        return api_key or "dev-mode"

    # 配置了白名单 → 必须匹配
    if configured:
        allowed = {k.strip() for k in configured.split(",") if k.strip()}
        if api_key and api_key in allowed:
            return api_key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 默认：拒绝
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: API key required. Set DATA_AI_API_KEYS or DATA_AI_DEV_MODE=true.",
        headers={"WWW-Authenticate": "Bearer"},
    )


# 为 FastAPI 依赖注入声明 Header 别名（如果用户在路由用 Depends(verify_api_key)）
try:
    from fastapi import Header as _Header  # noqa: F401

    # 重新声明一个有 Header 注解的 wrapper 以便 FastAPI 识别
    async def verify_api_key_header(
        authorization: str | None = _Header(None),
        x_api_key: str | None = _Header(None),
    ) -> str:
        return await verify_api_key(authorization=authorization, x_api_key=x_api_key)
except Exception:
    pass
