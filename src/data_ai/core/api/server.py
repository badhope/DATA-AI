"""
DATA-AI REST API Server

FastAPI 服务端，提供 OpenAI 兼容的 HTTP 接口
"""

import json
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from data_ai.core.agent.base import (
    AgentConfig,
    BaseAgent,
)
from data_ai.core.api.extensions import router as extensions_router
from data_ai.core.i18n import Locale, negotiate_locale, tr
from data_ai.core.llm.manager import ChatMessage, ChatResponse, LLMManager, get_llm_manager
from data_ai.core.tool.registry import ToolRegistry, get_tool_registry
from data_ai.utils.exceptions import (
    DataAIException,
    ToolExecutionError,
)
from data_ai.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("api.server")


# ============================================================================
# Pydantic Models - Request/Response Schemas
# ============================================================================


class ChatMessageModel(BaseModel):
    """聊天消息模型"""

    role: str = Field(..., description="消息角色: system, user, assistant, tool")
    content: str = Field(..., description="消息内容")
    name: str | None = Field(None, description="工具名称（工具消息时）")
    tool_calls: list[dict] | None = Field(None, description="工具调用")
    tool_call_id: str | None = Field(None, description="工具调用ID")


class ChatCompletionRequest(BaseModel):
    """聊天补全请求"""

    model: str = Field(..., description="模型名称，如 'gpt-4', 'claude-3' 等")
    messages: list[ChatMessageModel] = Field(..., description="消息列表")
    temperature: float | None = Field(0.7, ge=0, le=2, description="采样温度")
    max_tokens: int | None = Field(None, ge=1, description="最大生成token数")
    top_p: float | None = Field(1.0, ge=0, le=1, description="核采样概率")
    stream: bool | None = Field(False, description="是否流式输出")
    tools: list[dict] | None = Field(None, description="可用工具定义")
    tool_choice: str | dict | None = Field("auto", description="工具选择策略")
    user: str | None = Field(None, description="用户标识")

    # DATA-AI 特有参数
    agent_mode: str | None = Field("tool_call", description="Agent模式: react 或 tool_call")
    enable_tools: bool | None = Field(True, description="是否启用工具")
    tool_names: list[str] | None = Field(None, description="指定可用工具列表")
    # 企业角色预设:P0-3 — 让请求者直接套客服/财务/秘书/小说 4 套预置 Agent
    # 设为 None / 未知值 时不生效,等价于通用 Agent
    role: str | None = Field(
        None, description="企业角色预设: customer_service | finance_analyst | secretary | novel_writer"
    )


class ChatCompletionChoice(BaseModel):
    """聊天补全选择"""

    index: int = Field(..., description="选择索引")
    message: ChatMessageModel = Field(..., description="消息")
    finish_reason: str | None = Field(None, description="结束原因")


class ChatCompletionResponse(BaseModel):
    """聊天补全响应"""

    id: str = Field(..., description="响应ID")
    object: str = Field("chat.completion", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: list[ChatCompletionChoice] = Field(..., description="选择列表")
    usage: dict[str, int] = Field(default_factory=dict, description="token使用量")
    # Agent 扩展(透传 OpenAI 客户端,前端可读)
    agent_trace: dict[str, Any] | None = Field(
        default=None, description="Agent 执行 trace: iterations/tool_calls/reflections"
    )
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="工具调用历史(平铺)")
    reflections: list[dict[str, Any]] = Field(default_factory=list, description="Self-Reflection 历史(平铺)")

    model_config = {"extra": "allow"}


class ChatCompletionStreamChoice(BaseModel):
    """流式聊天补全选择"""

    index: int = Field(..., description="选择索引")
    delta: dict[str, Any] = Field(..., description="增量内容")
    finish_reason: str | None = Field(None, description="结束原因")


class ChatCompletionStreamResponse(BaseModel):
    """流式聊天补全响应"""

    id: str = Field(..., description="响应ID")
    object: str = Field("chat.completion.chunk", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    model: str = Field(..., description="模型名称")
    choices: list[ChatCompletionStreamChoice] = Field(..., description="选择列表")


class CompletionRequest(BaseModel):
    """纯文本补全请求"""

    model: str = Field(..., description="模型名称")
    prompt: str | list[str] = Field(..., description="提示文本")
    temperature: float | None = Field(0.7, ge=0, le=2)
    max_tokens: int | None = Field(None, ge=1)
    top_p: float | None = Field(1.0, ge=0, le=1)
    stream: bool | None = Field(False)
    suffix: str | None = Field(None, description="后缀文本")
    user: str | None = Field(None)


class CompletionChoice(BaseModel):
    """补全选择"""

    index: int
    text: str
    finish_reason: str | None = None
    logprobs: dict | None = None


class CompletionResponse(BaseModel):
    """补全响应"""

    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: list[CompletionChoice]
    usage: dict[str, int] = Field(default_factory=dict)


class ModelInfo(BaseModel):
    """模型信息"""

    id: str = Field(..., description="模型ID")
    object: str = Field("model", description="对象类型")
    created: int = Field(..., description="创建时间戳")
    owned_by: str = Field("data-ai", description="所有者")
    permission: list[dict] = Field(default_factory=list)
    root: str | None = None
    parent: str | None = None


class ModelsResponse(BaseModel):
    """模型列表响应"""

    object: str = Field("list", description="对象类型")
    data: list[ModelInfo] = Field(..., description="模型列表")


class ToolInfo(BaseModel):
    """工具信息"""

    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    category: str | None = Field(None, description="工具分类")
    parameters: dict[str, Any] = Field(default_factory=dict, description="参数定义")


class ToolsResponse(BaseModel):
    """工具列表响应"""

    object: str = Field("list", description="对象类型")
    data: list[ToolInfo] = Field(..., description="工具列表")


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""

    tool: str = Field(..., description="工具名称")
    parameters: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolExecuteResponse(BaseModel):
    """工具执行响应"""

    success: bool = Field(..., description="是否成功")
    result: Any = Field(None, description="执行结果")
    error: str | None = Field(None, description="错误信息")
    execution_time_ms: float = Field(0.0, description="执行时间（毫秒）")


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="状态: healthy / degraded / unhealthy")
    version: str = Field(..., description="版本")
    timestamp: int = Field(..., description="时间戳")
    components: dict[str, str] = Field(default_factory=dict, description="组件状态")
    checks: dict[str, dict] = Field(
        default_factory=dict,
        description="每个子项的详细检查 (P1-7: 用于主动修补环境)",
    )
    uptime_ms: int | None = Field(default=None, description="运行时长(毫秒)")
    fixes: list[str] = Field(
        default_factory=list,
        description="如果 status != healthy,这里给出修复建议",
    )
    trace_id: str | None = Field(default=None, description="本次检查的 trace_id")


class ErrorResponse(BaseModel):
    """错误响应"""

    error: dict[str, Any] = Field(..., description="错误信息")


# ============================================================================
# API Key 认证
# ============================================================================


async def verify_api_key(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None),
) -> str:
    """re-export auth.verify_api_key_header 以兼容旧 import。"""
    from data_ai.core.api.auth import verify_api_key_header as _impl

    return await _impl(authorization=authorization, x_api_key=x_api_key)


# ============================================================================
# 辅助函数：构建 Agent
# ============================================================================


def _attach_agent_trace(
    response: ChatCompletionResponse,
    *,
    tool_calls: list[dict[str, Any]] | None = None,
    reflections: list[dict[str, Any]] | None = None,
    iterations: int = 0,
) -> ChatCompletionResponse:
    """
    把 Agent 内部的工具调用 + 自反思 附加到 ChatCompletionResponse 上,
    以扩展字段(OpenAI 兼容,但保留 trace 透明度)。
    """
    payload = response.model_dump()
    payload["agent_trace"] = {
        "iterations": iterations,
        "tool_calls": tool_calls or [],
        "reflections": reflections or [],
    }
    # 兼容直接 .tool_calls/.reflections 字段访问
    payload["tool_calls"] = tool_calls or []
    payload["reflections"] = reflections or []
    # 重新构造(保留 id/created/model/choices/usage)
    return ChatCompletionResponse.model_validate(payload)


