"""
Hermes 风格闭环学习系统

实现 Execute → Evaluate → Extract → Retrieve 的闭环学习流程，
从交互中持续学习并改进系统表现。

核心组件：
- InteractionRecord: 交互记录数据类
- EvaluationResult: 评估结果数据类
- ClosedLoopLearner: 闭环学习器
- ExperienceStore: 经验存储
- PatternLibrary: 模式库
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
)

from ...utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# 枚举类型
# ============================================================================


class InteractionStatus(Enum):
    """交互状态"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    PENDING = "pending"


class PatternType(Enum):
    """模式类型"""

    TOOL_SEQUENCE = "tool_sequence"  # 工具调用序列
    QUERY_PATTERN = "query_pattern"  # 查询模式
    ERROR_RECOVERY = "error_recovery"  # 错误恢复
    SUCCESS_STRATEGY = "success_strategy"  # 成功策略
    USER_PREFERENCE = "user_preference"  # 用户偏好
    CONTEXT_PATTERN = "context_pattern"  # 上下文模式


class EvaluationDimension(Enum):
    """评估维度"""

    CORRECTNESS = "correctness"  # 正确性
    EFFICIENCY = "efficiency"  # 效率
    COMPLETENESS = "completeness"  # 完整性
    USER_SATISFACTION = "user_satisfaction"  # 用户满意度
    ERROR_HANDLING = "error_handling"  # 错误处理


# ============================================================================
# 数据类定义
# ============================================================================


