"""
语言润色类型定义模块。

本模块定义了语言润色系统所需的所有核心类型和数据结构。

主要类型:
- PolishLevel: 润色等级枚举
- PolishStyle: 润色风格枚举
- PolishResult: 润色结果数据类
- TextChange: 文本变更数据类
- PolishConfig: 润色配置
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PolishLevel(Enum):
    """
    润色等级枚举类。

    定义不同深度的文本润色级别。

    Attributes:
        LIGHT: 轻微润色，仅修正明显错误
        MODERATE: 中等润色，改善表达和流畅度
        DEEP: 深度润色，全面重构和优化
    """

    LIGHT = "light"
    MODERATE = "moderate"
    DEEP = "deep"

    def get_intensity(self) -> float:
        """
        获取润色强度系数。

        Returns:
            润色强度系数（0.0-1.0）
        """
        intensity_map = {
            PolishLevel.LIGHT: 0.3,
            PolishLevel.MODERATE: 0.6,
            PolishLevel.DEEP: 1.0,
        }
        return intensity_map[self]

    def get_description(self) -> str:
        """
        获取润色等级描述。

        Returns:
            等级描述字符串
        """
        descriptions = {
            PolishLevel.LIGHT: "轻微润色：仅修正语法错误和明显的表达问题",
            PolishLevel.MODERATE: "中等润色：改善表达方式，提升文本流畅度",
            PolishLevel.DEEP: "深度润色：全面重构文本，优化结构和表达",
        }
        return descriptions[self]


class PolishStyle(Enum):
    """
    润色风格枚举类。

    定义不同的文本润色风格。

    Attributes:
        FORMAL: 正式风格，适用于商务、学术场景
        CASUAL: 随意风格，适用于日常交流、社交媒体
        TECHNICAL: 技术风格，适用于技术文档、说明文档
        CREATIVE: 创意风格，适用于创意写作、营销文案
    """

    FORMAL = "formal"
    CASUAL = "casual"
    TECHNICAL = "technical"
    CREATIVE = "creative"

    def get_prompt_modifier(self) -> str:
        """
        获取风格提示修饰词。

        Returns:
            风格修饰词字符串
        """
        modifiers = {
            PolishStyle.FORMAL: "使用正式、专业的语言风格，避免口语化表达",
            PolishStyle.CASUAL: "使用轻松、自然的语言风格，可以适当使用口语化表达",
            PolishStyle.TECHNICAL: "使用精确、严谨的技术语言，注重准确性和专业性",
            PolishStyle.CREATIVE: "使用富有创意和感染力的语言，可以运用修辞手法",
        }
        return modifiers[self]

    def get_example_patterns(self) -> list[str]:
        """
        获取风格示例模式。

        Returns:
            示例模式列表
        """
        patterns = {
            PolishStyle.FORMAL: [
                "请允许我向您说明...",
                "根据分析结果...",
                "综上所述...",
            ],
            PolishStyle.CASUAL: [
                "跟你说个事儿...",
                "简单来说就是...",
                "反正就是...",
            ],
            PolishStyle.TECHNICAL: [
                "从技术角度分析...",
                "具体实现方式为...",
                "系统架构包含...",
            ],
            PolishStyle.CREATIVE: [
                "想象一下...",
                "让我们一起探索...",
                "故事从这里开始...",
            ],
        }
        return patterns[self]


class ChangeType(Enum):
    """
    变更类型枚举类。

    定义文本变更的类型分类。

    Attributes:
        GRAMMAR: 语法修正
        STYLE: 风格调整
        CLARITY: 清晰度改进
        CONCISENESS: 简洁性优化
        VOCABULARY: 词汇替换
        STRUCTURE: 结构调整
        PUNCTUATION: 标点修正
    """

    GRAMMAR = "grammar"
    STYLE = "style"
    CLARITY = "clarity"
    CONCISENESS = "conciseness"
    VOCABULARY = "vocabulary"
    STRUCTURE = "structure"
    PUNCTUATION = "punctuation"

    def get_display_name(self) -> str:
        """获取变更类型的显示名称。"""
        names = {
            ChangeType.GRAMMAR: "语法修正",
            ChangeType.STYLE: "风格调整",
            ChangeType.CLARITY: "清晰度改进",
            ChangeType.CONCISENESS: "简洁性优化",
            ChangeType.VOCABULARY: "词汇替换",
            ChangeType.STRUCTURE: "结构调整",
            ChangeType.PUNCTUATION: "标点修正",
        }
        return names[self]


@dataclass
class TextChange:
    """
    文本变更数据类。

    表示文本中的单个变更，包含位置、原始内容、替换内容和变更原因。

    Attributes:
        position: 变更在原文中的位置（起始索引，结束索引）
        original: 原始文本
        replacement: 替换文本
        change_type: 变更类型
        reason: 变更原因说明
        confidence: 变更置信度（0.0-1.0）
        metadata: 附加元数据

    Example:
        >>> change = TextChange(
        ...     position=(10, 15),
        ...     original="很好看",
        ...     replacement="非常漂亮",
        ...     change_type=ChangeType.VOCABULARY,
        ...     reason="提升表达正式度",
        ...     confidence=0.9,
        ... )
    """

    position: tuple[int, int]
    original: str
    replacement: str
    change_type: ChangeType
    reason: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """初始化后验证。"""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"置信度必须在 0.0-1.0 之间，当前值: {self.confidence}")

        if self.position[0] < 0 or self.position[1] < self.position[0]:
            raise ValueError(f"无效的位置范围: {self.position}")

    @property
    def length_diff(self) -> int:
        """
        计算文本长度变化。

        Returns:
            长度变化值（正数表示变长，负数表示变短）
        """
        return len(self.replacement) - len(self.original)

    @property
    def is_deletion(self) -> bool:
        """检查是否为删除操作。"""
        return len(self.replacement) == 0 and len(self.original) > 0

    @property
    def is_insertion(self) -> bool:
        """检查是否为插入操作。"""
        return len(self.original) == 0 and len(self.replacement) > 0

    @property
    def is_replacement(self) -> bool:
        """检查是否为替换操作。"""
        return len(self.original) > 0 and len(self.replacement) > 0

    def to_dict(self) -> dict[str, Any]:
        """将变更转换为字典格式。"""
        return {
            "position": self.position,
            "original": self.original,
            "replacement": self.replacement,
            "change_type": self.change_type.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "length_diff": self.length_diff,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextChange:
        """从字典创建变更实例。"""
        if isinstance(data.get("change_type"), str):
            data["change_type"] = ChangeType(data["change_type"])
        return cls(**data)


@dataclass
class PolishScore:
    """
    润色评分数据类。

    表示文本在不同维度的评分。

    Attributes:
        grammar: 语法评分（0-100）
        clarity: 清晰度评分（0-100）
        conciseness: 简洁性评分（0-100）
        style: 风格一致性评分（0-100）
        readability: 可读性评分（0-100）
        overall: 综合评分（0-100）
    """

    grammar: float = 0.0
    clarity: float = 0.0
    conciseness: float = 0.0
    style: float = 0.0
    readability: float = 0.0
    overall: float = 0.0

    def __post_init__(self) -> None:
        """初始化后计算综合评分。"""
        if self.overall == 0.0:
            self.overall = self._calculate_overall()

    def _calculate_overall(self) -> float:
        """计算加权综合评分。"""
        weights = {
            "grammar": 0.25,
            "clarity": 0.25,
            "conciseness": 0.20,
            "style": 0.15,
            "readability": 0.15,
        }
        return sum(getattr(self, k) * v for k, v in weights.items())

    def get_grade(self) -> str:
        """
        获取评分等级。

        Returns:
            等级字符串（A/B/C/D/E）
        """
        if self.overall >= 90:
            return "A"
        elif self.overall >= 80:
            return "B"
        elif self.overall >= 70:
            return "C"
        elif self.overall >= 60:
            return "D"
        else:
            return "E"

    def to_dict(self) -> dict[str, Any]:
        """将评分转换为字典格式。"""
        return {
            "grammar": round(self.grammar, 2),
            "clarity": round(self.clarity, 2),
            "conciseness": round(self.conciseness, 2),
            "style": round(self.style, 2),
            "readability": round(self.readability, 2),
            "overall": round(self.overall, 2),
            "grade": self.get_grade(),
        }


@dataclass
class PolishResult:
    """
    润色结果数据类。

    表示完整的润色结果，包含原文、润色后文本、变更列表和评分。

    Attributes:
        original: 原始文本
        polished: 润色后文本
        changes: 变更列表
        score: 润色评分
        level: 润色等级
        style: 润色风格
        processing_time: 处理时间（秒）
        timestamp: 时间戳
        metadata: 附加元数据

    Example:
        >>> result = PolishResult(
        ...     original="这个很好看",
        ...     polished="这件物品外观非常精美",
        ...     changes=[TextChange(...)],
        ...     score=PolishScore(grammar=95, clarity=90, ...),
        ...     level=PolishLevel.MODERATE,
        ...     style=PolishStyle.FORMAL,
        ... )
    """

    original: str
    polished: str
    changes: list[TextChange] = field(default_factory=list)
    score: PolishScore = field(default_factory=PolishScore)
    level: PolishLevel = PolishLevel.MODERATE
    style: PolishStyle = PolishStyle.FORMAL
    processing_time: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def change_count(self) -> int:
        """获取变更数量。"""
        return len(self.changes)

    @property
    def improvement_ratio(self) -> float:
        """
        计算改进比例。

        Returns:
            改进比例（0.0-1.0）
        """
        if not self.original:
            return 0.0

        # 基于变更数量和文本长度计算改进比例
        change_chars = sum(max(len(c.original), len(c.replacement)) for c in self.changes)
        return min(1.0, change_chars / len(self.original))

    def get_changes_by_type(self, change_type: ChangeType) -> list[TextChange]:
        """
        获取指定类型的变更。

        Args:
            change_type: 变更类型

        Returns:
            该类型的变更列表
        """
        return [c for c in self.changes if c.change_type == change_type]

    def get_summary(self) -> dict[str, Any]:
        """
        获取结果摘要。

        Returns:
            摘要信息字典
        """
        type_counts = {}
        for change in self.changes:
            type_name = change.change_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1

        return {
            "original_length": len(self.original),
            "polished_length": len(self.polished),
            "change_count": self.change_count,
            "change_types": type_counts,
            "score": self.score.to_dict(),
            "level": self.level.value,
            "style": self.style.value,
            "processing_time": self.processing_time,
        }

    def to_dict(self) -> dict[str, Any]:
        """将结果转换为字典格式。"""
        return {
            "original": self.original,
            "polished": self.polished,
            "changes": [c.to_dict() for c in self.changes],
            "score": self.score.to_dict(),
            "level": self.level.value,
            "style": self.style.value,
            "processing_time": self.processing_time,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "summary": self.get_summary(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolishResult:
        """从字典创建结果实例。"""
        if isinstance(data.get("level"), str):
            data["level"] = PolishLevel(data["level"])
        if isinstance(data.get("style"), str):
            data["style"] = PolishStyle(data["style"])
        if isinstance(data.get("changes"), list):
            data["changes"] = [TextChange.from_dict(c) if isinstance(c, dict) else c for c in data["changes"]]
        if isinstance(data.get("score"), dict):
            data["score"] = PolishScore(**data["score"])
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class PolishConfig:
    """
    润色配置数据类。

    配置润色器的行为参数。

    Attributes:
        level: 润色等级
        style: 润色风格
        preserve_formatting: 是否保留格式
        max_changes: 最大变更数量
        min_confidence: 最小置信度阈值
        enabled_rules: 启用的规则列表
        disabled_rules: 禁用的规则列表
        custom_rules: 自定义规则配置
        language: 目标语言
        timeout: 超时时间（秒）
    """

    level: PolishLevel = PolishLevel.MODERATE
    style: PolishStyle = PolishStyle.FORMAL
    preserve_formatting: bool = True
    max_changes: int = 100
    min_confidence: float = 0.5
    enabled_rules: list[str] = field(default_factory=list)
    disabled_rules: list[str] = field(default_factory=list)
    custom_rules: dict[str, Any] = field(default_factory=dict)
    language: str = "zh"
    timeout: float = 30.0

    def __post_init__(self) -> None:
        """初始化后验证。"""
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence 必须在 0.0-1.0 之间，当前值: {self.min_confidence}")

        if self.max_changes < 1:
            raise ValueError(f"max_changes 必须大于 0，当前值: {self.max_changes}")

    def to_dict(self) -> dict[str, Any]:
        """将配置转换为字典格式。"""
        return {
            "level": self.level.value,
            "style": self.style.value,
            "preserve_formatting": self.preserve_formatting,
            "max_changes": self.max_changes,
            "min_confidence": self.min_confidence,
            "enabled_rules": self.enabled_rules,
            "disabled_rules": self.disabled_rules,
            "custom_rules": self.custom_rules,
            "language": self.language,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolishConfig:
        """从字典创建配置实例。"""
        if isinstance(data.get("level"), str):
            data["level"] = PolishLevel(data["level"])
        if isinstance(data.get("style"), str):
            data["style"] = PolishStyle(data["style"])
        return cls(**data)


@dataclass
class DiffSegment:
    """
    差异片段数据类。

    表示文本对比中的单个差异片段。

    Attributes:
        type: 片段类型（equal, delete, insert, replace）
        content: 片段内容
        original_start: 原文起始位置
        original_end: 原文结束位置
        polished_start: 润色后起始位置
        polished_end: 润色后结束位置
    """

    type: str  # equal, delete, insert, replace
    content: str
    original_start: int = 0
    original_end: int = 0
    polished_start: int = 0
    polished_end: int = 0

    @property
    def is_change(self) -> bool:
        """检查是否为变更片段。"""
        return self.type in ("delete", "insert", "replace")

    def to_dict(self) -> dict[str, Any]:
        """将片段转换为字典格式。"""
        return {
            "type": self.type,
            "content": self.content,
            "original_start": self.original_start,
            "original_end": self.original_end,
            "polished_start": self.polished_start,
            "polished_end": self.polished_end,
        }


class PolishException(Exception):
    """
    润色处理异常。

    用于表示润色处理过程中发生的各种错误。

    Attributes:
        message: 错误消息
        code: 错误代码
        details: 详细错误信息
    """

    def __init__(
        self,
        message: str,
        code: str = "POLISH_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        初始化润色异常。

        Args:
            message: 错误消息
            code: 错误代码
            details: 详细错误信息
        """
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """将异常转换为字典格式。"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# 类型别名
TextProcessor = callable  # type: ignore
"""文本处理函数类型。"""

ChangeFilter = callable  # type: ignore
"""变更过滤函数类型。"""

ResultCallback = callable  # type: ignore
"""结果回调函数类型。"""
