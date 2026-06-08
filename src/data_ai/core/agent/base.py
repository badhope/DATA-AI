"""
DATA-AI 智能体基类

基于 Tool Calling 的现代 Agent 实现，支持：
- 工具调用（OpenAI/Anthropic 原生 tool calling）
- 真正的流式输出（token 级别）
- 上下文窗口管理（自动截断）
- 异步上下文管理器
- 消息历史管理
- 工具执行结果追踪
"""

from __future__ import annotations

import asyncio
import time as _time
import uuid


def _now() -> float:
    return _time.time()


def _msg_to_dict(m: ChatMessage) -> dict[str, Any]:
    """ChatMessage → dict (兼容 OpenAI/Anthropic tool_call_id)"""
    return {
        "role": m.role,
        "content": m.content,
        "tool_calls": m.tool_calls,
        "tool_call_id": getattr(m, "tool_call_id", None),
        "name": getattr(m, "name", None),
    }


def _dict_to_msg(d: dict[str, Any]) -> ChatMessage:
    """dict → ChatMessage (用于 resume 反序列化)"""
    return ChatMessage(
        role=d.get("role") or "user",
        content=d.get("content") or "",
        tool_calls=d.get("tool_calls"),
        tool_call_id=d.get("tool_call_id"),
        name=d.get("name"),
    )


import inspect
import json
from abc import ABC
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...utils.exceptions import (
    AgentExecutionError,
    AgentMaxIterationsExceededError,
    AgentTimeoutError,
    ToolExecutionError,
)
from ...utils.logging import get_logger
from ..llm.manager import (
    ChatMessage,
    ContextWindowManager,
    LLMManager,
    get_llm_manager,
)
from ..tool.registry import ToolRegistry, get_tool_registry

logger = get_logger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    STREAMING = "streaming"
    REFLECTING = "reflecting"  # 新增: 自反思中
    FINISHED = "finished"
    ERROR = "error"


@dataclass
class ReflectionResult:
    """Self-Reflection 输出

    Agent 在 LLM 返回最终答案时(非 tool_call),额外调一次 LLM
    评估"我刚才的答案是否可信",如果发现 issues 就注入回 messages
    让 LLM 重新回答。
    """

    is_confident: bool
    confidence: float  # 0.0 - 1.0
    issues: list[str]  # 发现的问题列表
    rationale: str  # 反思的推理过程
    iteration: int = 0  # 第几轮反思
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_confident": self.is_confident,
            "confidence": self.confidence,
            "issues": self.issues,
            "rationale": self.rationale,
            "iteration": self.iteration,
            "metadata": self.metadata,
        }


@dataclass
class AgentState:
    messages: list[ChatMessage] = field(default_factory=list)
    system_message: ChatMessage | None = None
    tool_results: dict[str, Any] = field(default_factory=dict)
    iteration_count: int = 0
    reflection_count: int = 0
    reflection_log: list[ReflectionResult] = field(default_factory=list)
    tool_call_log: list[dict[str, Any]] = field(default_factory=list)  # 新增: 工具调用历史
    status: AgentStatus = AgentStatus.IDLE
    total_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    model_name: str = "default"
    system_prompt: str = ""
    max_iterations: int = 10
    max_tool_calls: int = 20
    timeout: float = 300.0
    temperature: float = 0.7
    stream: bool = True
    enable_context_management: bool = True
    enable_reflection: bool = False  # 新增: 是否启用 Self-Reflection
    max_reflections: int = 2  # 新增: 最多反思次数(避免无限循环)
    reflection_threshold: float = 0.6  # 新增: 低于此 confidence 视为不可信
    reserve_output_tokens: int = 4096
    metadata: dict[str, Any] = field(default_factory=dict)
    # ── P1-1 Checkpoint ──
    enable_checkpoint: bool = True  # 新增: 每轮 iteration 后自动持久化
    # ── P1-2 Human-in-the-Loop ──
    require_approval_for_tools: list[str] = field(default_factory=list)  # 这些 tool 调前需人工批
    human_loop_timeout: float = 300.0  # 审批超时秒数,超时自动 reject
    # ── P1-3 Sub-Agent ──
    enable_sub_agent: bool = False  # 是否允许 LLM 调 delegate_subagent tool
    # ── P1-4 Tool Retry ──
    enable_tool_retry: bool = False  # 工具失败时是否自动 retry (transient 错误)
    tool_retry_max_retries: int = 3
    tool_retry_base_delay: float = 0.5


