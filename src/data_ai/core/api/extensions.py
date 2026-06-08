"""
DATA-AI API 扩展端点

为 server.py 提供所有缺失的模块端点：
- Agents: list / get / create / update / delete / run / runs
- Teams: list / get / create / update / delete / run / messages
- Memory: list / search / create / update / delete
- RAG: docs / upload / delete / search / detail / chunks
- Sandbox: list / create / delete / execute / files / snapshots
- Office: word / ppt / excel / pdf 全部操作
- Skills: list / execute / create / save / extract
- Notifications: list / mark-read
- Sessions: history

存储策略: 进程内 ThreadSafe 字典 + lock。
运行时调用 data_ai 现有模块（sandbox / agent / tool registry）。
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, model_validator

from data_ai.core.i18n import Locale, tr
from data_ai.utils.logging import get_logger

logger = get_logger("api.extensions")


def t_req(request, key: str, **kwargs) -> str:
    """从 request.state.locale 翻译，与 server.py 的 t_req 行为一致。"""
    locale = getattr(request.state, "locale", None) or Locale.EN
    return tr(key, locale, **kwargs)


# ============================================================================
# 线程安全的进程内存储
# ============================================================================


class _Store:
    """线程安全的内存存储"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.agents: dict[str, dict[str, Any]] = {}
        self.teams: dict[str, dict[str, Any]] = {}
        self.memories: dict[str, dict[str, Any]] = {}
        self.rag_docs: dict[str, dict[str, Any]] = {}
        self.rag_chunks: dict[str, list[dict[str, Any]]] = {}
        self.sandboxes: dict[str, dict[str, Any]] = {}
        self.sandbox_snapshots: dict[str, list[dict[str, Any]]] = {}
        self.skills: dict[str, dict[str, Any]] = {}
        self.notifications: list[dict[str, Any]] = []
        self.sessions: dict[str, dict[str, Any]] = {}
        self.agent_runs: dict[str, list[dict[str, Any]]] = {}
        self.team_runs: dict[str, list[dict[str, Any]]] = {}
        self.team_messages: dict[str, list[dict[str, Any]]] = {}
        self.sandbox_files: dict[str, dict[str, Any]] = {}

    def lock(self):
        return self._lock


STORE = _Store()


# ============================================================================
# Pydantic schemas
# ============================================================================

# ---------- Agent ----------


class AgentCreatePayload(BaseModel):
    name: str
    description: str | None = ""
    model: str
    system_prompt: str = ""
    tool_names: list[str] = Field(default_factory=list)
    max_iterations: int = 10
    temperature: float = 0.7
    enable_reflection: bool = False
    # P0-3: 创建时套用预置角色(可选)。会覆盖 system_prompt/tool_names/temperature/max_iterations/enable_reflection
    preset: str | None = None


class AgentUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    tool_names: list[str] | None = None
    max_iterations: int | None = None
    temperature: float | None = None
    enable_reflection: bool | None = None
    # P0-3: update 也支持切到 preset(把整张配置替换为预置)
    preset: str | None = None


class AgentRunPayload(BaseModel):
    input: str
    session_id: str | None = None


class AgentDelegateManyPayload(BaseModel):
    """P1-7: 委派多个 sub-agent"""
    queries: list[dict[str, Any]] = Field(..., description="每个 sub-task: {query, role?, run_id?}")
    model: str | None = Field(default=None, description="统一模型 (缺省 qwen-turbo)")


# ---------- Team ----------


class TeamMemberPayload(BaseModel):
    id: str | None = None
    name: str
    role: str
    agent_id: str | None = None
    weight: float = 1.0


class TeamCreatePayload(BaseModel):
    name: str
    description: str | None = ""
    mode: str = "collaboration"
    consensus_method: str = "llm_synthesis"
    members: list[TeamMemberPayload] = Field(default_factory=list)


class TeamRunPayload(BaseModel):
    input: str
    consensus_method: str | None = None


# ---------- Memory ----------


class MemoryCreatePayload(BaseModel):
    type: str = Field(..., alias="type", description="记忆类型")
    memory_type: str | None = Field(
        None,
        alias="memory_type",
        description="兼容别名 — 旧版本前端用此名，deprecated，请改用 type",
    )
    content: str
    importance: float = 0.5
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False
    metadata: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _compat_memory_type(cls, data: Any) -> Any:
        """兼容前端旧字段名 ``memory_type``，统一映射到 ``type``。"""
        if isinstance(data, dict) and "type" not in data and "memory_type" in data:
            data = {**data, "type": data["memory_type"]}
        return data


class MemoryUpdatePayload(BaseModel):
    content: str | None = None
    importance: float | None = None
    tags: list[str] | None = None
    pinned: bool | None = None
    type: str | None = None


class MemorySearchPayload(BaseModel):
    query: str
    type: str | None = None
    top_k: int = 5


# ---------- RAG ----------


class RagSearchPayload(BaseModel):
    query: str
    top_k: int = 5
    embedder: str | None = None
    document_ids: list[str] | None = None


# ---------- Sandbox ----------


class SandboxCreatePayload(BaseModel):
    name: str
    type: str = "local"
    timeout: int = 30
    memory: int = 512
    cpu: int = 50
    network: bool = True
    image: str | None = None


class SandboxExecutePayload(BaseModel):
    language: str
    code: str
    timeout: int = 30
    stdin: str | None = None
    env: dict[str, str] | None = None


class FileSavePayload(BaseModel):
    path: str
    content: str


class SnapshotCreatePayload(BaseModel):
    name: str
    description: str | None = ""


# ---------- Office ----------


class WordReadPayload(BaseModel):
    file_path: str
    extract_tables: bool = True
    extract_images: bool = False


class WordWritePayload(BaseModel):
    file_path: str
    content: str
    title: str = ""
    author: str = ""
    format: str = "text"


class WordEditPayload(BaseModel):
    file_path: str
    operation: str  # replace | append_paragraph | add_heading | add_table
    find: str | None = None
    replace: str | None = None
    text: str | None = None
    level: int | None = None
    table: list[list[str]] | None = None


class WordTemplatePayload(BaseModel):
    template_path: str
    data: dict[str, Any]
    output_path: str


class PptReadPayload(BaseModel):
    file_path: str


class PptWritePayload(BaseModel):
    file_path: str
    title: str = ""
    slides: list[dict[str, Any]] = Field(default_factory=list)


class ExcelReadPayload(BaseModel):
    file_path: str
    sheet_name: str | None = None


class ExcelAnalyzePayload(BaseModel):
    file_path: str
    analysis_type: str = "summary"  # summary | stats | correlation


class ExcelChartPayload(BaseModel):
    file_path: str
    chart_type: str  # bar | line | pie | scatter
    sheet_name: str | None = None
    data_range: str = ""
    output_path: str | None = None


class PdfReadPayload(BaseModel):
    file_path: str


class PdfMergePayload(BaseModel):
    file_paths: list[str]
    output_path: str


class PdfSplitPayload(BaseModel):
    file_path: str
    ranges: str  # "1-3, 5, 7-10"
    output_dir: str


# ---------- Skills ----------


class SkillCreatePayload(BaseModel):
    name: str | None = None
    description: str = ""
    version: str = "0.1.0"
    tags: list[str] = Field(default_factory=list)
    category: str = "custom"
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    yaml: str | None = None
    implementation: str | None = None


class SkillExecutePayload(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


class SkillExtractPayload(BaseModel):
    source: str
    source_type: str = "text"  # text | file | url


# ---------- MCP ----------

class MCPServerCreatePayload(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    type: str = "stdio"  # stdio | sse | http
    command: str = ""
    args: list[str] = Field(default_factory=list)
    url: str = ""
    env: dict[str, str] = Field(default_factory=dict)
    icon: str = "🔌"
    enabled: bool = True


class MCPServerUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    command: str | None = None
    args: list[str] | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    enabled: bool | None = None
    icon: str | None = None


class MCPInvokePayload(BaseModel):
    server_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout: float = 30.0


# ---------- Notifications ----------


class NotificationMarkPayload(BaseModel):
    ids: list[str] | None = None
    all_read: bool = False


# ============================================================================
# 路由器
# ============================================================================

from data_ai.core.api.auth import verify_api_key_header as verify_api_key  # noqa: E402

router = APIRouter(dependencies=[Depends(verify_api_key)])


def _now_ms() -> int:
    return int(time.time() * 1000)


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _parse_ranges(ranges: str) -> list[int]:
    """解析 "1-3, 5, 7-10" 这样的页码字符串为页码列表"""
    pages: list[int] = []
    for part in ranges.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                a, b = part.split("-", 1)
                a, b = int(a.strip()), int(b.strip())
                pages.extend(range(min(a, b), max(a, b) + 1))
            except ValueError:
                continue
        else:
            try:
                pages.append(int(part))
            except ValueError:
                continue
    return sorted(set(pages))


def _notify(level: str, title: str, description: str = "", link: str | None = None, category: str = "system") -> None:
    """写入一条通知（线程安全）"""
    n = {
        "id": _gen_id("ntf"),
        "level": level,
        "title": title,
        "description": description,
        "ts": _now_ms(),
        "read": False,
        "link": link,
        "category": category,
    }
    with STORE.lock():
        STORE.notifications.insert(0, n)
        # 限制最多保留 200 条
        if len(STORE.notifications) > 200:
            STORE.notifications = STORE.notifications[:200]


@router.get("/v1/llm/providers", tags=["LLM"])
async def list_llm_providers():
    """
    列出所有 LLM provider + 注册状态。

    P0-5 整改:把 LLMManager 支持的 14+ 个 provider 暴露到 HTTP,
    让前端/SDK 知道当前环境配了几个 key、每个 provider 默认 base_url 是什么。
    """
    # 已注册的模型(provider 实际连过的)
    from data_ai.core.api.server import app as _server_app
    from data_ai.core.llm.manager import (
        PROVIDER_DEFAULT_BASE_URL,
        LLMManager,
        ModelProvider,
    )
    llm_mgr: LLMManager = _server_app.state.llm_manager
    registered = {
        m_id: {
            "provider": cfg.provider.value,
            "model_name": cfg.model_name,
            "base_url": cfg.base_url,
        }
        for m_id, cfg in getattr(llm_mgr, "_configs", {}).items()
    }

    # 全部支持的 provider
    all_providers = []
    env_key_map = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "aws": "AWS_ACCESS_KEY_ID",
        "deepseek": "DEEPSEEK_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",  # qwen 复用 dashscope
        "zhipu": "ZHIPU_API_KEY",
        "moonshot": "MOONSHOT_API_KEY",
        "yi": "YI_API_KEY",
        "baichuan": "BAICHUAN_API_KEY",
        "doubao": "DOUBAO_API_KEY",
        "stepfun": "STEPFUN_API_KEY",
    }
    import os as _os

    for prov in ModelProvider:
        key_name = env_key_map.get(prov.value)
        has_key = bool(_os.getenv(key_name)) if key_name else None
        all_providers.append(
            {
                "provider": prov.value,
                "default_base_url": PROVIDER_DEFAULT_BASE_URL.get(prov.value),
                "env_var": key_name,
                "env_key_set": has_key,
                "client_class": getattr(llm_mgr, "_client_map", {}).get(prov).__name__
                if hasattr(llm_mgr, "_client_map")
                else None,
            }
        )

    return {
        "object": "list",
        "registered_models": registered,
        "registered_count": len(registered),
        "providers": all_providers,
        "total_providers": len(all_providers),
        "hint": "设置 provider 对应 env var(如 DASHSCOPE_API_KEY / OPENAI_API_KEY)即可自动注册并真连",
    }


@router.post("/v1/llm/health", tags=["LLM"])
async def llm_health(payload: dict | None = None):
    """
    真连 LLM provider 发最小请求,验证可用性。

    P0-5 整改:用户改了 key 想测是否生效,不必发完整对话,
    这个端点用 1 token 的"ping"消息快速验证连通性。

    Request body:
        {"model": "qwen-turbo"}        # 测已注册模型
        {"model": "openai-gpt-4o-mini"} # 测未注册模型(走注册流程)
    """
    payload = payload or {}
    target_model = payload.get("model")
    if not target_model:
        raise HTTPException(status_code=400, detail="model required")

    from data_ai.core.api.server import app as _server_app
    from data_ai.core.llm.manager import (
        LLMManager,
        ModelConfig,
        ModelProvider,
    )

    llm_mgr: LLMManager = _server_app.state.llm_manager

    # 如果 model 未注册,尝试根据 model id 推断 provider 注册
    if target_model not in llm_mgr._clients:
        _INFER_MAP = {
            "openai": (ModelProvider.OPENAI, "gpt-4o-mini", "OPENAI_API_KEY"),
            "anthropic": (ModelProvider.ANTHROPIC, "claude-3-5-sonnet-20241022", "ANTHROPIC_API_KEY"),
            "deepseek": (ModelProvider.DEEPSEEK, "deepseek-chat", "DEEPSEEK_API_KEY"),
            "qwen": (ModelProvider.QWEN, "qwen-plus-2025-01-25", "DASHSCOPE_API_KEY"),
            "zhipu": (ModelProvider.ZHIPU, "glm-4-flash", "ZHIPU_API_KEY"),
            "moonshot": (ModelProvider.MOONSHOT, "moonshot-v1-32k", "MOONSHOT_API_KEY"),
            "yi": (ModelProvider.YI, "yi-medium", "YI_API_KEY"),
            "baichuan": (ModelProvider.BAICHUAN, "Baichuan4", "BAICHUAN_API_KEY"),
            "doubao": (ModelProvider.DOUBAO, "doubao-lite-32k", "DOUBAO_API_KEY"),
            "stepfun": (ModelProvider.STEPFUN, "step-1-flash", "STEPFUN_API_KEY"),
            "siliconflow": (
                ModelProvider.SILICONFLOW,
                "deepseek-ai/DeepSeek-V2.5",
                "SILICONFLOW_API_KEY",
            ),
        }
        import os as _os

        for prefix, (provider, default_model, env_var) in _INFER_MAP.items():
            if target_model.startswith(prefix):
                api_key = _os.getenv(env_var)
                if not api_key:
                    return {
                        "ok": False,
                        "model": target_model,
                        "reason": f"{env_var} 未设置,无法注册 provider {provider.value}",
                    }
                try:
                    llm_mgr.register_model(
                        target_model,
                        ModelConfig(
                            provider=provider,
                            model_name=default_model,
                            api_key=api_key,
                        ),
                    )
                except Exception as exc:
                    return {
                        "ok": False,
                        "model": target_model,
                        "reason": f"注册失败: {exc!r}",
                    }
                break
        else:
            return {
                "ok": False,
                "model": target_model,
                "reason": f"未知模型前缀: {target_model}",
            }

    # 发 1 token 最小请求
    try:
        from data_ai.core.llm.manager import ChatMessage

        client = llm_mgr.get_client(target_model)
        # 用带前缀避免冲突
        ping_msg = "ping"  # 1 token 短消息
        resp = await client.chat(
            messages=[ChatMessage(role="user", content=ping_msg)],
            max_tokens=8,
            temperature=0.0,
        )
        return {
            "ok": True,
            "model": target_model,
            "provider": client.config.provider.value,
            "base_url": client.config.base_url,
            "response_chars": len(resp.content or ""),
            "usage": dict(resp.usage or {}),
            "content_preview": (resp.content or "")[:60],
        }
    except Exception as exc:
        return {
            "ok": False,
            "model": target_model,
            "reason": f"{type(exc).__name__}: {exc}",
        }


# ============================================================================
# P1-1 / P1-2: Agent Checkpoint + Human-in-the-Loop HTTP 端点
# ============================================================================


@router.get("/v1/agents/runs", tags=["Agent"])
async def list_all_agent_runs(request: Request, status: str | None = None, limit: int = 50):
    """
    列出所有 Agent 运行记录(checkpoint)。

    P1-1 整改:让前端能看到所有 run 状态(running/awaiting_approval/finished/error),
    支持前端"任务列表"和"恢复哪个"功能。
    """
    try:
        from data_ai.core.agent.checkpoint import get_checkpoint_store
        store = get_checkpoint_store()
        runs = await store.list_runs(status=status, limit=limit)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"checkpoint 不可用: {exc!r}")
    return {
        "object": "list",
        "data": [
            {
                "run_id": r.run_id,
                "status": r.status,
                "iteration_count": r.iteration_count,
                "reflection_count": r.reflection_count,
                "tool_call_count": len(r.tool_call_log),
                "has_pending_approval": r.pending_approval is not None,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "error": r.error,
            }
            for r in runs
        ],
        "total": len(runs),
        "hint": "POST /v1/agents/runs/{run_id}/resume 从断点继续; "
        "如果 has_pending_approval=true,先调 /v1/agents/runs/{run_id}/approve",
    }


@router.get("/v1/agents/runs/{run_id}", tags=["Agent"])
async def get_agent_run(request: Request, run_id: str):
    """
    查单个 Agent run 详情。
    """
    try:
        from data_ai.core.agent.checkpoint import get_checkpoint_store
        store = get_checkpoint_store()
        ck = await store.load(run_id)
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"checkpoint 不可用: {exc!r}")
    if ck is None:
        raise HTTPException(status_code=404, detail=f"run_id={run_id} not found")
    return {
        "object": "checkpoint",
        **ck.to_dict(),
    }


@router.post("/v1/agents/runs/{run_id}/resume", tags=["Agent"])
async def resume_agent_run(request: Request, run_id: str):
    """
    恢复一个已 paused 的 Agent run。

    P1-1 + P1-2 配合:
    - 普通 resume: body={}  从最近 checkpoint 继续
    - 审批后 resume: body={"approved": true/false, "reason": "..."}  继续 + 解锁 pending_approval
    """
    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}

    # 审批相关: 调本端点时如果 run 在 awaiting_approval,body 里的 approved/reason 会被转发
    approval = None
    if "approved" in body:
        approval = {
            "approved": body.get("approved"),
            "reason": body.get("reason") or ("approved" if body.get("approved") else "no reason"),
        }

    try:
        # 找原 agent 没法做(没存 instance),所以用 transient agent + resume
        from data_ai.core.agent.base import BaseAgent
        from data_ai.core.agent.checkpoint import get_checkpoint_store

        store = get_checkpoint_store()
        ck = await store.load(run_id)
        if ck is None:
            raise HTTPException(status_code=404, detail=f"run_id={run_id} not found")

        # 用 saved metadata 重建 agent(如果存在)
        meta = ck.metadata or {}
        _model_name = meta.get("model_name") or "qwen-turbo"
        agent = BaseAgent(
            checkpoint_store=store,
        )
        # 注入 saved run_id
        agent.run_id = run_id

        # 如果只是查 pending_approval(不 resume),返回等待详情
        if approval is None and ck.status == "awaiting_approval":
            return {
                "object": "pending_approval",
                "run_id": run_id,
                "pending_approval": ck.pending_approval,
                "hint": "POST {approved: true/false, reason: '...'} 来审批",
            }

        result = await agent.resume(run_id, approval=approval)
        return {
            "object": "agent_run_result",
            "resumed": True,
            **result,
        }
    except HTTPException:
        raise
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:  # pragma: no cover
        logger.error(f"resume_agent_run 失败: run_id={run_id} err={exc!r}")
        raise HTTPException(status_code=500, detail=f"resume 失败: {exc!r}")


@router.post("/v1/agents/runs/{run_id}/approve", tags=["Agent"])
async def approve_agent_run(request: Request, run_id: str):
    """
    P1-2 端点: 同意 Agent 的 pending 工具调用,自动续跑。
    body: {"reason": "ok"}  (可选)
    """
    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    from data_ai.core.agent.base import BaseAgent
    from data_ai.core.agent.checkpoint import get_checkpoint_store

    store = get_checkpoint_store()
    ck = await store.load(run_id)
    if ck is None:
        raise HTTPException(status_code=404, detail=f"run_id={run_id} not found")
    if ck.status != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"run_id={run_id} 状态={ck.status},非 awaiting_approval,无需审批",
        )

    agent = BaseAgent(checkpoint_store=store)
    agent.run_id = run_id
    agent.approve(body.get("reason", "approved by reviewer"))
    # 等主循环真正完成(让它跑完审批后的剩余步骤)
    try:
        result = await agent.resume(
            run_id,
            approval={"approved": True, "reason": body.get("reason", "ok")},
        )
    except Exception as exc:
        logger.error(f"approve resume 失败: {exc!r}")
        raise HTTPException(status_code=500, detail=f"resume 失败: {exc!r}")
    return {"object": "approved_resumed", "run_id": run_id, **result}


