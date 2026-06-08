"""
天气查询工具插件（WeatherTool）

提供基于 wttr.in 公共 API 的实时天气查询能力（无需鉴权）。

- :func:`get_weather` / :class:`WeatherTool`: 异步查询当前天气
- :func:`get_forecast`: 异步查询未来若干天的天气预报
- :func:`register_weather_tools`: 将上述能力注册到 :class:`ToolRegistry`
- :class:`WeatherToolPlugin`: 兼容旧插件系统的 BasePlugin 包装

数据源：https://wttr.in/{city}?format=j1
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from ...utils.logging import get_logger
from .. import BasePlugin, PluginInfo

logger = get_logger(__name__)


# ─── 公共常量 ──────────────────────────────────────────────────────────────


WTTR_URL_TEMPLATE = "https://wttr.in/{city}?format=j1"
DEFAULT_TIMEOUT: float = 15.0
DEFAULT_USER_AGENT = "data-ai-weather-plugin/1.0 (+https://github.com/badhope/DATA-AI)"


# ─── 配置 / 工具类 ────────────────────────────────────────────────────────


@dataclass
class WeatherConfig:
    """天气插件配置。"""

    default_city: str = "Beijing"
    timeout: float = DEFAULT_TIMEOUT
    units: str = "metric"  # metric / imperial
    language: str = "en"
    max_retries: int = 2


class WeatherTool:
    """
    天气工具类。

    Example:
        >>> tool = WeatherTool()
        >>> import asyncio
        >>> result = asyncio.run(tool.get_weather("Shanghai"))
        >>> result["city"]
        'Shanghai'
    """

    def __init__(self, config: WeatherConfig | None = None) -> None:
        self._config = config or WeatherConfig()

    @property
    def config(self) -> WeatherConfig:
        return self._config

    async def get_weather(self, city: str) -> dict[str, Any]:
        """
        异步获取指定城市的当前天气。

        Args:
            city: 城市名称（支持中英文、机场代码，例如 ``"Beijing"``、``"上海"``）。

        Returns:
            包含温度、湿度、天气描述、风速等字段的字典。
            失败时返回 ``{"success": False, "error": "..."}``。
        """
        return await self._fetch_weather(city, forecast_days=0)

    async def get_forecast(self, city: str, days: int = 3) -> dict[str, Any]:
        """
        异步获取未来若干天的天气预报。

        Args:
            city: 城市名称。
            days: 预报天数（1-3）。
        """
        if days < 1:
            days = 1
        if days > 3:
            days = 3
        return await self._fetch_weather(city, forecast_days=days)

    # ─── 内部实现 ────────────────────────────────────────────────────

    async def _fetch_weather(self, city: str, forecast_days: int) -> dict[str, Any]:
        if not city or not city.strip():
            return self._error_result("city 参数不能为空")

        url = WTTR_URL_TEMPLATE.format(city=quote(city.strip()))
        headers = {
            "Accept": "application/json",
            "Accept-Language": self._config.language,
            "User-Agent": DEFAULT_USER_AGENT,
        }
        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 2):  # 至少 1 次
            try:
                async with httpx.AsyncClient(
                    timeout=self._config.timeout,
                    follow_redirects=True,
                    headers=headers,
                ) as client:
                    response = await client.get(url)
                if response.status_code != 200:
                    last_error = RuntimeError(f"wttr.in 返回 HTTP {response.status_code}: {response.text[:200]}")
                    logger.warning(f"获取天气失败 city={city} status={response.status_code} attempt={attempt}")
                    continue
                data = response.json()
                return self._parse_response(city, data, forecast_days)
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(f"获取天气超时 city={city} attempt={attempt}: {exc}")
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(f"获取天气网络错误 city={city} attempt={attempt}: {exc}")
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                logger.warning(f"解析天气响应失败 city={city}: {exc}")
                break  # 数据格式错误无需重试
            except Exception as exc:  # pragma: no cover - 兜底
                last_error = exc
                logger.exception(f"未知错误 city={city}: {exc}")
                break

        return self._error_result(f"获取天气失败 city={city}: {last_error}" if last_error else "未知错误")

    def _parse_response(
        self,
        city: str,
        data: dict[str, Any],
        forecast_days: int,
    ) -> dict[str, Any]:
        """将 wttr.in 的 JSON 响应解析为标准化结构。"""
        current_section = (data.get("current_condition") or [{}])[0]
        nearest_area = (data.get("nearest_area") or [{}])[0]
        area_name = self._first_or_default(nearest_area.get("areaName"))
        region = self._first_or_default(nearest_area.get("region"))
        country = self._first_or_default(nearest_area.get("country"))
        resolved = ", ".join(filter(None, [area_name, region, country])) or city

        weather_desc_list = current_section.get("weatherDesc") or []
        weather_desc = self._first_or_default(weather_desc_list) or "Unknown"

        current_payload: dict[str, Any] = {
            "city": city,
            "resolved_location": resolved,
            "observation_time_utc": current_section.get("localObsDateTime", ""),
            "temperature_c": self._safe_float(current_section.get("temp_C")),
            "temperature_f": self._safe_float(current_section.get("temp_F")),
            "feels_like_c": self._safe_float(current_section.get("FeelsLikeC")),
            "feels_like_f": self._safe_float(current_section.get("FeelsLikeF")),
            "humidity": self._safe_int(current_section.get("humidity")),
            "weather_desc": weather_desc,
            "wind_speed_kmph": self._safe_float(current_section.get("windspeedKmph")),
            "wind_speed_mph": self._safe_float(current_section.get("windspeedMiles")),
            "wind_direction": current_section.get("winddir16Point", ""),
            "pressure_mb": self._safe_int(current_section.get("pressure")),
            "cloud_cover": self._safe_int(current_section.get("cloudcover")),
            "visibility_km": self._safe_float(current_section.get("visibility")),
            "uv_index": self._safe_float(current_section.get("uvIndex")),
            "units": self._config.units,
            "source": "wttr.in",
            "fetched_at": time.time(),
            "success": True,
        }

        if forecast_days > 0:
            forecasts: list[dict[str, Any]] = []
            for entry in (data.get("weather") or [])[:forecast_days]:
                hourly = entry.get("hourly") or []
                hourly[0] if hourly else {}
                forecasts.append(
                    {
                        "date": entry.get("date", ""),
                        "min_temp_c": self._safe_float(entry.get("mintempC")),
                        "max_temp_c": self._safe_float(entry.get("maxtempC")),
                        "min_temp_f": self._safe_float(entry.get("mintempF")),
                        "max_temp_f": self._safe_float(entry.get("maxtempF")),
                        "sunrise": entry.get("astronomy", [{}])[0].get("sunrise", ""),
                        "sunset": entry.get("astronomy", [{}])[0].get("sunset", ""),
                        "hourly": [
                            {
                                "time": self._safe_int(h.get("time")),
                                "temperature_c": self._safe_float(h.get("tempC")),
                                "weather_desc": self._first_or_default(h.get("weatherDesc")),
                                "wind_speed_kmph": self._safe_float(h.get("windspeedKmph")),
                                "humidity": self._safe_int(h.get("humidity")),
                                "chance_of_rain": self._safe_int(h.get("chanceofrain")),
                            }
                            for h in hourly
                            if h
                        ],
                    }
                )
            current_payload["forecast_days"] = forecasts
            current_payload["requested_forecast_days"] = forecast_days

        return current_payload

    # ─── 工具方法 ────────────────────────────────────────────────────

    @staticmethod
    def _first_or_default(value: Any, default: str = "") -> str:
        if isinstance(value, list) and value:
            first = value[0]
            if isinstance(first, dict):
                return str(first.get("value", default))
            return str(first)
        if isinstance(value, dict):
            return str(value.get("value", default))
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _error_result(self, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": message,
            "city": "",
            "source": "wttr.in",
            "fetched_at": time.time(),
        }


# ─── 便捷函数 / 向后兼容 ──────────────────────────────────────────────────


async def get_weather(city: str) -> dict[str, Any]:
    """
    顶层异步函数：查询指定城市的当前天气。

    Example:
        >>> import asyncio
        >>> asyncio.run(get_weather("Beijing"))  # doctest: +SKIP
    """
    return await WeatherTool().get_weather(city)


async def get_forecast(city: str, days: int = 3) -> dict[str, Any]:
    """顶层异步函数：查询天气预报。"""
    return await WeatherTool().get_forecast(city, days)


def register_weather_tools(registry: Any = None) -> int:
    """
    将天气工具注册到 :class:`ToolRegistry`（或其他具备 ``register`` 方法的对象）。

    Returns:
        注册的工具数量。
    """
    from ...core.tool.registry import ToolRegistry, get_tool_registry

    if registry is None:
        registry = get_tool_registry()
    elif isinstance(registry, ToolRegistry):
        pass  # 已是 ToolRegistry
    elif hasattr(registry, "register"):
        pass
    else:
        raise TypeError(
            f"register_weather_tools 需要 ToolRegistry 或 register() 兼容对象，收到 {type(registry).__name__}"
        )

    tool = WeatherTool()

    def _weather_query(city: str) -> dict[str, Any]:
        """同步包装：用于直接调用。返回字典（可能为 ``success=False``）。"""
        # 这里仅做同步兜底，真实调用应使用 await get_weather
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # 事件循环正在运行 -> 返回一个错误信息，让调用方改用异步接口
            return {
                "success": False,
                "error": "在事件循环中请使用 await get_weather(city)",
                "city": city,
            }
        return asyncio.run(tool.get_weather(city))

    def _weather_forecast(city: str, days: int = 3) -> dict[str, Any]:
        """同步包装：天气预报。"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            return {
                "success": False,
                "error": "在事件循环中请使用 await get_forecast(city, days)",
                "city": city,
            }
        return asyncio.run(tool.get_forecast(city, days))

    registry.register(
        name="weather_query",
        description="查询指定城市的当前天气（基于 wttr.in 公共 API）。",
        parameters={
            "city": {
                "type": "string",
                "description": "城市名称，例如 Beijing、Shanghai、Tokyo",
            }
        },
        required=["city"],
        function=_weather_query,
        is_async=False,
    )
    registry.register(
        name="weather_forecast",
        description="查询指定城市的未来若干天天气预报。",
        parameters={
            "city": {
                "type": "string",
                "description": "城市名称，例如 Beijing、Shanghai、Tokyo",
            },
            "days": {
                "type": "integer",
                "description": "预报天数，范围 1-3",
                "default": 3,
            },
        },
        required=["city"],
        function=_weather_forecast,
        is_async=False,
    )
    # 同时把异步函数注册为 is_async，让 ToolRegistry.execute 走 await 路径
    try:
        registry.register(
            name="weather_query_async",
            description="异步查询指定城市的当前天气。",
            parameters={
                "city": {
                    "type": "string",
                    "description": "城市名称",
                }
            },
            required=["city"],
            function=get_weather,
            is_async=True,
        )
        registry.register(
            name="weather_forecast_async",
            description="异步查询天气预报。",
            parameters={
                "city": {"type": "string", "description": "城市名称"},
                "days": {"type": "integer", "description": "预报天数 1-3", "default": 3},
            },
            required=["city"],
            function=get_forecast,
            is_async=True,
        )
        return 4
    except Exception:  # pragma: no cover
        return 2


