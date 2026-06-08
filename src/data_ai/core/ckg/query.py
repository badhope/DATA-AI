"""
图谱查询

提供代码图谱的高级查询能力。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...utils.logging import get_logger
from .graph import CodeKnowledgeGraph, CodeNode, NodeType

logger = get_logger(__name__)


@dataclass
class QueryResult:
    """查询结果"""

    query: str
    nodes: list[CodeNode]
    relationships: list[dict[str, Any]]
    explanation: str


class GraphQuery:
    """
    图谱查询器

    提供自然语言式的图谱查询能力。
    """

    def __init__(self, graph: CodeKnowledgeGraph):
        self._graph = graph

    def find_class(self, name: str) -> QueryResult:
        """查找类"""
        nodes = self._graph.find_by_name(name)
        class_nodes = [n for n in nodes if n.node_type == NodeType.CLASS]

        relationships = []
        for node in class_nodes:
            deps = self._graph.get_dependencies(node.id)
            dependents = self._graph.get_dependents(node.id)

            relationships.append(
                {
                    "node": node.name,
                    "dependencies": [d.name for d in deps],
                    "dependents": [d.name for d in dependents],
                }
            )

        return QueryResult(
            query=f"find class {name}",
            nodes=class_nodes,
            relationships=relationships,
            explanation=f"找到 {len(class_nodes)} 个名为 '{name}' 的类",
        )

    def find_function(self, name: str) -> QueryResult:
        """查找函数"""
        nodes = self._graph.find_by_name(name)
        func_nodes = [n for n in nodes if n.node_type in (NodeType.FUNCTION, NodeType.METHOD)]

        relationships = []
        for node in func_nodes:
            deps = self._graph.get_dependencies(node.id)

            relationships.append(
                {
                    "node": node.name,
                    "location": node.location.file_path if node.location else "unknown",
                    "dependencies": [d.name for d in deps],
                }
            )

        return QueryResult(
            query=f"find function {name}",
            nodes=func_nodes,
            relationships=relationships,
            explanation=f"找到 {len(func_nodes)} 个名为 '{name}' 的函数",
        )

    def find_usages(self, symbol_name: str) -> QueryResult:
        """查找符号的使用位置"""
        nodes = self._graph.find_by_name(symbol_name)

        all_usages = []
        for node in nodes:
            dependents = self._graph.get_dependents(node.id)
            for dep in dependents:
                all_usages.append(
                    {
                        "used_in": dep.name,
                        "type": dep.node_type.value,
                        "location": dep.location.file_path if dep.location else "unknown",
                    }
                )

        return QueryResult(
            query=f"find usages of {symbol_name}",
            nodes=[],
            relationships=all_usages,
            explanation=f"'{symbol_name}' 被 {len(all_usages)} 处引用",
        )

    def find_dependencies(self, file_path: str) -> QueryResult:
        """查找文件的依赖"""
        file_node = self._graph.get_node(f"file:{file_path}")

        if not file_node:
            return QueryResult(
                query=f"find dependencies of {file_path}",
                nodes=[],
                relationships=[],
                explanation=f"未找到文件: {file_path}",
            )

        deps = self._graph.get_dependencies(file_node.id)

        relationships = [
            {
                "dependency": d.name,
                "type": d.node_type.value,
            }
            for d in deps
        ]

        return QueryResult(
            query=f"find dependencies of {file_path}",
            nodes=[file_node],
            relationships=relationships,
            explanation=f"'{file_path}' 有 {len(deps)} 个依赖",
        )

    def analyze_structure(self) -> dict[str, Any]:
        """分析代码结构"""
        stats = self._graph.get_statistics()

        # 找出最被依赖的节点
        dependency_counts = {}
        for node_id, node in self._graph._nodes.items():
            dependents = self._graph.get_dependents(node_id)
            if dependents:
                dependency_counts[node.name] = len(dependents)

        most_depended = sorted(
            dependency_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "statistics": stats,
            "most_depended_symbols": most_depended,
        }
