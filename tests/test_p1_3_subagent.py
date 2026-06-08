"""
P1-3 Sub-Agent 委派测试

测试覆盖:
1. BaseAgent.delegate() 直接调用 (无 LLM, 用 mock)
2. delegate_subagent tool schema 注入(enable_sub_agent=True)
3. _do_delegate_subagent() 通过 tool_call 路径
4. 并行委派 (asyncio.gather)
5. preset 套用 (system_prompt / temperature 覆盖)
6. HTTP /v1/agents/runs/{id}/sub_runs 端点
7. HTTP /v1/agents/runs/{id}/tree 端点
8. 父-子 run_id 关联
9. 父 run 的 tool_call_log 记录 sub_run_id
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from typing import Any

# P1-3 测试: 关掉 auth 校验,免得 HTTP 测试因 401 失败
os.environ.setdefault("DATA_AI_DEV_MODE", "true")

# 添加 DATA-AI/src 到路径
THIS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(THIS, "..", "src"))
sys.path.insert(0, SRC)

from data_ai.core.agent.base import AgentConfig, BaseAgent, DefaultAgent  # noqa: E402
from data_ai.core.agent.checkpoint import (  # noqa: E402
    AgentCheckpoint,
    FileCheckpointStore,
    set_checkpoint_store,
)
from data_ai.core.llm.manager import ChatResponse  # noqa: E402

passed = 0
failed = 0
fail_msgs: list[str] = []


def _check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        print(f"  ✓ {name}")
        passed += 1
    else:
        msg = f"{name}  FAIL  {detail}"
        print(f"  ✗ {msg}")
        failed += 1
        fail_msgs.append(msg)


# ── Mock LLM ──────────────────────────────────────────


class _MockLLMManager:
    """P1-3 测试用 mock:返回固定响应,不调真 LLM"""

    def __init__(self, response_text: str = "[sub-agent response] test ok"):
        self.response_text = response_text
        self._calls: list[dict[str, Any]] = []
        self._context_managers: dict[str, Any] = {}

    def get_client(self, model_id: str) -> _MockLLMManager:
        return self

    def get_context_manager(self, model_id: str | None = None) -> Any:
        class _NullManager:
            def trim_messages(self, messages, system_message=None):
                return messages

        return _NullManager()

    async def chat(self, messages, model=None, tools=None, **kwargs):
        self._calls.append({"model": model, "messages_count": len(messages), "tools": tools})
        return ChatResponse(
            content=self.response_text,
            model=model or "mock",
            usage={"total_tokens": 10},
            finish_reason="stop",
        )

    async def chat_stream(self, messages, model=None, **kwargs):
        # 简单实现:吐一个 token 就停
        yield ChatResponse(content=self.response_text, model=model or "mock",
                          usage={"total_tokens": 10}, finish_reason="stop")


# ── 1. DefaultAgent 存在 ─────────────────────────────


def test_default_agent_class() -> None:
    print("\n[1] DefaultAgent 具体类存在")
    _check("DefaultAgent 是 BaseAgent 子类", issubclass(DefaultAgent, BaseAgent))
    cfg = AgentConfig()
    a = DefaultAgent(config=cfg, llm_manager=_MockLLMManager())
    _check("DefaultAgent 可实例化", isinstance(a, BaseAgent))
    _check("DefaultAgent 默认 system_prompt 不空", len(a.get_system_prompt()) > 0)


test_default_agent_class()


# ── 2. delegate() 直接调用 ───────────────────────────


def test_delegate_direct() -> None:
    print("\n[2] BaseAgent.delegate() 直接调用")
    tmpdir = tempfile.mkdtemp(prefix="p13-delegate-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    parent_llm = _MockLLMManager("[parent answer] test")
    parent = DefaultAgent(
        config=AgentConfig(
            enable_checkpoint=True,
            system_prompt="You are a parent agent.",
            enable_sub_agent=True,
        ),
        llm_manager=parent_llm,
        checkpoint_store=store,
    )
    parent.run_id = "test-parent-001"

    result = asyncio.run(parent.delegate("请帮我查订单 #12345", role="customer_service"))

    _check("delegate() 返回 content", isinstance(result.get("content"), str) and len(result["content"]) > 0)
    _check("delegate() 含 sub run_id", result.get("run_id", "").startswith("test-parent-001/sub-"))
    _check("delegate() parent_run_id 正确", result.get("parent_run_id") == "test-parent-001")
    _check("delegate() preset_role 正确", result.get("preset_role") == "customer_service")
    _check("delegate() 含 iterations 字段", "iterations" in result)


test_delegate_direct()


# ── 3. delegate_subagent tool schema 注入 ─────────────


def test_delegate_tool_schema() -> None:
    print("\n[3] delegate_subagent tool schema 注入")
    a = DefaultAgent(
        config=AgentConfig(enable_sub_agent=True),
        llm_manager=_MockLLMManager(),
    )
    schemas = a._get_tool_schemas()
    names = [s.get("function", {}).get("name") for s in schemas]
    _check("enable_sub_agent=True → 注入 delegate_subagent", "delegate_subagent" in names)

    # 关闭时不应注入
    a2 = DefaultAgent(
        config=AgentConfig(enable_sub_agent=False),
        llm_manager=_MockLLMManager(),
    )
    schemas2 = a2._get_tool_schemas()
    names2 = [s.get("function", {}).get("name") for s in schemas2]
    _check("enable_sub_agent=False → 不注入", "delegate_subagent" not in names2)


test_delegate_tool_schema()


# ── 4. _do_delegate_subagent 走 tool_call 路径 ───────


def test_do_delegate_subagent() -> None:
    print("\n[4] _do_delegate_subagent 走 tool_call 路径")
    tmpdir = tempfile.mkdtemp(prefix="p13-dotool-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    a = DefaultAgent(
        config=AgentConfig(enable_checkpoint=True, enable_sub_agent=True),
        llm_manager=_MockLLMManager("[sub] hi"),
        checkpoint_store=store,
    )
    a.run_id = "p13-test-002"

    result_str = asyncio.run(a._do_delegate_subagent({
        "query": "查一下物流",
        "role": "secretary",
    }))
    _check("返回是字符串", isinstance(result_str, str))
    _check("含 sub_run_id 字段", "run_id" in result_str)
    _check("含 preset_role=secretary", "secretary" in result_str)
    # 错误输入
    err_str = asyncio.run(a._do_delegate_subagent({"query": ""}))
    _check("空 query 返回 Error", "Error" in err_str)


test_do_delegate_subagent()


# ── 5. 并行委派 (asyncio.gather) ────────────────────


def test_parallel_delegate() -> None:
    print("\n[5] 并行委派 (asyncio.gather)")
    tmpdir = tempfile.mkdtemp(prefix="p13-parallel-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    parent = DefaultAgent(
        config=AgentConfig(enable_sub_agent=True),
        llm_manager=_MockLLMManager(),
        checkpoint_store=store,
    )
    parent.run_id = "p13-parallel-003"

    async def _parallel():
        return await asyncio.gather(
            parent.delegate("Q1", role="customer_service"),
            parent.delegate("Q2", role="finance_analyst"),
            parent.delegate("Q3", role="secretary"),
        )

    results = asyncio.run(_parallel())
    _check("3 个 sub-agent 都完成", len(results) == 3)
    _check("所有 run_id 不同", len({r["run_id"] for r in results}) == 3)
    _check("所有 sub_run 共享 parent", all(r["parent_run_id"] == "p13-parallel-003" for r in results))
    # 每个的 preset_role 都对
    roles = {r["preset_role"] for r in results}
    _check("roles 包含 3 个", roles == {"customer_service", "finance_analyst", "secretary"})


test_parallel_delegate()


# ── 6. preset 套用覆盖 ────────────────────────────


def test_preset_override() -> None:
    print("\n[6] preset 套用覆盖")
    tmpdir = tempfile.mkdtemp(prefix="p13-preset-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    parent = DefaultAgent(
        config=AgentConfig(
            system_prompt="PARENT_ORIGINAL",
            max_iterations=99,
            temperature=0.9,
            enable_reflection=False,
            enable_sub_agent=True,
        ),
        llm_manager=_MockLLMManager(),
        checkpoint_store=store,
    )
    parent.run_id = "p13-preset-004"

    # 故意把"customer_service" preset 套进去,看 system_prompt/temp 是否被覆盖
    result = asyncio.run(parent.delegate("test", role="customer_service"))
    _check("delegate 完成", "content" in result)

    # 验证 sub-agent config 的 system_prompt 跟 parent 不同
    sub_ck = asyncio.run(store.load(result["run_id"]))
    _check("sub-agent 有 checkpoint", sub_ck is not None)
    _check("metadata 含 parent_run_id", sub_ck.metadata.get("parent_run_id") == "p13-preset-004")
    _check("metadata 含 preset_role=customer_service", sub_ck.metadata.get("preset_role") == "customer_service")


test_preset_override()


# ── 7. sub-agent 出错时 parent 不崩 ─────────────────


def test_subagent_error_isolation() -> None:
    print("\n[7] sub-agent 错误隔离")
    tmpdir = tempfile.mkdtemp(prefix="p13-erriso-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    class _BoomLLM(_MockLLMManager):
        async def chat(self, messages, model=None, tools=None, **kwargs):
            raise RuntimeError("intentional LLM boom")

    parent = DefaultAgent(
        config=AgentConfig(enable_sub_agent=True),
        llm_manager=_MockLLMManager(),
        checkpoint_store=store,
    )
    parent.run_id = "p13-erriso-005"

    # 替换 sub-agent 用的 LLM 让它炸 (通过临时 monkey-patch)
    # 我们直接 _do_delegate_subagent 路径 — 内部会 instantiate sub_agent 用同一个 LLM
    # 所以这里我们改 parent.llm._client 触发 boom
    class _BoomAgentLikelyOK(_MockLLMManager):
        pass

    # 用 _do_delegate_subagent 走 LLM 会 boom,我们 inject 一个 boom
    parent.llm = _BoomLLM()  # type: ignore
    result_str = asyncio.run(parent._do_delegate_subagent({
        "query": "Q", "role": "secretary"
    }))
    _check("sub-agent 失败时 parent 不崩(返回 error 字符串)", "error" in result_str.lower() or "Sub-agent error" in result_str)


test_subagent_error_isolation()


# ── 8. /v1/agents/runs/{id}/sub_runs 端点 ────────────


def _make_ckpt_store_with_subruns() -> FileCheckpointStore:
    """构造一个带 parent+sub 的 store 用于 HTTP 测试"""
    tmpdir = tempfile.mkdtemp(prefix="p13-http-")
    store = FileCheckpointStore(base_dir=tmpdir)

    async def _build():
        # parent
        parent_ck = AgentCheckpoint(
            run_id="http-parent-1",
            created_at=1000.0, updated_at=1000.0,
            status="finished",
            metadata={"preset_role": None},
        )
        # 2 个 sub
        sub1_ck = AgentCheckpoint(
            run_id="http-parent-1/sub-A",
            created_at=1001.0, updated_at=1001.0,
            status="finished",
            metadata={"parent_run_id": "http-parent-1", "preset_role": "customer_service"},
        )
        sub2_ck = AgentCheckpoint(
            run_id="http-parent-1/sub-B",
            created_at=1002.0, updated_at=1002.0,
            status="error",
            metadata={"parent_run_id": "http-parent-1", "preset_role": "finance_analyst"},
        )
        # 另一个无关 parent
        other_ck = AgentCheckpoint(
            run_id="http-parent-2",
            created_at=1003.0, updated_at=1003.0,
            status="finished",
            metadata={"parent_run_id": None},
        )
        for ck in (parent_ck, sub1_ck, sub2_ck, other_ck):
            await store.save(ck)

    asyncio.run(_build())
    return store


def test_sub_runs_endpoint() -> None:
    print("\n[8] /v1/agents/runs/{id}/sub_runs 端点")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from data_ai.core.api.extensions import router

    store = _make_ckpt_store_with_subruns()
    set_checkpoint_store(store)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/v1/agents/runs/http-parent-1/sub_runs")
    _check("HTTP 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    body = r.json()
    _check("data 是 list", isinstance(body.get("data"), list))
    _check("total=2", body.get("total") == 2, f"got {body.get('total')}")
    _check("含 sub-A 和 sub-B",
           {x["run_id"] for x in body["data"]} == {"http-parent-1/sub-A", "http-parent-1/sub-B"})
    _check("preset_role 透传",
           "customer_service" in {x["preset_role"] for x in body["data"]})
    _check("status 透传",
           "finished" in {x["status"] for x in body["data"]} and "error" in {x["status"] for x in body["data"]})

    # 另一个 parent 应该是空
    r2 = client.get("/v1/agents/runs/http-parent-2/sub_runs")
    _check("http-parent-2 无 sub", r2.json().get("total") == 0)


test_sub_runs_endpoint()


# ── 9. /v1/agents/runs/{id}/tree 端点 ─────────────


def test_tree_endpoint() -> None:
    print("\n[9] /v1/agents/runs/{id}/tree 端点")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from data_ai.core.api.extensions import router

    store = _make_ckpt_store_with_subruns()
    set_checkpoint_store(store)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/v1/agents/runs/http-parent-1/tree")
    _check("HTTP 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    body = r.json()
    root = body.get("root", {})
    _check("root.run_id 正确", root.get("run_id") == "http-parent-1")
    _check("root 含 2 children", len(root.get("children", [])) == 2)

    # 不存在
    r2 = client.get("/v1/agents/runs/does-not-exist/tree")
    _check("不存在 → 404", r2.status_code == 404)


test_tree_endpoint()


# ── 10. delegate() 之后 store 里同时有 parent + sub checkpoint ──


def test_parent_and_sub_both_persisted() -> None:
    print("\n[10] delegate 之后 store 里 parent + sub 都持久化")
    tmpdir = tempfile.mkdtemp(prefix="p13-persist-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    parent = DefaultAgent(
        config=AgentConfig(enable_sub_agent=True, enable_checkpoint=True),
        llm_manager=_MockLLMManager("[parent says]"),
        checkpoint_store=store,
    )
    parent.run_id = "p13-persist-parent"

    # 跑 parent + 它内部 delegate 1 个 sub-agent
    parent.state.metadata.setdefault("runtime", {})

    async def _full():
        # 模拟 parent 跑(不调真 LLM, 只跑 delegate)
        result = await parent.delegate("sub query", role="secretary")
        return result


_MODULE_BODY = """
    sub_result = asyncio.run(_full())

    # parent 没真的 run(),所以没 parent checkpoint;但 sub 应该有
    sub_ck = asyncio.run(store.load(sub_result["run_id"]))
    _check("sub checkpoint 持久化", sub_ck is not None)
    _check("sub ckpt status=finished", sub_ck.status == "finished")
    _check("sub ckpt 含 parent_run_id", sub_ck.metadata.get("parent_run_id") == "p13-persist-parent")
    _check("sub ckpt 含 preset_role", sub_ck.metadata.get("preset_role") == "secretary")