@router.post("/v1/agents/runs/{run_id}/reject", tags=["Agent"])
async def reject_agent_run(request: Request, run_id: str):
    """
    P1-2 端点: 拒绝 Agent 的 pending 工具调用,继续跑(reject 原因写回 tool message)。
    body: {"reason": "危险操作,禁止"}  (必填或可选)
    """
    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}

    from data_ai.core.agent.base import BaseAgent
    from data_ai.core.agent.checkpoint import get_checkpoint_store

    store = get_checkpoint_store()
    ck = await store.load(run_id)
    if ck is None:
        raise HTTPException(status_code=404, detail=f"run_id={run_id} not found")
    if ck.status != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"run_id={run_id} 状态={ck.status},非 awaiting_approval,无需审批",
        )

    agent = BaseAgent(checkpoint_store=store)
    agent.run_id = run_id
    reason = body.get("reason") or "rejected by reviewer"
    agent.reject(reason)
    try:
        result = await agent.resume(
            run_id,
            approval={"approved": False, "reason": reason},
        )
    except Exception as exc:
        logger.error(f"reject resume 失败: {exc!r}")
        raise HTTPException(status_code=500, detail=f"resume 失败: {exc!r}")
    return {"object": "rejected_resumed", "run_id": run_id, "rejected_reason": reason, **result}


# ── P1-3: Sub-Agent 端点 ──────────────────────────────────────


@router.get("/v1/agents/runs/{run_id}/sub_runs", tags=["Agent"])
async def list_sub_runs(request: Request, run_id: str):
    """
    P1-3 端点: 列出某个 run 派生出的所有 sub-agent run。

    实现: 扫所有 checkpoint,过滤 metadata.parent_run_id == run_id 的。
    """
    from data_ai.core.agent.checkpoint import get_checkpoint_store

    store = get_checkpoint_store()
    # 列所有 (limit 大一点确保能扫到 sub-runs)
    all_cks = await store.list_runs(limit=500)
    sub_runs: list[dict[str, Any]] = []
    for ck in all_cks:
        parent = (ck.metadata or {}).get("parent_run_id")
        if parent == run_id:
            sub_runs.append({
                "run_id": ck.run_id,
                "status": ck.status,
                "preset_role": (ck.metadata or {}).get("preset_role"),
                "created_at": ck.created_at,
                "updated_at": ck.updated_at,
                "iterations": ck.iteration_count,
                "has_error": bool(ck.error),
            })
    # 按 created_at 升序(子任务先后顺序)
    sub_runs.sort(key=lambda r: r["created_at"])
    return {
        "object": "list",
        "parent_run_id": run_id,
        "data": sub_runs,
        "total": len(sub_runs),
    }


@router.get("/v1/agents/runs/{run_id}/await_approval", tags=["Agent"])
async def await_approval_long_poll(request: Request, run_id: str, timeout: float = 30.0):
    """
    P1-2 补充: 长轮询 (long-polling) 端点,等审批触发时立刻返回。

    适用场景: 前端订阅式 UI(WebSocket 替代),不用每秒轮 GET 一次。

    行为:
    - 立即查 pending_approval → 有就返回
    - 没有 → 最多等 timeout 秒,期间每 0.5s 查一次
    - 超时 → 返回 {pending: false, status: <current>, hint: "no pending approval"}
    - 状态变 finished/error → 返回 {finished: true, status: <current>}

    timeout 上限 60s(防止长连接占满)。
    """
    timeout = min(float(timeout), 60.0)
    if timeout < 0.5:
        timeout = 0.5

    from data_ai.core.agent.checkpoint import get_checkpoint_store

    store = get_checkpoint_store()
    poll_interval = 0.5
    elapsed = 0.0

    while elapsed < timeout:
        ck = await store.load(run_id)
        if ck is None:
            raise HTTPException(status_code=404, detail=f"run_id={run_id} not found")

        # 1) 有 pending approval → 立即返回
        if ck.status == "awaiting_approval" and ck.pending_approval:
            return {
                "object": "await_approval",
                "pending": True,
                "run_id": run_id,
                "status": ck.status,
                "pending_approval": ck.pending_approval,
                "elapsed_s": elapsed,
            }

        # 2) 已终态 → 返回
        if ck.status in ("finished", "error"):
            return {
                "object": "finished",
                "finished": True,
                "run_id": run_id,
                "status": ck.status,
                "elapsed_s": elapsed,
                "final_content_preview": (ck.final_content or "")[:500] if ck.final_content else None,
            }

        # 3) 还在 running/thinking → 等
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    # 4) 超时
    ck = await store.load(run_id)
    return {
        "object": "timeout",
        "pending": False,
        "run_id": run_id,
        "status": ck.status if ck else "unknown",
        "elapsed_s": elapsed,
        "hint": f"Long-polling timed out after {timeout}s. Use ?timeout=60 to wait longer, or poll /v1/agents/runs/{run_id} manually.",
    }


@router.get("/v1/agents/runs/{run_id}/tree", tags=["Agent"])
async def get_run_tree(request: Request, run_id: str, max_depth: int = 5):
    """
    P1-3 端点: 递归查 run tree (parent ↔ sub-runs),用于前端可视化 agent 调用图。
    max_depth 默认 5,防极深递归。
    """
    from data_ai.core.agent.checkpoint import get_checkpoint_store

    store = get_checkpoint_store()
    all_cks = await store.list_runs(limit=500)
    by_run_id: dict[str, Any] = {ck.run_id: ck for ck in all_cks}
    children_map: dict[str, list[str]] = {}
    for ck in all_cks:
        parent = (ck.metadata or {}).get("parent_run_id")
        if parent:
            children_map.setdefault(parent, []).append(ck.run_id)

    def _build_node(rid: str, depth: int) -> dict[str, Any]:
        ck = by_run_id.get(rid)
        if ck is None:
            return {"run_id": rid, "status": "unknown", "children": []}
        node = {
            "run_id": rid,
            "status": ck.status,
            "preset_role": (ck.metadata or {}).get("preset_role"),
            "iterations": ck.iteration_count,
            "children": [],
        }
        if depth < max_depth:
            for child_id in children_map.get(rid, []):
                node["children"].append(_build_node(child_id, depth + 1))
        return node

    if run_id not in by_run_id:
        raise HTTPException(status_code=404, detail=f"run_id={run_id} not found")
    return {
        "object": "tree",
        "root": _build_node(run_id, 0),
    }


# ============================================================================
# Agent 端点
# ============================================================================


def _list_presets() -> list[dict[str, Any]]:
    """返回 4 个企业 Agent 预设的简要元信息。"""
    try:
        from data_ai.plugins.agents import list_presets
        items = list_presets()
        # list_presets() 内部已经返回 {role, name, description, tools_count}
        # 这里补一层 max_iterations / temperature / reflection / tools 摘要
        try:
            from data_ai.plugins.agents import REGISTERED_PRESETS
            for item in items:
                p = REGISTERED_PRESETS.get(item["role"])
                if p:
                    item["max_iterations"] = p.get("max_iterations")
                    item["temperature"] = p.get("temperature")
                    item["reflection"] = bool(p.get("reflection", False))
                    item["tools"] = list(p.get("tools", []))
                    item["default_namespace"] = p.get("default_namespace")
        except Exception as exc:  # pragma: no cover
            logger.warning(f"补全 preset 元信息失败: {exc!r}")
        return items
    except Exception as exc:  # pragma: no cover - 容错
        logger.error(f"加载 presets 失败: {exc!r}")
        return []


@router.get("/v1/agents/presets", tags=["Agent"])
async def list_agent_presets(request: Request):
    """
    列出全部企业 Agent 预设(读 REGISTERED_PRESETS)。

    P0-3 整改:把 plugins/agents 下的 4 套预置 agent 暴露到 HTTP,
    让前端/SDK 可以直接挑选客服/财务/秘书/小说 4 种角色,而不必手工
    把 system_prompt / tool 列表 / temperature 复制到请求体里。
    """
    presets = _list_presets()
    return {
        "object": "list",
        "data": presets,
        "total": len(presets),
        "hint": "把任一 preset['role'] 传到 /v1/chat/completions 的 role 字段即可套用预设",
    }


@router.get("/v1/agents/presets/{role}", tags=["Agent"])
async def get_agent_preset(request: Request, role: str):
    """
    按 role 获取单个 Agent 预设的完整定义。
    """
    try:
        from data_ai.plugins.agents import get_preset

        preset = get_preset(role)
    except Exception as exc:  # pragma: no cover
        logger.error(f"加载 preset 失败 role={role!r} err={exc!r}")
        preset = None
    if not preset:
        raise HTTPException(
            status_code=404,
            detail=t_req(request, "api.error.preset_not_found", role=role),
        )
    return {
        "object": "preset",
        "role": preset.get("role"),
        "name": preset.get("name"),
        "description": preset.get("description"),
        "system_prompt": preset.get("system_prompt"),
        "tools": preset.get("tools", []),
        "max_iterations": preset.get("max_iterations"),
        "temperature": preset.get("temperature"),
        "reflection": bool(preset.get("reflection", False)),
        "default_namespace": preset.get("default_namespace"),
        "default_context_names": preset.get("default_context_names", []),
        "user_facing_traits": preset.get("user_facing_traits", []),
    }


@router.get("/v1/agents")
async def list_agents(
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = 0,
):
    with STORE.lock():
        items = list(STORE.agents.values())
    if q:
        ql = q.lower()
        items = [a for a in items if ql in a["name"].lower() or ql in (a.get("description") or "").lower()]
    items.sort(key=lambda a: a["created_at"], reverse=True)
    return {"object": "list", "data": items[offset : offset + limit], "total": len(items)}


@router.post("/v1/agents", status_code=201)
async def create_agent(payload: AgentCreatePayload):
    # P0-3: preset 套预设
    if payload.preset:
        try:
            from data_ai.plugins.agents import get_preset
            preset_def = get_preset(payload.preset)
        except Exception as exc:  # pragma: no cover
            logger.error(f"create_agent: preset 解析失败 err={exc!r}")
            preset_def = None
        if not preset_def:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown preset role: {payload.preset}",
            )
        # preset 覆盖显式字段(允许用户传 preset 即可完成全部配置)
        payload_dict = payload.model_dump()
        payload_dict["system_prompt"] = preset_def.get("system_prompt", payload.system_prompt)
        payload_dict["tool_names"] = list(preset_def.get("tools", payload.tool_names))
        payload_dict["max_iterations"] = int(preset_def.get("max_iterations", payload.max_iterations))
        payload_dict["temperature"] = float(preset_def.get("temperature", payload.temperature))
        payload_dict["enable_reflection"] = bool(preset_def.get("reflection", payload.enable_reflection))
        agent = {
            "id": _gen_id("agent"),
            "name": payload.name,
            "description": payload.description or "",
            "model": payload.model,
            **payload_dict,
            "preset": payload.preset,
            "status": "idle",
            "created_at": _now_ms(),
            "updated_at": _now_ms(),
        }
        _notify("info", "智能体已创建(套用 preset)", f"{payload.name} ({payload.preset})", category="agent")
    else:
        agent = {
            "id": _gen_id("agent"),
            "name": payload.name,
            "description": payload.description or "",
            "model": payload.model,
            "system_prompt": payload.system_prompt,
            "tool_names": payload.tool_names,
            "max_iterations": payload.max_iterations,
            "temperature": payload.temperature,
            "enable_reflection": payload.enable_reflection,
            "status": "idle",
            "created_at": _now_ms(),
            "updated_at": _now_ms(),
        }
        _notify("info", "智能体已创建", payload.name, category="agent")
    with STORE.lock():
        STORE.agents[agent["id"]] = agent
        STORE.agent_runs[agent["id"]] = []
    return agent


@router.get("/v1/agents/{agent_id}")
async def get_agent(request: Request, agent_id: str):
    with STORE.lock():
        agent = STORE.agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=t_req(request, "api.error.agent_not_found", agent_id=agent_id))
    return agent


@router.patch("/v1/agents/{agent_id}")
async def update_agent(request: Request, agent_id: str, payload: AgentUpdatePayload):
    with STORE.lock():
        agent = STORE.agents.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=t_req(request, "api.error.agent_not_found", agent_id=agent_id))
        data = payload.model_dump(exclude_unset=True)
        # P0-3: 切 preset 时覆盖全部相关字段
        if "preset" in data and data["preset"]:
            try:
                from data_ai.plugins.agents import get_preset
                preset_def = get_preset(data["preset"])
            except Exception as exc:  # pragma: no cover
                logger.error(f"update_agent: preset 解析失败 err={exc!r}")
                preset_def = None
            if not preset_def:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown preset role: {data['preset']}",
                )
            data["system_prompt"] = preset_def.get("system_prompt", agent.get("system_prompt", ""))
            data["tool_names"] = list(preset_def.get("tools", agent.get("tool_names", [])))
            data["max_iterations"] = int(preset_def.get("max_iterations", agent.get("max_iterations", 10)))
            data["temperature"] = float(preset_def.get("temperature", agent.get("temperature", 0.7)))
            data["enable_reflection"] = bool(preset_def.get("reflection", agent.get("enable_reflection", False)))
        agent.update(data)
        agent["updated_at"] = _now_ms()
    return agent


@router.delete("/v1/agents/{agent_id}", status_code=204, response_class=Response, response_model=None)
async def delete_agent(request: Request, agent_id: str):
    with STORE.lock():
        if agent_id not in STORE.agents:
            raise HTTPException(status_code=404, detail=t_req(request, "api.error.agent_not_found", agent_id=agent_id))
        del STORE.agents[agent_id]
        STORE.agent_runs.pop(agent_id, None)
    return None


@router.post("/v1/agents/delegate-many", tags=["Agent"])
async def delegate_many(request: Request, payload: AgentDelegateManyPayload):
    """
    P1-7 增强: 并行委派多个 sub-agent + 主动检查 + 准确报错

    每个 sub-task 独立跑,一个失败不影响其他,失败的会带 trace_id + error_class
    """
    import uuid as _uuid
    trace_id = _uuid.uuid4().hex[:12]
    llm_manager = request.app.state.llm_manager
    tool_registry = request.app.state.tool_registry

    if not payload.queries:
        return {"results": [], "trace_id": trace_id}

    from data_ai.core.agent.base import AgentConfig, BaseAgent

    # P1-7 主动检查: 验证 LLM Manager / Tool Registry 可用
    try:
        models = llm_manager.list_models() if hasattr(llm_manager, "list_models") else []
        if not models:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "llm_unavailable",
                        "message": "LLM Manager 不可用: 没有注册任何模型",
                        "fix": "设置 DASHSCOPE_API_KEY 后重启",
                        "trace_id": trace_id,
                    }
                },
            )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "llm_check_failed",
                    "message": f"LLM 健康检查失败: {str(e)[:200]}",
                    "fix": "查看后端日志",
                    "trace_id": trace_id,
                }
            },
        )

    model_name = payload.model or "qwen-turbo"
    if not hasattr(llm_manager, "_clients") or model_name not in (llm_manager._clients if hasattr(llm_manager, "_clients") else {}):
        # fallback 到 default
        if hasattr(llm_manager, "get_default_model"):
            default = llm_manager.get_default_model()
            if default:
                model_name = default

    cfg = AgentConfig(
        model_name=model_name,
        system_prompt="你是一个多任务并行助手",
        temperature=0.3,
        stream=False,
    )
    ag = BaseAgent(config=cfg, llm_manager=llm_manager, tool_registry=tool_registry)

    try:
        results = await ag.delegate_many(payload.queries)
        # 验证每个结果都带 trace_id
        for i, r in enumerate(results):
            if isinstance(r, dict) and "trace_id" not in r:
                r["trace_id"] = _uuid.uuid4().hex[:12]
                r["sub_task_index"] = i
        return {"results": results, "model": model_name, "trace_id": trace_id, "total": len(results)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "delegate_many_failed",
                    "message": f"多委派整体失败: {str(e)[:200]}",
                    "fix": "查看后端日志,trace_id 关联",
                    "trace_id": trace_id,
                }
            },
        )


@router.post("/v1/agents/{agent_id}/run")
async def run_agent(request: Request, agent_id: str, payload: AgentRunPayload):
    with STORE.lock():
        agent = STORE.agents.get(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=t_req(request, "api.error.agent_not_found", agent_id=agent_id))
        agent_copy = dict(agent)
        STORE.agent_runs.setdefault(agent_id, [])

    started = _now_ms()
    run_id = _gen_id("run")

    # 调用真实 LLM：复用已有 chat 端点逻辑，但走最简路径
    output = ""
    iterations = 0
    error: str | None = None
    tool_calls: list[dict[str, Any]] = []

    try:
        from data_ai.core.api.server import app as server_app

        llm_manager = server_app.state.llm_manager
        tool_registry = server_app.state.tool_registry

        from data_ai.core.agent.base import AgentConfig, BaseAgent

        cfg = AgentConfig(
            model_name=agent_copy["model"],
            system_prompt=agent_copy["system_prompt"],
            temperature=agent_copy["temperature"],
            stream=False,
        )
        ag = BaseAgent(config=cfg, llm_manager=llm_manager, tool_registry=tool_registry)
        # 限制可用工具
        if agent_copy.get("tool_names"):
            from data_ai.core.tool.registry import ToolRegistry as _TR

            limited = _TR()
            for name in agent_copy["tool_names"]:
                t = tool_registry.get(name)
                if t:
                    limited._tools[name] = t
            ag.tools = limited

        result = await ag.run(payload.input)
        output = result.get("content", "")
        iterations = result.get("iterations", 0)
        # BaseAgent 内部 tool_calls 不直接透出，但 messages 含 tool_calls
        for m in result.get("messages", []):
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.get("id", ""),
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                    )
    except Exception as e:
        logger.exception("agent run failed")
        error = str(e)
        # 兜底：返回友好提示
        output = f"[运行失败] {e}\n请检查：1) 后端 LLM provider 已配置；2) API key 有效；3) 模型名正确。"

    finished = _now_ms()
    run = {
        "run_id": run_id,
        "agent_id": agent_id,
        "input": payload.input,
        "status": "error" if error else "finished",
        "output": output,
        "tool_calls": tool_calls,
        "iterations": iterations,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": finished - started,
        "error": error,
    }
    with STORE.lock():
        STORE.agent_runs.setdefault(agent_id, []).insert(0, run)
        # 限制每个 agent 最多保留 50 条运行
        if len(STORE.agent_runs[agent_id]) > 50:
            STORE.agent_runs[agent_id] = STORE.agent_runs[agent_id][:50]
    return run


@router.get("/v1/agents/{agent_id}/runs")
async def list_agent_runs(agent_id: str, limit: int = 20):
    with STORE.lock():
        runs = list(STORE.agent_runs.get(agent_id, []))
    return {"object": "list", "data": runs[:limit], "total": len(runs)}


# ============================================================================
# Team 端点
# ============================================================================


@router.get("/v1/teams")
async def list_teams(limit: int = 50, offset: int = 0):
    with STORE.lock():
        items = list(STORE.teams.values())
    items.sort(key=lambda t: t["created_at"], reverse=True)
    return {"object": "list", "data": items[offset : offset + limit], "total": len(items)}


@router.post("/v1/teams", status_code=201)
async def create_team(payload: TeamCreatePayload):
    members = []
    for i, m in enumerate(payload.members):
        members.append(
            {
                "id": m.id or _gen_id("mem"),
                "name": m.name,
                "role": m.role,
                "agent_id": m.agent_id,
                "weight": m.weight,
            }
        )
    team = {
        "id": _gen_id("team"),
        "name": payload.name,
        "description": payload.description or "",
        "mode": payload.mode,
        "consensus_method": payload.consensus_method,
        "members": members,
        "created_at": _now_ms(),
        "updated_at": _now_ms(),
    }
    with STORE.lock():
        STORE.teams[team["id"]] = team
        STORE.team_runs[team["id"]] = []
        STORE.team_messages[team["id"]] = []
    _notify("info", "团队已创建", payload.name, category="team")
    return team


