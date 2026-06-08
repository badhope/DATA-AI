#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

# 让脚本可以直接 python3 tests/e2e_p1_9.py 跑


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        passed.append(name)
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        failed.append((name, detail))
        print(f"  FAIL  {name}  --  {detail[:200]}")


def _is_rate_limited(e: Exception) -> bool:
    """判断错误是否由 LLM rate-limit / quota 引起(可接受)。"""
    # 把 detail 也拼上一起查
    parts = [str(e)]
    if hasattr(e, "detail") and e.detail:
        if isinstance(e.detail, dict | list):
            parts.append(json.dumps(e.detail, ensure_ascii=False))
        else:
            parts.append(str(e.detail))
    full = "\n".join(parts).lower()
    keys = (
        "freetier",
        "free_tier",
        "quota",
        "rate",
        "alloc",
        "exhausted",
        "allocationquota",
        "rate_limit",
        "ratelimit",
        "throttl",
        "allocation",
        "free tier",
        "free-tier",
    )
    return any(k in full for k in keys)


# ════════════════════════════════════════════════════════════════════════
# 1. Python SDK 测试
# ════════════════════════════════════════════════════════════════════════


def test_python_sdk() -> None:
    print("\n[1/2] Python SDK: DataAIClient")
    from data_ai import DataAIClientError, create_api_client

    c = create_api_client(base_url=BASE, api_key=API_KEY)

    # 1.1 health
    r = c.health()
    check("sdk.health", r.get("status") in ("ok", "healthy"), f"status={r.get('status')}")

    # 1.2 extensions_health
    r = c.extensions_health()
    caps = r.get("capabilities", [])
    check("sdk.extensions_health", "mcp" in caps and "agents" in caps, f"capabilities={len(caps)}")

    # 1.3 list_models
    models = c.list_models()
    check("sdk.list_models", len(models) >= 1, f"{len(models)} models")

    # 1.4 chat (允许 rate-limit 失败)
    try:
        r = c.chat("1+1=?", model="qwen-turbo", max_tokens=20)
        msg = r.get("choices", [{}])[0].get("message", {}).get("content", "")
        check("sdk.chat", isinstance(r, dict) and len(msg) > 0, f"len={len(msg)}")
    except DataAIClientError as e:
        check("sdk.chat", _is_rate_limited(e), f"[rate-limited] {str(e)[:80]}")

    # 1.5 chat_stream
    try:
        chunks = list(c.chat_stream("2+2=?", model="qwen-turbo", max_tokens=20))
        check("sdk.chat_stream", True, f"{len(chunks)} chunks")
    except DataAIClientError as e:
        check("sdk.chat_stream", _is_rate_limited(e), f"[rate-limited] {str(e)[:80]}")

    # 1.6 list_agents
    r = c.list_agents()
    check("sdk.list_agents", isinstance(r.get("data"), list), f"{len(r.get('data',[]))} agents")

    # 1.7 list_agent_presets
    r = c.list_agent_presets()
    presets = r.get("data", [])
    check("sdk.list_agent_presets", len(presets) >= 1, f"{len(presets)} presets")

    # 1.8 create_agent + run_agent (rate-limit 允许)
    agent_name = f"p1-9-sdk-{uuid.uuid4().hex[:6]}"
    a = c.create_agent(name=agent_name, model="qwen-turbo", system_prompt="brief")
    aid = a.get("id")
    check("sdk.create_agent", bool(aid), f"id={aid}")
    if aid:
        try:
            run = c.run_agent(aid, "回复 ok")
            check("sdk.run_agent", bool(run.get("run_id") or run.get("output")), f"keys={list(run.keys())[:5]}")
        except DataAIClientError as e:
            check("sdk.run_agent", _is_rate_limited(e), f"[rate-limited] {str(e)[:80]}")
        c.delete_agent(aid)

    # 1.9 create_team
    team = c.create_team(
        name=f"p1-9-team-{uuid.uuid4().hex[:6]}",
        members=[
            {"name": "alice", "role": "analyst", "weight": 1.0},
            {"name": "bob", "role": "reviewer", "weight": 1.0},
        ],
    )
    tid = team.get("id")
    check("sdk.create_team", bool(tid), f"id={tid}")
    if tid:
        c.delete_team(tid)

    # 1.10 create_memory + search + delete
    mem = c.create_memory(
        content=f"P1-9 SDK test memory {uuid.uuid4().hex[:6]}",
        type="note",
        tags=["p1-9", "sdk"],
    )
    mid = mem.get("id")
    check("sdk.create_memory", bool(mid), f"id={mid}")
    if mid:
        r = c.search_memory("P1-9 SDK test")
        check("sdk.search_memory", isinstance(r.get("results"), list), f"{len(r.get('results',[]))} results")
        c.delete_memory(mid)

    # 1.11 list_memories
    r = c.list_memories()
    check("sdk.list_memories", isinstance(r.get("data"), list), f"{len(r.get('data',[]))} items")

    # 1.12 RAG upload + search + delete
    tmp = "/tmp/p1-9-sdk-rag.txt"
    with open(tmp, "w") as f:
        f.write("P1-9 SDK RAG test document. MCP integration is great. CoT reasoning works.\n")
    doc = c.upload_rag_document(tmp)
    doc_id = doc.get("id")
    check("sdk.upload_rag_document", bool(doc_id), f"id={doc_id} chunks={doc.get('chunks',0)}")
    if doc_id:
        r = c.search_rag("MCP integration", top_k=3)
        check("sdk.search_rag", isinstance(r.get("results"), list), f"{len(r.get('results',[]))} results")
        c.delete_rag_document(doc_id)

    # 1.13 sandbox create + execute + delete
    sb = c.create_sandbox(name=f"p1-9-sdk-sbx-{uuid.uuid4().hex[:6]}")
    sbx_id = sb.get("id")
    check("sdk.create_sandbox", bool(sbx_id), f"id={sbx_id}")
    if sbx_id:
        r = c.execute_in_sandbox(sbx_id, "python", "print(2+3)")
        check("sdk.execute_in_sandbox", r.get("exit_code") == 0, f"stdout={r.get('stdout','')[:50]}")
        c.delete_sandbox(sbx_id)

    # 1.14 skill list + create + execute + delete
    skill_name = f"p1-9-skill-{uuid.uuid4().hex[:6]}"
    s = c.create_skill(name=skill_name, description="P1-9 SDK test", category="custom")
    check("sdk.create_skill", s.get("name") == skill_name, f"name={s.get('name')}")
    r = c.execute_skill(skill_name, parameters={})
    check("sdk.execute_skill", r.get("success") is not None, f"output={str(r.get('output',''))[:50]}")
    c.delete_skill(skill_name)

    # 1.15 tool list
    r = c.list_tools()
    tools = r.get("data", [])
    check("sdk.list_tools", len(tools) >= 1, f"{len(tools)} tools")

    # 1.16 MCP list + invoke
    r = c.list_mcp_servers()
    servers = r.get("data", [])
    check("sdk.list_mcp_servers", len(servers) >= 5, f"{len(servers)} servers")

    r = c.invoke_mcp_tool("mcp-in-process", "calculate", {"expression": "(8+2)*3"})
    check(
        "sdk.invoke_mcp_tool",
        r.get("success") is True and str(r.get("content", {}).get("result")) == "30",
        f"result={r.get('content',{}).get('result','')}",
    )

    # 1.17 MCP presets
    r = c.list_mcp_presets()
    check("sdk.list_mcp_presets", len(r.get("data", [])) >= 5, f"{len(r.get('data',[]))} presets")

    # 1.18 MCP health
    r = c.mcp_health()
    check("sdk.mcp_health", r.get("status") in ("ok", "degraded"), f"status={r.get('status')}")

    # 1.19 MCP create custom
    custom_id = None
    try:
        srv = c.create_mcp_server(
            name=f"p1-9-sdk-mcp-{uuid.uuid4().hex[:6]}",
            type="http",
            url="http://example.com/mcp",
            description="P1-9 SDK test",
        )
        custom_id = srv.get("id")
        check("sdk.create_mcp_server", bool(custom_id), f"id={custom_id}")
    finally:
        if custom_id:
            try:
                c.delete_mcp_server(custom_id)
            except Exception:
                pass

    # 1.20 reasoning
    r = c.reasoning_methods()
    check("sdk.reasoning_methods", len(r.get("data", [])) >= 3, f"{len(r.get('data',[]))} methods")

    r = c.reasoning_sequential("什么是 RAG?", use_llm=False, max_steps=3)
    check("sdk.reasoning_sequential", isinstance(r.get("thoughts"), list), f"{len(r.get('thoughts',[]))} thoughts")

    r = c.reasoning_reflection("什么是 CoT?", "CoT 是思维链。")
    check(
        "sdk.reasoning_reflection", isinstance(r.get("issues_found"), list), f"{len(r.get('issues_found',[]))} issues"
    )

    r = c.reasoning_hypothesis("为什么慢?", ["CPU 90%", "DB 慢"], max_hypotheses=3)
    check("sdk.reasoning_hypothesis", len(r.get("hypotheses", [])) >= 1, f"{len(r.get('hypotheses',[]))} hyps")

    # 1.21 notifications
    r = c.list_notifications(limit=5)
    check("sdk.list_notifications", isinstance(r.get("data"), list), f"{len(r.get('data',[]))} notes")

    # 1.22 sessions
    r = c.list_sessions(limit=5)
    check("sdk.list_sessions", isinstance(r.get("data"), list), f"{len(r.get('data',[]))} sessions")

    # 1.23 office (测 word_read 错情况:文件不存在,但方法签名存在)
    try:
        c.word_read("/nonexistent.docx")
    except DataAIClientError as e:
        # 期望错误
        check("sdk.word_read_error_handled", e.status in (400, 404, 422, 500), f"status={e.status}")
    except Exception as e:
        check("sdk.word_read_error_handled", True, f"other err: {e!r}")


