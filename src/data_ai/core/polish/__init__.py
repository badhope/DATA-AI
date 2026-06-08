"""
语言润色模块。

本模块提供完整的文本润色功能，支持基于规则和基于 LLM 的润色方式。

主要组件:
- 类型定义: PolishLevel, PolishStyle, PolishResult, TextChange
- 润色器: TextPolisher, LLMPolisher
- 规则引擎: RuleEngine, GrammarRule, StyleRule, ClarityRule, ConcisenessRule
- 差异对比: TextDiffer, DiffFormatter

快速开始:
    >>> from data_ai.core.polish import TextPolisher, PolishLevel, PolishStyle
    >>>
    >>> # 创建润色器
    >>> polisher = TextPolisher()
    >>>
    >>> # 润色文本
    >>> result = polisher.polish(
    ...     "这个很好看",
    ...     level=PolishLevel.MODERATE,
    ...     style=PolishStyle.FORMAL,
    ... )
    >>>
    >>> print(result.polished)
    这件物品外观非常精美

使用 LLM 润色:
    >>> from data_ai.core.polish import LLMPolisher, LLMPolisherBuilder
    >>>
    >>> polisher = (
    ...     LLMPolisherBuilder()
    ...     .with_openai_backend(api_key="your-api-key")
    ...     .with_model("gpt-4")
    ...     .build()
    ... )
    >>>
    >>> result = await polisher.polish_async("你的文本")

使用构建器:
    >>> from data_ai.core.polish import PolisherBuilder
    >>>
    >>> polisher = (
    ...     PolisherBuilder()
    ...     .with_level(PolishLevel.DEEP)
    ...     .with_style(PolishStyle.FORMAL)
    ...     .with_min_confidence(0.7)
    ...     .build()
    ... )
"""

from __future__ import annotations

# 差异对比
from .diff import (
    DiffApplier,
    DiffFormat,
    DiffFormatter,
    DiffOptions,
    DiffResult,
    TextDiffer,
)

# LLM 润色器
from .llm_polisher import (
    AnthropicBackend,
    LLMBackend,
    LLMConfig,
    LLMPolisher,
    LLMPolisherBuilder,
    MockBackend,
    OpenAIBackend,
    PromptTemplate,
    PromptTemplates,
    polish_with_llm,
)

# 润色器
from .polisher import (
    BasePolisher,
    PolisherBuilder,
    PolisherRegistry,
    TextPolisher,
    polish_text,
    polish_text_async,
)

# 规则相关
from .rules import (
    ClarityRule,
    ConcisenessRule,
    # 具体规则
    GrammarRule,
    # 基类
    PolishRule,
    PunctuationRule,
    RuleConfig,
    # 规则引擎
    RuleEngine,
    RuleMatch,
    StyleRule,
    VocabularyRule,
)

# 类型定义
from .types import (
    ChangeFilter,
    ChangeType,
    DiffSegment,
    PolishConfig,
    # 异常
    PolishException,
    # 枚举类型
    PolishLevel,
    PolishResult,
    PolishScore,
    PolishStyle,
    ResultCallback,
    # 数据类
    TextChange,
    # 类型别名
    TextProcessor,
)

__all__ = [
    # 类型定义
    "PolishLevel",
    "PolishStyle",
    "ChangeType",
    "DiffFormat",
    "TextChange",
    "PolishResult",
    "PolishScore",
    "PolishConfig",
    "DiffSegment",
    "PolishException",
    "TextProcessor",
    "ChangeFilter",
    "ResultCallback",
    # 规则
    "PolishRule",
    "RuleMatch",
    "RuleConfig",
    "GrammarRule",
    "StyleRule",
    "ClarityRule",
    "ConcisenessRule",
    "PunctuationRule",
    "VocabularyRule",
    "RuleEngine",
    # 差异对比
    "TextDiffer",
    "DiffFormatter",
    "DiffApplier",
    "DiffResult",
    "DiffOptions",
    # 润色器
    "BasePolisher",
    "TextPolisher",
    "PolisherBuilder",
    "PolisherRegistry",
    "polish_text",
    "polish_text_async",
    # LLM 润色器
    "LLMPolisher",
    "LLMPolisherBuilder",
    "LLMBackend",
    "LLMConfig",
    "PromptTemplate",
    "PromptTemplates",
    "OpenAIBackend",
    "AnthropicBackend",
    "MockBackend",
    "polish_with_llm",
]

__version__ = "1.0.0"
__author__ = "DATA-AI Team"
