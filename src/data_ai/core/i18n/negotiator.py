"""HTTP ``Accept-Language`` 协商。

支持 RFC 7231 简化子集，例如::

    Accept-Language: zh-CN,zh;q=0.9,en;q=0.8
    Accept-Language: en
    Accept-Language: *
"""

from __future__ import annotations

from .catalog import DEFAULT_LOCALE, SUPPORTED_LOCALES, Locale

# 主语言前缀 → Locale 映射（接受长 tag）
_LANG_PREFIX_MAP = {
    "en": Locale.EN,
    "zh": Locale.ZH,
}


def _parse_q_pairs(accept_language: str) -> list[tuple[str, float]]:
    """解析 Accept-Language 头为 ``(lang, q)`` 列表，按 q 降序。"""
    items: list[tuple[str, float]] = []
    if not accept_language:
        return items
    for part in accept_language.split(","):
        part = part.strip()
        if not part:
            continue
        if ";" in part:
            tag, *params = (p.strip() for p in part.split(";"))
            q = 1.0
            for p in params:
                if p.startswith("q="):
                    try:
                        q = float(p[2:])
                    except ValueError:
                        q = 1.0
        else:
            tag, q = part, 1.0
        if tag and tag != "*":
            items.append((tag.lower(), q))
        elif tag == "*":
            items.append(("*", q))
    items.sort(key=lambda x: x[1], reverse=True)
    return items


def negotiate_locale(accept_language: str | None) -> Locale:
    """根据 ``Accept-Language`` 协商出最匹配的 ``Locale``。"""
    pairs = _parse_q_pairs(accept_language or "")
    # 先按 q 顺序匹配完整 tag → 再按 prefix 匹配
    for tag, _q in pairs:
        if tag == "*":
            return DEFAULT_LOCALE
        for loc in SUPPORTED_LOCALES:
            if tag == loc.value:
                return loc
    for tag, _q in pairs:
        prefix = tag.split("-", 1)[0]
        if prefix in _LANG_PREFIX_MAP:
            return _LANG_PREFIX_MAP[prefix]
    return DEFAULT_LOCALE


__all__ = ["negotiate_locale"]
