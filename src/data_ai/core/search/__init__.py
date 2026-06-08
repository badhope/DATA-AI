"""
DATA-AI 搜索引擎模块

提供统一的搜索接口，支持多种搜索引擎：
- DuckDuckGo（默认，免费无需API Key）
- Google（需要API Key）
- Baidu（需要API Key，国内优化）
- Bing（需要API Key）
- SerpAPI（需要API Key）
- 自定义搜索引擎
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ...utils.exceptions import SearchException
from ...utils.logging import get_logger

logger = get_logger(__name__)


class SearchEngineType(Enum):
    """搜索引擎类型"""

    DUCKDUCKGO = "duckduckgo"
    GOOGLE = "google"
    BAIDU = "baidu"
    BING = "bing"
    SERPAPI = "serpapi"
    CUSTOM = "custom"


@dataclass
class SearchResult:
    """搜索结果"""

    title: str
    url: str
    snippet: str
    source: str = ""
    rank: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """搜索响应"""

    query: str
    engine: str
    results: list[SearchResult]
    total: int = 0
    error: str | None = None
    execution_time_ms: float = 0.0


class BaseSearchEngine(ABC):
    """搜索引擎基类"""

    name: str = "base"
    requires_api_key: bool = False

    def __init__(self, api_key: str | None = None, **kwargs):
        self.api_key = api_key
        self.config = kwargs
        self.logger = get_logger(f"search.{self.name}")

    @abstractmethod
    async def search(self, query: str, num_results: int = 5) -> SearchResponse:
        """执行搜索"""
        pass

    def is_available(self) -> bool:
        """检查引擎是否可用"""
        if self.requires_api_key and not self.api_key:
            return False
        return True


class DuckDuckGoEngine(BaseSearchEngine):
    """DuckDuckGo 搜索引擎（免费，无需API Key）"""

    name = "duckduckgo"
    requires_api_key = False

    async def search(self, query: str, num_results: int = 5) -> SearchResponse:
        import time

        start_time = time.time()

        try:
            from duckduckgo_search import DDGS

            results = []
            with DDGS() as ddgs:
                search_results = ddgs.text(query, max_results=num_results)
                for i, r in enumerate(search_results):
                    results.append(
                        SearchResult(
                            title=r.get("title", ""),
                            url=r.get("href", ""),
                            snippet=r.get("body", ""),
                            source=self.name,
                            rank=i + 1,
                        )
                    )

            return SearchResponse(
                query=query,
                engine=self.name,
                results=results,
                total=len(results),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except ImportError:
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error="duckduckgo-search not installed. Run: pip install duckduckgo-search",
            )
        except Exception as e:
            self.logger.error(f"DuckDuckGo search error: {e}")
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error=str(e),
            )


class GoogleEngine(BaseSearchEngine):
    """Google 搜索引擎（需要API Key）"""

    name = "google"
    requires_api_key = True

    def __init__(self, api_key: str | None = None, search_engine_id: str | None = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.search_engine_id = search_engine_id or kwargs.get("cx")

    async def search(self, query: str, num_results: int = 5) -> SearchResponse:
        import time

        import httpx

        start_time = time.time()

        if not self.api_key or not self.search_engine_id:
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error="Google search requires API key and Search Engine ID (cx)",
            )

        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.api_key,
                "cx": self.search_engine_id,
                "q": query,
                "num": num_results,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            results = []
            items = data.get("items", [])
            for i, item in enumerate(items):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        source=self.name,
                        rank=i + 1,
                        extra={
                            "display_link": item.get("displayLink", ""),
                        },
                    )
                )

            return SearchResponse(
                query=query,
                engine=self.name,
                results=results,
                total=len(results),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.error(f"Google search error: {e}")
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error=str(e),
            )


class BaiduEngine(BaseSearchEngine):
    """百度搜索引擎（国内优化）"""

    name = "baidu"
    requires_api_key = False  # 可以通过爬虫方式实现

    async def search(self, query: str, num_results: int = 5) -> SearchResponse:
        import time
        import urllib.parse

        import httpx

        start_time = time.time()

        try:
            # 使用百度搜索API（简化版，实际可能需要更多处理）
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.baidu.com/s?wd={encoded_query}&rn={num_results}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
                html = response.text

            # 简单解析结果（实际应使用BeautifulSoup）
            results = self._parse_baidu_results(html, num_results)

            return SearchResponse(
                query=query,
                engine=self.name,
                results=results,
                total=len(results),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.error(f"Baidu search error: {e}")
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error=str(e),
            )

    def _parse_baidu_results(self, html: str, max_results: int) -> list[SearchResult]:
        """解析百度搜索结果"""
        results = []
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")

            for i, item in enumerate(soup.select(".result")[:max_results]):
                title_elem = item.select_one("h3 a")
                snippet_elem = item.select_one(".c-abstract") or item.select_one(".c-span9")

                if title_elem:
                    results.append(
                        SearchResult(
                            title=title_elem.get_text(strip=True),
                            url=title_elem.get("href", ""),
                            snippet=snippet_elem.get_text(strip=True) if snippet_elem else "",
                            source=self.name,
                            rank=i + 1,
                        )
                    )
        except ImportError:
            # 如果没有BeautifulSoup，返回提示
            results.append(
                SearchResult(
                    title="需要安装 BeautifulSoup",
                    url="",
                    snippet="运行: pip install beautifulsoup4 lxml",
                    source=self.name,
                )
            )
        except Exception as e:
            self.logger.warning(f"Parse baidu results error: {e}")

        return results


class BingEngine(BaseSearchEngine):
    """Bing 搜索引擎（需要API Key）"""

    name = "bing"
    requires_api_key = True

    async def search(self, query: str, num_results: int = 5) -> SearchResponse:
        import time

        import httpx

        start_time = time.time()

        if not self.api_key:
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error="Bing search requires API key",
            )

        try:
            url = "https://api.bing.microsoft.com/v7.0/search"
            headers = {"Ocp-Apim-Subscription-Key": self.api_key}
            params = {"q": query, "count": num_results, "mkt": "zh-CN"}

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            results = []
            web_pages = data.get("webPages", {}).get("value", [])
            for i, item in enumerate(web_pages):
                results.append(
                    SearchResult(
                        title=item.get("name", ""),
                        url=item.get("url", ""),
                        snippet=item.get("snippet", ""),
                        source=self.name,
                        rank=i + 1,
                        extra={
                            "display_url": item.get("displayUrl", ""),
                            "date_last_crawled": item.get("dateLastCrawled", ""),
                        },
                    )
                )

            return SearchResponse(
                query=query,
                engine=self.name,
                results=results,
                total=len(results),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.error(f"Bing search error: {e}")
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error=str(e),
            )


class SerpAPIEngine(BaseSearchEngine):
    """SerpAPI 搜索引擎（聚合搜索）"""

    name = "serpapi"
    requires_api_key = True

    async def search(self, query: str, num_results: int = 5) -> SearchResponse:
        import time

        import httpx

        start_time = time.time()

        if not self.api_key:
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error="SerpAPI requires API key",
            )

        try:
            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": self.api_key,
                "num": num_results,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                response.raise_for_status()
                data = response.json()

            results = []
            organic_results = data.get("organic_results", [])
            for i, item in enumerate(organic_results):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        source=self.name,
                        rank=i + 1,
                        extra={
                            "position": item.get("position", 0),
                            "displayed_link": item.get("displayed_link", ""),
                        },
                    )
                )

            return SearchResponse(
                query=query,
                engine=self.name,
                results=results,
                total=len(results),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.error(f"SerpAPI search error: {e}")
            return SearchResponse(
                query=query,
                engine=self.name,
                results=[],
                error=str(e),
            )


class CustomSearchEngine(BaseSearchEngine):
    """自定义搜索引擎"""

    name = "custom"
    requires_api_key = False

    def __init__(
        self,
        name: str = "custom",
        search_url: str = "",
        api_key: str | None = None,
        result_parser: callable | None = None,
        headers: dict[str, str] | None = None,
        **kwargs,
    ):
        super().__init__(api_key, **kwargs)
        self.custom_name = name
        self.search_url = search_url
        self.result_parser = result_parser
        self.headers = headers or {}

    async def search(self, query: str, num_results: int = 5) -> SearchResponse:
        import time

        import httpx

        start_time = time.time()

        if not self.search_url:
            return SearchResponse(
                query=query,
                engine=self.custom_name,
                results=[],
                error="Custom search engine requires search_url",
            )

        try:
            # 替换URL中的占位符
            url = self.search_url.replace("{query}", query).replace("{num}", str(num_results))
            if self.api_key:
                url = url.replace("{api_key}", self.api_key)

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, timeout=10.0)
                response.raise_for_status()

                if self.result_parser:
                    data = self.result_parser(response.text, response)
                else:
                    data = response.json()

            results = []
            if isinstance(data, list):
                for i, item in enumerate(data[:num_results]):
                    results.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", item.get("link", "")),
                            snippet=item.get("snippet", item.get("description", "")),
                            source=self.custom_name,
                            rank=i + 1,
                        )
                    )

            return SearchResponse(
                query=query,
                engine=self.custom_name,
                results=results,
                total=len(results),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            self.logger.error(f"Custom search error: {e}")
            return SearchResponse(
                query=query,
                engine=self.custom_name,
                results=[],
                error=str(e),
            )


class SearchEngineManager:
    """
    搜索引擎管理器

    管理所有搜索引擎的注册、配置和切换
    """

    _instance: SearchEngineManager | None = None

    def __new__(cls) -> SearchEngineManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._engines: dict[str, BaseSearchEngine] = {}
            cls._instance._default_engine: str = "duckduckgo"
            cls._instance._configs: dict[str, dict] = {}
        return cls._instance

    def register_engine(self, engine: BaseSearchEngine, set_default: bool = False) -> None:
        """注册搜索引擎"""
        self._engines[engine.name] = engine
        if set_default:
            self._default_engine = engine.name
        logger.info(f"搜索引擎已注册: {engine.name}")

    def register_custom_engine(
        self,
        name: str,
        search_url: str,
        api_key: str | None = None,
        headers: dict | None = None,
        result_parser: callable | None = None,
    ) -> None:
        """注册自定义搜索引擎"""
        engine = CustomSearchEngine(
            name=name,
            search_url=search_url,
            api_key=api_key,
            headers=headers,
            result_parser=result_parser,
        )
        self._engines[name] = engine
        logger.info(f"自定义搜索引擎已注册: {name}")

    def get_engine(self, name: str | None = None) -> BaseSearchEngine:
        """获取搜索引擎"""
        engine_name = name or self._default_engine
        if engine_name not in self._engines:
            raise SearchException(f"搜索引擎不存在: {engine_name}")
        return self._engines[engine_name]

    def set_default_engine(self, name: str) -> None:
        """设置默认搜索引擎"""
        if name not in self._engines:
            raise SearchException(f"搜索引擎不存在: {name}")
        self._default_engine = name
        logger.info(f"默认搜索引擎已设置为: {name}")

    def list_engines(self) -> list[str]:
        """列出所有搜索引擎"""
        return list(self._engines.keys())

    def get_available_engines(self) -> list[str]:
        """列出所有可用的搜索引擎"""
        return [name for name, engine in self._engines.items() if engine.is_available()]

    async def search(
        self,
        query: str,
        engine: str | None = None,
        num_results: int = 5,
    ) -> SearchResponse:
        """执行搜索"""
        search_engine = self.get_engine(engine)
        return await search_engine.search(query, num_results)

    def configure_engine(self, name: str, **kwargs) -> None:
        """配置搜索引擎"""
        self._configs[name] = kwargs
        # 如果引擎已存在，更新配置
        if name in self._engines:
            engine = self._engines[name]
            for key, value in kwargs.items():
                if hasattr(engine, key):
                    setattr(engine, key, value)
        logger.info(f"搜索引擎配置已更新: {name}")


def register_builtin_engines(
    google_api_key: str | None = None,
    google_cx: str | None = None,
    bing_api_key: str | None = None,
    serpapi_key: str | None = None,
) -> SearchEngineManager:
    """注册内置搜索引擎"""
    manager = SearchEngineManager()

    # DuckDuckGo（默认）
    manager.register_engine(DuckDuckGoEngine(), set_default=True)

    # Google
    if google_api_key and google_cx:
        manager.register_engine(GoogleEngine(api_key=google_api_key, search_engine_id=google_cx))
    else:
        manager.register_engine(GoogleEngine())

    # Baidu
    manager.register_engine(BaiduEngine())

    # Bing
    if bing_api_key:
        manager.register_engine(BingEngine(api_key=bing_api_key))
    else:
        manager.register_engine(BingEngine())

    # SerpAPI
    if serpapi_key:
        manager.register_engine(SerpAPIEngine(api_key=serpapi_key))
    else:
        manager.register_engine(SerpAPIEngine())

    logger.info(f"已注册 {len(manager.list_engines())} 个内置搜索引擎")
    return manager


# 全局管理器
_search_manager: SearchEngineManager | None = None


def get_search_manager() -> SearchEngineManager:
    """获取全局搜索引擎管理器"""
    global _search_manager
    if _search_manager is None:
        _search_manager = register_builtin_engines()
    return _search_manager
