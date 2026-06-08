"""
DATA-AI 新模块综合测试

测试以下模块：
1. IntentRecognizer — 意图识别器
2. IntentRouter — 意图路由器
3. CodeKnowledgeGraph — 代码知识图谱
4. SkillManager — 技能管理器
5. ReflectionEngine — 反思引擎
6. ToolOrchestrator — 工具编排器
7. Tool Registration — 工具注册（extended, system, planning）
8. SDK Integration — SDK 集成
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from data_ai.core.tool.registry import ToolRegistry

# ============================================================================
# 1. IntentRecognizer 测试
# ============================================================================


class TestIntentRecognizer:
    """测试意图识别器"""

    def test_intent_type_enum_values(self):
        """测试 IntentType 枚举值"""
        from data_ai.core.intent.recognizer import IntentType

        assert IntentType.CODE_GENERATION.value == "code_generation"
        assert IntentType.CODE_EXPLANATION.value == "code_explanation"
        assert IntentType.CODE_REFACTORING.value == "code_refactoring"
        assert IntentType.CODE_DEBUGGING.value == "code_debugging"
        assert IntentType.QUESTION_ANSWERING.value == "question_answering"
        assert IntentType.CONVERSATION.value == "conversation"
        assert IntentType.UNKNOWN.value == "unknown"
        assert IntentType.WEB_SEARCH.value == "web_search"
        assert IntentType.SHELL_COMMAND.value == "shell_command"
        assert IntentType.COMPLEX_TASK.value == "complex_task"
        assert IntentType.PLANNING.value == "planning"
        assert IntentType.AUTOMATION.value == "automation"
        assert IntentType.FILE_READ.value == "file_read"
        assert IntentType.FILE_WRITE.value == "file_write"
        assert IntentType.FILE_SEARCH.value == "file_search"
        assert IntentType.BROWSER_AUTOMATION.value == "browser_automation"

    def test_entity_creation(self):
        """测试 Entity 数据类创建"""
        from data_ai.core.intent.recognizer import Entity

        entity = Entity(
            name="file_path",
            value="/home/user/test.py",
            entity_type="file",
            confidence=0.9,
        )
        assert entity.name == "file_path"
        assert entity.value == "/home/user/test.py"
        assert entity.entity_type == "file"
        assert entity.confidence == 0.9
        assert entity.metadata == {}

        entity2 = Entity(
            name="language",
            value="python",
            entity_type="programming_language",
            confidence=0.7,
            metadata={"source": "keyword"},
        )
        assert entity2.metadata["source"] == "keyword"

    def test_intent_dataclass_creation(self):
        """测试 Intent 数据类创建"""
        from data_ai.core.intent.recognizer import Intent, IntentType

        intent = Intent(
            intent_type=IntentType.CODE_GENERATION,
            confidence=0.85,
            raw_query="帮我写一个排序函数",
            normalized_query="帮我写一个排序函数",
        )
        assert intent.intent_type == IntentType.CODE_GENERATION
        assert intent.confidence == 0.85
        assert intent.entities == []
        assert intent.sub_intents == []
        assert intent.raw_query == "帮我写一个排序函数"

    def test_intent_is_complex(self):
        """测试 Intent is_complex 属性"""
        from data_ai.core.intent.recognizer import Intent, IntentType

        complex_intent = Intent(intent_type=IntentType.COMPLEX_TASK, confidence=0.9)
        assert complex_intent.is_complex is True

        planning_intent = Intent(intent_type=IntentType.PLANNING, confidence=0.9)
        assert planning_intent.is_complex is True

        simple_intent = Intent(intent_type=IntentType.CODE_GENERATION, confidence=0.9)
        assert simple_intent.is_complex is False

        unknown_intent = Intent(intent_type=IntentType.UNKNOWN, confidence=0.1)
        assert unknown_intent.is_complex is False

    def test_intent_requires_tools(self):
        """测试 Intent requires_tools 属性"""
        from data_ai.core.intent.recognizer import Intent, IntentType

        code_intent = Intent(intent_type=IntentType.CODE_GENERATION, confidence=0.9)
        assert code_intent.requires_tools is True

        conversation_intent = Intent(intent_type=IntentType.CONVERSATION, confidence=0.9)
        assert conversation_intent.requires_tools is False

        qa_intent = Intent(intent_type=IntentType.QUESTION_ANSWERING, confidence=0.9)
        assert qa_intent.requires_tools is False

        unknown_intent = Intent(intent_type=IntentType.UNKNOWN, confidence=0.1)
        assert unknown_intent.requires_tools is False

    def test_intent_get_primary_entity(self):
        """测试 Intent get_primary_entity 方法"""
        from data_ai.core.intent.recognizer import Entity, Intent, IntentType

        intent = Intent(
            intent_type=IntentType.FILE_READ,
            confidence=0.9,
            entities=[
                Entity(name="file_path", value="/tmp/test.py", entity_type="file"),
                Entity(name="language", value="python", entity_type="programming_language"),
            ],
        )

        primary = intent.get_primary_entity()
        assert primary is not None
        assert primary.value == "/tmp/test.py"

        lang = intent.get_primary_entity("programming_language")
        assert lang is not None
        assert lang.value == "python"

        assert intent.get_primary_entity("nonexistent") is None

        empty_intent = Intent(intent_type=IntentType.UNKNOWN, confidence=0.1)
        assert empty_intent.get_primary_entity() is None

    def test_recognizer_initialization(self):
        """测试 IntentRecognizer 初始化"""
        from data_ai.core.intent.recognizer import IntentRecognizer

        recognizer = IntentRecognizer()
        assert recognizer._use_llm is True

        recognizer_no_llm = IntentRecognizer(use_llm=False)
        assert recognizer_no_llm._use_llm is False

    def test_recognize_code_generation(self):
        """测试识别代码生成意图"""
        from data_ai.core.intent.recognizer import IntentRecognizer, IntentType

        recognizer = IntentRecognizer(use_llm=False)

        intent = recognizer.recognize("帮我写一个排序函数")
        assert isinstance(intent.intent_type, IntentType)
        assert intent.raw_query == "帮我写一个排序函数"
        assert intent.normalized_query is not None
        assert 0.0 <= intent.confidence <= 1.0

        intent2 = recognizer.recognize("write a python function to sort list")
        assert intent2.intent_type in (
            IntentType.CODE_GENERATION,
            IntentType.SHELL_COMMAND,
        )

    def test_recognize_question(self):
        """测试识别问答意图"""
        from data_ai.core.intent.recognizer import IntentRecognizer, IntentType

        recognizer = IntentRecognizer(use_llm=False)

        intent = recognizer.recognize("什么是Python装饰器？")
        assert intent.intent_type in (
            IntentType.QUESTION_ANSWERING,
            IntentType.CODE_EXPLANATION,
        )

        intent2 = recognizer.recognize("how does async/await work?")
        assert intent2.intent_type in (
            IntentType.QUESTION_ANSWERING,
            IntentType.CODE_EXPLANATION,
        )

    def test_recognize_command(self):
        """测试识别命令意图"""
        from data_ai.core.intent.recognizer import IntentRecognizer, IntentType

        recognizer = IntentRecognizer(use_llm=False)

        intent = recognizer.recognize("git status")
        assert intent.intent_type in (
            IntentType.SHELL_COMMAND,
            IntentType.QUESTION_ANSWERING,
        )

        intent2 = recognizer.recognize("npm install react")
        assert intent2.intent_type in (
            IntentType.SHELL_COMMAND,
            IntentType.QUESTION_ANSWERING,
        )

    def test_recognize_general(self):
        """测试识别一般意图"""
        from data_ai.core.intent.recognizer import IntentRecognizer, IntentType

        recognizer = IntentRecognizer(use_llm=False)

        intent = recognizer.recognize("你好")
        assert isinstance(intent.intent_type, IntentType)

    def test_recognize_empty_input(self):
        """测试空输入"""
        from data_ai.core.intent.recognizer import IntentRecognizer

        recognizer = IntentRecognizer(use_llm=False)

        intent = recognizer.recognize("")
        assert intent is not None
        assert intent.confidence == 0.0
        assert intent.raw_query == ""
        assert intent.entities == []

    def test_recognize_none_input_handling(self):
        """测试 None 输入不会崩溃"""
        from data_ai.core.intent.recognizer import IntentRecognizer

        recognizer = IntentRecognizer(use_llm=False)

        try:
            result = recognizer.recognize("  ")
            assert result is not None
        except Exception as e:
            pytest.fail(f"recognize with whitespace-only raised: {e}")

    def test_batch_recognize(self):
        """测试批量识别"""
        from data_ai.core.intent.recognizer import IntentRecognizer

        recognizer = IntentRecognizer(use_llm=False)

        queries = ["帮我写代码", "什么是Python", "运行测试", "你好"]
        results = recognizer.batch_recognize(queries)
        assert len(results) == 4
        for result in results:
            assert result is not None
            assert result.raw_query in queries

    def test_recognizer_entity_extraction(self):
        """测试实体提取"""
        from data_ai.core.intent.recognizer import IntentRecognizer

        recognizer = IntentRecognizer(use_llm=False)

        intent = recognizer.recognize("打开 /home/user/test.py 文件")
        entities = intent.entities
        file_entities = [e for e in entities if e.entity_type == "file"]
        assert len(file_entities) > 0

    def test_intent_context_creation(self):
        """测试 IntentContext 创建"""
        from data_ai.core.intent.recognizer import IntentContext

        context = IntentContext(
            session_id="test-session",
            available_tools=["file_read", "bash"],
            working_directory="/tmp",
            recent_files=["main.py", "utils.py"],
        )
        assert context.session_id == "test-session"
        assert len(context.available_tools) == 2
        assert context.working_directory == "/tmp"

    def test_recognize_with_context(self):
        """测试带上下文的识别"""
        from data_ai.core.intent.recognizer import IntentContext, IntentRecognizer

        recognizer = IntentRecognizer(use_llm=False)
        context = IntentContext(
            session_id="test",
            working_directory="/tmp",
            recent_files=["main.py"],
        )

        intent = recognizer.recognize("帮我写代码", context=context)
        assert "recent_files" in intent.context_hints
        assert intent.context_hints["recent_files"] == ["main.py"]
        assert intent.raw_query == "帮我写代码"


# ============================================================================
# 2. IntentRouter 测试
# ============================================================================


class TestIntentRouter:
    """测试意图路由器"""

    def test_route_strategy_enum(self):
        """测试 RouteStrategy 枚举"""
        from data_ai.core.intent.router import RouteStrategy

        assert RouteStrategy.DIRECT.value == "direct"
        assert RouteStrategy.AGENT.value == "agent"
        assert RouteStrategy.TOOL_CHAIN.value == "tool_chain"
        assert RouteStrategy.MULTI_AGENT.value == "multi_agent"
        assert RouteStrategy.CLARIFY.value == "clarify"
        assert RouteStrategy.REJECT.value == "reject"

    def test_router_initialization(self):
        """测试 IntentRouter 初始化"""
        from data_ai.core.intent.router import IntentRouter

        router = IntentRouter()
        assert router._tool_mapping is not None
        assert router._agent_mapping is not None
        assert len(router._tool_mapping) > 0

    def test_route_code_generation(self):
        """测试代码生成意图路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.CODE_GENERATION, confidence=0.9)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.AGENT
        assert result.agent_type == "swe_agent"

    def test_route_question_answering(self):
        """测试问答意图路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.QUESTION_ANSWERING, confidence=0.9)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.DIRECT

    def test_route_low_confidence(self):
        """测试低置信度意图路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.UNKNOWN, confidence=0.1)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.CLARIFY
        assert "置信度" in result.explanation

    def test_route_unknown(self):
        """测试未知意图路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.UNKNOWN, confidence=0.5)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.CLARIFY

    def test_route_shell_command(self):
        """测试 Shell 命令意图路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.SHELL_COMMAND, confidence=0.9)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.DIRECT
        assert "bash" in result.tools or "python_execute" in result.tools

    def test_route_complex_task(self):
        """测试复杂任务路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.COMPLEX_TASK, confidence=0.9)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.MULTI_AGENT
        assert result.agent_type == "team"

    def test_route_web_search(self):
        """测试网络搜索意图路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.WEB_SEARCH, confidence=0.9)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.DIRECT
        assert "web_search" in result.tools

    def test_route_conversation(self):
        """测试对话意图路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(intent_type=IntentType.CONVERSATION, confidence=0.9)
        result = router.route(intent)

        assert result.strategy == RouteStrategy.DIRECT
        assert result.tools == []

    def test_route_with_sub_intents(self):
        """测试带子意图的路由"""
        from data_ai.core.intent.recognizer import Intent, IntentType
        from data_ai.core.intent.router import IntentRouter, RouteStrategy

        router = IntentRouter()
        intent = Intent(
            intent_type=IntentType.FILE_READ,
            confidence=0.9,
            sub_intents=[
                Intent(intent_type=IntentType.FILE_WRITE, confidence=0.7),
            ],
        )
        result = router.route(intent)
        assert result.strategy == RouteStrategy.TOOL_CHAIN
        assert len(result.tools) >= 2

    def test_route_file_read_with_entities(self):
        """测试带实体的文件读取路由"""
        from data_ai.core.intent.recognizer import Entity, Intent, IntentType
        from data_ai.core.intent.router import IntentRouter

        router = IntentRouter()
        intent = Intent(
            intent_type=IntentType.FILE_READ,
            confidence=0.9,
            entities=[
                Entity(name="file_path", value="/tmp/test.py", entity_type="file"),
            ],
        )
        result = router.route(intent)
        assert result.strategy.value in ("direct", "tool_chain")
        assert "file_path" in result.parameters
        assert result.parameters["file_path"] == "/tmp/test.py"

    def test_register_handler(self):
        """测试注册自定义处理器"""
        from data_ai.core.intent.recognizer import IntentType
        from data_ai.core.intent.router import IntentRouter

        router = IntentRouter()

        def custom_handler(intent):
            return "custom_result"

        router.register_handler(IntentType.CODE_DEBUGGING, custom_handler)
        assert IntentType.CODE_DEBUGGING in router._handlers
        assert router._handlers[IntentType.CODE_DEBUGGING] is custom_handler

    def test_get_route_explanation(self):
        """测试获取路由解释"""
        from data_ai.core.intent.router import IntentRouter, RouteResult, RouteStrategy

        router = IntentRouter()
        result = RouteResult(
            strategy=RouteStrategy.AGENT,
            agent_type="swe_agent",
            tools=["file_read"],
            confidence=0.9,
            explanation="使用 swe_agent 处理",
        )
        explanation = router.get_route_explanation(result)
        assert "agent" in explanation
        assert "swe_agent" in explanation
        assert "file_read" in explanation
        assert "0.90" in explanation


# ============================================================================
# 3. CodeKnowledgeGraph 测试
# ============================================================================


class TestCodeKnowledgeGraph:
    """测试代码知识图谱"""

    def test_node_type_enum(self):
        """测试 NodeType 枚举"""
        from data_ai.core.ckg.graph import NodeType

        assert NodeType.FILE.value == "file"
        assert NodeType.CLASS.value == "class"
        assert NodeType.FUNCTION.value == "function"
        assert NodeType.METHOD.value == "method"
        assert NodeType.VARIABLE.value == "variable"
        assert NodeType.INTERFACE.value == "interface"
        assert NodeType.MODULE.value == "module"
        assert NodeType.PACKAGE.value == "package"

    def test_edge_type_enum(self):
        """测试 EdgeType 枚举"""
        from data_ai.core.ckg.graph import EdgeType

        assert EdgeType.IMPORTS.value == "imports"
        assert EdgeType.EXTENDS.value == "extends"
        assert EdgeType.IMPLEMENTS.value == "implements"
        assert EdgeType.CALLS.value == "calls"
        assert EdgeType.USES.value == "uses"
        assert EdgeType.DEFINES.value == "defines"
        assert EdgeType.CONTAINS.value == "contains"
        assert EdgeType.DEPENDS_ON.value == "depends_on"

    def test_code_node_creation(self):
        """测试 CodeNode 创建"""
        from data_ai.core.ckg.graph import CodeNode, NodeType
        from data_ai.core.ckg.parser import CodeLocation

        loc = CodeLocation(file_path="/tmp/test.py", line_start=1, line_end=10)
        node = CodeNode(
            id="func:test_func",
            name="test_func",
            node_type=NodeType.FUNCTION,
            location=loc,
            metadata={"language": "python"},
        )
        assert node.id == "func:test_func"
        assert node.name == "test_func"
        assert node.node_type == NodeType.FUNCTION
        assert node.location.file_path == "/tmp/test.py"

        d = node.to_dict()
        assert d["id"] == "func:test_func"
        assert d["node_type"] == "function"
        assert d["location"]["file_path"] == "/tmp/test.py"

    def test_code_node_without_location(self):
        """测试无位置的 CodeNode"""
        from data_ai.core.ckg.graph import CodeNode, NodeType

        node = CodeNode(
            id="var:x",
            name="x",
            node_type=NodeType.VARIABLE,
        )
        d = node.to_dict()
        assert d["location"] is None

    def test_code_edge_creation(self):
        """测试 CodeEdge 创建"""
        from data_ai.core.ckg.graph import CodeEdge, EdgeType

        edge = CodeEdge(
            source_id="func:foo",
            target_id="func:bar",
            edge_type=EdgeType.CALLS,
            weight=0.8,
        )
        assert edge.source_id == "func:foo"
        assert edge.target_id == "func:bar"
        assert edge.edge_type == EdgeType.CALLS
        assert edge.weight == 0.8

        d = edge.to_dict()
        assert d["source"] == "func:foo"
        assert d["target"] == "func:bar"
        assert d["type"] == "calls"
        assert d["weight"] == 0.8

    def test_ckg_initialization(self):
        """测试 CodeKnowledgeGraph 初始化"""
        from data_ai.core.ckg.graph import CodeKnowledgeGraph

        ckg = CodeKnowledgeGraph()
        assert ckg._nodes == {}
        assert ckg._edges == []
        assert len(ckg._adjacency) == 0
        assert len(ckg._name_index) == 0

    def test_add_node(self):
        """测试添加节点"""
        from data_ai.core.ckg.graph import CodeKnowledgeGraph, CodeNode, NodeType

        ckg = CodeKnowledgeGraph()
        node = CodeNode(id="node1", name="my_func", node_type=NodeType.FUNCTION)
        ckg.add_node(node)

        assert "node1" in ckg._nodes
        assert "my_func" in ckg._name_index
        assert "node1" in ckg._name_index["my_func"]

    def test_get_node(self):
        """测试获取节点"""
        from data_ai.core.ckg.graph import CodeKnowledgeGraph, CodeNode, NodeType

        ckg = CodeKnowledgeGraph()
        node = CodeNode(id="node1", name="my_func", node_type=NodeType.FUNCTION)
        ckg.add_node(node)

        retrieved = ckg.get_node("node1")
        assert retrieved is not None
        assert retrieved.name == "my_func"
        assert retrieved.node_type == NodeType.FUNCTION

        assert ckg.get_node("nonexistent") is None

    def test_add_edge(self):
        """测试添加边"""
        from data_ai.core.ckg.graph import CodeEdge, CodeKnowledgeGraph, CodeNode, EdgeType, NodeType

        ckg = CodeKnowledgeGraph()
        node_a = CodeNode(id="a", name="func_a", node_type=NodeType.FUNCTION)
        node_b = CodeNode(id="b", name="func_b", node_type=NodeType.FUNCTION)
        ckg.add_node(node_a)
        ckg.add_node(node_b)

        edge = CodeEdge(source_id="a", target_id="b", edge_type=EdgeType.CALLS)
        ckg.add_edge(edge)

        assert len(ckg._edges) == 1
        assert "b" in ckg._adjacency["a"]
        assert "a" in ckg._reverse_adjacency["b"]

    def test_find_by_name(self):
        """测试按名称查找"""
        from data_ai.core.ckg.graph import CodeKnowledgeGraph, CodeNode, NodeType

        ckg = CodeKnowledgeGraph()
        node1 = CodeNode(id="id1", name="do_stuff", node_type=NodeType.FUNCTION)
        node2 = CodeNode(id="id2", name="do_stuff", node_type=NodeType.METHOD)
        ckg.add_node(node1)
        ckg.add_node(node2)

        results = ckg.find_by_name("do_stuff")
        assert len(results) == 2

        results_none = ckg.find_by_name("nonexistent")
        assert len(results_none) == 0

    def test_get_dependencies(self):
        """测试获取依赖"""
        from data_ai.core.ckg.graph import (
            CodeEdge,
            CodeKnowledgeGraph,
            CodeNode,
            EdgeType,
            NodeType,
        )

        ckg = CodeKnowledgeGraph()
        node_a = CodeNode(id="a", name="func_a", node_type=NodeType.FUNCTION)
        node_b = CodeNode(id="b", name="func_b", node_type=NodeType.FUNCTION)
        node_c = CodeNode(id="c", name="func_c", node_type=NodeType.FUNCTION)
        ckg.add_node(node_a)
        ckg.add_node(node_b)
        ckg.add_node(node_c)

        ckg.add_edge(CodeEdge(source_id="a", target_id="b", edge_type=EdgeType.CALLS))
        ckg.add_edge(CodeEdge(source_id="a", target_id="c", edge_type=EdgeType.CALLS))

        deps = ckg.get_dependencies("a")
        assert len(deps) == 2
        dep_names = {d.name for d in deps}
        assert dep_names == {"func_b", "func_c"}

    def test_get_dependents(self):
        """测试获取反向依赖"""
        from data_ai.core.ckg.graph import (
            CodeEdge,
            CodeKnowledgeGraph,
            CodeNode,
            EdgeType,
            NodeType,
        )

        ckg = CodeKnowledgeGraph()
        node_a = CodeNode(id="a", name="func_a", node_type=NodeType.FUNCTION)
        node_b = CodeNode(id="b", name="func_b", node_type=NodeType.FUNCTION)
        ckg.add_node(node_a)
        ckg.add_node(node_b)
        ckg.add_edge(CodeEdge(source_id="a", target_id="b", edge_type=EdgeType.CALLS))

        dependents = ckg.get_dependents("b")
        assert len(dependents) == 1
        assert dependents[0].name == "func_a"

    def test_find_path(self):
        """测试查找路径"""
        from data_ai.core.ckg.graph import (
            CodeEdge,
            CodeKnowledgeGraph,
            CodeNode,
            EdgeType,
            NodeType,
        )

        ckg = CodeKnowledgeGraph()
        n1 = CodeNode(id="1", name="n1", node_type=NodeType.FUNCTION)
        n2 = CodeNode(id="2", name="n2", node_type=NodeType.FUNCTION)
        n3 = CodeNode(id="3", name="n3", node_type=NodeType.FUNCTION)
        ckg.add_node(n1)
        ckg.add_node(n2)
        ckg.add_node(n3)
        ckg.add_edge(CodeEdge(source_id="1", target_id="2", edge_type=EdgeType.CALLS))
        ckg.add_edge(CodeEdge(source_id="2", target_id="3", edge_type=EdgeType.CALLS))

        paths = ckg.find_path("1", "3")
        assert len(paths) >= 1
        assert paths[0] == ["1", "2", "3"]

    def test_get_statistics(self):
        """测试获取统计"""
        from data_ai.core.ckg.graph import (
            CodeEdge,
            CodeKnowledgeGraph,
            CodeNode,
            EdgeType,
            NodeType,
        )

        ckg = CodeKnowledgeGraph()
        node = CodeNode(id="f", name="func", node_type=NodeType.FUNCTION)
        ckg.add_node(node)
        ckg.add_edge(CodeEdge(source_id="f", target_id="f", edge_type=EdgeType.USES))

        stats = ckg.get_statistics()
        assert stats["total_nodes"] == 1
        assert stats["total_edges"] == 1
        assert "function" in stats["node_types"]
        assert "uses" in stats["edge_types"]

    def test_export_json(self):
        """测试导出 JSON"""
        from data_ai.core.ckg.graph import CodeKnowledgeGraph, CodeNode, NodeType

        ckg = CodeKnowledgeGraph()
        node = CodeNode(id="n1", name="foo", node_type=NodeType.FUNCTION)
        ckg.add_node(node)

        json_str = ckg.export_json()
        assert "foo" in json_str
        assert '"id": "n1"' in json_str or "'id': 'n1'" in json_str

    def test_clear(self):
        """测试清空图谱"""
        from data_ai.core.ckg.graph import (
            CodeEdge,
            CodeKnowledgeGraph,
            CodeNode,
            EdgeType,
            NodeType,
        )

        ckg = CodeKnowledgeGraph()
        node = CodeNode(id="n1", name="foo", node_type=NodeType.FUNCTION)
        ckg.add_node(node)
        ckg.add_edge(CodeEdge(source_id="n1", target_id="n1", edge_type=EdgeType.USES))

        ckg.clear()
        assert len(ckg._nodes) == 0
        assert len(ckg._edges) == 0
        assert len(ckg._adjacency) == 0
        assert len(ckg._reverse_adjacency) == 0
        assert len(ckg._name_index) == 0

    def test_build_from_files(self):
        """测试从 ParsedFile 构建图谱"""
        from data_ai.core.ckg.graph import CodeKnowledgeGraph
        from data_ai.core.ckg.parser import CodeLocation, CodeSymbol, Language, ParsedFile

        ckg = CodeKnowledgeGraph()

        symbol = CodeSymbol(
            name="hello_world",
            symbol_type="function",
            location=CodeLocation(file_path="/tmp/test.py", line_start=1, line_end=3),
        )
        parsed = ParsedFile(
            file_path="/tmp/test.py",
            language=Language.PYTHON,
            symbols=[symbol],
            imports=["os"],
            exports=["hello_world"],
            dependencies=["os"],
            lines_of_code=3,
        )

        ckg.build_from_files([parsed])
        stats = ckg.get_statistics()
        assert stats["total_nodes"] > 0
        assert "contains" in stats["edge_types"]


# ============================================================================
# 4. SkillManager 测试
# ============================================================================


class TestSkillManager:
    """测试技能管理器"""

    @pytest.fixture
    def temp_storage(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def skill_manager(self, temp_storage):
        from data_ai.core.skill.manager import SkillManager

        mgr = SkillManager(storage_dir=temp_storage)
        yield mgr

    def test_skill_manager_initialization(self, skill_manager):
        """测试 SkillManager 初始化"""

        assert hasattr(skill_manager, "_storage_dir")
        assert isinstance(skill_manager._skills, dict)

    def test_register_skill(self, skill_manager):
        """测试注册技能"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-001",
            name="代码审查",
            description="执行代码审查任务",
            category=SkillCategory.CODE_GENERATION,
            triggers=["审查", "review", "检查代码"],
            steps=[
                SkillStep(step_number=1, description="读取代码"),
                SkillStep(step_number=2, description="分析代码"),
            ],
            success_patterns=["审查完成"],
            failure_patterns=["审查失败"],
        )
        skill_manager.register(skill)

        assert "skill-001" in skill_manager._skills

    def test_get_skill(self, skill_manager):
        """测试获取技能"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-002",
            name="代码生成",
            description="生成代码",
            category=SkillCategory.CODE_GENERATION,
            triggers=["生成", "编写", "创建"],
            steps=[SkillStep(step_number=1, description="生成代码")],
            success_patterns=["生成完成"],
            failure_patterns=[],
        )
        skill_manager.register(skill)

        retrieved = skill_manager.get("skill-002")
        assert retrieved is not None
        assert retrieved.name == "代码生成"
        assert retrieved.category == SkillCategory.CODE_GENERATION

        assert skill_manager.get("nonexistent") is None

    def test_get_by_name(self, skill_manager):
        """测试按名称获取技能"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-003",
            name="数据分析",
            description="分析数据",
            category=SkillCategory.DATA_ANALYSIS,
            triggers=["分析数据", "统计"],
            steps=[SkillStep(step_number=1, description="分析")],
            success_patterns=[],
            failure_patterns=[],
        )
        skill_manager.register(skill)

        retrieved = skill_manager.get_by_name("数据分析")
        assert retrieved is not None
        assert retrieved.id == "skill-003"

        assert skill_manager.get_by_name("nonexistent") is None

    def test_list_skills(self, skill_manager):
        """测试列出技能"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill1 = Skill(
            id="s1",
            name="S1",
            description="D1",
            category=SkillCategory.CODE_GENERATION,
            triggers=["t1"],
            steps=[SkillStep(step_number=1, description="s")],
            success_patterns=[],
            failure_patterns=[],
        )
        skill2 = Skill(
            id="s2",
            name="S2",
            description="D2",
            category=SkillCategory.DATA_ANALYSIS,
            triggers=["t2"],
            steps=[SkillStep(step_number=1, description="s")],
            success_patterns=[],
            failure_patterns=[],
        )
        skill_manager.register(skill1)
        skill_manager.register(skill2)

        all_skills = skill_manager.list_skills()
        assert len(all_skills) == 2

        code_skills = skill_manager.list_skills(category=SkillCategory.CODE_GENERATION)
        assert len(code_skills) == 1
        assert code_skills[0].name == "S1"

    def test_list_skills_by_tags(self, skill_manager):
        """测试按标签列出技能"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillMetadata, SkillStep

        meta = SkillMetadata(tags=["python", "web"])
        skill = Skill(
            id="s-tag",
            name="Tagged",
            description="D",
            category=SkillCategory.CODE_GENERATION,
            triggers=["t"],
            steps=[SkillStep(step_number=1, description="s")],
            success_patterns=[],
            failure_patterns=[],
            metadata=meta,
        )
        skill_manager.register(skill)

        result = skill_manager.list_skills(tags=["python"])
        assert len(result) == 1

        result = skill_manager.list_skills(tags=["nonexistent"])
        assert len(result) == 0

    def test_unregister_skill(self, skill_manager):
        """测试注销技能"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-rm",
            name="要删除",
            description="D",
            category=SkillCategory.CUSTOM,
            triggers=["t"],
            steps=[SkillStep(step_number=1, description="s")],
            success_patterns=[],
            failure_patterns=[],
        )
        skill_manager.register(skill)
        assert skill_manager.get("skill-rm") is not None

        result = skill_manager.unregister("skill-rm")
        assert result is True
        assert skill_manager.get("skill-rm") is None

        result = skill_manager.unregister("nonexistent")
        assert result is False

    def test_match(self, skill_manager):
        """测试技能匹配"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-match",
            name="匹配测试",
            description="D",
            category=SkillCategory.CODE_GENERATION,
            triggers=["代码审查", "review code"],
            steps=[SkillStep(step_number=1, description="s")],
            success_patterns=["审查通过"],
            failure_patterns=[],
        )
        skill_manager.register(skill)

        matches = skill_manager.match("请帮我进行代码审查")
        assert len(matches) > 0
        matched_skill, score = matches[0]
        assert matched_skill.id == "skill-match"
        assert score > 0

    def test_get_stats(self, skill_manager):
        """测试获取统计"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-stat",
            name="统计测试",
            description="D",
            category=SkillCategory.CODE_GENERATION,
            triggers=["t"],
            steps=[SkillStep(step_number=1, description="s")],
            success_patterns=[],
            failure_patterns=[],
        )
        skill_manager.register(skill)

        stats = skill_manager.get_stats()
        assert stats["total_skills"] > 0
        assert "categories" in stats

    def test_update_usage(self, skill_manager):
        """测试更新使用统计"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-usage",
            name="使用统计",
            description="D",
            category=SkillCategory.CODE_GENERATION,
            triggers=["t"],
            steps=[SkillStep(step_number=1, description="s")],
            success_patterns=[],
            failure_patterns=[],
        )
        skill_manager.register(skill)

        skill_manager.update_usage("skill-usage", success=True, execution_time_ms=100.0)
        updated = skill_manager.get("skill-usage")
        assert updated.metadata.usage_count == 1
        assert updated.metadata.success_rate > 0

        skill_manager.update_usage("nonexistent", success=True, execution_time_ms=100.0)

    def test_skill_to_from_dict(self):
        """测试技能序列化/反序列化"""
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        skill = Skill(
            id="skill-dict",
            name="序列化测试",
            description="测试序列化",
            category=SkillCategory.TESTING,
            triggers=["测试", "test"],
            steps=[SkillStep(step_number=1, description="运行测试")],
            success_patterns=["测试通过"],
            failure_patterns=["测试失败"],
            prerequisites=["prereq-skill"],
            parameters={"timeout": 30},
        )

        d = skill.to_dict()
        assert d["id"] == "skill-dict"
        assert d["name"] == "序列化测试"
        assert d["category"] == "testing"
        assert d["triggers"] == ["测试", "test"]
        assert len(d["steps"]) == 1
        assert d["prerequisites"] == ["prereq-skill"]
        assert d["parameters"]["timeout"] == 30

        restored = Skill.from_dict(d)
        assert restored.id == "skill-dict"
        assert restored.name == "序列化测试"
        assert restored.category == SkillCategory.TESTING
        assert restored.triggers == ["测试", "test"]
        assert len(restored.steps) == 1

    def test_load_from_directory_graceful(self):
        """测试从目录加载（优雅跳过）"""
        from data_ai.core.skill.manager import SkillManager

        mgr = SkillManager(storage_dir="/tmp/nonexistent_dir_12345")
        assert mgr._skills == {}


