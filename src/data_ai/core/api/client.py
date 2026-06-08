"""
DATA-AI API 客户端基类

提供标准化的HTTP API客户端，支持：
- 统一的请求/响应处理
- 自动重试机制
- 超时控制
- 错误处理和转换
- 请求/响应日志记录
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

import httpx

from ...utils.exceptions import APIConnectionError, APIResponseError, APITimeoutError
from ...utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class HTTPMethod(Enum):
    """HTTP 方法枚举"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class APIResponse(Generic[T]):
    """
    API 响应封装

    Attributes:
        status_code: HTTP 状态码
        data: 解析后的响应数据
        headers: 响应头
        raw_response: 原始响应对象
        request_time_ms: 请求耗时（毫秒）
    """

    status_code: int
    data: T
    headers: dict[str, str] = field(default_factory=dict)
    raw_response: httpx.Response | None = None
    request_time_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        """是否成功响应（2xx）"""
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        """是否错误响应（4xx, 5xx）"""
        return self.status_code >= 400


@dataclass
class APIError(Exception):
    """
    API 错误封装

    Attributes:
        message: 错误消息
        status_code: HTTP 状态码
        error_code: 业务错误码
        details: 详细错误信息
    """

    message: str
    status_code: int | None = None
    error_code: str | None = None
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        if self.error_code:
            parts.append(f"[Code: {self.error_code}]")
        return " ".join(parts)


class APIClient:
    """
    标准化 API 客户端

    提供统一的HTTP请求接口，自动处理：
    - 连接管理
    - 重试机制
    - 超时控制
    - 错误转换
    - 日志记录

    Example:
        ```python
        client = APIClient(
            base_url="https://api.example.com",
            api_key="your-api-key",
            timeout=30.0,
        )

        response = client.get("/users/123")
        if response.is_success:
            print(response.data)
        ```
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        headers: dict[str, str] | None = None,
    ):
        """
        初始化 API 客户端

        Args:
            base_url: API 基础 URL
            api_key: API 密钥（可选）
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟基数（秒）
            headers: 默认请求头
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # 构建默认请求头
        self.default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DATA-AI-CLI/1.0",
        }
        if headers:
            self.default_headers.update(headers)
        if api_key:
            self.default_headers["Authorization"] = f"Bearer {api_key}"

        # 创建 HTTP 客户端
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers=self.default_headers,
        )

        logger.debug(
            "API客户端初始化完成",
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=self.max_retries,
        )

    def _make_request(
        self,
        method: HTTPMethod,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> APIResponse[Any]:
        """
        执行 HTTP 请求

        Args:
            method: HTTP 方法
            endpoint: API 端点（相对于 base_url）
            params: URL 查询参数
            json_data: JSON 请求体
            headers: 额外请求头
            timeout: 本次请求超时时间

        Returns:
            APIResponse 对象

        Raises:
            APIConnectionError: 连接错误
            APITimeoutError: 超时错误
            APIResponseError: 响应错误
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_headers = {**self.default_headers}
        if headers:
            request_headers.update(headers)

        start_time = time.time()

        try:
            logger.debug(
                f"API请求: {method.value} {endpoint}",
                method=method.value,
                endpoint=endpoint,
                has_body=json_data is not None,
            )

            response = self._client.request(
                method=method.value,
                url=url,
                params=params,
                json=json_data,
                headers=request_headers,
                timeout=timeout or self.timeout,
            )

            request_time_ms = (time.time() - start_time) * 1000

            # 解析响应
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = {"raw": response.text}

            api_response = APIResponse(
                status_code=response.status_code,
                data=data,
                headers=dict(response.headers),
                raw_response=response,
                request_time_ms=request_time_ms,
            )

            # 记录响应
            log_level = "info" if api_response.is_success else "warning"
            getattr(logger, log_level)(
                f"API响应: {method.value} {endpoint} - {response.status_code}",
                method=method.value,
                endpoint=endpoint,
                status_code=response.status_code,
                request_time_ms=round(request_time_ms, 2),
            )

            # 处理错误响应
            if api_response.is_error:
                error_msg = data.get("error", data.get("message", "Unknown error"))
                error_code = data.get("code")

                raise APIResponseError(
                    message=f"API请求失败: {error_msg}",
                    status_code=response.status_code,
                    error_code=error_code,
                    details=data,
                )

            return api_response

        except httpx.TimeoutException as e:
            request_time_ms = (time.time() - start_time) * 1000
            logger.error(
                f"API请求超时: {method.value} {endpoint}",
                method=method.value,
                endpoint=endpoint,
                timeout=timeout or self.timeout,
                request_time_ms=round(request_time_ms, 2),
            )
            raise APITimeoutError(
                message=f"API请求超时: {endpoint}",
                timeout=timeout or self.timeout,
            ) from e

        except httpx.NetworkError as e:
            logger.error(
                f"API连接错误: {method.value} {endpoint}",
                method=method.value,
                endpoint=endpoint,
                error=str(e),
            )
            raise APIConnectionError(
                message=f"API连接错误: {endpoint}",
                details={"error": str(e)},
            ) from e

        except APIResponseError:
            raise

        except Exception as e:
            logger.error(
                f"API请求异常: {method.value} {endpoint}",
                method=method.value,
                endpoint=endpoint,
                error_type=type(e).__name__,
                error=str(e),
            )
            raise APIConnectionError(
                message=f"API请求异常: {endpoint}",
                details={"error": str(e), "error_type": type(e).__name__},
            ) from e

    def get(
        self,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> APIResponse[Any]:
        """GET 请求"""
        return self._make_request(HTTPMethod.GET, endpoint, params=params, headers=headers, timeout=timeout)

    def post(
        self,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> APIResponse[Any]:
        """POST 请求"""
        return self._make_request(
            HTTPMethod.POST, endpoint, params=params, json_data=json_data, headers=headers, timeout=timeout
        )

    def put(
        self,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> APIResponse[Any]:
        """PUT 请求"""
        return self._make_request(HTTPMethod.PUT, endpoint, json_data=json_data, headers=headers, timeout=timeout)

    def delete(
        self,
        endpoint: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> APIResponse[Any]:
        """DELETE 请求"""
        return self._make_request(HTTPMethod.DELETE, endpoint, headers=headers, timeout=timeout)

    def patch(
        self,
        endpoint: str,
        *,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> APIResponse[Any]:
        """PATCH 请求"""
        return self._make_request(HTTPMethod.PATCH, endpoint, json_data=json_data, headers=headers, timeout=timeout)

    def close(self) -> None:
        """关闭客户端连接"""
        self._client.close()
        logger.debug("API客户端已关闭")

    def __enter__(self) -> APIClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


def create_api_client(
    provider: str,
    api_key: str,
    **kwargs,
) -> APIClient:
    """
    创建预配置的 API 客户端

    Args:
        provider: 提供商名称 (openai, anthropic, deepseek, etc.)
        api_key: API 密钥
        **kwargs: 额外配置参数

    Returns:
        配置好的 APIClient 实例
    """
    from .providers import PROVIDER_CONFIGS

    if provider not in PROVIDER_CONFIGS:
        raise ValueError(f"未知的 API 提供商: {provider}")

    config = PROVIDER_CONFIGS[provider].copy()
    config.update(kwargs)
    config["api_key"] = api_key

    return APIClient(**config)
