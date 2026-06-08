"""
意图路由器

根据识别的意图，选择最优的处理策略。
提供真实的路由分发：直接调用 LLM / 工具 / Agent。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...utils.logging import get_logger
from .recognizer import Intent, IntentContext, IntentType

logger = get_logger(__name__)


class RouteStrategy(Enum):
    """路由策略"""

    DIRECT = "direct"  # 直接处理（直接 LLM 调用）
    AGENT = "agent"  # 使用 Agent
    TOOL_CHAIN = "tool_chain"  # 工具链
    MULTI_AGENT = "multi_agent"  # 多 Agent 协作
    CLARIFY = "clarify"  # 需要澄清
    REJECT = "reject"  # 拒绝处理


class RouteTarget(Enum):
    """路由目标类型"""

    LLM = "llm"
    AGENT = "agent"
    TOOL = "tool"
    TEAM = "team"
    CHAT = "chat"
    NONE = "none"


@dataclass
class RouteResult:
    """路由结果

    Attributes:
        strategy: 路由策略
        target:   路由目标（llm / agent / tool / team / chat / none）
        handler:  处理器名称（具体哪个 LLM/Agent/Tool）
        tools:    工具链
        agent_type: Agent 类型
        parameters: 路由参数
        confidence: 置信度
        alternatives: 备选路由
        explanation: 决策说明
        metadata: 附加元数据
    """

    strategy: RouteStrategy
    target: RouteTarget = RouteTarget.NONE
    handler: str | None = None
    tools: list[str] = field(default_factory=list)
    agent_type: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    alternatives: list[RouteResult] = field(default_factory=list)
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class IntentRouter:
    """
    意图路由器

    根据意图类型和上下文，选择最优的处理方式：
    1. 简单意图 → 直接工具调用
    2. 中等复杂度 → 单 Agent 处理
    3. 高复杂度 → 多 Agent 协作
    4. 不明确 → 澄清请求

    既支持纯决策（返回 RouteResult），也支持实际分发
    （传入 llm_manager / tool_registry / agent_factory 后调用
    dispatch() 真正执行）。
    """

    def __init__(
        self,
        llm_manager: Any | None = None,
        tool_registry: Any | None = None,
        agent_factory: Callable[[str], Any] | None = None,
    ):
        self._handlers: dict[IntentType, Callable] = {}
        self._tool_mapping = self._build_tool_mapping()
        self._agent_mapping = self._build_agent_mapping()
        self._llm_manager = llm_manager
        self._tool_registry = tool_registry
        self._agent_factory = agent_factory

    # ------------------------------------------------------------------
    # 配置
    # ------------------------------------------------------------------

    def set_llm_manager(self, manager: Any) -> None:
        self._llm_manager = manager

    def set_tool_registry(self, registry: Any) -> None:
        self._tool_registry = registry

    def set_agent_factory(self, factory: Callable[[str], Any]) -> None:
        """Agent 工厂函数：给定 agent_type 返回 Agent 实例"""
        self._agent_factory = factory

    def _build_tool_mapping(self) -> dict[IntentType, list[str]]:
        """构建意图到工具的映射"""
        return {
            IntentType.FILE_READ: ["file_read", "read_file", "view"],
            IntentType.FILE_WRITE: ["file_write", "write_file"],
            IntentType.FILE_SEARCH: ["glob_search", "grep", "find"],
            IntentType.FILE_MODIFY: ["str_replace_editor", "file_modify"],
            IntentType.WEB_SEARCH: ["web_search", "tavily_search"],
            IntentType.SHELL_COMMAND: ["bash", "python_execute", "execute_command"],
            IntentType.DATA_ANALYSIS: ["python_execute", "excel_read", "excel_analyze"],
            IntentType.DATA_VISUALIZATION: ["python_execute", "excel_chart"],
            IntentType.BROWSER_AUTOMATION: ["browser_navigate", "browser_click", "browser_screenshot"],
            IntentType.CODE_DEBUGGING: ["python_execute", "bash"],
        }

    def _build_agent_mapping(self) -> dict[IntentType, str]:
        """构建意图到 Agent 的映射"""
        return {
            IntentType.CODE_GENERATION: "swe_agent",
            IntentType.CODE_REFACTORING: "swe_agent",
            IntentType.CODE_REVIEW: "swe_agent",
            IntentType.CODE_DEBUGGING: "swe_agent",
            IntentType.COMPLEX_TASK: "data_agent",
            IntentType.PLANNING: "data_agent",
            IntentType.DATA_ANALYSIS: "data_agent",
            IntentType.AUTOMATION: "data_agent",
        }

    def register_handler(self, intent_type: IntentType, handler: Callable) -> None:
        """注册自定义处理器"""
        self._handlers[intent_type] = handler

    # ------------------------------------------------------------------
    # 决策接口
    # ------------------------------------------------------------------

    def route(
        self,
        intent: Intent,
        context: IntentContext | None = None,
    ) -> RouteResult:
        """
        根据意图选择路由策略

        Args:
            intent: 识别出的意图
            context: 上下文

        Returns:
            路由结果
        """
        # 1. 置信度过低，需要澄清
        if intent.confidence < 0.3:
            return RouteResult(
                strategy=RouteStrategy.CLARIFY,
                target=RouteTarget.NONE,
                confidence=intent.confidence,
                explanation=f"意图不明确（置信度: {intent.confidence:.2f}），需要用户澄清",
                metadata={"intent": intent.intent_type.value},
            )

        # 2. UNKNOWN → 需要澄清
        if intent.intent_type == IntentType.UNKNOWN:
            return RouteResult(
                strategy=RouteStrategy.CLARIFY,
                target=RouteTarget.NONE,
                confidence=intent.confidence,
                explanation="未知意图，需要用户澄清",
                metadata={"intent": "unknown"},
            )

        # 3. 根据意图类型选择策略
        strategy = self._select_strategy(intent)

        if strategy == RouteStrategy.DIRECT:
            return self._route_direct(intent)
        elif strategy == RouteStrategy.TOOL_CHAIN:
            return self._route_tool_chain(intent)
        elif strategy == RouteStrategy.AGENT:
            return self._route_agent(intent)
        elif strategy == RouteStrategy.MULTI_AGENT:
            return self._route_multi_agent(intent)
        else:
            return RouteResult(
                strategy=strategy,
                target=RouteTarget.NONE,
                confidence=intent.confidence,
                explanation="默认路由",
            )

    def _select_strategy(self, intent: Intent) -> RouteStrategy:
        """选择路由策略"""
        simple_intents = {
            IntentType.FILE_READ,
            IntentType.FILE_SEARCH,
            IntentType.WEB_SEARCH,
            IntentType.SHELL_COMMAND,
            IntentType.QUESTION_ANSWERING,
            IntentType.CONVERSATION,
        }

        medium_intents = {
            IntentType.CODE_GENERATION,
            IntentType.CODE_EXPLANATION,
            IntentType.CODE_DEBUGGING,
            IntentType.DATA_ANALYSIS,
            IntentType.BROWSER_AUTOMATION,
            IntentType.FILE_WRITE,
            IntentType.FILE_MODIFY,
        }

        complex_intents = {
            IntentType.COMPLEX_TASK,
            IntentType.PLANNING,
            IntentType.AUTOMATION,
            IntentType.CODE_REFACTORING,
        }

        if intent.intent_type in simple_intents:
            return RouteStrategy.DIRECT if not intent.sub_intents else RouteStrategy.TOOL_CHAIN
        elif intent.intent_type in medium_intents:
            return RouteStrategy.AGENT
        elif intent.intent_type in complex_intents:
            return RouteStrategy.MULTI_AGENT
        elif intent.intent_type == IntentType.UNKNOWN:
            return RouteStrategy.CLARIFY
        else:
            return RouteStrategy.AGENT

    # ------------------------------------------------------------------
    # 路由实现
    # ------------------------------------------------------------------

    def _route_direct(self, intent: Intent) -> RouteResult:
        """直接路由"""
        parameters = self._extract_parameters(intent)

        # 对话类问题
        if intent.intent_type in (IntentType.QUESTION_ANSWERING, IntentType.CONVERSATION):
            return RouteResult(
                strategy=RouteStrategy.DIRECT,
                target=RouteTarget.LLM,
                handler="chat",
                tools=[],
                parameters=parameters,
                confidence=intent.confidence,
                explanation="直接调用 LLM 回答问题",
                metadata={"intent": intent.intent_type.value},
            )

        # 命令类：直接执行
        if intent.intent_type == IntentType.SHELL_COMMAND:
            tools = self._tool_mapping.get(intent.intent_type, ["bash", "execute_command"])
            return RouteResult(
                strategy=RouteStrategy.DIRECT,
                target=RouteTarget.TOOL,
                handler=tools[0] if tools else "bash",
                tools=tools,
                parameters=parameters,
                confidence=intent.confidence,
                explanation=f"使用命令执行工具: {tools[0] if tools else 'bash'}",
                metadata={"intent": intent.intent_type.value},
            )

        # 文件读取 / 搜索
        if intent.intent_type in (IntentType.FILE_READ, IntentType.FILE_SEARCH, IntentType.WEB_SEARCH):
            tools = self._tool_mapping.get(intent.intent_type, [])
            return RouteResult(
                strategy=RouteStrategy.DIRECT,
                target=RouteTarget.TOOL,
                handler=tools[0] if tools else "tool",
                tools=tools,
                parameters=parameters,
                confidence=intent.confidence,
                explanation=f"使用工具: {', '.join(tools) if tools else '对话'}",
                metadata={"intent": intent.intent_type.value},
            )

        # 默认 DIRECT（对话）
        return RouteResult(
            strategy=RouteStrategy.DIRECT,
            target=RouteTarget.CHAT,
            handler="general_chat",
            tools=[],
            parameters=parameters,
            confidence=intent.confidence,
            explanation="默认直接对话",
        )

    def _route_tool_chain(self, intent: Intent) -> RouteResult:
        """工具链路由"""
        all_tools: list[str] = []
        all_tools.extend(self._tool_mapping.get(intent.intent_type, []))

        for sub_intent in intent.sub_intents:
            all_tools.extend(self._tool_mapping.get(sub_intent.intent_type, []))

        # 去重保持顺序
        seen = set()
        deduped = []
        for t in all_tools:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
        all_tools = deduped

        return RouteResult(
            strategy=RouteStrategy.TOOL_CHAIN,
            target=RouteTarget.TOOL,
            handler=all_tools[0] if all_tools else None,
            tools=all_tools,
            parameters=self._extract_parameters(intent),
            confidence=intent.confidence,
            explanation=f"使用工具链: {' → '.join(all_tools)}",
            metadata={
                "intent": intent.intent_type.value,
                "sub_intents": [s.intent_type.value for s in intent.sub_intents],
            },
        )

    def _route_agent(self, intent: Intent) -> RouteResult:
        """Agent 路由"""
        agent_type = self._agent_mapping.get(intent.intent_type, "data_agent")
        tools = self._tool_mapping.get(intent.intent_type, [])

        return RouteResult(
            strategy=RouteStrategy.AGENT,
            target=RouteTarget.AGENT,
            agent_type=agent_type,
            tools=tools,
            parameters=self._extract_parameters(intent),
            confidence=intent.confidence,
            explanation=f"使用 {agent_type} 处理",
            metadata={"intent": intent.intent_type.value},
        )

    def _route_multi_agent(self, intent: Intent) -> RouteResult:
        """多 Agent 路由"""
        agent_types = set()
        main_agent = self._agent_mapping.get(intent.intent_type, "data_agent")
        agent_types.add(main_agent)

        for sub_intent in intent.sub_intents:
            sub_agent = self._agent_mapping.get(sub_intent.intent_type)
            if sub_agent:
                agent_types.add(sub_agent)

        all_tools = set(self._tool_mapping.get(intent.intent_type, []))
        for sub_intent in intent.sub_intents:
            all_tools.update(self._tool_mapping.get(sub_intent.intent_type, []))

        return RouteResult(
            strategy=RouteStrategy.MULTI_AGENT,
            target=RouteTarget.TEAM,
            agent_type="team",
            tools=list(all_tools),
            parameters={
                "team_members": list(agent_types),
                "intent_entities": [e.to_dict() if hasattr(e, "to_dict") else e.__dict__ for e in intent.entities],
            },
            confidence=intent.confidence,
            explanation=f"多 Agent 协作: {', '.join(agent_types)}",
            metadata={"intent": intent.intent_type.value, "agent_types": list(agent_types)},
        )

    def _extract_parameters(self, intent: Intent) -> dict[str, Any]:
        """从实体提取参数"""
        parameters: dict[str, Any] = {}
        for entity in intent.entities:
            parameters[entity.name] = entity.value
        parameters["_query"] = intent.raw_query
        parameters["_intent_type"] = intent.intent_type.value
        return parameters

    # ------------------------------------------------------------------
    # 实际分发执行
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        intent: Intent,
        context: IntentContext | None = None,
    ) -> dict[str, Any]:
        """
        根据路由结果实际执行：
        - LLM: 直接调用 chat
        - Tool: 通过 tool_registry 执行
        - Agent: 通过 agent_factory 创建并执行
        - Team: 通过多 Agent 协作执行
        """
        result = self.route(intent, context)
        return await self._execute_route(result, intent)

    async def _execute_route(
        self,
        result: RouteResult,
        intent: Intent,
    ) -> dict[str, Any]:
        """根据 RouteResult 实际执行"""
        query = intent.raw_query or ""
        output: dict[str, Any] = {
            "strategy": result.strategy.value,
            "target": result.target.value,
            "content": "",
            "success": False,
        }

        try:
            if result.strategy == RouteStrategy.CLARIFY:
                output["success"] = True
                output["content"] = "请进一步澄清您的需求。"
                output["needs_clarification"] = True
                return output

            if result.target == RouteTarget.LLM:
                output.update(await self._dispatch_llm(query, result))
            elif result.target == RouteTarget.TOOL:
                output.update(await self._dispatch_tool(query, result))
            elif result.target == RouteTarget.AGENT:
                output.update(await self._dispatch_agent(query, result))
            elif result.target == RouteTarget.TEAM:
                output.update(await self._dispatch_team(query, result))
            elif result.target == RouteTarget.CHAT:
                output.update(await self._dispatch_chat(query, result))
            else:
                output["content"] = "无法确定处理方式"
        except Exception as e:
            output["success"] = False
            output["error"] = str(e)
            logger.error(f"路由分发失败: {e}")

        return output

    async def _dispatch_llm(self, query: str, result: RouteResult) -> dict[str, Any]:
        """调用 LLM"""
        if self._llm_manager is None:
            return {"success": False, "content": "LLM 管理器未配置", "error": "llm_manager_missing"}
        try:
            from ..llm.manager import ChatMessage

            response = await self._llm_manager.chat(
                messages=[
                    ChatMessage(role="system", content="你是一个有帮助的助手。"),
                    ChatMessage(role="user", content=query),
                ]
            )
            return {
                "success": True,
                "content": response.content,
                "model": response.model,
                "usage": response.usage,
            }
        except Exception as e:
            return {"success": False, "content": "", "error": str(e)}

    async def _dispatch_tool(self, query: str, result: RouteResult) -> dict[str, Any]:
        """调用工具"""
        if self._tool_registry is None or not result.tools:
            return {"success": False, "content": "", "error": "tool_registry_missing"}

        # 选择主工具并构造参数
        tool_name = result.handler or result.tools[0]
        arguments: dict[str, Any] = dict(result.parameters or {})
        arguments.pop("_query", None)
        arguments.pop("_intent_type", None)
        # 通用约定：把 query 视作 'command' 或 'query' 参数
        if "command" not in arguments and "query" not in arguments and "input" not in arguments:
            arguments["query"] = query

        try:
            tool_result = await self._tool_registry.execute(tool_name, arguments)
            return {
                "success": True,
                "content": str(tool_result),
                "tool": tool_name,
                "tool_result": tool_result,
            }
        except Exception as e:
            return {"success": False, "content": "", "error": str(e), "tool": tool_name}

    async def _dispatch_agent(self, query: str, result: RouteResult) -> dict[str, Any]:
        """调用 Agent"""
        if self._agent_factory is None:
            # 没有 agent_factory，则 fallback 到 LLM
            return await self._dispatch_llm(query, result)

        try:
            agent = self._agent_factory(result.agent_type or "data_agent")
            agent_result = await agent.run(user_input=query)
            content = agent_result.get("content", "") if isinstance(agent_result, dict) else str(agent_result)
            return {
                "success": True,
                "content": content,
                "agent_type": result.agent_type,
                "agent_result": agent_result,
            }
        except Exception as e:
            return {"success": False, "content": "", "error": str(e)}

    async def _dispatch_team(self, query: str, result: RouteResult) -> dict[str, Any]:
        """调用多 Agent 团队（这里只是简单地将任务分配给多个 Agent 并合并）"""
        if self._agent_factory is None:
            return await self._dispatch_llm(query, result)

        members = result.parameters.get("team_members", [])
        if not members:
            members = ["data_agent"]

        async def _run_one(member: str) -> str:
            try:
                agent = self._agent_factory(member)
                res = await agent.run(user_input=query)
                return res.get("content", "") if isinstance(res, dict) else str(res)
            except Exception as e:
                return f"[{member}] 错误: {e}"

        outputs = await asyncio.gather(*[_run_one(m) for m in members])
        return {
            "success": True,
            "content": "\n\n---\n\n".join(outputs),
            "team_members": members,
        }

    async def _dispatch_chat(self, query: str, result: RouteResult) -> dict[str, Any]:
        """通用对话路由"""
        return await self._dispatch_llm(query, result)

    # ------------------------------------------------------------------
    # 解释
    # ------------------------------------------------------------------

    def get_route_explanation(self, result: RouteResult) -> str:
        """获取路由解释"""
        parts = [f"策略: {result.strategy.value}", f"目标: {result.target.value}"]

        if result.handler:
            parts.append(f"处理器: {result.handler}")
        if result.tools:
            parts.append(f"工具: {', '.join(result.tools)}")
        if result.agent_type:
            parts.append(f"Agent: {result.agent_type}")

        parts.append(f"置信度: {result.confidence:.2f}")

        if result.explanation:
            parts.append(f"说明: {result.explanation}")

        return " | ".join(parts)