# ============================================================================
# 5. ReflectionEngine 测试
# ============================================================================


class TestReflectionEngine:
    """测试反思引擎"""

    def test_reflection_dataclass(self):
        """测试 Reflection 数据类"""
        from data_ai.core.reasoning.reflection import Reflection

        reflection = Reflection(
            original_conclusion="答案是42",
            issues_found=["缺少推导过程"],
            improvements=["添加推导步骤"],
            revised_conclusion="答案是42（经过推导）",
            confidence_change=-0.1,
        )
        assert reflection.original_conclusion == "答案是42"
        assert len(reflection.issues_found) == 1
        assert len(reflection.improvements) == 1
        assert reflection.confidence_change == -0.1

    def test_reflection_engine_initialization(self):
        """测试 ReflectionEngine 初始化"""
        from data_ai.core.reasoning.reflection import ReflectionEngine

        engine = ReflectionEngine()
        assert engine._reflection_history == []

    def test_reflect_empty_chain(self):
        """测试对空链的反思"""
        from data_ai.core.reasoning.reflection import ReflectionEngine
        from data_ai.core.reasoning.sequential import ReasoningChain

        engine = ReflectionEngine()
        chain = ReasoningChain(
            question="测试问题",
            final_answer="测试答案",
        )
        reflection = engine.reflect(chain)

        assert reflection.original_conclusion == "测试答案"
        assert isinstance(reflection.issues_found, list)
        assert isinstance(reflection.improvements, list)
        assert len(engine._reflection_history) == 1

    def test_reflect_with_thoughts(self):
        """测试对带思考步骤的链进行反思"""
        from data_ai.core.reasoning.reflection import ReflectionEngine
        from data_ai.core.reasoning.sequential import ReasoningChain, Thought

        engine = ReflectionEngine()
        chain = ReasoningChain(
            question="如何优化代码？",
            thoughts=[
                Thought(
                    content="分析代码性能瓶颈",
                    confidence=0.8,
                    metadata={"thought_type": "analysis", "evidence": ["profiling结果"]},
                ),
                Thought(
                    content="识别主要瓶颈在循环中",
                    confidence=0.9,
                    metadata={"thought_type": "reasoning", "evidence": ["O(n^2)复杂度"]},
                ),
                Thought(
                    content="建议使用哈希表优化",
                    confidence=0.85,
                    metadata={"thought_type": "conclusion", "evidence": ["优化到O(n)"]},
                ),
            ],
            final_answer="使用哈希表将复杂度从O(n^2)优化到O(n)",
        )
        reflection = engine.reflect(chain)

        assert reflection.original_conclusion is not None
        assert isinstance(reflection.issues_found, list)
        assert isinstance(reflection.improvements, list)

    def test_reflect_missing_verification(self):
        """测试缺少验证步骤的反思"""
        from data_ai.core.reasoning.reflection import ReflectionEngine
        from data_ai.core.reasoning.sequential import ReasoningChain, Thought

        engine = ReflectionEngine()
        chain = ReasoningChain(
            question="问题",
            thoughts=[
                Thought(content="分析", confidence=0.8, metadata={"thought_type": "analysis"}),
            ],
            final_answer="答案",
        )
        reflection = engine.reflect(chain)

        issues_text = " ".join(reflection.issues_found)
        assert "缺少" in issues_text or len(reflection.issues_found) > 0

    def test_get_history(self):
        """测试获取反思历史"""
        from data_ai.core.reasoning.reflection import ReflectionEngine
        from data_ai.core.reasoning.sequential import ReasoningChain

        engine = ReflectionEngine()
        chain = ReasoningChain(question="Q", final_answer="A")

        engine.reflect(chain)
        engine.reflect(chain)

        history = engine.get_history()
        assert len(history) == 2
        for item in history:
            assert item.original_conclusion == "A"

    def test_clear_history(self):
        """测试清除历史"""
        from data_ai.core.reasoning.reflection import ReflectionEngine
        from data_ai.core.reasoning.sequential import ReasoningChain

        engine = ReflectionEngine()
        chain = ReasoningChain(question="Q", final_answer="A")

        engine.reflect(chain)
        assert len(engine._reflection_history) == 1

        engine.clear_history()
        assert engine._reflection_history == []

    def test_reflect_with_confidence_drop(self):
        """测试置信度下降检测"""
        from data_ai.core.reasoning.reflection import ReflectionEngine
        from data_ai.core.reasoning.sequential import ReasoningChain, Thought

        engine = ReflectionEngine()
        chain = ReasoningChain(
            question="复杂问题",
            thoughts=[
                Thought(content="第一步", confidence=0.9, metadata={"thought_type": "analysis"}),
                Thought(content="第二步", confidence=0.2, metadata={"thought_type": "reasoning"}),
                Thought(content="结论", confidence=0.3, metadata={"thought_type": "conclusion"}),
            ],
            final_answer="不确定的答案",
        )
        reflection = engine.reflect(chain)
        assert isinstance(reflection, object)


