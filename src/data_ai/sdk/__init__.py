"""
DATA-AI SDK

面向开发者的便捷 API，支持同步和异步调用。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Dict, List, Optional

from ..core.agent.base import AgentConfig, AgentState, AgentStatus, BaseAgent
from ..core.ckg.graph import CodeEdge, CodeKnowledgeGraph, CodeNode, EdgeType, NodeType
from ..core.intent.recognizer import Intent, IntentContext, IntentRecognizer, IntentType
from ..core.intent.router import IntentRouter, RouteResult, RouteStrategy
from ..core.llm.manager import (
    ChatMessage,
    ChatResponse,
    LLMManager,
    ModelConfig,
    ModelProvider,
    get_llm_manager,
    register_model,
)
from ..core.memory.manager import MemoryEntry, MemoryManager, MemoryStore, MemoryType, get_memory_manager
from ..core.polish.polisher import PolisherRegistry, TextPolisher, polish_text
from ..core.rag.pipeline import (
    ChromaVectorStore,
    Document,
    HuggingFaceEmbedder,
    InMemoryVectorStore,
    OpenAIEmbedder,
    RAGPipeline,
    RetrievalResult,
    TextSplitter,
)
from ..core.reasoning.reflection import Reflection, ReflectionEngine
from ..core.reasoning.sequential import ReasoningChain, SequentialThinking, Thought
from ..core.skill.manager import SkillManager
from ..core.tool.orchestrator import ToolChain, ToolOrchestrator, get_orchestrator, get_toolchain
from ..core.tool.registry import ToolRegistry, get_tool_registry
from ..utils.exceptions import (
    AgentException,
    AgentExecutionError,
    AgentMaxIterationsExceededError,
    AgentTimeoutError,
    ErrorCode,
    LLMConfigError,
    LLMConnectionError,
    LLMException,
    LLMRateLimitError,
    MemoryConfigError,
    MemoryException,
    RAGConfigError,
    RAGException,
    ToolExecutionError,
)
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DataAI:
    def __init__(
        self,
        model: str = "gpt-4o",
        provider: str = "openai",
        api_key: str | None = None,
        base_url: str | None = None,
        system_prompt: str | None = None,
        max_iterations: int = 10,
        timeout: float = 300.0,
        temperature: float = 0.7,
        stream: bool = True,
        share_global: bool = False,
        rag_config: dict[str, Any] | None = None,
        **kwargs,
    ):
        if share_global:
            self._llm_manager = get_llm_manager()
            self._tool_registry = get_tool_registry()
            self._memory_manager = get_memory_manager()
        else:
            from ..core.llm.manager import LLMManager as _LLMManager
            from ..core.memory.manager import MemoryManager as _MemoryManager
            from ..core.tool.registry import ToolRegistry as _ToolRegistry

            self._llm_manager = _LLMManager()
            self._tool_registry = _ToolRegistry()
            self._memory_manager = _MemoryManager()

        provider_enum = ModelProvider(provider)
        config = ModelConfig(
            provider=provider_enum,
            model_name=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            timeout=timeout,
            **kwargs,
        )
        self._llm_manager.register_model("default", config, set_default=True)

        self.model = model
        self.provider = provider
        self._system_prompt = system_prompt
        self._max_iterations = max_iterations
        self._timeout = timeout
        self._temperature = temperature
        self._stream = stream
        self._rag_config = rag_config or {}

        self._rag: RAGPipeline | None = None
        self._reasoning: SequentialThinking | None = None
        self._reflection: ReflectionEngine | None = None
        self._intent_recognizer: IntentRecognizer | None = None
        self._intent_router: IntentRouter | None = None
        self._ckg: CodeKnowledgeGraph | None = None
        self._skill_manager: SkillManager | None = None
        self._orchestrator: ToolOrchestrator | None = None
        self._toolchain: ToolChain | None = None

    def get_system_prompt(self) -> str:
        return self._system_prompt or "You are a helpful AI assistant. Use tools when needed."

    @property
    def rag(self) -> RAGPipeline:
        if self._rag is None:
            self._rag = RAGPipeline(**self._rag_config)
        return self._rag

    @property
    def reasoning(self) -> SequentialThinking:
        if self._reasoning is None:
            self._reasoning = SequentialThinking()
        return self._reasoning

    @property
    def memory(self) -> MemoryManager:
        return self._memory_manager

    @property
    def tools(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def llm(self) -> LLMManager:
        return self._llm_manager

    @property
    def reflection(self) -> ReflectionEngine:
        if self._reflection is None:
            self._reflection = ReflectionEngine()
        return self._reflection

    @property
    def intent(self) -> IntentRecognizer:
        if self._intent_recognizer is None:
            self._intent_recognizer = IntentRecognizer()
        return self._intent_recognizer

    @property
    def intent_router(self) -> IntentRouter:
        if self._intent_router is None:
            self._intent_router = IntentRouter()
        return self._intent_router

    @property
    def ckg(self) -> CodeKnowledgeGraph:
        if self._ckg is None:
            self._ckg = CodeKnowledgeGraph()
        return self._ckg

    @property
    def skill_manager(self) -> SkillManager:
        if self._skill_manager is None:
            self._skill_manager = SkillManager()
        return self._skill_manager

    @property
    def orchestrator(self) -> ToolOrchestrator:
        if self._orchestrator is None:
            self._orchestrator = ToolOrchestrator()
        return self._orchestrator

    @property
    def toolchain(self) -> ToolChain:
        if self._toolchain is None:
            self._toolchain = ToolChain()
            self._toolchain.register_builtin_chains()
        return self._toolchain

    async def chat(
        self,
        message: str,
        messages: list[dict[str, str]] | None = None,
        tools: list[dict] | None = None,
        model: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        chat_messages = []

        chat_messages.append(ChatMessage(role="system", content=self.get_system_prompt()))

        if messages:
            for msg in messages:
                chat_messages.append(
                    ChatMessage(
                        role=msg.get("role", "user"),
                        content=msg.get("content", ""),
                    )
                )

        chat_messages.append(ChatMessage(role="user", content=message))

        response = await self._llm_manager.chat(
            messages=chat_messages,
            model=model or "default",
            tools=tools,
            temperature=kwargs.get("temperature", self._temperature),
        )

        return {
            "content": response.content,
            "model": response.model,
            "usage": response.usage,
            "finish_reason": response.finish_reason,
            "tool_calls": response.tool_calls,
        }

    async def chat_stream(
        self,
        message: str,
        messages: list[dict[str, str]] | None = None,
        tools: list[dict] | None = None,
        model: str | None = None,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        chat_messages = [ChatMessage(role="system", content=self.get_system_prompt())]
        if messages:
            for msg in messages:
                chat_messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
        chat_messages.append(ChatMessage(role="user", content=message))

        async for chunk in self._llm_manager.chat_stream(
            messages=chat_messages,
            model=model or "default",
            tools=tools,
            **kwargs,
        ):
            yield {
                "content": chunk.content,
                "model": chunk.model,
                "finish_reason": chunk.finish_reason,
                "tool_calls": chunk.tool_calls,
            }

    async def run(
        self,
        user_input: str,
        **kwargs,
    ) -> dict[str, Any]:
        agent = _DataAIAgent(self)
        return await agent.run(user_input)

    async def run_stream(
        self,
        user_input: str,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        agent = _DataAIAgent(self)
        async for chunk in agent.run_stream(user_input):
            yield chunk

    def add_documents(self, texts: list[str], metadata: dict | None = None) -> int:
        return self.rag.add_texts(texts, metadata)

    def search_documents(self, query: str, top_k: int = 5) -> str:
        return self.rag.query(query, top_k)

    def remember(self, content: str, importance: float = 0.5) -> None:
        self._memory_manager.remember(content, importance)

    def recall(self, query: str, limit: int = 10) -> str:
        return self._memory_manager.recall_relevant(query, limit)

    async def think(self, question: str, context: str | None = None) -> ReasoningChain:
        async def llm_fn(prompt: str) -> str:
            msgs = [ChatMessage(role="user", content=prompt)]
            response = await self._llm_manager.chat(msgs)
            return response.content

        return await self.reasoning.think(question, llm_fn=llm_fn, context=context)

    async def cleanup(self) -> None:
        if self._rag:
            self._rag.clear()
        if self._reflection:
            self._reflection.clear_history()
        if self._intent_recognizer:
            self._intent_recognizer.clear_history()
        if self._ckg:
            self._ckg.clear()
        if self._skill_manager:
            self._skill_manager.clear()

    def register_all_tools(self) -> int:
        count = 0
        self._tool_registry.register_builtin_tools()
        count += 5
        try:
            from ..core.tool.extended import register_extended_tools

            register_extended_tools()
            count += 9
        except Exception:
            pass
        try:
            from ..core.tool.system import register_system_tools

            register_system_tools()
            count += 4
        except Exception:
            pass
        try:
            from ..core.tool.planning import register_planning_tools

            register_planning_tools()
            count += 5
        except Exception:
            pass
        return count

    def recognize_intent(self, text: str) -> Intent:
        return self.intent.recognize(text)

    def build_code_graph(self, path: str) -> CodeKnowledgeGraph:
        self._ckg = CodeKnowledgeGraph()
        self._ckg.build_from_path(path)
        return self._ckg

    def polish(self, text: str, style: str = "general") -> str:
        return polish_text(text, style=style)

    def reflect_on(self, chain: ReasoningChain) -> Reflection:
        return self.reflection.reflect(chain)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


class _DataAIAgent(BaseAgent):
    def __init__(self, client: DataAI):
        super().__init__(
            config=AgentConfig(
                model_name="default",
                system_prompt=client.get_system_prompt(),
                max_iterations=client._max_iterations,
                timeout=client._timeout,
                temperature=client._temperature,
                stream=client._stream,
            ),
            llm_manager=client._llm_manager,
            tool_registry=client._tool_registry,
        )
        self._client = client

    def get_system_prompt(self) -> str:
        return self._client.get_system_prompt()


def create_client(
    model: str = "gpt-4o",
    provider: str = "openai",
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs,
) -> DataAI:
    return DataAI(
        model=model,
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        **kwargs,
    )