@router.get("/v1/teams/{team_id}")
async def get_team(request: Request, team_id: str):
    with STORE.lock():
        team = STORE.teams.get(team_id)
    if not team:
        raise HTTPException(status_code=404, detail=t_req(request, "api.error.team_not_found", team_id=team_id))
    return team


@router.delete("/v1/teams/{team_id}", status_code=204, response_class=Response, response_model=None)
async def delete_team(request: Request, team_id: str):
    with STORE.lock():
        if team_id not in STORE.teams:
            raise HTTPException(status_code=404, detail=t_req(request, "api.error.team_not_found", team_id=team_id))
        del STORE.teams[team_id]
        STORE.team_runs.pop(team_id, None)
        STORE.team_messages.pop(team_id, None)
    return None


@router.post("/v1/teams/{team_id}/run")
async def run_team(request: Request, team_id: str, payload: TeamRunPayload):
    with STORE.lock():
        team = STORE.teams.get(team_id)
        if not team:
            raise HTTPException(status_code=404, detail=t_req(request, "api.error.team_not_found", team_id=team_id))
        team_copy = dict(team)
        team_copy["members"] = list(team.get("members", []))
        messages = STORE.team_messages.setdefault(team_id, [])

    started = _now_ms()
    run_id = _gen_id("trun")
    method = payload.consensus_method or team_copy["consensus_method"]
    member_answers: list[dict[str, Any]] = []
    votes: list[dict[str, Any]] = []
    final = ""
    error: str | None = None

    try:
        from data_ai.core.api.server import app as server_app

        llm_manager = server_app.state.llm_manager
        tool_registry = server_app.state.tool_registry

        from data_ai.core.agent.base import AgentConfig, BaseAgent

        # 让每个成员跑一次
        per_member_results: list[dict[str, Any]] = []
        for m in team_copy["members"]:
            m_started = _now_ms()
            role = m.get("role") or m.get("name") or "member"
            member_prompt = (
                f"作为团队成员「{m['name']}」（角色：{role}），请针对以下问题给出你的专业回答：\n\n{payload.input}"
            )
            try:
                cfg = AgentConfig(
                    model_name=llm_manager.get_default_model() or "offline-chat",
                    system_prompt=f"你是团队成员 {m['name']}，角色是 {role}。请从你的专业角度回答。",
                    temperature=0.5,
                    stream=False,
                )
                ag = BaseAgent(config=cfg, llm_manager=llm_manager, tool_registry=tool_registry)
                res = await ag.run(member_prompt)
                ans = res.get("content", "")
                iterations = res.get("iterations", 0)
            except Exception as e:
                logger.warning(f"member {m['name']} run failed: {e}")
                ans = f"[{m['name']} 运行失败] {e}"
                iterations = 0
            m_dur = _now_ms() - m_started
            per_member_results.append(
                {
                    "member": m["name"],
                    "answer": ans,
                    "confidence": 0.7,
                    "duration_ms": m_dur,
                    "iterations": iterations,
                }
            )
            member_answers.append(
                {
                    "member": m["name"],
                    "answer": ans,
                    "confidence": 0.7,
                    "duration_ms": m_dur,
                }
            )
            # 写入消息流
            messages.append(
                {
                    "id": _gen_id("msg"),
                    "from": m["id"],
                    "to": "coordinator",
                    "content": ans,
                    "ts": _now_ms(),
                }
            )

        # 共识合成
        try:
            from data_ai.core.agent.consensus import (
                ConcatenationStrategy,
                ConsensusMethod,
                LLMSynthesisStrategy,
                MajorityVoteStrategy,
            )
            from data_ai.core.llm.manager import ChatResponse

            # 把字符串包装成 ChatResponse
            chat_responses = [
                ChatResponse(content=ans, model="member", finish_reason="stop")
                for ans in [r["answer"] for r in per_member_results]
            ]
            try:
                method_enum = ConsensusMethod(method)
            except ValueError:
                method_enum = ConsensusMethod.LLM_SYNTHESIS

            # 优先用 LLMSynthesis（走 LLM 真的合成）
            if method_enum in (ConsensusMethod.LLM_SYNTHESIS, ConsensusMethod.SEMANTIC):
                strategy = LLMSynthesisStrategy(llm_manager=llm_manager)
            elif method_enum == ConsensusMethod.MAJORITY_VOTE:
                strategy = MajorityVoteStrategy()
            else:
                strategy = ConcatenationStrategy()
            result = strategy.synthesize(chat_responses, original_query=payload.input)
            final = result.content or ""
        except Exception as e:
            logger.warning(f"consensus failed: {e}")
            # 兜底：拼接所有回答
            final = "\n\n---\n\n".join(f"【{r['member']}】\n{r['answer']}" for r in per_member_results)

        # 模拟投票
        from collections import Counter

        words = Counter()
        for r in per_member_results:
            for w in re.findall(r"[\u4e00-\u9fff]{2,}", r["answer"]):
                words[w] += 1
        for r in per_member_results:
            votes.append(
                {
                    "member": r["member"],
                    "answer": r["answer"],
                    "votes": max(1, sum(1 for v in words.values() if v >= 2)),
                    "confidence": r["confidence"],
                }
            )
    except Exception as e:
        logger.exception("team run failed")
        error = str(e)
        final = f"[团队运行失败] {e}"

    finished = _now_ms()
    run = {
        "run_id": run_id,
        "team_id": team_id,
        "status": "error" if error else "finished",
        "consensus_method": method,
        "member_answers": member_answers,
        "votes": votes,
        "final_answer": final,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": finished - started,
        "error": error,
    }
    with STORE.lock():
        STORE.team_runs.setdefault(team_id, []).insert(0, run)
        if len(STORE.team_runs[team_id]) > 30:
            STORE.team_runs[team_id] = STORE.team_runs[team_id][:30]
    return run


@router.get("/v1/teams/{team_id}/messages")
async def get_team_messages(team_id: str, limit: int = 100):
    with STORE.lock():
        msgs = list(STORE.team_messages.get(team_id, []))
    return {"data": msgs[-limit:][::-1]}


# ============================================================================
# Memory 端点
# ============================================================================


@router.get("/v1/memory")
async def list_memories(
    type: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    with STORE.lock():
        items = list(STORE.memories.values())
    if type:
        items = [m for m in items if m["type"] == type]
    if q:
        ql = q.lower()
        items = [m for m in items if ql in m["content"].lower() or any(ql in t.lower() for t in m.get("tags", []))]
    items.sort(key=lambda m: m["created_at"], reverse=True)
    total = len(items)
    sliced = items[offset : offset + limit]
    stats: dict[str, int] = {}
    for m in items:
        stats[m["type"]] = stats.get(m["type"], 0) + 1
    return {"object": "list", "data": sliced, "total": total, "stats": stats}


@router.post("/v1/memory", status_code=201)
async def create_memory(payload: MemoryCreatePayload):
    item = {
        "id": _gen_id("mem"),
        "type": payload.type,
        "content": payload.content,
        "importance": payload.importance,
        "tags": payload.tags,
        "pinned": payload.pinned,
        "metadata": payload.metadata or {},
        "created_at": _now_ms(),
    }
    with STORE.lock():
        STORE.memories[item["id"]] = item
    return item


@router.patch("/v1/memory/{memory_id}")
async def update_memory(request: Request, memory_id: str, payload: MemoryUpdatePayload):
    with STORE.lock():
        mem = STORE.memories.get(memory_id)
        if not mem:
            raise HTTPException(
                status_code=404, detail=t_req(request, "api.error.memory_not_found", memory_id=memory_id)
            )
        data = payload.model_dump(exclude_unset=True)
        mem.update(data)
    return mem


@router.get("/v1/memory/{memory_id}")
async def get_memory(memory_id: str):
    """获取单条记忆详情"""
    with STORE.lock():
        item = STORE.memories.get(memory_id)
        if not item:
            # 也允许按 short_term 索引查找
            for k, v in STORE.short_term_memory.items():
                if k == memory_id or memory_id in str(v.get("id", "")):
                    return v
            raise HTTPException(status_code=404, detail=f"Memory not found: {memory_id}")
        return item


@router.delete("/v1/memory/{memory_id}", status_code=204, response_class=Response, response_model=None)
async def delete_memory(request: Request, memory_id: str):
    with STORE.lock():
        if memory_id not in STORE.memories:
            raise HTTPException(
                status_code=404, detail=t_req(request, "api.error.memory_not_found", memory_id=memory_id)
            )
        del STORE.memories[memory_id]
    return None


@router.post("/v1/memory/search")
async def search_memory(payload: MemorySearchPayload):
    with STORE.lock():
        items = list(STORE.memories.values())
    if payload.type:
        items = [m for m in items if m["type"] == payload.type]
    ql = payload.query.lower()
    scored = []
    for m in items:
        # 简单 TF 评分
        content = m["content"].lower()
        if not ql:
            continue
        if ql in content:
            # 出现次数
            cnt = content.count(ql)
            scored.append((m, 0.5 + 0.1 * min(cnt, 5)))
        elif any(ql in t.lower() for t in m.get("tags", [])):
            scored.append((m, 0.4))
    scored.sort(key=lambda x: x[1], reverse=True)
    return {
        "query": payload.query,
        "results": [
            {"id": m["id"], "content": m["content"], "score": s, "type": m["type"]} for m, s in scored[: payload.top_k]
        ],
    }


# ============================================================================
# RAG 端点
# ============================================================================


def _chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[dict[str, Any]]:
    """简单按字符数分块（中文友好）"""
    if not text:
        return []
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end]
        chunks.append(
            {
                "id": _gen_id("chunk"),
                "index": idx,
                "content": chunk,
                "tokens": len(chunk),  # 粗略估计
            }
        )
        idx += 1
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _extract_text(file_path: str) -> str:
    """从文件中提取纯文本（支持 .txt / .md / .html，docx/pdf 给占位提示）"""
    p = Path(file_path)
    if not p.exists():
        return ""
    ext = p.suffix.lower()
    try:
        if ext in (".txt", ".md", ".csv", ".log", ".json"):
            return p.read_text(encoding="utf-8", errors="ignore")
        if ext in (".html", ".htm"):
            return p.read_text(encoding="utf-8", errors="ignore")
        if ext == ".docx":
            try:
                from docx import Document

                doc = Document(str(p))
                return "\n".join(para.text for para in doc.paragraphs)
            except Exception:
                return "[无法读取 docx: 请安装 python-docx]"
        if ext == ".pdf":
            try:
                from pypdf import PdfReader

                return "\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
            except Exception:
                try:
                    from PyPDF2 import PdfReader

                    return "\n".join(page.extract_text() or "" for page in PdfReader(str(p)).pages)
                except Exception:
                    return "[无法读取 pdf: 请安装 pypdf 或 PyPDF2]"
        if ext == ".xlsx":
            try:
                from openpyxl import load_workbook

                wb = load_workbook(str(p), read_only=True, data_only=True)
                out = []
                for ws in wb.worksheets:
                    for row in ws.iter_rows(values_only=True):
                        out.append("\t".join(str(c) if c is not None else "" for c in row))
                return "\n".join(out)
            except Exception:
                return "[无法读取 xlsx: 请安装 openpyxl]"
        if ext == ".pptx":
            try:
                from pptx import Presentation

                prs = Presentation(str(p))
                out = []
                for slide in prs.slides:
                    for shape in slide.shapes:
                        if shape.has_text_frame:
                            for para in shape.text_frame.paragraphs:
                                out.append("".join(run.text for run in para.runs))
                return "\n".join(out)
            except Exception:
                return "[无法读取 pptx: 请安装 python-pptx]"
        # 默认按文本读
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"[读取失败: {e}]"


@router.get("/v1/rag/documents")
async def list_rag_documents(limit: int = 100, offset: int = 0):
    with STORE.lock():
        items = list(STORE.rag_docs.values())
    items.sort(key=lambda d: d["uploaded_at"], reverse=True)
    return {"object": "list", "data": items[offset : offset + limit], "total": len(items)}


@router.post("/v1/rag/documents", status_code=201)
async def upload_rag_document(file: UploadFile = File(...)):
    """上传文档。读取文本、分块、存入。"""
    name = file.filename or "untitled"
    raw = await file.read()
    # 写到本地 tmp 目录
    safe_name = re.sub(r"[^\w.\-]+", "_", name)
    dest = Path("/tmp/data-ai-uploads") / f"{_gen_id('doc')}-{safe_name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)

    # 提取文本
    text = _extract_text(str(dest))
    if not text:
        text = raw.decode("utf-8", errors="ignore")

    doc_id = _gen_id("doc")
    ext = Path(name).suffix.lower().lstrip(".")
    type_ = ext if ext in ("pdf", "docx", "txt", "md", "html", "pptx", "xlsx") else "txt"

    doc = {
        "id": doc_id,
        "name": name,
        "type": type_,
        "size": len(raw),
        "chunks": 0,
        "uploaded_at": _now_ms(),
        "status": "processing",
        "embedder": "text-embedding-3-small",
        "vector_dim": 1536,
        "store": "ChromaDB",
        "metadata": {"path": str(dest)},
    }
    chunks = _chunk_text(text)
    with STORE.lock():
        STORE.rag_docs[doc_id] = doc
        STORE.rag_chunks[doc_id] = chunks
        doc["chunks"] = len(chunks)
        doc["status"] = "ready"
    _notify("success", "文档已上传", f"{name} · {len(chunks)} 块", category="rag")
    return doc


@router.delete("/v1/rag/documents/{doc_id}", status_code=204, response_class=Response, response_model=None)
async def delete_rag_document(request: Request, doc_id: str):
    with STORE.lock():
        if doc_id not in STORE.rag_docs:
            raise HTTPException(status_code=404, detail=t_req(request, "api.error.not_found"))
        del STORE.rag_docs[doc_id]
        STORE.rag_chunks.pop(doc_id, None)
    return None


@router.get("/v1/rag/documents/{doc_id}")
async def get_rag_document(request: Request, doc_id: str):
    with STORE.lock():
        doc = STORE.rag_docs.get(doc_id)
        chunks = list(STORE.rag_chunks.get(doc_id, []))
    if not doc:
        raise HTTPException(status_code=404, detail=t_req(request, "api.error.not_found"))
    return {"document": doc, "chunks": chunks, "total_chunks": len(chunks)}


@router.post("/v1/rag/search")
async def search_rag(payload: RagSearchPayload):
    started = _now_ms()
    ql = payload.query.lower()
    tokens = [t for t in re.split(r"\s+", ql) if t]
    results = []
    with STORE.lock():
        docs = list(STORE.rag_docs.items())
    if payload.document_ids:
        docs = [(d_id, doc) for d_id, doc in docs if d_id in set(payload.document_ids)]
    for d_id, doc in docs:
        if doc["status"] != "ready":
            continue
        with STORE.lock():
            chunks = STORE.rag_chunks.get(d_id, [])
        for c in chunks:
            content = c["content"].lower()
            if not tokens:
                score = 0.0
            else:
                hits = sum(1 for t in tokens if t in content)
                score = hits / len(tokens) if tokens else 0.0
            if score > 0:
                results.append(
                    {
                        "id": c["id"],
                        "content": c["content"],
                        "score": round(score, 4),
                        "document_id": d_id,
                        "document_name": doc["name"],
                        "chunk_index": c["index"],
                    }
                )
    results.sort(key=lambda r: r["score"], reverse=True)
    return {
        "query": payload.query,
        "results": results[: payload.top_k],
        "embedder": payload.embedder or "text-embedding-3-small",
        "duration_ms": _now_ms() - started,
    }


# ============================================================================
# Sandbox 端点
# ============================================================================


@router.get("/v1/sandboxes")
async def list_sandboxes():
    with STORE.lock():
        items = list(STORE.sandboxes.values())
    items.sort(key=lambda s: s["created_at"], reverse=True)
    return {"object": "list", "data": items, "total": len(items)}


@router.post("/v1/sandboxes", status_code=201)
async def create_sandbox(payload: SandboxCreatePayload):
    sid = _gen_id("sbx")
    sbx = {
        "id": sid,
        "name": payload.name,
        "type": payload.type,
        "status": "creating",
        "cpu": 0,
        "memory": 0,
        "network": payload.network,
        "timeout": payload.timeout,
        "memory_limit": payload.memory,
        "cpu_limit": payload.cpu,
        "image": payload.image or "python:3.11-slim",
        "created_at": _now_ms(),
        "uptime": 0,
        "workspace": f"/tmp/data-ai-sandboxes/{sid}",
    }
    # 真实创建工作目录
    Path(sbx["workspace"]).mkdir(parents=True, exist_ok=True)
    sbx["status"] = "running"
    sbx["cpu"] = 1
    sbx["memory"] = 24
    with STORE.lock():
        STORE.sandboxes[sid] = sbx
        STORE.sandbox_snapshots[sid] = []
        STORE.sandbox_files[sid] = {
            "workspace": sbx["workspace"],
            "files": {},
        }
    _notify("success", "沙箱已创建", payload.name, link=f"/sandbox/{sid}", category="sandbox")
    return sbx


@router.get("/v1/sandboxes/{sandbox_id}")
async def get_sandbox(request: Request, sandbox_id: str):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
    if not sbx:
        raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    # 实时累计 uptime
    sbx["uptime"] = (_now_ms() - sbx["created_at"]) // 1000
    return sbx


@router.delete("/v1/sandboxes/{sandbox_id}", status_code=204, response_class=Response, response_model=None)
async def delete_sandbox(request: Request, sandbox_id: str):
    with STORE.lock():
        if sandbox_id not in STORE.sandboxes:
            raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
        del STORE.sandboxes[sandbox_id]
        STORE.sandbox_snapshots.pop(sandbox_id, None)
        STORE.sandbox_files.pop(sandbox_id, None)
    return None


@router.post("/v1/sandboxes/{sandbox_id}/execute")
async def execute_in_sandbox(request: Request, sandbox_id: str, payload: SandboxExecutePayload):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
        if not sbx:
            raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    started = _now_ms()
    timeout = payload.timeout or sbx.get("timeout", 30)
    code = payload.code
    language = payload.language

    stdout = ""
    stderr = ""
    exit_code = 0
    files_changed: list[str] = []

    try:
        if language == "python":
            # 使用真实 Sandbox 模块
            from data_ai.core.sandbox import create_sandbox

            py_sandbox = create_sandbox(
                name=sbx["name"],
                policy_name="moderate",
                timeout=float(timeout),
            )
            with py_sandbox:
                result = py_sandbox.execute(code)
                # 真实 stdout 在 result.output 中；return_value 是 Python __return__
                stdout = str(getattr(result, "output", "") or "")
                err = getattr(result, "error", None)
                ret = getattr(result, "return_value", None)
                if ret is not None and not stdout:
                    stdout = str(ret)
                if err:
                    stderr = str(err)
                    exit_code = 1 if not stdout else 0
                else:
                    exit_code = 0 if getattr(result, "success", True) else 1
        elif language in ("bash", "shell", "sh"):
            import subprocess

            proc = subprocess.run(
                ["bash", "-c", code],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        elif language == "javascript":
            try:
                proc = subprocess.run(
                    ["node", "-e", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode
            except FileNotFoundError:
                stderr = "node 未安装"
                exit_code = 1
        elif language in ("go", "rust"):
            stderr = f"{language} 需要对应编译器；当前为简化实现仅支持 python/bash/javascript"
            exit_code = 1
        else:
            stderr = f"不支持的语言: {language}"
            exit_code = 1
    except subprocess.TimeoutExpired:
        stderr = f"执行超时（>{timeout}s）"
        exit_code = 124
    except Exception as e:
        stderr = f"执行异常: {e}"
        exit_code = 1

    duration = _now_ms() - started
    return {
        "success": exit_code == 0,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_ms": duration,
        "files_changed": files_changed,
    }


@router.get("/v1/sandboxes/{sandbox_id}/files")
async def list_sandbox_files(request: Request, sandbox_id: str, path: str = "."):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
    if not sbx:
        raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    base = Path(sbx["workspace"])
    target = base / path if path != "." else base
    if not target.exists() or not str(target.resolve()).startswith(str(base.resolve())):
        return {"sandbox_id": sandbox_id, "path": path, "tree": []}

    def build(p: Path) -> dict[str, Any]:
        st = p.stat()
        node = {
            "name": p.name,
            "path": str(p.relative_to(base)),
            "type": "dir" if p.is_dir() else "file",
            "size": st.st_size if p.is_file() else None,
            "modified_at": int(st.st_mtime * 1000),
        }
        if p.is_dir():
            children = []
            try:
                for child in sorted(p.iterdir()):
                    children.append(build(child))
            except PermissionError:
                pass
            node["children"] = children
        return node

    tree = []
    if target.is_dir():
        for child in sorted(target.iterdir()):
            tree.append(build(child))
    return {"sandbox_id": sandbox_id, "path": path, "tree": tree}


@router.get("/v1/sandboxes/{sandbox_id}/files/content")
async def get_sandbox_file(request: Request, sandbox_id: str, path: str):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
    if not sbx:
        raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    base = Path(sbx["workspace"]).resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail=t_req(request, "api.error.file_path_invalid", path=""))
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=t_req(request, "api.error.file_not_found", path=path))
    try:
        content = target.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=500, detail=t_req(request, "api.error.file_read_failed", reason=str(e)))
    return {
        "path": path,
        "content": content,
        "size": target.stat().st_size,
        "language": target.suffix.lstrip("."),
    }


