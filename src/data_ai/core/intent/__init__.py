"""
DATA-AI 意图识别系统

提供用户查询的意图识别和智能路由能力。
"""

from .recognizer import Intent, IntentContext, IntentRecognizer, IntentType
from .router import IntentRouter, RouteResult, RouteStrategy

__all__ = [
    "IntentRecognizer",
    "Intent",
    "IntentType",
    "IntentContext",
    "IntentRouter",
    "RouteResult",
    "RouteStrategy",
]