def _build_agent(
    model_name: str,
    tool_registry: ToolRegistry,
    llm_manager: LLMManager,
    system_prompt: str = "",
    preset: dict[str, Any] | None = None,
) -> BaseAgent:
    """
    构建 BaseAgent 实例

    新版 BaseAgent 接受 AgentConfig / LLMManager / ToolRegistry。
    不再使用 create_agent() 工厂函数。

    ``system_prompt`` 用于注入 locale 指令等全局系统消息。
    ``preset`` 来自 REGISTERED_PRESETS(role),会覆盖:
      - system_prompt (preset 的 system_prompt)
      - tool 白名单 (preset['tools'])
      - temperature / max_iterations
      - enable_reflection
    """
    if preset:
        # preset 优先级最高,完全覆盖请求方的 system_prompt
        system_prompt = str(preset.get("system_prompt") or system_prompt)
        temperature = float(preset.get("temperature", 0.7))
        max_iterations = int(preset.get("max_iterations", 10))
        enable_reflection = bool(preset.get("reflection", False))
        preset_role = preset.get("role", "preset")
        preset_name = preset.get("name", preset_role)
    else:
        temperature = 0.7
        max_iterations = 10
        enable_reflection = False
        preset_role = None
        preset_name = None

    config = AgentConfig(
        model_name=model_name,
        system_prompt=system_prompt,
        temperature=temperature,
        max_iterations=max_iterations,
        enable_reflection=enable_reflection,
        stream=True,
    )
    agent = BaseAgent(
        config=config,
        llm_manager=llm_manager,
        tool_registry=tool_registry,
    )
    # 透传 preset 元信息(供 observability / log 读取)
    if preset_role:
        agent.state.metadata["preset_role"] = preset_role
    if preset_name:
        agent.state.metadata["preset_name"] = preset_name
    return agent


def _resolve_preset(role: str | None) -> dict[str, Any] | None:
    """
    把请求方的 role 字符串解析为 REGISTERED_PRESETS 里的 dict。
    失败(模块未注册 / role 未知)统一返回 None,调用方应当视为"不套预设"。
    """
    if not role:
        return None
    try:
        from data_ai.plugins.agents import get_preset

        return get_preset(role)
    except Exception as exc:  # pragma: no cover - 容错
        logger.warning(f"preset 解析失败 role={role!r} err={exc!r}")
        return None


