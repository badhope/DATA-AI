"""
语言润色规则模块。

本模块定义了各种润色规则和规则引擎，用于检测和修正文本问题。

主要组件:
- PolishRule: 润色规则基类
- GrammarRule: 语法规则
- StyleRule: 风格规则
- ClarityRule: 清晰度规则
- ConcisenessRule: 简洁性规则
- RuleEngine: 规则引擎
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from .types import (
    ChangeType,
    PolishException,
    PolishLevel,
    PolishStyle,
    TextChange,
)


@dataclass
class RuleMatch:
    """
    规则匹配结果。

    表示规则在文本中检测到的一个匹配项。

    Attributes:
        position: 匹配位置（起始索引，结束索引）
        original: 原始文本
        suggestion: 建议替换文本
        reason: 匹配原因说明
        confidence: 置信度（0.0-1.0）
        metadata: 附加元数据
    """

    position: tuple[int, int]
    original: str
    suggestion: str
    reason: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_text_change(self, change_type: ChangeType) -> TextChange:
        """
        转换为文本变更对象。

        Args:
            change_type: 变更类型

        Returns:
            TextChange 实例
        """
        return TextChange(
            position=self.position,
            original=self.original,
            replacement=self.suggestion,
            change_type=change_type,
            reason=self.reason,
            confidence=self.confidence,
            metadata=self.metadata,
        )


@dataclass
class RuleConfig:
    """
    规则配置。

    Attributes:
        enabled: 是否启用
        priority: 优先级（数值越大优先级越高）
        min_confidence: 最小置信度阈值
        max_matches: 最大匹配数量
        custom_patterns: 自定义模式列表
        exceptions: 例外模式列表
    """

    enabled: bool = True
    priority: int = 0
    min_confidence: float = 0.5
    max_matches: int = 100
    custom_patterns: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)


class PolishRule(ABC):
    """
    润色规则基类。

    所有润色规则都应继承此类并实现 apply 方法。

    Attributes:
        name: 规则名称
        description: 规则描述
        change_type: 变更类型
        config: 规则配置
    """

    def __init__(
        self,
        name: str,
        description: str,
        change_type: ChangeType,
        config: RuleConfig | None = None,
    ) -> None:
        """
        初始化润色规则。

        Args:
            name: 规则名称
            description: 规则描述
            change_type: 变更类型
            config: 规则配置
        """
        self.name = name
        self.description = description
        self.change_type = change_type
        self.config = config or RuleConfig()

    @abstractmethod
    def apply(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> list[RuleMatch]:
        """
        应用规则到文本。

        Args:
            text: 待润色文本
            level: 润色等级
            style: 润色风格

        Returns:
            规则匹配列表
        """
        pass

    def is_enabled(self) -> bool:
        """检查规则是否启用。"""
        return self.config.enabled

    def filter_matches(
        self,
        matches: list[RuleMatch],
        min_confidence: float | None = None,
    ) -> list[RuleMatch]:
        """
        过滤匹配结果。

        Args:
            matches: 匹配列表
            min_confidence: 最小置信度

        Returns:
            过滤后的匹配列表
        """
        threshold = min_confidence or self.config.min_confidence
        filtered = [m for m in matches if m.confidence >= threshold]
        return filtered[: self.config.max_matches]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


class GrammarRule(PolishRule):
    """
    语法规则。

    检测和修正语法错误，包括：
    - 标点符号错误
    - 错别字
    - 语法结构问题
    """

    # 常见中文语法错误模式
    GRAMMAR_PATTERNS = [
        # 重复词语
        (r"(.{1,5})\1{1,}", r"\1", "重复词语", 0.9),
        # 错误的"的、地、得"用法
        (r"(\w+)的(\w+)(?:了|着|过)", r"\1地\2", "的地得用法错误", 0.7),
        # 双重否定
        (r"没有(\w+)不(\w+)", r"\1\2", "双重否定，建议简化", 0.6),
        # 标点后缺少空格（英文）
        (r"([,.:;!?])([A-Za-z])", r"\1 \2", "标点后缺少空格", 0.8),
    ]

    # 常见错别字
    COMMON_TYPOS = {
        "的地得": {"的的": "地", "地的": "得", "得的": "地"},
        "形近字": {"己经": "已经", "在次": "再次", "做作": "做作"},
        "同音字": {"必须": "必需", "反应": "反映", "权力": "权利"},
    }

    def __init__(self, config: RuleConfig | None = None) -> None:
        super().__init__(
            name="grammar",
            description="检测和修正语法错误",
            change_type=ChangeType.GRAMMAR,
            config=config,
        )
        self._patterns = self._compile_patterns()

    def _compile_patterns(self) -> list[tuple[re.Pattern, str, str, float]]:
        """编译正则表达式模式。"""
        patterns = []
        for pattern, replacement, reason, confidence in self.GRAMMAR_PATTERNS:
            compiled = re.compile(pattern)
            patterns.append((compiled, replacement, reason, confidence))
        return patterns

    def apply(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> list[RuleMatch]:
        """应用语法规则。"""
        matches = []

        # 应用正则模式
        for pattern, replacement, reason, confidence in self._patterns:
            for match in pattern.finditer(text):
                original = match.group(0)
                suggested = match.expand(replacement)

                if original != suggested:
                    matches.append(
                        RuleMatch(
                            position=(match.start(), match.end()),
                            original=original,
                            suggestion=suggested,
                            reason=reason,
                            confidence=confidence * level.get_intensity(),
                        )
                    )

        # 检查错别字
        matches.extend(self._check_typos(text, level))

        return self.filter_matches(matches)

    def _check_typos(
        self,
        text: str,
        level: PolishLevel,
    ) -> list[RuleMatch]:
        """检查常见错别字。"""
        matches = []

        for category, typos in self.COMMON_TYPOS.items():
            for wrong, correct in typos.items():
                start = 0
                while True:
                    pos = text.find(wrong, start)
                    if pos == -1:
                        break
                    matches.append(
                        RuleMatch(
                            position=(pos, pos + len(wrong)),
                            original=wrong,
                            suggestion=correct,
                            reason=f"错别字修正（{category}）",
                            confidence=0.85 * level.get_intensity(),
                        )
                    )
                    start = pos + 1

        return matches


class StyleRule(PolishRule):
    """
    风格规则。

    根据目标风格调整文本表达，包括：
    - 口语化/正式化转换
    - 词汇风格调整
    - 语气调整
    """

    # 口语化表达 -> 正式表达
    CASUAL_TO_FORMAL = {
        "挺好的": "良好",
        "差不多": "基本相同",
        "弄": "处理",
        "搞": "进行",
        "说": "表示",
        "看": "查看",
        "想": "认为",
        "觉得": "认为",
        "反正": "总之",
        "其实": "实际上",
        "就是": "即",
        "然后": "随后",
        "所以说": "因此",
        "不管怎样": "无论如何",
    }

    # 正式表达 -> 口语化表达
    FORMAL_TO_CASUAL = {
        "良好": "挺好的",
        "基本相同": "差不多",
        "处理": "弄",
        "进行": "搞",
        "表示": "说",
        "查看": "看",
        "认为": "觉得",
        "实际上": "其实",
        "即": "就是",
        "随后": "然后",
        "因此": "所以说",
        "无论如何": "不管怎样",
    }

    # 技术术语
    TECHNICAL_TERMS = {
        "做": "执行",
        "用": "使用",
        "改": "修改",
        "查": "查询",
        "删": "删除",
        "加": "添加",
        "弄好": "配置完成",
        "搞定": "处理完毕",
    }

    def __init__(self, config: RuleConfig | None = None) -> None:
        super().__init__(
            name="style",
            description="调整文本风格",
            change_type=ChangeType.STYLE,
            config=config,
        )

    def apply(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> list[RuleMatch]:
        """应用风格规则。"""
        matches = []

        if style == PolishStyle.FORMAL:
            matches = self._apply_formal_style(text, level)
        elif style == PolishStyle.CASUAL:
            matches = self._apply_casual_style(text, level)
        elif style == PolishStyle.TECHNICAL:
            matches = self._apply_technical_style(text, level)

        return self.filter_matches(matches)

    def _apply_formal_style(
        self,
        text: str,
        level: PolishLevel,
    ) -> list[RuleMatch]:
        """应用正式风格。"""
        matches = []
        intensity = level.get_intensity()

        for casual, formal in self.CASUAL_TO_FORMAL.items():
            start = 0
            while True:
                pos = text.find(casual, start)
                if pos == -1:
                    break
                matches.append(
                    RuleMatch(
                        position=(pos, pos + len(casual)),
                        original=casual,
                        suggestion=formal,
                        reason="转换为正式表达",
                        confidence=0.7 * intensity,
                    )
                )
                start = pos + 1

        return matches

    def _apply_casual_style(
        self,
        text: str,
        level: PolishLevel,
    ) -> list[RuleMatch]:
        """应用随意风格。"""
        matches = []
        intensity = level.get_intensity()

        for formal, casual in self.FORMAL_TO_CASUAL.items():
            start = 0
            while True:
                pos = text.find(formal, start)
                if pos == -1:
                    break
                matches.append(
                    RuleMatch(
                        position=(pos, pos + len(formal)),
                        original=formal,
                        suggestion=casual,
                        reason="转换为口语化表达",
                        confidence=0.6 * intensity,
                    )
                )
                start = pos + 1

        return matches

    def _apply_technical_style(
        self,
        text: str,
        level: PolishLevel,
    ) -> list[RuleMatch]:
        """应用技术风格。"""
        matches = []
        intensity = level.get_intensity()

        for common, technical in self.TECHNICAL_TERMS.items():
            start = 0
            while True:
                pos = text.find(common, start)
                if pos == -1:
                    break
                matches.append(
                    RuleMatch(
                        position=(pos, pos + len(common)),
                        original=common,
                        suggestion=technical,
                        reason="转换为技术术语",
                        confidence=0.75 * intensity,
                    )
                )
                start = pos + 1

        return matches


class ClarityRule(PolishRule):
    """
    清晰度规则。

    提升文本清晰度，包括：
    - 消除歧义表达
    - 简化复杂句式
    - 明确指代关系
    """

    # 模糊表达 -> 清晰表达
    VAGUE_EXPRESSIONS = {
        "一些": "若干",
        "很多东西": "多项内容",
        "这个": "该",
        "那个": "上述",
        "有点": "略微",
        "比较": "相对",
        "大概": "大约",
        "可能": "可能",
        "应该": "应当",
        "差不多是": "接近于",
    }

    # 冗余表达模式
    REDUNDANT_PATTERNS = [
        (r"(.+?)的原因是因为", r"\1的原因是", "消除冗余表达"),
        (r"(.+?)的结果是结果", r"\1的结果是", "消除冗余表达"),
        (r"首先首先", r"首先", "消除重复"),
        (r"然后然后", r"然后", "消除重复"),
        (r"最后最后", r"最后", "消除重复"),
    ]

    def __init__(self, config: RuleConfig | None = None) -> None:
        super().__init__(
            name="clarity",
            description="提升文本清晰度",
            change_type=ChangeType.CLARITY,
            config=config,
        )
        self._patterns = [(re.compile(p), r, desc) for p, r, desc in self.REDUNDANT_PATTERNS]

    def apply(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> list[RuleMatch]:
        """应用清晰度规则。"""
        matches = []
        intensity = level.get_intensity()

        # 检查模糊表达
        for vague, clear in self.VAGUE_EXPRESSIONS.items():
            start = 0
            while True:
                pos = text.find(vague, start)
                if pos == -1:
                    break
                matches.append(
                    RuleMatch(
                        position=(pos, pos + len(vague)),
                        original=vague,
                        suggestion=clear,
                        reason="使用更清晰的表达",
                        confidence=0.65 * intensity,
                    )
                )
                start = pos + 1

        # 检查冗余表达
        for pattern, replacement, reason in self._patterns:
            for match in pattern.finditer(text):
                original = match.group(0)
                suggested = match.expand(replacement)
                if original != suggested:
                    matches.append(
                        RuleMatch(
                            position=(match.start(), match.end()),
                            original=original,
                            suggestion=suggested,
                            reason=reason,
                            confidence=0.8 * intensity,
                        )
                    )

        return self.filter_matches(matches)


class ConcisenessRule(PolishRule):
    """
    简洁性规则。

    提升文本简洁性，包括：
    - 删除冗余词语
    - 简化表达
    - 合并相似内容
    """

    # 可删除的冗余词
    REDUNDANT_WORDS = [
        "其实",
        "实际上",
        "事实上",  # 常可省略
        "然后",
        "接着",  # 过度使用时
        "就是",
        "也就是",  # 常可省略
        "的话",  # 口语冗余
        "进行",  # 动词冗余
    ]

    # 冗余短语模式
    WORDY_PHRASES = {
        "在...方面": "...方面",
        "对...进行": "...",
        "做出...决定": "决定...",
        "进行...处理": "处理...",
        "开展...工作": "...工作",
        "实施...行动": "...行动",
        "加以...改进": "改进...",
        "予以...支持": "支持...",
        "给予...帮助": "帮助...",
    }

    # 常见简化
    SIMPLIFICATIONS = {
        "能够": "能",
        "可以": "可",
        "需要": "需",
        "应该": "应",
        "已经": "已",
        "正在": "正",
        "将要": "将",
        "关于": "关于",
        "由于": "因",
        "但是": "但",
        "并且": "并",
        "或者": "或",
    }

    def __init__(self, config: RuleConfig | None = None) -> None:
        super().__init__(
            name="conciseness",
            description="提升文本简洁性",
            change_type=ChangeType.CONCISENESS,
            config=config,
        )

    def apply(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> list[RuleMatch]:
        """应用简洁性规则。"""
        matches = []
        intensity = level.get_intensity()

        # 深度润色时才考虑删除冗余词
        if level == PolishLevel.DEEP:
            matches.extend(self._find_redundant_words(text, intensity))

        # 应用简化
        matches.extend(self._apply_simplifications(text, intensity, style))

        return self.filter_matches(matches)

    def _find_redundant_words(
        self,
        text: str,
        intensity: float,
    ) -> list[RuleMatch]:
        """查找可删除的冗余词。"""
        matches = []

        for word in self.REDUNDANT_WORDS:
            start = 0
            while True:
                pos = text.find(word, start)
                if pos == -1:
                    break

                # 检查上下文，避免过度删除
                context_start = max(0, pos - 10)
                context_end = min(len(text), pos + len(word) + 10)
                context = text[context_start:context_end]

                # 简单判断：如果上下文有其他连接词，可以删除
                if self._is_safe_to_remove(word, context):
                    matches.append(
                        RuleMatch(
                            position=(pos, pos + len(word)),
                            original=word,
                            suggestion="",
                            reason="删除冗余词语",
                            confidence=0.5 * intensity,
                        )
                    )
                start = pos + 1

        return matches

    def _is_safe_to_remove(self, word: str, context: str) -> bool:
        """判断是否安全删除。"""
        # 简单规则：句首的连接词通常不应删除
        if context.startswith(word):
            return False
        return True

    def _apply_simplifications(
        self,
        text: str,
        intensity: float,
        style: PolishStyle,
    ) -> list[RuleMatch]:
        """应用简化规则。"""
        matches = []

        # 正式风格不应用简化
        if style == PolishStyle.FORMAL:
            return matches

        for long_form, short_form in self.SIMPLIFICATIONS.items():
            start = 0
            while True:
                pos = text.find(long_form, start)
                if pos == -1:
                    break
                matches.append(
                    RuleMatch(
                        position=(pos, pos + len(long_form)),
                        original=long_form,
                        suggestion=short_form,
                        reason="简化表达",
                        confidence=0.6 * intensity,
                    )
                )
                start = pos + 1

        return matches


class PunctuationRule(PolishRule):
    """
    标点符号规则。

    规范标点符号使用，包括：
    - 中英文标点转换
    - 标点符号规范化
    - 标点使用一致性
    """

    # 英文标点 -> 中文标点
    EN_TO_CN_PUNCTUATION = {
        ",": "，",
        "。": "。",
        "?": "？",
        "!": "！",
        ":": "：",
        ";": "；",
        "(": "（",
        ")": "）",
        "[": "【",
        "]": "】",
    }

    # 重复标点模式
    REPEATED_PUNCTUATION = [
        (r"([，。！？；：])\1+", r"\1", "消除重复标点"),
        (r"\.{2,}", "。", "规范化省略号"),
        (r"—{2,}", "——", "规范化破折号"),
    ]

    def __init__(self, config: RuleConfig | None = None) -> None:
        super().__init__(
            name="punctuation",
            description="规范标点符号使用",
            change_type=ChangeType.PUNCTUATION,
            config=config,
        )
        self._patterns = [(re.compile(p), r, desc) for p, r, desc in self.REPEATED_PUNCTUATION]

    def apply(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> list[RuleMatch]:
        """应用标点规则。"""
        matches = []
        intensity = level.get_intensity()

        # 检查标点转换
        matches.extend(self._check_punctuation_conversion(text, intensity))

        # 检查重复标点
        matches.extend(self._check_repeated_punctuation(text, intensity))

        return self.filter_matches(matches)

    def _check_punctuation_conversion(
        self,
        text: str,
        intensity: float,
    ) -> list[RuleMatch]:
        """检查标点转换。"""
        matches = []

        # 判断是否为中文文本
        chinese_ratio = self._get_chinese_ratio(text)

        if chinese_ratio > 0.5:  # 中文为主，转换英文标点
            for en_punct, cn_punct in self.EN_TO_CN_PUNCTUATION.items():
                start = 0
                while True:
                    pos = text.find(en_punct, start)
                    if pos == -1:
                        break

                    # 检查周围是否为中文
                    if self._is_in_chinese_context(text, pos):
                        matches.append(
                            RuleMatch(
                                position=(pos, pos + 1),
                                original=en_punct,
                                suggestion=cn_punct,
                                reason="转换为中文标点",
                                confidence=0.8 * intensity,
                            )
                        )
                    start = pos + 1

        return matches

    def _check_repeated_punctuation(
        self,
        text: str,
        intensity: float,
    ) -> list[RuleMatch]:
        """检查重复标点。"""
        matches = []

        for pattern, replacement, reason in self._patterns:
            for match in pattern.finditer(text):
                original = match.group(0)
                suggested = match.expand(replacement)
                if original != suggested:
                    matches.append(
                        RuleMatch(
                            position=(match.start(), match.end()),
                            original=original,
                            suggestion=suggested,
                            reason=reason,
                            confidence=0.9 * intensity,
                        )
                    )

        return matches

    def _get_chinese_ratio(self, text: str) -> float:
        """计算中文字符比例。"""
        if not text:
            return 0.0
        chinese_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        return chinese_count / len(text)

    def _is_in_chinese_context(self, text: str, pos: int) -> bool:
        """判断位置是否在中文上下文中。"""
        # 检查前后字符
        before = text[max(0, pos - 1) : pos]
        after = text[pos + 1 : pos + 2]

        for char in before + after:
            if "\u4e00" <= char <= "\u9fff":
                return True
        return False


class VocabularyRule(PolishRule):
    """
    词汇规则。

    优化词汇使用，包括：
    - 词汇替换
    - 避免重复用词
    - 提升词汇丰富度
    """

    # 同义词替换
    SYNONYMS = {
        "好": ["优秀", "出色", "良好", "优异"],
        "坏": ["不良", "糟糕", "欠佳", "差"],
        "大": ["巨大", "庞大", "宏大", "重大"],
        "小": ["微小", "细小", "渺小", "微小"],
        "多": ["众多", "大量", "繁多", "丰富"],
        "少": ["稀少", "罕见", "稀缺", "有限"],
        "快": ["迅速", "快速", "敏捷", "飞快"],
        "慢": ["缓慢", "迟缓", "徐徐", "渐渐"],
        "新": ["新颖", "创新", "崭新", "最新"],
        "旧": ["陈旧", "过时", "老旧", "传统"],
    }

    # 高频词替换（避免过度使用）
    HIGH_FREQUENCY_WORDS = {
        "非常": ["极其", "十分", "相当", "格外"],
        "很多": ["众多", "大量", "诸多", "许多"],
        "一些": ["若干", "部分", "某些", "少量"],
        "这样": ["如此", "这般", "如此这般"],
        "那样": ["那般", "如此"],
    }

    def __init__(self, config: RuleConfig | None = None) -> None:
        super().__init__(
            name="vocabulary",
            description="优化词汇使用",
            change_type=ChangeType.VOCABULARY,
            config=config,
        )

    def apply(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> list[RuleMatch]:
        """应用词汇规则。"""
        matches = []
        intensity = level.get_intensity()

        # 检查重复用词
        matches.extend(self._check_repeated_words(text, intensity))

        # 检查高频词
        matches.extend(self._check_high_frequency_words(text, intensity, style))

        return self.filter_matches(matches)

    def _check_repeated_words(
        self,
        text: str,
        intensity: float,
    ) -> list[RuleMatch]:
        """检查重复用词。"""
        matches = []
        word_positions: dict[str, list[int]] = {}

        # 简单分词（按标点和空格）
        import re

        re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text)

        # 记录位置
        for match in re.finditer(r"[\u4e00-\u9fff]+|[a-zA-Z]+", text):
            word = match.group()
            if len(word) >= 2:  # 只检查2字以上的词
                if word not in word_positions:
                    word_positions[word] = []
                word_positions[word].append((match.start(), match.end()))

        # 查找重复
        for word, positions in word_positions.items():
            if len(positions) > 1 and word in self.SYNONYMS:
                # 对后续出现的词建议替换
                for i, (start, end) in enumerate(positions[1:], 1):
                    synonym = self.SYNONYMS[word][i % len(self.SYNONYMS[word])]
                    matches.append(
                        RuleMatch(
                            position=(start, end),
                            original=word,
                            suggestion=synonym,
                            reason="避免重复用词",
                            confidence=0.5 * intensity,
                        )
                    )

        return matches

    def _check_high_frequency_words(
        self,
        text: str,
        intensity: float,
        style: PolishStyle,
    ) -> list[RuleMatch]:
        """检查高频词。"""
        matches = []

        # 只在深度润色时替换高频词
        if intensity < 0.8:
            return matches

        for word, alternatives in self.HIGH_FREQUENCY_WORDS.items():
            count = text.count(word)
            if count > 1:  # 出现多次才考虑替换
                start = 0
                alt_index = 0
                while True:
                    pos = text.find(word, start)
                    if pos == -1:
                        break

                    if start > 0:  # 跳过第一次出现
                        alt = alternatives[alt_index % len(alternatives)]
                        matches.append(
                            RuleMatch(
                                position=(pos, pos + len(word)),
                                original=word,
                                suggestion=alt,
                                reason="丰富词汇表达",
                                confidence=0.4 * intensity,
                            )
                        )
                        alt_index += 1
                    start = pos + 1

        return matches


class RuleEngine:
    """
    规则引擎。

    管理和协调多个润色规则的执行。

    Attributes:
        rules: 注册的规则列表
        config: 引擎配置
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """
        初始化规则引擎。

        Args:
            config: 引擎配置
        """
        self.config = config or {}
        self._rules: dict[str, PolishRule] = {}
        self._initialize_default_rules()

    def _initialize_default_rules(self) -> None:
        """初始化默认规则。"""
        default_rules = [
            GrammarRule(),
            StyleRule(),
            ClarityRule(),
            ConcisenessRule(),
            PunctuationRule(),
            VocabularyRule(),
        ]

        for rule in default_rules:
            self.register_rule(rule)

    def register_rule(self, rule: PolishRule) -> None:
        """
        注册规则。

        Args:
            rule: 要注册的规则
        """
        self._rules[rule.name] = rule

    def unregister_rule(self, name: str) -> bool:
        """
        注销规则。

        Args:
            name: 规则名称

        Returns:
            是否成功注销
        """
        if name in self._rules:
            del self._rules[name]
            return True
        return False

    def get_rule(self, name: str) -> PolishRule | None:
        """
        获取规则。

        Args:
            name: 规则名称

        Returns:
            规则实例，如果不存在返回 None
        """
        return self._rules.get(name)

    def list_rules(self) -> list[str]:
        """列出所有注册的规则名称。"""
        return list(self._rules.keys())

    def apply_rules(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
        enabled_rules: list[str] | None = None,
        disabled_rules: list[str] | None = None,
    ) -> list[TextChange]:
        """
        应用所有规则到文本。

        Args:
            text: 待润色文本
            level: 润色等级
            style: 润色风格
            enabled_rules: 启用的规则列表（None表示全部启用）
            disabled_rules: 禁用的规则列表

        Returns:
            所有规则产生的变更列表
        """
        all_changes: list[TextChange] = []

        # 按优先级排序规则
        sorted_rules = sorted(
            self._rules.values(),
            key=lambda r: r.config.priority,
            reverse=True,
        )

        for rule in sorted_rules:
            # 检查是否启用
            if enabled_rules and rule.name not in enabled_rules:
                continue
            if disabled_rules and rule.name in disabled_rules:
                continue
            if not rule.is_enabled():
                continue

            try:
                matches = rule.apply(text, level, style)
                for match in matches:
                    all_changes.append(match.to_text_change(rule.change_type))
            except Exception as e:
                raise PolishException(
                    message=f"规则 {rule.name} 执行失败: {e}",
                    code="RULE_EXECUTION_ERROR",
                    details={"rule": rule.name, "error": str(e)},
                )

        # 按位置排序并去重
        all_changes.sort(key=lambda c: c.position[0])
        all_changes = self._deduplicate_changes(all_changes)

        return all_changes

    def _deduplicate_changes(
        self,
        changes: list[TextChange],
    ) -> list[TextChange]:
        """
        去除重复的变更。

        Args:
            changes: 变更列表

        Returns:
            去重后的变更列表
        """
        if not changes:
            return changes

        unique_changes = []
        seen_positions = set()

        for change in changes:
            pos_key = (change.position, change.original, change.replacement)
            if pos_key not in seen_positions:
                seen_positions.add(pos_key)
                unique_changes.append(change)

        return unique_changes

    def analyze_text(
        self,
        text: str,
        level: PolishLevel = PolishLevel.MODERATE,
        style: PolishStyle = PolishStyle.FORMAL,
    ) -> dict[str, Any]:
        """
        分析文本，返回各规则的检测结果统计。

        Args:
            text: 待分析文本
            level: 润色等级
            style: 润色风格

        Returns:
            分析结果字典
        """
        analysis = {
            "text_length": len(text),
            "rules": {},
            "total_issues": 0,
        }

        for name, rule in self._rules.items():
            if not rule.is_enabled():
                continue

            matches = rule.apply(text, level, style)
            analysis["rules"][name] = {
                "issue_count": len(matches),
                "description": rule.description,
            }
            analysis["total_issues"] += len(matches)

        return analysis

    def to_dict(self) -> dict[str, Any]:
        """将引擎状态转换为字典。"""
        return {
            "rules": {
                name: {
                    "enabled": rule.is_enabled(),
                    "priority": rule.config.priority,
                    "description": rule.description,
                }
                for name, rule in self._rules.items()
            },
            "config": self.config,
        }
