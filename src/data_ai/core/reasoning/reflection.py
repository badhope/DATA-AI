"""
反思引擎

对推理过程进行反思和优化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from data_ai.core.reasoning.sequential import ReasoningChain, Thought

from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Reflection:
    """反思结果"""

    original_conclusion: str
    issues_found: list[str]
    improvements: list[str]
    revised_conclusion: str | None = None
    confidence_change: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ReflectionEngine:
    """
    反思引擎

    对推理过程进行批判性审视：
    1. 检查逻辑漏洞
    2. 识别潜在偏见
    3. 发现遗漏信息
    4. 提出改进建议
    """

    def __init__(self):
        self._reflection_history: list[Reflection] = []

    def reflect(
        self,
        thinking_result: ReasoningChain,
    ) -> Reflection:
        """
        对思考结果进行反思

        Args:
            thinking_result: 思考结果

        Returns:
            反思结果
        """
        issues = []
        improvements = []

        # 1. 检查步骤完整性
        issues.extend(self._check_completeness(thinking_result.thoughts))

        # 2. 检查逻辑一致性
        issues.extend(self._check_consistency(thinking_result.thoughts))

        # 3. 检查证据充分性
        issues.extend(self._check_evidence(thinking_result.thoughts))

        # 4. 生成改进建议
        improvements.extend(self._generate_improvements(issues))

        # 5. 尝试修正结论
        revised = self._revise_conclusion(thinking_result, issues)

        reflection = Reflection(
            original_conclusion=thinking_result.final_answer,
            issues_found=issues,
            improvements=improvements,
            revised_conclusion=revised,
            confidence_change=-len(issues) * 0.05,
        )

        self._reflection_history.append(reflection)

        return reflection

    def _check_completeness(self, steps: list[Thought]) -> list[str]:
        """检查完整性"""
        issues = []

        # 检查是否有分析步骤
        has_analysis = any(s.metadata.get("thought_type", "") == "analysis" for s in steps)
        if not has_analysis:
            issues.append("缺少问题分析步骤")

        has_verification = any(s.metadata.get("thought_type", "") == "verification" for s in steps)
        if not has_verification:
            issues.append("缺少结论验证步骤")

        # 检查步骤数量
        if len(steps) < 3:
            issues.append("推理步骤过少，可能不够深入")

        return issues

    def _check_consistency(self, steps: list[Thought]) -> list[str]:
        """检查一致性"""
        issues = []

        # 检查置信度变化是否合理
        for i in range(1, len(steps)):
            prev_conf = steps[i - 1].metadata.get("confidence", 0.0)
            curr_conf = steps[i].metadata.get("confidence", 0.0)

            if prev_conf - curr_conf > 0.3:
                issues.append(f"步骤 {i + 1} 置信度突然下降，可能存在问题")

        for i, step in enumerate(steps):
            for dep in step.metadata.get("dependencies", []):
                if dep > (i + 1):
                    issues.append(f"步骤 {i + 1} 依赖了后续步骤 {dep}")

        return issues

    def _check_evidence(self, steps: list[Thought]) -> list[str]:
        """检查证据充分性"""
        issues = []

        for i, step in enumerate(steps):
            if step.metadata.get("thought_type", "") in ("reasoning", "conclusion"):
                if not step.metadata.get("evidence", []):
                    issues.append(f"步骤 {i + 1} 缺少支持证据")

        return issues

    def _generate_improvements(self, issues: list[str]) -> list[str]:
        """生成改进建议"""
        improvements = []

        for issue in issues:
            if "缺少" in issue:
                improvements.append(f"建议: 添加{issue.replace('缺少', '')}")
            elif "过少" in issue:
                improvements.append("建议: 增加更多推理步骤")
            elif "突然下降" in issue:
                improvements.append("建议: 检查推理逻辑，补充中间步骤")
            elif "依赖" in issue:
                improvements.append("建议: 调整步骤顺序，确保依赖正确")

        return improvements

    def _revise_conclusion(
        self,
        result: ReasoningChain,
        issues: list[str],
    ) -> str | None:
        """修正结论"""
        if not issues:
            return None

        # 如果问题较多，添加警示
        if len(issues) >= 3:
            return f"[需谨慎] {result.final_answer} (存在 {len(issues)} 个潜在问题)"

        # 如果有少量问题，添加备注
        if issues:
            return f"{result.final_answer} (注意: {issues[0]})"

        return None

    def get_history(self) -> list[Reflection]:
        """获取反思历史"""
        return self._reflection_history.copy()

    def clear_history(self) -> None:
        """清除历史"""
        self._reflection_history = []