# ============================================================================
# FastAPI 应用
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    import time as _t

    app.state.start_time = _t.time()  # P1-7: 启动时间用于 uptime 计算
    logger.info("API server starting up...")

    app.state.llm_manager = get_llm_manager()
    app.state.tool_registry = get_tool_registry()

    # 如果没有手动注册任何模型，则注入默认的离线模型占位，
    # 确保 /v1/chat/completions、Agent、Team 都能真实响应（而不是 500）。
    from data_ai.core.llm.manager import (
        LLMManager as _LLMManager,
    )
    from data_ai.core.llm.manager import (
        ModelConfig,
        ModelProvider,
    )

    llm_mgr: _LLMManager = app.state.llm_manager

    # ── 1. 自动从环境变量注册国际 + 国内 LLM（如果用户配了对应 API key）──
    _ENV_PROVIDER_MAP: list = [
        # (env_var,                  model_id,                          provider,                model_name)
        ("OPENAI_API_KEY", "openai-gpt-4o-mini", ModelProvider.OPENAI, "gpt-4o-mini"),
        ("ANTHROPIC_API_KEY", "anthropic-claude-3-5-sonnet", ModelProvider.ANTHROPIC, "claude-3-5-sonnet-20241022"),
        ("DEEPSEEK_API_KEY", "deepseek-chat", ModelProvider.DEEPSEEK, "deepseek-chat"),
        ("SILICONFLOW_API_KEY", "siliconflow-deepseek", ModelProvider.SILICONFLOW, "deepseek-ai/DeepSeek-V2.5"),
        ("QWEN_API_KEY", "qwen-plus", ModelProvider.QWEN, "qwen-plus"),
        # P0-5: DASHSCOPE 一次注入 3 个常用 qwen 模型(同 key,不同 model_id)
        ("DASHSCOPE_API_KEY", "qwen-turbo", ModelProvider.QWEN, "qwen-turbo"),
        ("DASHSCOPE_API_KEY", "qwen-plus-2025", ModelProvider.QWEN, "qwen-plus-2025-01-25"),
        ("DASHSCOPE_API_KEY", "qwen-max-2025", ModelProvider.QWEN, "qwen-max-2025-01-25"),
        # P1-5: 阿里百炼 200+ 模型池 — 同 key 多 model_id,按需注册
        # 主力 (强能力)
        ("DASHSCOPE_API_KEY", "qwen-max", ModelProvider.QWEN, "qwen-max"),
        ("DASHSCOPE_API_KEY", "qwen-max-latest", ModelProvider.QWEN, "qwen-max-latest"),
        ("DASHSCOPE_API_KEY", "qwen-plus", ModelProvider.QWEN, "qwen-plus"),
        ("DASHSCOPE_API_KEY", "qwen-plus-latest", ModelProvider.QWEN, "qwen-plus-latest"),
        # 速度优先
        ("DASHSCOPE_API_KEY", "qwen-turbo-latest", ModelProvider.QWEN, "qwen-turbo-latest"),
        # 长上下文 (1M tokens)
        ("DASHSCOPE_API_KEY", "qwen-long", ModelProvider.QWEN, "qwen-long"),
        # 编程专用
        ("DASHSCOPE_API_KEY", "qwen-coder-plus", ModelProvider.QWEN, "qwen-coder-plus"),
        ("DASHSCOPE_API_KEY", "qwen-coder-plus-latest", ModelProvider.QWEN, "qwen-coder-plus-latest"),
        ("DASHSCOPE_API_KEY", "qwen-coder-turbo", ModelProvider.QWEN, "qwen-coder-turbo"),
        # Qwen 2.5 开源尺寸 (按需选)
        ("DASHSCOPE_API_KEY", "qwen2.5-72b-instruct", ModelProvider.QWEN, "qwen2.5-72b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen2.5-32b-instruct", ModelProvider.QWEN, "qwen2.5-32b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen2.5-14b-instruct", ModelProvider.QWEN, "qwen2.5-14b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen2.5-7b-instruct", ModelProvider.QWEN, "qwen2.5-7b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen2.5-3b-instruct", ModelProvider.QWEN, "qwen2.5-3b-instruct"),
        # Coder 系列
        ("DASHSCOPE_API_KEY", "qwen2.5-coder-32b-instruct", ModelProvider.QWEN, "qwen2.5-coder-32b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen2.5-coder-14b-instruct", ModelProvider.QWEN, "qwen2.5-coder-14b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen2.5-coder-7b-instruct", ModelProvider.QWEN, "qwen2.5-coder-7b-instruct"),
        # 数学
        ("DASHSCOPE_API_KEY", "qwen2.5-math-72b-instruct", ModelProvider.QWEN, "qwen2.5-math-72b-instruct"),
        # 视觉 (multi-modal)
        ("DASHSCOPE_API_KEY", "qwen-vl-max", ModelProvider.QWEN, "qwen-vl-max"),
        ("DASHSCOPE_API_KEY", "qwen-vl-plus", ModelProvider.QWEN, "qwen-vl-plus"),
        # 翻译
        ("DASHSCOPE_API_KEY", "qwen-mt-plus", ModelProvider.QWEN, "qwen-mt-plus"),
        # 文本向量化 (embedding)
        ("DASHSCOPE_API_KEY", "text-embedding-v3", ModelProvider.QWEN, "text-embedding-v3"),
        # 老一代 (1.5 系列, 仍可用)
        ("DASHSCOPE_API_KEY", "qwen1.5-110b-chat", ModelProvider.QWEN, "qwen1.5-110b-chat"),
        ("DASHSCOPE_API_KEY", "qwen1.5-72b-chat", ModelProvider.QWEN, "qwen1.5-72b-chat"),
        ("DASHSCOPE_API_KEY", "qwen1.5-32b-chat", ModelProvider.QWEN, "qwen1.5-32b-chat"),
        ("DASHSCOPE_API_KEY", "qwen1.5-14b-chat", ModelProvider.QWEN, "qwen1.5-14b-chat"),
        ("DASHSCOPE_API_KEY", "qwen1.5-7b-chat", ModelProvider.QWEN, "qwen1.5-7b-chat"),
        # P1-6: Qwen3 系列 (2025 新一代, 强能力/多尺寸, 需 enable_thinking=false)
        ("DASHSCOPE_API_KEY", "qwen3-max", ModelProvider.QWEN, "qwen3-max"),
        ("DASHSCOPE_API_KEY", "qwen3-max-preview", ModelProvider.QWEN, "qwen3-max-preview"),
        ("DASHSCOPE_API_KEY", "qwen3-235b-a22b", ModelProvider.QWEN, "qwen3-235b-a22b"),
        ("DASHSCOPE_API_KEY", "qwen3-32b", ModelProvider.QWEN, "qwen3-32b"),
        ("DASHSCOPE_API_KEY", "qwen3-30b-a3b", ModelProvider.QWEN, "qwen3-30b-a3b"),
        ("DASHSCOPE_API_KEY", "qwen3-14b", ModelProvider.QWEN, "qwen3-14b"),
        ("DASHSCOPE_API_KEY", "qwen3-8b", ModelProvider.QWEN, "qwen3-8b"),
        # Qwen3 思考强化版 (默认 thinking, 可强制 false)
        ("DASHSCOPE_API_KEY", "qwen3-235b-a22b-instruct-2507", ModelProvider.QWEN, "qwen3-235b-a22b-instruct-2507"),
        ("DASHSCOPE_API_KEY", "qwen3-30b-a3b-instruct-2507", ModelProvider.QWEN, "qwen3-30b-a3b-instruct-2507"),
        ("DASHSCOPE_API_KEY", "qwen3-next-80b-a3b-instruct", ModelProvider.QWEN, "qwen3-next-80b-a3b-instruct"),
        # Qwen3 Coder (编程, 480B MoE 大杯)
        ("DASHSCOPE_API_KEY", "qwen3-coder-flash", ModelProvider.QWEN, "qwen3-coder-flash"),
        ("DASHSCOPE_API_KEY", "qwen3-coder-480b-a35b-instruct", ModelProvider.QWEN, "qwen3-coder-480b-a35b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen3-coder-30b-a3b-instruct", ModelProvider.QWEN, "qwen3-coder-30b-a3b-instruct"),
        # Qwen3 VL (视觉多模态, 多尺寸)
        ("DASHSCOPE_API_KEY", "qwen3-vl-plus", ModelProvider.QWEN, "qwen3-vl-plus"),
        ("DASHSCOPE_API_KEY", "qwen3-vl-flash", ModelProvider.QWEN, "qwen3-vl-flash"),
        ("DASHSCOPE_API_KEY", "qwen3-vl-32b-thinking", ModelProvider.QWEN, "qwen3-vl-32b-thinking"),
        ("DASHSCOPE_API_KEY", "qwen3-vl-32b-instruct", ModelProvider.QWEN, "qwen3-vl-32b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen3-vl-235b-a22b-instruct", ModelProvider.QWEN, "qwen3-vl-235b-a22b-instruct"),
        ("DASHSCOPE_API_KEY", "qwen3-vl-235b-a22b-thinking", ModelProvider.QWEN, "qwen3-vl-235b-a22b-thinking"),
        # Qwen 视觉推理 (qvq) - 边看图边思考
        ("DASHSCOPE_API_KEY", "qvq-plus", ModelProvider.QWEN, "qvq-plus"),
        # Qwen Omni (多模态端到端, 音视频图文)
        ("DASHSCOPE_API_KEY", "qwen-omni-turbo", ModelProvider.QWEN, "qwen-omni-turbo"),
        ("DASHSCOPE_API_KEY", "qwen-omni-turbo-latest", ModelProvider.QWEN, "qwen-omni-turbo-latest"),
        # Qwen Flash (高速, Flash Attention)
        ("DASHSCOPE_API_KEY", "qwen-flash", ModelProvider.QWEN, "qwen-flash"),
        # Qwen Doc Turbo (长文档处理)
        ("DASHSCOPE_API_KEY", "qwen-doc-turbo", ModelProvider.QWEN, "qwen-doc-turbo"),
        # 第三方 (DeepSeek 满血版, 百炼托管)
        ("DASHSCOPE_API_KEY", "deepseek-v3", ModelProvider.QWEN, "deepseek-v3"),
        ("DASHSCOPE_API_KEY", "deepseek-v3.1", ModelProvider.QWEN, "deepseek-v3.1"),
        ("DASHSCOPE_API_KEY", "deepseek-r1", ModelProvider.QWEN, "deepseek-r1"),
        # DeepSeek R1 蒸馏版 (轻量)
        ("DASHSCOPE_API_KEY", "deepseek-r1-distill-qwen-32b", ModelProvider.QWEN, "deepseek-r1-distill-qwen-32b"),
        ("DASHSCOPE_API_KEY", "deepseek-r1-distill-qwen-14b", ModelProvider.QWEN, "deepseek-r1-distill-qwen-14b"),
        ("DASHSCOPE_API_KEY", "deepseek-r1-distill-qwen-7b", ModelProvider.QWEN, "deepseek-r1-distill-qwen-7b"),
        ("DASHSCOPE_API_KEY", "deepseek-r1-distill-qwen-1.5b", ModelProvider.QWEN, "deepseek-r1-distill-qwen-1.5b"),
        ("DASHSCOPE_API_KEY", "deepseek-r1-distill-llama-8b", ModelProvider.QWEN, "deepseek-r1-distill-llama-8b"),
        # Qwen3.5/3.6/3.7 (2026 最新代, 思考模式默认开)
        ("DASHSCOPE_API_KEY", "qwen3.7-max", ModelProvider.QWEN, "qwen3.7-max"),
        ("DASHSCOPE_API_KEY", "qwen3.6-plus", ModelProvider.QWEN, "qwen3.6-plus"),
        ("DASHSCOPE_API_KEY", "qwen3.6-flash", ModelProvider.QWEN, "qwen3.6-flash"),
        ("DASHSCOPE_API_KEY", "qwen3.6-27b", ModelProvider.QWEN, "qwen3.6-27b"),
        ("DASHSCOPE_API_KEY", "qwen3.6-35b-a3b", ModelProvider.QWEN, "qwen3.6-35b-a3b"),
        ("DASHSCOPE_API_KEY", "qwen3.5-flash", ModelProvider.QWEN, "qwen3.5-flash"),
        ("DASHSCOPE_API_KEY", "qwen3.5-plus", ModelProvider.QWEN, "qwen3.5-plus"),
        ("DASHSCOPE_API_KEY", "qwen3.5-27b", ModelProvider.QWEN, "qwen3.5-27b"),
        ("DASHSCOPE_API_KEY", "qwen3.5-35b-a3b", ModelProvider.QWEN, "qwen3.5-35b-a3b"),
        ("DASHSCOPE_API_KEY", "qwen3.5-122b-a10b", ModelProvider.QWEN, "qwen3.5-122b-a10b"),
        ("DASHSCOPE_API_KEY", "qwen3.5-397b-a17b", ModelProvider.QWEN, "qwen3.5-397b-a17b"),
        # Qwen3.5 Omni (多模态端到端 Flash)
        ("DASHSCOPE_API_KEY", "qwen3.5-omni-flash", ModelProvider.QWEN, "qwen3.5-omni-flash"),
        # Qwen3 Omni Flash
        ("DASHSCOPE_API_KEY", "qwen3-omni-flash", ModelProvider.QWEN, "qwen3-omni-flash"),
        # DeepSeek v4 / v3.2 (新代)
        ("DASHSCOPE_API_KEY", "deepseek-v4-flash", ModelProvider.QWEN, "deepseek-v4-flash"),
        ("DASHSCOPE_API_KEY", "deepseek-v4-pro", ModelProvider.QWEN, "deepseek-v4-pro"),
        ("DASHSCOPE_API_KEY", "deepseek-v3.2", ModelProvider.QWEN, "deepseek-v3.2"),
        # Qwen 数学
        ("DASHSCOPE_API_KEY", "qwen-math-plus", ModelProvider.QWEN, "qwen-math-plus"),
        ("DASHSCOPE_API_KEY", "qwen-math-plus-latest", ModelProvider.QWEN, "qwen-math-plus-latest"),
        ("DASHSCOPE_API_KEY", "qwen-math-turbo", ModelProvider.QWEN, "qwen-math-turbo"),
        # Qwen 翻译 (MT) 系列
        ("DASHSCOPE_API_KEY", "qwen-mt-turbo", ModelProvider.QWEN, "qwen-mt-turbo"),
        ("DASHSCOPE_API_KEY", "qwen-mt-flash", ModelProvider.QWEN, "qwen-mt-flash"),
        ("DASHSCOPE_API_KEY", "qwen-mt-lite", ModelProvider.QWEN, "qwen-mt-lite"),
        # Qwen 长上下文变种
        ("DASHSCOPE_API_KEY", "qwen-max-longcontext", ModelProvider.QWEN, "qwen-max-longcontext"),
        # 编程老代
        ("DASHSCOPE_API_KEY", "qwen-coder-plus-1106", ModelProvider.QWEN, "qwen-coder-plus-1106"),
        ("DASHSCOPE_API_KEY", "codeqwen1.5-7b-chat", ModelProvider.QWEN, "codeqwen1.5-7b-chat"),
        # 其它 provider
        ("ZHIPU_API_KEY", "zhipu-glm-4-flash", ModelProvider.ZHIPU, "glm-4-flash"),
        ("GLM_API_KEY", "zhipu-glm-4-air", ModelProvider.ZHIPU, "glm-4-air"),
        ("MOONSHOT_API_KEY", "moonshot-v1-32k", ModelProvider.MOONSHOT, "moonshot-v1-32k"),
        ("YI_API_KEY", "yi-medium", ModelProvider.YI, "yi-medium"),
        ("BAICHUAN_API_KEY", "baichuan4", ModelProvider.BAICHUAN, "Baichuan4"),
        ("DOUBAO_API_KEY", "doubao-lite-32k", ModelProvider.DOUBAO, "doubao-lite-32k"),
        ("STEPFUN_API_KEY", "step-1-flash", ModelProvider.STEPFUN, "step-1-flash"),
    ]
    # P1-6: 部分模型需要额外参数(比如 qwen3 思考模型需 enable_thinking=false)
    _MODEL_EXTRA_PARAMS: dict[str, dict] = {
        "qwen3-32b": {"enable_thinking": False},
        "qwen3-30b-a3b": {"enable_thinking": False},
        "qwen3-14b": {"enable_thinking": False},
        "qwen3-8b": {"enable_thinking": False},
        "qwen3-next-80b-a3b-instruct": {"enable_thinking": False},
        "qwen3-235b-a22b-instruct-2507": {"enable_thinking": False},
        "qwen3-30b-a3b-instruct-2507": {"enable_thinking": False},
        "qwen3-vl-32b-instruct": {"enable_thinking": False},
        "qwen3-vl-235b-a22b-instruct": {"enable_thinking": False},
        # qwen3.5/3.6/3.7 思考模式默认开
        "qwen3.7-max": {"enable_thinking": False},
        "qwen3.6-plus": {"enable_thinking": False},
        "qwen3.6-flash": {"enable_thinking": False},
        "qwen3.6-27b": {"enable_thinking": False},
        "qwen3.6-35b-a3b": {"enable_thinking": False},
        "qwen3.5-flash": {"enable_thinking": False},
        "qwen3.5-plus": {"enable_thinking": False},
        "qwen3.5-27b": {"enable_thinking": False},
        "qwen3.5-35b-a3b": {"enable_thinking": False},
        "qwen3.5-122b-a10b": {"enable_thinking": False},
        "qwen3.5-397b-a17b": {"enable_thinking": False},
    }
    for env_var, model_id, provider, model_name in _ENV_PROVIDER_MAP:
        api_key = os.getenv(env_var)
        if not api_key or model_id in llm_mgr._configs:
            continue
        try:
            llm_mgr.register_model(
                model_id,
                ModelConfig(
                    provider=provider,
                    model_name=model_name,
                    api_key=api_key,
                    extra_params=_MODEL_EXTRA_PARAMS.get(model_id, {}),
                ),
            )
            logger.info(f"Auto-registered model from {env_var}: {model_id}")
        except Exception as e:
            logger.error(f"Failed to register {model_id} from {env_var}: {e}")

    # ── 2. 如果还是没注册任何模型，注入离线占位 ───────────────────
    if not llm_mgr._configs:
        try:
            llm_mgr.register_model(
                "offline-chat",
                ModelConfig(
                    provider=ModelProvider.OFFLINE,
                    model_name="data-ai-offline",
                ),
                set_default=True,
            )
            llm_mgr.register_model(
                "offline-fast",
                ModelConfig(
                    provider=ModelProvider.OFFLINE,
                    model_name="data-ai-offline-fast",
                ),
            )
            llm_mgr.register_model(
                "offline-mini",
                ModelConfig(
                    provider=ModelProvider.OFFLINE,
                    model_name="data-ai-offline-mini",
                ),
            )
            logger.info("No external LLM configured, registered 3 offline placeholder models")
        except Exception as e:
            logger.error(f"Failed to register offline models: {e}")

    # 注册内置工具（包括 sandbox/system/office/document 等）
    try:
        from data_ai.core.tool.tools import register_builtin_tools

        register_builtin_tools()
    except Exception as e:
        logger.warning(f"register_builtin_tools failed: {e}")

    # 触发其他工具模块的模块级注册（office/document/system/browser/extended/planning/...)
    for mod_name in (
        "data_ai.core.tool.office",
        "data_ai.core.tool.document",
        "data_ai.core.tool.system",
        "data_ai.core.tool.browser",
        "data_ai.core.tool.extended",
        "data_ai.core.tool.planning",
        "data_ai.core.tool.orchestrator",
        "data_ai.core.tool.browser_session",
    ):
        try:
            __import__(mod_name)
        except Exception as e:
            logger.debug(f"optional tool module {mod_name} import skipped: {e}")

    # 显式注册办公文档工具（office 模块只暴露函数，需要主动调用 register_office_tools）
    try:
        from data_ai.core.tool.office import register_office_tools

        register_office_tools()
    except Exception as e:
        logger.debug(f"register_office_tools skipped: {e}")

    # P1-8 整改: 加载 builtin MCP servers + 把 in-process server 工具注册到 ToolRegistry
    try:
        import asyncio as _asyncio

        from data_ai.core.mcp import get_mcp_registry, load_builtin_servers
        from data_ai.core.mcp.client import get_in_process_server

        mcp_reg = get_mcp_registry()
        app.state.mcp_registry = mcp_reg
        load_builtin_servers(mcp_reg)

        # 把 in-process MCP server 的工具同步到 ToolRegistry,LLM 可直接调用
        # 用同步包装跑 async handler,通过 _asyncio.run_coroutine_threadsafe 在新 loop 跑
        try:
            from data_ai.core.tool.registry import get_tool_registry as _gtr

            in_proc = get_in_process_server()
            tr = _gtr()

            def _make_sync_handler(_tn: str):
                def _handler(**kwargs):
                    coro = in_proc.call_tool(_tn, kwargs or {})
                    try:
                        loop = _asyncio.get_event_loop()
                        if loop.is_running():
                            # 在新线程跑,避免 nested loop 报错
                            import concurrent.futures as _cf

                            with _cf.ThreadPoolExecutor(max_workers=1) as ex:
                                fut = ex.submit(_asyncio.run, coro)
                                return fut.result(timeout=10)
                        else:
                            return loop.run_until_complete(coro)
                    except RuntimeError:
                        return _asyncio.run(coro)

                return _handler

            for tool in in_proc.list_tools():
                full_name = f"mcp__{tool['name']}"
                if full_name not in tr.list_tools():
                    tr.register(
                        name=full_name,
                        description=f"[MCP:内置] {tool['description']}",
                        parameters=tool["inputSchema"].get("properties", {}),
                        required=tool["inputSchema"].get("required", []),
                        function=_make_sync_handler(tool["name"]),
                        is_async=False,
                        category="mcp",
                    )
        except Exception as mcp_e:
            logger.debug(f"sync in-process MCP tools to ToolRegistry skipped: {mcp_e!r}")

        logger.info(f"MCP registry initialized with {len(mcp_reg.list_servers())} servers")
    except Exception as e:
        logger.warning(f"MCP init skipped: {e!r}")

    # P1-10: 启动定时任务调度器 (审计中间件必须在 app 实例化时安装,在 lifespan 前)
    try:
        from data_ai.core.scheduler import get_scheduler

        get_scheduler().start()
        logger.info("Enterprise governance: scheduler started (audit middleware installed at module load)")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Governance init skipped: {e!r}")

    logger.info(
        f"API server started successfully (tools: {app.state.tool_registry.get_tool_count()}, models: {len(llm_mgr._configs)})"
    )
    yield

    # 关闭调度器
    try:
        from data_ai.core.scheduler import get_scheduler

        get_scheduler().stop()
    except Exception:  # noqa: BLE001
        pass

    logger.info("API server shutting down...")


