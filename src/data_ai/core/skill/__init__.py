"""
DATA-AI 技能系统

提供技能的定义、存储、提炼和复用能力。
参考 Hermes Agent 的技能管理机制。

本模块暴露两类技能定义：
- :class:`LegacySkill`: 旧版完整技能（包含触发条件、步骤等），定义在 :mod:`.skill`
- :class:`Skill`: 面向运行时调度的精简版本，定义在 :mod:`.manager`
- :class:`SkillManager`: 统一技能管理器
"""

from .executor import SkillExecutor
from .extractor import SkillExtractor
from .manager import Skill, SkillManager
from .skill import (
    Skill as LegacySkill,
)
from .skill import (
    SkillCategory,
    SkillLevel,
    SkillMetadata,
    SkillStep,
)

__all__ = [
    # 新版
    "Skill",
    "SkillManager",
    # 旧版（向后兼容，导出时使用 LegacySkill 别名）
    "LegacySkill",
    "SkillStep",
    "SkillLevel",
    "SkillCategory",
    "SkillMetadata",
    # 其它
    "SkillExtractor",
    "SkillExecutor",
]
