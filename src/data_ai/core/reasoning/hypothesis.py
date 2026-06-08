"""
假设生成与验证

提供假设生成、验证和评估能力。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


class HypothesisStatus(Enum):
    """假设状态"""

    PROPOSED = "proposed"  # 已提出
    TESTING = "testing"  # 测试中
    CONFIRMED = "confirmed"  # 已确认
    REFUTED = "refuted"  # 已反驳
    INCONCLUSIVE = "inconclusive"  # 无结论


@dataclass
class Hypothesis:
    """假设"""

    id: str
    statement: str
    premises: list[str] = field(default_factory=list)
    predictions: list[str] = field(default_factory=list)
    confidence: float = 0.5
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_confidence(self, delta: float) -> None:
        """更新置信度"""
        self.confidence = max(0.0, min(1.0, self.confidence + delta))


@dataclass
class VerificationResult:
    """验证结果"""

    hypothesis_id: str
    is_valid: bool
    confidence: float
    evidence: list[str]
    counter_evidence: list[str]
    conclusion: str
    recommendations: list[str] = field(default_factory=list)


class HypothesisGenerator:
    """
    假设生成器

    支持：
    1. 从问题生成多个假设
    2. 设计验证实验
    3. 评估假设有效性
    4. 选择最优假设
    """

    def __init__(self, max_hypotheses: int = 5):
        self._max_hypotheses = max_hypotheses
        self._hypotheses: dict[str, Hypothesis] = {}
        self._counter = 0

    def generate(
        self,
        problem: str,
        context: dict[str, Any] | None = None,
        num_hypotheses: int = 3,
    ) -> list[Hypothesis]:
        """
        生成假设

        Args:
            problem: 问题描述
            context: 上下文
            num_hypotheses: 假设数量

        Returns:
            生成的假设列表
        """
        hypotheses = []

        # 基于问题类型生成假设
        problem.lower()

        # 假设模板
        templates = self._get_hypothesis_templates(problem, context)

        for i, template in enumerate(templates[:num_hypotheses]):
            self._counter += 1
            hypothesis = Hypothesis(
                id=f"h_{self._counter}",
                statement=template["statement"],
                premises=template.get("premises", []),
                predictions=template.get("predictions", []),
                confidence=template.get("initial_confidence", 0.5),
            )
            hypotheses.append(hypothesis)
            self._hypotheses[hypothesis.id] = hypothesis

        return hypotheses

    def _get_hypothesis_templates(
        self,
        problem: str,
        context: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """获取假设模板"""
        templates = []

        # 基于问题关键词生成假设
        if "为什么" in problem or "why" in problem.lower():
            templates.extend(
                [
                    {"statement": "原因可能是技术层面的限制", "initial_confidence": 0.4},
                    {"statement": "原因可能是设计决策", "initial_confidence": 0.4},
                    {"statement": "原因可能是外部因素影响", "initial_confidence": 0.3},
                ]
            )

        if "如何" in problem or "怎么" in problem or "how" in problem.lower():
            templates.extend(
                [
                    {"statement": "可以通过直接方法解决", "initial_confidence": 0.5},
                    {"statement": "可能需要间接方法", "initial_confidence": 0.4},
                    {"statement": "可能需要组合多种方法", "initial_confidence": 0.4},
                ]
            )

        if "是什么" in problem or "什么是" in problem or "what" in problem.lower():
            templates.extend(
                [
                    {"statement": "这是一个技术概念", "initial_confidence": 0.4},
                    {"statement": "这是一个业务概念", "initial_confidence": 0.4},
                    {"statement": "这是一个工具或方法", "initial_confidence": 0.4},
                ]
            )

        # 默认假设
        if not templates:
            templates = [
                {"statement": "假设1: 问题可以通过常规方法解决", "initial_confidence": 0.5},
                {"statement": "假设2: 问题可能需要特殊处理", "initial_confidence": 0.4},
                {"statement": "假设3: 问题可能涉及多个因素", "initial_confidence": 0.3},
            ]

        return templates

    def verify(
        self,
        hypothesis: Hypothesis,
        evidence: list[str],
        counter_evidence: list[str] | None = None,
    ) -> VerificationResult:
        """
        验证假设

        Args:
            hypothesis: 待验证的假设
            evidence: 支持证据
            counter_evidence: 反对证据

        Returns:
            验证结果
        """
        counter_evidence = counter_evidence or []

        # 计算证据权重
        evidence_score = len(evidence) * 0.2
        counter_score = len(counter_evidence) * 0.3

        # 更新置信度
        delta = evidence_score - counter_score
        hypothesis.update_confidence(delta)

        # 更新假设状态
        if hypothesis.confidence >= 0.8:
            hypothesis.status = HypothesisStatus.CONFIRMED
        elif hypothesis.confidence <= 0.2:
            hypothesis.status = HypothesisStatus.REFUTED
        else:
            hypothesis.status = HypothesisStatus.INCONCLUSIVE

        # 更新证据
        hypothesis.evidence_for.extend(evidence)
        hypothesis.evidence_against.extend(counter_evidence)

        # 生成结论
        is_valid = hypothesis.confidence >= 0.5
        conclusion = self._generate_conclusion(hypothesis, is_valid)

        # 生成建议
        recommendations = self._generate_recommendations(hypothesis)

        return VerificationResult(
            hypothesis_id=hypothesis.id,
            is_valid=is_valid,
            confidence=hypothesis.confidence,
            evidence=evidence,
            counter_evidence=counter_evidence,
            conclusion=conclusion,
            recommendations=recommendations,
        )

    def _generate_conclusion(self, hypothesis: Hypothesis, is_valid: bool) -> str:
        """生成结论"""
        if hypothesis.status == HypothesisStatus.CONFIRMED:
            return f"假设 '{hypothesis.statement}' 已被确认，置信度: {hypothesis.confidence:.2f}"
        elif hypothesis.status == HypothesisStatus.REFUTED:
            return f"假设 '{hypothesis.statement}' 已被反驳，置信度: {hypothesis.confidence:.2f}"
        elif is_valid:
            return f"假设 '{hypothesis.statement}' 可能成立，需要更多验证"
        else:
            return f"假设 '{hypothesis.statement}' 可能不成立，需要更多验证"

    def _generate_recommendations(self, hypothesis: Hypothesis) -> list[str]:
        """生成建议"""
        recommendations = []

        if hypothesis.confidence < 0.5:
            recommendations.append("建议收集更多支持证据")

        if len(hypothesis.evidence_against) > 0:
            recommendations.append("建议分析反对证据的来源")

        if hypothesis.status == HypothesisStatus.INCONCLUSIVE:
            recommendations.append("建议设计更多验证实验")

        return recommendations

    def select_best(
        self,
        hypotheses: list[Hypothesis],
    ) -> Hypothesis | None:
        """选择最佳假设"""
        if not hypotheses:
            return None

        # 按置信度排序
        sorted_hypotheses = sorted(
            hypotheses,
            key=lambda h: h.confidence,
            reverse=True,
        )

        return sorted_hypotheses[0]

    def get_hypothesis(self, hypothesis_id: str) -> Hypothesis | None:
        """获取假设"""
        return self._hypotheses.get(hypothesis_id)

    def list_hypotheses(self, status: HypothesisStatus | None = None) -> list[Hypothesis]:
        """列出假设"""
        hypotheses = list(self._hypotheses.values())
        if status:
            hypotheses = [h for h in hypotheses if h.status == status]
        return hypotheses