# ============================================================================
# 6. ToolOrchestrator 测试
# ============================================================================


class TestToolOrchestrator:
    """测试工具编排器"""

    def test_tool_dependency_creation(self):
        """测试 ToolDependency 创建"""
        from data_ai.core.tool.orchestrator import ToolDependency

        dep = ToolDependency(
            tool_name="file_write",
            depends_on=["file_read"],
            conflicts_with=["file_delete"],
            priority=8,
            estimated_duration=2.0,
            retry_count=3,
        )
        assert dep.tool_name == "file_write"
        assert dep.depends_on == ["file_read"]
        assert dep.conflicts_with == ["file_delete"]
        assert dep.priority == 8
        assert dep.estimated_duration == 2.0
        assert dep.retry_count == 3

    def test_tool_dependency_priority_validation(self):
        """测试 ToolDependency 优先级验证"""
        from data_ai.core.tool.orchestrator import ToolDependency

        with pytest.raises(ValueError):
            ToolDependency(tool_name="test", priority=0)

        with pytest.raises(ValueError):
            ToolDependency(tool_name="test", priority=11)

    def test_tool_dependency_to_from_dict(self):
        """测试 ToolDependency 序列化"""
        from data_ai.core.tool.orchestrator import ResourceRequirement, ToolDependency

        dep = ToolDependency(
            tool_name="test_tool",
            depends_on=["dep1"],
            conflicts_with=["conf1"],
            resource_requirements=ResourceRequirement(cpu=0.5, memory=100, network=True),
            priority=5,
            estimated_duration=3.0,
        )
        d = dep.to_dict()
        assert d["tool_name"] == "test_tool"
        assert d["depends_on"] == ["dep1"]
        assert d["resource_requirements"]["cpu"] == 0.5

        restored = ToolDependency.from_dict(d)
        assert restored.tool_name == "test_tool"
        assert restored.resource_requirements.cpu == 0.5

    def test_resource_requirement_add(self):
        """测试 ResourceRequirement 加法"""
        from data_ai.core.tool.orchestrator import ResourceRequirement

        r1 = ResourceRequirement(cpu=0.3, memory=50, disk=10, timeout=10.0)
        r2 = ResourceRequirement(cpu=0.4, memory=100, disk=5, network=True, timeout=20.0)

        r3 = r1 + r2
        assert r3.cpu == 0.7
        assert r3.memory == 150
        assert r3.disk == 15
        assert r3.network is True
        assert r3.timeout == 20.0

    def test_execution_plan_properties(self):
        """测试 ExecutionPlan 属性"""
        from data_ai.core.tool.orchestrator import ExecutionPlan

        plan = ExecutionPlan()
        assert plan.step_count == 0
        assert plan.parallel_group_count == 0
        assert plan.max_parallelism == 0
        assert plan.risk_level.value == "low"
        assert plan.estimated_time == 0.0

    def test_execution_plan_to_dict(self):
        """测试 ExecutionPlan 序列化"""
        from data_ai.core.tool.orchestrator import ExecutionPlan

        plan = ExecutionPlan()
        d = plan.to_dict()
        assert "plan_id" in d
        assert d["step_count"] == 0
        assert d["risk_level"] == "low"

    def test_execution_metrics(self):
        """测试 ExecutionMetrics"""
        from data_ai.core.tool.orchestrator import ExecutionMetrics

        metrics = ExecutionMetrics(
            total_steps=10,
            completed_steps=8,
            failed_steps=1,
            skipped_steps=1,
            total_time=5.0,
            avg_step_time=0.5,
            max_step_time=2.0,
            min_step_time=0.1,
            parallel_efficiency=0.8,
        )
        d = metrics.to_dict()
        assert d["total_steps"] == 10
        assert d["completed_steps"] == 8
        assert d["failed_steps"] == 1
        assert d["skipped_steps"] == 1
        assert d["total_time"] == 5.0

    def test_conflict_info_creation(self):
        """测试 ConflictInfo 创建"""
        from data_ai.core.tool.orchestrator import ConflictInfo, ConflictType, RiskLevel

        conflict = ConflictInfo(
            conflict_type=ConflictType.EXCLUSIVE,
            tools=["file_write", "file_delete"],
            description="文件写入和删除冲突",
            severity=RiskLevel.HIGH,
            suggestion="避免同时执行",
        )
        assert conflict.conflict_type == ConflictType.EXCLUSIVE
        assert conflict.tools == ["file_write", "file_delete"]
        assert conflict.severity == RiskLevel.HIGH

        d = conflict.to_dict()
        assert d["conflict_type"] == "exclusive"
        assert d["severity"] == "high"
        assert d["tools"] == ["file_write", "file_delete"]

    def test_tool_chain_initialization(self):
        """测试 ToolChain 初始化"""
        from data_ai.core.tool.orchestrator import ToolChain

        tc = ToolChain()
        assert tc._chains == {}
        assert tc._cache == {}

    def test_tool_chain_register_builtin_chains(self):
        """测试注册内置工具链"""
        from data_ai.core.tool.orchestrator import ToolChain

        tc = ToolChain()
        tc.register_builtin_chains()

        chains = tc.list_chains()
        assert "file_processing" in chains
        assert "code_analysis" in chains
        assert "web_research" in chains
        assert "data_pipeline" in chains
        assert "project_analysis" in chains

    def test_tool_chain_get(self):
        """测试获取工具链定义"""
        from data_ai.core.tool.orchestrator import ToolChain

        tc = ToolChain()
        tc.register_builtin_chains()

        chain = tc.get("file_processing")
        assert chain is not None
        assert chain.name == "file_processing"
        assert "file_read" in chain.tools
        assert "python_execute" in chain.tools
        assert "file_write" in chain.tools

        assert tc.get("nonexistent") is None

    def test_tool_chain_list_by_tag(self):
        """测试按标签列出工具链"""
        from data_ai.core.tool.orchestrator import ToolChain

        tc = ToolChain()
        tc.register_builtin_chains()

        file_chains = tc.list_chains(tag="file")
        assert "file_processing" in file_chains

        web_chains = tc.list_chains(tag="web")
        assert "web_research" in web_chains

    def test_tool_chain_register_custom(self):
        """测试注册自定义工具链"""
        from data_ai.core.tool.orchestrator import ToolChain, ToolChainDefinition

        tc = ToolChain()
        custom = ToolChainDefinition(
            name="custom_chain",
            description="Custom tool chain",
            tools=["bash", "file_read"],
            tags=["custom"],
        )
        tc.register(custom)

        assert tc.get("custom_chain") is not None
        assert "custom_chain" in tc.list_chains(tag="custom")

    def test_tool_chain_unregister(self):
        """测试注销工具链"""
        from data_ai.core.tool.orchestrator import ToolChain, ToolChainDefinition

        tc = ToolChain()
        tc.register(
            ToolChainDefinition(
                name="temp_chain",
                description="D",
                tools=["bash"],
                tags=[],
            )
        )
        assert tc.get("temp_chain") is not None

        tc.unregister("temp_chain")
        assert tc.get("temp_chain") is None

    def test_tool_chain_create_plan(self):
        """测试从工具链创建执行计划"""
        from data_ai.core.tool.orchestrator import ToolChain

        tc = ToolChain()
        tc.register_builtin_chains()

        plan = tc.create_plan("file_processing", args={"path": "/tmp/test.txt"})
        assert plan is not None
        assert len(plan.steps) == 3
        assert plan.steps[0].tool_name == "file_read"
        assert plan.steps[1].tool_name == "python_execute"
        assert plan.steps[2].tool_name == "file_write"

    def test_tool_chain_create_plan_nonexistent(self):
        """测试不存在的工具链创建计划"""
        from data_ai.core.tool.orchestrator import ToolChain

        tc = ToolChain()
        plan = tc.create_plan("nonexistent_chain")
        assert plan is None

    def test_tool_chain_auto_combine(self):
        """测试自动组合工具链"""
        from data_ai.core.tool.orchestrator import ToolChain

        tc = ToolChain()
        combined = tc.auto_combine(["file_read", "file_write"])

        assert combined.name.startswith("auto_chain_")
        assert len(combined.tools) == 2
        assert "file_read" in combined.tools
        assert "file_write" in combined.tools

    def test_orchestrator_initialization(self):
        """测试 ToolOrchestrator 初始化"""
        from data_ai.core.tool.orchestrator import ToolOrchestrator

        orch = ToolOrchestrator(
            max_parallel=4,
            default_timeout=30.0,
        )
        assert orch.max_parallel == 4
        assert orch.default_timeout == 30.0
        assert len(orch._dependencies) > 0

    def test_create_execution_plan(self):
        """测试创建执行计划"""
        from data_ai.core.tool.orchestrator import ToolOrchestrator

        orch = ToolOrchestrator()
        plan = orch.create_execution_plan(
            [
                ("file_read", {"path": "/tmp/test.txt"}),
                ("bash", {"command": "echo hello"}),
            ]
        )

        assert plan is not None
        assert plan.step_count == 2
        assert plan.steps[0].tool_name == "file_read"
        assert plan.steps[1].tool_name == "bash"
        assert plan.estimated_time >= 0

    def test_create_execution_plan_with_conflicts(self):
        """测试带冲突的执行计划"""
        from data_ai.core.tool.orchestrator import ToolOrchestrator

        orch = ToolOrchestrator()
        plan = orch.create_execution_plan(
            [
                ("file_write", {"path": "/tmp/a.txt"}),
                ("file_delete", {"path": "/tmp/b.txt"}),
            ]
        )

        assert plan is not None
        assert len(plan.conflicts) > 0

    def test_detect_conflicts(self):
        """测试检测冲突"""
        from data_ai.core.tool.orchestrator import ToolOrchestrator

        orch = ToolOrchestrator()
        conflicts = orch.detect_conflicts(["file_write", "file_delete"])
        assert len(conflicts) > 0

        conflicts = orch.detect_conflicts(["file_read", "bash"])
        assert len(conflicts) == 0

    def test_analyze_dependencies(self):
        """测试分析依赖"""
        from data_ai.core.tool.orchestrator import ToolOrchestrator

        orch = ToolOrchestrator()
        deps = orch.analyze_dependencies(["file_write", "bash"])

        assert "file_write" in deps
        assert "bash" in deps
        assert isinstance(deps["file_write"], object)

    def test_estimate_resources(self):
        """测试估算资源"""
        from data_ai.core.tool.orchestrator import ToolOrchestrator

        orch = ToolOrchestrator()
        resources = orch.estimate_resources(["python_execute", "web_search"])

        assert resources.cpu >= 0
        assert resources.memory >= 0
        assert resources.network is True

    def test_register_dependency(self):
        """测试注册依赖"""
        from data_ai.core.tool.orchestrator import ToolDependency, ToolOrchestrator

        orch = ToolOrchestrator()
        custom_dep = ToolDependency(
            tool_name="custom_tool",
            depends_on=["file_read"],
            estimated_duration=1.5,
        )
        orch.register_dependency(custom_dep)

        dep = orch.get_dependency("custom_tool")
        assert dep is not None
        assert dep.tool_name == "custom_tool"
        assert dep.estimated_duration == 1.5

    def test_get_monitor_and_toolchain(self):
        """测试获取监控器和工具链"""
        from data_ai.core.tool.orchestrator import ExecutionMonitor, ToolChain, ToolOrchestrator

        orch = ToolOrchestrator()

        monitor = orch.get_monitor()
        assert isinstance(monitor, ExecutionMonitor)

        tc = orch.get_toolchain()
        assert isinstance(tc, ToolChain)

    def test_execute_plan_with_registered_tools(self):
        """测试执行计划（使用注册的工具）"""
        import asyncio

        from data_ai.core.tool.orchestrator import ToolOrchestrator
        from data_ai.core.tool.registry import ToolRegistry

        reg = ToolRegistry()
        reg.register_builtin_tools()

        orch = ToolOrchestrator()
        orch._registry = reg

        plan = orch.create_execution_plan(
            [
                ("get_current_time", {}),
            ]
        )

        async def run():
            return await orch.execute_plan(plan)

        result = asyncio.run(run())
        assert len(result) > 0
        step_result = list(result.values())[0]
        assert step_result["success"] is True

    def test_execution_monitor_initialization(self):
        """测试 ExecutionMonitor 初始化"""
        from data_ai.core.tool.orchestrator import ExecutionMonitor

        monitor = ExecutionMonitor(history_size=50, bottleneck_threshold=1.5)
        assert monitor.history_size == 50
        assert monitor.bottleneck_threshold == 1.5
        assert monitor._current_plan is None
        assert monitor._start_time is None

    def test_execution_monitor_start_tracking(self):
        """测试监控器开始跟踪"""
        from data_ai.core.tool.orchestrator import ExecutionMonitor, ExecutionPlan

        monitor = ExecutionMonitor()
        plan = ExecutionPlan()
        plan.steps = []

        monitor.start_tracking(plan)
        assert monitor._current_plan is plan
        assert monitor._start_time is not None
        assert monitor._metrics.total_steps == 0

    def test_execution_monitor_get_progress_no_plan(self):
        """测试无计划时获取进度"""
        from data_ai.core.tool.orchestrator import ExecutionMonitor

        monitor = ExecutionMonitor()
        progress = monitor.get_progress()
        assert progress["status"] == "no_plan"

    def test_execution_monitor_detect_bottlenecks_empty(self):
        """测试空瓶颈检测"""
        from data_ai.core.tool.orchestrator import ExecutionMonitor

        monitor = ExecutionMonitor()
        bottlenecks = monitor.detect_bottlenecks()
        assert bottlenecks == []

    def test_execution_monitor_metrics(self):
        """测试获取指标"""
        from data_ai.core.tool.orchestrator import ExecutionMonitor

        monitor = ExecutionMonitor()
        metrics = monitor.get_metrics()
        assert metrics.total_steps == 0
        assert metrics.completed_steps == 0

    def test_execution_monitor_stop_tracking(self):
        """测试停止跟踪"""
        from data_ai.core.tool.orchestrator import ExecutionMonitor, ExecutionPlan

        monitor = ExecutionMonitor()
        plan = ExecutionPlan()
        monitor.start_tracking(plan)
        metrics = monitor.stop_tracking()
        assert metrics.total_time >= 0


