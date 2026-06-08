"""
技能管理器（SkillManager）

为 Agent 提供技能的注册、检索、匹配、持久化和导入导出能力。
设计上以 ``name`` 作为主键，同时也支持按 ``id`` 检索（兼容旧 API）。

存储策略：
- 以原始对象（:class:`Skill` / :class:`data_ai.core.skill.skill.Skill`）存放在
  ``_skills`` 字典中，不做类型转换 —— 这样既保留旧版 dataclass 的 ``id`` /
  ``category`` / ``triggers`` 等字段，又兼容新版轻量级 :class:`Skill`。
- 对外提供一致的属性访问（``name``、``tags``、``description``、``content``、
  ``usage_count`` 等），缺失字段时使用 ``getattr(..., default)``。
"""

from __future__ import annotations

import json
import re
import time
import uuid
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


# ─── 数据类 ────────────────────────────────────────────────────────────────


@dataclass
class Skill:
    """
    技能定义（轻量级版本）。

    与 ``core.skill.skill.Skill`` 不同，此处是面向运行时调度的精简模型：
    - 以 ``name`` 作为唯一主键
    - ``content`` 为技能主体（Markdown / 自然语言描述）
    - ``parameters_schema`` 为 JSON Schema 风格的参数定义
    - ``enabled`` 用于启用/禁用
    - ``usage_count`` 由 :meth:`SkillManager.update_usage` 累加
    - ``id`` 可选：旧版 / 外部系统可能依赖 ``id`` 字段
    """

    name: str
    description: str = ""
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    content: str = ""
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    examples: list[str] = field(default_factory=list)
    enabled: bool = True
    usage_count: int = 0
    id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())
    updated_at: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Skill:
        if not isinstance(data, dict):
            raise TypeError(f"Skill.from_dict 需要 dict，实际为 {type(data).__name__}")
        return cls(
            id=str(data.get("id", "") or ""),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            version=str(data.get("version", "1.0.0")),
            tags=list(data.get("tags", []) or []),
            content=str(data.get("content", "")),
            parameters_schema=dict(data.get("parameters_schema", {}) or {}),
            examples=list(data.get("examples", []) or []),
            enabled=bool(data.get("enabled", True)),
            usage_count=int(data.get("usage_count", 0) or 0),
            metadata=dict(data.get("metadata", {}) or {}),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
        )


# ─── 文本相关性辅助 ────────────────────────────────────────────────────────


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]+", re.UNICODE)
_STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "of",
    "to",
    "in",
    "on",
    "and",
    "or",
    "for",
    "with",
    "as",
    "by",
    "at",
    "from",
}


def _tokenize(text: str) -> list[str]:
    """
    分词：将英文 / 数字 单词和连续中文段分别作为独立 token。

    适合中英文混合场景；对纯中文文本，连续的中文段会作为一个 token。
    """
    if not text:
        return []
    raw_tokens = [t.lower() for t in _TOKEN_RE.findall(text)]
    result: list[str] = []
    for token in raw_tokens:
        if not token or len(token) <= 1:
            continue
        if token in _STOPWORDS:
            continue
        result.append(token)
    return result


def _chinese_substrings(text: str, min_len: int = 2, max_len: int = 4) -> list[str]:
    """
    提取中文文本的所有 ``[min_len, max_len]`` 长度的子串，用于模糊匹配。
    """
    if not text:
        return []
    cjk_chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
    if not cjk_chars:
        return []
    cjk_text = "".join(cjk_chars)
    seen: set = set()
    result: list[str] = []
    for n in range(min_len, min(max_len, len(cjk_text)) + 1):
        for i in range(len(cjk_text) - n + 1):
            sub = cjk_text[i : i + n]
            if sub not in seen:
                seen.add(sub)
                result.append(sub)
    return result