@router.post("/v1/sandboxes/{sandbox_id}/files/content")
async def save_sandbox_file(request: Request, sandbox_id: str, payload: FileSavePayload):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
    if not sbx:
        raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    base = Path(sbx["workspace"]).resolve()
    target = (base / payload.path).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail=t_req(request, "api.error.file_path_invalid", path=""))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(payload.content, encoding="utf-8")
    return {"path": payload.path, "size": target.stat().st_size}


@router.get("/v1/sandboxes/{sandbox_id}/snapshots")
async def list_snapshots(sandbox_id: str):
    with STORE.lock():
        snaps = list(STORE.sandbox_snapshots.get(sandbox_id, []))
    if not snaps:
        # 自动加载磁盘上已存在的快照
        sbx = STORE.sandboxes.get(sandbox_id)
        if sbx:
            snap_dir = Path(sbx["workspace"]).parent / ".snapshots"
            if snap_dir.exists():
                for f in snap_dir.iterdir():
                    if f.suffix == ".zip":
                        snaps.append(
                            {
                                "name": f.stem,
                                "created_at": int(f.stat().st_mtime * 1000),
                                "size": f.stat().st_size,
                            }
                        )
                snaps.sort(key=lambda s: s["created_at"], reverse=True)
    return {"data": snaps, "total": len(snaps)}


@router.post("/v1/sandboxes/{sandbox_id}/snapshots", status_code=201)
async def create_snapshot(request: Request, sandbox_id: str, payload: SnapshotCreatePayload):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
    if not sbx:
        raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    base = Path(sbx["workspace"])
    snap_dir = base.parent / ".snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    zip_path = snap_dir / f"{payload.name}.zip"
    if zip_path.exists():
        raise HTTPException(status_code=409, detail=t_req(request, "api.error.snapshot_exists", name=payload.name))

    with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
        for p in base.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(base))
    snap = {
        "name": payload.name,
        "created_at": _now_ms(),
        "size": zip_path.stat().st_size,
        "description": payload.description or "",
    }
    with STORE.lock():
        STORE.sandbox_snapshots.setdefault(sandbox_id, []).insert(0, snap)
    return snap


@router.post("/v1/sandboxes/{sandbox_id}/snapshots/{name}/restore")
async def restore_snapshot(request: Request, sandbox_id: str, name: str):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
    if not sbx:
        raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    base = Path(sbx["workspace"])
    zip_path = base.parent / ".snapshots" / f"{name}.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail=t_req(request, "api.error.snapshot_not_found", name=name))
    # 清空工作区
    for p in base.rglob("*"):
        if p.is_file():
            p.unlink()
    # 解压
    with zipfile.ZipFile(str(zip_path), "r") as zf:
        zf.extractall(str(base))
    return {"restored": name}


@router.delete("/v1/sandboxes/{sandbox_id}/snapshots/{name}", status_code=204, response_class=Response, response_model=None)
async def delete_snapshot(request: Request, sandbox_id: str, name: str):
    with STORE.lock():
        sbx = STORE.sandboxes.get(sandbox_id)
    if not sbx:
        raise HTTPException(status_code=404, detail=t_req(request, "api.sandbox.not_found", sandbox_id=sandbox_id))
    zip_path = Path(sbx["workspace"]).parent / ".snapshots" / f"{name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with STORE.lock():
        snaps = STORE.sandbox_snapshots.get(sandbox_id, [])
        STORE.sandbox_snapshots[sandbox_id] = [s for s in snaps if s["name"] != name]
    return None


# ============================================================================
# Office 端点 - 委托给现有 tool
# ============================================================================


@router.post("/v1/office/word/read")
async def office_word_read(request: Request, payload: WordReadPayload):
    from pathlib import Path as _P

    from data_ai.core.tool.office import word_read

    if not _P(payload.file_path).exists():
        raise HTTPException(status_code=404, detail=t_req(request, "api.error.file_not_found", path=payload.file_path))
    try:
        result = await word_read(
            file_path=payload.file_path,
            extract_tables=payload.extract_tables,
            extract_images=payload.extract_images,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=t_req(request, "api.error.file_not_found", path=payload.file_path))
    except Exception as e:
        # 业务级错误返回 400 而非 500
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.post("/v1/office/word/write")
async def office_word_write(payload: WordWritePayload):
    from data_ai.core.tool.office import word_write

    result = await word_write(
        file_path=payload.file_path,
        content=payload.content,
        title=payload.title,
        author=payload.author,
        format=payload.format,
    )
    return result


@router.post("/v1/office/word/edit")
async def office_word_edit(payload: WordEditPayload):
    import json as _json

    from data_ai.core.tool.office import word_edit

    # 把分散字段组装成 tool 期望的 operations JSON 字符串
    op = payload.operation
    op_obj: dict
    if op == "replace":
        op_obj = {"op": "replace", "find": payload.find or "", "replace": payload.replace or ""}
    elif op in ("append_paragraph", "add_heading"):
        op_obj = {"op": op, "text": payload.text or ""}
        if payload.level is not None:
            op_obj["level"] = payload.level
    elif op == "add_table":
        op_obj = {"op": "add_table", "rows": payload.table or []}
    else:
        op_obj = {"op": op}

    result = await word_edit(
        file_path=payload.file_path,
        operations=_json.dumps([op_obj], ensure_ascii=False),
    )
    return result


@router.post("/v1/office/word/template")
async def office_word_template(payload: WordTemplatePayload):
    import json as _json

    from data_ai.core.tool.office import word_template

    result = await word_template(
        template_path=payload.template_path,
        data=_json.dumps(payload.data, ensure_ascii=False),
        output_path=payload.output_path,
    )
    return result


@router.post("/v1/office/ppt/read")
async def office_ppt_read(payload: PptReadPayload):
    from data_ai.core.tool.office import ppt_read

    result = await ppt_read(file_path=payload.file_path)
    return result


@router.post("/v1/office/ppt/write")
async def office_ppt_write(payload: PptWritePayload):
    from data_ai.core.tool.office import ppt_write

    # 前端 schema 传 List[Dict]；tool 内部需要 JSON 字符串。
    # 在这里统一序列化，避免前端/后端类型不一致。
    result = await ppt_write(
        file_path=payload.file_path,
        title=payload.title,
        slides=json.dumps(payload.slides, ensure_ascii=False),
    )
    return result


# ---------- Office: Excel ----------
# 后端原有 ``excel_write`` 工具函数，但缺少对应路由；这里补齐。
class ExcelWritePayload(BaseModel):
    file_path: str
    data: str | list[list[Any]] | dict[str, Any]
    sheet_name: str = "Sheet1"


@router.post("/v1/office/excel/write")
async def office_excel_write(payload: ExcelWritePayload):
    from data_ai.core.tool.office import excel_write

    if not isinstance(payload.data, str):
        data_str = json.dumps(payload.data, ensure_ascii=False)
    else:
        data_str = payload.data
    result = await excel_write(
        file_path=payload.file_path,
        data=data_str,
        sheet_name=payload.sheet_name,
    )
    return result


@router.post("/v1/office/excel/read")
async def office_excel_read(payload: ExcelReadPayload):
    from data_ai.core.tool.office import excel_read

    result = await excel_read(
        file_path=payload.file_path,
        sheet_name=payload.sheet_name,
    )
    return result


@router.post("/v1/office/excel/analyze")
async def office_excel_analyze(payload: ExcelAnalyzePayload):
    from data_ai.core.tool.office import excel_analyze

    result = await excel_analyze(
        file_path=payload.file_path,
        analysis_type=payload.analysis_type,
    )
    return result


@router.post("/v1/office/excel/chart")
async def office_excel_chart(payload: ExcelChartPayload):
    from data_ai.core.tool.office import excel_chart

    result = await excel_chart(
        file_path=payload.file_path,
        chart_type=payload.chart_type,
        sheet_name=payload.sheet_name,
        data_range=payload.data_range,
        output_file=payload.output_path,
    )
    return result


@router.post("/v1/office/pdf/read")
async def office_pdf_read(payload: PdfReadPayload):
    from data_ai.core.tool.office import pdf_read

    result = await pdf_read(file_path=payload.file_path)
    return result


@router.post("/v1/office/pdf/merge")
async def office_pdf_merge(payload: PdfMergePayload):
    import json as _json

    from data_ai.core.tool.office import pdf_merge

    result = await pdf_merge(
        input_files=_json.dumps(payload.file_paths, ensure_ascii=False),
        output_file=payload.output_path,
    )
    return result


@router.post("/v1/office/pdf/split")
async def office_pdf_split(request: Request, payload: PdfSplitPayload):
    import json as _json

    from data_ai.core.tool.office import pdf_split

    pages = _parse_ranges(payload.ranges)
    if not pages:
        raise HTTPException(
            status_code=400,
            detail=t_req(request, "api.skill.invalid_page_range", ranges=payload.ranges),
        )
    # 把 flat 页码列表 [1,2,3,5] 合并为 [[1,3],[5,5]] 段再 JSON 化传给 tool
    segments: list[list[int]] = []
    for p in sorted(set(pages)):
        if segments and segments[-1][1] == p - 1:
            segments[-1][1] = p
        else:
            segments.append([p, p])
    page_ranges_json = _json.dumps(segments, ensure_ascii=False)
    result = await pdf_split(
        file_path=payload.file_path,
        page_ranges=page_ranges_json,
        output_dir=payload.output_dir,
    )
    return result


# ============================================================================
# Skills 端点
# ============================================================================


@router.get("/v1/skills")
async def list_skills(category: str | None = None, q: str | None = None, limit: int = 100, offset: int = 0):
    with STORE.lock():
        items = list(STORE.skills.values())
    if category:
        items = [s for s in items if s.get("category") == category]
    if q:
        ql = q.lower()
        items = [s for s in items if ql in s["name"].lower() or ql in s["description"].lower()]
    items.sort(key=lambda s: s.get("created_at", 0), reverse=True)
    return {"object": "list", "data": items[offset : offset + limit], "total": len(items)}


@router.post("/v1/skills", status_code=201)
async def create_skill(payload: SkillCreatePayload):
    if not payload.name:
        raise HTTPException(
            status_code=422,
            detail={"loc": ["body", "name"], "msg": "Field required", "type": "missing"},
        )
    skill = {
        "name": payload.name,
        "description": payload.description,
        "version": payload.version,
        "tags": payload.tags,
        "category": payload.category,
        "parameters": payload.parameters,
        "yaml": payload.yaml or "",
        "implementation": payload.implementation or "",
        "source": "user",
        "created_at": _now_ms(),
    }
    with STORE.lock():
        STORE.skills[skill["name"]] = skill
    _notify("success", "技能已创建", payload.name, category="skill")
    return skill


@router.get("/v1/skills/{name}")
async def get_skill(request: Request, name: str):
    with STORE.lock():
        s = STORE.skills.get(name)
    if not s:
        raise HTTPException(
            status_code=404,
            detail=t_req(request, "api.skill.not_found", skill_name=name),
        )
    return s


@router.put("/v1/skills/{name}")
async def save_skill(name: str, payload: SkillCreatePayload):
    payload.name = name
    return await create_skill(payload)


@router.delete("/v1/skills/{name}", status_code=204, response_class=Response, response_model=None)
async def delete_skill(request: Request, name: str):
    with STORE.lock():
        if name not in STORE.skills:
            raise HTTPException(
                status_code=404,
                detail=t_req(request, "api.skill.not_found", skill_name=name),
            )
        del STORE.skills[name]
    return None


@router.post("/v1/skills/{name}/execute")
async def execute_skill(request: Request, name: str, payload: SkillExecutePayload):
    with STORE.lock():
        s = STORE.skills.get(name)
    if not s:
        raise HTTPException(
            status_code=404,
            detail=t_req(request, "api.skill.not_found", skill_name=name),
        )
    started = _now_ms()
    try:
        # 优先调用实现，否则用 LLM 模拟
        impl = s.get("implementation") or ""
        if impl and impl.strip():
            # ⚠️ 简化执行：把 parameters 当作 Python 局部变量执行。
            # Skill 的 implementation 字段只应由受信管理员编辑，调用方通过
            # DATA_AI_SKILL_EXEC=allow 显式放行；否则直接走 LLM 路径。
            import os as _os

            if _os.environ.get("DATA_AI_SKILL_EXEC", "").lower() not in ("1", "true", "yes"):
                raise RuntimeError(
                    "Direct skill execution is disabled. Set DATA_AI_SKILL_EXEC=1 to enable (admin-only)."
                )
            ns: dict[str, Any] = dict(payload.parameters)
            import contextlib
            import io as _io

            buf = _io.StringIO()
            with contextlib.redirect_stdout(buf):
                exec(impl, {"__builtins__": {}}, ns)  # noqa: S102 - gated by env flag
            output = buf.getvalue()
            success = True
            error = None
        else:
            # 用 LLM 跑
            from data_ai.core.api.server import app as server_app
            from data_ai.core.llm.manager import ChatMessage

            llm_manager = server_app.state.llm_manager
            default_model = llm_manager.get_default_model() or list(llm_manager._configs.keys())[0]
            params_desc = "\n".join(f"- {p['name']}: {payload.parameters.get(p['name'], '')}" for p in s["parameters"])
            prompt = (
                f"请执行技能「{s['name']}」\n描述：{s['description']}\n"
                f"参数：\n{params_desc}\n\n请基于以上信息给出执行结果。"
            )
            resp = await llm_manager.chat(
                messages=[ChatMessage(role="user", content=prompt)],
                model=default_model,
                temperature=0.3,
            )
            output = getattr(resp, "content", "") or ""
            success = True
            error = None
    except Exception as e:
        logger.exception("skill execute failed")
        success = False
        output = None
        error = str(e)
    return {
        "success": success,
        "output": output,
        "error": error,
        "duration_ms": _now_ms() - started,
    }


@router.post("/v1/skills/extract")
async def extract_skill(request: Request, payload: SkillExtractPayload):
    """从文本/URL 中提取可能的 skill 描述"""
    text = payload.source
    if payload.source_type == "url":
        # 不真去抓取，给出明确说明
        return {
            "candidates": [],
            "note": "URL 抓取需要额外实现（httpx + html 解析），当前简化版本只接受 text/file",
        }
    if payload.source_type == "file":
        p = Path(payload.source)
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="ignore")
        else:
            raise HTTPException(
                status_code=404,
                detail=t_req(request, "api.sandbox.file_not_found", path=payload.source),
            )

    # 启发式：寻找「动词 + 名词」短语作为候选技能
    candidates = []
    # 匹配 "实现一个 X" / "X 函数" / "X 工具" / "def X"
    patterns = [
        r"(?:实现|编写|提供|添加)(?:一个)?([\u4e00-\u9fffA-Za-z_]{2,20})(?:函数|工具|方法|技能)",
        r"def\s+([a-zA-Z_][a-zA-Z0-9_]{1,30})\s*\(([^)]*)\)",
        r"async\s+def\s+([a-zA-Z_][a-zA-Z0-9_]{1,30})\s*\(([^)]*)\)",
    ]
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text):
            if pat.startswith("def") or pat.startswith("async"):
                name = m.group(1)
                params_raw = m.group(2)
            else:
                name = m.group(1)
                params_raw = ""
            if name in seen:
                continue
            seen.add(name)
            params = []
            if params_raw.strip():
                for p in re.split(r",\s*", params_raw):
                    p = p.strip()
                    if not p:
                        continue
                    pname = re.split(r"[:=\s]", p, 1)[0]
                    params.append({"name": pname, "type": "string", "required": "=" not in p, "description": ""})
            candidates.append(
                {
                    "name": name,
                    "description": f"从文档提取: {name}",
                    "parameters": params,
                    "confidence": 0.7,
                }
            )
    return {"candidates": candidates[:20]}


# ============================================================================
# MCP (Model Context Protocol) 端点
# ============================================================================


def _mcp_registry(request: Request):
    """从 app.state 拿 MCP registry,缺失则懒加载"""
    reg = getattr(request.app.state, "mcp_registry", None)
    if reg is None:
        from data_ai.core.mcp import get_mcp_registry, load_builtin_servers
        reg = get_mcp_registry()
        load_builtin_servers(reg)
        request.app.state.mcp_registry = reg
    return reg


@router.get("/v1/mcp/servers", tags=["MCP"])
async def list_mcp_servers(request: Request, include_tools: bool = False):
    """列出所有已注册的 MCP server(builtin + user)"""
    reg = _mcp_registry(request)
    servers = [s.to_dict() for s in reg.list_servers()]
    servers.sort(key=lambda s: (not s.get("enabled", False), s.get("created_at", 0)))
    out = {
        "object": "list",
        "data": servers,
        "total": len(servers),
        "builtin_count": sum(1 for s in reg.list_servers() if reg.is_builtin(s.id)),
        "user_count": sum(1 for s in reg.list_servers() if not reg.is_builtin(s.id)),
    }
    if include_tools:
        for s in out["data"]:
            s["tools"] = [t.to_dict() for t in reg.get_cached_tools(s["id"])]
    return out


@router.get("/v1/mcp/presets", tags=["MCP"])
async def list_mcp_presets():
    """列出 mcp_schema.json 中预置的 builtin server 配置(可一键 install)"""
    from data_ai.core.mcp.server import BUILTIN_MCP_SERVERS
    return {
        "object": "list",
        "data": BUILTIN_MCP_SERVERS,
        "total": len(BUILTIN_MCP_SERVERS),
        "hint": "POST /v1/mcp/servers/preset/{id} 一键启用 builtin server",
    }


