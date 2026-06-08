"""
技能提取器

从成功的交互中自动提炼技能。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from ...utils.logging import get_logger
from .skill import Skill, SkillCategory, SkillMetadata, SkillStep

logger = get_logger(__name__)


@dataclass
class Interaction:
    """交互记录"""

    query: str
    steps: list[dict[str, Any]]
    result: str
    success: bool
    tools_used: list[str]
    execution_time_ms: float
    metadata: dict[str, Any]


class SkillExtractor:
    """
    技能提取器

    从成功的交互中自动提炼可复用的技能：
    1. 识别成功模式
    2. 提取关键步骤
    3. 生成触发条件
    4. 创建技能定义
    """

    def __init__(self, min_success_rate: float = 0.8, min_usage: int = 2):
        self._min_success_rate = min_success_rate
        self._min_usage = min_usage
        self._interaction_history: list[Interaction] = []

    def record_interaction(
        self,
        query: str,
        steps: list[dict[str, Any]],
        result: str,
        success: bool,
        tools_used: list[str],
        execution_time_ms: float = 0,
        metadata: dict | None = None,
    ) -> None:
        """记录交互"""
        interaction = Interaction(
            query=query,
            steps=steps,
            result=result,
            success=success,
            tools_used=tools_used,
            execution_time_ms=execution_time_ms,
            metadata=metadata or {},
        )
        self._interaction_history.append(interaction)

        # 限制历史长度
        if len(self._interaction_history) > 1000:
            self._interaction_history = self._interaction_history[-500:]

    def extract_skill(self, interaction: Interaction) -> Skill | None:
        """
        从交互中提取技能

        Args:
            interaction: 成功的交互记录

        Returns:
            提取的技能，如果无法提取则返回 None
        """
        if not interaction.success:
            return None

        if not interaction.steps:
            return None

        # 生成技能名称
        name = self._generate_skill_name(interaction)

        # 提取触发条件
        triggers = self._extract_triggers(interaction)

        # 提取步骤
        steps = self._extract_steps(interaction)

        # 确定分类
        category = self._determine_category(interaction)

        # 提取成功模式
        success_patterns = self._extract_success_patterns(interaction)

        # 创建技能
        skill = Skill(
            id="",
            name=name,
            description=f"从交互中自动提炼: {interaction.query[:100]}",
            category=category,
            triggers=triggers,
            steps=steps,
            success_patterns=success_patterns,
            failure_patterns=[],
            metadata=SkillMetadata(
                source="auto_extracted",
                author="system",
            ),
        )

        return skill

    def _generate_skill_name(self, interaction: Interaction) -> str:
        """生成技能名称"""
        # 从查询中提取关键词
        query = interaction.query.lower()

        # 常见任务关键词
        task_keywords = {
            "创建": "create",
            "生成": "generate",
            "写": "write",
            "分析": "analyze",
            "处理": "process",
            "转换": "convert",
            "搜索": "search",
            "查找": "find",
            "读取": "read",
            "create": "create",
            "generate": "generate",
            "write": "write",
            "analyze": "analyze",
            "process": "process",
            "search": "search",
        }

        for keyword, task in task_keywords.items():
            if keyword in query:
                # 提取目标对象
                words = query.split()
                for i, word in enumerate(words):
                    if keyword in word and i + 1 < len(words):
                        return f"{task}_{words[i + 1][:10]}"

        # 默认名称
        return f"skill_{int(time.time())}"

    def _extract_triggers(self, interaction: Interaction) -> list[str]:
        """提取触发条件"""
        triggers = []

        # 从查询中提取关键词
        query = interaction.query.lower()

        # 添加查询中的关键词
        words = query.split()
        for word in words:
            if len(word) > 2:
                triggers.append(word)

        # 添加使用的工具名
        triggers.extend(interaction.tools_used)

        # 去重并限制数量
        return list(set(triggers))[:5]

    def _extract_steps(self, interaction: Interaction) -> list[SkillStep]:
        """提取步骤"""
        steps = []

        for i, step_data in enumerate(interaction.steps):
            step = SkillStep(
                step_number=i + 1,
                description=step_data.get("description", step_data.get("thought", "")),
                tool_name=step_data.get("tool_name") or step_data.get("action"),
                tool_params=step_data.get("tool_params") or step_data.get("action_input", {}),
                expected_output=step_data.get("expected_output", ""),
                on_failure="retry",
            )
            steps.append(step)

        return steps

    def _determine_category(self, interaction: Interaction) -> SkillCategory:
        """确定技能分类"""
        query = interaction.query.lower()
        tools = set(interaction.tools_used)

        # 根据工具和查询内容判断
        if any(t in tools for t in ["file_read", "file_write", "str_replace_editor"]):
            return SkillCategory.FILE_MANIPULATION

        if any(t in tools for t in ["python_execute", "bash"]):
            if "分析" in query or "analyze" in query:
                return SkillCategory.DATA_ANALYSIS
            return SkillCategory.CODE_GENERATION

        if any(t in tools for t in ["browser_navigate", "browser_click"]):
            return SkillCategory.WEB_SCRAPING

        if any(t in tools for t in ["web_search"]):
            return SkillCategory.COMMUNICATION

        return SkillCategory.CUSTOM

    def _extract_success_patterns(self, interaction: Interaction) -> list[str]:
        """提取成功模式"""
        patterns = []

        # 从结果中提取模式
        if interaction.result:
            # 提取关键短语
            sentences = interaction.result.split("。")
            for sentence in sentences[:3]:
                if len(sentence) > 10:
                    patterns.append(sentence[:50])

        return patterns

    def batch_extract(self, min_interactions: int = 3) -> list[Skill]:
        """
        批量提取技能

        从历史交互中提取高频成功的模式作为技能
        """
        # 按相似查询分组
        query_groups: dict[str, list[Interaction]] = {}

        for interaction in self._interaction_history:
            if not interaction.success:
                continue

            # 简单的查询分组（按首词）
            key = interaction.query.split()[0] if interaction.query.split() else "other"

            if key not in query_groups:
                query_groups[key] = []
            query_groups[key].append(interaction)

        # 提取技能
        skills = []

        for key, interactions in query_groups.items():
            if len(interactions) < min_interactions:
                continue

            # 计算成功率
            success_rate = sum(1 for i in interactions if i.success) / len(interactions)

            if success_rate < self._min_success_rate:
                continue

            # 选择最具代表性的交互
            best_interaction = max(
                interactions,
                key=lambda i: len(i.steps) if i.success else 0,
            )

            skill = self.extract_skill(best_interaction)
            if skill:
                skill.metadata.usage_count = len(interactions)
                skill.metadata.success_rate = success_rate
                skills.append(skill)

        return skills

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        total = len(self._interaction_history)
        successful = sum(1 for i in self._interaction_history if i.success)

        return {
            "total_interactions": total,
            "successful_interactions": successful,
            "success_rate": successful / total if total > 0 else 0,
        }