test_parent_and_sub_both_persisted()


# ── 总结 ──────────────────────────────────────────


print("\\n" + "=" * 60)
print(f"P1-3 测试: {passed} passed, {failed} failed")
print("=" * 60)
if failed:
    print("失败详情:")
    for m in fail_msgs:
        print(f"  - {m}")
    sys.exit(1)
sys.exit(0)



"""

def _run_module_body() -> None:
    """执行原模块体, 把 ``sys.exit()`` 包装成 ``RuntimeError``."""
    import sys as _sys
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

# ── pytest 集成 ────────────────────────────────────────────
def test_test_p1_3_subagent() -> None:
    """原模块体直接执行, 把 sys.exit 转成 pytest 结果."""
    import sys
    import pytest as _pytest
    try:
        exec(compile('test_parent_and_sub_both_persisted()\n\n\n# ── 总结 ──────────────────────────────────────────\n\n\nprint("\\n" + "=" * 60)\nprint(f"P1-3 测试: {passed} passed, {failed} failed")\nprint("=" * 60)\nif failed:\n    print("失败详情:")\n    for m in fail_msgs:\n        print(f"  - {m}")\n    sys.exit(1)\nsys.exit(0)\n' , 'tests\\test_p1_3_subagent.py', "exec"), globals())
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"test_p1_3_subagent 退出码 {code}")
