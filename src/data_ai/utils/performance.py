"""
DATA-AI 性能优化模块

提供缓存、连接池、预热等性能优化能力。
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from .logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class LRUCache:
    """
    线程安全的 LRU 缓存

    支持过期时间和最大容量限制。
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, float] = {}
        self._access_count: dict[str, int] = {}

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存值"""
        if key not in self._cache:
            return default

        # 检查过期
        if self._is_expired(key):
            self.delete(key)
            return default

        # 更新访问时间
        self._timestamps[key] = time.time()
        self._access_count[key] = self._access_count.get(key, 0) + 1

        return self._cache[key]

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """设置缓存值"""
        # 超过容量时淘汰
        if len(self._cache) >= self._max_size and key not in self._cache:
            self._evict()

        self._cache[key] = value
        self._timestamps[key] = time.time()
        self._access_count[key] = 0

        # 如果有自定义 TTL，存储在 _timestamps 中用负数标记
        if ttl is not None and ttl != self._default_ttl:
            self._timestamps[f"_ttl_{key}"] = ttl

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        if key in self._cache:
            del self._cache[key]
            self._timestamps.pop(key, None)
            self._access_count.pop(key, None)
            self._timestamps.pop(f"_ttl_{key}", None)
            return True
        return False

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._timestamps.clear()
        self._access_count.clear()

    def _is_expired(self, key: str) -> bool:
        """检查是否过期"""
        ts = self._timestamps.get(key, 0)
        ttl = self._timestamps.get(f"_ttl_{key}", self._default_ttl)
        return time.time() - ts > ttl

    def _evict(self) -> None:
        """淘汰最少使用的缓存项"""
        # 先清理过期项
        expired = [k for k in self._cache if self._is_expired(k)]
        for key in expired:
            self.delete(key)

        if len(self._cache) < self._max_size:
            return

        # 按 LRU 淘汰
        if self._timestamps:
            oldest_key = min(
                (k for k in self._cache if not k.startswith("_ttl_")),
                key=lambda k: self._timestamps.get(k, 0),
            )
            self.delete(oldest_key)

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计"""
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "expired": sum(1 for k in self._cache if self._is_expired(k)),
        }

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return key in self._cache and not self._is_expired(key)


class FileCache:
    """
    基于文件的持久化缓存

    将缓存数据存储在磁盘上，适合跨会话使用。
    """

    def __init__(self, cache_dir: str | None = None, max_size_mb: int = 100):
        self._cache_dir = Path(cache_dir or os.path.expanduser("~/.data-ai/cache"))
        self._max_size_bytes = max_size_mb * 1024 * 1024
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        """将缓存键转换为文件路径"""
        safe_key = hashlib.md5(key.encode()).hexdigest()
        return self._cache_dir / f"{safe_key}.json"

    def get(self, key: str, default: Any = None) -> Any:
        """获取缓存"""
        path = self._key_to_path(key)
        if not path.exists():
            return default

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            # 检查过期
            if "expires_at" in data and time.time() > data["expires_at"]:
                path.unlink()
                return default

            return data.get("value", default)
        except Exception:
            return default

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """设置缓存"""
        data = {"value": value}
        if ttl:
            data["expires_at"] = time.time() + ttl

        path = self._key_to_path(key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def delete(self, key: str) -> bool:
        """删除缓存"""
        path = self._key_to_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear(self, max_age_seconds: float | None = None) -> int:
        """清理缓存"""
        count = 0
        for path in self._cache_dir.glob("*.json"):
            try:
                if max_age_seconds:
                    if time.time() - path.stat().st_mtime > max_age_seconds:
                        path.unlink()
                        count += 1
                else:
                    path.unlink()
                    count += 1
            except Exception:
                pass
        return count

    def get_size_mb(self) -> float:
        """获取缓存大小（MB）"""
        total = sum(f.stat().st_size for f in self._cache_dir.glob("*.json") if f.is_file())
        return total / (1024 * 1024)


def timed_cache(max_size: int = 128, ttl: float = 300.0):
    """
    带过期时间的缓存装饰器

    Usage:
        @timed_cache(max_size=50, ttl=60)
        def expensive_function(x):
            return x * x
    """
    cache = LRUCache(max_size=max_size, default_ttl=ttl)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = hashlib.md5(f"{func.__name__}:{args}:{kwargs}".encode()).hexdigest()

            result = cache.get(key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache_clear = cache.clear
        wrapper.cache_stats = cache.get_stats
        return wrapper

    return decorator


class ConnectionPool:
    """
    简单的异步连接池

    用于管理 HTTP 客户端等可复用连接。
    """

    def __init__(self, factory: Callable, max_size: int = 10):
        self._factory = factory
        self._max_size = max_size
        self._pool: list[Any] = []
        self._in_use: int = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> Any:
        """获取连接"""
        async with self._lock:
            if self._pool:
                return self._pool.pop()

            if self._in_use < self._max_size:
                self._in_use += 1
                return await self._factory()

            raise RuntimeError("连接池已满")

    async def release(self, conn: Any) -> None:
        """释放连接"""
        async with self._lock:
            self._pool.append(conn)

    @property
    def available(self) -> int:
        return len(self._pool)

    @property
    def in_use(self) -> int:
        return self._in_use - len(self._pool)


class PerformanceMonitor:
    """
    性能监控器

    跟踪函数执行时间和资源使用。
    """

    def __init__(self):
        self._timings: dict[str, list[float]] = {}
        self._counters: dict[str, int] = {}

    def timing(self, name: str):
        """计时装饰器"""

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    return await func(*args, **kwargs)
                finally:
                    elapsed = (time.time() - start) * 1000
                    self._timings.setdefault(name, []).append(elapsed)

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    return func(*args, **kwargs)
                finally:
                    elapsed = (time.time() - start) * 1000
                    self._timings.setdefault(name, []).append(elapsed)

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def increment(self, name: str, count: int = 1) -> None:
        """增加计数器"""
        self._counters[name] = self._counters.get(name, 0) + count

    def get_timing_stats(self, name: str) -> dict[str, float]:
        """获取计时统计"""
        timings = self._timings.get(name, [])
        if not timings:
            return {"count": 0, "avg_ms": 0, "min_ms": 0, "max_ms": 0, "total_ms": 0}

        return {
            "count": len(timings),
            "avg_ms": sum(timings) / len(timings),
            "min_ms": min(timings),
            "max_ms": max(timings),
            "total_ms": sum(timings),
        }

    def get_all_stats(self) -> dict[str, Any]:
        """获取所有统计"""
        return {
            "timings": {name: self.get_timing_stats(name) for name in self._timings},
            "counters": dict(self._counters),
        }

    def reset(self) -> None:
        """重置统计"""
        self._timings.clear()
        self._counters.clear()


# 全局性能监控器
_global_monitor: PerformanceMonitor | None = None


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor
