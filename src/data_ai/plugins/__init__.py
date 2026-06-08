"""
DATA-AI 插件系统

提供插件加载、管理、热更新能力：
- 插件基类（:class:`BasePlugin`）和生命周期
- 插件注册表（:class:`PluginRegistry`）
- 插件发现和加载
- 内置工具 / 记忆 / Agent 插件导出
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PluginInfo:
    """插件信息。"""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    plugin_type: str = "tool"  # tool, agent, memory
    dependencies: list[str] = field(default_factory=list)


class BasePlugin(ABC):
    """插件基类。"""

    info: PluginInfo = PluginInfo(name="base")

    def __init__(self) -> None:
        self._initialized = False
        self.logger = get_logger(f"plugin.{self.info.name}")

    @abstractmethod
    async def initialize(self) -> None:
        """初始化插件。"""
        raise NotImplementedError

    @abstractmethod
    async def cleanup(self) -> None:
        """清理插件资源。"""
        raise NotImplementedError

    @property
    def is_initialized(self) -> bool:
        """检查插件是否已初始化。"""
        return self._initialized


class PluginRegistry:
    """
    插件注册表。

    管理所有插件的注册、初始化和生命周期。
    """

    _instance: PluginRegistry | None = None

    def __new__(cls) -> PluginRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins = {}
            cls._instance._plugin_classes = {}
        return cls._instance

    def register_class(self, plugin_class: type[BasePlugin]) -> None:
        """注册插件类。"""
        info = plugin_class.info
        self._plugin_classes[info.name] = plugin_class
        logger.info(f"插件类已注册: {info.name}")

    def register_instance(self, plugin: BasePlugin) -> None:
        """注册插件实例。"""
        self._plugins[plugin.info.name] = plugin
        logger.info(f"插件实例已注册: {plugin.info.name}")

    async def create_and_initialize(self, name: str) -> BasePlugin | None:
        """创建并初始化插件。"""
        if name not in self._plugin_classes:
            logger.error(f"插件类未找到: {name}")
            return None

        plugin_class = self._plugin_classes[name]
        plugin = plugin_class()

        try:
            await plugin.initialize()
            plugin._initialized = True
            self._plugins[name] = plugin
            logger.info(f"插件已创建并初始化: {name}")
            return plugin
        except Exception as e:
            logger.error(f"插件初始化失败: {name}: {e}")
            return None

    def get(self, name: str) -> BasePlugin | None:
        """获取插件。"""
        return self._plugins.get(name)

    def list_plugins(self) -> list[str]:
        """列出所有已注册的插件。"""
        return list(self._plugins.keys())

    async def cleanup_all(self) -> None:
        """清理所有插件。"""
        for name, plugin in self._plugins.items():
            try:
                await plugin.cleanup()
                plugin._initialized = False
                logger.info(f"插件已清理: {name}")
            except Exception as e:
                logger.warning(f"插件清理失败: {name}: {e}")

    def discover_plugins(self, directory: str) -> list[str]:
        """
        从目录发现插件。

        扫描指定目录下的 Python 文件，查找 :class:`BasePlugin` 子类。
        """
        plugin_dir = Path(directory)
        if not plugin_dir.exists():
            logger.warning(f"插件目录不存在: {directory}")
            return []

        discovered: list[str] = []

        # 添加到 Python 路径
        dir_str = str(plugin_dir.parent)
        if dir_str not in sys.path:
            sys.path.insert(0, dir_str)

        for py_file in plugin_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = py_file.stem

            try:
                module = importlib.import_module(f"{plugin_dir.name}.{module_name}")

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BasePlugin) and obj is not BasePlugin and hasattr(obj, "info"):
                        self.register_class(obj)
                        discovered.append(obj.info.name)
                        logger.info(f"发现插件: {obj.info.name} ({py_file.name})")
            except Exception as e:
                logger.warning(f"加载插件文件失败: {py_file.name}: {e}")

        return discovered


# 全局注册表
_plugin_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    """获取全局插件注册表。"""
    global _plugin_registry
    if _plugin_registry is None:
        _plugin_registry = PluginRegistry()
    return _plugin_registry


# ─── 重新导出子模块中的主要 API ─────────────────────────────────────────────


# 工具插件
# 记忆插件
from .memory.json_memory import JSONMemory, JSONMemoryPlugin
from .tools.weather_tool import (
    WeatherConfig,
    WeatherTool,
    WeatherToolPlugin,
    get_forecast,
    get_weather,
    register_weather_tools,
)

__all__ = [
    # 核心
    "BasePlugin",
    "PluginInfo",
    "PluginRegistry",
    "get_plugin_registry",
    # 工具插件
    "WeatherTool",
    "WeatherConfig",
    "WeatherToolPlugin",
    "get_weather",
    "get_forecast",
    "register_weather_tools",
    # 记忆插件
    "JSONMemory",
    "JSONMemoryPlugin",
]
