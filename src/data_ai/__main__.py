"""
DATA-AI CLI 入口 (P1-9 完整化)

P1-9 整改:补全 Web/CLI/Python 三层控制,新增如下子命令,覆盖 8 大能力:

现有保留:
    version / list-models / chat / rag

新增:
    health                — 后端健康/诊断
    agent                 — Agent CRUD + run + delegate-many + presets
    team                  — Team CRUD + run + messages
    memory                — Memory CRUD + search
    skill                 — Skill CRUD + execute + extract
    tools                 — Tool list + execute
    sandbox               — Sandbox CRUD + execute + files + snapshots
    mcp                   — MCP server CRUD + preset + tools + invoke
    reasoning             — CoT / reflection / hypothesis
    notifications         — list / mark-read
    sessions              — list / create / delete
    office                — word/ppt/excel/pdf 子命令
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

# ════════════════════════════════════════════════════════════════════════════
# 共用
# ════════════════════════════════════════════════════════════════════════════

console = Console()
err_console = Console(stderr=True)


def _get_client(ctx: typer.Context) -> Any:
    """从 typer Context 拿共享的 DataAIClient,未指定时新建。"""
    client = getattr(ctx.obj, "client", None) if ctx.obj else None
    if client is None:
        from data_ai import create_api_client

        client = create_api_client()
    return client


def _print_json(obj: Any) -> None:
    console.print_json(data=obj)


def _print_table(headers: list[str], rows: list[list[Any]], title: str | None = None) -> None:
    t = Table(title=title, show_header=True, header_style="bold cyan")
    for h in headers:
        t.add_column(h, overflow="fold")
    for row in rows:
        t.add_row(*[str(c) if c is not None else "" for c in row])
    console.print(t)


def _err(e: Exception) -> None:
    if hasattr(e, "trace_id") and e.trace_id:
        err_console.print(f"[red]Error[/red] ({e.trace_id}): {e}")
    else:
        err_console.print(f"[red]Error[/red]: {e}")
    raise typer.Exit(code=1)


# ════════════════════════════════════════════════════════════════════════════
# 顶层 app
# ════════════════════════════════════════════════════════════════════════════

app = typer.Typer(
    name="data-ai",
    help="DATA-AI: Production-grade AI Agent Framework",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# 子命令分组
agents_app = typer.Typer(help="Agent 智能体管理 (CRUD + run + delegate + presets)")
teams_app = typer.Typer(help="Team 多 agent 协作")
memory_app = typer.Typer(help="Memory 记忆管理")
skills_app = typer.Typer(help="Skill 技能管理")
tools_app = typer.Typer(help="Tool 工具")
sandbox_app = typer.Typer(help="Sandbox 沙箱")
mcp_app = typer.Typer(help="MCP (Model Context Protocol) 服务")
reasoning_app = typer.Typer(help="Reasoning CoT 思维链/反思/假设")
office_app = typer.Typer(help="Office Word/PPT/Excel/PDF 操作")
audit_app = typer.Typer(help="Audit 审计日志查询 / 导出")
quota_app = typer.Typer(help="Quota 用量/配额策略管理")
webhooks_app = typer.Typer(help="Webhooks 事件订阅管理")
cron_app = typer.Typer(help="Cron 定时任务调度")

app.add_typer(agents_app, name="agent")
app.add_typer(teams_app, name="team")
app.add_typer(memory_app, name="memory")
app.add_typer(skills_app, name="skill")
app.add_typer(tools_app, name="tools")
app.add_typer(sandbox_app, name="sandbox")
app.add_typer(mcp_app, name="mcp")
app.add_typer(reasoning_app, name="reasoning")
app.add_typer(office_app, name="office")
app.add_typer(audit_app, name="audit")
app.add_typer(quota_app, name="quota")
app.add_typer(webhooks_app, name="webhooks")
app.add_typer(cron_app, name="cron")


# ════════════════════════════════════════════════════════════════════════════
# 1. version / list-models / health
# ════════════════════════════════════════════════════════════════════════════


@app.command()
def version():
    """显示 DATA-AI 版本。"""
    from data_ai import __version__

    console.print(f"[bold green]DATA-AI[/bold green] version [bold]{__version__}[/bold]")


@app.command("list-models")
def list_models():
    """列出已注册的 LLM 模型。"""
    from data_ai import get_llm_manager

    manager = get_llm_manager()
    # 没启动 server 时本地 manager 是空的, 退化为注册离线占位模型
    if not manager.list_models():
        _ensure_offline_models_registered(manager)
    models = manager.list_models()
    if not models:
        console.print("[yellow]No models registered[/yellow]")
        return
    t = Table(title="Registered Models")
    t.add_column("Name", style="cyan")
    t.add_column("Default", style="green")
    default = manager.get_default_model()
    for m in models:
        t.add_row(m, "✓" if m == default else "")
    console.print(t)


def _ensure_offline_models_registered(manager) -> None:
    """CLI 在没启 server 时, 也保证至少有 3 个 offline 占位模型可用."""
    try:
        from data_ai.core.llm.manager import ModelConfig, ModelProvider
    except Exception:
        return
    for mid, mname, default in (
        ("offline-chat", "data-ai-offline", True),
        ("offline-fast", "data-ai-offline-fast", False),
        ("offline-mini", "data-ai-offline-mini", False),
    ):
        if mid in manager.list_models():
            continue
        try:
            manager.register_model(
                mid,
                ModelConfig(provider=ModelProvider.OFFLINE, model_name=mname),
                set_default=default,
            )
        except Exception:
            # 已注册 / 单例冲突等小情况直接忽略
            pass


@app.command()
def health(
    ctx: typer.Context,
    detailed: bool = typer.Option(False, "--detailed", "-d", help="输出 extensions_health 详情"),
):
    """查看后端健康状态。"""
    try:
        c = _get_client(ctx)
        if detailed:
            _print_json(c.extensions_health())
        else:
            _print_json(c.health())
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 2. chat (保留 + 支持 streaming + thinking)
# ════════════════════════════════════════════════════════════════════════════


@app.command()
def chat(
    message: str | None = typer.Argument(None, help="直接发一条消息"),
    model: str = typer.Option("qwen-turbo", "--model", "-m", help="Model id"),
    provider: str = typer.Option("qwen", "--provider", "-p", help="Provider"),
    api_key: str | None = typer.Option(None, "--api-key", "-k"),
    system: str = typer.Option("", "--system", "-s"),
    stream: bool = typer.Option(True, "--stream/--no-stream"),
    enable_thinking: bool = typer.Option(False, "--think/--no-think", help="深度思考模式"),
    max_tokens: int | None = typer.Option(None, "--max-tokens"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url", "-u"),
    backend_api_key: str | None = typer.Option(None, "--backend-key", help="后端 API key"),
):
    """通过后端 API 跟 LLM 对话(单条 / 交互式)。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_api_key)
        console.print(
            Panel.fit(
                f"[bold]DATA-AI Chat[/bold]\nModel: {model}\nBackend: {base_url}\n"
                f"Stream: {stream} · Thinking: {enable_thinking}",
                title="Session",
            )
        )

        if message:
            # 单条模式
            if stream:
                for chunk in client.chat_stream(
                    message,
                    model=model,
                    system=system or None,
                    enable_thinking=enable_thinking,
                    max_tokens=max_tokens,
                ):
                    console.print(chunk, end="")
                console.print()
            else:
                r = client.chat(
                    message,
                    model=model,
                    system=system or None,
                    enable_thinking=enable_thinking,
                    max_tokens=max_tokens,
                )
                _print_json(r)
            return

        # 交互式
        msgs: list[dict[str, str]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        while True:
            try:
                user_input = Prompt.ask("\n[bold green]You[/bold green]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold]Goodbye![/bold]")
                break
            if user_input.lower() in ("exit", "quit", "/exit", "/quit"):
                console.print("[bold]Goodbye![/bold]")
                break
            try:
                msgs.append({"role": "user", "content": user_input})
                if stream:
                    console.print("[bold blue]Assistant[/bold blue]: ", end="")
                    full = ""
                    for chunk in client.chat_stream(
                        msgs,
                        model=model,
                        enable_thinking=enable_thinking,
                        max_tokens=max_tokens,
                    ):
                        console.print(chunk, end="")
                        full += chunk
                    console.print()
                    msgs.append({"role": "assistant", "content": full})
                else:
                    with console.status("[bold blue]Thinking...[/bold blue]"):
                        r = client.chat(
                            msgs,
                            model=model,
                            enable_thinking=enable_thinking,
                            max_tokens=max_tokens,
                        )
                    content = r.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if not content:
                        # 也可能不是 openai 格式
                        content = r.get("content", "")
                    console.print("\n[bold blue]Assistant[/bold blue]:")
                    console.print(Markdown(content))
                    msgs.append({"role": "assistant", "content": content})
            except Exception as e:
                _err(e)
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 3. rag (保留 + 加 search)
# ════════════════════════════════════════════════════════════════════════════


@app.command()
def rag(
    list_: bool = typer.Option(False, "--list", "-l", help="列已上传文档"),
    upload: str | None = typer.Option(None, "--upload", "-u", help="上传文件路径"),
    query: str | None = typer.Option(None, "--query", "-q", help="检索 query"),
    doc_id: str | None = typer.Option(None, "--doc-id", help="按 doc_id 检索"),
    top_k: int = typer.Option(5, "--top-k", "-k"),
    delete: str | None = typer.Option(None, "--delete", help="按 doc_id 删除"),
    embedder: str | None = typer.Option(None, "--embedder", "-e"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """RAG 知识库: 上传 / 检索 / 列表 / 删除。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)

        if list_:
            r = client.list_rag_documents()
            docs = r.get("data", [])
            t = Table(title=f"RAG 文档 ({len(docs)})")
            t.add_column("ID", style="cyan")
            t.add_column("Name")
            t.add_column("Chunks", justify="right")
            t.add_column("Status")
            for d in docs:
                t.add_row(
                    (d.get("id", "") or "")[:16],
                    d.get("name", ""),
                    str(d.get("chunks", "")),
                    d.get("status", ""),
                )
            console.print(t)
        if upload:
            console.print(f"[dim]Uploading {upload}...[/dim]")
            r = client.upload_rag_document(upload)
            _print_json(r)
        if query:
            r = client.search_rag(query, top_k=top_k, embedder=embedder, document_ids=[doc_id] if doc_id else None)
            _print_json(r)
        if delete:
            client.delete_rag_document(delete)
            console.print(f"[green]Deleted {delete}[/green]")
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 4. agent
# ════════════════════════════════════════════════════════════════════════════


@agents_app.command("list")
def agent_list(
    q: str | None = typer.Option(None, "--query", "-q"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """列出所有 Agent。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_agents(q=q)
        agents = r.get("data", [])
        t = Table(title=f"Agent 列表 ({len(agents)})")
        t.add_column("ID", style="cyan")
        t.add_column("Name")
        t.add_column("Model")
        t.add_column("Status")
        t.add_column("Tools")
        for a in agents:
            t.add_row(
                (a.get("id", "") or "")[:16],
                a.get("name", ""),
                a.get("model", ""),
                a.get("status", ""),
                ",".join(a.get("tool_names", []) or []),
            )
        console.print(t)
    except Exception as e:
        _err(e)


@agents_app.command("presets")
def agent_presets(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """列出可用的 Agent 预设角色。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_agent_presets()
        presets = r.get("data", [])
        t = Table(title=f"Agent 预设 ({len(presets)})")
        t.add_column("Role", style="cyan")
        t.add_column("Name")
        t.add_column("Description")
        t.add_column("Tools", style="green")
        for p in presets:
            t.add_row(
                p.get("role", ""),
                p.get("name", ""),
                p.get("description", ""),
                ",".join(p.get("tools", []) or []),
            )
        console.print(t)
    except Exception as e:
        _err(e)


@agents_app.command("create")
def agent_create(
    name: str = typer.Option(..., "--name", "-n"),
    model: str = typer.Option("qwen-turbo", "--model", "-m"),
    preset: str | None = typer.Option(None, "--preset", "-p", help="套预设角色"),
    system: str = typer.Option("", "--system", "-s"),
    description: str = typer.Option("", "--description", "-d"),
    tools_: str = typer.Option("", "--tools", help="工具名逗号分隔"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """创建 Agent。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.create_agent(
            name=name,
            model=model,
            system_prompt=system,
            description=description,
            tool_names=[t.strip() for t in tools_.split(",") if t.strip()],
            preset=preset,
        )
        _print_json(r)
    except Exception as e:
        _err(e)


@agents_app.command("run")
def agent_run(
    agent_id: str = typer.Option(..., "--id", "-i"),
    input: str = typer.Option(..., "--input", "-p"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """运行 Agent。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.run_agent(agent_id, input)
        _print_json(r)
    except Exception as e:
        _err(e)


@agents_app.command("delete")
def agent_delete(
    agent_id: str = typer.Option(..., "--id", "-i"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """删除 Agent。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        client.delete_agent(agent_id)
        console.print(f"[green]Deleted {agent_id}[/green]")
    except Exception as e:
        _err(e)


@agents_app.command("delegate")
def agent_delegate(
    query: str = typer.Option(..., "--query", "-q"),
    role: str = typer.Option("secretary", "--role", "-r"),
    model: str | None = typer.Option(None, "--model", "-m"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """委派一个子任务。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.delegate_many([{"query": query, "role": role}], model=model)
        _print_json(r)
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 5. team
# ════════════════════════════════════════════════════════════════════════════


@teams_app.command("list")
def team_list(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_teams()
        teams = r.get("data", [])
        t = Table(title=f"Team 列表 ({len(teams)})")
        t.add_column("ID", style="cyan")
        t.add_column("Name")
        t.add_column("Mode")
        t.add_column("Members", justify="right")
        for tm in teams:
            t.add_row(
                (tm.get("id", "") or "")[:16],
                tm.get("name", ""),
                tm.get("mode", ""),
                str(len(tm.get("members", []) or [])),
            )
        console.print(t)
    except Exception as e:
        _err(e)


@teams_app.command("create")
def team_create(
    name: str = typer.Option(..., "--name", "-n"),
    members: str = typer.Option(..., "--members", help="JSON 字符串或 name:role,weight 列表"),
    mode: str = typer.Option("collaboration", "--mode", "-m"),
    consensus: str = typer.Option("llm_synthesis", "--consensus", "-c"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        if members.startswith("["):
            parsed = json.loads(members)
        else:
            # name:role,weight 格式
            parsed = []
            for idx, item in enumerate(members.split(";")):
                parts = item.split(":")
                if len(parts) >= 2:
                    mname, mrole = parts[0].strip(), parts[1].strip()
                    mweight = float(parts[2]) if len(parts) > 2 else 1.0
                else:
                    mname, mrole, mweight = parts[0].strip(), "member", 1.0
                parsed.append({"name": mname, "role": mrole, "weight": mweight})
        r = client.create_team(name=name, members=parsed, mode=mode, consensus_method=consensus)
        _print_json(r)
    except Exception as e:
        _err(e)


@teams_app.command("run")
def team_run(
    team_id: str = typer.Option(..., "--id", "-i"),
    input: str = typer.Option(..., "--input", "-p"),
    consensus: str | None = typer.Option(None, "--consensus", "-c"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.run_team(team_id, input, consensus_method=consensus)
        _print_json(r)
    except Exception as e:
        _err(e)


@teams_app.command("delete")
def team_delete(
    team_id: str = typer.Option(..., "--id", "-i"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        client.delete_team(team_id)
        console.print(f"[green]Deleted {team_id}[/green]")
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 6. memory
# ════════════════════════════════════════════════════════════════════════════


@memory_app.command("list")
def memory_list(
    type: str | None = typer.Option(None, "--type", "-t"),
    q: str | None = typer.Option(None, "--query", "-q"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_memories(type=type, q=q)
        items = r.get("data", [])
        t = Table(title=f"Memory ({len(items)})")
        t.add_column("ID", style="cyan")
        t.add_column("Type")
        t.add_column("Content", overflow="fold")
        t.add_column("Tags")
        for m in items:
            t.add_row(
                (m.get("id", "") or "")[:16],
                m.get("type", ""),
                (m.get("content", "") or "")[:100],
                ",".join(m.get("tags", []) or []),
            )
        console.print(t)
    except Exception as e:
        _err(e)


@memory_app.command("add")
def memory_add(
    content: str = typer.Option(..., "--content", "-c"),
    type: str = typer.Option("note", "--type", "-t"),
    tags: str = typer.Option("", "--tags", help="逗号分隔"),
    importance: float = typer.Option(0.5, "--importance", "-i"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.create_memory(
            content=content,
            type=type,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            importance=importance,
        )
        _print_json(r)
    except Exception as e:
        _err(e)


@memory_app.command("search")
def memory_search(
    query: str = typer.Option(..., "--query", "-q"),
    type: str | None = typer.Option(None, "--type", "-t"),
    top_k: int = typer.Option(5, "--top-k", "-k"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.search_memory(query, type=type, top_k=top_k)
        _print_json(r)
    except Exception as e:
        _err(e)


@memory_app.command("delete")
def memory_delete(
    memory_id: str = typer.Option(..., "--id", "-i"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        client.delete_memory(memory_id)
        console.print(f"[green]Deleted {memory_id}[/green]")
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 7. skill
# ════════════════════════════════════════════════════════════════════════════


@skills_app.command("list")
def skill_list(
    category: str | None = typer.Option(None, "--category", "-c"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_skills(category=category)
        items = r.get("data", [])
        t = Table(title=f"Skill ({len(items)})")
        t.add_column("Name", style="cyan")
        t.add_column("Version")
        t.add_column("Category")
        t.add_column("Description", overflow="fold")
        for s in items:
            t.add_row(
                s.get("name", ""),
                s.get("version", ""),
                s.get("category", ""),
                (s.get("description", "") or "")[:100],
            )
        console.print(t)
    except Exception as e:
        _err(e)


@skills_app.command("create")
def skill_create(
    name: str = typer.Option(..., "--name", "-n"),
    description: str = typer.Option("", "--description", "-d"),
    category: str = typer.Option("custom", "--category", "-c"),
    implementation: str | None = typer.Option(None, "--impl", help="Python 实现代码"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.create_skill(
            name=name,
            description=description,
            category=category,
            implementation=implementation,
        )
        _print_json(r)
    except Exception as e:
        _err(e)


@skills_app.command("execute")
def skill_execute(
    name: str = typer.Option(..., "--name", "-n"),
    parameters: str = typer.Option("{}", "--params", "-p", help="JSON 字符串"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        params = json.loads(parameters) if parameters else {}
        r = client.execute_skill(name, parameters=params)
        _print_json(r)
    except Exception as e:
        _err(e)


@skills_app.command("extract")
def skill_extract(
    source: str = typer.Option(..., "--source", "-s"),
    source_type: str = typer.Option("text", "--type", "-t"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.extract_skill(source, source_type=source_type)
        _print_json(r)
    except Exception as e:
        _err(e)


@skills_app.command("delete")
def skill_delete(
    name: str = typer.Option(..., "--name", "-n"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        client.delete_skill(name)
        console.print(f"[green]Deleted {name}[/green]")
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 8. tools
# ════════════════════════════════════════════════════════════════════════════


@tools_app.command("list")
def tools_list(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_tools()
        tools = r.get("data", [])
        t = Table(title=f"Tool ({len(tools)})")
        t.add_column("Name", style="cyan")
        t.add_column("Category")
        t.add_column("Description", overflow="fold")
        for tool in tools:
            t.add_row(
                tool.get("name", ""),
                tool.get("category", ""),
                (tool.get("description", "") or "")[:100],
            )
        console.print(t)
    except Exception as e:
        _err(e)


@tools_app.command("exec")
def tools_exec(
    name: str = typer.Option(..., "--name", "-n"),
    parameters: str = typer.Option("{}", "--params", "-p"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        params = json.loads(parameters) if parameters else {}
        r = client.execute_tool(name, parameters=params)
        _print_json(r)
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 9. sandbox
# ════════════════════════════════════════════════════════════════════════════


@sandbox_app.command("list")
def sandbox_list(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_sandboxes()
        items = r.get("data", [])
        t = Table(title=f"Sandbox ({len(items)})")
        t.add_column("ID", style="cyan")
        t.add_column("Name")
        t.add_column("Type")
        t.add_column("Status")
        for s in items:
            t.add_row(
                (s.get("id", "") or "")[:16],
                s.get("name", ""),
                s.get("type", ""),
                s.get("status", ""),
            )
        console.print(t)
    except Exception as e:
        _err(e)


@sandbox_app.command("create")
def sandbox_create(
    name: str = typer.Option(..., "--name", "-n"),
    type: str = typer.Option("local", "--type", "-t"),
    timeout: int = typer.Option(30, "--timeout"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.create_sandbox(name=name, type=type, timeout=timeout)
        _print_json(r)
    except Exception as e:
        _err(e)


@sandbox_app.command("exec")
def sandbox_exec(
    sandbox_id: str = typer.Option(..., "--id", "-i"),
    code: str = typer.Option(..., "--code", "-c"),
    language: str = typer.Option("python", "--lang", "-l"),
    timeout: int = typer.Option(30, "--timeout"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.execute_in_sandbox(sandbox_id, language, code, timeout=timeout)
        _print_json(r)
    except Exception as e:
        _err(e)


@sandbox_app.command("delete")
def sandbox_delete(
    sandbox_id: str = typer.Option(..., "--id", "-i"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        client.delete_sandbox(sandbox_id)
        console.print(f"[green]Deleted {sandbox_id}[/green]")
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 10. mcp
# ════════════════════════════════════════════════════════════════════════════


@mcp_app.command("list")
def mcp_list(
    include_tools: bool = typer.Option(False, "--tools/--no-tools"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_mcp_servers(include_tools=include_tools)
        items = r.get("data", [])
        t = Table(title=f"MCP Servers ({len(items)})")
        t.add_column("ID", style="cyan")
        t.add_column("Name")
        t.add_column("Type")
        t.add_column("Status")
        t.add_column("Tools", justify="right")
        for s in items:
            t.add_row(
                s.get("id", ""),
                s.get("name", ""),
                s.get("type", ""),
                s.get("status", ""),
                str(len(s.get("tools", []) or [])),
            )
        console.print(t)
    except Exception as e:
        _err(e)


@mcp_app.command("presets")
def mcp_presets(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.list_mcp_presets()
        items = r.get("data", [])
        t = Table(title=f"MCP Presets ({len(items)})")
        t.add_column("ID", style="cyan")
        t.add_column("Name")
        t.add_column("Type")
        for s in items:
            t.add_row(s.get("id", ""), s.get("name", ""), s.get("type", ""))
        console.print(t)
    except Exception as e:
        _err(e)


@mcp_app.command("invoke")
def mcp_invoke(
    server_id: str = typer.Option(..., "--server", "-s"),
    tool_name: str = typer.Option(..., "--tool", "-t"),
    arguments: str = typer.Option("{}", "--args", "-a", help="JSON 字符串"),
    timeout: float = typer.Option(30.0, "--timeout"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        args = json.loads(arguments) if arguments else {}
        r = client.invoke_mcp_tool(server_id, tool_name, args, timeout=timeout)
        _print_json(r)
    except Exception as e:
        _err(e)


@mcp_app.command("install")
def mcp_install(
    preset_id: str = typer.Argument(..., help="preset id (e.g. mcp-filesystem)"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.install_mcp_preset(preset_id)
        _print_json(r)
    except Exception as e:
        _err(e)


@mcp_app.command("health")
def mcp_health(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        _print_json(client.mcp_health())
    except Exception as e:
        _err(e)


@mcp_app.command("create")
def mcp_create(
    name: str = typer.Option(..., "--name", "-n"),
    type: str = typer.Option("stdio", "--type", "-t"),
    command: str = typer.Option("", "--cmd", help="stdio command"),
    url: str = typer.Option("", "--url"),
    args: str = typer.Option("", "--args", help="逗号分隔"),
    env: str = typer.Option("", "--env", help="k=v,k=v"),
    description: str = typer.Option("", "--description", "-d"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        arg_list = [a.strip() for a in args.split(",") if a.strip()]
        env_dict = {}
        for kv in env.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                env_dict[k.strip()] = v.strip()
        r = client.create_mcp_server(
            name=name,
            type=type,
            command=command,
            url=url,
            args=arg_list,
            env=env_dict,
            description=description,
        )
        _print_json(r)
    except Exception as e:
        _err(e)


@mcp_app.command("delete")
def mcp_delete(
    server_id: str = typer.Argument(...),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        client.delete_mcp_server(server_id)
        console.print(f"[green]Deleted {server_id}[/green]")
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 11. reasoning
# ════════════════════════════════════════════════════════════════════════════


@reasoning_app.command("methods")
def reasoning_methods(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        _print_json(client.reasoning_methods())
    except Exception as e:
        _err(e)


@reasoning_app.command("sequential")
def reasoning_sequential(
    question: str = typer.Option(..., "--question", "-q"),
    context: str | None = typer.Option(None, "--context", "-c"),
    max_steps: int = typer.Option(5, "--max-steps"),
    no_llm: bool = typer.Option(False, "--no-llm", help="不用 LLM 走 fallback"),
    model: str | None = typer.Option(None, "--model", "-m"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.reasoning_sequential(
            question,
            context=context,
            max_steps=max_steps,
            use_llm=not no_llm,
            model=model,
        )
        _print_json(r)
    except Exception as e:
        _err(e)


@reasoning_app.command("reflection")
def reasoning_reflection(
    question: str = typer.Option(..., "--question", "-q"),
    draft: str = typer.Option(..., "--draft", "-d"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.reasoning_reflection(question, draft)
        _print_json(r)
    except Exception as e:
        _err(e)


@reasoning_app.command("hypothesis")
def reasoning_hypothesis(
    question: str = typer.Option(..., "--question", "-q"),
    observations: str = typer.Option("", "--observations", help="逗号分隔"),
    max_hypotheses: int = typer.Option(3, "--max"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        obs = [o.strip() for o in observations.split(",") if o.strip()]
        r = client.reasoning_hypothesis(question, obs, max_hypotheses=max_hypotheses)
        _print_json(r)
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 12. office (word / ppt / excel / pdf)
# ════════════════════════════════════════════════════════════════════════════


@office_app.command("read")
def office_read(
    file: str = typer.Option(..., "--file", "-f"),
    type: str = typer.Option("word", "--type", "-t", help="word|ppt|excel|pdf"),
    sheet: str | None = typer.Option(None, "--sheet", help="excel sheet"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        if type == "word":
            r = client.word_read(file)
        elif type == "ppt":
            r = client.ppt_read(file)
        elif type == "excel":
            r = client.excel_read(file, sheet_name=sheet)
        elif type == "pdf":
            r = client.pdf_read(file)
        else:
            err_console.print(f"Unknown office type: {type}")
            raise typer.Exit(code=1)
        _print_json(r)
    except Exception as e:
        _err(e)


@office_app.command("word-write")
def office_word_write(
    file: str = typer.Option(..., "--file", "-f"),
    content: str = typer.Option(..., "--content", "-c"),
    title: str = typer.Option("", "--title"),
    author: str = typer.Option("", "--author"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.word_write(file, content, title=title, author=author)
        _print_json(r)
    except Exception as e:
        _err(e)


@office_app.command("ppt-write")
def office_ppt_write(
    file: str = typer.Option(..., "--file", "-f"),
    slides: str = typer.Option(..., "--slides", help="JSON 字符串"),
    title: str = typer.Option("", "--title"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        slide_list = json.loads(slides) if slides.startswith("[") else [{"title": title, "content": slides}]
        r = client.ppt_write(file, slide_list, title=title)
        _print_json(r)
    except Exception as e:
        _err(e)


@office_app.command("excel-write")
def office_excel_write(
    file: str = typer.Option(..., "--file", "-f"),
    data: str = typer.Option(..., "--data", help="JSON 二维数组或 dict"),
    sheet: str = typer.Option("Sheet1", "--sheet"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        parsed = json.loads(data)
        r = client.excel_write(file, parsed, sheet_name=sheet)
        _print_json(r)
    except Exception as e:
        _err(e)


@office_app.command("excel-analyze")
def office_excel_analyze(
    file: str = typer.Option(..., "--file", "-f"),
    type: str = typer.Option("summary", "--type", "-t"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.excel_analyze(file, analysis_type=type)
        _print_json(r)
    except Exception as e:
        _err(e)


@office_app.command("pdf-merge")
def office_pdf_merge(
    files: str = typer.Option(..., "--files", help="逗号分隔"),
    output: str = typer.Option(..., "--output", "-o"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        file_list = [f.strip() for f in files.split(",") if f.strip()]
        r = client.pdf_merge(file_list, output)
        _print_json(r)
    except Exception as e:
        _err(e)


@office_app.command("pdf-split")
def office_pdf_split(
    file: str = typer.Option(..., "--file", "-f"),
    ranges: str = typer.Option(..., "--ranges", help="1-3,5,7-10"),
    output_dir: str = typer.Option(..., "--out-dir", "-o"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        r = client.pdf_split(file, ranges, output_dir)
        _print_json(r)
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 13. notifications
# ════════════════════════════════════════════════════════════════════════════


@app.command("notifications")
def notifications(
    unread: bool = typer.Option(False, "--unread", "-u"),
    mark_all: bool = typer.Option(False, "--mark-all"),
    limit: int = typer.Option(20, "--limit", "-n"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """查看 / 标记通知。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        if mark_all:
            r = client.mark_notifications_read(all_read=True)
            _print_json(r)
            return
        r = client.list_notifications(unread_only=unread, limit=limit)
        items = r.get("data", [])
        t = Table(title=f"Notifications ({len(items)})")
        t.add_column("Read", style="cyan")
        t.add_column("Level")
        t.add_column("Title")
        t.add_column("Description", overflow="fold")
        t.add_column("Time")
        for n in items:
            from datetime import datetime

            ts = n.get("ts", 0)
            tstr = datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
            t.add_row(
                "✓" if n.get("read") else "[bold yellow]•[/bold yellow]",
                n.get("level", ""),
                n.get("title", ""),
                (n.get("description", "") or "")[:80],
                tstr,
            )
        console.print(t)
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# 14. sessions
# ════════════════════════════════════════════════════════════════════════════


@app.command("sessions")
def sessions(
    delete: str | None = typer.Option(None, "--delete", help="按 id 删除"),
    limit: int = typer.Option(20, "--limit", "-n"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """查看 / 删除会话。"""
    try:
        from data_ai import create_api_client

        client = create_api_client(base_url=base_url, api_key=backend_key)
        if delete:
            client.delete_session(delete)
            console.print(f"[green]Deleted {delete}[/green]")
            return
        r = client.list_sessions(limit=limit)
        items = r.get("data", [])
        t = Table(title=f"Sessions ({len(items)})")
        t.add_column("ID", style="cyan")
        t.add_column("Title")
        t.add_column("Model")
        t.add_column("Messages", justify="right")
        t.add_column("Preview", overflow="fold")
        for s in items:
            t.add_row(
                (s.get("id", "") or "")[:16],
                s.get("title", ""),
                s.get("model", ""),
                str(s.get("message_count", 0)),
                (s.get("preview", "") or "")[:80],
            )
        console.print(t)
    except Exception as e:
        _err(e)


# ════════════════════════════════════════════════════════════════════════════
# P1-10 企业治理: Audit / Quota / Webhooks / Cron
# ════════════════════════════════════════════════════════════════════════════


# ---------- Audit ----------


@audit_app.command("list")
def audit_list(
    actor: str | None = typer.Option(None, "--actor", help="按 actor 过滤"),
    action: str | None = typer.Option(None, "--action", help="按 action 过滤"),
    resource_type: str | None = typer.Option(None, "--type", help="按 resource_type 过滤"),
    limit: int = typer.Option(20, "-n", "--limit"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """查询审计日志 (who/what/when/result)。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        r = c.list_audit(actor=actor, action=action, resource_type=resource_type, limit=limit)
        rows = [
            [
                i.get("timestamp", ""),
                i.get("actor", "")[:14],
                i.get("action", ""),
                i.get("resource_type", ""),
                str(i.get("status_code", "")),
                f"{i.get('duration_ms', 0):.0f}ms",
                i.get("path", "")[:40],
            ]
            for i in r.get("items", [])
        ]
        _print_table(
            ["Time", "Actor", "Action", "Resource", "Status", "Latency", "Path"],
            rows,
            title=f"Audit log ({r.get('total', 0)} entries)",
        )
    except Exception as e:
        _err(e)


@audit_app.command("stats")
def audit_stats(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """审计统计。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        _print_json(c.audit_stats())
    except Exception as e:
        _err(e)


@audit_app.command("export")
def audit_export(
    fmt: str = typer.Option("json", "--fmt", help="json|csv"),
    output: str | None = typer.Option(None, "--output", "-o", help="输出到文件"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """导出审计 (合规取证)。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        r = c.export_audit(fmt=fmt)
        data = r.get("data", "")
        if output:
            Path(output).write_text(data, encoding="utf-8")
            console.print(f"[green]✓[/green] 导出 {r.get('count', 0)} 条审计到 [bold]{output}[/bold]")
        else:
            console.print(data[:2000])
            if len(data) > 2000:
                console.print(f"...(共 {len(data)} 字符,可用 --output 保存到文件)")
    except Exception as e:
        _err(e)


# ---------- Quota ----------


@quota_app.command("list")
def quota_list(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """列出所有配额策略。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        policies = c.list_quota_policies()
        rows = [
            [
                p.get("scope", ""),
                p.get("scope_id", "")[:16],
                str(p.get("daily_token_limit", "-") or "-"),
                str(p.get("qps_limit", "-") or "-"),
                str(p.get("max_concurrent", "-") or "-"),
                "✓" if p.get("enabled") else "✗",
            ]
            for p in policies
        ]
        _print_table(
            ["Scope", "ScopeID", "DailyTok", "QPS", "MaxConc", "Enabled"],
            rows,
            title=f"Quota policies ({len(policies)})",
        )
    except Exception as e:
        _err(e)


@quota_app.command("set")
def quota_set(
    scope: str = typer.Option("key", "--scope", help="global|key|user"),
    scope_id: str = typer.Option("", "--scope-id"),
    daily_token_limit: int | None = typer.Option(None, "--daily-tokens"),
    qps_limit: float | None = typer.Option(None, "--qps"),
    max_concurrent: int | None = typer.Option(None, "--max-concurrent"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """创建/更新配额策略。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        p = c.create_quota_policy(
            scope=scope,
            scope_id=scope_id,
            daily_token_limit=daily_token_limit,
            qps_limit=qps_limit,
            max_concurrent=max_concurrent,
        )
        _print_json(p)
    except Exception as e:
        _err(e)


@quota_app.command("delete")
def quota_delete(
    scope: str = typer.Option(..., "--scope"),
    scope_id: str = typer.Option(..., "--scope-id"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """删除配额策略。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        c.delete_quota_policy(scope, scope_id)
        console.print(f"[green]✓[/green] 删除 {scope}:{scope_id}")
    except Exception as e:
        _err(e)


@quota_app.command("usage")
def quota_usage(
    actor: str | None = typer.Option(None, "--actor"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """查看用量统计。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        r = c.quota_usage(actor=actor)
        _print_json(r.get("summary", {}))
    except Exception as e:
        _err(e)


@quota_app.command("status")
def quota_status_cmd(
    actor: str = typer.Argument(..., help="actor key hash / user id"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """查看 actor 剩余配额。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        _print_json(c.quota_status(actor))
    except Exception as e:
        _err(e)


# ---------- Webhooks ----------


@webhooks_app.command("events")
def webhooks_events(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """列出所有支持的事件类型。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        events = c.list_webhook_events()
        for e in events:
            console.print(f"  • {e}")
        console.print(f"\n[bold]{len(events)}[/bold] 事件类型")
    except Exception as e:
        _err(e)


@webhooks_app.command("list")
def webhooks_list(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """列出所有 webhook 订阅。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        subs = c.list_webhooks()
        rows = [
            [
                s.get("id", "")[:14],
                s.get("name", ""),
                s.get("url", "")[:50],
                ", ".join(s.get("events", []))[:40],
                "✓" if s.get("active") else "✗",
            ]
            for s in subs
        ]
        _print_table(
            ["ID", "Name", "URL", "Events", "Active"],
            rows,
            title=f"Webhooks ({len(subs)})",
        )
    except Exception as e:
        _err(e)


@webhooks_app.command("create")
def webhooks_create(
    name: str = typer.Option(..., "--name", "-n"),
    url: str = typer.Option(..., "--url", "-u"),
    events: str = typer.Option(..., "--events", help="逗号分隔,例如 agent.run.completed,job.completed"),
    description: str = typer.Option("", "--desc", "-d"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """创建 webhook 订阅。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        ev_list = [e.strip() for e in events.split(",") if e.strip()]
        sub = c.create_webhook(name=name, url=url, events=ev_list, description=description)
        console.print(f"[green]✓[/green] 创建 webhook [bold]{sub['id']}[/bold]")
        console.print(f"  secret: [dim]{sub.get('secret', '')}[/dim]")
        _print_json(sub)
    except Exception as e:
        _err(e)


@webhooks_app.command("delete")
def webhooks_delete(
    sub_id: str = typer.Argument(..., help="subscription id"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """删除 webhook 订阅。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        c.delete_webhook(sub_id)
        console.print(f"[green]✓[/green] 删除 {sub_id}")
    except Exception as e:
        _err(e)


@webhooks_app.command("deliveries")
def webhooks_deliveries(
    sub_id: str | None = typer.Option(None, "--sub", help="按订阅过滤"),
    status: str | None = typer.Option(None, "--status", help="success|failed|pending|retrying"),
    limit: int = typer.Option(20, "-n", "--limit"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """查看 webhook 投递日志。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        r = c.list_webhook_deliveries(sub_id=sub_id, status=status, limit=limit)
        rows = [
            [
                d.get("id", "")[:14],
                d.get("event", ""),
                str(d.get("status_code", "")),
                d.get("status", ""),
                f"#{d.get('attempt', 0)}",
                f"{d.get('duration_ms', 0):.0f}ms",
            ]
            for d in r.get("deliveries", [])
        ]
        _print_table(
            ["ID", "Event", "HTTP", "Status", "Try", "Latency"],
            rows,
            title=f"Deliveries ({r.get('stats', {}).get('total', 0)} total)",
        )
    except Exception as e:
        _err(e)


# ---------- Cron ----------


@cron_app.command("list")
def cron_list(
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """列出所有定时任务。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        r = c.list_jobs()
        rows = [
            [
                j.get("id", "")[:14],
                j.get("name", ""),
                j.get("action_type", ""),
                f"{j.get('schedule', {}).get('kind', '')}:{j.get('schedule', {}).get('expression', '')}"[:30],
                str(j.get("next_run_at", "") or "-")[:20],
                j.get("last_status", "never"),
                str(j.get("run_count", 0)),
            ]
            for j in r.get("jobs", [])
        ]
        _print_table(
            ["ID", "Name", "Action", "Schedule", "Next Run", "Last", "Runs"],
            rows,
            title=f"Jobs ({r.get('stats', {}).get('total_jobs', 0)})",
        )
    except Exception as e:
        _err(e)


@cron_app.command("create")
def cron_create(
    name: str = typer.Option(..., "--name", "-n"),
    action_type: str = typer.Option("http", "--action", help="http|agent_run|memory_cleanup|rag_reindex"),
    url: str | None = typer.Option(None, "--url", help="http 任务的回调 URL"),
    schedule_kind: str = typer.Option("cron", "--kind", help="cron|at|every"),
    schedule_expr: str = typer.Option(..., "--expr", help='cron: "0 9 * * *", every: "60s"'),
    description: str = typer.Option("", "--desc", "-d"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """创建定时任务。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        payload: dict = {}
        if action_type == "http":
            payload = {"url": url or "", "method": "POST"}
        job = c.create_job(
            name=name,
            action_type=action_type,
            action_payload=payload,
            schedule_kind=schedule_kind,
            schedule_expression=schedule_expr,
            description=description,
        )
        console.print(f"[green]✓[/green] 创建 job [bold]{job['id']}[/bold],下次跑:[dim]{job.get('next_run_at')}[/dim]")
    except Exception as e:
        _err(e)


@cron_app.command("trigger")
def cron_trigger(
    job_id: str = typer.Argument(..., help="job id"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """立即触发一次任务。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        e = c.trigger_job(job_id)
        console.print(f"[green]✓[/green] 触发执行 {e.get('id', '')[:14]}")
    except Exception as e:
        _err(e)


@cron_app.command("delete")
def cron_delete(
    job_id: str = typer.Argument(...),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """删除定时任务。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        c.delete_job(job_id)
        console.print(f"[green]✓[/green] 删除 {job_id}")
    except Exception as e:
        _err(e)


@cron_app.command("executions")
def cron_executions(
    job_id: str | None = typer.Option(None, "--job"),
    status: str | None = typer.Option(None, "--status"),
    limit: int = typer.Option(20, "-n", "--limit"),
    base_url: str = typer.Option("http://localhost:8000", "--base-url"),
    backend_key: str | None = typer.Option(None, "--backend-key"),
):
    """查看执行历史。"""
    try:
        c = _get_client_from_url(base_url, backend_key)
        execs = c.list_job_executions(job_id=job_id, status=status, limit=limit)
        rows = [
            [
                e.get("id", "")[:14],
                e.get("job_id", "")[:14],
                e.get("status", ""),
                f"{e.get('duration_ms', 0):.0f}ms",
                (e.get("error", "") or "")[:50],
            ]
            for e in execs
        ]
        _print_table(
            ["ID", "JobID", "Status", "Latency", "Error"],
            rows,
            title=f"Executions ({len(execs)})",
        )
    except Exception as e:
        _err(e)


# ─── 内部 helper ───


def _get_client_from_url(base_url: str, backend_key: str | None):  # type: ignore[no-untyped-def]
    """根据 base_url 构造一个 SDK client(支持 --base-url 覆盖)。"""
    from data_ai import create_api_client

    return create_api_client(base_url=base_url, api_key=backend_key)


# ════════════════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════════════════


def main() -> int:
    """Entry point for ``data-ai`` console script."""
    try:
        app()
        return 0
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