@router.post("/v1/mcp/servers", status_code=201, tags=["MCP"])
async def create_mcp_server(request: Request, payload: MCPServerCreatePayload):
    """注册新 MCP server"""
    from data_ai.core.mcp.types import MCPServerConfig, MCPServerStatus, MCPServerType

    try:
        t = MCPServerType(payload.type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid type: {payload.type}")

    reg = _mcp_registry(request)
    cfg = MCPServerConfig(
        id=payload.id or "",
        name=payload.name,
        type=t,
        command=payload.command,
        args=list(payload.args),
        url=payload.url,
        env=dict(payload.env),
        description=payload.description,
        icon=payload.icon,
        enabled=payload.enabled,
        status=MCPServerStatus.INACTIVE,
    )
    saved = reg.add_server(cfg, builtin=False)
    return saved.to_dict()


@router.post("/v1/mcp/servers/preset/{preset_id}", status_code=201, tags=["MCP"])
async def install_mcp_preset(request: Request, preset_id: str):
    """一键启用 builtin preset(比如把 mcp-filesystem 从 inactive → active)"""
    from data_ai.core.mcp.server import BUILTIN_MCP_SERVERS
    reg = _mcp_registry(request)
    target = next((s for s in BUILTIN_MCP_SERVERS if s["id"] == preset_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"preset not found: {preset_id}")
    existing = reg.get_server(preset_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"preset not registered in registry: {preset_id}")
    updated = reg.update_server(preset_id, {"enabled": True, "status": "active"})
    if updated is None:
        raise HTTPException(status_code=500, detail="update_server returned None")
    return updated.to_dict()


@router.get("/v1/mcp/servers/{server_id}", tags=["MCP"])
async def get_mcp_server(request: Request, server_id: str):
    reg = _mcp_registry(request)
    cfg = reg.get_server(server_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"MCP server not found: {server_id}")
    out = cfg.to_dict()
    out["is_builtin"] = reg.is_builtin(server_id)
    out["tools"] = [t.to_dict() for t in reg.get_cached_tools(server_id)]
    return out


@router.patch("/v1/mcp/servers/{server_id}", tags=["MCP"])
async def update_mcp_server(request: Request, server_id: str, payload: MCPServerUpdatePayload):
    reg = _mcp_registry(request)
    cfg = reg.get_server(server_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"MCP server not found: {server_id}")
    patch = payload.model_dump(exclude_unset=True)
    if "enabled" in patch and patch["enabled"]:
        patch["status"] = "active"
    elif "enabled" in patch and not patch["enabled"]:
        patch["status"] = "inactive"
    updated = reg.update_server(server_id, patch)
    if updated is None:
        raise HTTPException(status_code=500, detail="update_server returned None")
    return updated.to_dict()


@router.delete("/v1/mcp/servers/{server_id}", status_code=204, tags=["MCP"], response_class=Response, response_model=None)
async def delete_mcp_server(request: Request, server_id: str):
    reg = _mcp_registry(request)
    if reg.get_server(server_id) is None:
        raise HTTPException(status_code=404, detail=f"MCP server not found: {server_id}")
    if reg.is_builtin(server_id):
        raise HTTPException(status_code=400, detail=f"cannot delete builtin server: {server_id}")
    reg.remove_server(server_id)
    return None


@router.get("/v1/mcp/servers/{server_id}/tools", tags=["MCP"])
async def list_mcp_server_tools(request: Request, server_id: str, refresh: bool = False):
    """列 server 暴露的工具;refresh=true 时主动从远端拉一次"""
    import uuid as _uuid

    reg = _mcp_registry(request)
    cfg = reg.get_server(server_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"MCP server not found: {server_id}")
    trace_id = _uuid.uuid4().hex[:12]

    if not refresh:
        tools = reg.get_cached_tools(server_id)
        return {
            "object": "list",
            "server_id": server_id,
            "server_name": cfg.name,
            "data": [t.to_dict() for t in tools],
            "total": len(tools),
            "cached": True,
            "trace_id": trace_id,
        }

    # refresh: 主动从 server 拉
    from data_ai.core.mcp.client import MCPServerProxy, get_in_process_server

    try:
        if cfg.id == "mcp-in-process" or cfg.url.startswith("in-process://"):
            in_proc = get_in_process_server()
            tools = in_proc.to_mcp_tools(server_id=cfg.id, server_name=cfg.name)
        else:
            proxy = MCPServerProxy(cfg)
            tools = await proxy.list_tools()
        reg.cache_tools(server_id, tools)
        reg.update_server(server_id, {"status": "active", "last_error": None, "last_check_at": _now_ms()})
        return {
            "object": "list",
            "server_id": server_id,
            "server_name": cfg.name,
            "data": [t.to_dict() for t in tools],
            "total": len(tools),
            "cached": False,
            "trace_id": trace_id,
        }
    except Exception as e:
        reg.update_server(server_id, {"status": "error", "last_error": str(e)[:300]})
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "code": "mcp_refresh_failed",
                    "message": f"无法从 server 拉取工具: {e!r}",
                    "fix": "检查 command 是否安装 / url 是否可达,或查看 server.last_error",
                    "trace_id": trace_id,
                    "server_id": server_id,
                }
            },
        )


@router.post("/v1/mcp/invoke", tags=["MCP"])
async def invoke_mcp_tool(request: Request, payload: MCPInvokePayload):
    """调用 MCP 工具"""
    import uuid as _uuid

    from data_ai.core.mcp.types import MCPInvokeRequest

    trace_id = _uuid.uuid4().hex[:12]
    reg = _mcp_registry(request)

    cfg = reg.get_server(payload.server_id)
    if cfg is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "server_not_found",
                    "message": f"MCP server 不存在: {payload.server_id}",
                    "fix": "GET /v1/mcp/servers 查可用 id",
                    "trace_id": trace_id,
                }
            },
        )

    req = MCPInvokeRequest(
        server_id=payload.server_id,
        tool_name=payload.tool_name,
        arguments=payload.arguments,
        timeout=payload.timeout,
    )
    result = await reg.invoke(req)
    if not result.success:
        return JSONResponse(
            status_code=400 if "not found" in (result.error or "").lower() else 502,
            content={
                "error": {
                    "code": result.error_class or "invoke_failed",
                    "message": result.error,
                    "trace_id": result.trace_id,
                    "server_id": result.server_id,
                    "tool_name": result.tool_name,
                }
            },
        )
    return result.to_dict()


@router.get("/v1/mcp/health", tags=["MCP"])
async def mcp_health(request: Request):
    reg = _mcp_registry(request)
    return reg.health().to_dict()


@router.get("/v1/mcp/tools", tags=["MCP"])
async def list_all_mcp_tools(request: Request):
    """列所有 active server 的工具(供 LLM 选择调用)"""
    reg = _mcp_registry(request)
    tools = reg.list_all_tools()
    return {
        "object": "list",
        "data": [t.to_dict() for t in tools],
        "openai_format": [t.to_openai_tool() for t in tools],
        "total": len(tools),
    }


# ============================================================================
# Reasoning (CoT / 思维链) 端点
# ============================================================================


class ReasoningSequentialPayload(BaseModel):
    question: str
    context: str | None = None
    max_steps: int = 5
    use_llm: bool = True
    model: str | None = None


class ReasoningReflectionPayload(BaseModel):
    question: str
    draft_answer: str
    context: str | None = None
    use_llm: bool = True
    model: str | None = None


class ReasoningHypothesisPayload(BaseModel):
    question: str
    observations: list[str] = Field(default_factory=list)
    max_hypotheses: int = 3
    use_llm: bool = True
    model: str | None = None


async def _resolve_llm_fn(request: Request, model: str | None):
    """从 app.state.llm_manager 拿一个 async llm_fn(question, system=None) -> str"""
    llm_manager = getattr(request.app.state, "llm_manager", None)
    if llm_manager is None:
        return None, None

    model_name = model
    if not model_name and hasattr(llm_manager, "get_default_model"):
        try:
            model_name = llm_manager.get_default_model()
        except Exception:
            model_name = None
    model_name = model_name or "qwen-turbo"

    async def llm_fn(question: str, system: str | None = None) -> str:
        try:
            from data_ai.core.llm.manager import ChatMessage
        except ImportError:
            return "[LLM unavailable: ChatMessage not found]"

        msgs = []
        if system:
            msgs.append(ChatMessage(role="system", content=system))
        msgs.append(ChatMessage(role="user", content=question))
        try:
            resp = await llm_manager.chat(msgs, model=model_name, temperature=0.3)
            return getattr(resp, "content", "") or ""
        except Exception as e:
            return f"[LLM error: {type(e).__name__}: {e}]"

    return llm_fn, model_name


@router.post("/v1/reasoning/sequential", tags=["Reasoning"])
async def reasoning_sequential(request: Request, payload: ReasoningSequentialPayload):
    """CoT 思维链:让 LLM 多步推理一个 question

    body: {question, context?, max_steps?, use_llm?, model?}
    returns: {question, thoughts:[{content, confidence, is_hypothesis}], final_answer, method, model, duration_ms}
    """
    import time as _t

    from data_ai.core.reasoning.sequential import SequentialThinking

    started = _t.time()
    llm_fn, model_name = await _resolve_llm_fn(request, payload.model) if payload.use_llm else (None, None)

    engine = SequentialThinking(max_steps=payload.max_steps)
    chain = await engine.think(payload.question, llm_fn=llm_fn, context=payload.context)

    out = chain.to_dict()
    out["method"] = "llm" if llm_fn else "fallback"
    out["model"] = model_name
    out["duration_ms"] = int((_t.time() - started) * 1000)
    return out


@router.post("/v1/reasoning/reflection", tags=["Reasoning"])
async def reasoning_reflection(request: Request, payload: ReasoningReflectionPayload):
    """Reflection 反思:基于 draft_answer 二次思考给出更准确的答案"""
    import time as _t

    from data_ai.core.reasoning.reflection import ReflectionEngine
    from data_ai.core.reasoning.sequential import ReasoningChain, Thought

    started = _t.time()
    llm_fn, model_name = await _resolve_llm_fn(request, payload.model) if payload.use_llm else (None, None)
    engine = ReflectionEngine()

    # 把 draft_answer 包装成 ReasoningChain 喂给 reflect()
    chain = ReasoningChain(
        question=payload.question,
        thoughts=[Thought(content=payload.draft_answer, confidence=0.7)],
        final_answer=payload.draft_answer,
    )
    if payload.context:
        chain.thoughts.append(Thought(content=f"Context: {payload.context}", confidence=0.6))

    reflection = engine.reflect(chain)
    out = {
        "question": payload.question,
        "draft_answer": payload.draft_answer,
        "final_answer": reflection.revised_conclusion or reflection.original_conclusion,
        "issues_found": list(reflection.issues_found),
        "improvements": list(reflection.improvements),
        "confidence_change": reflection.confidence_change,
        "method": "rule-based",
        "model": model_name,
        "duration_ms": int((_t.time() - started) * 1000),
    }
    return out


@router.post("/v1/reasoning/hypothesis", tags=["Reasoning"])
async def reasoning_hypothesis(request: Request, payload: ReasoningHypothesisPayload):
    """Hypothesis 假设:根据 observations 推断可能的解释"""
    import time as _t

    from data_ai.core.reasoning.hypothesis import Hypothesis, HypothesisGenerator, HypothesisStatus

    started = _t.time()
    llm_fn, model_name = await _resolve_llm_fn(request, payload.model) if payload.use_llm else (None, None)
    gen = HypothesisGenerator(max_hypotheses=payload.max_hypotheses)

    context: dict = {}
    if payload.observations:
        context["observations"] = payload.observations
    hypotheses: list[Hypothesis] = gen.generate(
        problem=payload.question,
        context=context,
        num_hypotheses=payload.max_hypotheses,
    )
    out = {
        "question": payload.question,
        "hypotheses": [
            {
                "id": h.id,
                "statement": h.statement,
                "premises": list(h.premises),
                "predictions": list(h.predictions),
                "confidence": h.confidence,
                "status": h.status.value if isinstance(h.status, HypothesisStatus) else h.status,
            }
            for h in hypotheses
        ],
        "method": "template-based",
        "model": model_name,
        "duration_ms": int((_t.time() - started) * 1000),
    }
    return out


@router.get("/v1/reasoning/methods", tags=["Reasoning"])
async def reasoning_methods():
    """列出所有可用的推理方法"""
    return {
        "object": "list",
        "data": [
            {
                "name": "sequential",
                "description": "Chain-of-thought 顺序推理:多步分解问题,逐步思考得出答案",
                "endpoint": "/v1/reasoning/sequential",
                "params": ["question", "context?", "max_steps?", "model?"],
            },
            {
                "name": "reflection",
                "description": "Reflection 反思:对初稿答案二次审视、找出不足并改进",
                "endpoint": "/v1/reasoning/reflection",
                "params": ["question", "draft_answer", "context?", "model?"],
            },
            {
                "name": "hypothesis",
                "description": "Hypothesis 假设生成:根据观察推断可能的解释,适合故障排查/根因分析",
                "endpoint": "/v1/reasoning/hypothesis",
                "params": ["question", "observations[]", "max_hypotheses?", "model?"],
            },
        ],
        "total": 3,
    }


# ============================================================================
# Notifications
# ============================================================================


@router.get("/v1/notifications")
async def list_notifications(unread_only: bool = False, limit: int = 50):
    with STORE.lock():
        items = list(STORE.notifications)
    if unread_only:
        items = [n for n in items if not n["read"]]
    return {
        "object": "list",
        "data": items[:limit],
        "total": len(items),
        "unread_count": sum(1 for n in items if not n["read"]),
    }


@router.post("/v1/notifications/mark-read")
async def mark_notifications_read(payload: NotificationMarkPayload):
    with STORE.lock():
        if payload.all_read:
            for n in STORE.notifications:
                n["read"] = True
            count = len(STORE.notifications)
        else:
            ids = set(payload.ids or [])
            count = 0
            for n in STORE.notifications:
                if n["id"] in ids and not n["read"]:
                    n["read"] = True
                    count += 1
    return {"marked": count}


# ============================================================================
# Session history (服务器端)
# ============================================================================


@router.get("/v1/sessions")
async def list_sessions(limit: int = 50):
    with STORE.lock():
        items = list(STORE.sessions.values())
    items.sort(key=lambda s: s["updated_at"], reverse=True)
    return {"object": "list", "data": items[:limit], "total": len(items)}


@router.post("/v1/sessions", status_code=201)
async def create_session(payload: dict[str, Any]):
    """创建会话（前端主动调用）"""
    now = _now_ms()
    sid = _gen_id("sess")
    item = {
        "id": sid,
        "title": payload.get("title", "新对话"),
        "model": payload.get("model", "gpt-4"),
        "messages": payload.get("messages", []),
        "message_count": len(payload.get("messages", [])),
        "preview": (payload.get("messages", [{}])[-1].get("content", "") or "")[:100],
        "created_at": now,
        "updated_at": now,
    }
    with STORE.lock():
        STORE.sessions[sid] = item
    return item


@router.put("/v1/sessions/{session_id}")
async def upsert_session(session_id: str, payload: dict[str, Any]):
    """前端把会话存到服务器（可选）"""
    now = _now_ms()
    item = {
        "id": session_id,
        "title": payload.get("title", "新对话"),
        "model": payload.get("model", "gpt-4"),
        "messages": payload.get("messages", []),
        "message_count": len(payload.get("messages", [])),
        "preview": (payload.get("messages", [{}])[-1].get("content", "") or "")[:100],
        "created_at": payload.get("created_at", now),
        "updated_at": now,
    }
    with STORE.lock():
        STORE.sessions[session_id] = item
    return item


@router.delete("/v1/sessions/{session_id}", status_code=204, response_class=Response, response_model=None)
async def delete_session(session_id: str):
    with STORE.lock():
        STORE.sessions.pop(session_id, None)
    return None


# ============================================================================
# 健康检查扩展 - 注册组件
# ============================================================================