@dataclass
class InteractionRecord:
    """
    交互记录数据类

    记录一次完整的用户交互，包括查询、响应、使用的工具、
    执行状态和用户反馈等信息。

    Attributes:
        query: 用户查询内容
        response: 系统响应内容
        tools_used: 使用的工具列表
        success: 是否成功
        user_feedback: 用户反馈（可选），1-5分或文本反馈
        execution_time_ms: 执行时间（毫秒）
        timestamp: 时间戳
        context: 上下文信息
        error_info: 错误信息（如果有）
        metadata: 额外元数据
    """

    query: str
    response: str
    tools_used: list[str] = field(default_factory=list)
    success: bool = True
    user_feedback: int | float | str | None = None
    execution_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)
    context: dict[str, Any] = field(default_factory=dict)
    error_info: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        if not self.tools_used:
            self.tools_used = []
        if not self.context:
            self.context = {}
        if not self.metadata:
            self.metadata = {}

    @property
    def id(self) -> str:
        """生成唯一ID"""
        content = f"{self.query}{self.timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    @property
    def status(self) -> InteractionStatus:
        """获取交互状态"""
        if self.success:
            if self.user_feedback is not None:
                if isinstance(self.user_feedback, (int, float)):
                    if self.user_feedback >= 4:
                        return InteractionStatus.SUCCESS
                    elif self.user_feedback >= 2:
                        return InteractionStatus.PARTIAL
                    else:
                        return InteractionStatus.FAILURE
            return InteractionStatus.SUCCESS
        return InteractionStatus.FAILURE

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "query": self.query,
            "response": self.response,
            "tools_used": self.tools_used,
            "success": self.success,
            "user_feedback": self.user_feedback,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp,
            "context": self.context,
            "error_info": self.error_info,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InteractionRecord:
        """从字典创建"""
        return cls(
            query=data["query"],
            response=data["response"],
            tools_used=data.get("tools_used", []),
            success=data.get("success", True),
            user_feedback=data.get("user_feedback"),
            execution_time_ms=data.get("execution_time_ms", 0.0),
            timestamp=data.get("timestamp", time.time()),
            context=data.get("context", {}),
            error_info=data.get("error_info"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class EvaluationResult:
    """
    评估结果数据类

    存储对一次交互的评估结果，包括成功评分、发现的问题、
    改进建议和识别的模式。

    Attributes:
        score: 成功评分 (0.0-1.0)
        issues: 问题列表
        improvements: 改进建议列表
        patterns: 识别的模式列表
        dimension_scores: 各维度评分
        confidence: 评估置信度
        reasoning: 评估推理过程
        metadata: 额外元数据
    """

    score: float
    issues: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    dimension_scores: dict[str, float] = field(default_factory=dict)
    confidence: float = 0.8
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初始化后处理"""
        self.score = max(0.0, min(1.0, self.score))
        if not self.issues:
            self.issues = []
        if not self.improvements:
            self.improvements = []
        if not self.patterns:
            self.patterns = []
        if not self.dimension_scores:
            self.dimension_scores = {}

    @property
    def is_successful(self) -> bool:
        """是否成功（分数 >= 0.6）"""
        return self.score >= 0.6

    @property
    def needs_improvement(self) -> bool:
        """是否需要改进"""
        return len(self.issues) > 0 or self.score < 0.8

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "score": self.score,
            "issues": self.issues,
            "improvements": self.improvements,
            "patterns": self.patterns,
            "dimension_scores": self.dimension_scores,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvaluationResult:
        """从字典创建"""
        return cls(
            score=data.get("score", 0.0),
            issues=data.get("issues", []),
            improvements=data.get("improvements", []),
            patterns=data.get("patterns", []),
            dimension_scores=data.get("dimension_scores", {}),
            confidence=data.get("confidence", 0.8),
            reasoning=data.get("reasoning", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Experience:
    """
    经验数据类

    存储从成功交互中提取的可复用经验。

    Attributes:
        id: 经验唯一标识
        content: 经验内容描述
        embedding: 向量嵌入
        interaction_id: 来源交互ID
        pattern_type: 模式类型
        success_rate: 成功率
        usage_count: 使用次数
        last_used: 最后使用时间
        created_at: 创建时间
        importance: 重要程度 (0.0-1.0)
        tags: 标签列表
        metadata: 额外元数据
    """

    id: str
    content: str
    embedding: list[float] = field(default_factory=list)
    interaction_id: str = ""
    pattern_type: PatternType = PatternType.SUCCESS_STRATEGY
    success_rate: float = 1.0
    usage_count: int = 0
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding,
            "interaction_id": self.interaction_id,
            "pattern_type": self.pattern_type.value,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Experience:
        """从字典创建"""
        return cls(
            id=data["id"],
            content=data["content"],
            embedding=data.get("embedding", []),
            interaction_id=data.get("interaction_id", ""),
            pattern_type=PatternType(data.get("pattern_type", "success_strategy")),
            success_rate=data.get("success_rate", 1.0),
            usage_count=data.get("usage_count", 0),
            last_used=data.get("last_used", time.time()),
            created_at=data.get("created_at", time.time()),
            importance=data.get("importance", 0.5),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Pattern:
    """
    模式数据类

    存储从成功交互中提取的可复用模式。

    Attributes:
        id: 模式唯一标识
        name: 模式名称
        description: 模式描述
        pattern_type: 模式类型
        triggers: 触发条件列表
        actions: 动作序列
        conditions: 适用条件
        confidence: 置信度 (0.0-1.0)
        usage_count: 使用次数
        success_count: 成功次数
        last_used: 最后使用时间
        created_at: 创建时间
        examples: 示例列表
        metadata: 额外元数据
    """

    id: str
    name: str
    description: str
    pattern_type: PatternType
    triggers: list[str] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    conditions: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5
    usage_count: int = 0
    success_count: int = 0
    last_used: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    examples: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count

    def matches(self, query: str, context: dict | None = None) -> float:
        """
        检查查询是否匹配此模式

        Args:
            query: 用户查询
            context: 上下文信息

        Returns:
            匹配分数 (0.0-1.0)
        """
        query_lower = query.lower()
        score = 0.0

        # 检查触发条件
        for trigger in self.triggers:
            if trigger.lower() in query_lower:
                score += 0.25

        # 检查上下文条件
        if context and self.conditions:
            matched_conditions = 0
            for key, value in self.conditions.items():
                if key in context and context[key] == value:
                    matched_conditions += 1
            if self.conditions:
                score += 0.25 * (matched_conditions / len(self.conditions))

        return min(score, 1.0)

    def record_usage(self, success: bool) -> None:
        """记录使用情况"""
        self.usage_count += 1
        if success:
            self.success_count += 1
        self.last_used = time.time()

        # 更新置信度（使用贝叶斯更新）
        alpha = 0.1  # 学习率
        if success:
            self.confidence = self.confidence + alpha * (1.0 - self.confidence)
        else:
            self.confidence = self.confidence * (1.0 - alpha)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "pattern_type": self.pattern_type.value,
            "triggers": self.triggers,
            "actions": self.actions,
            "conditions": self.conditions,
            "confidence": self.confidence,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "last_used": self.last_used,
            "created_at": self.created_at,
            "examples": self.examples,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Pattern:
        """从字典创建"""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            pattern_type=PatternType(data.get("pattern_type", "success_strategy")),
            triggers=data.get("triggers", []),
            actions=data.get("actions", []),
            conditions=data.get("conditions", {}),
            confidence=data.get("confidence", 0.5),
            usage_count=data.get("usage_count", 0),
            success_count=data.get("success_count", 0),
            last_used=data.get("last_used", time.time()),
            created_at=data.get("created_at", time.time()),
            examples=data.get("examples", []),
            metadata=data.get("metadata", {}),
        )


# ============================================================================
# 经验存储
# ============================================================================


class ExperienceStore:
    """
    经验存储

    存储成功的交互模式，支持向量化存储和相似度搜索。

    Features:
        - 向量化存储便于检索
        - 支持相似度搜索
        - 时间衰减机制
        - 重要性排序
        - 持久化存储
    """

    def __init__(
        self,
        storage_dir: str | None = None,
        dimensions: int = 1536,
        decay_factor: float = 0.995,
        max_experiences: int = 5000,
    ):
        """
        初始化经验存储

        Args:
            storage_dir: 存储目录
            dimensions: 向量维度
            decay_factor: 时间衰减因子
            max_experiences: 最大经验数量
        """
        self._storage_dir = Path(storage_dir or os.path.expanduser("~/.data-ai/memory/experiences"))
        self._dimensions = dimensions
        self._decay_factor = decay_factor
        self._max_experiences = max_experiences
        self._experiences: dict[str, Experience] = {}
        self._embed_fn: Callable[[str], list[float]] | None = None
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load()

        logger.info(
            "经验存储初始化完成",
            storage_dir=str(self._storage_dir),
            dimensions=dimensions,
            max_experiences=max_experiences,
        )

    def set_embed_fn(self, fn: Callable[[str], list[float]]) -> None:
        """
        设置嵌入函数

        Args:
            fn: 嵌入函数，接受文本返回向量
        """
        self._embed_fn = fn

    def _get_embedding(self, text: str) -> list[float]:
        """
        获取文本嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        if self._embed_fn:
            try:
                return self._embed_fn(text)
            except Exception as e:
                logger.warning(f"获取嵌入向量失败: {e}")

        # 默认伪嵌入（基于哈希）
        hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
        emb = [((hash_val >> (i * 8)) & 0xFF) / 255.0 for i in range(self._dimensions)]
        norm = math.sqrt(sum(x * x for x in emb))
        return [x / norm for x in emb] if norm > 0 else emb

    def store(
        self,
        content: str,
        interaction_id: str = "",
        pattern_type: PatternType = PatternType.SUCCESS_STRATEGY,
        importance: float = 0.5,
        tags: list[str] | None = None,
        metadata: dict | None = None,
    ) -> str:
        """
        存储经验

        Args:
            content: 经验内容
            interaction_id: 来源交互ID
            pattern_type: 模式类型
            importance: 重要程度
            tags: 标签列表
            metadata: 额外元数据

        Returns:
            经验ID
        """
        exp_id = hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12]
        embedding = self._get_embedding(content)

        experience = Experience(
            id=exp_id,
            content=content,
            embedding=embedding,
            interaction_id=interaction_id,
            pattern_type=pattern_type,
            importance=importance,
            tags=tags or [],
            metadata=metadata or {},
        )

        self._experiences[exp_id] = experience

        # 超过上限时淘汰低重要性的经验
        if len(self._experiences) > self._max_experiences:
            self._evict()

        self._save()
        logger.debug(f"经验已存储: {exp_id}")
        return exp_id

    def store_from_interaction(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> str | None:
        """
        从交互记录存储经验

        Args:
            interaction: 交互记录
            evaluation: 评估结果

        Returns:
            经验ID，如果不符合存储条件则返回None
        """
        # 只存储成功的交互
        if not interaction.success or evaluation.score < 0.6:
            return None

        # 构建经验内容
        content = self._build_experience_content(interaction, evaluation)

        # 确定模式类型
        pattern_type = self._determine_pattern_type(interaction, evaluation)

        # 计算重要性
        importance = self._calculate_importance(interaction, evaluation)

        # 提取标签
        tags = self._extract_tags(interaction, evaluation)

        return self.store(
            content=content,
            interaction_id=interaction.id,
            pattern_type=pattern_type,
            importance=importance,
            tags=tags,
            metadata={
                "evaluation_score": evaluation.score,
                "tools_used": interaction.tools_used,
                "execution_time_ms": interaction.execution_time_ms,
            },
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        pattern_type: PatternType | None = None,
        min_score: float = 0.0,
    ) -> list[tuple[Experience, float]]:
        """
        检索相关经验

        Args:
            query: 查询文本
            top_k: 返回数量
            pattern_type: 模式类型过滤
            min_score: 最低分数阈值

        Returns:
            (经验, 分数) 列表
        """
        query_emb = self._get_embedding(query)

        scored = []
        for exp in self._experiences.values():
            # 类型过滤
            if pattern_type and exp.pattern_type != pattern_type:
                continue

            # 计算相似度
            similarity = self._cosine_similarity(query_emb, exp.embedding)

            # 时间衰减
            age_hours = (time.time() - exp.created_at) / 3600
            time_decay = self._decay_factor**age_hours

            # 使用频率加成
            usage_bonus = min(0.1 * math.log1p(exp.usage_count), 0.2)

            # 综合分数 = 相似度 * 时间衰减 * 重要性 + 使用加成
            score = similarity * time_decay * exp.importance + usage_bonus

            if score >= min_score:
                scored.append((exp, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # 更新使用计数
        for exp, _ in scored[:top_k]:
            exp.usage_count += 1
            exp.last_used = time.time()

        self._save()
        return scored[:top_k]

    def search_by_tags(
        self,
        tags: list[str],
        top_k: int = 10,
    ) -> list[Experience]:
        """
        按标签搜索经验

        Args:
            tags: 标签列表
            top_k: 返回数量

        Returns:
            匹配的经验列表
        """
        results = []
        for exp in self._experiences.values():
            if any(tag in exp.tags for tag in tags):
                results.append(exp)

        # 按重要性和使用次数排序
        results.sort(
            key=lambda e: (e.importance, e.usage_count),
            reverse=True,
        )
        return results[:top_k]

    def get_by_interaction(self, interaction_id: str) -> list[Experience]:
        """
        获取与特定交互关联的经验

        Args:
            interaction_id: 交互ID

        Returns:
            经验列表
        """
        return [exp for exp in self._experiences.values() if exp.interaction_id == interaction_id]

    def delete(self, exp_id: str) -> bool:
        """
        删除经验

        Args:
            exp_id: 经验ID

        Returns:
            是否成功删除
        """
        if exp_id in self._experiences:
            del self._experiences[exp_id]
            self._save()
            return True
        return False

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        type_counts = Counter(exp.pattern_type.value for exp in self._experiences.values())
        tag_counts = Counter(tag for exp in self._experiences.values() for tag in exp.tags)

        return {
            "total_experiences": len(self._experiences),
            "by_type": dict(type_counts),
            "top_tags": dict(tag_counts.most_common(10)),
            "avg_importance": sum(e.importance for e in self._experiences.values()) / len(self._experiences)
            if self._experiences
            else 0,
            "storage_dir": str(self._storage_dir),
        }

    def clear(self) -> None:
        """清空所有经验"""
        self._experiences.clear()
        self._save()

    def _build_experience_content(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> str:
        """构建经验内容"""
        parts = [
            f"查询: {interaction.query}",
            f"工具序列: {' -> '.join(interaction.tools_used) if interaction.tools_used else '无'}",
        ]

        if evaluation.patterns:
            parts.append(f"模式: {', '.join(evaluation.patterns)}")

        if evaluation.improvements:
            parts.append(f"改进: {', '.join(evaluation.improvements[:3])}")

        return "\n".join(parts)

    def _determine_pattern_type(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> PatternType:
        """确定模式类型"""
        if interaction.tools_used:
            return PatternType.TOOL_SEQUENCE
        elif evaluation.patterns:
            return PatternType.QUERY_PATTERN
        elif interaction.error_info:
            return PatternType.ERROR_RECOVERY
        else:
            return PatternType.SUCCESS_STRATEGY

    def _calculate_importance(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> float:
        """计算经验重要性"""
        base = evaluation.score

        # 用户反馈加成
        if interaction.user_feedback:
            if isinstance(interaction.user_feedback, (int, float)):
                base += (interaction.user_feedback - 3) * 0.1

        # 效率加成
        if interaction.execution_time_ms > 0:
            if interaction.execution_time_ms < 1000:
                base += 0.1
            elif interaction.execution_time_ms > 10000:
                base -= 0.1

        return max(0.0, min(1.0, base))

    def _extract_tags(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> list[str]:
        """提取标签"""
        tags = []

        # 工具标签
        for tool in interaction.tools_used:
            tags.append(f"tool:{tool}")

        # 模式标签
        for pattern in evaluation.patterns:
            tags.append(f"pattern:{pattern}")

        # 上下文标签
        for key in interaction.context.keys():
            tags.append(f"context:{key}")

        return list(set(tags))

    def _evict(self) -> None:
        """淘汰低重要性经验"""
        if len(self._experiences) <= self._max_experiences:
            return

        # 按重要性、使用次数和时间排序
        sorted_exps = sorted(
            self._experiences.values(),
            key=lambda e: (
                e.importance * 0.5 + min(e.usage_count / 10, 0.3) + (1 - (time.time() - e.last_used) / 86400 / 30) * 0.2
            ),
        )

        to_remove = len(self._experiences) - self._max_experiences
        for exp in sorted_exps[:to_remove]:
            del self._experiences[exp.id]

        logger.info(f"已淘汰 {to_remove} 条低重要性经验")

    def _save(self) -> None:
        """保存到文件"""
        data = {}
        for exp_id, exp in self._experiences.items():
            data[exp_id] = exp.to_dict()

        file_path = self._storage_dir / "experiences.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存经验失败: {e}")

    def _load(self) -> None:
        """从文件加载"""
        file_path = self._storage_dir / "experiences.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            for exp_id, exp_data in data.items():
                self._experiences[exp_id] = Experience.from_dict(exp_data)

            logger.info(f"已加载 {len(self._experiences)} 条经验")
        except Exception as e:
            logger.warning(f"加载经验失败: {e}")

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算余弦相似度"""
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


# ============================================================================
# 模式库
# ============================================================================


class PatternLibrary:
    """
    模式库

    从成功交互中提取的模式库，支持模式的存储、检索和更新。

    Features:
        - 模式的置信度和使用次数追踪
        - 模式的适用条件管理
        - 自动模式提取
        - 模式匹配和推荐
    """

    def __init__(
        self,
        storage_dir: str | None = None,
        min_confidence: float = 0.3,
        max_patterns: int = 1000,
    ):
        """
        初始化模式库

        Args:
            storage_dir: 存储目录
            min_confidence: 最小置信度阈值
            max_patterns: 最大模式数量
        """
        self._storage_dir = Path(storage_dir or os.path.expanduser("~/.data-ai/memory/patterns"))
        self._min_confidence = min_confidence
        self._max_patterns = max_patterns
        self._patterns: dict[str, Pattern] = {}
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._load()

        logger.info(
            "模式库初始化完成",
            storage_dir=str(self._storage_dir),
            min_confidence=min_confidence,
            max_patterns=max_patterns,
        )

    def add_pattern(
        self,
        name: str,
        description: str,
        pattern_type: PatternType,
        triggers: list[str] | None = None,
        actions: list[dict[str, Any]] | None = None,
        conditions: dict[str, Any] | None = None,
        examples: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        添加模式

        Args:
            name: 模式名称
            description: 模式描述
            pattern_type: 模式类型
            triggers: 触发条件
            actions: 动作序列
            conditions: 适用条件
            examples: 示例列表
            metadata: 额外元数据

        Returns:
            模式ID
        """
        pattern_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:12]

        pattern = Pattern(
            id=pattern_id,
            name=name,
            description=description,
            pattern_type=pattern_type,
            triggers=triggers or [],
            actions=actions or [],
            conditions=conditions or {},
            examples=examples or [],
            metadata=metadata or {},
        )

        self._patterns[pattern_id] = pattern
        self._save()

        logger.info(f"模式已添加: {name} ({pattern_id})")
        return pattern_id

    def extract_from_interaction(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> Pattern | None:
        """
        从交互中提取模式

        Args:
            interaction: 交互记录
            evaluation: 评估结果

        Returns:
            提取的模式，如果无法提取则返回None
        """
        # 只从成功交互中提取
        if not interaction.success or evaluation.score < 0.7:
            return None

        # 提取触发条件
        triggers = self._extract_triggers(interaction.query)
        if not triggers:
            return None

        # 提取动作序列
        actions = self._extract_actions(interaction)
        if not actions:
            return None

        # 生成模式名称和描述
        name = self._generate_pattern_name(interaction, triggers)
        description = self._generate_pattern_description(interaction, evaluation)

        # 确定模式类型
        pattern_type = self._determine_pattern_type(interaction)

        # 提取适用条件
        conditions = self._extract_conditions(interaction, evaluation)

        # 创建模式
        pattern_id = hashlib.md5(f"{name}{time.time()}".encode()).hexdigest()[:12]

        pattern = Pattern(
            id=pattern_id,
            name=name,
            description=description,
            pattern_type=pattern_type,
            triggers=triggers,
            actions=actions,
            conditions=conditions,
            confidence=evaluation.score * 0.8,  # 初始置信度基于评估分数
            examples=[interaction.query[:100]],
        )

        self._patterns[pattern_id] = pattern
        self._save()

        logger.info(f"从交互中提取模式: {name}")
        return pattern

    def find_matching_patterns(
        self,
        query: str,
        context: dict | None = None,
        top_k: int = 5,
        min_confidence: float | None = None,
    ) -> list[tuple[Pattern, float]]:
        """
        查找匹配的模式

        Args:
            query: 用户查询
            context: 上下文信息
            top_k: 返回数量
            min_confidence: 最小置信度阈值

        Returns:
            (模式, 匹配分数) 列表
        """
        min_conf = min_confidence or self._min_confidence

        scored = []
        for pattern in self._patterns.values():
            if pattern.confidence < min_conf:
                continue

            score = pattern.matches(query, context)
            if score > 0:
                # 加入置信度权重
                final_score = score * (0.5 + 0.5 * pattern.confidence)
                scored.append((pattern, final_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get_pattern(self, pattern_id: str) -> Pattern | None:
        """
        获取模式

        Args:
            pattern_id: 模式ID

        Returns:
            模式对象，不存在则返回None
        """
        return self._patterns.get(pattern_id)

    def update_pattern(
        self,
        pattern_id: str,
        success: bool,
    ) -> bool:
        """
        更新模式使用情况

        Args:
            pattern_id: 模式ID
            success: 是否成功

        Returns:
            是否更新成功
        """
        pattern = self._patterns.get(pattern_id)
        if not pattern:
            return False

        pattern.record_usage(success)
        self._save()
        return True

    def delete_pattern(self, pattern_id: str) -> bool:
        """
        删除模式

        Args:
            pattern_id: 模式ID

        Returns:
            是否删除成功
        """
        if pattern_id in self._patterns:
            del self._patterns[pattern_id]
            self._save()
            return True
        return False

    def get_patterns_by_type(
        self,
        pattern_type: PatternType,
    ) -> list[Pattern]:
        """
        按类型获取模式

        Args:
            pattern_type: 模式类型

        Returns:
            模式列表
        """
        return [p for p in self._patterns.values() if p.pattern_type == pattern_type]

    def get_top_patterns(
        self,
        top_n: int = 10,
        by: str = "confidence",
    ) -> list[Pattern]:
        """
        获取顶级模式

        Args:
            top_n: 返回数量
            by: 排序依据 (confidence, usage_count, success_rate)

        Returns:
            模式列表
        """
        if by == "confidence":
            sorted_patterns = sorted(
                self._patterns.values(),
                key=lambda p: p.confidence,
                reverse=True,
            )
        elif by == "usage_count":
            sorted_patterns = sorted(
                self._patterns.values(),
                key=lambda p: p.usage_count,
                reverse=True,
            )
        elif by == "success_rate":
            sorted_patterns = sorted(
                self._patterns.values(),
                key=lambda p: p.success_rate,
                reverse=True,
            )
        else:
            sorted_patterns = list(self._patterns.values())

        return sorted_patterns[:top_n]

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        type_counts = Counter(p.pattern_type.value for p in self._patterns.values())

        return {
            "total_patterns": len(self._patterns),
            "by_type": dict(type_counts),
            "avg_confidence": sum(p.confidence for p in self._patterns.values()) / len(self._patterns)
            if self._patterns
            else 0,
            "avg_success_rate": sum(p.success_rate for p in self._patterns.values()) / len(self._patterns)
            if self._patterns
            else 0,
            "total_usage": sum(p.usage_count for p in self._patterns.values()),
        }

    def clear(self) -> None:
        """清空所有模式"""
        self._patterns.clear()
        self._save()

    def _extract_triggers(self, query: str) -> list[str]:
        """从查询中提取触发条件"""
        triggers = []

        # 提取关键词
        keywords = re.findall(r"\b[a-zA-Z]{3,}\b", query.lower())

        # 过滤常见词
        stop_words = {
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "had",
            "her",
            "was",
            "one",
            "our",
            "out",
        }
        keywords = [k for k in keywords if k not in stop_words]

        # 取前5个关键词
        triggers = keywords[:5]

        return triggers

    def _extract_actions(self, interaction: InteractionRecord) -> list[dict[str, Any]]:
        """从交互中提取动作序列"""
        actions = []

        for i, tool in enumerate(interaction.tools_used):
            actions.append(
                {
                    "step": i + 1,
                    "tool": tool,
                    "description": f"使用 {tool} 工具",
                }
            )

        return actions

    def _extract_conditions(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> dict[str, Any]:
        """提取适用条件"""
        conditions = {}

        # 执行时间条件
        if interaction.execution_time_ms > 0:
            if interaction.execution_time_ms < 2000:
                conditions["expected_time"] = "fast"
            elif interaction.execution_time_ms < 10000:
                conditions["expected_time"] = "medium"
            else:
                conditions["expected_time"] = "slow"

        # 工具数量条件
        if len(interaction.tools_used) > 3:
            conditions["complexity"] = "high"
        elif len(interaction.tools_used) > 1:
            conditions["complexity"] = "medium"
        else:
            conditions["complexity"] = "low"

        return conditions

    def _generate_pattern_name(
        self,
        interaction: InteractionRecord,
        triggers: list[str],
    ) -> str:
        """生成模式名称"""
        if triggers:
            return f"{triggers[0].title()}Pattern_{interaction.id[:4]}"
        return f"Pattern_{interaction.id[:4]}"

    def _generate_pattern_description(
        self,
        interaction: InteractionRecord,
        evaluation: EvaluationResult,
    ) -> str:
        """生成模式描述"""
        parts = [f"处理 '{interaction.query[:50]}...' 的成功模式"]

        if interaction.tools_used:
            parts.append(f"使用工具: {', '.join(interaction.tools_used)}")

        if evaluation.patterns:
            parts.append(f"识别模式: {', '.join(evaluation.patterns)}")

        return ". ".join(parts)

    def _determine_pattern_type(self, interaction: InteractionRecord) -> PatternType:
        """确定模式类型"""
        if len(interaction.tools_used) > 1:
            return PatternType.TOOL_SEQUENCE
        elif interaction.error_info:
            return PatternType.ERROR_RECOVERY
        else:
            return PatternType.SUCCESS_STRATEGY

    def _save(self) -> None:
        """保存到文件"""
        data = {}
        for pattern_id, pattern in self._patterns.items():
            data[pattern_id] = pattern.to_dict()

        file_path = self._storage_dir / "patterns.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存模式失败: {e}")

    def _load(self) -> None:
        """从文件加载"""
        file_path = self._storage_dir / "patterns.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            for pattern_id, pattern_data in data.items():
                self._patterns[pattern_id] = Pattern.from_dict(pattern_data)

            logger.info(f"已加载 {len(self._patterns)} 个模式")
        except Exception as e:
            logger.warning(f"加载模式失败: {e}")


# ============================================================================
# 评估器
# ============================================================================


class BaseEvaluator(ABC):
    """评估器基类"""

    @abstractmethod
    def evaluate(
        self,
        interaction: InteractionRecord,
    ) -> EvaluationResult:
        """
        评估交互

        Args:
            interaction: 交互记录

        Returns:
            评估结果
        """
        pass


class RuleBasedEvaluator(BaseEvaluator):
    """基于规则的评估器"""

    def __init__(self):
        """初始化规则评估器"""
        self._rules: list[Callable[[InteractionRecord], tuple[float, list[str]] | None]] = []
        self._setup_default_rules()

    def _setup_default_rules(self) -> None:
        """设置默认规则"""
        self._rules = [
            self._check_response_length,
            self._check_execution_time,
            self._check_tool_usage,
            self._check_user_feedback,
            self._check_error_info,
        ]

    def evaluate(
        self,
        interaction: InteractionRecord,
    ) -> EvaluationResult:
        """评估交互"""
        scores = []
        issues = []
        improvements = []
        dimension_scores = {}

        # 应用所有规则
        for rule in self._rules:
            result = rule(interaction)
            if result:
                score, rule_issues = result
                scores.append(score)
                issues.extend(rule_issues)

        # 计算各维度分数
        dimension_scores[EvaluationDimension.CORRECTNESS.value] = 1.0 if interaction.success else 0.0
        dimension_scores[EvaluationDimension.EFFICIENCY.value] = self._calculate_efficiency_score(interaction)
        dimension_scores[EvaluationDimension.ERROR_HANDLING.value] = 1.0 if not interaction.error_info else 0.5

        if interaction.user_feedback is not None:
            if isinstance(interaction.user_feedback, (int, float)):
                dimension_scores[EvaluationDimension.USER_SATISFACTION.value] = interaction.user_feedback / 5.0

        # 计算总分
        final_score = sum(scores) / len(scores) if scores else 0.5

        # 生成改进建议
        improvements = self._generate_improvements(interaction, issues)

        return EvaluationResult(
            score=final_score,
            issues=issues,
            improvements=improvements,
            dimension_scores=dimension_scores,
            confidence=0.7,  # 规则评估置信度较低
            reasoning="基于规则的自动评估",
        )

    def _check_response_length(
        self,
        interaction: InteractionRecord,
    ) -> tuple[float, list[str]] | None:
        """检查响应长度"""
        issues = []
        score = 1.0

        if len(interaction.response) < 10:
            issues.append("响应过短")
            score = 0.3
        elif len(interaction.response) < 50:
            issues.append("响应可能不够详细")
            score = 0.7

        return (score, issues) if issues else (1.0, [])

    def _check_execution_time(
        self,
        interaction: InteractionRecord,
    ) -> tuple[float, list[str]] | None:
        """检查执行时间"""
        issues = []
        score = 1.0

        if interaction.execution_time_ms > 30000:
            issues.append("执行时间过长")
            score = 0.5
        elif interaction.execution_time_ms > 10000:
            issues.append("执行时间较长")
            score = 0.7

        return (score, issues) if issues else (1.0, [])

    def _check_tool_usage(
        self,
        interaction: InteractionRecord,
    ) -> tuple[float, list[str]] | None:
        """检查工具使用"""
        issues = []
        score = 1.0

        if not interaction.tools_used and len(interaction.query) > 20:
            issues.append("可能需要使用工具来完成任务")
            score = 0.8

        return (score, issues) if issues else (1.0, [])

    def _check_user_feedback(
        self,
        interaction: InteractionRecord,
    ) -> tuple[float, list[str]] | None:
        """检查用户反馈"""
        issues = []
        score = 1.0

        if interaction.user_feedback is not None:
            if isinstance(interaction.user_feedback, (int, float)):
                if interaction.user_feedback < 2:
                    issues.append("用户反馈较差")
                    score = 0.3
                elif interaction.user_feedback < 3:
                    issues.append("用户反馈一般")
                    score = 0.6

        return (score, issues) if issues else (1.0, [])

    def _check_error_info(
        self,
        interaction: InteractionRecord,
    ) -> tuple[float, list[str]] | None:
        """检查错误信息"""
        issues = []
        score = 1.0

        if interaction.error_info:
            issues.append(f"存在错误: {interaction.error_info[:100]}")
            score = 0.3

        return (score, issues) if issues else (1.0, [])

    def _calculate_efficiency_score(self, interaction: InteractionRecord) -> float:
        """计算效率分数"""
        if interaction.execution_time_ms <= 0:
            return 0.5

        # 基于执行时间的效率评分
        if interaction.execution_time_ms < 1000:
            return 1.0
        elif interaction.execution_time_ms < 5000:
            return 0.8
        elif interaction.execution_time_ms < 10000:
            return 0.6
        elif interaction.execution_time_ms < 30000:
            return 0.4
        else:
            return 0.2

    def _generate_improvements(
        self,
        interaction: InteractionRecord,
        issues: list[str],
    ) -> list[str]:
        """生成改进建议"""
        improvements = []

        if "响应过短" in issues or "响应可能不够详细" in issues:
            improvements.append("考虑提供更详细的响应内容")

        if "执行时间过长" in issues or "执行时间较长" in issues:
            improvements.append("考虑优化执行流程或使用更高效的工具")

        if "存在错误" in str(issues):
            improvements.append("需要改进错误处理机制")

        if interaction.user_feedback is not None:
            if isinstance(interaction.user_feedback, (int, float)) and interaction.user_feedback < 3:
                improvements.append("根据用户反馈调整响应策略")

        return improvements


class LLMEvaluator(BaseEvaluator):
    """基于 LLM 的评估器"""

    def __init__(
        self,
        llm_client: Any | None = None,
        model: str = "gpt-4",
    ):
        """
        初始化 LLM 评估器

        Args:
            llm_client: LLM 客户端
            model: 模型名称
        """
        self._llm_client = llm_client
        self._model = model
        self._rule_evaluator = RuleBasedEvaluator()

    def set_llm_client(self, client: Any) -> None:
        """设置 LLM 客户端"""
        self._llm_client = client

    async def evaluate_async(
        self,
        interaction: InteractionRecord,
    ) -> EvaluationResult:
        """
        异步评估交互

        Args:
            interaction: 交互记录

        Returns:
            评估结果
        """
        # 如果没有 LLM 客户端，使用规则评估
        if not self._llm_client:
            return self._rule_evaluator.evaluate(interaction)

        try:
            prompt = self._build_evaluation_prompt(interaction)
            response = await self._call_llm(prompt)
            return self._parse_llm_response(response, interaction)
        except Exception as e:
            logger.warning(f"LLM 评估失败，回退到规则评估: {e}")
            return self._rule_evaluator.evaluate(interaction)

    def evaluate(
        self,
        interaction: InteractionRecord,
    ) -> EvaluationResult:
        """同步评估（使用规则评估器）"""
        return self._rule_evaluator.evaluate(interaction)

    def _build_evaluation_prompt(self, interaction: InteractionRecord) -> str:
        """构建评估提示"""
        return f"""请评估以下交互的质量：

用户查询：{interaction.query}

系统响应：{interaction.response[:500]}...

使用的工具：{", ".join(interaction.tools_used) if interaction.tools_used else "无"}

执行时间：{interaction.execution_time_ms}ms

是否成功：{"是" if interaction.success else "否"}

{"错误信息：" + interaction.error_info if interaction.error_info else ""}

请从以下维度评估（0-1分）：
1. 正确性：响应是否正确解决了用户的问题
2. 效率：执行时间和资源使用是否合理
3. 完整性：响应是否完整覆盖了用户需求
4. 用户满意度：预计用户对响应的满意程度

请以JSON格式返回评估结果：
{{
    "score": 总分(0-1),
    "issues": ["问题1", "问题2"],
    "improvements": ["改进建议1", "改进建议2"],
    "patterns": ["识别的模式1", "识别的模式2"],
    "reasoning": "评估推理过程"
}}"""

    async def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if hasattr(self._llm_client, "chat"):
            # 假设是 LLMManager
            from .manager import ChatMessage

            messages = [ChatMessage(role="user", content=prompt)]
            response = await self._llm_client.chat(messages, model=self._model)
            return response.content
        else:
            raise ValueError("不支持的 LLM 客户端类型")

    def _parse_llm_response(
        self,
        response: str,
        interaction: InteractionRecord,
    ) -> EvaluationResult:
        """解析 LLM 响应"""
        try:
            # 尝试提取 JSON
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                return EvaluationResult(
                    score=data.get("score", 0.5),
                    issues=data.get("issues", []),
                    improvements=data.get("improvements", []),
                    patterns=data.get("patterns", []),
                    reasoning=data.get("reasoning", ""),
                    confidence=0.9,
                )
        except json.JSONDecodeError:
            pass

        # 解析失败，使用规则评估
        return self._rule_evaluator.evaluate(interaction)


# ============================================================================
# 闭环学习器
# ============================================================================


class FeedbackLoopStatus:
    """反馈循环状态"""

    def __init__(self):
        self.total_interactions: int = 0
        self.successful_interactions: int = 0
        self.failed_interactions: int = 0
        self.patterns_extracted: int = 0
        self.experiences_stored: int = 0
        self.avg_score: float = 0.0
        self.recent_scores: list[float] = []
        self.improvement_trend: str = "stable"  # improving, declining, stable

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_interactions": self.total_interactions,
            "successful_interactions": self.successful_interactions,
            "failed_interactions": self.failed_interactions,
            "success_rate": self.successful_interactions / self.total_interactions
            if self.total_interactions > 0
            else 0,
            "patterns_extracted": self.patterns_extracted,
            "experiences_stored": self.experiences_stored,
            "avg_score": self.avg_score,
            "recent_scores": self.recent_scores[-10:],
            "improvement_trend": self.improvement_trend,
        }


class ClosedLoopLearner:
    """
    闭环学习器

    实现 Hermes 风格的 Execute → Evaluate → Extract → Retrieve 闭环学习流程。

    流程说明：
    1. Execute: 执行交互并记录
    2. Evaluate: 评估交互质量（使用规则+LLM）
    3. Extract: 提取可复用的模式/技能
    4. Retrieve: 检索相关经验用于新查询

    Features:
        - 自动从成功交互中学习
        - 支持多种评估方式
        - 模式自动提取和存储
        - 经验检索和推荐
        - 反馈循环状态追踪
    """

    def __init__(
        self,
        storage_dir: str | None = None,
        evaluator: BaseEvaluator | None = None,
        llm_client: Any | None = None,
    ):
        """
        初始化闭环学习器

        Args:
            storage_dir: 存储目录
            evaluator: 评估器（默认使用规则评估器）
            llm_client: LLM 客户端（用于 LLM 评估）
        """
        self._storage_dir = Path(storage_dir or os.path.expanduser("~/.data-ai/memory/closed_loop"))
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self._experience_store = ExperienceStore(storage_dir=str(self._storage_dir / "experiences"))
        self._pattern_library = PatternLibrary(storage_dir=str(self._storage_dir / "patterns"))
        self._evaluator = evaluator or RuleBasedEvaluator()
        self._llm_evaluator = LLMEvaluator(llm_client) if llm_client else None

        # 交互历史
        self._interaction_history: list[InteractionRecord] = []
        self._evaluation_history: dict[str, EvaluationResult] = {}

        # 反馈循环状态
        self._feedback_status = FeedbackLoopStatus()

        # 加载历史数据
        self._load()

        logger.info(
            "闭环学习器初始化完成",
            storage_dir=str(self._storage_dir),
        )

    def set_llm_client(self, client: Any) -> None:
        """设置 LLM 客户端"""
        self._llm_evaluator = LLMEvaluator(client)

    def set_embed_fn(self, fn: Callable[[str], list[float]]) -> None:
        """设置嵌入函数"""
        self._experience_store.set_embed_fn(fn)

    # ========================================================================
    # Execute: 执行交互并记录
    # ========================================================================

    def execute(
        self,
        query: str,
        response: str,
        tools_used: list[str] | None = None,
        success: bool = True,
        user_feedback: int | float | str | None = None,
        execution_time_ms: float = 0.0,
        context: dict[str, Any] | None = None,
        error_info: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionRecord:
        """
        执行交互并记录

        Args:
            query: 用户查询
            response: 系统响应
            tools_used: 使用的工具列表
            success: 是否成功
            user_feedback: 用户反馈
            execution_time_ms: 执行时间
            context: 上下文信息
            error_info: 错误信息
            metadata: 额外元数据

        Returns:
            交互记录
        """
        interaction = InteractionRecord(
            query=query,
            response=response,
            tools_used=tools_used or [],
            success=success,
            user_feedback=user_feedback,
            execution_time_ms=execution_time_ms,
            context=context or {},
            error_info=error_info,
            metadata=metadata or {},
        )

        # 记录交互
        self._interaction_history.append(interaction)

        # 限制历史长度
        if len(self._interaction_history) > 1000:
            self._interaction_history = self._interaction_history[-500:]

        # 更新状态
        self._feedback_status.total_interactions += 1
        if success:
            self._feedback_status.successful_interactions += 1
        else:
            self._feedback_status.failed_interactions += 1

        self._save()

        logger.debug(
            "交互已记录",
            interaction_id=interaction.id,
            success=success,
            tools_count=len(tools_used or []),
        )

        return interaction

    def record_interaction(
        self,
        interaction: InteractionRecord,
    ) -> None:
        """
        记录已存在的交互

        Args:
            interaction: 交互记录
        """
        self._interaction_history.append(interaction)

        if len(self._interaction_history) > 1000:
            self._interaction_history = self._interaction_history[-500:]

        self._feedback_status.total_interactions += 1
        if interaction.success:
            self._feedback_status.successful_interactions += 1
        else:
            self._feedback_status.failed_interactions += 1

        self._save()

    # ========================================================================
    # Evaluate: 评估交互质量
    # ========================================================================

    def evaluate(
        self,
        interaction: InteractionRecord | str,
    ) -> EvaluationResult:
        """
        评估交互质量

        Args:
            interaction: 交互记录或交互ID

        Returns:
            评估结果
        """
        # 获取交互记录
        if isinstance(interaction, str):
            interaction = self._get_interaction(interaction)
            if not interaction:
                return EvaluationResult(
                    score=0.0,
                    issues=["交互记录不存在"],
                    confidence=0.0,
                )

        # 执行评估
        result = self._evaluator.evaluate(interaction)

        # 存储评估结果
        self._evaluation_history[interaction.id] = result

        # 更新反馈状态
        self._update_feedback_status(result)

        self._save()

        logger.debug(
            "交互已评估",
            interaction_id=interaction.id,
            score=result.score,
            issues_count=len(result.issues),
        )

        return result

    async def evaluate_with_llm(
        self,
        interaction: InteractionRecord | str,
    ) -> EvaluationResult:
        """
        使用 LLM 评估交互质量

        Args:
            interaction: 交互记录或交互ID

        Returns:
            评估结果
        """
        if isinstance(interaction, str):
            interaction = self._get_interaction(interaction)
            if not interaction:
                return EvaluationResult(
                    score=0.0,
                    issues=["交互记录不存在"],
                    confidence=0.0,
                )

        if self._llm_evaluator:
            result = await self._llm_evaluator.evaluate_async(interaction)
        else:
            result = self._evaluator.evaluate(interaction)

        self._evaluation_history[interaction.id] = result
        self._update_feedback_status(result)
        self._save()

        return result

    # ========================================================================
    # Extract: 提取可复用的模式/技能
    # ========================================================================

    def extract(
        self,
        interaction: InteractionRecord | str,
        evaluation: EvaluationResult | None = None,
    ) -> tuple[Experience | None, Pattern | None]:
        """
        提取可复用的模式和经验

        Args:
            interaction: 交互记录或交互ID
            evaluation: 评估结果（可选，如未提供则自动评估）

        Returns:
            (经验, 模式) 元组，可能为None
        """
        # 获取交互记录
        if isinstance(interaction, str):
            interaction = self._get_interaction(interaction)
            if not interaction:
                return (None, None)

        # 获取或执行评估
        if evaluation is None:
            evaluation = self._evaluation_history.get(interaction.id)
            if evaluation is None:
                evaluation = self.evaluate(interaction)

        # 提取经验
        experience = None
        if evaluation.is_successful:
            exp_id = self._experience_store.store_from_interaction(interaction, evaluation)
            if exp_id:
                experience = self._experience_store._experiences.get(exp_id)
                self._feedback_status.experiences_stored += 1

        # 提取模式
        pattern = None
        if evaluation.score >= 0.7:
            pattern = self._pattern_library.extract_from_interaction(interaction, evaluation)
            if pattern:
                self._feedback_status.patterns_extracted += 1

        self._save()

        logger.debug(
            "提取完成",
            interaction_id=interaction.id,
            has_experience=experience is not None,
            has_pattern=pattern is not None,
        )

        return (experience, pattern)

    def extract_batch(
        self,
        min_score: float = 0.6,
        limit: int = 100,
    ) -> dict[str, tuple[Experience | None, Pattern | None]]:
        """
        批量提取模式和经验

        Args:
            min_score: 最低评估分数阈值
            limit: 最大处理数量

        Returns:
            {交互ID: (经验, 模式)} 字典
        """
        results = {}

        for interaction in self._interaction_history[-limit:]:
            evaluation = self._evaluation_history.get(interaction.id)
            if evaluation and evaluation.score >= min_score:
                results[interaction.id] = self.extract(interaction, evaluation)

        return results

    # ========================================================================
    # Retrieve: 检索相关经验用于新查询
    # ========================================================================

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_patterns: bool = True,
    ) -> dict[str, Any]:
        """
        检索相关经验和模式

        Args:
            query: 用户查询
            top_k: 返回数量
            include_patterns: 是否包含模式

        Returns:
            检索结果字典
        """
        result = {
            "experiences": [],
            "patterns": [],
            "suggestions": [],
        }

        # 检索经验
        experiences = self._experience_store.retrieve(query, top_k=top_k)
        result["experiences"] = [
            {
                "content": exp.content,
                "score": score,
                "pattern_type": exp.pattern_type.value,
                "tags": exp.tags,
            }
            for exp, score in experiences
        ]

        # 检索模式
        if include_patterns:
            patterns = self._pattern_library.find_matching_patterns(query, top_k=top_k)
            result["patterns"] = [
                {
                    "name": p.name,
                    "description": p.description,
                    "confidence": p.confidence,
                    "match_score": score,
                    "actions": p.actions,
                }
                for p, score in patterns
            ]

        # 生成建议
        result["suggestions"] = self._generate_suggestions(query, experiences, patterns if include_patterns else [])

        logger.debug(
            "检索完成",
            query=query[:50],
            experiences_count=len(result["experiences"]),
            patterns_count=len(result["patterns"]),
        )

        return result

    def get_recommended_tools(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """
        获取推荐工具

        Args:
            query: 用户查询
            top_k: 返回数量

        Returns:
            (工具名, 置信度) 列表
        """
        tool_scores: Counter = Counter()

        # 从经验中提取工具
        experiences = self._experience_store.retrieve(query, top_k=top_k * 2)
        for exp, score in experiences:
            tools = exp.metadata.get("tools_used", [])
            for tool in tools:
                tool_scores[tool] += score

        # 从模式中提取工具
        patterns = self._pattern_library.find_matching_patterns(query, top_k=top_k)
        for pattern, score in patterns:
            for action in pattern.actions:
                tool = action.get("tool")
                if tool:
                    tool_scores[tool] += score * pattern.confidence

        return tool_scores.most_common(top_k)

    # ========================================================================
    # 反馈循环状态
    # ========================================================================

    def get_feedback_loop(self) -> FeedbackLoopStatus:
        """
        获取反馈循环状态

        Returns:
            反馈循环状态对象
        """
        return self._feedback_status

    def get_learning_stats(self) -> dict[str, Any]:
        """
        获取学习统计信息

        Returns:
            统计信息字典
        """
        return {
            "feedback_loop": self._feedback_status.to_dict(),
            "experience_store": self._experience_store.get_stats(),
            "pattern_library": self._pattern_library.get_stats(),
            "interaction_history_size": len(self._interaction_history),
            "evaluation_history_size": len(self._evaluation_history),
        }

    # ========================================================================
    # 辅助方法
    # ========================================================================

    def _get_interaction(self, interaction_id: str) -> InteractionRecord | None:
        """获取交互记录"""
        for interaction in self._interaction_history:
            if interaction.id == interaction_id:
                return interaction
        return None

    def _update_feedback_status(self, result: EvaluationResult) -> None:
        """更新反馈状态"""
        self._feedback_status.recent_scores.append(result.score)

        # 保留最近100个分数
        if len(self._feedback_status.recent_scores) > 100:
            self._feedback_status.recent_scores = self._feedback_status.recent_scores[-100:]

        # 计算平均分
        self._feedback_status.avg_score = sum(self._feedback_status.recent_scores) / len(
            self._feedback_status.recent_scores
        )

        # 计算趋势
        if len(self._feedback_status.recent_scores) >= 10:
            recent = self._feedback_status.recent_scores[-5:]
            earlier = self._feedback_status.recent_scores[-10:-5]

            recent_avg = sum(recent) / len(recent)
            earlier_avg = sum(earlier) / len(earlier)

            if recent_avg > earlier_avg + 0.05:
                self._feedback_status.improvement_trend = "improving"
            elif recent_avg < earlier_avg - 0.05:
                self._feedback_status.improvement_trend = "declining"
            else:
                self._feedback_status.improvement_trend = "stable"

    def _generate_suggestions(
        self,
        query: str,
        experiences: list[tuple[Experience, float]],
        patterns: list[tuple[Pattern, float]],
    ) -> list[str]:
        """生成建议"""
        suggestions = []

        # 基于经验的建议
        if experiences:
            top_exp = experiences[0][0]
            if top_exp.metadata.get("tools_used"):
                suggestions.append(f"考虑使用工具: {', '.join(top_exp.metadata['tools_used'])}")

        # 基于模式的建议
        if patterns:
            top_pattern = patterns[0][0]
            suggestions.append(f"可能适用的模式: {top_pattern.name}")

        # 基于历史的建议
        similar_interactions = [
            i for i in self._interaction_history if i.success and any(t in query.lower() for t in i.tools_used)
        ]
        if similar_interactions:
            suggestions.append(f"历史上有 {len(similar_interactions)} 个类似的成功交互")

        return suggestions[:5]

    def _save(self) -> None:
        """保存数据"""
        data = {
            "interaction_history": [i.to_dict() for i in self._interaction_history[-200:]],
            "evaluation_history": {k: v.to_dict() for k, v in list(self._evaluation_history.items())[-200:]},
            "feedback_status": self._feedback_status.to_dict(),
        }

        file_path = self._storage_dir / "closed_loop.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存闭环学习数据失败: {e}")

    def _load(self) -> None:
        """加载数据"""
        file_path = self._storage_dir / "closed_loop.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            self._interaction_history = [InteractionRecord.from_dict(i) for i in data.get("interaction_history", [])]

            self._evaluation_history = {
                k: EvaluationResult.from_dict(v) for k, v in data.get("evaluation_history", {}).items()
            }

            # 恢复反馈状态
            status_data = data.get("feedback_status", {})
            self._feedback_status.total_interactions = status_data.get("total_interactions", 0)
            self._feedback_status.successful_interactions = status_data.get("successful_interactions", 0)
            self._feedback_status.failed_interactions = status_data.get("failed_interactions", 0)
            self._feedback_status.patterns_extracted = status_data.get("patterns_extracted", 0)
            self._feedback_status.experiences_stored = status_data.get("experiences_stored", 0)
            self._feedback_status.avg_score = status_data.get("avg_score", 0.0)
            self._feedback_status.recent_scores = status_data.get("recent_scores", [])
            self._feedback_status.improvement_trend = status_data.get("improvement_trend", "stable")

            logger.info(
                "闭环学习数据已加载",
                interactions=len(self._interaction_history),
                evaluations=len(self._evaluation_history),
            )
        except Exception as e:
            logger.warning(f"加载闭环学习数据失败: {e}")

    def clear(self) -> None:
        """清空所有数据"""
        self._interaction_history.clear()
        self._evaluation_history.clear()
        self._experience_store.clear()
        self._pattern_library.clear()
        self._feedback_status = FeedbackLoopStatus()
        self._save()


# ============================================================================
# 便捷函数
# ============================================================================


_learner: ClosedLoopLearner | None = None


def get_closed_loop_learner() -> ClosedLoopLearner:
    """获取全局闭环学习器实例"""
    global _learner
    if _learner is None:
        _learner = ClosedLoopLearner()
    return _learner


def create_closed_loop_learner(
    storage_dir: str | None = None,
    llm_client: Any | None = None,
) -> ClosedLoopLearner:
    """创建新的闭环学习器实例"""
    return ClosedLoopLearner(storage_dir=storage_dir, llm_client=llm_client)
