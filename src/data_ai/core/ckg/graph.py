"""
代码知识图谱（CodeKnowledgeGraph）

将解析后的 Python/其他语言代码组织为有向图，支持：
- 节点：文件、类、函数、方法、变量、模块
- 边：包含、调用、导入、继承、实现、依赖、使用
- 搜索（关键词 / 名称）
- 递归查找调用者 / 被调用者
- DOT 导出（Graphviz 可视化）
- 统计信息
"""

from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from ...utils.logging import get_logger
from .parser import (
    CodeLocation,
    CodeParser,
    CodeSymbol,
    ParsedFile,
)

logger = get_logger(__name__)


# ─── 节点 / 边 类型 ────────────────────────────────────────────────────────


class NodeType(Enum):
    """代码图节点类型。"""

    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    INTERFACE = "interface"
    MODULE = "module"
    PACKAGE = "package"


class EdgeType(Enum):
    """代码图边类型。"""

    IMPORTS = "imports"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    CALLS = "calls"
    USES = "uses"
    DEFINES = "defines"
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"


# ─── 数据类 ────────────────────────────────────────────────────────────────


@dataclass
class CodeNode:
    """代码图节点。"""

    id: str
    name: str
    node_type: NodeType
    location: CodeLocation | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        loc = None
        if self.location is not None:
            loc = {
                "file_path": self.location.file_path,
                "line_start": self.location.line_start,
                "line_end": self.location.line_end,
                "column_start": self.location.column_start,
                "column_end": self.location.column_end,
            }
        return {
            "id": self.id,
            "name": self.name,
            "node_type": self.node_type.value,
            "location": loc,
            "metadata": self.metadata,
        }


@dataclass
class CodeEdge:
    """代码图边。"""

    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "weight": self.weight,
            "metadata": self.metadata,
        }


# ─── 文本匹配辅助 ──────────────────────────────────────────────────────────


_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[\u4e00-\u9fff]+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def _score_node(query_tokens: list[str], node: CodeNode) -> float:
    if not query_tokens:
        return 0.0
    score = 0.0
    name_l = node.name.lower()
    name_tokens = set(_tokenize(node.name))
    type_token = node.node_type.value.lower()
    file_path_l = (node.location.file_path if node.location else "").lower()

    for token in query_tokens:
        if token in name_l:
            # 完整子串匹配得分
            if token == name_l:
                score += 5.0
            else:
                score += 2.0
        if token in name_tokens:
            score += 1.5
        if token == type_token:
            score += 0.5
        if token and token in file_path_l:
            score += 0.5
        if node.metadata:
            doc = (node.metadata.get("docstring") or "").lower()
            if token in doc:
                score += 0.3
    return score


# ─── 主类 ──────────────────────────────────────────────────────────────────