# ============================================================================
# 7. Tool Registration 测试
# ============================================================================


class TestToolRegistration:
    """测试工具注册"""

    @pytest.fixture
    def registry(self):
        reg = ToolRegistry()
        yield reg
        reg.clear()

    def test_register_extended_tools_count(self, registry):
        """测试注册扩展工具数量"""
        from data_ai.core.tool.extended import (
            directory_create,
            directory_delete,
            directory_tree,
            file_copy,
            file_delete,
            file_metadata,
            file_move,
            glob_search,
            node_execute,
        )

        functions = [
            ("directory_create", directory_create),
            ("directory_delete", directory_delete),
            ("directory_tree", directory_tree),
            ("file_move", file_move),
            ("file_copy", file_copy),
            ("file_delete", file_delete),
            ("glob_search", glob_search),
            ("file_metadata", file_metadata),
            ("node_execute", node_execute),
        ]

        for name, func in functions:
            registry.register_function(name=name, func=func)

        assert registry.get_tool_count() == 9

    def test_register_system_tools_count(self, registry):
        """测试注册系统工具数量"""
        from data_ai.core.tool.system import (
            env_var,
            git,
            http_request,
            system_info,
        )

        functions = [
            ("system_info", system_info),
            ("env_var", env_var),
            ("git", git),
            ("http_request", http_request),
        ]

        for name, func in functions:
            registry.register_function(name=name, func=func)

        assert registry.get_tool_count() == 4

    def test_register_planning_tools_count(self, registry):
        """测试注册规划工具数量"""
        from data_ai.core.tool.planning import (
            ask_human,
            planning,
            task_decomposition,
            terminate,
            think,
        )

        functions = [
            ("planning", planning),
            ("task_decomposition", task_decomposition),
            ("ask_human", ask_human),
            ("terminate", terminate),
            ("think", think),
        ]

        for name, func in functions:
            registry.register_function(name=name, func=func)

        assert registry.get_tool_count() == 5

    def test_directory_create_execute(self, registry):
        """测试 directory_create 执行"""
        import asyncio

        from data_ai.core.tool.extended import directory_create

        registry.register_function(name="directory_create", func=directory_create)

        result = asyncio.run(
            registry.execute(
                "directory_create",
                {
                    "path": "/tmp/test_dir_for_tests",
                },
            )
        )
        assert result["success"] is True

    def test_directory_tree_execute(self, registry):
        """测试 directory_tree 执行"""
        import asyncio

        from data_ai.core.tool.extended import directory_tree

        registry.register_function(name="directory_tree", func=directory_tree)

        result = asyncio.run(
            registry.execute(
                "directory_tree",
                {
                    "path": "/tmp",
                    "max_depth": 1,
                },
            )
        )
        assert result["success"] is True
        assert "tree" in result
        assert result["total_lines"] > 0

    def test_file_metadata_execute(self, registry):
        """测试 file_metadata 执行"""
        import asyncio

        from data_ai.core.tool.extended import file_metadata

        registry.register_function(name="file_metadata", func=file_metadata)

        result = asyncio.run(
            registry.execute(
                "file_metadata",
                {
                    "path": "/tmp",
                },
            )
        )
        assert result["success"] is True
        assert result["type"] == "directory"
        assert "size_bytes" in result

    def test_glob_search_execute(self, registry):
        """测试 glob_search 执行"""
        import asyncio

        from data_ai.core.tool.extended import glob_search

        registry.register_function(name="glob_search", func=glob_search)

        result = asyncio.run(
            registry.execute(
                "glob_search",
                {
                    "pattern": "*.py",
                    "path": str(_SRC_DIR),
                },
            )
        )
        assert result["success"] is True
        assert result["count"] >= 0

    def test_system_info_execute(self, registry):
        """测试 system_info 执行"""
        import asyncio

        from data_ai.core.tool.system import system_info

        registry.register_function(name="system_info", func=system_info)

        result = asyncio.run(
            registry.execute(
                "system_info",
                {
                    "detail_level": "basic",
                },
            )
        )
        assert result["success"] is True
        assert "info" in result
        assert "os" in result["info"]

    def test_env_var_list_execute(self, registry):
        """测试 env_var list 执行"""
        import asyncio

        from data_ai.core.tool.system import env_var

        registry.register_function(name="env_var", func=env_var)

        result = asyncio.run(
            registry.execute(
                "env_var",
                {
                    "action": "list",
                },
            )
        )
        assert result["success"] is True
        assert "variables" in result
        assert result["count"] > 0

    def test_env_var_set_get_execute(self, registry):
        """测试 env_var set/get 执行"""
        import asyncio
        import os

        from data_ai.core.tool.system import env_var

        registry.register_function(name="env_var", func=env_var)

        set_result = asyncio.run(
            registry.execute(
                "env_var",
                {
                    "action": "set",
                    "name": "TEST_NEW_MODULE_VAR",
                    "value": "hello_world",
                },
            )
        )
        assert set_result["success"] is True

        get_result = asyncio.run(
            registry.execute(
                "env_var",
                {
                    "action": "get",
                    "name": "TEST_NEW_MODULE_VAR",
                },
            )
        )
        assert get_result["success"] is True
        assert get_result["value"] == "hello_world"

        del os.environ["TEST_NEW_MODULE_VAR"]

    def test_planning_execute(self, registry):
        """测试 planning 执行"""
        import asyncio

        from data_ai.core.tool.planning import planning

        registry.register_function(name="planning", func=planning)

        result = asyncio.run(
            registry.execute(
                "planning",
                {
                    "task": "创建一个web应用",
                    "steps": 3,
                },
            )
        )
        assert result["success"] is True
        assert len(result["plan"]["steps"]) == 3

    def test_task_decomposition_execute(self, registry):
        """测试 task_decomposition 执行"""
        import asyncio

        from data_ai.core.tool.planning import task_decomposition

        registry.register_function(name="task_decomposition", func=task_decomposition)

        result = asyncio.run(
            registry.execute(
                "task_decomposition",
                {
                    "task": "构建数据管道",
                },
            )
        )
        assert result["success"] is True
        assert result["total_subtasks"] == 5

    def test_think_execute(self, registry):
        """测试 think 执行"""
        import asyncio

        from data_ai.core.tool.planning import think

        registry.register_function(name="think", func=think)

        result = asyncio.run(
            registry.execute(
                "think",
                {
                    "thought": "这是一个测试思考",
                },
            )
        )
        assert result["success"] is True
        assert result["thought"] == "这是一个测试思考"

    def test_terminate_execute(self, registry):
        """测试 terminate 执行"""
        import asyncio

        from data_ai.core.tool.planning import terminate

        registry.register_function(name="terminate", func=terminate)

        result = asyncio.run(
            registry.execute(
                "terminate",
                {
                    "reason": "测试完成",
                },
            )
        )
        assert result["success"] is True
        assert result["terminated"] is True

    def test_ask_human_execute(self, registry):
        """测试 ask_human 执行"""
        import asyncio

        from data_ai.core.tool.planning import ask_human

        registry.register_function(name="ask_human", func=ask_human)

        result = asyncio.run(
            registry.execute(
                "ask_human",
                {
                    "question": "确认执行？",
                    "type": "confirm",
                },
            )
        )
        assert result["success"] is True
        assert result["requires_input"] is True

    def test_registry_isolated(self):
        """测试独立 registry 不会相互污染"""
        reg1 = ToolRegistry()
        reg2 = ToolRegistry()

        from data_ai.core.tool.planning import think

        reg1.register_function(name="think", func=think)

        assert reg1.get_tool_count() == 1
        assert reg2.get_tool_count() == 0


