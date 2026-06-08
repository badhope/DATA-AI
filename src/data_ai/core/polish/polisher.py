"""
文本润色器模块。

本模块提供核心的文本润色功能，支持同步和异步润色。

主要组件:
- TextPolisher: 文本润色器
- PolisherBuilder: 润色器构建器
"""

from __future__ import annotations

import asyncio
import builtins
import time
from abc import ABC, abstractmethod
from typing import Any

from .diff import TextDiffer
from .rules import PolishRule, RuleEngine
from .types import (
    ChangeType,
    PolishConfig,
    PolishException,
    PolishLevel,
    PolishResult,
    PolishScore,
    PolishStyle,
    TextChange,
)


class BasePolisher(ABC):
    """
    润色器基类。

    定义润色器的公共接口和基础功能。
    """

    def __init__(self, config: PolishConfig | None = None) -> None:
        """
        初始化润色器。

        Args:
            config: 润色配置
        """
        self.config = config or PolishConfig()
        self._differ = TextDiffer()

    @abstractmethod
    def polish(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> PolishResult:
        """
        润色文本。

        Args:
            text: 待润色文本
            level: 润色等级（可选，覆盖配置）
            style: 润色风格（可选，覆盖配置）

        Returns:
            润色结果
        """
        pass

    @abstractmethod
    async def polish_async(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> PolishResult:
        """
        异步润色文本。

        Args:
            text: 待润色文本
            level: 润色等级（可选，覆盖配置）
            style: 润色风格（可选，覆盖配置）

        Returns:
            润色结果
        """
        pass

    def set_style(self, style: PolishStyle) -> None:
        """
        设置润色风格。

        Args:
            style: 润色风格
        """
        self.config.style = style

    def set_level(self, level: PolishLevel) -> None:
        """
        设置润色等级。

        Args:
            level: 润色等级
        """
        self.config.level = level

    def _calculate_score(
        self,
        original: str,
        polished: str,
        changes: list[TextChange],
    ) -> PolishScore:
        """
        计算润色评分。

        Args:
            original: 原始文本
            polished: 润色后文本
            changes: 变更列表

        Returns:
            润色评分
        """
        # 基于变更类型和数量计算各维度评分
        grammar_score = self._calculate_grammar_score(original, changes)
        clarity_score = self._calculate_clarity_score(original, polished, changes)
        conciseness_score = self._calculate_conciseness_score(original, polished)
        style_score = self._calculate_style_score(changes)
        readability_score = self._calculate_readability_score(polished)

        return PolishScore(
            grammar=grammar_score,
            clarity=clarity_score,
            conciseness=conciseness_score,
            style=style_score,
            readability=readability_score,
        )

    def _calculate_grammar_score(
        self,
        text: str,
        changes: list[TextChange],
    ) -> float:
        """计算语法评分。"""
        if not text:
            return 100.0

        grammar_changes = [c for c in changes if c.change_type == ChangeType.GRAMMAR]

        # 基于语法错误数量计算评分
        error_ratio = len(grammar_changes) / max(len(text) / 50, 1)
        score = max(0, 100 - error_ratio * 20)

        return min(100, score)

    def _calculate_clarity_score(
        self,
        original: str,
        polished: str,
        changes: list[TextChange],
    ) -> float:
        """计算清晰度评分。"""
        if not polished:
            return 0.0

        clarity_changes = [c for c in changes if c.change_type == ChangeType.CLARITY]

        # 基于清晰度改进计算评分
        base_score = 70.0
        improvement = len(clarity_changes) * 5

        # 检查句子长度
        avg_sentence_length = self._get_avg_sentence_length(polished)
        if 15 <= avg_sentence_length <= 25:
            base_score += 10
        elif avg_sentence_length > 35:
            base_score -= 10

        return min(100, base_score + improvement)

    def _calculate_conciseness_score(
        self,
        original: str,
        polished: str,
    ) -> float:
        """计算简洁性评分。"""
        if not original:
            return 100.0

        # 基于文本长度变化计算评分
        length_ratio = len(polished) / len(original) if original else 1.0

        if length_ratio <= 1.0:
            # 文本变短，通常更好
            score = 80 + (1 - length_ratio) * 20
        else:
            # 文本变长，可能不够简洁
            score = max(50, 80 - (length_ratio - 1) * 30)

        return min(100, score)

    def _calculate_style_score(
        self,
        changes: list[TextChange],
    ) -> float:
        """计算风格一致性评分。"""
        style_changes = [c for c in changes if c.change_type == ChangeType.STYLE]

        # 基于风格调整数量计算评分
        # 适当的风格调整表明改进
        base_score = 75.0
        improvement = min(20, len(style_changes) * 3)

        return min(100, base_score + improvement)

    def _calculate_readability_score(
        self,
        text: str,
    ) -> float:
        """计算可读性评分。"""
        if not text:
            return 0.0

        score = 70.0

        # 检查段落结构
        paragraphs = text.split("\n\n")
        if len(paragraphs) > 1:
            score += 5

        # 检查句子长度分布
        sentences = self._split_sentences(text)
        if sentences:
            avg_length = sum(len(s) for s in sentences) / len(sentences)
            if 15 <= avg_length <= 30:
                score += 10
            elif avg_length > 40:
                score -= 5

        # 检查标点使用
        punctuation_count = sum(1 for c in text if c in "，。！？；：")
        if punctuation_count > 0:
            score += 5

        return min(100, score)

    def _get_avg_sentence_length(self, text: str) -> float:
        """获取平均句子长度。"""
        sentences = self._split_sentences(text)
        if not sentences:
            return 0.0
        return sum(len(s) for s in sentences) / len(sentences)

    def _split_sentences(self, text: str) -> list[str]:
        """分割句子。"""
        import re

        # 按中英文句号、问号、感叹号分割
        sentences = re.split(r"[。！？.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]


class TextPolisher(BasePolisher):
    """
    文本润色器。

    基于规则的文本润色器，提供同步和异步润色功能。

    Example:
        >>> polisher = TextPolisher()
        >>> result = polisher.polish("这个很好看", level=PolishLevel.MODERATE)
        >>> print(result.polished)
        这件物品外观非常精美
    """

    def __init__(
        self,
        config: PolishConfig | None = None,
        rule_engine: RuleEngine | None = None,
    ) -> None:
        """
        初始化文本润色器。

        Args:
            config: 润色配置
            rule_engine: 规则引擎（可选）
        """
        super().__init__(config)
        self._rule_engine = rule_engine or RuleEngine()

    @property
    def rule_engine(self) -> RuleEngine:
        """获取规则引擎。"""
        return self._rule_engine

    def register_rule(self, rule: PolishRule) -> None:
        """
        注册自定义规则。

        Args:
            rule: 润色规则
        """
        self._rule_engine.register_rule(rule)

    def unregister_rule(self, name: str) -> bool:
        """
        注销规则。

        Args:
            name: 规则名称

        Returns:
            是否成功注销
        """
        return self._rule_engine.unregister_rule(name)

    def polish(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> PolishResult:
        """
        润色文本。

        Args:
            text: 待润色文本
            level: 润色等级（可选，覆盖配置）
            style: 润色风格（可选，覆盖配置）

        Returns:
            润色结果

        Raises:
            PolishException: 润色过程中发生错误
        """
        start_time = time.time()

        # 使用传入的参数或配置中的默认值
        polish_level = level or self.config.level
        polish_style = style or self.config.style

        if not text:
            return PolishResult(
                original=text,
                polished=text,
                changes=[],
                score=PolishScore(),
                level=polish_level,
                style=polish_style,
                processing_time=time.time() - start_time,
            )

        try:
            # 应用规则获取变更
            changes = self._rule_engine.apply_rules(
                text=text,
                level=polish_level,
                style=polish_style,
                enabled_rules=self.config.enabled_rules or None,
                disabled_rules=self.config.disabled_rules or None,
            )

            # 过滤低置信度变更
            changes = [c for c in changes if c.confidence >= self.config.min_confidence]

            # 限制变更数量
            changes = changes[: self.config.max_changes]

            # 应用变更
            polished = self._apply_changes(text, changes)

            # 计算评分
            score = self._calculate_score(text, polished, changes)

            processing_time = time.time() - start_time

            return PolishResult(
                original=text,
                polished=polished,
                changes=changes,
                score=score,
                level=polish_level,
                style=polish_style,
                processing_time=processing_time,
                metadata={
                    "rule_count": len(self._rule_engine.list_rules()),
                    "change_count": len(changes),
                },
            )

        except Exception as e:
            raise PolishException(
                message=f"润色过程中发生错误: {e}",
                code="POLISH_ERROR",
                details={"error": str(e)},
            )

    async def polish_async(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> PolishResult:
        """
        异步润色文本。

        Args:
            text: 待润色文本
            level: 润色等级（可选，覆盖配置）
            style: 润色风格（可选，覆盖配置）

        Returns:
            润色结果
        """
        # 在线程池中执行同步润色
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.polish(text, level, style),
        )

    def polish_batch(
        self,
        texts: list[str],
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> list[PolishResult]:
        """
        批量润色文本。

        Args:
            texts: 待润色文本列表
            level: 润色等级
            style: 润色风格

        Returns:
            润色结果列表
        """
        return [self.polish(text, level, style) for text in texts]

    async def polish_batch_async(
        self,
        texts: list[str],
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> list[PolishResult]:
        """
        异步批量润色文本。

        Args:
            texts: 待润色文本列表
            level: 润色等级
            style: 润色风格

        Returns:
            润色结果列表
        """
        tasks = [self.polish_async(text, level, style) for text in texts]
        return await asyncio.gather(*tasks)

    def _apply_changes(
        self,
        text: str,
        changes: list[TextChange],
    ) -> str:
        """
        应用变更到文本。

        Args:
            text: 原始文本
            changes: 变更列表

        Returns:
            应用变更后的文本
        """
        return self._differ.apply_diff(text, changes)

    def analyze(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> dict[str, Any]:
        """
        分析文本，返回问题统计。

        Args:
            text: 待分析文本
            level: 润色等级
            style: 润色风格

        Returns:
            分析结果字典
        """
        polish_level = level or self.config.level
        polish_style = style or self.config.style

        return self._rule_engine.analyze_text(text, polish_level, polish_style)

    def preview(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
        format_type: str = "markdown",
    ) -> str:
        """
        预览润色结果。

        Args:
            text: 待润色文本
            level: 润色等级
            style: 润色风格
            format_type: 格式类型

        Returns:
            格式化后的预览字符串
        """
        result = self.polish(text, level, style)

        from .diff import DiffFormat

        diff_result = self._differ.compute_diff(text, result.polished)

        format_map = {
            "unified": DiffFormat.UNIFIED,
            "context": DiffFormat.CONTEXT,
            "html": DiffFormat.HTML,
            "markdown": DiffFormat.MARKDOWN,
            "json": DiffFormat.JSON,
        }

        diff_format = format_map.get(format_type, DiffFormat.MARKDOWN)
        return self._differ.format_diff(diff_result, diff_format)


class PolisherBuilder:
    """
    润色器构建器。

    提供流畅的 API 来构建和配置润色器。

    Example:
        >>> polisher = (
        ...     PolisherBuilder()
        ...     .with_level(PolishLevel.DEEP)
        ...     .with_style(PolishStyle.FORMAL)
        ...     .with_min_confidence(0.7)
        ...     .build()
        ... )
    """

    def __init__(self) -> None:
        """初始化构建器。"""
        self._config = PolishConfig()
        self._custom_rules: list[PolishRule] = []
        self._rule_engine: RuleEngine | None = None

    def with_level(self, level: PolishLevel) -> PolisherBuilder:
        """
        设置润色等级。

        Args:
            level: 润色等级

        Returns:
            构建器实例
        """
        self._config.level = level
        return self

    def with_style(self, style: PolishStyle) -> PolisherBuilder:
        """
        设置润色风格。

        Args:
            style: 润色风格

        Returns:
            构建器实例
        """
        self._config.style = style
        return self

    def with_min_confidence(self, confidence: float) -> PolisherBuilder:
        """
        设置最小置信度。

        Args:
            confidence: 最小置信度（0.0-1.0）

        Returns:
            构建器实例
        """
        self._config.min_confidence = confidence
        return self

    def with_max_changes(self, max_changes: int) -> PolisherBuilder:
        """
        设置最大变更数量。

        Args:
            max_changes: 最大变更数量

        Returns:
            构建器实例
        """
        self._config.max_changes = max_changes
        return self

    def with_enabled_rules(self, rules: list[str]) -> PolisherBuilder:
        """
        设置启用的规则。

        Args:
            rules: 规则名称列表

        Returns:
            构建器实例
        """
        self._config.enabled_rules = rules
        return self

    def with_disabled_rules(self, rules: list[str]) -> PolisherBuilder:
        """
        设置禁用的规则。

        Args:
            rules: 规则名称列表

        Returns:
            构建器实例
        """
        self._config.disabled_rules = rules
        return self

    def with_custom_rule(self, rule: PolishRule) -> PolisherBuilder:
        """
        添加自定义规则。

        Args:
            rule: 润色规则

        Returns:
            构建器实例
        """
        self._custom_rules.append(rule)
        return self

    def with_rule_engine(self, engine: RuleEngine) -> PolisherBuilder:
        """
        设置规则引擎。

        Args:
            engine: 规则引擎

        Returns:
            构建器实例
        """
        self._rule_engine = engine
        return self

    def with_language(self, language: str) -> PolisherBuilder:
        """
        设置目标语言。

        Args:
            language: 语言代码

        Returns:
            构建器实例
        """
        self._config.language = language
        return self

    def with_timeout(self, timeout: float) -> PolisherBuilder:
        """
        设置超时时间。

        Args:
            timeout: 超时时间（秒）

        Returns:
            构建器实例
        """
        self._config.timeout = timeout
        return self

    def with_preserve_formatting(self, preserve: bool) -> PolisherBuilder:
        """
        设置是否保留格式。

        Args:
            preserve: 是否保留格式

        Returns:
            构建器实例
        """
        self._config.preserve_formatting = preserve
        return self

    def build(self) -> TextPolisher:
        """
        构建润色器。

        Returns:
            配置好的润色器实例
        """
        rule_engine = self._rule_engine or RuleEngine()

        # 注册自定义规则
        for rule in self._custom_rules:
            rule_engine.register_rule(rule)

        return TextPolisher(
            config=self._config,
            rule_engine=rule_engine,
        )


class PolisherRegistry:
    """
    润色器注册表。

    管理多个命名润色器实例。
    """

    _instance: PolisherRegistry | None = None

    def __new__(cls) -> PolisherRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._polishers: dict[str, TextPolisher] = {}
        return cls._instance

    def register(
        self,
        name: str,
        polisher: TextPolisher,
    ) -> None:
        """
        注册润色器。

        Args:
            name: 润色器名称
            polisher: 润色器实例
        """
        self._polishers[name] = polisher

    def get(self, name: str) -> TextPolisher | None:
        """
        获取润色器。

        Args:
            name: 润色器名称

        Returns:
            润色器实例，如果不存在返回 None
        """
        return self._polishers.get(name)

    def list(self) -> builtins.list[str]:
        """列出所有注册的润色器名称。"""
        return list(self._polishers.keys())

    def remove(self, name: str) -> bool:
        """
        移除润色器。

        Args:
            name: 润色器名称

        Returns:
            是否成功移除
        """
        if name in self._polishers:
            del self._polishers[name]
            return True
        return False


# 便捷函数
def polish_text(
    text: str,
    level: PolishLevel = PolishLevel.MODERATE,
    style: PolishStyle = PolishStyle.FORMAL,
) -> PolishResult:
    """
    便捷函数：润色文本。

    Args:
        text: 待润色文本
        level: 润色等级
        style: 润色风格

    Returns:
        润色结果
    """
    polisher = TextPolisher()
    return polisher.polish(text, level, style)


async def polish_text_async(
    text: str,
    level: PolishLevel = PolishLevel.MODERATE,
    style: PolishStyle = PolishStyle.FORMAL,
) -> PolishResult:
    """
    便捷函数：异步润色文本。

    Args:
        text: 待润色文本
        level: 润色等级
        style: 润色风格

    Returns:
        润色结果
    """
    polisher = TextPolisher()
    return await polisher.polish_async(text, level, style)