class CodeKnowledgeGraph:
    """
    代码知识图谱。

    采用纯内存的字典结构存储节点与边，邻接关系同时维护正向与反向索引，
    便于快速遍历图谱。提供查询、依赖分析、调用者追踪、Dot 导出等能力。
    """

    _SYMBOL_TYPE_MAP: dict[str, NodeType] = {
        "function": NodeType.FUNCTION,
        "class": NodeType.CLASS,
        "method": NodeType.METHOD,
        "variable": NodeType.VARIABLE,
        "interface": NodeType.INTERFACE,
        "type": NodeType.INTERFACE,
        "struct": NodeType.CLASS,
    }

    def __init__(self) -> None:
        self._nodes: dict[str, CodeNode] = {}
        self._edges: list[CodeEdge] = []
        self._adjacency: dict[str, list[str]] = defaultdict(list)
        self._reverse_adjacency: dict[str, list[str]] = defaultdict(list)
        self._name_index: dict[str, list[str]] = defaultdict(list)
        self._parser: CodeParser = CodeParser()

    # ─── 节点 / 边 API ───────────────────────────────────────────────

    def add_node(self, node: CodeNode) -> bool:
        """
        添加一个节点。

        Returns:
            新增返回 ``True``，已存在则覆盖并返回 ``True``，节点不合法返回 ``False``。
        """
        if not isinstance(node, CodeNode):
            logger.error(f"add_node 需要 CodeNode，得到 {type(node).__name__}")
            return False
        if not node.id or not node.name:
            logger.warning("节点 id/name 不能为空，已忽略")
            return False
        existed = node.id in self._nodes
        self._nodes[node.id] = node
        if not existed:
            self._name_index[node.name].append(node.id)
        return True

    def add_edge(self, edge: CodeEdge) -> bool:
        """
        添加一条边，自动维护正反向邻接表。

        Returns:
            成功返回 ``True``，参数无效返回 ``False``。
        """
        if not isinstance(edge, CodeEdge):
            logger.error(f"add_edge 需要 CodeEdge，得到 {type(edge).__name__}")
            return False
        if not edge.source_id or not edge.target_id:
            logger.warning("边的 source/target 不能为空，已忽略")
            return False
        # 避免完全重复的边
        if self._has_edge(edge.source_id, edge.target_id, edge.edge_type):
            return True
        self._edges.append(edge)
        self._adjacency[edge.source_id].append(edge.target_id)
        self._reverse_adjacency[edge.target_id].append(edge.source_id)
        return True

    def _has_edge(self, source_id: str, target_id: str, edge_type: EdgeType) -> bool:
        for e in self._adjacency.get(source_id, []):
            if e != target_id:
                continue
            # 找到 target_id，还需要确认类型一致
            for existing in self._edges:
                if (
                    existing.source_id == source_id
                    and existing.target_id == target_id
                    and existing.edge_type == edge_type
                ):
                    return True
        return False

    def get_node(self, node_id: str) -> CodeNode | None:
        """按 ID 获取节点。"""
        return self._nodes.get(node_id)

    def remove_node(self, node_id: str) -> bool:
        """删除节点及其所有相关边。"""
        if node_id not in self._nodes:
            return False
        node = self._nodes.pop(node_id)
        # 清理索引
        ids = self._name_index.get(node.name, [])
        if node_id in ids:
            ids.remove(node_id)
        # 清理邻接表
        for target in list(self._adjacency.get(node_id, [])):
            if node_id in self._reverse_adjacency.get(target, []):
                self._reverse_adjacency[target].remove(node_id)
        self._adjacency.pop(node_id, None)
        # 清理反向邻接
        for source in list(self._reverse_adjacency.get(node_id, [])):
            if node_id in self._adjacency.get(source, []):
                self._adjacency[source].remove(node_id)
        self._reverse_adjacency.pop(node_id, None)
        # 清理边
        self._edges = [e for e in self._edges if e.source_id != node_id and e.target_id != node_id]
        return True

    # ─── 构建 ───────────────────────────────────────────────────────

    def build_from_path(self, path: str) -> int:
        """
        从路径构建图谱（文件或目录）。

        Args:
            path: 文件路径或目录路径。

        Returns:
            新增的节点数量（包含文件节点和符号节点）。
        """
        target = Path(path).expanduser().resolve()
        if not target.exists():
            logger.warning(f"构建图谱失败，路径不存在: {target}")
            return 0
        if target.is_file():
            files = [target]
        else:
            files = [
                p
                for p in target.rglob("*.py")
                if not any(part in {"__pycache__", ".git", ".venv", "venv", "node_modules"} for part in p.parts)
            ]
        return self.build_from_files(files)

    def build_from_files(self, files: list[Any]) -> int:
        """
        从文件列表构建图谱。

        元素可以是 :class:`pathlib.Path`（会被自动解析）或
        已经解析好的 :class:`data_ai.core.ckg.parser.ParsedFile`。
        """
        before = len(self._nodes)
        for item in files:
            try:
                if isinstance(item, ParsedFile):
                    parsed = item
                else:
                    parsed = self._parser.parse_file(str(item))
            except Exception as exc:
                logger.warning(f"解析失败 {item}: {exc}")
                continue
            self._add_parsed_file(parsed)
        return len(self._nodes) - before

    def _add_parsed_file(self, parsed: ParsedFile) -> None:
        file_node = CodeNode(
            id=f"file:{parsed.file_path}",
            name=parsed.file_path,
            node_type=NodeType.FILE,
            location=CodeLocation(
                file_path=parsed.file_path,
                line_start=1,
                line_end=max(parsed.lines_of_code, 1),
            ),
            metadata={
                "language": parsed.language.value,
                "lines_of_code": parsed.lines_of_code,
                "imports": list(parsed.imports),
            },
        )
        self.add_node(file_node)

        # 顶层符号
        for symbol in parsed.symbols:
            symbol_node = self._symbol_to_node(symbol, parsed.file_path)
            self.add_node(symbol_node)
            self.add_edge(
                CodeEdge(
                    source_id=file_node.id,
                    target_id=symbol_node.id,
                    edge_type=EdgeType.CONTAINS,
                )
            )

            # 继承 / 实现
            for dep in symbol.dependencies or []:
                if not dep:
                    continue
                if dep in {"extends"} or dep in {"implements"}:
                    continue
                if self._looks_like_class_reference(dep):
                    self.add_edge(
                        CodeEdge(
                            source_id=symbol_node.id,
                            target_id=f"class:{dep}",
                            edge_type=EdgeType.EXTENDS,
                        )
                    )
                else:
                    self.add_edge(
                        CodeEdge(
                            source_id=symbol_node.id,
                            target_id=f"symbol:{dep}",
                            edge_type=EdgeType.DEPENDS_ON,
                        )
                    )

        # 文件级导入
        for imp in parsed.dependencies or []:
            self.add_edge(
                CodeEdge(
                    source_id=file_node.id,
                    target_id=f"module:{imp}",
                    edge_type=EdgeType.IMPORTS,
                )
            )

        # 变量节点（来自 metadata 字段）
        variables = parsed.metadata.get("variables", []) if parsed.metadata else []
        for var in variables:
            var_id = f"variable:{parsed.file_path}:{var.get('name', '')}"
            self.add_node(
                CodeNode(
                    id=var_id,
                    name=var.get("name", ""),
                    node_type=NodeType.VARIABLE,
                    location=CodeLocation(
                        file_path=parsed.file_path,
                        line_start=var.get("line", 0),
                        line_end=var.get("line", 0),
                    ),
                    metadata=var,
                )
            )
            self.add_edge(
                CodeEdge(
                    source_id=file_node.id,
                    target_id=var_id,
                    edge_type=EdgeType.CONTAINS,
                )
            )

    @classmethod
    def _symbol_to_node(cls, symbol: CodeSymbol, file_path: str) -> CodeNode:
        node_type = cls._SYMBOL_TYPE_MAP.get(symbol.symbol_type, NodeType.FUNCTION)
        return CodeNode(
            id=f"{node_type.value}:{file_path}:{symbol.name}",
            name=symbol.name,
            node_type=node_type,
            location=symbol.location,
            metadata={
                "signature": symbol.signature,
                "docstring": symbol.docstring,
                "modifiers": list(symbol.modifiers or []),
                "parameters": list(symbol.parameters or []),
                "return_type": symbol.return_type,
            },
        )

    @staticmethod
    def _looks_like_class_reference(name: str) -> bool:
        """简单启发式：首字母大写且不是关键字则视为类引用。"""
        if not name or not name[0].isalpha():
            return False
        return name[0].isupper()

    # ─── 查询 / 搜索 ────────────────────────────────────────────────

    def find_by_name(self, name: str, exact: bool = False) -> list[CodeNode]:
        """
        按名称查找节点。

        Args:
            name: 节点名。
            exact: ``True`` 时严格匹配；``False`` 时按子串匹配。
        """
        if not name:
            return []
        if exact:
            ids = list(self._name_index.get(name, []))
            return [self._nodes[i] for i in ids if i in self._nodes]
        name_l = name.lower()
        results: list[CodeNode] = []
        seen: set[str] = set()
        for node in self._nodes.values():
            if node.id in seen:
                continue
            if name_l in node.name.lower():
                results.append(node)
                seen.add(node.id)
        return results

    def search(
        self,
        query: str,
        top_k: int = 10,
        node_type: NodeType | None = None,
    ) -> list[CodeNode]:
        """
        关键词搜索节点。

        Args:
            query: 搜索词，支持多关键词。
            top_k: 返回的最大节点数。
            node_type: 可选类型过滤。

        Returns:
            按相关度降序排列的 :class:`CodeNode` 列表。
        """
        if not query or not query.strip():
            return []
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple[CodeNode, float]] = []
        for node in self._nodes.values():
            if node_type is not None and node.node_type != node_type:
                continue
            score = _score_node(query_tokens, node)
            if score > 0:
                scored.append((node, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return [node for node, _ in scored[: max(0, top_k)]]

    def search_with_relations(
        self,
        query: str,
        top_k: int = 10,
    ) -> list[tuple[CodeNode, list[CodeEdge]]]:
        """
        关键词搜索节点，并附带其相关边。

        Returns:
            列表，每项为 ``(节点, [该节点相关的边])``。
        """
        nodes = self.search(query, top_k=top_k)
        results: list[tuple[CodeNode, list[CodeEdge]]] = []
        for node in nodes:
            related = [e for e in self._edges if e.source_id == node.id or e.target_id == node.id]
            results.append((node, related))
        return results

    # ─── 关系遍历 ───────────────────────────────────────────────────

    def find_dependencies(self, node_id: str, recursive: bool = True) -> list[CodeNode]:
        """
        查找节点依赖的其它节点（正向遍历）。

        Args:
            node_id: 起始节点 ID。
            recursive: 是否递归查找间接依赖。
        """
        if node_id not in self._nodes:
            return []
        seen: set[str] = set()
        result: list[CodeNode] = []
        queue: deque[str] = deque(self._adjacency.get(node_id, []))
        while queue:
            current = queue.popleft()
            if current in seen or current == node_id:
                continue
            seen.add(current)
            node = self._nodes.get(current)
            if node:
                result.append(node)
            if recursive:
                for nxt in self._adjacency.get(current, []):
                    if nxt not in seen:
                        queue.append(nxt)
        return result

    def find_callers(self, node_id: str, recursive: bool = True) -> list[CodeNode]:
        """
        查找调用 / 引用该节点的其它节点（反向遍历）。
        """
        if node_id not in self._nodes:
            return []
        seen: set[str] = set()
        result: list[CodeNode] = []
        queue: deque[str] = deque(self._reverse_adjacency.get(node_id, []))
        while queue:
            current = queue.popleft()
            if current in seen or current == node_id:
                continue
            seen.add(current)
            node = self._nodes.get(current)
            if node:
                result.append(node)
            if recursive:
                for nxt in self._reverse_adjacency.get(current, []):
                    if nxt not in seen:
                        queue.append(nxt)
        return result

    def find_callers_of_file(self, file_path: str) -> list[CodeNode]:
        """
        查找引用了该文件的节点（一般是其它文件节点或符号节点）。
        """
        file_id = f"file:{file_path}"
        if file_id not in self._nodes:
            return []
        return self.find_callers(file_id, recursive=False)

    # ─── 图操作 ─────────────────────────────────────────────────────

    def clear(self) -> None:
        """清空图谱。"""
        self._nodes.clear()
        self._edges.clear()
        self._adjacency.clear()
        self._reverse_adjacency.clear()
        self._name_index.clear()

    def export_json(self) -> str:
        """导出为 JSON 字符串。"""
        return json.dumps(
            {
                "nodes": [n.to_dict() for n in self._nodes.values()],
                "edges": [e.to_dict() for e in self._edges],
            },
            ensure_ascii=False,
            indent=2,
        )

    def export_dot(self) -> str:
        """
        导出为 Graphviz DOT 格式字符串。

        Example:
            >>> print(graph.export_dot())
            digraph CodeKnowledgeGraph {
              rankdir=LR;
              "node1" [label="...", shape=box];
              "node1" -> "node2" [label="contains"];
            }
        """
        lines = [
            "digraph CodeKnowledgeGraph {",
            "  rankdir=LR;",
            '  node [fontname="Helvetica", fontsize=10];',
        ]
        type_styles = {
            NodeType.FILE: ("box", "file"),
            NodeType.CLASS: ("ellipse", "class"),
            NodeType.FUNCTION: ("note", "function"),
            NodeType.METHOD: ("note", "method"),
            NodeType.VARIABLE: ("plaintext", "variable"),
            NodeType.INTERFACE: ("diamond", "interface"),
            NodeType.MODULE: ("folder", "module"),
            NodeType.PACKAGE: ("folder", "package"),
        }
        # 限制节点过多导致输出爆炸
        max_nodes = 500
        nodes_to_render = list(self._nodes.values())[:max_nodes]
        for node in nodes_to_render:
            shape, _ = type_styles.get(node.node_type, ("box", ""))
            label = node.name.replace('"', '\\"')
            lines.append(f'  "{node.id}" [label="{label}", shape={shape}];')
        for edge in self._edges:
            if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
                continue
            label = edge.edge_type.value
            lines.append(f'  "{edge.source_id}" -> "{edge.target_id}" [label="{label}"];')
        lines.append("}")
        return "\n".join(lines)

    # ─── 统计 ───────────────────────────────────────────────────────

    def get_statistics(self) -> dict[str, Any]:
        """获取图谱统计信息。"""
        node_types: dict[str, int] = defaultdict(int)
        edge_types: dict[str, int] = defaultdict(int)
        for node in self._nodes.values():
            node_types[node.node_type.value] += 1
        for edge in self._edges:
            edge_types[edge.edge_type.value] += 1

        # 查找 hub 节点（被引用最多）
        referenced: dict[str, int] = defaultdict(int)
        for source in self._adjacency.values():
            for tgt in source:
                referenced[tgt] += 1
        top_referenced = sorted(
            ((self._nodes[nid].name, cnt) for nid, cnt in referenced.items() if nid in self._nodes),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "node_types": dict(node_types),
            "edge_types": dict(edge_types),
            "top_referenced": [{"name": n, "references": c} for n, c in top_referenced],
        }

    # ─── 兼容旧 API ────────────────────────────────────────────────

    def get_dependencies(self, node_id: str) -> list[CodeNode]:
        """兼容旧版：默认非递归。"""
        return self.find_dependencies(node_id, recursive=False)

    def get_dependents(self, node_id: str) -> list[CodeNode]:
        """兼容旧版：默认非递归。"""
        return self.find_callers(node_id, recursive=False)

    def find_path(self, from_id: str, to_id: str, max_depth: int = 6) -> list[list[str]]:
        """使用 BFS 查找两个节点之间的最短路径。"""
        if from_id not in self._nodes or to_id not in self._nodes:
            return []
        if from_id == to_id:
            return [[from_id]]
        # BFS
        parents: dict[str, str | None] = {from_id: None}
        queue: deque[str] = deque([from_id])
        found = False
        while queue and not found:
            current = queue.popleft()
            if parents[current] is not None and self._path_length(parents, current) >= max_depth:
                continue
            for nxt in self._adjacency.get(current, []):
                if nxt in parents:
                    continue
                parents[nxt] = current
                if nxt == to_id:
                    found = True
                    break
                queue.append(nxt)
        if not found and to_id not in parents:
            return []
        # 重建路径
        path: list[str] = []
        node = to_id
        while node is not None:
            path.append(node)
            node = parents.get(node)
        return [list(reversed(path))]

    @staticmethod
    def _path_length(parents: dict[str, str | None], node: str) -> int:
        length = 0
        current: str | None = node
        while current is not None and parents.get(current) is not None:
            current = parents[current]
            length += 1
        return length


__all__ = [
    "CodeKnowledgeGraph",
    "CodeNode",
    "CodeEdge",
    "NodeType",
    "EdgeType",
]