app = FastAPI(
    title="DATA-AI API",
    description="DATA-AI 的 REST API 服务，兼容 OpenAI API 格式",
    version="1.0.0",
    lifespan=lifespan,
)


def _cors_origins() -> list[str]:
    """从环境变量 ``DATA_AI_CORS_ORIGINS`` 读取允许的 origin（逗号分隔）。

    默认仅允许同源 (本服务自身 host) + 常见 dev 端口，生产部署时请显式配置。
    """
    import os

    raw = os.environ.get("DATA_AI_CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    # 默认：保守白名单（dev 友好）
    return [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5180",
        "http://127.0.0.1:5180",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# P1-10: 装上审计中间件 (必须 app 实例化后立即装,不能放到 lifespan)
try:
    from data_ai.core.audit import install_audit_middleware

    install_audit_middleware(app)
except Exception:  # noqa: BLE001
    pass


# ============================================================================
# P1-7: 全局错误处理 + trace_id
# ============================================================================


def _gen_trace_id() -> str:
    import uuid

    return uuid.uuid4().hex[:12]


def _classify_error(e: Exception) -> dict[str, Any]:
    """P1-7: 把异常分类,生成准确报错 + 修复建议"""
    err_str = str(e)
    err_type = type(e).__name__

    # 已知错误的精确分类
    if "401" in err_str or "Unauthorized" in err_str or "Invalid API key" in err_str:
        return {
            "category": "auth_error",
            "fix": "检查 API key 是否正确,或重新填入 DASHSCOPE_API_KEY",
            "user_message": "API key 无效或已过期",
        }
    if "429" in err_str or "rate limit" in err_str.lower() or "RateLimit" in err_type:
        return {
            "category": "rate_limit",
            "fix": "降低请求频率,或升级到付费 API key",
            "user_message": "API 调用频率超限,稍后重试",
        }
    if "404" in err_str and "model" in err_str.lower():
        return {
            "category": "model_not_found",
            "fix": "检查模型名是否拼写正确,当前可用模型: 87 个 (qwen3-32b / qwen-max / ...)",
            "user_message": "请求的模型不存在",
        }
    if "Connection" in err_type or "Timeout" in err_type or "Network" in err_type:
        return {
            "category": "network_error",
            "fix": "检查网络连接 / API base URL 是否可达",
            "user_message": "网络连接失败",
        }
    if "ImportError" in err_type or "ModuleNotFoundError" in err_type:
        return {
            "category": "missing_dependency",
            "fix": f"pip install 缺失的包: {err_str[:100]}",
            "user_message": "依赖缺失",
        }
    if "Tool" in err_type and "not found" in err_str.lower():
        return {
            "category": "tool_not_found",
            "fix": "检查工具名是否正确,或检查 office/sandbox 插件是否加载",
            "user_message": "工具不存在",
        }
    return {
        "category": "internal_error",
        "fix": "查看后端日志 (trace_id 关联)",
        "user_message": "服务器内部错误",
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """P1-7: HTTPException 标准化响应 — 带 trace_id + 修复建议"""
    trace_id = _gen_trace_id()
    classification = _classify_error(exc)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": classification["category"],
                "message": classification["user_message"],
                "detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "fix": classification["fix"],
                "trace_id": trace_id,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """P1-7: 兜底异常处理 — 不让 traceback 泄露给用户,但保留日志"""
    trace_id = _gen_trace_id()
    classification = _classify_error(exc)
    logger.error(
        f"[{trace_id}] Unhandled exception at {request.method} {request.url.path}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": classification["category"],
                "message": classification["user_message"],
                "detail": str(exc)[:500],
                "fix": classification["fix"],
                "trace_id": trace_id,
                "path": request.url.path,
                "method": request.method,
            }
        },
    )


# ============================================================================
# Locale middleware — 必须在 app 创建之后注册
# ============================================================================


def _resolve_locale(request: Request) -> Locale:
    """从 X-Locale 或 Accept-Language 解析 Locale。"""
    header = request.headers.get("x-locale")
    if header:
        from data_ai.core.i18n.catalog import _coerce_locale  # 局部 import

        return _coerce_locale(header)
    return negotiate_locale(request.headers.get("accept-language"))


@app.middleware("http")
async def locale_middleware(request: Request, call_next):
    """在每个请求进入路由前解析 locale，挂到 request.state 上。"""
    request.state.locale = _resolve_locale(request)
    return await call_next(request)


def t_req(request: Request, key: str, **kwargs: Any) -> str:
    """从 request 取 locale 并调用 :func:`tr`，在 endpoint 内翻译文案。"""
    locale = getattr(request.state, "locale", None) or Locale.EN
    return tr(key, locale, **kwargs)


def _build_locale_system_prompt(locale: Locale) -> str:
    """根据 locale 构造一条"用此语言回复"的 system 指令，注入到对话最前面。

    不会覆盖用户已有的 system 消息 —— 只会 prepend。
    """
    if locale == Locale.ZH:
        language_label = tr("agent.locale.language_zh", locale)
    else:
        language_label = tr("agent.locale.language_en", locale)
    return tr("agent.locale.system_prompt", locale, language=language_label)


# 挂载扩展端点（agents / teams / memory / rag / sandbox / office / skills / notifications）
app.include_router(extensions_router)


# ============================================================================
# 路由定义
# ============================================================================


# P1-7: uptime helper
def _get_uptime_ms() -> int | None:
    start = getattr(app.state, "start_time", None)
    if start is None:
        return None
    return int((time.time() - start) * 1000)


@app.get("/health", response_model=HealthResponse, tags=["系统"])
async def health_check():
    """
    P1-7 增强: 主动检查 + 修复建议 + trace_id

    与 /health/live /health/ready 的区别:
    - /health      完整深度检查 (默认,可缓存 5s)
    - /health/live 进程活着 (k8s liveness)
    - /health/ready 服务就绪 (k8s readiness,会主动 ping LLM)
    """
    import uuid

    trace_id = uuid.uuid4().hex[:12]
    checks: dict[str, dict] = {}
    components: dict[str, str] = {}
    fixes: list[str] = []

    # ── 1. LLM Manager ──
    try:
        llm_manager: LLMManager = app.state.llm_manager
        models = llm_manager.list_models() if hasattr(llm_manager, "list_models") else []
        default = llm_manager.get_default_model() if hasattr(llm_manager, "get_default_model") else None
        checks["llm_manager"] = {
            "ok": True,
            "model_count": len(models),
            "default_model": default,
            "first_5_models": models[:5],
        }
        components["llm_manager"] = "ok"
        if not models:
            checks["llm_manager"]["ok"] = False
            checks["llm_manager"]["error"] = "no models registered"
            components["llm_manager"] = "degraded"
            fixes.append("LLM Manager: 没有注册任何模型 — 设置 DASHSCOPE_API_KEY / OPENAI_API_KEY 环境变量后重启")
    except Exception as e:
        checks["llm_manager"] = {"ok": False, "error": str(e)[:200]}
        components["llm_manager"] = "error"
        fixes.append(f"LLM Manager 不可用: {str(e)[:120]}")

    # ── 2. Tool Registry ──
    try:
        tool_registry: ToolRegistry = app.state.tool_registry
        tool_count = len(tool_registry.list_tools()) if hasattr(tool_registry, "list_tools") else 0
        checks["tool_registry"] = {"ok": tool_count > 0, "tool_count": tool_count}
        components["tool_registry"] = "ok" if tool_count > 0 else "degraded"
        if tool_count == 0:
            fixes.append("Tool Registry: 没有注册任何工具 — 检查 office/sandbox 插件是否正常加载")
    except Exception as e:
        checks["tool_registry"] = {"ok": False, "error": str(e)[:200]}
        components["tool_registry"] = "error"
        fixes.append(f"Tool Registry 不可用: {str(e)[:120]}")

    # ── 3. 配置 & 环境 ──
    env_checks = {
        "DATA_AI_DEV_MODE": os.getenv("DATA_AI_DEV_MODE", "false"),
        "DASHSCOPE_API_KEY_set": bool(os.getenv("DASHSCOPE_API_KEY")),
        "OPENAI_API_KEY_set": bool(os.getenv("OPENAI_API_KEY")),
        "ANTHROPIC_API_KEY_set": bool(os.getenv("ANTHROPIC_API_KEY")),
        "DEEPSEEK_API_KEY_set": bool(os.getenv("DEEPSEEK_API_KEY")),
    }
    any_key = any(
        [
            env_checks["DASHSCOPE_API_KEY_set"],
            env_checks["OPENAI_API_KEY_set"],
            env_checks["ANTHROPIC_API_KEY_set"],
            env_checks["DEEPSEEK_API_KEY_set"],
        ]
    )
    checks["environment"] = {
        "ok": any_key,
        "details": env_checks,
    }
    components["environment"] = "ok" if any_key else "degraded"
    if not any_key:
        fixes.append("Environment: 没有任何 LLM API key — 设置 DASHSCOPE_API_KEY 等环境变量")

    # ── 4. 决定总体状态 ──
    failed = [k for k, v in checks.items() if not v.get("ok", True)]
    if not failed:
        status = "healthy"
    elif "llm_manager" in failed or "environment" in failed:
        status = "unhealthy"  # 关键依赖坏了
    else:
        status = "degraded"  # 非关键 (如部分工具缺失)

    return HealthResponse(
        status=status,
        version=getattr(__import__("data_ai"), "__version__", "unknown"),
        timestamp=int(time.time()),
        components=components,
        checks=checks,
        uptime_ms=_get_uptime_ms(),
        fixes=fixes,
        trace_id=trace_id,
    )


@app.get("/health/live", tags=["系统"])
async def health_live():
    """
    K8s liveness probe: 进程是否还活着
    永远返回 200,除非进程已死
    """
    return {"status": "alive", "timestamp": int(time.time())}


@app.get("/health/ready", tags=["系统"])
async def health_ready():
    """
    K1-7 K8s readiness probe: 服务是否就绪

    检查标准:
    - LLM Manager 可用
    - 至少注册了 1 个模型
    - 至少配置了 1 个 LLM API key

    200 = 就绪,可接流量
    503 = 未就绪,k8s 不应路由流量
    """
    import uuid

    trace_id = uuid.uuid4().hex[:12]
    try:
        llm_manager: LLMManager = app.state.llm_manager
        models = llm_manager.list_models() if hasattr(llm_manager, "list_models") else []
        any_key = bool(
            os.getenv("DASHSCOPE_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
        )
        if not models:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "no_models", "trace_id": trace_id},
            )
        if not any_key:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "reason": "no_api_key", "trace_id": trace_id},
            )
        return {"status": "ready", "model_count": len(models), "trace_id": trace_id}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "exception", "error": str(e)[:200], "trace_id": trace_id},
        )


