"""
P1-3/P1-2 补充测试:
- delegate_many (并行 sub-agent)
- 长轮询 await_approval 端点
- 树状端点含多层 (grand-child)
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time

os.environ.setdefault("DATA_AI_DEV_MODE", "true")

THIS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(THIS, "..", "src"))
sys.path.insert(0, SRC)

from data_ai.core.agent.base import AgentConfig, DefaultAgent  # noqa: E402
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


class _MockLLMManager:
    def __init__(self, response_text: str = "ok"):
        self.response_text = response_text
        self.call_log: list[str] = []

    def get_client(self, model_id): return self

    def get_context_manager(self, model_id=None):
        class _NullManager:
            def trim_messages(self, messages, system_message=None):
                return messages
        return _NullManager()

    async def chat(self, messages, model=None, tools=None, **kwargs):
        self.call_log.append(f"chat@{time.time():.3f}")
        # 模拟 50ms LLM 延迟
        await asyncio.sleep(0.05)
        return ChatResponse(content=self.response_text, model=model or "mock",
                          usage={"total_tokens": 5}, finish_reason="stop")

    async def chat_stream(self, messages, model=None, **kwargs):
        yield ChatResponse(content=self.response_text, model=model or "mock",
                          usage={"total_tokens": 5}, finish_reason="stop")


# ── 1. delegate_many 并行 ─────────────────


def test_delegate_many_parallel() -> None:
    print("\n[1] delegate_many 并行 sub-agent")
    tmpdir = tempfile.mkdtemp(prefix="p13many-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    parent = DefaultAgent(
        config=AgentConfig(enable_sub_agent=True),
        llm_manager=_MockLLMManager("p"),
        checkpoint_store=store,
    )
    parent.run_id = "p13many-parent"

    # 5 个 sub-agent, 每个 mock LLM 睡 0.05s
    # 串行需要 0.25s, 并行应该 ~0.1s (含 0.05s + 少量 overhead)
    queries = [
        {"query": f"Q{i}", "role": "customer_service" if i % 2 == 0 else "secretary"}
        for i in range(5)
    ]
    t0 = time.time()
    results = asyncio.run(parent.delegate_many(queries))
    elapsed = time.time() - t0

    _check("返回 5 个结果", len(results) == 5)
    _check("5 个 run_id 唯一", len({r["run_id"] for r in results}) == 5)
    _check("5 个都成功 (无 error key)", all("error" not in r for r in results))
    _check(f"并行耗时 < 0.2s (实际 {elapsed:.3f}s)", elapsed < 0.2, f"got {elapsed:.3f}s")


test_delegate_many_parallel()


# ── 2. delegate_many 空查询 ──────────────


def test_delegate_many_empty() -> None:
    print("\n[2] delegate_many 空查询")
    parent = DefaultAgent(
        config=AgentConfig(),
        llm_manager=_MockLLMManager(),
    )
    result = asyncio.run(parent.delegate_many([]))
    _check("空查询返回 []", result == [])


test_delegate_many_empty()


# ── 3. /v1/agents/runs/{id}/await_approval 长轮询 — 立即返回(无 pending) ─


def test_long_poll_no_pending() -> None:
    print("\n[3] await_approval 端点 — 立即返回 (running 无 pending)")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from data_ai.core.api.extensions import router

    tmpdir = tempfile.mkdtemp(prefix="p13longpoll-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    # 存一个 running 状态, 没 pending_approval
    async def _setup():
        await store.save(AgentCheckpoint(
            run_id="lp-test-1",
            created_at=time.time(),
            updated_at=time.time(),
            status="running",
        ))
    asyncio.run(_setup())
    set_checkpoint_store(store)

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/v1/agents/runs/lp-test-1/await_approval?timeout=1.0")
    _check("HTTP 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    body = r.json()
    _check("object=timeout (无 pending)", body.get("object") == "timeout", f"got {body.get('object')}")
    _check("pending=False", body.get("pending") is False)
    _check("status=running", body.get("status") == "running")

    # 不存在
    r2 = client.get("/v1/agents/runs/does-not-exist/await_approval?timeout=0.5")
    _check("不存在 → 404", r2.status_code == 404)


test_long_poll_no_pending()


# ── 4. /v1/agents/runs/{id}/await_approval 长轮询 — 立即返回(有 pending) ─


def test_long_poll_immediate_with_pending() -> None:
    print("\n[4] await_approval 端点 — 立即返回 (有 pending)")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from data_ai.core.api.extensions import router

    tmpdir = tempfile.mkdtemp(prefix="p13lp-pending-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    async def _setup():
        await store.save(AgentCheckpoint(
            run_id="lp-test-pending",
            created_at=time.time(),
            updated_at=time.time(),
            status="awaiting_approval",
            pending_approval={
                "tool_name": "dangerous_write",
                "arguments": {"path": "/etc/x"},
                "tool_call_id": "tc-1",
                "iteration": 1,
                "requested_at": time.time(),
            },
        ))
    asyncio.run(_setup())

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/v1/agents/runs/lp-test-pending/await_approval?timeout=5.0")
    _check("HTTP 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    body = r.json()
    _check("object=await_approval", body.get("object") == "await_approval", f"got {body.get('object')}")
    _check("pending=True", body.get("pending") is True)
    _check("含 tool_name=dangerous_write", body.get("pending_approval", {}).get("tool_name") == "dangerous_write")
    _check("elapsed_s < 1.0 (立即返回)", body.get("elapsed_s", 99) < 1.0)


test_long_poll_immediate_with_pending()


# ── 5. /v1/agents/runs/{id}/await_approval — 终态立即返回 ─


def test_long_poll_finished() -> None:
    print("\n[5] await_approval 端点 — finished 状态立即返回")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from data_ai.core.api.extensions import router

    tmpdir = tempfile.mkdtemp(prefix="p13lp-fin-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    async def _setup():
        await store.save(AgentCheckpoint(
            run_id="lp-test-finished",
            created_at=time.time(),
            updated_at=time.time(),
            status="finished",
            final_content="All done!",
        ))
    asyncio.run(_setup())

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/v1/agents/runs/lp-test-finished/await_approval?timeout=2.0")
    body = r.json()
    _check("HTTP 200", r.status_code == 200, f"got {r.status_code}")
    _check("object=finished", body.get("object") == "finished", f"got {body.get('object')}")
    _check("finished=True", body.get("finished") is True)
    _check("status=finished", body.get("status") == "finished")
    _check("含 final_content_preview", body.get("final_content_preview") == "All done!")


test_long_poll_finished()


# ── 6. 树状端点含 grand-child ──────────────


def test_tree_with_grandchild() -> None:
    print("\n[6] tree 端点 — 3 层嵌套")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from data_ai.core.api.extensions import router

    tmpdir = tempfile.mkdtemp(prefix="p13tree3-")
    store = FileCheckpointStore(base_dir=tmpdir)
    set_checkpoint_store(store)

    async def _setup():
        # root → child → grandchild
        await store.save(AgentCheckpoint(
            run_id="root3", created_at=1.0, updated_at=1.0, status="finished",
            metadata={"parent_run_id": None},
        ))
        await store.save(AgentCheckpoint(
            run_id="root3/child", created_at=2.0, updated_at=2.0, status="finished",
            metadata={"parent_run_id": "root3", "preset_role": "secretary"},
        ))
        await store.save(AgentCheckpoint(
            run_id="root3/child/grand", created_at=3.0, updated_at=3.0, status="finished",
            metadata={"parent_run_id": "root3/child", "preset_role": "customer_service"},
        ))


_MODULE_BODY = """
    asyncio.run(_setup())

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    r = client.get("/v1/agents/runs/root3/tree?max_depth=5")
    _check("HTTP 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    body = r.json()
    root = body.get("root", {})
    _check("root 1 个 child", len(root.get("children", [])) == 1)
    child = root["children"][0]
    _check("child 1 个 grandchild", len(child.get("children", [])) == 1)
    grand = child["children"][0]
    _check("grandchild run_id 正确", grand.get("run_id") == "root3/child/grand")
    _check("grandchild 无 children (叶子)", grand.get("children") == [])


test_tree_with_grandchild()


# ── 总结 ──────────────────────────────────


print("\\n" + "=" * 60)
print(f"P1 补充测试: {passed} passed, {failed} failed")
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
def test_test_p1_supplementary() -> None:
    """原模块体直接执行, 把 sys.exit 转成 pytest 结果."""
    import sys
    import pytest as _pytest
    try:
        exec(compile('test_tree_with_grandchild()\n\n\n# ── 总结 ──────────────────────────────────\n\n\nprint("\\n" + "=" * 60)\nprint(f"P1 补充测试: {passed} passed, {failed} failed")\nprint("=" * 60)\nif failed:\n    print("失败详情:")\n    for m in fail_msgs:\n        print(f"  - {m}")\n    sys.exit(1)\nsys.exit(0)\n' , 'tests\\test_p1_supplementary.py', "exec"), globals())
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"test_p1_supplementary 退出码 {code}")
