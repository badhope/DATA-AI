"""
DATA-AI 预置 Agent 列表

通过 REGISTERED_PRESETS 字典统一注册,可通过角色名加载。
"""

from .customer_service import PRESET as CUSTOMER_SERVICE
from .finance_analyst import PRESET as FINANCE_ANALYST
from .novel_writer import PRESET as NOVEL_WRITER
from .secretary import PRESET as SECRETARY

REGISTERED_PRESETS = {
    "customer_service": CUSTOMER_SERVICE,
    "finance_analyst": FINANCE_ANALYST,
    "secretary": SECRETARY,
    "novel_writer": NOVEL_WRITER,
}


def list_presets() -> list[dict]:
    """列出所有预置 agent(简要)"""
    return [
        {
            "role": p["role"],
            "name": p["name"],
            "description": p["description"],
            "tools_count": len(p["tools"]),
        }
        for p in REGISTERED_PRESETS.values()
    ]


def get_preset(role: str) -> dict | None:
    """按角色名获取预设"""
    return REGISTERED_PRESETS.get(role)


__all__ = [
    "CUSTOMER_SERVICE",
    "FINANCE_ANALYST",
    "SECRETARY",
    "NOVEL_WRITER",
    "REGISTERED_PRESETS",
    "list_presets",
    "get_preset",
]