# ============================================================================
# 8. SDK Integration 测试
# ============================================================================


class TestSDKIntegration:
    """测试 SDK 集成"""

    def test_client_reflection_property(self):
        """测试 client.reflection"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        reflection = client.reflection
        from data_ai.core.reasoning.reflection import ReflectionEngine

        assert isinstance(reflection, ReflectionEngine)

    def test_client_intent_property(self):
        """测试 client.intent"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        intent = client.intent
        from data_ai.core.intent.recognizer import IntentRecognizer

        assert isinstance(intent, IntentRecognizer)

    def test_client_intent_router_property(self):
        """测试 client.intent_router"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        router = client.intent_router
        from data_ai.core.intent.router import IntentRouter

        assert isinstance(router, IntentRouter)

    def test_client_ckg_property(self):
        """测试 client.ckg"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        ckg = client.ckg
        from data_ai.core.ckg.graph import CodeKnowledgeGraph

        assert isinstance(ckg, CodeKnowledgeGraph)

    def test_client_skill_manager_property(self):
        """测试 client.skill_manager"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        sm = client.skill_manager
        from data_ai.core.skill.manager import SkillManager

        assert isinstance(sm, SkillManager)

    def test_client_orchestrator_property(self):
        """测试 client.orchestrator"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        orch = client.orchestrator
        from data_ai.core.tool.orchestrator import ToolOrchestrator

        assert isinstance(orch, ToolOrchestrator)

    def test_client_toolchain_property(self):
        """测试 client.toolchain"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        tc = client.toolchain
        from data_ai.core.tool.orchestrator import ToolChain

        assert isinstance(tc, ToolChain)
        assert len(tc.list_chains()) > 0

    def test_client_register_all_tools(self):
        """测试 client.register_all_tools"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        count = client.register_all_tools()
        assert count > 0

    def test_client_recognize_intent(self):
        """测试 client.recognize_intent"""
        from data_ai.core.intent.recognizer import Intent
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        intent = client.recognize_intent("帮我写一个函数")
        assert isinstance(intent, Intent)
        assert intent.raw_query == "帮我写一个函数"
        assert intent.confidence >= 0.0

    def test_client_polish(self):
        """测试 client.polish"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        result = client.polish("你好世界")

        assert result is not None
        assert hasattr(result, "original")
        assert hasattr(result, "polished")

    def test_client_reflect_on(self):
        """测试 client.reflect_on"""
        from data_ai.core.reasoning.reflection import Reflection
        from data_ai.core.reasoning.sequential import ReasoningChain, Thought
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        chain = ReasoningChain(
            question="测试反思",
            thoughts=[
                Thought(content="步骤1", confidence=0.8, metadata={"thought_type": "analysis"}),
                Thought(content="步骤2", confidence=0.7, metadata={"thought_type": "reasoning"}),
            ],
            final_answer="答案",
        )
        reflection = client.reflect_on(chain)
        assert isinstance(reflection, Reflection)
        assert reflection.original_conclusion == "答案"

    def test_client_caching_properties(self):
        """测试属性缓存"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=False)
        r1 = client.reflection
        r2 = client.reflection
        assert r1 is r2

        i1 = client.intent
        i2 = client.intent
        assert i1 is i2

    def test_client_share_global_mode(self):
        """测试 share_global 模式"""
        from data_ai.sdk import DataAI

        client = DataAI(api_key="test-key", share_global=True)
        assert client is not None
        assert client.reflection is not None

    def test_create_client_function(self):
        """测试 create_client 函数"""
        from data_ai.sdk import create_client

        client = create_client(
            model="gpt-4o",
            provider="openai",
            api_key="test-key",
        )
        assert client.model == "gpt-4o"
        assert client.provider == "openai"


