"""
DATA-AI API 注册表

提供标准化的API客户端注册和发现机制，确保：
- 新API可以方便地接入
- 统一的配置管理
- 自动错误处理
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ...utils.logging import get_logger
from .client import APIClient

logger = get_logger(__name__)


@dataclass
class APIConfig:
    """
    API 配置

    Attributes:
        name: API 名称
        base_url: 基础 URL
        auth_type: 认证类型 (api_key, bearer, basic, custom)
        default_headers: 默认请求头
        timeout: 默认超时时间
        max_retries: 最大重试次数
        doc_url: 文档 URL
    """

    name: str
    base_url: str
    auth_type: str = "api_key"
    default_headers: dict[str, str] = field(default_factory=dict)
    timeout: float = 30.0
    max_retries: int = 3
    doc_url: str | None = None


class APIRegistry:
    """
    API 注册表

    管理所有 API 客户端的注册和创建

    Example:
        ```python
        # 注册新的 API
        registry.register(
            "my_api",
            APIConfig(
                name="My API",
                base_url="https://api.example.com",
                auth_type="api_key",
            )
        )

        # 创建客户端
        client = registry.create_client("my_api", api_key="secret")
        ```
    """

    _instance: APIRegistry | None = None

    def __new__(cls) -> APIRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._configs: dict[str, APIConfig] = {}
            cls._instance._clients: dict[str, APIClient] = {}
            cls._instance._factories: dict[str, Callable[..., APIClient]] = {}
        return cls._instance

    def register(
        self,
        name: str,
        config: APIConfig,
        factory: Callable[..., APIClient] | None = None,
    ) -> None:
        """
        注册 API

        Args:
            name: API 标识名
            config: API 配置
            factory: 可选的自定义客户端工厂函数
        """
        self._configs[name] = config
        if factory:
            self._factories[name] = factory

        logger.info(
            f"API已注册: {name}",
            api_name=name,
            base_url=config.base_url,
            auth_type=config.auth_type,
        )

    def unregister(self, name: str) -> None:
        """注销 API"""
        if name in self._configs:
            del self._configs[name]
        if name in self._clients:
            self._clients[name].close()
            del self._clients[name]
        if name in self._factories:
            del self._factories[name]

        logger.info(f"API已注销: {name}")

    def create_client(
        self,
        name: str,
        api_key: str | None = None,
        **kwargs,
    ) -> APIClient:
        """
        创建 API 客户端

        Args:
            name: API 标识名
            api_key: API 密钥
            **kwargs: 额外配置参数

        Returns:
            APIClient 实例

        Raises:
            ValueError: API 未注册
        """
        if name not in self._configs:
            raise ValueError(f"API未注册: {name}")

        # 使用自定义工厂
        if name in self._factories:
            return self._factories[name](api_key=api_key, **kwargs)

        # 使用默认配置创建
        config = self._configs[name]
        client_kwargs = {
            "base_url": config.base_url,
            "timeout": config.timeout,
            "max_retries": config.max_retries,
            "headers": config.default_headers.copy(),
        }

        if api_key:
            client_kwargs["api_key"] = api_key

        client_kwargs.update(kwargs)

        client = APIClient(**client_kwargs)
        self._clients[name] = client

        logger.debug(
            f"API客户端已创建: {name}",
            api_name=name,
            base_url=config.base_url,
        )

        return client

    def get_client(self, name: str) -> APIClient | None:
        """获取已创建的客户端"""
        return self._clients.get(name)

    def get_config(self, name: str) -> APIConfig | None:
        """获取 API 配置"""
        return self._configs.get(name)

    def list_apis(self) -> dict[str, APIConfig]:
        """列出所有已注册的 API"""
        return self._configs.copy()

    def close_all(self) -> None:
        """关闭所有客户端连接"""
        for name, client in self._clients.items():
            client.close()
            logger.debug(f"API客户端已关闭: {name}")
        self._clients.clear()


# 全局注册表实例
_registry = APIRegistry()


def register_api(
    name: str,
    base_url: str,
    auth_type: str = "api_key",
    **kwargs,
) -> None:
    """
    注册 API（便捷函数）

    Args:
        name: API 标识名
        base_url: 基础 URL
        auth_type: 认证类型
        **kwargs: 其他配置参数
    """
    config = APIConfig(
        name=name,
        base_url=base_url,
        auth_type=auth_type,
        **kwargs,
    )
    _registry.register(name, config)


def get_api_client(
    name: str,
    api_key: str | None = None,
    **kwargs,
) -> APIClient:
    """
    获取 API 客户端（便捷函数）

    Args:
        name: API 标识名
        api_key: API 密钥
        **kwargs: 其他配置参数

    Returns:
        APIClient 实例
    """
    return _registry.create_client(name, api_key=api_key, **kwargs)


def get_registry() -> APIRegistry:
    """获取全局注册表实例"""
    return _registry