@app.get("/v1/models", response_model=ModelsResponse, tags=["模型"])
async def list_models(
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    """列出可用模型"""
    llm_manager: LLMManager = app.state.llm_manager

    models = []
    for model_id, config in getattr(llm_manager, "_configs", {}).items():
        models.append(
            ModelInfo(
                id=model_id,
                created=int(time.time()),
                owned_by=config.provider.value if hasattr(config.provider, "value") else str(config.provider),
            )
        )

    if not models:
        raise HTTPException(
            status_code=503,
            detail=t_req(request, "api.chat.no_model"),
        )

    return ModelsResponse(data=models)


@app.get("/v1/tools", response_model=ToolsResponse, tags=["工具"])
async def list_tools(
    api_key: str = Depends(verify_api_key),
    category: str | None = None,
):
    """列出可用工具"""
    tool_registry: ToolRegistry = app.state.tool_registry

    tools = []
    for tool_name in tool_registry.list_tools():
        tool = tool_registry.get(tool_name)
        if tool:
            tool_category = getattr(tool, "category", None) or (tool.metadata or {}).get("category")
            if category and tool_category != category:
                continue

            schema = tool.to_openai_tool()
            function_def = schema.get("function", {}) if isinstance(schema, dict) else {}
            tools.append(
                ToolInfo(
                    name=tool_name,
                    description=tool.description or "",
                    category=tool_category,
                    parameters=function_def.get("parameters", {}),
                )
            )

    return ToolsResponse(data=tools)


@app.get("/v1/tools/{tool_name}", tags=["工具"])
async def get_tool_detail(
    tool_name: str,
    api_key: str = Depends(verify_api_key),
):
    """获取单个工具的详情（description / parameters / category）"""
    tool_registry: ToolRegistry = app.state.tool_registry
    if tool_name not in tool_registry.list_tools():
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    tool = tool_registry.get(tool_name)
    schema = tool.to_openai_tool()
    function_def = schema.get("function", {}) if isinstance(schema, dict) else {}
    return ToolInfo(
        name=tool_name,
        description=tool.description or "",
        category=getattr(tool, "category", None) or (tool.metadata or {}).get("category"),
        parameters=function_def.get("parameters", {}),
    )


@app.post("/v1/tools/execute", response_model=ToolExecuteResponse, tags=["工具"])
async def execute_tool(
    request: Request,
    tool_request: ToolExecuteRequest,
    api_key: str = Depends(verify_api_key),
):
    """执行指定工具"""
    tool_registry: ToolRegistry = app.state.tool_registry

    start_time = time.time()

    try:
        if (
            not tool_registry.has(tool_request.tool)
            if hasattr(tool_registry, "has")
            else tool_request.tool not in tool_registry.list_tools()
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=t_req(request, "api.error.tool_not_found", tool_name=tool_request.tool),
            )

        # 新版 ToolRegistry.execute(name, arguments) 直接返回结果（字符串）
        raw_result = await tool_registry.execute(
            tool_request.tool,
            tool_request.parameters,
        )

        execution_time_ms = (time.time() - start_time) * 1000

        # ToolResult 不再存在；用 dict 包装结果
        return ToolExecuteResponse(
            success=True,
            result=raw_result,
            error=None,
            execution_time_ms=execution_time_ms,
        )

    except HTTPException:
        raise
    except ToolExecutionError as e:
        execution_time_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Tool execution error: {e}",
            tool=tool_request.tool,
            details=e.details,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t_req(
                request,
                "api.tool.execution_failed",
                tool_name=tool_request.tool,
                reason=str(e),
            ),
        )
    except Exception as e:
        logger.error(f"Tool execution error: {e}", tool=tool_request.tool)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=t_req(
                request,
                "api.tool.execution_failed",
                tool_name=tool_request.tool,
                reason=str(e),
            ),
        )