@router.get("/v1/extensions/health")
async def extensions_health():
    """返回详细诊断信息（供前端 settings 连接测试用）。

    包括：后端版本、模型/工具数量、各 store 的扩展计数、uptime、
    capabilities 列表、Python 进程信息。轻量、无副作用。
    """
    import os
    import platform
    import time as _time

    with STORE.lock():
        ext = {
            "agents": len(STORE.agents),
            "teams": len(STORE.teams),
            "memories": len(STORE.memories),
            "rag_documents": len(STORE.rag_docs),
            "sandboxes": len(STORE.sandboxes),
            "skills": len(STORE.skills),
            "notifications": len(STORE.notifications),
        }

    # 模型 / 工具计数（从 LLMManager / ToolRegistry 单例拿）
    models_count = 0
    tools_count = 0
    try:
        from data_ai.core.llm.manager import get_llm_manager

        llm_mgr = get_llm_manager()
        models_count = len(list(llm_mgr.list_models()))
    except Exception:
        pass
    try:
        from data_ai.core.tool.registry import get_tool_registry

        tools_count = len(get_tool_registry().list_tools())
    except Exception:
        pass

    # 启动时间（用来算 uptime）
    started_at = float(os.environ.get("_DATA_AI_STARTED_AT", "0") or "0")
    if not started_at:
        # 进程启动时间（boot time ≈ uptime）
        try:
            with open("/proc/stat") as f:
                for line in f:
                    if line.startswith("btime "):
                        started_at = float(line.split()[1])
                        break
        except Exception:
            started_at = 0
    uptime_ms = int((_time.time() - started_at) * 1000) if started_at else None

    # capabilities 列表（前端 settings 据此启用/禁用 UI）
    capabilities = [
        "chat",
        "agents",
        "teams",
        "memory",
        "rag",
        "sandbox",
        "office",
        "skills",
        "mcp",
        "notifications",
        "sessions",
    ]

    # 后端版本
    try:
        from data_ai import __version__ as _v

        version = _v
    except Exception:
        version = "unknown"

    return {
        "status": "ok",
        "version": version,
        "api_version": "v1",
        "uptime_ms": uptime_ms,
        "ts": _now_ms(),
        "process": {
            "pid": os.getpid(),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "models_count": models_count,
        "tools_count": tools_count,
        "capabilities": capabilities,
        "extensions": ext,
        "endpoints": {
            "chat": "/v1/chat/completions",
            "models": "/v1/models",
            "tools": "/v1/tools",
            "agents": "/v1/agents",
            "teams": "/v1/teams",
            "memory": "/v1/memory",
            "rag": "/v1/rag/documents",
            "sandbox": "/v1/sandboxes",
            "office": "/v1/office/{word,ppt,excel,pdf}",
            "skills": "/v1/skills",
            "mcp": "/v1/mcp/servers",
        },
    }


# ============================================================================
# P1-10 企业治理: 审计 / 配额 / Webhook / 定时任务
# ============================================================================

from data_ai.core.audit import get_audit_store  # noqa: E402
from data_ai.core.quota import QuotaPolicy, get_quota_manager  # noqa: E402
from data_ai.core.scheduler import ScheduledJob, get_scheduler  # noqa: E402
from data_ai.core.webhooks import EVENT_TYPES, WebhookSubscription, get_webhook_dispatcher  # noqa: E402

# ---------- Audit ----------


class AuditQueryParams(BaseModel):
    actor: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    status_code: int | None = None
    since: float | None = None
    until: float | None = None
    limit: int = Query(100, ge=1, le=1000)
    offset: int = Query(0, ge=0)


@router.get("/v1/audit", tags=["Audit"])
def audit_list(params: AuditQueryParams = Depends()) -> dict:
    """查询审计日志 (who/what/when/result)"""
    store = get_audit_store()
    items = store.query(
        actor=params.actor,
        action=params.action,
        resource_type=params.resource_type,
        resource_id=params.resource_id,
        status_code=params.status_code,
        since=params.since,
        until=params.until,
        limit=params.limit,
        offset=params.offset,
    )
    return {"total": len(items), "items": items, "query": params.model_dump()}


@router.get("/v1/audit/stats", tags=["Audit"])
def audit_stats() -> dict:
    """审计统计 (按状态/动作聚合)"""
    return get_audit_store().stats()


@router.get("/v1/audit/export", tags=["Audit"])
def audit_export(
    fmt: str = Query("json", pattern="^(json|csv)$"),
    actor: str | None = None,
    action: str | None = None,
) -> JSONResponse:
    """导出审计 (合规取证)"""
    store = get_audit_store()
    items = store.query(actor=actor, action=action, limit=10000)
    if fmt == "csv":
        return JSONResponse(
            content={"format": "csv", "data": store.export_csv(items), "count": len(items)}
        )
    return JSONResponse(
        content={"format": "json", "data": store.export_json(items), "count": len(items)}
    )


@router.delete("/v1/audit", tags=["Audit"], status_code=204, response_class=Response, response_model=None)
def audit_clear() -> None:
    """清空审计 (慎用,留痕)"""
    get_audit_store().clear()


# ---------- Quota ----------


class QuotaPolicyPayload(BaseModel):
    scope: str = Field("key", pattern="^(global|key|user)$")
    scope_id: str = ""
    daily_token_limit: int | None = None
    monthly_token_limit: int | None = None
    daily_request_limit: int | None = None
    qps_limit: float | None = None
    max_concurrent: int | None = None
    enabled: bool = True


@router.get("/v1/quota/policies", tags=["Quota"])
def quota_policies_list() -> dict:
    return {"policies": get_quota_manager().list_policies()}


@router.post("/v1/quota/policies", status_code=201, tags=["Quota"])
def quota_policies_create(payload: QuotaPolicyPayload) -> dict:
    policy = QuotaPolicy(**payload.model_dump())
    get_quota_manager().set_policy(policy)
    return {"policy": get_quota_manager().get_policy(policy.scope, policy.scope_id)}


@router.delete("/v1/quota/policies/{scope}/{scope_id}", status_code=204, tags=["Quota"], response_class=Response, response_model=None)
def quota_policies_delete(scope: str, scope_id: str) -> None:
    get_quota_manager().delete_policy(scope, scope_id)


@router.get("/v1/quota/usage", tags=["Quota"])
def quota_usage(
    actor: str | None = None,
    model: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    mgr = get_quota_manager()
    return {
        "summary": mgr.usage_summary(actor=actor),
        "records": mgr.usage_records(actor=actor, model=model, limit=limit),
    }


@router.get("/v1/quota/status/{actor}", tags=["Quota"])
def quota_status(actor: str) -> dict:
    return get_quota_manager().quota_status(actor)


# ---------- Webhooks ----------


class WebhookCreatePayload(BaseModel):
    name: str
    url: str
    events: list[str]
    description: str = ""
    custom_headers: dict[str, str] = Field(default_factory=dict)
    max_retries: int = 3
    timeout_sec: float = 10.0
    active: bool = True


class WebhookUpdatePayload(BaseModel):
    name: str | None = None
    url: str | None = None
    events: list[str] | None = None
    description: str | None = None
    active: bool | None = None
    max_retries: int | None = None
    timeout_sec: float | None = None
    custom_headers: dict[str, str] | None = None


@router.get("/v1/webhooks/events", tags=["Webhooks"])
def webhooks_events() -> dict:
    """列出所有支持的事件类型"""
    return {"events": EVENT_TYPES, "total": len(EVENT_TYPES)}


@router.get("/v1/webhooks", tags=["Webhooks"])
def webhooks_list() -> dict:
    return {"subscriptions": get_webhook_dispatcher().list()}


@router.post("/v1/webhooks", status_code=201, tags=["Webhooks"])
def webhooks_create(payload: WebhookCreatePayload) -> dict:
    sub = WebhookSubscription(**payload.model_dump())
    get_webhook_dispatcher().create(sub)
    return {"subscription": sub.to_dict()}


# 注意: 这条"特殊字面量"路由必须在 /v1/webhooks/{sub_id} 之前注册,
# 否则 FastAPI 会把 deliveries 匹配为 sub_id 路径参数,导致 404。
@router.get("/v1/webhooks/deliveries", tags=["Webhooks"])
def webhooks_all_deliveries(
    event: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    return {
        "deliveries": get_webhook_dispatcher().list_deliveries(event=event, status=status, limit=limit),
        "stats": get_webhook_dispatcher().delivery_stats(),
    }


@router.get("/v1/webhooks/{sub_id}", tags=["Webhooks"])
def webhooks_get(sub_id: str) -> dict:
    sub = get_webhook_dispatcher().get(sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="webhook not found")
    return {"subscription": sub.to_dict()}


@router.patch("/v1/webhooks/{sub_id}", tags=["Webhooks"])
def webhooks_update(sub_id: str, payload: WebhookUpdatePayload) -> dict:
    sub = get_webhook_dispatcher().update(sub_id, **payload.model_dump(exclude_unset=True))
    if not sub:
        raise HTTPException(status_code=404, detail="webhook not found")
    return {"subscription": sub.to_dict()}


@router.delete("/v1/webhooks/{sub_id}", status_code=204, tags=["Webhooks"], response_class=Response, response_model=None)
def webhooks_delete(sub_id: str) -> None:
    get_webhook_dispatcher().delete(sub_id)


@router.post("/v1/webhooks/{sub_id}/test", tags=["Webhooks"])
async def webhooks_test(sub_id: str) -> dict:
    """测试发送 (验证订阅配置正确)"""
    try:
        d = await get_webhook_dispatcher().test_send(sub_id)
        return {"delivery": d.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------- Scheduler ----------


class SchedulePayload(BaseModel):
    kind: str = Field("cron", pattern="^(cron|at|every)$")
    expression: str = ""


class JobCreatePayload(BaseModel):
    name: str
    description: str = ""
    action_type: str = Field("http", pattern="^(http|agent_run|memory_cleanup|rag_reindex|shell)$")
    action_payload: dict = Field(default_factory=dict)
    schedule: SchedulePayload = Field(default_factory=lambda: SchedulePayload(kind="every", expression="3600s"))
    enabled: bool = True
    timeout_sec: float = 300.0
    max_retries: int = 0


class JobUpdatePayload(BaseModel):
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    action_payload: dict | None = None
    schedule: SchedulePayload | None = None
    timeout_sec: float | None = None


@router.get("/v1/jobs", tags=["Scheduler"])
def jobs_list() -> dict:
    scheduler = get_scheduler()
    return {"jobs": scheduler.list(), "stats": scheduler.stats()}


@router.post("/v1/jobs", status_code=201, tags=["Scheduler"])
def jobs_create(payload: JobCreatePayload) -> dict:
    from data_ai.core.scheduler import Schedule

    job = ScheduledJob(
        name=payload.name,
        description=payload.description,
        action_type=payload.action_type,
        action_payload=payload.action_payload,
        schedule=Schedule(**payload.schedule.model_dump()),
        enabled=payload.enabled,
        timeout_sec=payload.timeout_sec,
        max_retries=payload.max_retries,
    )
    get_scheduler().create(job)
    return {"job": job.to_dict()}


@router.get("/v1/jobs/{job_id}", tags=["Scheduler"])
def jobs_get(job_id: str) -> dict:
    job = get_scheduler().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job": job.to_dict()}


@router.patch("/v1/jobs/{job_id}", tags=["Scheduler"])
def jobs_update(job_id: str, payload: JobUpdatePayload) -> dict:
    from data_ai.core.scheduler import Schedule

    update_kwargs: dict = {}
    data = payload.model_dump(exclude_unset=True)
    if "schedule" in data and data["schedule"]:
        data["schedule"] = Schedule(**data["schedule"])
    update_kwargs.update(data)
    job = get_scheduler().update(job_id, **update_kwargs)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job": job.to_dict()}


@router.delete("/v1/jobs/{job_id}", status_code=204, tags=["Scheduler"], response_class=Response, response_model=None)
def jobs_delete(job_id: str) -> None:
    get_scheduler().delete(job_id)


@router.post("/v1/jobs/{job_id}/trigger", tags=["Scheduler"])
def jobs_trigger(job_id: str) -> dict:
    exec_rec = get_scheduler().trigger_now(job_id)
    if not exec_rec:
        raise HTTPException(status_code=404, detail="job not found")
    return {"execution": exec_rec.to_dict()}


@router.get("/v1/jobs/{job_id}/executions", tags=["Scheduler"])
def jobs_executions(job_id: str, limit: int = Query(50, ge=1, le=500)) -> dict:
    return {"executions": get_scheduler().list_executions(job_id=job_id, limit=limit)}


@router.get("/v1/jobs/executions/all", tags=["Scheduler"])
def jobs_all_executions(
    status: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    return {"executions": get_scheduler().list_executions(status=status, limit=limit)}


# ============================================================================
# P1-11 企业治理 Tier 2 — 多租户 / RBAC / 成本 / SLA / SSO / 驻留 / 审计链
# ============================================================================

# ---------- Pydantic Schemas ----------


class TenantCreatePayload(BaseModel):
    name: str
    slug: str | None = ""
    plan: str = "free"
    region: str = "default"
    contact_email: str = ""
    limits: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TenantUpdatePayload(BaseModel):
    name: str | None = None
    plan: str | None = None
    status: str | None = None
    region: str | None = None
    contact_email: str | None = None
    limits: dict[str, Any] | None = None


class TenantMemberPayload(BaseModel):
    user_id: str
    role: str = "member"


# ---------- 多租户 ----------


@router.get("/v1/tenants", tags=["Tenants"])
def tenants_list(status: str | None = None, plan: str | None = None) -> dict:
    from data_ai.core.tenants import get_tenant_store

    store = get_tenant_store()
    return {"tenants": [t.to_dict() for t in store.list(status=status, plan=plan)], "stats": store.stats()}


@router.post("/v1/tenants", status_code=201, tags=["Tenants"])
def tenants_create(payload: TenantCreatePayload) -> dict:
    from data_ai.core.tenants import get_tenant_store

    try:
        t = get_tenant_store().create(
            name=payload.name, slug=payload.slug or "", plan=payload.plan,  # type: ignore[arg-type]
            region=payload.region, contact_email=payload.contact_email,
            limits=payload.limits, metadata=payload.metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"tenant": t.to_dict()}


@router.get("/v1/tenants/{tenant_id}", tags=["Tenants"])
def tenants_get(tenant_id: str) -> dict:
    from data_ai.core.tenants import get_tenant_store

    t = get_tenant_store().get(tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="tenant not found")
    members = get_tenant_store().list_members(tenant_id)
    return {"tenant": t.to_dict(), "members": [m.to_dict() for m in members]}


@router.patch("/v1/tenants/{tenant_id}", tags=["Tenants"])
def tenants_update(tenant_id: str, payload: TenantUpdatePayload) -> dict:
    from data_ai.core.tenants import get_tenant_store

    update_kwargs = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    t = get_tenant_store().update(tenant_id, **update_kwargs)
    if not t:
        raise HTTPException(status_code=404, detail="tenant not found")
    return {"tenant": t.to_dict()}


@router.delete("/v1/tenants/{tenant_id}", status_code=204, tags=["Tenants"], response_class=Response, response_model=None)
def tenants_delete(tenant_id: str) -> None:
    from data_ai.core.tenants import get_tenant_store

    if not get_tenant_store().delete(tenant_id):
        raise HTTPException(status_code=404, detail="tenant not found")


@router.post("/v1/tenants/{tenant_id}/suspend", tags=["Tenants"])
def tenants_suspend(tenant_id: str) -> dict:
    from data_ai.core.tenants import get_tenant_store

    t = get_tenant_store().suspend(tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="tenant not found")
    return {"tenant": t.to_dict()}


@router.post("/v1/tenants/{tenant_id}/activate", tags=["Tenants"])
def tenants_activate(tenant_id: str) -> dict:
    from data_ai.core.tenants import get_tenant_store

    t = get_tenant_store().activate(tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="tenant not found")
    return {"tenant": t.to_dict()}


@router.get("/v1/tenants/{tenant_id}/members", tags=["Tenants"])
def tenants_list_members(tenant_id: str) -> dict:
    from data_ai.core.tenants import get_tenant_store

    return {"members": [m.to_dict() for m in get_tenant_store().list_members(tenant_id)]}


@router.post("/v1/tenants/{tenant_id}/members", status_code=201, tags=["Tenants"])
def tenants_add_member(tenant_id: str, payload: TenantMemberPayload) -> dict:
    from data_ai.core.tenants import get_tenant_store

    m = get_tenant_store().add_member(tenant_id, payload.user_id, payload.role)  # type: ignore[arg-type]
    return {"member": m.to_dict()}


@router.delete("/v1/tenants/{tenant_id}/members/{user_id}", status_code=204, tags=["Tenants"], response_class=Response, response_model=None)
def tenants_remove_member(tenant_id: str, user_id: str) -> None:
    from data_ai.core.tenants import get_tenant_store

    if not get_tenant_store().remove_member(tenant_id, user_id):
        raise HTTPException(status_code=404, detail="member not found")


# ---------- RBAC ----------


class RoleCreatePayload(BaseModel):
    name: str
    description: str = ""
    permissions: list[dict[str, Any]] = Field(default_factory=list)
    parent_roles: list[str] = Field(default_factory=list)
    tenant_id: str = ""


class PolicyCreatePayload(BaseModel):
    name: str
    description: str = ""
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    effect: str = "allow"
    priority: int = 100
    tenant_id: str = ""
    enabled: bool = True


class AssignmentPayload(BaseModel):
    user_id: str
    role_id: str
    tenant_id: str = ""
    granted_by: str = ""
    expires_at: float = 0.0


class RbacCheckPayload(BaseModel):
    user_id: str
    resource: str
    action: str
    tenant_id: str = ""
    env: dict[str, Any] = Field(default_factory=dict)
    resource_ctx: dict[str, Any] = Field(default_factory=dict)


# 注意: 字面量路由放在路径参数路由之前,避免 {role_id} 捕获
@router.get("/v1/rbac/decisions", tags=["RBAC"])
def rbac_recent_decisions(limit: int = Query(50, ge=1, le=500)) -> dict:
    from data_ai.core.rbac import get_rbac_engine

    decisions = get_rbac_engine().recent_decisions(limit=limit)
    return {"decisions": [d.to_dict() for d in decisions]}


@router.get("/v1/rbac/roles", tags=["RBAC"])
def rbac_list_roles(tenant_id: str | None = None, include_system: bool = True) -> dict:
    from data_ai.core.rbac import get_rbac_engine

    roles = get_rbac_engine().list_roles(tenant_id=tenant_id, include_system=include_system)
    return {"roles": [r.to_dict() for r in roles]}


@router.post("/v1/rbac/roles", status_code=201, tags=["RBAC"])
def rbac_create_role(payload: RoleCreatePayload) -> dict:
    from data_ai.core.rbac import Permission, get_rbac_engine

    perms = [Permission(**p) for p in payload.permissions]
    try:
        r = get_rbac_engine().create_role(
            name=payload.name, permissions=perms, parent_roles=payload.parent_roles,
            tenant_id=payload.tenant_id, description=payload.description,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"role": r.to_dict()}


@router.get("/v1/rbac/roles/{role_id}", tags=["RBAC"])
def rbac_get_role(role_id: str) -> dict:
    from data_ai.core.rbac import get_rbac_engine

    r = get_rbac_engine().get_role(role_id)
    if not r:
        raise HTTPException(status_code=404, detail="role not found")
    return {"role": r.to_dict()}


@router.delete("/v1/rbac/roles/{role_id}", status_code=204, tags=["RBAC"], response_class=Response, response_model=None)
def rbac_delete_role(role_id: str) -> None:
    from data_ai.core.rbac import get_rbac_engine

    if not get_rbac_engine().delete_role(role_id):
        raise HTTPException(status_code=404, detail="role not found")


@router.get("/v1/rbac/policies", tags=["RBAC"])
def rbac_list_policies(tenant_id: str = "") -> dict:
    from data_ai.core.rbac import get_rbac_engine

    return {"policies": [p.to_dict() for p in get_rbac_engine().list_policies(tenant_id=tenant_id)]}


@router.post("/v1/rbac/policies", status_code=201, tags=["RBAC"])
def rbac_create_policy(payload: PolicyCreatePayload) -> dict:
    from data_ai.core.rbac import get_rbac_engine

    p = get_rbac_engine().create_policy(
        name=payload.name, conditions=payload.conditions, effect=payload.effect,  # type: ignore[arg-type]
        priority=payload.priority, tenant_id=payload.tenant_id, enabled=payload.enabled, description=payload.description,
    )
    return {"policy": p.to_dict()}


@router.delete("/v1/rbac/policies/{policy_id}", status_code=204, tags=["RBAC"], response_class=Response, response_model=None)
def rbac_delete_policy(policy_id: str) -> None:
    from data_ai.core.rbac import get_rbac_engine

    if not get_rbac_engine().delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="policy not found")


@router.get("/v1/rbac/assignments", tags=["RBAC"])
def rbac_list_assignments(user_id: str = "", tenant_id: str = "") -> dict:
    from data_ai.core.rbac import get_rbac_engine

    return {"assignments": [a.to_dict() for a in get_rbac_engine().list_assignments(user_id=user_id, tenant_id=tenant_id)]}


@router.post("/v1/rbac/assignments", status_code=201, tags=["RBAC"])
def rbac_assign(payload: AssignmentPayload) -> dict:
    from data_ai.core.rbac import get_rbac_engine

    a = get_rbac_engine().assign(
        user_id=payload.user_id, role_id=payload.role_id, tenant_id=payload.tenant_id,
        granted_by=payload.granted_by, expires_at=payload.expires_at,
    )
    return {"assignment": a.to_dict()}


@router.delete("/v1/rbac/assignments", status_code=204, tags=["RBAC"], response_class=Response, response_model=None)
def rbac_revoke(user_id: str = Query(...), role_id: str = Query(...), tenant_id: str = Query("")) -> None:
    from data_ai.core.rbac import get_rbac_engine

    get_rbac_engine().revoke(user_id, role_id, tenant_id)


@router.post("/v1/rbac/check", tags=["RBAC"])
def rbac_check(payload: RbacCheckPayload) -> dict:
    from data_ai.core.rbac import get_rbac_engine

    d = get_rbac_engine().check(
        user_id=payload.user_id, resource=payload.resource, action=payload.action,
        tenant_id=payload.tenant_id, env=payload.env, resource_ctx=payload.resource_ctx,
    )
    return {"decision": d.to_dict()}


@router.post("/v1/rbac/delegate", tags=["RBAC"])
def rbac_delegate(from_user: str, to_user: str, role_id: str, tenant_id: str = "", expires_in: float = 3600) -> dict:
    from data_ai.core.rbac import get_rbac_engine

    expires_at = time.time() + expires_in if expires_in > 0 else 0.0
    a = get_rbac_engine().delegate(from_user, to_user, role_id, tenant_id, expires_at)
    return {"assignment": a.to_dict()}


# ---------- 成本中心 ----------


class PricingPayload(BaseModel):
    model_id: str
    input_per_1k: float
    output_per_1k: float
    cached_input_per_1k: float = 0.0
    currency: str = "USD"


class UsageRecordPayload(BaseModel):
    tenant_id: str = ""
    user_id: str = ""
    cost_center_id: str = ""
    project: str = ""
    resource_type: str = "agent"
    resource_id: str = ""
    model_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0


class BudgetPayload(BaseModel):
    name: str
    scope: str = "tenant"
    scope_id: str = ""
    period: str = "monthly"
    amount_usd: float = 1000.0
    hard_limit: bool = False
    warn_threshold: float = 0.8
    enabled: bool = True


class CostCenterPayload(BaseModel):
    tenant_id: str = ""
    name: str = ""
    code: str = ""
    parent_id: str = ""
    manager_user_id: str = ""
    monthly_budget_usd: float = 0.0


# 字面量路由必须放在路径参数路由之前
@router.get("/v1/billing/summary", tags=["Billing"])
def billing_summary(tenant_id: str = "", since: float | None = None, until: float | None = None) -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"summary": get_billing_engine().summary(tenant_id=tenant_id, since=since, until=until)}


@router.get("/v1/billing/cost-by-day", tags=["Billing"])
def billing_cost_by_day(tenant_id: str = "", days: int = Query(30, ge=1, le=365)) -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"series": get_billing_engine().cost_by_day(tenant_id=tenant_id, days=days)}


@router.get("/v1/billing/top-spenders", tags=["Billing"])
def billing_top_spenders(by: str = "user", tenant_id: str = "", limit: int = Query(10, ge=1, le=100)) -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"top": get_billing_engine().top_spenders(by=by, tenant_id=tenant_id, limit=limit)}


@router.get("/v1/billing/pricing", tags=["Billing"])
def billing_list_pricing() -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"pricing": [p.to_dict() for p in get_billing_engine().list_pricing()]}


@router.post("/v1/billing/pricing", status_code=201, tags=["Billing"])
def billing_set_pricing(payload: PricingPayload) -> dict:
    from data_ai.core.billing import get_billing_engine

    p = get_billing_engine().set_pricing(
        model_id=payload.model_id, input_per_1k=payload.input_per_1k,
        output_per_1k=payload.output_per_1k, cached_input_per_1k=payload.cached_input_per_1k,
        currency=payload.currency,
    )
    return {"pricing": p.to_dict()}


@router.post("/v1/billing/usage", status_code=201, tags=["Billing"])
def billing_record_usage(payload: UsageRecordPayload) -> dict:
    from data_ai.core.billing import get_billing_engine

    r = get_billing_engine().record(
        tenant_id=payload.tenant_id, user_id=payload.user_id, cost_center_id=payload.cost_center_id,
        project=payload.project, resource_type=payload.resource_type, resource_id=payload.resource_id,
        model_id=payload.model_id, prompt_tokens=payload.prompt_tokens,
        completion_tokens=payload.completion_tokens, cached_tokens=payload.cached_tokens,
    )
    return {"record": r.to_dict()}


@router.get("/v1/billing/usage", tags=["Billing"])
def billing_list_usage(
    tenant_id: str = "",
    cost_center_id: str = "",
    since: float | None = None,
    until: float | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"records": [r.to_dict() for r in get_billing_engine().list_records(tenant_id=tenant_id, cost_center_id=cost_center_id, since=since, until=until, limit=limit)]}