# ─── 兼容旧版 BasePlugin 包装 ─────────────────────────────────────────────


class WeatherToolPlugin(BasePlugin):
    """天气查询工具插件（BasePlugin 风格）。"""

    info = PluginInfo(
        name="weather_tool",
        version="0.2.0",
        description="天气查询工具插件，支持查询全球城市天气（基于 wttr.in 公共 API）",
        author="DATA-AI",
        plugin_type="tool",
    )

    def __init__(self, config: WeatherConfig | None = None) -> None:
        super().__init__()
        self._config = config or WeatherConfig()
        self._tool = WeatherTool(self._config)

    async def initialize(self) -> None:
        self.logger.info("天气工具插件初始化完成")
        self._initialized = True

    async def cleanup(self) -> None:
        self.logger.info("天气工具插件已清理")
        self._initialized = False

    async def get_weather(self, city: str) -> dict[str, Any]:
        return await self._tool.get_weather(city)

    async def get_forecast(self, city: str, days: int = 3) -> dict[str, Any]:
        return await self._tool.get_forecast(city, days)

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "weather_query",
                "description": "查询指定城市的当前天气",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称",
                        }
                    },
                    "required": ["city"],
                },
            },
            {
                "name": "weather_forecast",
                "description": "查询指定城市的天气预报",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名称"},
                        "days": {"type": "integer", "description": "预报天数", "default": 3},
                    },
                    "required": ["city"],
                },
            },
        ]


__all__ = [
    "WeatherTool",
    "WeatherConfig",
    "WeatherToolPlugin",
    "get_weather",
    "get_forecast",
    "register_weather_tools",
]