@app.post("/v1/chat/completions", tags=["聊天"])
async def chat_completions(
    request: Request,
    payload: ChatCompletionRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    聊天补全

    OpenAI 兼容的聊天补全接口，支持流式和非流式输出
    """
    llm_manager: LLMManager = app.state.llm_manager
    tool_registry: ToolRegistry = app.state.tool_registry

    request_id = f"chatcmpl-{int(time.time() * 1000)}"

    # 提前校验 model 是否已注册（用户错误：4xx）——避免走到 LLM 抛 LLMConfigError 后被当成 5xx
    if payload.model and payload.model not in llm_manager._clients:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "message": f"Model not found: {payload.model}",
                    "type": "ModelNotFound",
                    "code": "model_not_found",
                    "model": payload.model,
                }
            },
        )

    # P1-10: 配额/限流判定
    from data_ai.core.quota import get_quota_manager

    actor = api_key[:12] if api_key else "anonymous"
    quota_mgr = get_quota_manager()
    rl = quota_mgr.check_rate_limit(actor)
    if not rl.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "message": f"Quota exceeded: {rl.reason}",
                    "type": "RateLimitExceeded",
                    "code": rl.reason,
                    "retry_after_sec": rl.retry_after,
                }
            },
            headers={"Retry-After": str(int(rl.retry_after))},
        )
    quota_mgr.acquire_concurrency(actor)

    # Locale → 注入到 system prompt，让 agent 按用户语言回复
    locale: Locale = getattr(request.state, "locale", None) or Locale.EN
    locale_instruction = _build_locale_system_prompt(locale)

    try:
        user_messages = [
            ChatMessage(
                role=msg.role,
                content=msg.content,
                name=msg.name,
                tool_calls=msg.tool_calls,
                tool_call_id=msg.tool_call_id,
            )
            for msg in payload.messages
        ]
        logger.info(
            f"[chat_completions] model={payload.model} stream={payload.stream} enable_tools={payload.enable_tools} payload_messages={len(payload.messages)}"
        )
        # Prepend locale 指令（如果用户没显式 system 消息）
        if not user_messages or user_messages[0].role != "system":
            messages = [ChatMessage(role="system", content=locale_instruction)] + user_messages
        else:
            # 已有 system：把 locale 指令拼到第一条 system 末尾
            sys0 = user_messages[0]
            sys0.content = f"{sys0.content}\n\n{locale_instruction}"
            messages = user_messages

        # 流式输出
        if payload.stream:

            async def stream_generator() -> AsyncGenerator[str, None]:
                """流式生成器"""
                first_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=payload.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={"role": "assistant"},
                        )
                    ],
                )
                yield f"data: {first_chunk.model_dump_json()}\n\n"

                if payload.enable_tools:
                    # 使用新版 BaseAgent + run_stream()
                    user_system = ""
                    for m in user_messages:
                        if m.role == "system" and m.content:
                            user_system = m.content
                            break
                    agent_system = (
                        f"{user_system}\n\n{locale_instruction}".strip() if user_system else locale_instruction
                    )
                    # P0-3: 用 role 解析 preset,并合并 system_prompt(preset 优先)
                    preset = _resolve_preset(payload.role)
                    if preset:
                        logger.info(
                            f"[chat_completions] role={payload.role} preset_name={preset.get('name')} tools={len(preset.get('tools', []))}"
                        )
                    agent = _build_agent(
                        model_name=payload.model,
                        tool_registry=tool_registry,
                        llm_manager=llm_manager,
                        system_prompt=agent_system,
                        preset=preset,
                    )

                    query = messages[-1].content if messages else ""

                    # run_stream() 返回 AsyncIterator[Dict]，type 取值为
                    # "thinking" / "token" / "tool_call" / "tool_result" / "finish" / "error"
                    async for chunk in agent.run_stream(query):
                        delta: dict[str, Any] = {}

                        chunk_type = chunk.get("type") if isinstance(chunk, dict) else getattr(chunk, "type", None)

                        if chunk_type == "token":
                            content = (
                                chunk.get("content", "") if isinstance(chunk, dict) else getattr(chunk, "content", "")
                            )
                            if content:
                                delta["content"] = content
                        elif chunk_type == "tool_call":
                            tool_name = (
                                chunk.get("tool_name", "")
                                if isinstance(chunk, dict)
                                else getattr(chunk, "tool_name", "")
                            )
                            arguments = (
                                chunk.get("arguments", {})
                                if isinstance(chunk, dict)
                                else getattr(chunk, "arguments", {})
                            )
                            delta["tool_calls"] = [
                                {
                                    "index": 0,
                                    "id": f"call_{int(time.time() * 1000)}",
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": json.dumps(arguments)
                                        if not isinstance(arguments, str)
                                        else arguments,
                                    },
                                }
                            ]
                        elif chunk_type == "tool_result":
                            result_data = (
                                chunk.get("result", "") if isinstance(chunk, dict) else getattr(chunk, "result", "")
                            )
                            tool_name = (
                                chunk.get("tool_name", "")
                                if isinstance(chunk, dict)
                                else getattr(chunk, "tool_name", "")
                            )
                            delta["content"] = f"\n[Tool: {tool_name}]\n{result_data}\n"
                        elif chunk_type == "thinking":
                            continue
                        elif chunk_type == "error":
                            error_msg = (
                                chunk.get("error", "Unknown error")
                                if isinstance(chunk, dict)
                                else getattr(chunk, "error", "Unknown error")
                            )
                            delta["content"] = f"\n[Error: {error_msg}]"
                        elif chunk_type == "finish":
                            # P1-6: finish 事件的 content 是已累积的完整内容(已通过 token chunks 流过),
                            # 再发一次会导致前端显示重复。只发 finish_reason 标记
                            content = (
                                chunk.get("content", "") if isinstance(chunk, dict) else getattr(chunk, "content", "")
                            )
                            if content:
                                # 不设置 delta["content"],避免重复流式输出
                                delta["finish_reason"] = "stop"
                        else:
                            # 兜底：尝试读取 content
                            content = (
                                chunk.get("content", "") if isinstance(chunk, dict) else getattr(chunk, "content", "")
                            )
                            if content:
                                delta["content"] = content

                        if delta:
                            chunk_response = ChatCompletionStreamResponse(
                                id=request_id,
                                created=int(time.time()),
                                model=payload.model,
                                choices=[
                                    ChatCompletionStreamChoice(
                                        index=0,
                                        delta=delta,
                                    )
                                ],
                            )
                            yield f"data: {chunk_response.model_dump_json()}\n\n"
                else:
                    # 纯 LLM 流式输出
                    accumulated = ""
                    async for chunk in llm_manager.chat_stream(messages, model=payload.model):
                        content = getattr(chunk, "content", None) or ""
                        if not content:
                            continue
                        # P1-6: 去重 — Qwen3 末尾把全部内容再发一次
                        if accumulated:
                            if content == accumulated:
                                continue
                            if content.startswith(accumulated):
                                content = content[len(accumulated) :]
                                if not content:
                                    continue
                        accumulated += content

                        chunk_response = ChatCompletionStreamResponse(
                            id=request_id,
                            created=int(time.time()),
                            model=payload.model,
                            choices=[
                                ChatCompletionStreamChoice(
                                    index=0,
                                    delta={"content": content},
                                )
                            ],
                        )
                        yield f"data: {chunk_response.model_dump_json()}\n\n"

                final_chunk = ChatCompletionStreamResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=payload.model,
                    choices=[
                        ChatCompletionStreamChoice(
                            index=0,
                            delta={},
                            finish_reason="stop",
                        )
                    ],
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
            )

        # 非流式输出
        else:
            if payload.enable_tools:
                # 使用新版 BaseAgent + run()
                # 把 user 自己传的 system（如果有）和 locale_instruction 拼到 agent config
                user_system = ""
                for m in user_messages:
                    if m.role == "system" and m.content:
                        user_system = m.content
                        break
                agent_system = f"{user_system}\n\n{locale_instruction}".strip() if user_system else locale_instruction
                # P0-3: 用 role 解析 preset
                preset = _resolve_preset(payload.role)
                if preset:
                    logger.info(
                        f"[chat_completions] role={payload.role} preset_name={preset.get('name')} tools={len(preset.get('tools', []))}"
                    )
                agent = _build_agent(
                    model_name=payload.model,
                    tool_registry=tool_registry,
                    llm_manager=llm_manager,
                    system_prompt=agent_system,
                    preset=preset,
                )

                query = messages[-1].content if messages else ""
                # 关键修复：把整个对话历史传给 agent.run()，而不是只传最后一条 query。
                # 这样 LLM 在多轮 tool 调用中能"记住"前面对话（long-conversation memory）。
                # messages 第一条是 [system, locale_instruction]（如有），把 locale 提到 agent system 即可避免重复。
                history_for_agent = [m for m in messages if m.content and m.content != locale_instruction]
                # 去掉已合并到 agent_system 的 user system
                history_for_agent = [
                    m
                    for m in history_for_agent
                    if not (m.role == "system" and user_system and m.content == user_system)
                ]
                agent_response: dict[str, Any] = await agent.run(query, initial_messages=history_for_agent)

                # 把工具调用 + 自反思 暴露到 response
                resp = ChatCompletionResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=payload.model,
                    choices=[
                        ChatCompletionChoice(
                            index=0,
                            message=ChatMessageModel(
                                role="assistant",
                                content=agent_response.get("content", ""),
                            ),
                            finish_reason=agent_response.get("finish_reason") or "stop",
                        )
                    ],
                    usage=agent_response.get("usage", {}),
                )
                return _attach_agent_trace(
                    resp,
                    tool_calls=agent_response.get("tool_calls", []),
                    reflections=agent_response.get("reflections", []),
                    iterations=agent_response.get("iterations", 0),
                )
            else:
                response: ChatResponse = await llm_manager.chat(
                    messages,
                    model=payload.model,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                    top_p=payload.top_p,
                )

                return ChatCompletionResponse(
                    id=request_id,
                    created=int(time.time()),
                    model=payload.model,
                    choices=[
                        ChatCompletionChoice(
                            index=0,
                            message=ChatMessageModel(
                                role="assistant",
                                content=response.content,
                            ),
                            finish_reason="stop",
                        )
                    ],
                    usage=response.usage,
                )

            # P1-10: 记录 token 用量 + 触发 webhooks
            try:
                from data_ai.core.webhooks import get_webhook_dispatcher

                usage = response.usage or {}
                pt = usage.get("prompt_tokens", 0)
                ct = usage.get("completion_tokens", 0)
                quota_mgr.record_usage(
                    actor=actor,
                    model=payload.model,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    endpoint="/v1/chat/completions",
                )
                get_webhook_dispatcher().dispatch_sync(
                    "agent.run.completed",
                    {
                        "actor": actor,
                        "model": payload.model,
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "cost_usd": quota_mgr.usage_summary(actor=actor)["cost_usd"],
                    },
                )
            except Exception as e:  # noqa: BLE001
                logger.debug(f"usage tracking skipped: {e}")
            finally:
                quota_mgr.release_concurrency(actor)

    except DataAIException as e:
        logger.error(f"Chat completion error: {e}", error_code=e.code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": str(e),
                    "type": type(e).__name__,
                    "code": e.code.value if hasattr(e.code, "value") else str(e.code),
                }
            },
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "message": str(e),
                    "type": "internal_error",
                    "code": "500",
                }
            },
        )


@app.post("/v1/completions", response_model=CompletionResponse, tags=["补全"])
async def completions(
    request: CompletionRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    纯文本补全

    传统的文本补全接口
    """
    llm_manager: LLMManager = app.state.llm_manager

    request_id = f"cmpl-{int(time.time() * 1000)}"

    try:
        if isinstance(request.prompt, list):
            prompt = "\n".join(request.prompt)
        else:
            prompt = request.prompt

        messages = [ChatMessage(role="user", content=prompt)]

        if request.stream:

            async def stream_generator() -> AsyncGenerator[str, None]:
                full_text = ""
                async for chunk in llm_manager.chat_stream(messages, model=request.model):
                    content = getattr(chunk, "content", None) or ""
                    full_text += content

                    chunk_response = {
                        "id": request_id,
                        "object": "text_completion",
                        "created": int(time.time()),
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "text": content,
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk_response)}\n\n"

                final_response = {
                    "id": request_id,
                    "object": "text_completion",
                    "created": int(time.time()),
                    "model": request.model,
                    "choices": [
                        {
                            "index": 0,
                            "text": "",
                            "finish_reason": "stop",
                        }
                    ],
                }
                yield f"data: {json.dumps(final_response)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                stream_generator(),
                media_type="text/event-stream",
            )
        else:
            response: ChatResponse = await llm_manager.chat(
                messages,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                top_p=request.top_p,
            )

            return CompletionResponse(
                id=request_id,
                created=int(time.time()),
                model=request.model,
                choices=[
                    CompletionChoice(
                        index=0,
                        text=response.content,
                        finish_reason="stop",
                    )
                ],
                usage=response.usage,
            )

    except Exception as e:
        logger.error(f"Completion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


# ============================================================================
# 错误处理
# ============================================================================


@app.exception_handler(DataAIException)
async def dataai_exception_handler(request: Request, exc: DataAIException):
    """DATA-AI 异常处理 — 返回 JSONResponse，不要直接 return Pydantic model。

    直接 return Pydantic model 会让 FastAPI 在内部当作 ASGI callable 调用，
    触发 ``'ErrorResponse' object is not callable``，表现为 500 Internal
    Server Error 而非预期的 4xx。
    """
    return JSONResponse(
        status_code=exc.status_code if hasattr(exc, "status_code") else 400,
        content={
            "error": {
                "message": str(exc),
                "type": type(exc).__name__,
                "code": exc.code.value if hasattr(exc.code, "value") else str(exc.code),
            }
        },
    )


# ============================================================================
# 启动函数
# ============================================================================


def create_server() -> FastAPI:
    """创建服务器实例（用于测试）"""
    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
):
    """
    运行 API 服务器

    Args:
        host: 监听地址
        port: 监听端口
        reload: 是否热重载（开发模式）
        log_level: 日志级别
    """
    # 记录启动时间，让 /v1/extensions/health 能算出 uptime
    import os as _os
    import time as _time

    import uvicorn

    _os.environ["_DATA_AI_STARTED_AT"] = str(_time.time())

    uvicorn.run(
        "data_ai.core.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    run_server()