@router.get("/v1/billing/budgets", tags=["Billing"])
def billing_list_budgets(scope: str | None = None, scope_id: str = "") -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"budgets": [b.to_dict() for b in get_billing_engine().list_budgets(scope=scope, scope_id=scope_id)]}


@router.post("/v1/billing/budgets", status_code=201, tags=["Billing"])
def billing_set_budget(payload: BudgetPayload) -> dict:
    from data_ai.core.billing import Budget, get_billing_engine

    b = Budget(
        name=payload.name, scope=payload.scope, scope_id=payload.scope_id,
        period=payload.period,  # type: ignore[arg-type]
        amount_usd=payload.amount_usd, hard_limit=payload.hard_limit,
        warn_threshold=payload.warn_threshold, enabled=payload.enabled,
    )
    return {"budget": get_billing_engine().set_budget(b).to_dict()}


@router.delete("/v1/billing/budgets/{budget_id}", status_code=204, tags=["Billing"], response_class=Response, response_model=None)
def billing_delete_budget(budget_id: str) -> None:
    from data_ai.core.billing import get_billing_engine

    if not get_billing_engine().delete_budget(budget_id):
        raise HTTPException(status_code=404, detail="budget not found")


@router.get("/v1/billing/cost-centers", tags=["Billing"])
def billing_list_cost_centers(tenant_id: str = "") -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"cost_centers": [c.to_dict() for c in get_billing_engine().list_cost_centers(tenant_id=tenant_id)]}


@router.post("/v1/billing/cost-centers", status_code=201, tags=["Billing"])
def billing_add_cost_center(payload: CostCenterPayload) -> dict:
    from data_ai.core.billing import CostCenter, get_billing_engine

    c = CostCenter(
        tenant_id=payload.tenant_id, name=payload.name, code=payload.code,
        parent_id=payload.parent_id, manager_user_id=payload.manager_user_id,
        monthly_budget_usd=payload.monthly_budget_usd,
    )
    return {"cost_center": get_billing_engine().add_cost_center(c).to_dict()}


@router.get("/v1/billing/budget-check", tags=["Billing"])
def billing_budget_check(tenant_id: str = "", cost_center_id: str = "") -> dict:
    from data_ai.core.billing import get_billing_engine

    ok, alerts = get_billing_engine().check_budget(tenant_id=tenant_id, cost_center_id=cost_center_id)
    return {"ok": ok, "alerts": alerts}


@router.get("/v1/billing/invoice", tags=["Billing"])
def billing_invoice(tenant_id: str = Query(...), since: float = Query(...), until: float = Query(...), format: str = "json") -> dict:
    from data_ai.core.billing import get_billing_engine

    return {"invoice": get_billing_engine().export_invoice(tenant_id=tenant_id, since=since, until=until, format=format)}


# ---------- SLA 监控 + 状态页 ----------


# 字面量路由必须放在路径参数路由之前
@router.get("/v1/sla/status", tags=["SLA"])
def sla_status_page() -> dict:
    from data_ai.core.sla import get_sla_monitor

    return get_sla_monitor().status_page()


@router.get("/v1/sla/slos", tags=["SLA"])
def sla_list_slos() -> dict:
    from data_ai.core.sla import get_sla_monitor

    return {"slos": [s.to_dict() for s in get_sla_monitor().list_slos()]}


@router.post("/v1/sla/slos", status_code=201, tags=["SLA"])
def sla_create_slo(payload: dict) -> dict:
    from data_ai.core.sla import SLO, get_sla_monitor

    slo = SLO(**payload)
    return {"slo": get_sla_monitor().create_slo(slo).to_dict()}


@router.get("/v1/sla/slos/evaluate", tags=["SLA"])
def sla_evaluate_all_slos() -> dict:
    from data_ai.core.sla import get_sla_monitor

    return {"reports": get_sla_monitor().evaluate_all_slos()}


@router.get("/v1/sla/slos/{slo_id}/evaluate", tags=["SLA"])
def sla_evaluate_slo(slo_id: str, window_sec: float = Query(86400, ge=60, le=2592000)) -> dict:
    from data_ai.core.sla import get_sla_monitor

    slo = next((s for s in get_sla_monitor().list_slos() if s.id == slo_id), None)
    if not slo:
        raise HTTPException(status_code=404, detail="slo not found")
    return {"report": get_sla_monitor().evaluate_slo(slo, window_sec=window_sec)}


@router.get("/v1/sla/components", tags=["SLA"])
def sla_list_components() -> dict:
    from data_ai.core.sla import get_sla_monitor

    return {"components": [c.to_dict() for c in get_sla_monitor().list_components()]}


@router.post("/v1/sla/components", status_code=201, tags=["SLA"])
def sla_register_component(payload: dict) -> dict:
    from data_ai.core.sla import get_sla_monitor

    c = get_sla_monitor().register_component(name=payload.get("name", ""), description=payload.get("description", ""))
    return {"component": c.to_dict()}


@router.post("/v1/sla/probe", tags=["SLA"])
def sla_record_probe(payload: dict) -> dict:
    from data_ai.core.sla import get_sla_monitor

    p = get_sla_monitor().record_probe(
        component_id=payload.get("component_id", ""),
        success=bool(payload.get("success", True)),
        latency_ms=float(payload.get("latency_ms", 0)),
        error_code=int(payload.get("error_code", 200)),
    )
    return {"probe": p.__dict__}


class IncidentPayload(BaseModel):
    title: str
    severity: str = "minor"
    affected_components: list[str] = Field(default_factory=list)
    message: str = ""


class IncidentUpdatePayload(BaseModel):
    status: str = "investigating"
    message: str = ""
    by: str = ""


@router.get("/v1/sla/incidents", tags=["SLA"])
def sla_list_incidents(status: str | None = None, limit: int = Query(50, ge=1, le=500)) -> dict:
    from data_ai.core.sla import IncidentStatus, get_sla_monitor

    st = IncidentStatus(status) if status else None
    return {"incidents": [i.to_dict() for i in get_sla_monitor().list_incidents(status=st, limit=limit)]}


@router.post("/v1/sla/incidents", status_code=201, tags=["SLA"])
def sla_open_incident(payload: IncidentPayload) -> dict:
    from data_ai.core.sla import IncidentSeverity, get_sla_monitor

    inc = get_sla_monitor().open_incident(
        title=payload.title, severity=IncidentSeverity(payload.severity),
        affected_components=payload.affected_components, message=payload.message,
    )
    return {"incident": inc.to_dict()}


@router.patch("/v1/sla/incidents/{incident_id}", tags=["SLA"])
def sla_update_incident(incident_id: str, payload: IncidentUpdatePayload) -> dict:
    from data_ai.core.sla import IncidentStatus, get_sla_monitor

    inc = get_sla_monitor().update_incident(
        incident_id, status=IncidentStatus(payload.status),
        message=payload.message, by=payload.by,
    )
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    return {"incident": inc.to_dict()}


@router.get("/v1/sla/incidents/{incident_id}", tags=["SLA"])
def sla_get_incident(incident_id: str) -> dict:
    from data_ai.core.sla import get_sla_monitor

    inc = get_sla_monitor().get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    return {"incident": inc.to_dict()}


@router.get("/v1/sla/report/monthly", tags=["SLA"])
def sla_monthly_report(year: int = Query(...), month: int = Query(..., ge=1, le=12)) -> dict:
    from data_ai.core.sla import get_sla_monitor

    return {"report": get_sla_monitor().monthly_report(year=year, month=month)}


# ---------- SSO ----------


class IdpCreatePayload(BaseModel):
    name: str
    type: str = "oidc"
    issuer: str = ""
    client_id: str = ""
    client_secret: str = ""
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    userinfo_endpoint: str = ""
    jwks_uri: str = ""
    scopes: list[str] = Field(default_factory=lambda: ["openid", "email", "profile"])
    allowed_email_domains: list[str] = Field(default_factory=list)
    default_role: str = "member"
    auto_provision: bool = True


class LoginCompletePayload(BaseModel):
    code: str
    redirect_uri: str
    tenant_id: str = ""


class ScimUserPayload(BaseModel):
    user_name: str
    display_name: str = ""
    active: bool = True
    groups: list[str] = Field(default_factory=list)


# 字面量路由必须放在路径参数路由之前
@router.get("/v1/sso/auth-url", tags=["SSO"])
def sso_auth_url(idp_id: str = Query(...), redirect_uri: str = Query(...)) -> dict:
    from data_ai.core.sso import get_sso_engine

    engine = get_sso_engine()
    provider = engine.get_provider(idp_id)
    if not provider or not hasattr(provider, "build_authorization_url"):
        raise HTTPException(status_code=400, detail="idp not found or unsupported")
    url = provider.build_authorization_url(redirect_uri=redirect_uri)  # type: ignore[union-attr]
    return {"url": url}


@router.get("/v1/sso/idps", tags=["SSO"])
def sso_list_idps() -> dict:
    from data_ai.core.sso import get_sso_engine

    return {"idps": [i.to_dict() for i in get_sso_engine().list_idps()]}


@router.post("/v1/sso/idps", status_code=201, tags=["SSO"])
def sso_register_idp(payload: IdpCreatePayload) -> dict:
    from data_ai.core.sso import IdentityProvider, get_sso_engine

    idp = IdentityProvider(**payload.model_dump())
    return {"idp": get_sso_engine().register_idp(idp).to_dict()}


@router.get("/v1/sso/idps/{idp_id}", tags=["SSO"])
def sso_get_idp(idp_id: str) -> dict:
    from data_ai.core.sso import get_sso_engine

    idp = get_sso_engine().get_idp(idp_id)
    if not idp:
        raise HTTPException(status_code=404, detail="idp not found")
    return {"idp": idp.to_dict()}


@router.delete("/v1/sso/idps/{idp_id}", status_code=204, tags=["SSO"], response_class=Response, response_model=None)
def sso_delete_idp(idp_id: str) -> None:
    from data_ai.core.sso import get_sso_engine

    if not get_sso_engine().delete_idp(idp_id):
        raise HTTPException(status_code=404, detail="idp not found")


@router.post("/v1/sso/login", tags=["SSO"])
def sso_complete_login(idp_id: str = Query(...), payload: LoginCompletePayload = ..., request: Request = None) -> dict:  # type: ignore[assignment]
    from data_ai.core.sso import get_sso_engine

    ip = request.client.host if request and request.client else ""
    ua = request.headers.get("user-agent", "") if request else ""
    result = get_sso_engine().complete_login(
        idp_id=idp_id, code=payload.code, redirect_uri=payload.redirect_uri,
        tenant_id=payload.tenant_id, ip=ip, user_agent=ua,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "login failed"))
    return result


@router.post("/v1/sso/logout", tags=["SSO"])
def sso_logout(session_id: str = Query(...)) -> dict:
    from data_ai.core.sso import get_sso_engine

    return {"revoked": get_sso_engine().logout(session_id)}


@router.get("/v1/sso/sessions", tags=["SSO"])
def sso_list_sessions(user_id: str = "") -> dict:
    from data_ai.core.sso import get_sso_engine

    return {"sessions": [s.to_dict() for s in get_sso_engine().sessions.list_sessions(user_id=user_id)]}


@router.get("/v1/sso/scim/users", tags=["SSO"])
def sso_list_scim_users(active_only: bool = False) -> dict:
    from data_ai.core.sso import get_sso_engine

    return {"users": [u.to_dict() for u in get_sso_engine().scim.list_users(active_only=active_only)]}


@router.post("/v1/sso/scim/users", status_code=201, tags=["SSO"])
def sso_upsert_scim_user(payload: ScimUserPayload) -> dict:
    from data_ai.core.sso import get_sso_engine

    u = get_sso_engine().scim.upsert_user(
        user_name=payload.user_name, display_name=payload.display_name,
        active=payload.active, groups=payload.groups,
    )
    return {"user": u.to_dict()}


@router.delete("/v1/sso/scim/users/{user_name}", status_code=204, tags=["SSO"], response_class=Response, response_model=None)
def sso_deactivate_scim_user(user_name: str) -> None:
    from data_ai.core.sso import get_sso_engine

    get_sso_engine().scim.deactivate(user_name)


# ---------- 数据驻留 ----------


class RegionCreatePayload(BaseModel):
    id: str
    name: str = ""
    country: str = ""
    tier: str = "tier-2"
    storage_backend: str = "local"
    endpoint: str = ""


class ResidencyPolicyPayload(BaseModel):
    name: str
    data_class: str = "user_data"
    allowed_regions: list[str] = Field(default_factory=list)
    forbidden_regions: list[str] = Field(default_factory=list)
    allow_cross_region_transfer: bool = False
    encryption_required: bool = True
    retention_days: int = 365
    enabled: bool = True
    description: str = ""


class ResidencyRoutePayload(BaseModel):
    resource_id: str
    data_class: str = "user_data"
    tenant_id: str = ""
    prefer_region: str = ""


# 字面量路由必须放在路径参数路由之前
@router.get("/v1/residency/stats", tags=["Residency"])
def residency_stats() -> dict:
    from data_ai.core.residency import get_residency_router

    return get_residency_router().stats()


@router.get("/v1/residency/regions", tags=["Residency"])
def residency_list_regions() -> dict:
    from data_ai.core.residency import get_residency_router

    return {"regions": [r.to_dict() for r in get_residency_router().list_regions()]}


@router.post("/v1/residency/regions", status_code=201, tags=["Residency"])
def residency_add_region(payload: RegionCreatePayload) -> dict:
    from data_ai.core.residency import Region, get_residency_router

    r = Region(**payload.model_dump())
    return {"region": get_residency_router().add_region(r).to_dict()}


@router.post("/v1/residency/regions/{region_id}/status", tags=["Residency"])
def residency_set_region_status(region_id: str, status: str = Query(...)) -> dict:
    from data_ai.core.residency import RegionStatus, get_residency_router

    r = get_residency_router().set_region_status(region_id, RegionStatus(status))  # type: ignore[arg-type]
    if not r:
        raise HTTPException(status_code=404, detail="region not found")
    return {"region": r.to_dict()}


@router.get("/v1/residency/policies", tags=["Residency"])
def residency_list_policies() -> dict:
    from data_ai.core.residency import get_residency_router

    return {"policies": [p.to_dict() for p in get_residency_router().list_policies()]}


@router.post("/v1/residency/policies", status_code=201, tags=["Residency"])
def residency_add_policy(payload: ResidencyPolicyPayload) -> dict:
    from data_ai.core.residency import ResidencyPolicy, get_residency_router

    p = ResidencyPolicy(**payload.model_dump())
    return {"policy": get_residency_router().add_policy(p).to_dict()}


@router.delete("/v1/residency/policies/{policy_id}", status_code=204, tags=["Residency"], response_class=Response, response_model=None)
def residency_delete_policy(policy_id: str) -> None:
    from data_ai.core.residency import get_residency_router

    if not get_residency_router().delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="policy not found")


@router.post("/v1/residency/route", tags=["Residency"])
def residency_route(payload: ResidencyRoutePayload) -> dict:
    from data_ai.core.residency import get_residency_router

    a = get_residency_router().route(
        resource_id=payload.resource_id, data_class=payload.data_class,  # type: ignore[arg-type]
        tenant_id=payload.tenant_id, prefer_region=payload.prefer_region,
    )
    return {"assignment": a.to_dict()}


@router.post("/v1/residency/can-transfer", tags=["Residency"])
def residency_can_transfer(resource_id: str = Query(...), from_region: str = Query(...), to_region: str = Query(...)) -> dict:
    from data_ai.core.residency import get_residency_router

    ok, reason = get_residency_router().can_transfer(resource_id, from_region, to_region)
    return {"ok": ok, "reason": reason}


@router.get("/v1/residency/assignments", tags=["Residency"])
def residency_list_assignments(tenant_id: str = "", data_class: str | None = None, limit: int = Query(100, ge=1, le=1000)) -> dict:
    from data_ai.core.residency import get_residency_router

    return {"assignments": [a.to_dict() for a in get_residency_router().list_assignments(tenant_id=tenant_id, data_class=data_class, limit=limit)]}


# ---------- 审计链 (Merkle) ----------


class AuditChainAddPayload(BaseModel):
    entry: dict[str, Any]


# 字面量路由必须放在路径参数路由之前
@router.get("/v1/audit-chain/integrity", tags=["AuditChain"])
def audit_chain_integrity() -> dict:
    from data_ai.core.audit_chain import get_audit_chain

    return get_audit_chain().chain_integrity()


@router.get("/v1/audit-chain/blocks", tags=["AuditChain"])
def audit_chain_list_blocks() -> dict:
    from data_ai.core.audit_chain import get_audit_chain

    return {"blocks": [b.to_dict() for b in get_audit_chain().list_blocks()]}


@router.post("/v1/audit-chain/add", tags=["AuditChain"])
def audit_chain_add(payload: AuditChainAddPayload) -> dict:
    from data_ai.core.audit_chain import get_audit_chain

    block = get_audit_chain().add_entry(payload.entry)
    return {"block_sealed": block.to_dict() if block else None, "pending": get_audit_chain().pending_count()}


@router.post("/v1/audit-chain/seal", tags=["AuditChain"])
def audit_chain_force_seal() -> dict:
    from data_ai.core.audit_chain import get_audit_chain

    return {"block": get_audit_chain().force_seal().to_dict()}


@router.get("/v1/audit-chain/proof", tags=["AuditChain"])
def audit_chain_proof(entry_id: str = Query(...)) -> dict:
    from data_ai.core.audit_chain import get_audit_chain

    proof = get_audit_chain().get_proof(entry_id)
    if not proof:
        raise HTTPException(status_code=404, detail="entry not found in any block")
    return {"proof": proof}


# ---------- 跨区域复制 (Replication) ----------


class ReplicationPolicyPayload(BaseModel):
    name: str
    source_region: str
    target_region: str
    mode: str = "async"
    resource_types: list[str] = []
    max_lag_sec: float = 30.0
    encryption: bool = True
    compression: bool = True
    metadata: dict[str, Any] = {}


class FailoverInitPayload(BaseModel):
    from_region: str
    to_region: str
    mode: str = "planned"
    initiated_by: str = ""
    reason: str = ""
    affected_resources: list[str] = []


class FailoverAdvancePayload(BaseModel):
    new_state: str
    notes: str = ""


class FailoverCompletePayload(BaseModel):
    success: bool
    data_loss_records: int = 0
    notes: str = ""


class QuorumCheckPayload(BaseModel):
    region: str
    total_replicas: int
    reachable_replicas: int


@router.get("/v1/replication/stats", tags=["Replication"])
def replication_stats() -> dict:
    from data_ai.core.replication import get_replication_engine

    return get_replication_engine().stats()


@router.get("/v1/replication/policies", tags=["Replication"])
def replication_list_policies(
    source_region: str = "",
    target_region: str = "",
    enabled: bool | None = None,
) -> dict:
    from data_ai.core.replication import get_replication_engine

    return {
        "policies": [p.to_dict() for p in get_replication_engine().list_policies(
            source_region=source_region, target_region=target_region, enabled=enabled
        )]
    }


@router.post("/v1/replication/policies", status_code=201, tags=["Replication"])
def replication_create_policy(payload: ReplicationPolicyPayload) -> dict:
    from data_ai.core.replication import ReplicationMode, get_replication_engine

    p = get_replication_engine().create_policy(
        name=payload.name,
        source_region=payload.source_region,
        target_region=payload.target_region,
        mode=ReplicationMode(payload.mode),
        resource_types=payload.resource_types,
        max_lag_sec=payload.max_lag_sec,
        encryption=payload.encryption,
        compression=payload.compression,
        metadata=payload.metadata,
    )
    return {"policy": p.to_dict()}


@router.get("/v1/replication/policies/{policy_id}", tags=["Replication"])
def replication_get_policy(policy_id: str) -> dict:
    from data_ai.core.replication import get_replication_engine

    p = get_replication_engine().get_policy(policy_id)
    if not p:
        raise HTTPException(status_code=404, detail="policy not found")
    return {"policy": p.to_dict()}


@router.delete("/v1/replication/policies/{policy_id}", status_code=204, tags=["Replication"], response_class=Response, response_model=None)
def replication_delete_policy(policy_id: str) -> None:
    from data_ai.core.replication import get_replication_engine

    if not get_replication_engine().delete_policy(policy_id):
        raise HTTPException(status_code=404, detail="policy not found")