def _score_text(query_tokens: list[str], text: str) -> float:
    if not query_tokens or not text:
        return 0.0
    text_lower = text.lower()
    text_tokens = _tokenize(text)
    token_counts = Counter(text_tokens)
    total_tokens = max(sum(token_counts.values()), 1)

    score = 0.0
    for token in query_tokens:
        if token in text_lower:
            tf = token_counts.get(token, 0)
            tf_component = 1.0 + (1.0 if tf > 0 else 0.0)
            idf_like = 1.0 / (1.0 + tf / total_tokens)
            score += 0.5 * tf_component * (1.0 - idf_like) + 0.1
    return score


def _skill_attr(skill: Any, name: str, default: Any = None) -> Any:
    """统一获取 ``Skill`` 的属性，兼容旧版 dataclass / 新版 / dict。"""
    if isinstance(skill, dict):
        return skill.get(name, default)
    if hasattr(skill, name):
        value = getattr(skill, name)
        if value is None:
            return default
        return value
    return default


# ─── 主类 ──────────────────────────────────────────────────────────────────


class SkillManager:
    """
    技能管理器。

    内部以 ``id``（若存在） 或 ``name`` 作为存储键，原样保存传入的对象。
    同时维护 ``name -> id`` 反向索引，方法 ``get_skill`` / ``unregister_skill``
    可以同时按 ``id`` 与 ``name`` 查找。

    Example:
        >>> manager = SkillManager()
        >>> skill = Skill(name="hello", description="Say hi", content="print('hi')")
        >>> manager.register_skill(skill)
        True
        >>> manager.match("say hello")
        [(Skill(name='hello', ...), 0.6)]
    """

    DEFAULT_DIR_NAME = "skills"

    def __init__(self, storage_dir: str | None = None) -> None:
        self._storage_dir: Path = Path(storage_dir).expanduser() if storage_dir else Path.home() / ".data-ai" / "skills"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        # id -> Skill (原样存储)
        self._skills: dict[str, Any] = {}
        # name -> id
        self._name_to_id: dict[str, str] = {}
        self._load_from_directory(self._storage_dir)

    # ─── 基础属性 ─────────────────────────────────────────────────────

    @property
    def storage_dir(self) -> Path:
        """持久化目录。"""
        return self._storage_dir

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, key: str) -> bool:
        return self._resolve_key(key) is not None

    # ─── 注册 / 注销 ─────────────────────────────────────────────────

    def register_skill(self, skill: Any) -> bool:
        """
        注册一个技能（新版 :class:`Skill` / 旧版 dataclass / dict 都支持）。
        """
        if not self._is_valid_skill(skill):
            logger.error(f"register_skill 需要 Skill / dict / 旧版 dataclass，得到 {type(skill).__name__}")
            return False

        name = str(_skill_attr(skill, "name", "") or "")
        if not name.strip():
            logger.error("Skill.name 不能为空")
            return False

        key = self._compute_key(skill)
        # 设置 updated_at（如果对象有该属性）
        if hasattr(skill, "updated_at") and not isinstance(skill, dict):
            try:
                skill.updated_at = time.time()
            except Exception:
                pass
        if key in self._skills:
            logger.info(f"覆盖已存在的技能: {key}")
        old = self._skills.get(key)
        if old is not None:
            old_name = str(_skill_attr(old, "name", "") or "")
            if old_name and old_name != name:
                self._name_to_id.pop(old_name, None)
        self._skills[key] = skill
        self._name_to_id[name] = key
        # 仅当对象是我们自己的新版 Skill 时才持久化
        if isinstance(skill, Skill):
            self._persist_skill(skill)
        return True

    def unregister_skill(self, name_or_id: str) -> bool:
        """注销（删除）一个技能。"""
        skill, key = self._find(name_or_id)
        if not skill or not key:
            return False
        del self._skills[key]
        name = str(_skill_attr(skill, "name", "") or "")
        self._name_to_id.pop(name, None)
        # 删除持久化文件
        if isinstance(skill, Skill):
            skill_file = self._storage_dir / f"{self._safe_filename(name)}.json"
            try:
                if skill_file.exists():
                    skill_file.unlink()
            except OSError as exc:
                logger.warning(f"删除技能文件失败 {skill_file}: {exc}")
        return True

    # ─── 查询 ────────────────────────────────────────────────────────

    def get_skill(self, name_or_id: str) -> Any | None:
        """按 ``id`` 或 ``name`` 获取技能。"""
        skill, _ = self._find(name_or_id)
        return skill

    def list_skills(
        self,
        *,
        enabled_only: bool = False,
        tags: Iterable[str] | None = None,
        category: Any = None,
    ) -> list[Any]:
        """
        列出技能。

        Args:
            enabled_only: 仅返回启用的技能（仅对新版 Skill 生效）。
            tags: 给定标签时，仅返回包含**任一**标签的技能。
                标签既可以是新版 ``Skill.tags``，也可以是旧版
                ``Skill.metadata.tags``。
            category: 兼容旧版 API，按 ``Skill.category`` 或
                ``Skill.metadata.category`` 过滤，可传入枚举或字符串。
        """
        tag_filter = set(tags) if tags else None
        category_str: str | None = None
        if category is not None:
            category_str = category.value if hasattr(category, "value") else str(category)

        results: list[Any] = []
        for skill in self._skills.values():
            if enabled_only and not _skill_attr(skill, "enabled", True):
                continue
            skill_tags = set(self._get_skill_tags(skill))
            if tag_filter and not (tag_filter & skill_tags):
                continue
            if category_str:
                cat = _skill_attr(skill, "category", None)
                if cat is not None:
                    if hasattr(cat, "value"):
                        cat = cat.value
                    if str(cat) != category_str:
                        continue
                else:
                    meta = _skill_attr(skill, "metadata", {}) or {}
                    if isinstance(meta, dict) and str(meta.get("category", "")) != category_str:
                        continue
            results.append(skill)
        return results

    def list_skill_names(self, *, enabled_only: bool = False) -> list[str]:
        return [
            str(_skill_attr(s, "name", ""))
            for s in self._skills.values()
            if not enabled_only or _skill_attr(s, "enabled", True)
        ]

    def filter_by_tags(self, tags: list[str]) -> list[Any]:
        if not tags:
            return self.list_skills()
        tag_set = {t.strip() for t in tags if t and t.strip()}
        if not tag_set:
            return self.list_skills()
        return [s for s in self._skills.values() if tag_set & set(self._get_skill_tags(s))]

    def _get_skill_tags(self, skill: Any) -> list[str]:
        """
        提取技能的所有标签：兼容旧版 ``metadata.tags``（dataclass）
        与新版 ``tags``（list）。
        """
        tags: list[str] = []
        # 1) 新版 Skill.tags
        direct = _skill_attr(skill, "tags", None)
        if direct:
            tags.extend(list(direct))
        # 2) 旧版 Skill.metadata.tags（可能是 dataclass 或 dict）
        meta = _skill_attr(skill, "metadata", None)
        if meta is not None:
            if hasattr(meta, "tags"):
                tags.extend(list(getattr(meta, "tags", []) or []))
            elif isinstance(meta, dict):
                tags.extend(list(meta.get("tags", []) or []))
        # 3) 旧版 triggers
        triggers = _skill_attr(skill, "triggers", None)
        if triggers:
            tags.extend(list(triggers))
        # 去重并保留顺序
        seen: set = set()
        result: list[str] = []
        for tag in tags:
            if tag and tag not in seen:
                seen.add(tag)
                result.append(tag)
        return result

    def _get_skill_triggers(self, skill: Any) -> list[str]:
        """提取技能的 triggers，兼容旧版直接属性与新版 metadata。"""
        triggers = _skill_attr(skill, "triggers", None)
        if triggers:
            return list(triggers)
        meta = _skill_attr(skill, "metadata", {}) or {}
        if isinstance(meta, dict):
            return list(meta.get("triggers", []) or [])
        return []

    def _get_skill_success_patterns(self, skill: Any) -> list[str]:
        patterns = _skill_attr(skill, "success_patterns", None)
        if patterns:
            return list(patterns)
        meta = _skill_attr(skill, "metadata", {}) or {}
        if isinstance(meta, dict):
            return list(meta.get("success_patterns", []) or [])
        return []

    def match(self, query: str, top_k: int = 5) -> list[tuple[Any, float]]:
        """
        关键词相关度匹配。评分字段：
        - name: 3.0
        - tags / triggers: 2.0
        - description: 1.0
        - content / success_patterns: 0.5
        - examples: 0.5
        - 中文子串匹配：+ 1.5（处理中文无显式分词的情况）
        """
        if not query or not query.strip():
            return []
        query_tokens = _tokenize(query)
        # 对中文部分再生成短子串，以应对无分词场景
        query_substrings = _chinese_substrings(query)

        scored: list[tuple[Any, float]] = []
        for skill in self._skills.values():
            if not _skill_attr(skill, "enabled", True):
                continue
            score = 0.0
            score += 3.0 * _score_text(query_tokens, str(_skill_attr(skill, "name", "") or ""))
            score += 2.0 * _score_text(query_tokens, " ".join(self._get_skill_tags(skill)))
            score += 1.0 * _score_text(query_tokens, str(_skill_attr(skill, "description", "") or ""))
            score += 0.5 * _score_text(query_tokens, str(_skill_attr(skill, "content", "") or ""))
            score += 0.5 * _score_text(query_tokens, " ".join(_skill_attr(skill, "examples", []) or []))
            triggers_text = " ".join(self._get_skill_triggers(skill))
            success_patterns_text = " ".join(self._get_skill_success_patterns(skill))
            score += 2.0 * _score_text(query_tokens, triggers_text)
            score += 0.5 * _score_text(query_tokens, success_patterns_text)
            # 中文子串匹配（任意 2-4 字子串命中即加分）
            if query_substrings:
                for substr in query_substrings:
                    if substr in triggers_text or substr in str(_skill_attr(skill, "name", "") or ""):
                        score += 1.5
                        break
                    if substr in str(_skill_attr(skill, "description", "") or ""):
                        score += 1.0
                        break
            if score > 0:
                scored.append((skill, score))

        scored.sort(
            key=lambda item: (item[1], _skill_attr(item[0], "usage_count", 0)),
            reverse=True,
        )
        return scored[: max(0, top_k)]

    # ─── 启用 / 禁用 / 使用统计 ─────────────────────────────────────

    def enable_skill(self, name_or_id: str) -> bool:
        skill, _ = self._find(name_or_id)
        if not skill:
            return False
        if isinstance(skill, dict):
            skill["enabled"] = True
            return True
        if hasattr(skill, "enabled"):
            skill.enabled = True
        if hasattr(skill, "updated_at"):
            try:
                skill.updated_at = time.time()
            except Exception:
                pass
        if isinstance(skill, Skill):
            self._persist_skill(skill)
        return True

    def disable_skill(self, name_or_id: str) -> bool:
        skill, _ = self._find(name_or_id)
        if not skill:
            return False
        if isinstance(skill, dict):
            skill["enabled"] = False
            return True
        if hasattr(skill, "enabled"):
            skill.enabled = False
        if hasattr(skill, "updated_at"):
            try:
                skill.updated_at = time.time()
            except Exception:
                pass
        if isinstance(skill, Skill):
            self._persist_skill(skill)
        return True

    def update_usage(
        self,
        name_or_id: str,
        success: bool = True,
        execution_time_ms: float = 0.0,
    ) -> None:
        """
        累加技能使用次数；可选地更新成功率与平均耗时。

        - 新版 :class:`Skill`：更新 ``usage_count`` 字段 + ``metadata`` 中的统计
        - 旧版 dataclass：更新 ``metadata.usage_count`` / ``success_rate`` / ``avg_execution_time_ms``
        """
        skill, _ = self._find(name_or_id)
        if not skill:
            return
        # 旧版 dataclass
        if not isinstance(skill, Skill) and hasattr(skill, "metadata") and hasattr(skill.metadata, "usage_count"):
            skill.metadata.usage_count += 1
            if execution_time_ms and execution_time_ms > 0:
                prev = float(getattr(skill.metadata, "avg_execution_time_ms", 0.0))
                new_avg = (
                    prev * (skill.metadata.usage_count - 1) + float(execution_time_ms)
                ) / skill.metadata.usage_count
                skill.metadata.avg_execution_time_ms = new_avg
            if success:
                # 简化：success_rate 按调用计数等比更新
                prev_success = float(getattr(skill.metadata, "success_rate", 0.0))
                prev_total = skill.metadata.usage_count
                new_total = prev_total
                # 假设之前 success_total 比例 = prev_success
                new_success = int(prev_success * (new_total - 1)) + 1
                skill.metadata.success_rate = new_success / new_total
            return
        # 新版 Skill
        if isinstance(skill, Skill):
            skill.usage_count += 1
            if execution_time_ms and execution_time_ms > 0:
                prev_total = float(skill.metadata.get("total_execution_time_ms", 0.0))
                skill.metadata["total_execution_time_ms"] = prev_total + float(execution_time_ms)
                skill.metadata["avg_execution_time_ms"] = skill.metadata["total_execution_time_ms"] / skill.usage_count
            if success:
                success_total = int(skill.metadata.get("success_total", 0))
                skill.metadata["success_total"] = success_total + 1
                skill.metadata["success_rate"] = skill.metadata["success_total"] / skill.usage_count
            self._persist_skill(skill)
            return
        # 兜底：dict
        if isinstance(skill, dict):
            skill["usage_count"] = int(skill.get("usage_count", 0)) + 1
            return
        # 其它带 usage_count 属性的对象
        if hasattr(skill, "usage_count"):
            try:
                skill.usage_count = int(skill.usage_count) + 1
            except Exception:
                pass

    def get_stats(self) -> dict[str, Any]:
        total = len(self._skills)
        enabled = sum(1 for s in self._skills.values() if _skill_attr(s, "enabled", True))
        total_usage = sum(int(_skill_attr(s, "usage_count", 0) or 0) for s in self._skills.values())
        tags_counter: Counter = Counter()
        category_counter: Counter = Counter()
        for s in self._skills.values():
            for tag in _skill_attr(s, "tags", []) or []:
                tags_counter[tag] += 1
            cat = _skill_attr(s, "category", None)
            if cat is None:
                meta = _skill_attr(s, "metadata", {}) or {}
                if isinstance(meta, dict):
                    cat = meta.get("category")
            if cat is not None:
                if hasattr(cat, "value"):
                    cat = cat.value
                category_counter[str(cat)] += 1

        most_used = sorted(
            (
                (str(_skill_attr(s, "name", "") or ""), int(_skill_attr(s, "usage_count", 0) or 0))
                for s in self._skills.values()
            ),
            key=lambda x: x[1],
            reverse=True,
        )[:5]

        return {
            "total_skills": total,
            "enabled_skills": enabled,
            "disabled_skills": total - enabled,
            "total_usage": total_usage,
            "top_tags": dict(tags_counter.most_common(10)),
            "categories": dict(category_counter),
            "most_used": [{"name": n, "usage_count": c} for n, c in most_used if c > 0],
            "storage_dir": str(self._storage_dir),
        }

    # ─── 旧版 API 兼容 ───────────────────────────────────────────────

    def register(self, skill: Any) -> bool:  # noqa: D401
        """旧版 API 别名，等价于 :meth:`register_skill`。"""
        return self.register_skill(skill)

    def unregister(self, skill_id: str) -> bool:  # noqa: D401
        """旧版 API 别名，等价于 :meth:`unregister_skill`。"""
        return self.unregister_skill(skill_id)

    def get(self, name_or_id: str) -> Any | None:  # noqa: D401
        """旧版 API 别名，等价于 :meth:`get_skill`。"""
        return self.get_skill(name_or_id)

    def get_by_name(self, name: str) -> Any | None:  # noqa: D401
        """旧版 API：按名称获取技能。"""
        skill, _ = self._find(name)
        return skill

    # ─── 目录加载 / 保存 ─────────────────────────────────────────────

    def load_from_directory(self, path: str) -> int:
        """
        从目录加载技能，支持 ``.json``（新旧版格式）和 ``.md``/``.txt``。
        """
        return self._load_from_directory(Path(path).expanduser())

    def _load_from_directory(self, directory: Path) -> int:
        if not directory.exists() or not directory.is_dir():
            return 0
        loaded = 0
        for file_path in directory.iterdir():
            try:
                if file_path.suffix.lower() == ".json":
                    if self._load_json_skill(file_path):
                        loaded += 1
                elif file_path.suffix.lower() in {".md", ".txt", ".markdown"}:
                    if self._load_text_skill(file_path):
                        loaded += 1
            except Exception as exc:
                logger.warning(f"加载技能文件失败 {file_path}: {exc}")
        if loaded:
            logger.info(f"从 {directory} 加载了 {loaded} 个技能")
        return loaded

    def _load_json_skill(self, file_path: Path) -> bool:
        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"无法解析 JSON 技能文件 {file_path}: {exc}")
            return False
        if not isinstance(data, dict):
            return False
        if "steps" in data and "triggers" in data:
            # 旧版 dict 暂不直接构造 dataclass（旧版 dataclass 解析较重），
            # 这里以新版 Skill 兼容形态保存，避免循环依赖
            skill = self._legacy_dict_to_new_skill(data)
        else:
            if not data.get("name") and not data.get("id"):
                return False
            skill = Skill.from_dict(data)
        if not skill or not skill.name:
            return False
        return self.register_skill(skill)

    def _load_text_skill(self, file_path: Path) -> bool:
        try:
            raw = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning(f"读取技能文件失败 {file_path}: {exc}")
            return False
        skill = self._parse_text_skill(raw, default_name=file_path.stem)
        if not skill:
            return False
        return self.register_skill(skill)

    @staticmethod
    def _parse_text_skill(raw: str, default_name: str) -> Skill | None:
        if not raw or not raw.strip():
            return None
        lines = raw.splitlines()
        name = ""
        description_parts: list[str] = []
        tags: list[str] = []
        version = "1.0.0"
        content_lines: list[str] = []
        examples: list[str] = []
        in_content = False
        in_examples = False

        for line in lines:
            stripped = line.strip()
            if not name and stripped.startswith("# "):
                name = stripped[2:].strip()
                continue
            if stripped.lower().startswith("# description:"):
                description_parts.append(stripped.split(":", 1)[1].strip())
                in_content = False
                in_examples = False
                continue
            if stripped.lower().startswith("# tags:"):
                tag_text = stripped.split(":", 1)[1].strip()
                tags = [t.strip() for t in re.split(r"[,，;；\s]+", tag_text) if t.strip()]
                in_content = False
                in_examples = False
                continue
            if stripped.lower().startswith("# version:"):
                version = stripped.split(":", 1)[1].strip() or "1.0.0"
                in_content = False
                in_examples = False
                continue
            if stripped.lower().startswith("# example") or stripped.lower().startswith("## example"):
                in_examples = True
                in_content = False
                continue
            if stripped.lower().startswith("# content") or stripped.lower().startswith("## content"):
                in_content = True
                in_examples = False
                continue
            if in_examples:
                examples.append(line)
            elif in_content:
                content_lines.append(line)
            else:
                description_parts.append(stripped)

        if not name:
            name = default_name.strip()
        if not name:
            return None
        description = " ".join(p for p in description_parts if p).strip()
        content = "\n".join(content_lines).strip()
        examples = [e for e in examples if e.strip()]
        return Skill(
            name=name,
            description=description,
            version=version,
            tags=tags,
            content=content,
            examples=examples,
        )

    @staticmethod
    def _legacy_dict_to_new_skill(data: dict[str, Any]) -> Skill | None:
        name = str(data.get("name", "") or "")
        if not name:
            return None
        return Skill(
            id=str(data.get("id", "") or ""),
            name=name,
            description=str(data.get("description", "") or ""),
            version=str(data.get("version", "1.0.0")),
            tags=list(data.get("tags", []) or []),
            content=str(data.get("content", "") or ""),
            metadata={
                "triggers": list(data.get("triggers", []) or []),
                "success_patterns": list(data.get("success_patterns", []) or []),
                "failure_patterns": list(data.get("failure_patterns", []) or []),
                "prerequisites": list(data.get("prerequisites", []) or []),
                "parameters": dict(data.get("parameters", {}) or {}),
                "steps": list(data.get("steps", []) or []),
                "category": str(data.get("category", "") or ""),
            },
        )

    def save_to_directory(self, path: str) -> int:
        target = Path(path).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        written = 0
        for skill in self._skills.values():
            if not isinstance(skill, Skill):
                continue
            file_path = target / f"{self._safe_filename(skill.name)}.json"
            try:
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(skill.to_dict(), f, ensure_ascii=False, indent=2)
                written += 1
            except OSError as exc:
                logger.error(f"保存技能失败 {file_path}: {exc}")
        return written

    # ─── 导出 / 导入 ─────────────────────────────────────────────────

    def export_skill(self, name_or_id: str) -> dict[str, Any]:
        skill = self.get_skill(name_or_id)
        if not skill:
            raise KeyError(f"Skill '{name_or_id}' not found")
        if isinstance(skill, dict):
            return dict(skill)
        if hasattr(skill, "to_dict"):
            return skill.to_dict()
        return {
            "name": str(_skill_attr(skill, "name", "")),
            "id": str(_skill_attr(skill, "id", "")),
            "description": str(_skill_attr(skill, "description", "")),
        }

    def import_skill(self, data: dict[str, Any]) -> Skill:
        if "steps" in data and "triggers" in data:
            skill = self._legacy_dict_to_new_skill(data)
        else:
            skill = Skill.from_dict(data)
        if not skill or not skill.name:
            raise ValueError("导入的技能数据缺少 'name' 字段")
        original = skill.name
        suffix = 1
        while self._name_to_id.get(skill.name):
            skill.name = f"{original}_{suffix}"
            suffix += 1
        self.register_skill(skill)
        return skill

    # ─── 工具方法 ───────────────────────────────────────────────────

    def clear(self) -> None:
        self._skills.clear()
        self._name_to_id.clear()

    def remove_all(self) -> int:
        keys = list(self._skills.keys())
        for key in keys:
            self.unregister_skill(key)
        return len(keys)

    # ─── 内部 ────────────────────────────────────────────────────────

    @staticmethod
    def _is_valid_skill(skill: Any) -> bool:
        if isinstance(skill, Skill):
            return True
        if isinstance(skill, dict):
            return bool(skill.get("name"))
        return hasattr(skill, "name") and bool(skill.name)

    def _compute_key(self, skill: Any) -> str:
        sid = _skill_attr(skill, "id", "")
        if sid:
            return str(sid)
        return str(_skill_attr(skill, "name", ""))

    def _resolve_key(self, name_or_id: str) -> str | None:
        if name_or_id in self._skills:
            return name_or_id
        if name_or_id in self._name_to_id:
            return self._name_to_id[name_or_id]
        return None

    def _find(self, name_or_id: str) -> tuple[Any | None, str | None]:
        key = self._resolve_key(name_or_id)
        if key is None:
            return None, None
        return self._skills.get(key), key

    def _persist_skill(self, skill: Skill) -> None:
        file_path = self._storage_dir / f"{self._safe_filename(skill.name)}.json"
        try:
            with file_path.open("w", encoding="utf-8") as f:
                json.dump(skill.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error(f"持久化技能失败 {file_path}: {exc}")

    @staticmethod
    def _safe_filename(name: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9._\-一-鿿]+", "_", name).strip("_")
        return safe or f"skill_{uuid.uuid4().hex[:8]}"


__all__ = ["Skill", "SkillManager"]