class BaseAgent(ABC):
    def __init__(
        self,
        config: AgentConfig | None = None,
        llm_manager: LLMManager | None = None,
        tool_registry: ToolRegistry | None = None,
        checkpoint_store: Any | None = None,  # P1-1: AgentCheckpointStore
    ):
        self.config = config or AgentConfig()
        self.llm = llm_manager or get_llm_manager()
        self.tools = tool_registry or get_tool_registry()
        self.state = AgentState()
        self._context_manager: ContextWindowManager | None = None
        # P1-1: checkpoint store(默认 None, run() 时懒加载)
        self._checkpoint_store = checkpoint_store
        # P1-2: 当前 run 等待审批的事件 + 结果
        self._approval_event: asyncio.Event | None = None
        self._approval_result: dict[str, Any] | None = None
        # P1-1: 当前 run_id
        self.run_id: str | None = None
        self._event_handlers: dict[str, list[Callable]] = {
            "on_thinking": [],
            "on_tool_call": [],
            "on_tool_result": [],
            "on_finish": [],
            "on_error": [],
            # P1-2: 等待审批事件(让前端能 subscribe)
            "on_await_approval": [],
        }

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    def _get_context_manager(self) -> ContextWindowManager:
        if self._context_manager is None:
            self._context_manager = self.llm.get_context_manager(self.config.model_name)
        return self._context_manager

    def on(self, event: str, handler: Callable) -> None:
        if event in self._event_handlers:
            self._event_handlers[event].append(handler)

    async def _emit(self, event: str, **kwargs) -> None:
        for handler in self._event_handlers.get(event, []):
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(**kwargs)
                else:
                    handler(**kwargs)
            except Exception as e:
                logger.warning(f"Event handler error for {event}: {e}")

    # ── Self-Reflection ──────────────────────────────────

    async def reflect(
        self,
        last_response: str,
        messages: list[ChatMessage] | None = None,
    ) -> ReflectionResult:
        """
        Self-Reflection: 让 LLM 评估自己上一轮的回答是否可信。

        用法: 在 BaseAgent.run() 拿到 LLM 最终答案(无 tool_call)时调用。
        - 如果 is_confident=True → 直接返回答案
        - 如果 issues 非空 → 把 issues 注入回 messages,让 LLM 重新回答

        实现: 给 LLM 一个结构化 prompt,要求 JSON 输出 confidence/issues/rationale
        """
        self.state.status = AgentStatus.REFLECTING
        await self._emit("on_thinking", iteration=self.state.iteration_count, phase="reflect")

        reflect_prompt = (
            "你是 Self-Reflection 评估器。评估下面 AI 助手的回答是否可信、是否有事实依据。\n"
            "严格标准: 不确定就标 not_confident,有任何编造/无依据/答非所问都列出 issue。\n\n"
            "【原问题】\n{query}\n\n"
            "【AI 回答】\n{answer}\n\n"
            "【输出格式】(严格 JSON,不要其他内容):\n"
            '{{\n  "confidence": 0.0-1.0 的浮点数,\n'
            '  "is_confident": true/false (confidence >= 0.6 为 true),\n'
            '  "issues": ["问题1", "问题2", ...] (无问题返回空列表),\n'
            '  "rationale": "评估理由,1-2 句话"\n}}'
        )

        # 找原始 query(最近一条 user message)
        query = ""
        msgs = messages or self.state.messages
        for m in reversed(msgs):
            if m.role == "user":
                query = m.content if isinstance(m.content, str) else str(m.content)
                break

        prompt = reflect_prompt.format(query=query[:2000], answer=last_response[:2000])
        try:
            response = await asyncio.wait_for(
                self.llm.chat(
                    messages=[ChatMessage(role="user", content=prompt)],
                    model=self.config.model_name,
                    temperature=0.2,  # 反思要稳定
                ),
                timeout=min(self.config.timeout, 30.0),
            )
        except Exception as e:
            logger.warning(f"Self-Reflection LLM 调用失败,默认通过: {e}")
            return ReflectionResult(
                is_confident=True,
                confidence=1.0,
                issues=[],
                rationale=f"reflection failed: {e}",
                iteration=self.state.reflection_count,
            )

        # 解析 JSON
        text = response.content or ""
        result = self._parse_reflection_json(text)
        result.iteration = self.state.reflection_count
        result.metadata = {
            "llm_tokens": response.usage.get("total_tokens", 0),
            "model": self.config.model_name,
        }

        self.state.reflection_count += 1
        self.state.reflection_log.append(result)
        self.state.total_tokens += response.usage.get("total_tokens", 0)

        logger.info(
            f"Self-Reflection: confidence={result.confidence:.2f} "
            f"is_confident={result.is_confident} issues={len(result.issues)}"
        )
        return result

    def _parse_reflection_json(self, text: str) -> ReflectionResult:
        """从 LLM 输出里提 JSON(宽容)"""
        text = (text or "").strip()
        # 去掉 markdown 围栏
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(line for line in lines if not line.strip().startswith("```"))
        # 找第一个 { 到最后一个 }
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(f"Reflection JSON 解析失败,fallback 通过: {text[:100]}")
            return ReflectionResult(
                is_confident=True,
                confidence=0.7,
                issues=[],
                rationale="JSON 解析失败,默认通过",
            )
        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        is_confident = bool(data.get("is_confident", confidence >= self.config.reflection_threshold))
        issues = data.get("issues", [])
        if not isinstance(issues, list):
            issues = []
        issues = [str(i) for i in issues if i]
        return ReflectionResult(
            is_confident=is_confident,
            confidence=max(0.0, min(1.0, confidence)),
            issues=issues,
            rationale=str(data.get("rationale", "")),
        )

    def get_system_prompt(self) -> str:
        # 默认实现：返回基础 system prompt。
        # 子类可重写以定制 persona / domain instructions。
        return self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        return (
            "You are DATA-AI, a helpful AI assistant. "
            "Use the available tools when appropriate. "
            "Be concise, accurate, and respond in the user's language."
        )

    def _build_system_message(self) -> ChatMessage:
        prompt = self.get_system_prompt()
        if self.config.system_prompt:
            prompt = f"{prompt}\n\n{self.config.system_prompt}"
        return ChatMessage(role="system", content=prompt)

    def _get_tool_schemas(self) -> list[dict[str, Any]]:
        schemas = self.tools.get_openai_tool_schemas()
        # P1-3: 动态注入 delegate_subagent tool (仅当 enable_sub_agent=True)
        if self.config.enable_sub_agent and not any(
            s.get("function", {}).get("name") == "delegate_subagent" for s in schemas
        ):
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": "delegate_subagent",
                        "description": (
                            "把子任务委派给一个 sub-agent。可选 role 是 'customer_service' / "
                            "'finance_analyst' / 'secretary' / 'novel_writer'(不传则用 default "
                            "配置),sub-agent 会套用该 role 的 system_prompt/tools/temperature, "
                            "完全独立跑完后把结果作为 tool result 返回。\n"
                            "适用场景:需要不同 persona 的专家回答、需要隔离 context、并行处理多个子问题。"
                        ),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "交给 sub-agent 的具体子任务/问题",
                                },
                                "role": {
                                    "type": "string",
                                    "description": "可选: 套用的 preset role (customer_service / finance_analyst / secretary / novel_writer)",
                                    "enum": ["customer_service", "finance_analyst", "secretary", "novel_writer"],
                                },
                            },
                            "required": ["query"],
                        },
                    },
                }
            )
        return schemas

    def _build_context_message(self) -> ChatMessage | None:
        return None

    async def _execute_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        # P1-3: 拦截 delegate_subagent tool 调 — 在 agent 内部自己处理(不丢给 registry)
        if tool_name == "delegate_subagent":
            return await self._do_delegate_subagent(arguments)

        logger.info(
            f"Executing tool: {tool_name}",
            tool_name=tool_name,
            arguments=arguments,
        )
        await self._emit("on_tool_call", tool_name=tool_name, arguments=arguments)

        # P1-4: 走 retry 路径(如果 agent 开了 enable_tool_retry)
        exec_coro = (
            self.tools.execute_with_retry(
                tool_name,
                arguments,
                max_retries=self.config.tool_retry_max_retries,
                base_delay=self.config.tool_retry_base_delay,
            )
            if self.config.enable_tool_retry
            else self.tools.execute(tool_name, arguments)
        )

        try:
            result = await exec_coro
            result_str = str(result)
            await self._emit(
                "on_tool_result",
                tool_name=tool_name,
                result=result_str,
            )
            return result_str
        except Exception as e:
            error_msg = f"Tool execution error: {e}"
            logger.error(error_msg, tool_name=tool_name, error=str(e))
            raise ToolExecutionError(
                tool=tool_name,
                message=f"Error executing tool '{tool_name}': {e}",
            )

    async def run(
        self,
        user_input: str,
        initial_messages: list[ChatMessage] | None = None,
        run_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        # P1-1: 注入 run_id + checkpoint store
        from .checkpoint import get_checkpoint_store

        self.run_id = run_id or f"run-{int(_time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        if self.config.enable_checkpoint and self._checkpoint_store is None:
            self._checkpoint_store = get_checkpoint_store()
        self._approval_event = None
        self._approval_result = None

        self.state = AgentState()
        self.state.status = AgentStatus.THINKING

        system_message = self._build_system_message()
        self.state.system_message = system_message

        # 重建 messages：先放历史（不包含末尾那条 user_input），再追加末尾 user_input
        # 这样 LLM 在 tool_call 循环里能"看到"完整对话历史
        history = list(initial_messages) if initial_messages else []
        # 把 user_input 作为最后一条 user message（如已存在则替换）
        if history and history[-1].role == "user" and history[-1].content == user_input:
            pass  # 末尾就是同一 query，跳过
        else:
            history.append(ChatMessage(role="user", content=user_input))
        # 把 system 拼到最前（如果有 user-provided system，也合到第一条 system）
        if history and history[0].role == "system":
            self.state.messages = [history[0], system_message] + history[1:]
        else:
            self.state.messages = [system_message] + history

        tool_schemas = self._get_tool_schemas() if self.tools.get_tool_count() > 0 else None

        # P1-1: 写初始 checkpoint(status=running)
        await self._save_checkpoint(status="running")

        while self.state.iteration_count < self.config.max_iterations:
            self.state.iteration_count += 1

            if self.config.enable_context_management:
                self.state.messages = self._get_context_manager().trim_messages(
                    self.state.messages,
                    system_message=system_message,
                )

            await self._emit("on_thinking", iteration=self.state.iteration_count)

            try:
                response = await asyncio.wait_for(
                    self.llm.chat(
                        messages=self.state.messages,
                        model=self.config.model_name,
                        tools=tool_schemas,
                        temperature=self.config.temperature,
                    ),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                self.state.status = AgentStatus.ERROR
                await self._save_checkpoint(status="error", error=f"timeout after {self.config.timeout}s")
                raise AgentTimeoutError(
                    agent=self.config.model_name,
                    timeout=self.config.timeout,
                    iteration=self.state.iteration_count,
                    run_id=self.run_id,
                )
            except Exception as e:
                self.state.status = AgentStatus.ERROR
                await self._save_checkpoint(status="error", error=str(e))
                raise AgentExecutionError(
                    agent=self.config.model_name,
                    message=f"LLM call failed: {e}",
                    step=self.state.iteration_count,
                    run_id=self.run_id,
                    cause=str(e),
                )

            self.state.total_tokens += response.usage.get("total_tokens", 0)

            if response.tool_calls:
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
                self.state.messages.append(assistant_msg)
                # 记录工具调用历史(供 trace / response 暴露)
                for tc in response.tool_calls:
                    self.state.tool_call_log.append(
                        {
                            "iteration": self.state.iteration_count,
                            "tool_call_id": tc.get("id"),
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        }
                    )

                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}

                    # P1-2: Human-in-the-Loop — 高风险 tool 调前暂停等审批
                    if self.config.require_approval_for_tools and tool_name in self.config.require_approval_for_tools:
                        approved = await self._await_human_approval(
                            tool_name=tool_name,
                            arguments=arguments,
                            tool_call_id=tool_call["id"],
                            iteration=self.state.iteration_count,
                        )
                        if not approved:
                            # 拒绝:把拒绝理由写回 tool message,让 LLM 看到
                            result = f"Error: Human reviewer REJECTED this tool call ({tool_name}). Reason: {self._approval_result.get('reason', 'n/a') if self._approval_result else 'n/a'}"
                            self.state.messages.append(
                                ChatMessage(
                                    role="tool",
                                    content=result,
                                    tool_call_id=tool_call["id"],
                                )
                            )
                            for entry in self.state.tool_call_log:
                                if entry.get("tool_call_id") == tool_call["id"]:
                                    entry["result"] = result[:2000]
                                    entry["human_rejected"] = True
                                    break
                            continue

                    try:
                        result = await self._execute_tool(tool_name, arguments)
                    except ToolExecutionError as e:
                        result = f"Error: {e}"

                    self.state.messages.append(
                        ChatMessage(
                            role="tool",
                            content=str(result),
                            tool_call_id=tool_call["id"],
                        )
                    )
                    # 记录工具执行结果
                    for entry in self.state.tool_call_log:
                        if entry.get("tool_call_id") == tool_call["id"]:
                            entry["result"] = str(result)[:2000]
                            break

                # P1-1: 每轮 tool loop 结束存 checkpoint
                await self._save_checkpoint()
                continue

            # ── Self-Reflection 注入点 ──
            # LLM 返回了最终答案(无 tool_call),先 reflection 一次
            if self.config.enable_reflection and self.state.reflection_count < self.config.max_reflections:
                reflection = await self.reflect(response.content, self.state.messages)
                if not reflection.is_confident and reflection.issues:
                    # 把 reflection 反馈注入到 messages,让 LLM 重新回答
                    feedback = (
                        f"[Self-Reflection 第 {reflection.iteration + 1} 轮反馈]\n"
                        f"信心度: {reflection.confidence:.2f}\n"
                        f"问题: {'; '.join(reflection.issues)}\n"
                        f"理由: {reflection.rationale}\n\n"
                        "请基于上述反馈修正你的回答。"
                    )
                    self.state.messages.append(
                        ChatMessage(
                            role="assistant",
                            content=response.content,
                        )
                    )
                    self.state.messages.append(ChatMessage(role="user", content=feedback))
                    continue  # 让 LLM 重新生成

            self.state.messages.append(
                ChatMessage(
                    role="assistant",
                    content=response.content,
                )
            )

            self.state.status = AgentStatus.FINISHED
            await self._emit("on_finish", content=response.content)
            # P1-1: 成功终态存 checkpoint
            await self._save_checkpoint(
                status="finished",
                final_content=response.content,
            )

            return {
                "content": response.content,
                "run_id": self.run_id,
                "iterations": self.state.iteration_count,
                "reflections": [r.to_dict() for r in self.state.reflection_log],
                "tool_calls": list(self.state.tool_call_log),
                "total_tokens": self.state.total_tokens,
                "usage": response.usage,
                "finish_reason": response.finish_reason,
                "messages": self.state.messages,
            }

        # P1-1: 超过 max_iterations 存 error checkpoint
        await self._save_checkpoint(
            status="error",
            error=f"max_iterations={self.config.max_iterations} reached",
        )
        raise AgentMaxIterationsExceededError(
            agent=self.config.model_name,
            max_iterations=self.config.max_iterations,
            iterations=self.state.iteration_count,
        )

    # ── P1-3: Sub-Agent 委派 ──────────────────────────────────

    async def delegate(
        self,
        query: str,
        role: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """
        P1-3: 把子任务委派给一个 sub-agent。

        关键设计:
        - **共享 LLM/工具/CKPT store** — sub-agent 跟 parent 同一个 LLMManager / ToolRegistry
          / CheckpointStore,避免重复加载大模型/工具/磁盘 IO。
        - **隔离 system_prompt** — 如果传 role,则从 REGISTERED_PRESETS 拿 system_prompt /
          tools / max_iterations / temperature / reflection 配置(不传则继承 parent)。
        - **独立 run_id** — sub-agent 用 `{parent_run_id}/sub-{ms}-{uuid8}`,方便溯源。
        - **写回 parent 的 tool_call_log** — 在结果里返回 sub_run_id 让 parent 记录。
        - **支持并行** — 父 agent 可以 await asyncio.gather(*[self.delegate(q) for q in qs])。

        Args:
            query: 子任务/问题
            role:  preset role 名(customer_service / finance_analyst / secretary / novel_writer)
            run_id: 可选,手动指定 sub-agent run_id(测试 / 重放用)

        Returns:
            dict: {
                "content": sub-agent 最终答案,
                "run_id": sub-agent run_id,
                "parent_run_id": parent run_id,
                "iterations": ...,
                "tool_calls": [...],
                "preset_role": role 或 None,
            }
        """
        # 1) 生成 sub-agent run_id
        parent_run_id = self.run_id or "root"
        sub_run_id = run_id or f"{parent_run_id}/sub-{int(_time.time() * 1000)}-{uuid.uuid4().hex[:8]}"

        # 2) 解析 preset(如果有 role)
        preset_def: dict[str, Any] | None = None
        if role:
            try:
                from data_ai.plugins.agents import get_preset

                preset_def = get_preset(role) or {}
            except Exception as exc:
                logger.warning(f"delegate: preset role={role!r} 解析失败,fallback: {exc!r}")
                preset_def = {}

        # 3) 构造 sub-agent config(继承 parent + 覆盖 preset)
        sub_config = AgentConfig(
            model_name=self.config.model_name,
            system_prompt=preset_def.get("system_prompt", self.config.system_prompt)
            if preset_def
            else self.config.system_prompt,
            max_iterations=int(preset_def.get("max_iterations", self.config.max_iterations))
            if preset_def
            else self.config.max_iterations,
            temperature=float(preset_def.get("temperature", self.config.temperature))
            if preset_def
            else self.config.temperature,
            stream=False,  # sub-agent 走非流式,串到 parent 的 tool result
            enable_context_management=self.config.enable_context_management,
            enable_reflection=bool(preset_def.get("reflection", self.config.enable_reflection))
            if preset_def
            else self.config.enable_reflection,
            max_reflections=self.config.max_reflections,
            reflection_threshold=self.config.reflection_threshold,
            reserve_output_tokens=self.config.reserve_output_tokens,
            timeout=self.config.timeout,
            # 父 agent 的 checkpoint 配置继承下去(sub 也会存盘)
            enable_checkpoint=self.config.enable_checkpoint,
            # sub-agent 默认不需要再开 sub-agent(避免无限递归)
            enable_sub_agent=False,
            metadata={
                **self.config.metadata,
                "parent_run_id": parent_run_id,
                "preset_role": role,
            },
        )

        # 4) 实例化 sub-agent(用同 LLM / 工具 / checkpoint store)
        # DefaultAgent 跟 BaseAgent 在同 module,直接用
        sub_agent = DefaultAgent(
            config=sub_config,
            llm_manager=self.llm,
            tool_registry=self.tools,
            checkpoint_store=self._checkpoint_store,
        )

        # 5) 跑 sub-agent
        logger.info(f"[delegate] parent={parent_run_id} sub={sub_run_id} role={role!r} " f"query={query[:80]!r}")
        try:
            # P1-3: 把 parent_run_id/preset_role 写进 sub-agent state.metadata.runtime,
            # 这样 _save_checkpoint 会自动存到 checkpoint.metadata(供 /sub_runs 端点查)
            sub_agent.state.metadata.setdefault("runtime", {})
            sub_agent.state.metadata["runtime"]["parent_run_id"] = parent_run_id
            sub_agent.state.metadata["runtime"]["preset_role"] = role
            sub_result = await sub_agent.run(query, run_id=sub_run_id)
        except Exception as exc:
            logger.error(f"[delegate] sub-agent 失败: {exc!r}")
            return {
                "content": f"[Sub-agent error: {exc}]",
                "run_id": sub_run_id,
                "parent_run_id": parent_run_id,
                "iterations": 0,
                "tool_calls": [],
                "preset_role": role,
                "error": str(exc),
            }

        return {
            "content": sub_result.get("content", ""),
            "run_id": sub_run_id,
            "parent_run_id": parent_run_id,
            "iterations": sub_result.get("iterations", 0),
            "tool_calls": sub_result.get("tool_calls", []),
            "total_tokens": sub_result.get("total_tokens", 0),
            "reflections": sub_result.get("reflections", []),
            "preset_role": role,
        }

    async def delegate_many(
        self,
        queries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        P1-3 补充: 并行委派多个 sub-agent。
        P1-7 增强: 主动检查 sub-agent 可用性 + 准确报错。

        用 asyncio.gather 真正并发(共享 LLM 客户端的连接池),每个 sub-agent 独立跑。

        Args:
            queries: list of dict, 每个含 query 必填 + role 可选 + run_id 可选
                     例: [{"query": "Q1", "role": "customer_service"},
                           {"query": "Q2", "role": "finance_analyst"}]

        Returns:
            list of delegate() 返回的 dict(顺序跟输入一致)
            失败的子任务会以 dict {"success": False, "error": ..., "trace_id": ...} 形式返回,不抛异常
        """
        if not queries:
            return []

        # P1-7 主动检查: 验证每个 sub-agent 配置可用
        for i, q in enumerate(queries):
            role = q.get("role")
            if role:
                # 检查 preset role 是否有效
                available_roles = self._available_preset_roles() if hasattr(self, "_available_preset_roles") else []
                if available_roles and role not in available_roles:
                    logger.warning(
                        f"delegate_many: sub-task [{i}] role='{role}' 不在已知 presets 中, "
                        f"将使用 fallback。available={available_roles}"
                    )

        # P1-7: 用 return_exceptions=True + 单独处理,确保一个子任务失败不影响其他
        coros = [self._delegate_safe(q, idx) for idx, q in enumerate(queries)]
        return await asyncio.gather(*coros, return_exceptions=False)

    async def _delegate_safe(self, q: dict[str, Any], idx: int) -> dict[str, Any]:
        """
        P1-7: delegate 的安全包装 — 失败不抛,返回 dict with error info
        """
        import uuid as _uuid

        trace_id = _uuid.uuid4().hex[:12]
        query = q.get("query", "")
        role = q.get("role")
        if not query:
            return {
                "success": False,
                "error": "delegate requires 'query' argument",
                "trace_id": trace_id,
                "sub_task_index": idx,
            }
        try:
            result = await self.delegate(query, role=role, run_id=q.get("run_id"))
            # P1-7: 主动验证 sub-agent 结果
            if isinstance(result, dict):
                result.setdefault("trace_id", trace_id)
                result.setdefault("sub_task_index", idx)
                if not result.get("success", True):
                    result.setdefault("error_class", "sub_agent_failed")
            return result
        except Exception as e:
            logger.error(f"delegate_many sub-task [{idx}] failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)[:500],
                "error_class": type(e).__name__,
                "trace_id": trace_id,
                "sub_task_index": idx,
                "query": query[:200],
                "role": role,
            }

    async def _do_delegate_subagent(self, arguments: dict[str, Any]) -> str:
        """
        P1-3: 当 LLM 调 delegate_subagent tool 时的实际处理函数
        复用 self.delegate(),把 dict 结果压平成 tool result 字符串
        """
        query = arguments.get("query", "")
        role = arguments.get("role")
        if not query:
            return "Error: delegate_subagent requires 'query' argument"
        result = await self.delegate(query, role=role)
        # 把 dict 序列化成 JSON 字符串,LLM 看得到结构
        try:
            payload = json.dumps(result, ensure_ascii=False, indent=2)[:8000]
        except Exception:
            payload = str(result)[:8000]
        return payload

    # ── P1-1: Checkpoint 持久化 / Resume ─────────────────────

    async def _save_checkpoint(
        self,
        status: str | None = None,
        final_content: str | None = None,
        error: str | None = None,
        pending_approval: dict[str, Any] | None = None,
    ) -> None:
        """
        把当前 state 序列化成 AgentCheckpoint 存到 store

        P1-1 设计: 不每条 tool_call 都存,避免高频写盘。
        实际上在 run() 主循环里每轮 iteration 结束调一次(频率 = LLM 调用次数)。
        对于 sub-second 工具调用这个粒度足够;高频场景可调成"每 N 轮存一次"。
        """
        if not self.config.enable_checkpoint or self._checkpoint_store is None:
            return
        if not self.run_id:
            return
        from .checkpoint import AgentCheckpoint

        try:
            ck = AgentCheckpoint(
                run_id=self.run_id,
                created_at=self.state.metadata.get("checkpoint_created_at") or _now(),
                updated_at=_now(),
                status=status or self.state.status.value,
                messages=[_msg_to_dict(m) for m in self.state.messages],
                iteration_count=self.state.iteration_count,
                reflection_count=self.state.reflection_count,
                reflection_log=[r.to_dict() for r in self.state.reflection_log],
                tool_call_log=list(self.state.tool_call_log),
                pending_approval=pending_approval,
                final_content=final_content,
                error=error,
                metadata={
                    # P1-3: 合并 config 静态 metadata + 运行时 metadata(parent_run_id 等)
                    **(self.config.metadata or {}),
                    **(self.state.metadata.get("runtime") or {}),
                    "model_name": self.config.model_name,
                    "temperature": self.config.temperature,
                    "system_prompt_head": (self.config.system_prompt or "")[:200],
                    "enable_reflection": self.config.enable_reflection,
                },
            )
            await self._checkpoint_store.save(ck)
        except Exception as exc:  # pragma: no cover - 不让 checkpoint 失败搞垮 run
            logger.warning(f"checkpoint save 失败: run_id={self.run_id} err={exc!r}")

    async def resume(
        self,
        run_id: str,
        approval: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        从 checkpoint 恢复 run

        P1-1 + P1-2 配合:
        - 一般情况: 从 saved checkpoint 读 messages / iteration_count,继续 run
        - 审批恢复: approval={"approved": true/false, "reason": "..."} 时,
          注入 _approval_result 触发 _await_human_approval 返回
        - 终态(finished/error): 直接返回 saved final_content

        实现:
        - 读 checkpoint
        - 恢复 state.messages / tool_call_log / reflection_log / iteration_count
        - 调 _continue_after_resume() 进入 run() 主循环(同 run() 行为,但不重建 state)
        """

        if self._checkpoint_store is None:
            from .checkpoint import get_checkpoint_store

            self._checkpoint_store = get_checkpoint_store()
        ck = await self._checkpoint_store.load(run_id)
        if ck is None:
            raise FileNotFoundError(f"checkpoint not found: {run_id}")

        # 终态直接返回
        if ck.status in ("finished", "error"):
            return {
                "content": ck.final_content or "",
                "run_id": run_id,
                "iterations": ck.iteration_count,
                "reflections": ck.reflection_log,
                "tool_calls": ck.tool_call_log,
                "total_tokens": 0,
                "usage": {},
                "finish_reason": ck.status,
                "resumed": True,
                "checkpoint_status": ck.status,
            }

        # 恢复 state
        self.run_id = run_id
        self.state.messages = [_dict_to_msg(d) for d in ck.messages]
        self.state.iteration_count = ck.iteration_count
        self.state.reflection_count = ck.reflection_count
        self.state.reflection_log = [ReflectionResult(**r) for r in ck.reflection_log] if ck.reflection_log else []
        self.state.tool_call_log = list(ck.tool_call_log)
        self.state.status = AgentStatus.RUNNING if hasattr(AgentStatus, "RUNNING") else AgentStatus.THINKING
        self.state.metadata["checkpoint_created_at"] = ck.created_at

        # 审批恢复:把结果注入 _approval_result + set event
        if approval is not None:
            self._approval_result = {
                "approved": bool(approval.get("approved")),
                "reason": approval.get("reason") or ("auto-approved" if approval.get("approved") else "no reason"),
            }
            if self._approval_event is not None:
                self._approval_event.set()

        return await self._continue_after_resume()

    async def _continue_after_resume(self) -> dict[str, Any]:
        """
        resume() 后真正继续 run 的主循环(从当前 state 接续,不重建 messages)
        """
        from .checkpoint import AgentCheckpoint  # noqa: F401  保持引用

        # 重建 system_message(如果 state 里有就用,否则 new)
        system_message = self.state.system_message or self._build_system_message()
        self.state.system_message = system_message
        if not self.state.messages or self.state.messages[0] is not system_message:
            if not self.state.messages:
                self.state.messages = [system_message]

        tool_schemas = self._get_tool_schemas() if self.tools.get_tool_count() > 0 else None
        await self._save_checkpoint(status="running")

        while self.state.iteration_count < self.config.max_iterations:
            self.state.iteration_count += 1

            if self.config.enable_context_management:
                self.state.messages = self._get_context_manager().trim_messages(
                    self.state.messages,
                    system_message=system_message,
                )

            try:
                response = await asyncio.wait_for(
                    self.llm.chat(
                        messages=self.state.messages,
                        model=self.config.model_name,
                        tools=tool_schemas,
                        temperature=self.config.temperature,
                    ),
                    timeout=self.config.timeout,
                )
            except asyncio.TimeoutError:
                await self._save_checkpoint(status="error", error="timeout after resume")
                raise AgentTimeoutError(
                    agent=self.config.model_name,
                    timeout=self.config.timeout,
                    run_id=self.run_id,
                )
            except Exception as e:
                await self._save_checkpoint(status="error", error=str(e))
                raise AgentExecutionError(
                    agent=self.config.model_name,
                    message=f"LLM call failed after resume: {e}",
                    run_id=self.run_id,
                )

            self.state.total_tokens += response.usage.get("total_tokens", 0)

            if response.tool_calls:
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=response.tool_calls,
                )
                self.state.messages.append(assistant_msg)
                for tc in response.tool_calls:
                    self.state.tool_call_log.append(
                        {
                            "iteration": self.state.iteration_count,
                            "tool_call_id": tc.get("id"),
                            "name": tc.get("function", {}).get("name"),
                            "arguments": tc.get("function", {}).get("arguments"),
                        }
                    )

                for tool_call in response.tool_calls:
                    tool_name = tool_call["function"]["name"]
                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}

                    if self.config.require_approval_for_tools and tool_name in self.config.require_approval_for_tools:
                        approved = await self._await_human_approval(
                            tool_name=tool_name,
                            arguments=arguments,
                            tool_call_id=tool_call["id"],
                            iteration=self.state.iteration_count,
                        )
                        if not approved:
                            result = (
                                f"Error: Human reviewer REJECTED this tool call ({tool_name}). "
                                f"Reason: {self._approval_result.get('reason', 'n/a') if self._approval_result else 'n/a'}"
                            )
                            self.state.messages.append(
                                ChatMessage(role="tool", content=result, tool_call_id=tool_call["id"])
                            )
                            for entry in self.state.tool_call_log:
                                if entry.get("tool_call_id") == tool_call["id"]:
                                    entry["result"] = result[:2000]
                                    entry["human_rejected"] = True
                                    break
                            continue

                    try:
                        result = await self._execute_tool(tool_name, arguments)
                    except ToolExecutionError as e:
                        result = f"Error: {e}"
                    self.state.messages.append(
                        ChatMessage(role="tool", content=str(result), tool_call_id=tool_call["id"])
                    )
                    for entry in self.state.tool_call_log:
                        if entry.get("tool_call_id") == tool_call["id"]:
                            entry["result"] = str(result)[:2000]
                            break

                await self._save_checkpoint()
                continue

            if self.config.enable_reflection and self.state.reflection_count < self.config.max_reflections:
                reflection = await self.reflect(response.content, self.state.messages)
                if not reflection.is_confident and reflection.issues:
                    feedback = (
                        f"[Self-Reflection 第 {reflection.iteration + 1} 轮反馈]\n"
                        f"信心度: {reflection.confidence:.2f}\n"
                        f"问题: {'; '.join(reflection.issues)}\n"
                        f"理由: {reflection.rationale}\n\n"
                        "请基于上述反馈修正你的回答。"
                    )
                    self.state.messages.append(ChatMessage(role="assistant", content=response.content))
                    self.state.messages.append(ChatMessage(role="user", content=feedback))
                    continue

            self.state.messages.append(ChatMessage(role="assistant", content=response.content))
            self.state.status = AgentStatus.FINISHED
            await self._save_checkpoint(status="finished", final_content=response.content)
            return {
                "content": response.content,
                "run_id": self.run_id,
                "iterations": self.state.iteration_count,
                "reflections": [r.to_dict() for r in self.state.reflection_log],
                "tool_calls": list(self.state.tool_call_log),
                "total_tokens": self.state.total_tokens,
                "usage": response.usage,
                "finish_reason": response.finish_reason,
                "resumed": True,
            }

        await self._save_checkpoint(status="error", error="max_iterations reached after resume")
        raise AgentMaxIterationsExceededError(
            agent=self.config.model_name,
            max_iterations=self.config.max_iterations,
            iterations=self.state.iteration_count,
        )

    # ── P1-2: Human-in-the-Loop ─────────────────────────────

    async def _await_human_approval(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str,
        iteration: int,
    ) -> bool:
        """
        等人工审批 — 调前挂起,直到 approve()/reject() 被调或超时

        P1-2 设计:
        - 用 asyncio.Event 暂停主循环,直到外部 approve()
        - 持久化 pending_approval 到 checkpoint(进程崩了也不丢)
        - 超时默认 human_loop_timeout=300s,超时自动 reject
        - emit on_await_approval 让前端可订阅
        """
        if self._approval_event is None:
            self._approval_event = asyncio.Event()
            self._approval_result = None
        # 持久化 pending_approval
        await self._save_checkpoint(
            status="awaiting_approval",
            pending_approval={
                "tool_name": tool_name,
                "arguments": arguments,
                "tool_call_id": tool_call_id,
                "iteration": iteration,
                "requested_at": _now(),
            },
        )
        await self._emit(
            "on_await_approval",
            run_id=self.run_id,
            tool_name=tool_name,
            arguments=arguments,
            tool_call_id=tool_call_id,
            iteration=iteration,
        )
        logger.info(
            f"[await_approval] run_id={self.run_id} tool={tool_name} args={arguments} "
            f"timeout={self.config.human_loop_timeout}s"
        )

        try:
            await asyncio.wait_for(
                self._approval_event.wait(),
                timeout=self.config.human_loop_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"[await_approval] TIMEOUT run_id={self.run_id} tool={tool_name} "
                f"-> auto-reject after {self.config.human_loop_timeout}s"
            )
            self._approval_result = {
                "approved": False,
                "reason": f"auto-rejected: human_loop_timeout={self.config.human_loop_timeout}s exceeded",
            }
        # 重置 event(下次审批复用)
        if self._approval_event is not None:
            self._approval_event = asyncio.Event()

        approved = bool(self._approval_result and self._approval_result.get("approved"))
        # 清掉 pending_approval
        await self._save_checkpoint(status="running", pending_approval=None)
        return approved

    def approve(self, reason: str = "approved by reviewer") -> None:
        """
        外部 API: 同意 pending 工具调用。Agent 主循环会被唤醒继续。
        """
        if self._approval_event is None:
            # 还没 await 任何审批,直接缓存结果
            self._approval_result = {"approved": True, "reason": reason}
            return
        self._approval_result = {"approved": True, "reason": reason}
        self._approval_event.set()
        logger.info(f"[approve] run_id={self.run_id}")

    def reject(self, reason: str = "rejected by reviewer") -> None:
        """
        外部 API: 拒绝 pending 工具调用。Agent 主循环会被唤醒,tool_call 写回 reject reason。
        """
        if self._approval_event is None:
            self._approval_result = {"approved": False, "reason": reason}
            return
        self._approval_result = {"approved": False, "reason": reason}
        self._approval_event.set()
        logger.info(f"[reject] run_id={self.run_id} reason={reason}")

    def get_pending_approval(self) -> dict[str, Any] | None:
        """从最新 checkpoint 读 pending_approval — 外部 poll 用"""
        if self._checkpoint_store is None or not self.run_id:
            return None
        # 同步 helper: 用 asyncio.run_coroutine_threadsafe 或外部直接 load
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None  # 异步场景让外部用 await load_pending_approval()
            ck = loop.run_until_complete(self._checkpoint_store.load(self.run_id))
        except RuntimeError:
            return None
        return ck.pending_approval if ck else None

    async def load_pending_approval(self) -> dict[str, Any] | None:
        """异步版: 外部 await 查 pending approval"""
        if self._checkpoint_store is None or not self.run_id:
            return None
        ck = await self._checkpoint_store.load(self.run_id)
        return ck.pending_approval if ck else None

    async def run_stream(
        self,
        user_input: str,
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        self.state = AgentState()
        self.state.status = AgentStatus.STREAMING

        system_message = self._build_system_message()
        self.state.system_message = system_message
        self.state.messages = [system_message]

        context_msg = self._build_context_message()
        if context_msg:
            self.state.messages.append(context_msg)

        self.state.messages.append(ChatMessage(role="user", content=user_input))

        tool_schemas = self._get_tool_schemas() if self.tools.get_tool_count() > 0 else None

        while self.state.iteration_count < self.config.max_iterations:
            self.state.iteration_count += 1

            if self.config.enable_context_management:
                self.state.messages = self._get_context_manager().trim_messages(
                    self.state.messages,
                    system_message=system_message,
                )

            yield {
                "type": "thinking",
                "iteration": self.state.iteration_count,
                "status": self.state.status.value,
            }
            await self._emit("on_thinking", iteration=self.state.iteration_count)

            try:
                accumulated_content = ""
                final_tool_calls: list[dict] | None = None

                async def _stream_loop():
                    async for chunk in self.llm.chat_stream(
                        messages=self.state.messages,
                        model=self.config.model_name,
                        tools=tool_schemas,
                        temperature=self.config.temperature,
                    ):
                        yield chunk

                stream_gen = _stream_loop()
                while True:
                    try:
                        chunk = await asyncio.wait_for(stream_gen.__anext__(), timeout=self.config.timeout)
                    except StopAsyncIteration:
                        break
                    except asyncio.TimeoutError:
                        raise AgentTimeoutError(
                            message=f"Agent stream timed out after {self.config.timeout}s",
                            details={"iteration": self.state.iteration_count},
                        )
                    if chunk.content:
                        new_content = chunk.content
                        # P1-6: 去重 — 部分 Qwen3 模型会在流末尾把全部内容再发一次
                        # 检测方式:如果新 chunk 完全等于已累积内容,跳过;
                        # 或者新 chunk 是已累积内容的"扩展"(开头相同),只取扩展部分
                        if accumulated_content:
                            if new_content == accumulated_content:
                                continue
                            if new_content.startswith(accumulated_content):
                                new_content = new_content[len(accumulated_content) :]
                                if not new_content:
                                    continue
                        accumulated_content += new_content
                        yield {
                            "type": "token",
                            "content": new_content,
                            "model": chunk.model,
                        }

                    if chunk.tool_calls:
                        final_tool_calls = chunk.tool_calls

                if final_tool_calls:
                    assistant_msg = ChatMessage(
                        role="assistant",
                        content=accumulated_content,
                        tool_calls=final_tool_calls,
                    )
                    self.state.messages.append(assistant_msg)

                    for tool_call in final_tool_calls:
                        tool_name = tool_call["function"]["name"]
                        try:
                            arguments = json.loads(tool_call["function"]["arguments"])
                        except json.JSONDecodeError:
                            arguments = {}

                        yield {
                            "type": "tool_call",
                            "tool_name": tool_name,
                            "arguments": arguments,
                        }

                        try:
                            result = await self._execute_tool(tool_name, arguments)
                        except ToolExecutionError as e:
                            result = f"Error: {e}"

                        yield {
                            "type": "tool_result",
                            "tool_name": tool_name,
                            "result": str(result)[:2000],
                        }

                        self.state.messages.append(
                            ChatMessage(
                                role="tool",
                                content=str(result),
                                tool_call_id=tool_call["id"],
                            )
                        )

                    continue

                self.state.messages.append(
                    ChatMessage(
                        role="assistant",
                        content=accumulated_content,
                    )
                )

                self.state.status = AgentStatus.FINISHED
                yield {
                    "type": "finish",
                    "content": accumulated_content,
                    "iterations": self.state.iteration_count,
                    "total_tokens": self.state.total_tokens,
                }
                await self._emit("on_finish", content=accumulated_content)
                return

            except asyncio.TimeoutError:
                raise AgentTimeoutError(
                    message=f"Agent timed out after {self.config.timeout}s",
                    details={"iteration": self.state.iteration_count},
                )
            except Exception as e:
                yield {
                    "type": "error",
                    "error": str(e),
                    "iteration": self.state.iteration_count,
                }
                raise AgentExecutionError(
                    agent=self.config.model_name,
                    message=f"LLM call failed: {e}",
                    step=self.state.iteration_count,
                    run_id=self.run_id,
                    cause=str(e),
                )

        raise AgentMaxIterationsExceededError(
            agent=self.config.model_name,
            max_iterations=self.config.max_iterations,
            iterations=self.state.iteration_count,
        )

    def get_messages(self) -> list[ChatMessage]:
        return self.state.messages

    def get_tool_results(self) -> dict[str, Any]:
        return self.state.tool_results

    def get_state(self) -> AgentState:
        return self.state

    def reset(self) -> None:
        self.state = AgentState()

    async def cleanup(self) -> None:
        self.reset()
        self._event_handlers = {
            "on_thinking": [],
            "on_tool_call": [],
            "on_tool_result": [],
            "on_finish": [],
            "on_error": [],
        }


class DefaultAgent(BaseAgent):
    """P1-3: 默认的 BaseAgent 具体实现,直接用基类的 run()/delegate()。

    之所以独立成一个类,是因为 BaseAgent 是 ABC,但 run() 已完整实现,需要一个非
    abstract 的具体类给 sub-agent delegate() 用(避免直接 `BaseAgent(...)`)。
    """

    def get_system_prompt(self) -> str:
        return self._default_system_prompt()
