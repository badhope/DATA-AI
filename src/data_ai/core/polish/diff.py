"""
文本差异对比模块。

本模块提供文本差异计算、格式化和应用功能。

主要组件:
- TextDiffer: 文本差异对比器
- DiffFormatter: 差异格式化器
- DiffApplier: 差异应用器
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .types import (
    ChangeType,
    DiffSegment,
    PolishException,
    TextChange,
)


class DiffFormat(Enum):
    """
    差异格式枚举。

    Attributes:
        UNIFIED: 统一差异格式
        CONTEXT: 上下文差异格式
        HTML: HTML格式
        MARKDOWN: Markdown格式
        JSON: JSON格式
    """

    UNIFIED = "unified"
    CONTEXT = "context"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"


@dataclass
class DiffResult:
    """
    差异对比结果。

    Attributes:
        segments: 差异片段列表
        similarity: 相似度（0.0-1.0）
        added_count: 新增内容数量
        removed_count: 删除内容数量
        changed_count: 修改内容数量
    """

    segments: list[DiffSegment] = field(default_factory=list)
    similarity: float = 1.0
    added_count: int = 0
    removed_count: int = 0
    changed_count: int = 0

    @property
    def has_changes(self) -> bool:
        """检查是否有变更。"""
        return self.added_count > 0 or self.removed_count > 0 or self.changed_count > 0

    @property
    def total_changes(self) -> int:
        """获取总变更数。"""
        return self.added_count + self.removed_count + self.changed_count

    def to_dict(self) -> dict[str, Any]:
        """将结果转换为字典格式。"""
        return {
            "segments": [s.to_dict() for s in self.segments],
            "similarity": round(self.similarity, 4),
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "total_changes": self.total_changes,
            "has_changes": self.has_changes,
        }


@dataclass
class DiffOptions:
    """
    差异对比选项。

    Attributes:
        ignore_case: 是否忽略大小写
        ignore_whitespace: 是否忽略空白字符
        ignore_punctuation: 是否忽略标点符号
        line_mode: 是否按行对比
        word_mode: 是否按词对比
        context_lines: 上下文行数
        min_match_length: 最小匹配长度
    """

    ignore_case: bool = False
    ignore_whitespace: bool = False
    ignore_punctuation: bool = False
    line_mode: bool = True
    word_mode: bool = False
    context_lines: int = 3
    min_match_length: int = 2


class TextDiffer:
    """
    文本差异对比器。

    提供文本差异计算、格式化和应用功能。

    Example:
        >>> differ = TextDiffer()
        >>> result = differ.compute_diff("hello world", "hello python")
        >>> print(result.similarity)
        0.4545
    """

    def __init__(self, options: DiffOptions | None = None) -> None:
        """
        初始化文本差异对比器。

        Args:
            options: 差异对比选项
        """
        self.options = options or DiffOptions()

    def compute_diff(
        self,
        original: str,
        modified: str,
    ) -> DiffResult:
        """
        计算两个文本之间的差异。

        Args:
            original: 原始文本
            modified: 修改后文本

        Returns:
            差异对比结果
        """
        if self.options.line_mode:
            return self._compute_line_diff(original, modified)
        elif self.options.word_mode:
            return self._compute_word_diff(original, modified)
        else:
            return self._compute_char_diff(original, modified)

    def _compute_line_diff(
        self,
        original: str,
        modified: str,
    ) -> DiffResult:
        """计算行级差异。"""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        # 预处理
        if self.options.ignore_case:
            original_lines = [line.lower() for line in original_lines]
            modified_lines = [line.lower() for line in modified_lines]

        # 使用 difflib 计算差异
        matcher = difflib.SequenceMatcher(
            None,
            original_lines,
            modified_lines,
        )

        segments = []
        added_count = 0
        removed_count = 0
        changed_count = 0

        original_pos = 0
        modified_pos = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i in range(i1, i2):
                    line = original_lines[i] if i < len(original_lines) else ""
                    segments.append(
                        DiffSegment(
                            type="equal",
                            content=line,
                            original_start=original_pos,
                            original_end=original_pos + len(line),
                            polished_start=modified_pos,
                            polished_end=modified_pos + len(line),
                        )
                    )
                    original_pos += len(line)
                    modified_pos += len(line)

            elif tag == "replace":
                changed_count += 1
                # 删除的内容
                for i in range(i1, i2):
                    line = original_lines[i] if i < len(original_lines) else ""
                    segments.append(
                        DiffSegment(
                            type="delete",
                            content=line,
                            original_start=original_pos,
                            original_end=original_pos + len(line),
                            polished_start=modified_pos,
                            polished_end=modified_pos,
                        )
                    )
                    original_pos += len(line)

                # 新增的内容
                for j in range(j1, j2):
                    line = modified_lines[j] if j < len(modified_lines) else ""
                    segments.append(
                        DiffSegment(
                            type="insert",
                            content=line,
                            original_start=original_pos,
                            original_end=original_pos,
                            polished_start=modified_pos,
                            polished_end=modified_pos + len(line),
                        )
                    )
                    modified_pos += len(line)

            elif tag == "delete":
                removed_count += 1
                for i in range(i1, i2):
                    line = original_lines[i] if i < len(original_lines) else ""
                    segments.append(
                        DiffSegment(
                            type="delete",
                            content=line,
                            original_start=original_pos,
                            original_end=original_pos + len(line),
                            polished_start=modified_pos,
                            polished_end=modified_pos,
                        )
                    )
                    original_pos += len(line)

            elif tag == "insert":
                added_count += 1
                for j in range(j1, j2):
                    line = modified_lines[j] if j < len(modified_lines) else ""
                    segments.append(
                        DiffSegment(
                            type="insert",
                            content=line,
                            original_start=original_pos,
                            original_end=original_pos,
                            polished_start=modified_pos,
                            polished_end=modified_pos + len(line),
                        )
                    )
                    modified_pos += len(line)

        return DiffResult(
            segments=segments,
            similarity=matcher.ratio(),
            added_count=added_count,
            removed_count=removed_count,
            changed_count=changed_count,
        )

    def _compute_word_diff(
        self,
        original: str,
        modified: str,
    ) -> DiffResult:
        """计算词级差异。"""
        import re

        # 分词
        original_words = re.findall(r"\S+|\s+", original)
        modified_words = re.findall(r"\S+|\s+", modified)

        # 预处理
        if self.options.ignore_case:
            original_words = [w.lower() for w in original_words]
            modified_words = [w.lower() for w in modified_words]

        matcher = difflib.SequenceMatcher(
            None,
            original_words,
            modified_words,
        )

        segments = []
        added_count = 0
        removed_count = 0
        changed_count = 0

        original_pos = 0
        modified_pos = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i in range(i1, i2):
                    word = original_words[i] if i < len(original_words) else ""
                    segments.append(
                        DiffSegment(
                            type="equal",
                            content=word,
                            original_start=original_pos,
                            original_end=original_pos + len(word),
                            polished_start=modified_pos,
                            polished_end=modified_pos + len(word),
                        )
                    )
                    original_pos += len(word)
                    modified_pos += len(word)

            elif tag == "replace":
                changed_count += 1
                # 删除的内容
                for i in range(i1, i2):
                    word = original_words[i] if i < len(original_words) else ""
                    segments.append(
                        DiffSegment(
                            type="delete",
                            content=word,
                            original_start=original_pos,
                            original_end=original_pos + len(word),
                            polished_start=modified_pos,
                            polished_end=modified_pos,
                        )
                    )
                    original_pos += len(word)

                # 新增的内容
                for j in range(j1, j2):
                    word = modified_words[j] if j < len(modified_words) else ""
                    segments.append(
                        DiffSegment(
                            type="insert",
                            content=word,
                            original_start=original_pos,
                            original_end=original_pos,
                            polished_start=modified_pos,
                            polished_end=modified_pos + len(word),
                        )
                    )
                    modified_pos += len(word)

            elif tag == "delete":
                removed_count += 1
                for i in range(i1, i2):
                    word = original_words[i] if i < len(original_words) else ""
                    segments.append(
                        DiffSegment(
                            type="delete",
                            content=word,
                            original_start=original_pos,
                            original_end=original_pos + len(word),
                            polished_start=modified_pos,
                            polished_end=modified_pos,
                        )
                    )
                    original_pos += len(word)

            elif tag == "insert":
                added_count += 1
                for j in range(j1, j2):
                    word = modified_words[j] if j < len(modified_words) else ""
                    segments.append(
                        DiffSegment(
                            type="insert",
                            content=word,
                            original_start=original_pos,
                            original_end=original_pos,
                            polished_start=modified_pos,
                            polished_end=modified_pos + len(word),
                        )
                    )
                    modified_pos += len(word)

        return DiffResult(
            segments=segments,
            similarity=matcher.ratio(),
            added_count=added_count,
            removed_count=removed_count,
            changed_count=changed_count,
        )

    def _compute_char_diff(
        self,
        original: str,
        modified: str,
    ) -> DiffResult:
        """计算字符级差异。"""
        # 预处理
        orig = original
        mod = modified

        if self.options.ignore_case:
            orig = orig.lower()
            mod = mod.lower()

        matcher = difflib.SequenceMatcher(None, orig, mod)

        segments = []
        added_count = 0
        removed_count = 0
        changed_count = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                segments.append(
                    DiffSegment(
                        type="equal",
                        content=original[i1:i2],
                        original_start=i1,
                        original_end=i2,
                        polished_start=j1,
                        polished_end=j2,
                    )
                )

            elif tag == "replace":
                changed_count += 1
                segments.append(
                    DiffSegment(
                        type="delete",
                        content=original[i1:i2],
                        original_start=i1,
                        original_end=i2,
                        polished_start=j1,
                        polished_end=j1,
                    )
                )
                segments.append(
                    DiffSegment(
                        type="insert",
                        content=modified[j1:j2],
                        original_start=i2,
                        original_end=i2,
                        polished_start=j1,
                        polished_end=j2,
                    )
                )

            elif tag == "delete":
                removed_count += 1
                segments.append(
                    DiffSegment(
                        type="delete",
                        content=original[i1:i2],
                        original_start=i1,
                        original_end=i2,
                        polished_start=j1,
                        polished_end=j1,
                    )
                )

            elif tag == "insert":
                added_count += 1
                segments.append(
                    DiffSegment(
                        type="insert",
                        content=modified[j1:j2],
                        original_start=i1,
                        original_end=i1,
                        polished_start=j1,
                        polished_end=j2,
                    )
                )

        return DiffResult(
            segments=segments,
            similarity=matcher.ratio(),
            added_count=added_count,
            removed_count=removed_count,
            changed_count=changed_count,
        )

    def format_diff(
        self,
        result: DiffResult,
        format_type: DiffFormat = DiffFormat.UNIFIED,
    ) -> str:
        """
        格式化差异结果。

        Args:
            result: 差异对比结果
            format_type: 格式类型

        Returns:
            格式化后的差异字符串
        """
        formatters = {
            DiffFormat.UNIFIED: self._format_unified,
            DiffFormat.CONTEXT: self._format_context,
            DiffFormat.HTML: self._format_html,
            DiffFormat.MARKDOWN: self._format_markdown,
            DiffFormat.JSON: self._format_json,
        }

        formatter = formatters.get(format_type, self._format_unified)
        return formatter(result)

    def _format_unified(self, result: DiffResult) -> str:
        """格式化为统一差异格式。"""
        lines = []

        for segment in result.segments:
            if segment.type == "equal":
                lines.append(f"  {segment.content}")
            elif segment.type == "delete":
                lines.append(f"- {segment.content}")
            elif segment.type == "insert":
                lines.append(f"+ {segment.content}")

        return "\n".join(lines)

    def _format_context(self, result: DiffResult) -> str:
        """格式化为上下文差异格式。"""
        lines = ["*** 原文 ***", ""]

        for segment in result.segments:
            if segment.type in ("equal", "delete"):
                prefix = "  " if segment.type == "equal" else "- "
                lines.append(f"{prefix}{segment.content}")

        lines.extend(["", "*** 修改后 ***", ""])

        for segment in result.segments:
            if segment.type in ("equal", "insert"):
                prefix = "  " if segment.type == "equal" else "+ "
                lines.append(f"{prefix}{segment.content}")

        return "\n".join(lines)

    def _format_html(self, result: DiffResult) -> str:
        """格式化为 HTML 格式。"""
        import html

        html_parts = ['<div class="diff-container">']

        for segment in result.segments:
            content = html.escape(segment.content)

            if segment.type == "equal":
                html_parts.append(f'<span class="equal">{content}</span>')
            elif segment.type == "delete":
                html_parts.append(f'<del class="delete">{content}</del>')
            elif segment.type == "insert":
                html_parts.append(f'<ins class="insert">{content}</ins>')

        html_parts.append("</div>")

        return "".join(html_parts)

    def _format_markdown(self, result: DiffResult) -> str:
        """格式化为 Markdown 格式。"""
        lines = ["```diff"]

        for segment in result.segments:
            if segment.type == "equal":
                lines.append(f"  {segment.content}")
            elif segment.type == "delete":
                lines.append(f"- {segment.content}")
            elif segment.type == "insert":
                lines.append(f"+ {segment.content}")

        lines.append("```")

        return "\n".join(lines)

    def _format_json(self, result: DiffResult) -> str:
        """格式化为 JSON 格式。"""
        import json

        return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

    def apply_diff(
        self,
        original: str,
        changes: list[TextChange],
    ) -> str:
        """
        应用变更到原始文本。

        Args:
            original: 原始文本
            changes: 变更列表

        Returns:
            应用变更后的文本
        """
        if not changes:
            return original

        # 按位置倒序排列，从后往前应用变更
        sorted_changes = sorted(changes, key=lambda c: c.position[0], reverse=True)

        result = original
        for change in sorted_changes:
            start, end = change.position

            # 验证位置
            if start < 0 or end > len(result):
                raise PolishException(
                    message=f"无效的变更位置: {change.position}",
                    code="INVALID_CHANGE_POSITION",
                    details={"change": change.to_dict()},
                )

            # 应用变更
            result = result[:start] + change.replacement + result[end:]

        return result

    def reverse_diff(
        self,
        modified: str,
        changes: list[TextChange],
    ) -> str:
        """
        反向应用变更（从修改后文本恢复原始文本）。

        Args:
            modified: 修改后文本
            changes: 变更列表

        Returns:
            原始文本
        """
        if not changes:
            return modified

        # 创建反向变更
        reversed_changes = []
        offset = 0

        # 按位置正序排列
        sorted_changes = sorted(changes, key=lambda c: c.position[0])

        for change in sorted_changes:
            # 计算在修改后文本中的位置
            new_start = change.position[0] + offset
            new_end = new_start + len(change.replacement)

            reversed_changes.append(
                TextChange(
                    position=(new_start, new_end),
                    original=change.replacement,
                    replacement=change.original,
                    change_type=change.change_type,
                    reason=f"撤销: {change.reason}",
                    confidence=change.confidence,
                )
            )

            offset += len(change.replacement) - len(change.original)

        # 应用反向变更
        return self.apply_diff(modified, reversed_changes)

    def compute_similarity(
        self,
        text1: str,
        text2: str,
    ) -> float:
        """
        计算两个文本的相似度。

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            相似度（0.0-1.0）
        """
        matcher = difflib.SequenceMatcher(None, text1, text2)
        return matcher.ratio()

    def find_changes(
        self,
        original: str,
        modified: str,
        change_type: ChangeType = ChangeType.STYLE,
    ) -> list[TextChange]:
        """
        找出两个文本之间的所有变更。

        Args:
            original: 原始文本
            modified: 修改后文本
            change_type: 变更类型

        Returns:
            变更列表
        """
        result = self.compute_diff(original, modified)
        changes = []

        # 合并相邻的 delete 和 insert 为 replace
        i = 0
        while i < len(result.segments):
            segment = result.segments[i]

            if segment.type == "delete":
                # 检查下一个是否为 insert
                if i + 1 < len(result.segments) and result.segments[i + 1].type == "insert":
                    next_segment = result.segments[i + 1]
                    changes.append(
                        TextChange(
                            position=(segment.original_start, segment.original_end),
                            original=segment.content,
                            replacement=next_segment.content,
                            change_type=change_type,
                            reason="文本修改",
                        )
                    )
                    i += 2
                    continue
                else:
                    changes.append(
                        TextChange(
                            position=(segment.original_start, segment.original_end),
                            original=segment.content,
                            replacement="",
                            change_type=change_type,
                            reason="文本删除",
                        )
                    )

            elif segment.type == "insert":
                changes.append(
                    TextChange(
                        position=(segment.original_start, segment.original_end),
                        original="",
                        replacement=segment.content,
                        change_type=change_type,
                        reason="文本新增",
                    )
                )

            i += 1

        return changes

    def merge_changes(
        self,
        changes1: list[TextChange],
        changes2: list[TextChange],
    ) -> list[TextChange]:
        """
        合并两个变更列表。

        Args:
            changes1: 第一个变更列表
            changes2: 第二个变更列表

        Returns:
            合并后的变更列表
        """
        # 按位置排序
        all_changes = sorted(
            changes1 + changes2,
            key=lambda c: c.position[0],
        )

        # 去重
        seen = set()
        merged = []

        for change in all_changes:
            key = (change.position, change.original, change.replacement)
            if key not in seen:
                seen.add(key)
                merged.append(change)

        return merged


class DiffFormatter:
    """
    差异格式化器。

    提供多种格式的差异展示。
    """

    @staticmethod
    def format_side_by_side(
        original: str,
        modified: str,
        width: int = 80,
    ) -> str:
        """
        并排格式化差异。

        Args:
            original: 原始文本
            modified: 修改后文本
            width: 每列宽度

        Returns:
            并排格式的差异字符串
        """
        original_lines = original.splitlines()
        modified_lines = modified.splitlines()

        max_lines = max(len(original_lines), len(modified_lines))

        lines = []
        lines.append(f"{'原始文本':^{width}} | {'修改后文本':^{width}}")
        lines.append("-" * (width * 2 + 3))

        for i in range(max_lines):
            orig = original_lines[i] if i < len(original_lines) else ""
            mod = modified_lines[i] if i < len(modified_lines) else ""

            orig_display = orig[:width].ljust(width)
            mod_display = mod[:width].ljust(width)

            # 标记差异
            if orig != mod:
                orig_display = f"[{orig_display}]"
                mod_display = f"[{mod_display}]"

            lines.append(f"{orig_display} | {mod_display}")

        return "\n".join(lines)

    @staticmethod
    def format_inline_diff(
        original: str,
        modified: str,
        delete_marker: str = "[-",
        delete_end: str = "-]",
        insert_marker: str = "[+",
        insert_end: str = "+]",
    ) -> str:
        """
        行内差异格式化。

        Args:
            original: 原始文本
            modified: 修改后文本
            delete_marker: 删除标记开始
            delete_end: 删除标记结束
            insert_marker: 插入标记开始
            insert_end: 插入标记结束

        Returns:
            行内差异字符串
        """
        differ = TextDiffer()
        result = differ.compute_diff(original, modified)

        parts = []
        for segment in result.segments:
            if segment.type == "equal":
                parts.append(segment.content)
            elif segment.type == "delete":
                parts.append(f"{delete_marker}{segment.content}{delete_end}")
            elif segment.type == "insert":
                parts.append(f"{insert_marker}{segment.content}{insert_end}")

        return "".join(parts)

    @staticmethod
    def format_statistics(
        result: DiffResult,
    ) -> str:
        """
        格式化差异统计信息。

        Args:
            result: 差异对比结果

        Returns:
            统计信息字符串
        """
        lines = [
            "=== 差异统计 ===",
            f"相似度: {result.similarity:.2%}",
            f"新增: {result.added_count} 处",
            f"删除: {result.removed_count} 处",
            f"修改: {result.changed_count} 处",
            f"总计变更: {result.total_changes} 处",
        ]
        return "\n".join(lines)


class DiffApplier:
    """
    差异应用器。

    提供变更的应用和撤销功能。
    """

    @staticmethod
    def apply_changes(
        text: str,
        changes: list[TextChange],
        validate: bool = True,
    ) -> str:
        """
        应用变更到文本。

        Args:
            text: 原始文本
            changes: 变更列表
            validate: 是否验证变更

        Returns:
            应用变更后的文本
        """
        if validate:
            DiffApplier._validate_changes(text, changes)

        # 按位置倒序排列
        sorted_changes = sorted(changes, key=lambda c: c.position[0], reverse=True)

        result = text
        for change in sorted_changes:
            start, end = change.position
            result = result[:start] + change.replacement + result[end:]

        return result

    @staticmethod
    def _validate_changes(
        text: str,
        changes: list[TextChange],
    ) -> None:
        """
        验证变更的有效性。

        Args:
            text: 原始文本
            changes: 变更列表

        Raises:
            PolishException: 如果变更无效
        """
        # 检查位置是否有效
        for change in changes:
            start, end = change.position

            if start < 0:
                raise PolishException(
                    message=f"变更起始位置无效: {start}",
                    code="INVALID_START_POSITION",
                )

            if end > len(text):
                raise PolishException(
                    message=f"变更结束位置超出文本长度: {end} > {len(text)}",
                    code="INVALID_END_POSITION",
                )

            if start > end:
                raise PolishException(
                    message=f"变更位置范围无效: ({start}, {end})",
                    code="INVALID_POSITION_RANGE",
                )

        # 检查是否有重叠
        sorted_changes = sorted(changes, key=lambda c: c.position[0])
        for i in range(len(sorted_changes) - 1):
            current = sorted_changes[i]
            next_change = sorted_changes[i + 1]

            if current.position[1] > next_change.position[0]:
                raise PolishException(
                    message="检测到重叠的变更",
                    code="OVERLAPPING_CHANGES",
                    details={
                        "change1": current.to_dict(),
                        "change2": next_change.to_dict(),
                    },
                )

    @staticmethod
    def create_patch(
        original: str,
        modified: str,
    ) -> str:
        """
        创建补丁字符串。

        Args:
            original: 原始文本
            modified: 修改后文本

        Returns:
            补丁字符串
        """
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile="original",
            tofile="modified",
        )

        return "".join(diff)

    @staticmethod
    def apply_patch(
        text: str,
        patch: str,
    ) -> str:
        """
        应用补丁到文本。

        Args:
            text: 原始文本
            patch: 补丁字符串

        Returns:
            应用补丁后的文本
        """
        text.splitlines(keepends=True)
        patch_lines = patch.splitlines(keepends=True)

        # 解析补丁
        # 简化实现：使用 difflib 的 restore 函数
        # 这里提供一个基本实现

        result_lines = []

        for line in patch_lines:
            if line.startswith("@@"):
                # 解析位置信息
                pass
            elif line.startswith(" "):
                result_lines.append(line[1:])
            elif line.startswith("+"):
                result_lines.append(line[1:])
            elif line.startswith("-"):
                # 跳过删除的行
                pass

        return "".join(result_lines)