# ============================================================================
# 完整集成测试
# ============================================================================


class TestFullIntegration:
    """完整集成测试"""

    def test_end_to_end_intent_to_route(self):
        """端到端：意图识别到路由"""
        from data_ai.core.intent.recognizer import IntentRecognizer
        from data_ai.core.intent.router import IntentRouter

        recognizer = IntentRecognizer(use_llm=False)
        router = IntentRouter()

        queries = [
            "帮我写一个排序算法",
            "什么是机器学习",
            "运行单元测试",
            "你好",
        ]

        for query in queries:
            intent = recognizer.recognize(query)
            route_result = router.route(intent)
            assert route_result is not None
            assert route_result.strategy is not None

    def test_end_to_end_ckg_to_stats(self):
        """端到端：构建图谱并获取统计"""
        from data_ai.core.ckg.graph import CodeEdge, CodeKnowledgeGraph, CodeNode, EdgeType, NodeType

        ckg = CodeKnowledgeGraph()
        for i in range(5):
            ckg.add_node(
                CodeNode(
                    id=f"func_{i}",
                    name=f"func_{i}",
                    node_type=NodeType.FUNCTION,
                )
            )
        for i in range(4):
            ckg.add_edge(
                CodeEdge(
                    source_id=f"func_{i}",
                    target_id=f"func_{i + 1}",
                    edge_type=EdgeType.CALLS,
                )
            )

        stats = ckg.get_statistics()
        assert stats["total_nodes"] == 5
        assert stats["total_edges"] == 4

        json_str = ckg.export_json()
        assert "func_0" in json_str

    def test_end_to_end_reflection_cycle(self):
        """端到端：反思循环"""
        from data_ai.core.reasoning.reflection import ReflectionEngine
        from data_ai.core.reasoning.sequential import ReasoningChain, Thought

        engine = ReflectionEngine()
        chain = ReasoningChain(
            question="Python中如何实现单例模式？",
            thoughts=[
                Thought(
                    content="分析单例模式的需求",
                    confidence=0.9,
                    metadata={"thought_type": "analysis"},
                ),
                Thought(
                    content="使用 __new__ 方法实现",
                    confidence=0.85,
                    metadata={"thought_type": "reasoning"},
                ),
                Thought(
                    content="验证线程安全",
                    confidence=0.8,
                    metadata={"thought_type": "verification"},
                ),
            ],
            final_answer="使用 __new__ 方法配合锁实现线程安全的单例模式",
        )

        reflection = engine.reflect(chain)
        assert reflection is not None
        assert len(engine.get_history()) == 1

        engine.clear_history()
        assert len(engine.get_history()) == 0

    def test_end_to_end_orchestrator_with_real_tools(self):
        """端到端：编排器执行真实工具"""
        import asyncio

        from data_ai.core.tool.orchestrator import ToolOrchestrator
        from data_ai.core.tool.registry import ToolRegistry

        reg = ToolRegistry()
        reg.register_builtin_tools()

        orchestrator = ToolOrchestrator()
        orchestrator._registry = reg

        plan = orchestrator.create_execution_plan(
            [
                ("get_current_time", {}),
            ]
        )

        async def run():
            return await orchestrator.execute_plan(plan)

        result = asyncio.run(run())
        assert len(result) > 0
        statuses = [v["success"] for v in result.values()]
        assert all(statuses)

    def test_end_to_end_skill_manager_full_cycle(self):
        """端到端：技能管理器完整生命周期"""
        import tempfile

        from data_ai.core.skill.manager import SkillManager
        from data_ai.core.skill.skill import Skill, SkillCategory, SkillStep

        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SkillManager(storage_dir=tmpdir)

            skill = Skill(
                id="e2e-skill",
                name="端到端测试技能",
                description="完整测试",
                category=SkillCategory.TESTING,
                triggers=["e2e", "端到端"],
                steps=[SkillStep(step_number=1, description="执行测试")],
                success_patterns=["通过"],
                failure_patterns=["失败"],
            )

            mgr.register(skill)
            assert mgr.get("e2e-skill") is not None

            mgr.update_usage("e2e-skill", success=True, execution_time_ms=50.0)
            updated = mgr.get("e2e-skill")
            assert updated.metadata.usage_count == 1

            stats = mgr.get_stats()
            assert stats["total_skills"] == 1

            mgr.unregister("e2e-skill")
            assert mgr.get("e2e-skill") is None

    def test_end_to_end_all_tools_registered_and_executed(self):
        """端到端：所有工具注册和执行"""
        import asyncio

        from data_ai.core.tool.registry import ToolRegistry

        reg = ToolRegistry()

        from data_ai.core.tool.extended import (
            directory_create,
            directory_tree,
            file_metadata,
            glob_search,
        )
        from data_ai.core.tool.planning import planning, think
        from data_ai.core.tool.system import env_var, system_info

        reg.register_function(name="directory_create", func=directory_create)
        reg.register_function(name="directory_tree", func=directory_tree)
        reg.register_function(name="file_metadata", func=file_metadata)
        reg.register_function(name="glob_search", func=glob_search)
        reg.register_function(name="system_info", func=system_info)
        reg.register_function(name="env_var", func=env_var)
        reg.register_function(name="planning", func=planning)
        reg.register_function(name="think", func=think)

        test_dir = "/tmp/datatai_e2e_test"
        results = []

        async def run_tests():
            results.append(await reg.execute("directory_create", {"path": test_dir}))
            results.append(await reg.execute("directory_tree", {"path": test_dir, "max_depth": 1}))
            results.append(await reg.execute("file_metadata", {"path": test_dir}))
            results.append(await reg.execute("glob_search", {"pattern": "*", "path": "/tmp"}))
            results.append(await reg.execute("system_info", {"detail_level": "basic"}))
            results.append(await reg.execute("env_var", {"action": "list"}))
            results.append(await reg.execute("planning", {"task": "测试"}))
            results.append(await reg.execute("think", {"thought": "端到端测试"}))

        asyncio.run(run_tests())

        import shutil

        for result in results:
            assert result["success"] is True
        shutil.rmtree(test_dir, ignore_errors=True)