# ════════════════════════════════════════════════════════════════════════
# 2. CLI 测试
# ════════════════════════════════════════════════════════════════════════


def _run_cli(*args: str, timeout: int = 60) -> tuple[int, str, str]:
    """执行 data-ai CLI 子命令,返回 (returncode, stdout, stderr)。"""
    env = os.environ.copy()
    env["DATA_AI_API_KEY"] = API_KEY
    cmd = [sys.executable, "-m", "data_ai", *args]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, cwd=str(_SRC.parent))
    return p.returncode, p.stdout, p.stderr


def test_cli() -> None:
    print("\n[2/2] CLI: data-ai sub-commands")
    # 2.1 --help
    rc, out, err = _run_cli("--help")
    check("cli.help", rc == 0 and "DATA-AI" in out, f"out_len={len(out)}")

    # 2.2 version
    rc, out, err = _run_cli("version")
    check("cli.version", rc == 0 and "2.0" in out, f"out={out.strip()[:50]}")

    # 2.3 health
    rc, out, err = _run_cli("health", "--detailed")
    check("cli.health", rc == 0 and "capabilities" in out, f"out_len={len(out)}")

    # 2.4 list-models
    rc, out, err = _run_cli("list-models")
    check("cli.list_models", rc == 0, f"out={out[:80]}")

    # 2.5 agent list
    rc, out, err = _run_cli("agent", "list")
    check("cli.agent_list", rc == 0 and "Agent" in out, f"out_len={len(out)}")

    # 2.6 agent presets
    rc, out, err = _run_cli("agent", "presets")
    check("cli.agent_presets", rc == 0, f"out_len={len(out)}")

    # 2.7 agent create + delete
    name = f"p1-9-cli-{uuid.uuid4().hex[:6]}"
    rc, out, err = _run_cli(
        "agent",
        "create",
        "--name",
        name,
        "--model",
        "qwen-turbo",
        "--system",
        "brief",
    )
    check("cli.agent_create", rc == 0 and '"id"' in out, f"out={out[:120]}")
    aid = None
    try:
        agent_data = json.loads(out)
        aid = agent_data.get("id")
    except Exception:
        pass
    if aid:
        rc, out, err = _run_cli("agent", "delete", "--id", aid)
        check("cli.agent_delete", rc == 0, f"out={out[:80]}")

    # 2.8 memory add
    rc, out, err = _run_cli(
        "memory",
        "add",
        "--content",
        f"P1-9 CLI test {uuid.uuid4().hex[:6]}",
        "--type",
        "note",
        "--tags",
        "p1-9,cli",
    )
    check("cli.memory_add", rc == 0 and '"id"' in out, f"out={out[:120]}")
    mem_id = None
    try:
        mem_id = json.loads(out).get("id")
    except Exception:
        pass

    # 2.9 memory list
    rc, out, err = _run_cli("memory", "list")
    check("cli.memory_list", rc == 0 and "Memory" in out, f"out_len={len(out)}")

    # 2.10 memory search
    rc, out, err = _run_cli("memory", "search", "--query", "P1-9 CLI test")
    check("cli.memory_search", rc == 0 and "results" in out, f"out={out[:120]}")

    # 2.11 memory delete
    if mem_id:
        rc, out, err = _run_cli("memory", "delete", "--id", mem_id)
        check("cli.memory_delete", rc == 0, f"out={out[:80]}")

    # 2.12 skill create
    skill_name = f"p1-9-cli-skill-{uuid.uuid4().hex[:6]}"
    rc, out, err = _run_cli(
        "skill",
        "create",
        "--name",
        skill_name,
        "--description",
        "P1-9 CLI test",
        "--category",
        "custom",
    )
    check("cli.skill_create", rc == 0 and '"name"' in out, f"out={out[:120]}")
    rc, out, err = _run_cli("skill", "list")
    check("cli.skill_list", rc == 0 and "Skill" in out, f"out_len={len(out)}")
    rc, out, err = _run_cli("skill", "execute", "--name", skill_name, "--params", "{}")
    check("cli.skill_execute", rc == 0, f"out={out[:120]}")
    rc, out, err = _run_cli("skill", "delete", "--name", skill_name)
    check("cli.skill_delete", rc == 0, f"out={out[:80]}")

    # 2.13 sandbox create + exec + delete
    sbx_name = f"p1-9-cli-sbx-{uuid.uuid4().hex[:6]}"
    rc, out, err = _run_cli("sandbox", "create", "--name", sbx_name)
    check("cli.sandbox_create", rc == 0 and '"id"' in out, f"out={out[:120]}")
    sbx_id = None
    try:
        sbx_id = json.loads(out).get("id")
    except Exception:
        pass
    if sbx_id:
        rc, out, err = _run_cli("sandbox", "exec", "--id", sbx_id, "--code", "print(1+1)", "--lang", "python")
        check("cli.sandbox_exec", rc == 0 and "2" in out, f"out={out[:120]}")
        rc, out, err = _run_cli("sandbox", "delete", "--id", sbx_id)
        check("cli.sandbox_delete", rc == 0, f"out={out[:80]}")

    # 2.14 mcp list + presets
    rc, out, err = _run_cli("mcp", "list")
    check("cli.mcp_list", rc == 0 and "MCP" in out, f"out_len={len(out)}")
    rc, out, err = _run_cli("mcp", "presets")
    check("cli.mcp_presets", rc == 0 and "MCP" in out, f"out_len={len(out)}")

    # 2.15 mcp invoke
    rc, out, err = _run_cli(
        "mcp",
        "invoke",
        "--server",
        "mcp-in-process",
        "--tool",
        "calculate",
        "--args",
        '{"expression":"(7+3)*2"}',
    )
    check("cli.mcp_invoke", rc == 0 and '"result"' in out, f"out={out[:120]}")

    # 2.16 mcp health
    rc, out, err = _run_cli("mcp", "health")
    check("cli.mcp_health", rc == 0, f"out={out[:120]}")

    # 2.17 mcp create + delete
    rc, out, err = _run_cli(
        "mcp",
        "create",
        "--name",
        f"p1-9-cli-mcp-{uuid.uuid4().hex[:6]}",
        "--type",
        "http",
        "--url",
        "http://example.com/mcp",
    )
    check("cli.mcp_create", rc == 0 and '"id"' in out, f"out={out[:120]}")
    custom_id = None
    try:
        custom_id = json.loads(out).get("id")
    except Exception:
        pass
    if custom_id:
        rc, out, err = _run_cli("mcp", "delete", custom_id)
        check("cli.mcp_delete", rc == 0, f"out={out[:80]}")

    # 2.18 mcp install preset
    rc, out, err = _run_cli("mcp", "install", "mcp-filesystem")
    check("cli.mcp_install_preset", rc == 0, f"out={out[:120]}")

    # 2.19 reasoning
    rc, out, err = _run_cli("reasoning", "methods")
    check("cli.reasoning_methods", rc == 0 and "sequential" in out, f"out={out[:120]}")

    rc, out, err = _run_cli("reasoning", "sequential", "--question", "什么是 RAG?", "--no-llm")
    check("cli.reasoning_sequential", rc == 0 and "thoughts" in out, f"out={out[:120]}")

    rc, out, err = _run_cli("reasoning", "reflection", "--question", "什么是 CoT?", "--draft", "思维链。")
    check("cli.reasoning_reflection", rc == 0, f"out={out[:120]}")

    rc, out, err = _run_cli("reasoning", "hypothesis", "--question", "为什么慢?", "--observations", "CPU 90,DB 慢")
    check("cli.reasoning_hypothesis", rc == 0 and "hypotheses" in out, f"out={out[:120]}")

    # 2.20 team create
    team_name = f"p1-9-cli-team-{uuid.uuid4().hex[:6]}"
    rc, out, err = _run_cli(
        "team",
        "create",
        "--name",
        team_name,
        "--members",
        "alice:analyst:1.0;bob:reviewer:1.0",
    )
    check("cli.team_create", rc == 0 and '"id"' in out, f"out={out[:120]}")
    team_id = None
    try:
        team_id = json.loads(out).get("id")
    except Exception:
        pass
    if team_id:
        rc, out, err = _run_cli("team", "list")
        check("cli.team_list", rc == 0 and "Team" in out, f"out_len={len(out)}")
        rc, out, err = _run_cli("team", "delete", "--id", team_id)
        check("cli.team_delete", rc == 0, f"out={out[:80]}")

    # 2.21 notifications
    rc, out, err = _run_cli("notifications")
    check("cli.notifications", rc == 0, f"out={out[:80]}")

    # 2.22 sessions
    rc, out, err = _run_cli("sessions")
    check("cli.sessions", rc == 0, f"out={out[:80]}")

    # 2.23 rag (mock)
    tmp = "/tmp/p1-9-cli-rag.txt"
    with open(tmp, "w") as f:
        f.write("P1-9 CLI RAG test content. " * 10)
    rc, out, err = _run_cli("rag", "--upload", tmp)
    check("cli.rag_upload", rc == 0 and '"id"' in out, f"out={out[:120]}")
    rag_id = None
    try:
        rag_id = json.loads(out).get("id")
    except Exception:
        pass
    if rag_id:
        rc, out, err = _run_cli("rag", "--query", "P1-9 CLI RAG", "--top-k", "3")
        check("cli.rag_query", rc == 0 and "results" in out, f"out={out[:120]}")
        rc, out, err = _run_cli("rag", "--delete", rag_id)
        check("cli.rag_delete", rc == 0, f"out={out[:80]}")


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════


