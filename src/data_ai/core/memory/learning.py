"""
自我学习机制

从交互中学习模式、偏好和经验。
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LearningRecord:
    """学习记录"""

    pattern: str
    category: str
    frequency: int = 1
    last_seen: float = field(default_factory=time.time)
    success_rate: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class LearningEngine:
    """
    自我学习引擎

    支持多种学习模式：
    - 交互学习：从成功/失败交互中学习模式
    - 错误学习：记录错误类型和上下文
    - 偏好学习：学习用户偏好（语言/格式/风格）
    - 模式识别：识别重复出现的模式
    """

    def __init__(self, storage_dir: str | None = None):
        self._storage_dir = Path(storage_dir or os.path.expanduser("~/.data-ai/memory/learning"))
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._patterns: dict[str, LearningRecord] = {}
        self._preferences: dict[str, str] = {}
        self._error_patterns: dict[str, list[dict]] = {}
        self._interaction_history: list[dict] = []
        self._load()

    def learn_from_interaction(
        self,
        query: str,
        response: str,
        success: bool = True,
        tools_used: list[str] | None = None,
        execution_time_ms: float = 0,
    ) -> None:
        """从交互中学习"""
        # 提取模式
        pattern = self._extract_pattern(query)

        if pattern:
            if pattern not in self._patterns:
                self._patterns[pattern] = LearningRecord(
                    pattern=pattern,
                    category="interaction",
                )

            record = self._patterns[pattern]
            record.frequency += 1
            record.last_seen = time.time()

            # 更新成功率（指数移动平均）
            alpha = 0.3
            record.success_rate = alpha * (1.0 if success else 0.0) + (1 - alpha) * record.success_rate

            if tools_used:
                record.metadata["common_tools"] = tools_used

            record.metadata["avg_time_ms"] = (
                record.metadata.get("avg_time_ms", execution_time_ms) * 0.7 + execution_time_ms * 0.3
            )

        # 记录交互历史
        self._interaction_history.append(
            {
                "query": query[:200],
                "success": success,
                "timestamp": time.time(),
                "tools_used": tools_used or [],
            }
        )

        # 限制历史长度
        if len(self._interaction_history) > 1000:
            self._interaction_history = self._interaction_history[-500:]

        self._save()

    def learn_from_error(self, error: str, context: str = "", tool: str = "") -> None:
        """从错误中学习"""
        error_type = self._classify_error(error)

        if error_type not in self._error_patterns:
            self._error_patterns[error_type] = []

        self._error_patterns[error_type].append(
            {
                "error": error[:500],
                "context": context[:500],
                "tool": tool,
                "timestamp": time.time(),
            }
        )

        # 限制每个错误类型的记录数
        if len(self._error_patterns[error_type]) > 50:
            self._error_patterns[error_type] = self._error_patterns[error_type][-25:]

        logger.info(f"错误学习: {error_type} - {error[:100]}")
        self._save()

    def learn_preference(self, key: str, value: str) -> None:
        """学习用户偏好"""
        self._preferences[key] = value
        logger.info(f"偏好学习: {key} = {value}")
        self._save()

    def get_preference(self, key: str, default: str = "") -> str:
        """获取用户偏好"""
        return self._preferences.get(key, default)

    def get_suggestions(self, query: str) -> list[dict[str, Any]]:
        """基于学习到的模式给出建议"""
        suggestions = []
        pattern = self._extract_pattern(query)

        if pattern and pattern in self._patterns:
            record = self._patterns[pattern]
            suggestions.append(
                {
                    "type": "pattern_match",
                    "pattern": pattern,
                    "frequency": record.frequency,
                    "success_rate": record.success_rate,
                    "suggested_tools": record.metadata.get("common_tools", []),
                    "estimated_time_ms": record.metadata.get("avg_time_ms", 0),
                }
            )

        # 检查可能的错误
        for error_type, records in self._error_patterns.items():
            if error_type.lower() in query.lower():
                suggestions.append(
                    {
                        "type": "error_warning",
                        "error_type": error_type,
                        "occurrences": len(records),
                        "last_error": records[-1]["error"] if records else "",
                    }
                )

        return suggestions

    def get_common_tools(self, top_n: int = 5) -> list[tuple]:
        """获取最常用的工具"""
        tool_counter = Counter()
        for interaction in self._interaction_history:
            for tool in interaction.get("tools_used", []):
                tool_counter[tool] += 1
        return tool_counter.most_common(top_n)

    def get_success_rate(self) -> float:
        """获取总体成功率"""
        if not self._interaction_history:
            return 0.0
        successful = sum(1 for i in self._interaction_history if i["success"])
        return successful / len(self._interaction_history)

    def get_stats(self) -> dict[str, Any]:
        """获取学习统计"""
        return {
            "total_patterns": len(self._patterns),
            "total_preferences": len(self._preferences),
            "total_error_types": len(self._error_patterns),
            "total_interactions": len(self._interaction_history),
            "success_rate": self.get_success_rate(),
            "common_tools": self.get_common_tools(5),
        }

    def _extract_pattern(self, text: str) -> str:
        """从文本中提取模式"""
        # 简单模式提取：移除具体参数，保留结构
        pattern = text.lower().strip()
        # 移除数字
        pattern = re.sub(r"\b\d+\b", "<N>", pattern)
        # 移除文件路径
        pattern = re.sub(r"\b[\w/\\.-]+\.\w+\b", "<FILE>", pattern)
        # 移除引号内容
        pattern = re.sub(r'["\'][^"\']*["\']', "<STR>", pattern)
        # 截断
        return pattern[:100]

    def _classify_error(self, error: str) -> str:
        """分类错误类型"""
        error_lower = error.lower()

        if "file not found" in error_lower or "no such file" in error_lower:
            return "file_not_found"
        elif "permission" in error_lower or "access denied" in error_lower:
            return "permission_error"
        elif "timeout" in error_lower or "timed out" in error_lower:
            return "timeout"
        elif "syntax" in error_lower or "parse" in error_lower:
            return "syntax_error"
        elif "import" in error_lower or "module" in error_lower:
            return "import_error"
        elif "connection" in error_lower or "network" in error_lower:
            return "network_error"
        elif "api" in error_lower or "key" in error_lower:
            return "api_error"
        elif "memory" in error_lower or "out of memory" in error_lower:
            return "memory_error"
        else:
            return "unknown_error"

    def _save(self) -> None:
        """保存学习数据"""
        data = {
            "patterns": {
                k: {
                    "pattern": v.pattern,
                    "category": v.category,
                    "frequency": v.frequency,
                    "last_seen": v.last_seen,
                    "success_rate": v.success_rate,
                    "metadata": v.metadata,
                }
                for k, v in self._patterns.items()
            },
            "preferences": self._preferences,
            "error_patterns": self._error_patterns,
            "interaction_history": self._interaction_history[-200:],  # 只保存最近200条
        }

        file_path = self._storage_dir / "learning.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        """加载学习数据"""
        file_path = self._storage_dir / "learning.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            for k, v in data.get("patterns", {}).items():
                self._patterns[k] = LearningRecord(
                    pattern=v["pattern"],
                    category=v.get("category", "interaction"),
                    frequency=v.get("frequency", 1),
                    last_seen=v.get("last_seen", time.time()),
                    success_rate=v.get("success_rate", 1.0),
                    metadata=v.get("metadata", {}),
                )

            self._preferences = data.get("preferences", {})
            self._error_patterns = data.get("error_patterns", {})
            self._interaction_history = data.get("interaction_history", [])

            logger.info(f"学习数据已加载: {len(self._patterns)} 模式, {len(self._preferences)} 偏好")
        except Exception as e:
            logger.warning(f"加载学习数据失败: {e}")
