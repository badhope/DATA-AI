"""
DATA-AI 后端 i18n 模块

提供：
- Locale 枚举与 SupportedLocales
- tr(key, locale, **kwargs) 翻译函数（带参数占位符与 fallback）
- negotiate_locale(accept_language) 解析 HTTP Accept-Language
- get_locale(request)  FastAPI Dependency

约定：
- 所有文案 key 使用点号命名空间，例如 ``api.error.not_found``
- 占位符使用 Python ``str.format`` 语法，例如 ``"Model {name} not found"``
- 如果键缺失，函数返回 ``[key]`` 形式便于在日志中识别
"""

from .catalog import DEFAULT_LOCALE, SUPPORTED_LOCALES, Locale, tr
from .deps import get_locale
from .negotiator import negotiate_locale

__all__ = [
    "Locale",
    "DEFAULT_LOCALE",
    "SUPPORTED_LOCALES",
    "tr",
    "negotiate_locale",
    "get_locale",
]