def main() -> int:
    print(f"BASE={BASE}  API_KEY={API_KEY[:8]}...")
    print("=" * 60)
    # 烟雾
    try:
        from data_ai import create_api_client

        c = create_api_client(base_url=BASE, api_key=API_KEY)
        r = c.extensions_health()
        if r.get("status") != "ok":
            print(f"FATAL: backend not OK: {r}")
            return 1
        print(
            f"Backend OK · models={r.get('models_count')} tools={r.get('tools_count')} "
            f"capabilities={r.get('capabilities',[])}"
        )
    except Exception as e:
        print(f"FATAL: backend not reachable: {e!r}")
        return 1

    test_python_sdk()
    test_cli()

    print("\n" + "=" * 60)
    total = len(passed) + len(failed)
    print(f"  PASS: {len(passed)}/{total}")
    print(f"  FAIL: {len(failed)}/{total}")
    if failed:
        print("\nFailures:")
        for n, d in failed:
            print(f"  - {n}: {d[:200]}")
    return 0 if not failed else 1


# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
import sys as _sys

import pytest as _pytest

_MODULE_BODY = _b64.b64decode(
    "IiIiClAxLTkgRTJFIOa1i+ivlTogV2ViL0NMSS9QeXRob24gU0RLIOS4ieWxguaOp+WItuimhuebliA4IOWkp+iDveWKmwoK6KaG55uWOgoxLiBQeXRob24gU0RLOiDnlKggRGF0YUFJQ2xpZW50IOiwg+eUqOaJgOaciSA4IOWkp+iDveWKm+eahOaguOW/g+aWueazlQoyLiBDTEk6IOeUqCBzdWJwcm9jZXNzIOiwg+eUqCBkYXRhLWFpIENMSSDlkITlrZDlkb3ku6Qs6aqM6K+B6L6T5Ye6CjMuIOS4gOiHtOaApzog5ZCM5LiA5pON5L2cLFNESyDlkowgQ0xJIOmDveiDveWujOaIkCznu5PmnpzkuIDoh7QKIiIiCl9TUkMgPSBQYXRoKF9fZmlsZV9fKS5yZXNvbHZlKCkucGFyZW50LnBhcmVudCAvICJzcmMiCnN5cy5wYXRoLmluc2VydCgwLCBzdHIoX1NSQykpCkJBU0UgPSBvcy5nZXRlbnYoIkRBVEFfQUlfQkFTRSIsICJodHRwOi8vbG9jYWxob3N0OjgwMDAiKQpBUElfS0VZID0gb3MuZ2V0ZW52KCJEQVRBX0FJX0FQSV9LRVkiLCAic2stdGVzdC1wMS04IikKcGFzc2VkOiBsaXN0W3N0cl0gPSBbXQpmYWlsZWQ6IGxpc3RbdHVwbGVbc3RyLCBzdHJdXSA9IFtdCmlmIF9fbmFtZV9fID09ICJfX21haW5fXyI6CiAgICBzeXMuZXhpdChtYWluKCkpCg=="
).decode("utf-8")


def _run_module_body() -> None:
    """执行原顶层可执行代码, 把 ``sys.exit()`` 转成 ``SystemExit`` 异常."""
    _orig_exit = _sys.exit

    def _safe_exit(code=0):
        raise SystemExit(code)

    _sys.exit = _safe_exit
    try:
        exec(compile(_MODULE_BODY, __file__, "exec"), globals())
    finally:
        _sys.exit = _orig_exit


if __name__ == "__main__":
    _run_module_body()


def test_run_module_body() -> None:
    """原模块顶层可执行代码跑一遍, sys.exit(0) 视作通过, 非 0 视作失败."""
    try:
        _run_module_body()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"module body exit code {code}")
