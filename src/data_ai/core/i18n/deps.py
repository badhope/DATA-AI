"""FastAPI Dependency：从请求中提取 Locale。"""

from __future__ import annotations

from fastapi import Request

from .catalog import Locale
from .negotiator import negotiate_locale


def get_locale(request: Request) -> Locale:
    """FastAPI Depends。

    优先级：
    1. ``X-Locale`` 自定义头（前端 i18n 系统显式声明）
    2. ``Accept-Language`` HTTP 头
    3. 默认 ``en``
    """
    header = request.headers.get("x-locale")
    if header:
        from .catalog import _coerce_locale  # 局部 import 避免循环

        return _coerce_locale(header)
    return negotiate_locale(request.headers.get("accept-language"))


__all__ = ["get_locale"]