@router.get("/v1/replication/streams", tags=["Replication"])
def replication_list_streams(
    policy_id: str = "",
    state: str | None = None,
) -> dict:
    from data_ai.core.replication import StreamState, get_replication_engine

    st = StreamState(state) if state else None
    return {"streams": [s.to_dict() for s in get_replication_engine().list_streams(policy_id=policy_id, state=st)]}


@router.get("/v1/replication/streams/{stream_id}", tags=["Replication"])
def replication_get_stream(stream_id: str) -> dict:
    from data_ai.core.replication import get_replication_engine

    s = get_replication_engine().get_stream(stream_id)
    if not s:
        raise HTTPException(status_code=404, detail="stream not found")
    return {"stream": s.to_dict()}


class StreamSyncPayload(BaseModel):
    records: int
    bytes_sent: int
    lag_sec: float = 0.0


@router.post("/v1/replication/streams/{stream_id}/sync", tags=["Replication"])
def replication_record_sync(stream_id: str, payload: StreamSyncPayload) -> dict:
    from data_ai.core.replication import get_replication_engine

    s = get_replication_engine().record_sync(stream_id, payload.records, payload.bytes_sent, payload.lag_sec)
    return {"stream": s.to_dict()}


class StreamFailurePayload(BaseModel):
    error: str
    records_lost: int = 0


@router.post("/v1/replication/streams/{stream_id}/failure", tags=["Replication"])
def replication_record_failure(stream_id: str, payload: StreamFailurePayload) -> dict:
    from data_ai.core.replication import get_replication_engine

    s = get_replication_engine().record_failure(stream_id, payload.error, payload.records_lost)
    return {"stream": s.to_dict()}


@router.post("/v1/replication/streams/{stream_id}/pause", tags=["Replication"])
def replication_pause_stream(stream_id: str) -> dict:
    from data_ai.core.replication import get_replication_engine

    return {"stream": get_replication_engine().pause_stream(stream_id).to_dict()}


@router.post("/v1/replication/streams/{stream_id}/resume", tags=["Replication"])
def replication_resume_stream(stream_id: str) -> dict:
    from data_ai.core.replication import get_replication_engine

    return {"stream": get_replication_engine().resume_stream(stream_id).to_dict()}


@router.get("/v1/replication/failovers", tags=["Replication"])
def replication_list_failovers(
    mode: str | None = None,
    state: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from data_ai.core.replication import FailoverMode, FailoverState, get_replication_engine

    m = FailoverMode(mode) if mode else None
    s = FailoverState(state) if state else None
    return {"failovers": [f.to_dict() for f in get_replication_engine().list_failovers(mode=m, state=s, limit=limit)]}


@router.post("/v1/replication/failovers", status_code=201, tags=["Replication"])
def replication_initiate_failover(payload: FailoverInitPayload) -> dict:
    from data_ai.core.replication import FailoverMode, get_replication_engine

    ev = get_replication_engine().initiate_failover(
        from_region=payload.from_region,
        to_region=payload.to_region,
        mode=FailoverMode(payload.mode),
        initiated_by=payload.initiated_by,
        reason=payload.reason,
        affected_resources=payload.affected_resources,
    )
    return {"failover": ev.to_dict()}


@router.get("/v1/replication/failovers/{failover_id}", tags=["Replication"])
def replication_get_failover(failover_id: str) -> dict:
    from data_ai.core.replication import get_replication_engine

    ev = get_replication_engine().get_failover(failover_id)
    if not ev:
        raise HTTPException(status_code=404, detail="failover not found")
    return {"failover": ev.to_dict()}


@router.post("/v1/replication/failovers/{failover_id}/advance", tags=["Replication"])
def replication_advance_failover(failover_id: str, payload: FailoverAdvancePayload) -> dict:
    from data_ai.core.replication import FailoverState, get_replication_engine

    ev = get_replication_engine().advance_failover(failover_id, FailoverState(payload.new_state), payload.notes)
    return {"failover": ev.to_dict()}


@router.post("/v1/replication/failovers/{failover_id}/complete", tags=["Replication"])
def replication_complete_failover(failover_id: str, payload: FailoverCompletePayload) -> dict:
    from data_ai.core.replication import get_replication_engine

    ev = get_replication_engine().complete_failover(
        failover_id, success=payload.success, data_loss_records=payload.data_loss_records, notes=payload.notes
    )
    return {"failover": ev.to_dict()}


@router.post("/v1/replication/failovers/{failover_id}/rollback", tags=["Replication"])
def replication_rollback_failover(failover_id: str, notes: str = "") -> dict:
    from data_ai.core.replication import get_replication_engine

    ev = get_replication_engine().rollback_failover(failover_id, notes)
    return {"failover": ev.to_dict()}


@router.post("/v1/replication/quorum-check", tags=["Replication"])
def replication_quorum_check(payload: QuorumCheckPayload) -> dict:
    from data_ai.core.replication import get_replication_engine

    return get_replication_engine().check_quorum(payload.region, payload.total_replicas, payload.reachable_replicas)


# ---------- 灾备恢复 (Recovery) ----------


class BackupSchedulePayload(BaseModel):
    name: str
    resource_type: str = "all"
    backup_type: str = "full"
    cron_expr: str = "0 2 * * *"
    retention_days: int = 30
    target_regions: list[str] = []
    storage_class: str = "standard"
    encryption: bool = True
    metadata: dict[str, Any] = {}


class BackupTriggerPayload(BaseModel):
    schedule_id: str
    record_count: int = 0
    target_region: str = ""
    metadata: dict[str, Any] = {}


class RestoreCreatePayload(BaseModel):
    backup_id: str
    target_region: str = ""
    target_resource: str = ""
    requested_by: str = ""
    reason: str = ""


class RestoreAdvancePayload(BaseModel):
    status: str
    progress_pct: float | None = None
    records_restored: int | None = None
    error: str = ""
    validation_passed: bool | None = None


class DRDrillPayload(BaseModel):
    name: str
    schedule_id: str = ""
    backup_id: str = ""
    target_region: str = ""
    rto_target_sec: float = 3600.0
    rpo_target_sec: float = 300.0
    conducted_by: str = ""
    notes: str = ""


class RetentionHoldPayload(BaseModel):
    resource_id: str
    regulation: str
    action: str = "preserve"
    hold_until: float = 0.0
    reason: str = ""
    requested_by: str = ""


@router.get("/v1/recovery/stats", tags=["Recovery"])
def recovery_stats() -> dict:
    from data_ai.core.recovery import get_recovery_engine

    return get_recovery_engine().stats()


@router.get("/v1/recovery/schedules", tags=["Recovery"])
def recovery_list_schedules(enabled: bool | None = None) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    return {"schedules": [s.to_dict() for s in get_recovery_engine().list_schedules(enabled=enabled)]}


@router.post("/v1/recovery/schedules", status_code=201, tags=["Recovery"])
def recovery_create_schedule(payload: BackupSchedulePayload) -> dict:
    from data_ai.core.recovery import BackupType, get_recovery_engine

    s = get_recovery_engine().create_schedule(
        name=payload.name,
        resource_type=payload.resource_type,
        backup_type=BackupType(payload.backup_type),
        cron_expr=payload.cron_expr,
        retention_days=payload.retention_days,
        target_regions=payload.target_regions,
        storage_class=payload.storage_class,
        encryption=payload.encryption,
        metadata=payload.metadata,
    )
    return {"schedule": s.to_dict()}


@router.get("/v1/recovery/schedules/{schedule_id}", tags=["Recovery"])
def recovery_get_schedule(schedule_id: str) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    s = get_recovery_engine().get_schedule(schedule_id)
    if not s:
        raise HTTPException(status_code=404, detail="schedule not found")
    return {"schedule": s.to_dict()}


@router.delete("/v1/recovery/schedules/{schedule_id}", status_code=204, tags=["Recovery"], response_class=Response, response_model=None)
def recovery_delete_schedule(schedule_id: str) -> None:
    from data_ai.core.recovery import get_recovery_engine

    if not get_recovery_engine().delete_schedule(schedule_id):
        raise HTTPException(status_code=404, detail="schedule not found")


@router.post("/v1/recovery/schedules/{schedule_id}/trigger", status_code=201, tags=["Recovery"])
def recovery_trigger_backup(schedule_id: str, payload: BackupTriggerPayload) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    b = get_recovery_engine().trigger_backup(
        payload.schedule_id or schedule_id,
        record_count=payload.record_count,
        target_region=payload.target_region,
        metadata=payload.metadata,
    )
    return {"backup": b.to_dict()}


@router.get("/v1/recovery/backups", tags=["Recovery"])
def recovery_list_backups(
    schedule_id: str = "",
    status: str | None = None,
    region: str = "",
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from data_ai.core.recovery import BackupStatus, get_recovery_engine

    st = BackupStatus(status) if status else None
    return {"backups": [b.to_dict() for b in get_recovery_engine().list_backups(
        schedule_id=schedule_id, status=st, region=region, limit=limit
    )]}


@router.get("/v1/recovery/backups/{backup_id}", tags=["Recovery"])
def recovery_get_backup(backup_id: str) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    b = get_recovery_engine().get_backup(backup_id)
    if not b:
        raise HTTPException(status_code=404, detail="backup not found")
    return {"backup": b.to_dict()}


@router.get("/v1/recovery/backups/{backup_id}/verify", tags=["Recovery"])
def recovery_verify_backup(backup_id: str) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    return get_recovery_engine().verify_backup(backup_id)


@router.post("/v1/recovery/expire-old", tags=["Recovery"])
def recovery_expire_old() -> dict:
    from data_ai.core.recovery import get_recovery_engine

    return {"expired_count": get_recovery_engine().expire_old_backups()}


@router.post("/v1/recovery/restore", status_code=201, tags=["Recovery"])
def recovery_create_restore(payload: RestoreCreatePayload) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    j = get_recovery_engine().create_restore(
        backup_id=payload.backup_id,
        target_region=payload.target_region,
        target_resource=payload.target_resource,
        requested_by=payload.requested_by,
        reason=payload.reason,
    )
    return {"restore": j.to_dict()}


@router.post("/v1/recovery/restore/{restore_id}/advance", tags=["Recovery"])
def recovery_advance_restore(restore_id: str, payload: RestoreAdvancePayload) -> dict:
    from data_ai.core.recovery import RestoreStatus, get_recovery_engine

    j = get_recovery_engine().advance_restore(
        restore_id,
        RestoreStatus(payload.status),
        progress_pct=payload.progress_pct,
        records_restored=payload.records_restored,
        error=payload.error,
        validation_passed=payload.validation_passed,
    )
    return {"restore": j.to_dict()}


@router.get("/v1/recovery/restores", tags=["Recovery"])
def recovery_list_restores(
    backup_id: str = "",
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from data_ai.core.recovery import RestoreStatus, get_recovery_engine

    st = RestoreStatus(status) if status else None
    return {"restores": [j.to_dict() for j in get_recovery_engine().list_restores(
        backup_id=backup_id, status=st, limit=limit
    )]}


@router.post("/v1/recovery/drill", status_code=201, tags=["Recovery"])
def recovery_run_drill(payload: DRDrillPayload) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    d = get_recovery_engine().run_drill(
        name=payload.name,
        schedule_id=payload.schedule_id,
        backup_id=payload.backup_id,
        target_region=payload.target_region,
        rto_target_sec=payload.rto_target_sec,
        rpo_target_sec=payload.rpo_target_sec,
        conducted_by=payload.conducted_by,
        notes=payload.notes,
    )
    return {"drill": d.to_dict()}


@router.get("/v1/recovery/drills", tags=["Recovery"])
def recovery_list_drills(
    result: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from data_ai.core.recovery import DrillResult, get_recovery_engine

    r = DrillResult(result) if result else None
    return {"drills": [d.to_dict() for d in get_recovery_engine().list_drills(result=r, limit=limit)]}


@router.post("/v1/recovery/holds", status_code=201, tags=["Recovery"])
def recovery_create_hold(payload: RetentionHoldPayload) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    h = get_recovery_engine().create_hold(
        resource_id=payload.resource_id,
        regulation=payload.regulation,
        action=payload.action,  # type: ignore[arg-type]
        hold_until=payload.hold_until,
        reason=payload.reason,
        requested_by=payload.requested_by,
    )
    return {"hold": h.to_dict()}


@router.get("/v1/recovery/holds", tags=["Recovery"])
def recovery_list_holds(
    resource_id: str = "",
    regulation: str = "",
    active_only: bool = False,
) -> dict:
    from data_ai.core.recovery import get_recovery_engine

    return {"holds": [h.to_dict() for h in get_recovery_engine().list_holds(
        resource_id=resource_id, regulation=regulation, active_only=active_only
    )]}


@router.get("/v1/recovery/check-action", tags=["Recovery"])
def recovery_check_action(resource_id: str, action: str = "delete") -> dict:
    from data_ai.core.recovery import get_recovery_engine

    return get_recovery_engine().check_resource_action(resource_id, action)  # type: ignore[arg-type]


# ---------- SLA 违约赔付 (Compensation) ----------


class CompensationPolicyPayload(BaseModel):
    name: str
    plan_tier: str = "enterprise"
    target_availability_pct: float = 99.9
    measurement_window_days: int = 30
    tiers: list[dict[str, Any]] = []
    max_credit_pct: float = 100.0
    monthly_cap_pct: float = 100.0
    auto_apply: bool = True


class BreachDetectPayload(BaseModel):
    policy_id: str
    tenant_id: str
    actual_availability_pct: float
    downtime_sec: float = 0.0
    measurement_start: float = 0.0
    measurement_end: float = 0.0
    related_incident_ids: list[str] = []
    affected_components: list[str] = []
    description: str = ""


class CreditCalculatePayload(BaseModel):
    breach_id: str
    monthly_fee_usd: float


class DisputeRaisePayload(BaseModel):
    credit_id: str
    tenant_id: str
    raised_by: str
    reason: str
    evidence: dict[str, Any] = {}


class DisputeResolvePayload(BaseModel):
    resolution: str
    resolved_by: str = ""
    uphold_credit: bool = True


@router.get("/v1/compensation/stats", tags=["Compensation"])
def compensation_stats() -> dict:
    from data_ai.core.sla import get_compensation_engine

    return get_compensation_engine().stats()


@router.get("/v1/compensation/policies", tags=["Compensation"])
def compensation_list_policies(plan_tier: str = "") -> dict:
    from data_ai.core.sla import get_compensation_engine

    return {"policies": [p.to_dict() for p in get_compensation_engine().list_policies(plan_tier=plan_tier)]}


@router.post("/v1/compensation/policies", status_code=201, tags=["Compensation"])
def compensation_create_policy(payload: CompensationPolicyPayload) -> dict:
    from data_ai.core.sla import CompensationTier, get_compensation_engine

    tiers = [CompensationTier(**t) for t in payload.tiers]
    p = get_compensation_engine().create_policy(
        name=payload.name,
        plan_tier=payload.plan_tier,
        target_availability_pct=payload.target_availability_pct,
        measurement_window_days=payload.measurement_window_days,
        tiers=tiers,
        max_credit_pct=payload.max_credit_pct,
        monthly_cap_pct=payload.monthly_cap_pct,
        auto_apply=payload.auto_apply,
    )
    return {"policy": p.to_dict()}


@router.get("/v1/compensation/policies/{policy_id}", tags=["Compensation"])
def compensation_get_policy(policy_id: str) -> dict:
    from data_ai.core.sla import get_compensation_engine

    p = get_compensation_engine().get_policy(policy_id)
    if not p:
        raise HTTPException(status_code=404, detail="policy not found")
    return {"policy": p.to_dict()}


@router.post("/v1/compensation/breach", status_code=201, tags=["Compensation"])
def compensation_detect_breach(payload: BreachDetectPayload) -> dict:
    from data_ai.core.sla import get_compensation_engine

    b = get_compensation_engine().detect_breach(
        policy_id=payload.policy_id,
        tenant_id=payload.tenant_id,
        actual_availability_pct=payload.actual_availability_pct,
        downtime_sec=payload.downtime_sec,
        measurement_start=payload.measurement_start,
        measurement_end=payload.measurement_end,
        related_incident_ids=payload.related_incident_ids,
        affected_components=payload.affected_components,
        description=payload.description,
    )
    return {"breach": b.to_dict()}


@router.get("/v1/compensation/breaches", tags=["Compensation"])
def compensation_list_breaches(
    tenant_id: str = "",
    severity: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from data_ai.core.sla import BreachSeverity, get_compensation_engine

    sev = BreachSeverity(severity) if severity else None
    return {"breaches": [b.to_dict() for b in get_compensation_engine().list_breaches(
        tenant_id=tenant_id, severity=sev, limit=limit
    )]}


@router.post("/v1/compensation/calculate", status_code=201, tags=["Compensation"])
def compensation_calculate(payload: CreditCalculatePayload) -> dict:
    from data_ai.core.sla import get_compensation_engine

    c = get_compensation_engine().calculate_credit(payload.breach_id, payload.monthly_fee_usd)
    return {"credit": c.to_dict()}


@router.post("/v1/compensation/credits/{credit_id}/apply", tags=["Compensation"])
def compensation_apply_credit(credit_id: str) -> dict:
    from data_ai.core.sla import get_compensation_engine

    c = get_compensation_engine().apply_credit(credit_id)
    if not c:
        raise HTTPException(status_code=404, detail="credit not found")
    return {"credit": c.to_dict()}


@router.post("/v1/compensation/credits/{credit_id}/pay", tags=["Compensation"])
def compensation_mark_paid(credit_id: str) -> dict:
    from data_ai.core.sla import get_compensation_engine

    c = get_compensation_engine().mark_paid(credit_id)
    if not c:
        raise HTTPException(status_code=404, detail="credit not found")
    return {"credit": c.to_dict()}


@router.post("/v1/compensation/credits/{credit_id}/reject", tags=["Compensation"])
def compensation_reject_credit(credit_id: str, reason: str = "") -> dict:
    from data_ai.core.sla import get_compensation_engine

    c = get_compensation_engine().reject_credit(credit_id, reason)
    if not c:
        raise HTTPException(status_code=404, detail="credit not found")
    return {"credit": c.to_dict()}


@router.get("/v1/compensation/credits", tags=["Compensation"])
def compensation_list_credits(
    tenant_id: str = "",
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from data_ai.core.sla import CreditStatus, get_compensation_engine

    st = CreditStatus(status) if status else None
    return {"credits": [c.to_dict() for c in get_compensation_engine().list_credits(
        tenant_id=tenant_id, status=st, limit=limit
    )]}


@router.post("/v1/compensation/dispute", status_code=201, tags=["Compensation"])
def compensation_raise_dispute(payload: DisputeRaisePayload) -> dict:
    from data_ai.core.sla import get_compensation_engine

    d = get_compensation_engine().raise_dispute(
        credit_id=payload.credit_id,
        tenant_id=payload.tenant_id,
        raised_by=payload.raised_by,
        reason=payload.reason,
        evidence=payload.evidence,
    )
    return {"dispute": d.to_dict()}


@router.post("/v1/compensation/dispute/{dispute_id}/resolve", tags=["Compensation"])
def compensation_resolve_dispute(dispute_id: str, payload: DisputeResolvePayload) -> dict:
    from data_ai.core.sla import get_compensation_engine

    d = get_compensation_engine().resolve_dispute(
        dispute_id, payload.resolution, payload.resolved_by, payload.uphold_credit
    )
    if not d:
        raise HTTPException(status_code=404, detail="dispute not found")
    return {"dispute": d.to_dict()}


@router.get("/v1/compensation/disputes", tags=["Compensation"])
def compensation_list_disputes(
    tenant_id: str = "",
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    from data_ai.core.sla import DisputeStatus, get_compensation_engine

    st = DisputeStatus(status) if status else None
    return {"disputes": [d.to_dict() for d in get_compensation_engine().list_disputes(
        tenant_id=tenant_id, status=st, limit=limit
    )]}


@router.get("/v1/compensation/tenant-summary", tags=["Compensation"])
def compensation_tenant_summary(
    tenant_id: str = Query(...),
    period_start: float = Query(...),
    period_end: float = Query(...),
) -> dict:
    from data_ai.core.sla import get_compensation_engine

    return get_compensation_engine().tenant_summary(tenant_id, period_start, period_end)
