"""
技能定义

定义技能的数据结构和层级。
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


class SkillLevel(Enum):
    """技能层级（渐进式披露）"""

    LEVEL_0 = 0  # 概要（~3000 tokens）
    LEVEL_1 = 1  # 完整内容
    LEVEL_2 = 2  # 深入参考材料


class SkillCategory(Enum):
    """技能分类"""

    CODE_GENERATION = "code_generation"
    CODE_REFACTORING = "code_refactoring"
    FILE_MANIPULATION = "file_manipulation"
    DATA_ANALYSIS = "data_analysis"
    WEB_SCRAPING = "web_scraping"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEBUGGING = "debugging"
    DEPLOYMENT = "deployment"
    COMMUNICATION = "communication"
    CUSTOM = "custom"


@dataclass
class SkillStep:
    """技能步骤"""

    step_number: int
    description: str
    tool_name: str | None = None
    tool_params: dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    on_failure: str = "retry"  # retry, skip, abort
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "expected_output": self.expected_output,
            "on_failure": self.on_failure,
        }


@dataclass
class SkillMetadata:
    """技能元数据"""

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    usage_count: int = 0
    success_rate: float = 0.0
    avg_execution_time_ms: float = 0.0
    tags: list[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: str = "system"
    source: str = ""  # 学习来源


@dataclass
class Skill:
    """
    技能定义

    一个技能是一个可复用的任务执行模式，包含：
    - 触发条件
    - 执行步骤
    - 成功/失败模式
    - 元数据
    """

    id: str
    name: str
    description: str
    category: SkillCategory
    triggers: list[str]  # 触发关键词/模式
    steps: list[SkillStep]
    success_patterns: list[str]  # 成功模式
    failure_patterns: list[str]  # 失败模式
    prerequisites: list[str] = field(default_factory=list)  # 前置技能
    parameters: dict[str, Any] = field(default_factory=dict)  # 可配置参数
    metadata: SkillMetadata = field(default_factory=SkillMetadata)

    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(f"{self.name}{time.time()}".encode()).hexdigest()[:12]

    def matches(self, query: str) -> float:
        """
        检查查询是否匹配此技能

        Returns:
            匹配分数 (0.0 - 1.0)
        """
        query_lower = query.lower()
        score = 0.0

        for trigger in self.triggers:
            if trigger.lower() in query_lower:
                score += 0.3

        # 检查成功模式
        for pattern in self.success_patterns:
            if pattern.lower() in query_lower:
                score += 0.2

        return min(score, 1.0)

    def get_level_content(self, level: SkillLevel) -> str:
        """获取指定层级的技能内容"""
        if level == SkillLevel.LEVEL_0:
            return self._get_summary()
        elif level == SkillLevel.LEVEL_1:
            return self._get_full_content()
        else:
            return self._get_detailed_content()

    def _get_summary(self) -> str:
        """获取概要"""
        return f"""
# {self.name}

{self.description}

## 触发条件
{", ".join(self.triggers)}

## 步骤概要
{len(self.steps)} 个步骤: {", ".join(s.description[:30] for s in self.steps[:3])}...

## 成功率
{self.metadata.success_rate:.1%}
"""

    def _get_full_content(self) -> str:
        """获取完整内容"""
        steps_str = "\n".join(
            f"{i + 1}. {s.description}" + (f" (工具: {s.tool_name})" if s.tool_name else "")
            for i, s in enumerate(self.steps)
        )

        return f"""
# {self.name}

{self.description}

## 触发条件
{chr(10).join(f"- {t}" for t in self.triggers)}

## 执行步骤
{steps_str}

## 成功模式
{chr(10).join(f"- {p}" for p in self.success_patterns)}

## 失败模式
{chr(10).join(f"- {p}" for p in self.failure_patterns)}
"""

    def _get_detailed_content(self) -> str:
        """获取详细内容（含参考材料）"""
        base = self._get_full_content()

        detailed_steps = "\n\n## 详细步骤说明\n"
        for i, step in enumerate(self.steps):
            detailed_steps += f"""
### 步骤 {i + 1}: {step.description}
- 工具: {step.tool_name or "无"}
- 参数: {json.dumps(step.tool_params, ensure_ascii=False)}
- 预期输出: {step.expected_output}
- 失败处理: {step.on_failure}
"""

        return base + detailed_steps

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "triggers": self.triggers,
            "steps": [s.to_dict() for s in self.steps],
            "success_patterns": self.success_patterns,
            "failure_patterns": self.failure_patterns,
            "prerequisites": self.prerequisites,
            "parameters": self.parameters,
            "metadata": {
                "created_at": self.metadata.created_at,
                "updated_at": self.metadata.updated_at,
                "usage_count": self.metadata.usage_count,
                "success_rate": self.metadata.success_rate,
                "avg_execution_time_ms": self.metadata.avg_execution_time_ms,
                "tags": self.metadata.tags,
                "version": self.metadata.version,
                "author": self.metadata.author,
                "source": self.metadata.source,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Skill:
        """从字典创建"""
        metadata = SkillMetadata(
            created_at=data.get("metadata", {}).get("created_at", time.time()),
            updated_at=data.get("metadata", {}).get("updated_at", time.time()),
            usage_count=data.get("metadata", {}).get("usage_count", 0),
            success_rate=data.get("metadata", {}).get("success_rate", 0.0),
            avg_execution_time_ms=data.get("metadata", {}).get("avg_execution_time_ms", 0.0),
            tags=data.get("metadata", {}).get("tags", []),
            version=data.get("metadata", {}).get("version", "1.0.0"),
            author=data.get("metadata", {}).get("author", "system"),
            source=data.get("metadata", {}).get("source", ""),
        )

        steps = [
            SkillStep(
                step_number=s.get("step_number", i + 1),
                description=s.get("description", ""),
                tool_name=s.get("tool_name"),
                tool_params=s.get("tool_params", {}),
                expected_output=s.get("expected_output", ""),
                on_failure=s.get("on_failure", "retry"),
            )
            for i, s in enumerate(data.get("steps", []))
        ]

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            category=SkillCategory(data.get("category", "custom")),
            triggers=data.get("triggers", []),
            steps=steps,
            success_patterns=data.get("success_patterns", []),
            failure_patterns=data.get("failure_patterns", []),
            prerequisites=data.get("prerequisites", []),
            parameters=data.get("parameters", {}),
            metadata=metadata,
        )

    def to_markdown(self) -> str:
        """导出为 Markdown 格式"""
        return self._get_full_content()
