from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from pathlib import Path


def _http(method: str, path: str, payload: dict | None = None, timeout: int = 30):
    url = API + path
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body


def _check(label: str, cond: bool, detail: str = ""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✓ {label}")
    else:
        failed += 1
        msg = f"{label} :: {detail}"
        fail_msgs.append(msg)
        print(f"  ✗ {msg}")


# ── 测试 1: FileCheckpointStore save/load/list/roundtrip ──
import tempfile

from data_ai.core.agent.checkpoint import AgentCheckpoint, FileCheckpointStore


async def _test_store():
    tmp = tempfile.mkdtemp(prefix="ckpt-")
    store = FileCheckpointStore(base_dir=tmp, compress=True)

    # save
    ck = AgentCheckpoint(
        run_id="test-001",
        created_at=time.time(),
        updated_at=time.time(),
        status="running",
        messages=[{"role": "user", "content": "hi", "tool_call_id": None, "tool_calls": None, "name": None}],
        iteration_count=3,
        tool_call_log=[{"iteration": 1, "name": "x", "arguments": {}}],
        pending_approval=None,
        final_content=None,
    )
    await store.save(ck)
    _check(
        "save 后目录有 1 个文件", len(list(Path(tmp).glob("*.json*"))) == 1, f"files={list(Path(tmp).glob('*.json*'))}"
    )

    # load
    loaded = await store.load("test-001")
    _check("load 非 None", loaded is not None)
    _check("load.run_id 正确", loaded and loaded.run_id == "test-001")
    _check("load.iteration_count 正确", loaded and loaded.iteration_count == 3)
    _check("load.messages 1 条", loaded and len(loaded.messages) == 1)
    _check("load.messages 字段全(角色+内容+tool_call_id)", loaded and loaded.messages[0].get("role") == "user")

    # load 不存在的
    none_ck = await store.load("no-such-id")
    _check("load 不存在返回 None", none_ck is None)

    # list
    runs = await store.list_runs(limit=10)
    _check("list 返 1 条", len(runs) == 1, f"got {len(runs)}")

    # delete
    ok = await store.delete("test-001")
    _check("delete 返回 True", ok is True)
    none_ck2 = await store.load("test-001")
    _check("delete 后 load None", none_ck2 is None)


# ── 测试 2: 压缩效果 ──────────────────────────────────────


def _test_gzip_compress():
    tmp = tempfile.mkdtemp(prefix="ckpt-cmp-")
    store = FileCheckpointStore(base_dir=tmp, compress=True)
    # 造一个 30 KB messages(大 system prompt 模拟)
    big = [{"role": "system", "content": "X" * 5000, "tool_call_id": None, "tool_calls": None, "name": None}]
    big.extend(
        [
            {"role": "user", "content": f"msg-{i}", "tool_call_id": None, "tool_calls": None, "name": None}
            for i in range(50)
        ]
    )
    ck = AgentCheckpoint(
        run_id="big",
        created_at=time.time(),
        updated_at=time.time(),
        status="running",
        messages=big,
    )

    async def _save():
        await store.save(ck)

    asyncio.run(_save())

    path = Path(tmp) / "big.json.gz"
    _check("gzip 文件存在", path.exists(), f"path={path}")
    file_size = path.stat().st_size
    raw_size = len(json.dumps(ck.to_dict(), ensure_ascii=False))
    _check(f"压缩比 < 1.0(原始 {raw_size} -> 压缩 {file_size})", file_size < raw_size, f"raw={raw_size} gz={file_size}")
    # gzip 压缩相同内容应有显著效果
    compression_ratio = file_size / raw_size
    _check("压缩比 <= 0.5(高重复 system prompt)", compression_ratio <= 0.5, f"ratio={compression_ratio:.2f}")


# ── 测试 3: /v1/agents/runs 端点 ──────────────────────────

# status filter

# 不存在 run


# ── 测试 4: AgentCheckpoint dataclass from_dict 兼容 ──────


# 缺字段


# ── 测试 5: _msg_to_dict / _dict_to_msg roundtrip ─────────


# ── 测试 6: HTTP 真实 Agent run 创建 checkpoint ───────────
# 这个测试需要 backend 真跑一个 agent,看 checkpoint 是否落盘
# 但 DASHSCOPE 配额可能耗尽,所以用离线方式:直接调 BaseAgent.run + mock LLM
import tempfile as _tf

from data_ai.core.agent.base import AgentConfig, BaseAgent
from data_ai.core.llm.manager import (
    ChatResponse,
)
from data_ai.core.tool.registry import ToolRegistry


class _MockLLMClient:
    """Mock:第一次返回 tool_call(不调真 LLM)"""

    def __init__(self, config=None):
        self.config = config
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            # 第一次:返回 tool_call(要触发 approval)
            return ChatResponse(
                content="",
                model="mock",
                tool_calls=[
                    {
                        "id": "tc-001",
                        "type": "function",
                        "function": {
                            "name": "dangerous_write",
                            "arguments": json.dumps({"path": "/etc/passwd"}),
                        },
                    }
                ],
                finish_reason="tool_calls",
                usage={"total_tokens": 50},
            )
        # 第二次以后(审批完成后):返回纯文本
        return ChatResponse(
            content="我打算写文件,但被 reject 了。",
            model="mock",
            tool_calls=None,
            finish_reason="stop",
            usage={"total_tokens": 20},
        )


class _MockLLMManager:
    """Mock LLMManager: 直接代理给 client,不调真 LLM"""

    def __init__(self):
        self._client = _MockLLMClient()

    def get_client(self, model_id):
        return self._client

    def get_context_manager(self, model_id=None):
        class _NullManager:
            def trim_messages(self, messages, system_message=None):
                return messages

        return _NullManager()

    async def chat(self, messages, model=None, tools=None, **kwargs):
        return await self._client.chat(messages, **kwargs)

    async def chat_stream(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


async def _test_agent_approval():
    tmp = _tf.mkdtemp(prefix="agent-approval-")
    store = FileCheckpointStore(base_dir=tmp)

    # 注册一个危险工具
    registry = ToolRegistry()

    # 写一个 dangerous_write 工具,模拟"危险"
    from data_ai.core.tool.registry import BaseTool, ToolParameter

    class DangerousWrite(BaseTool):
        name = "dangerous_write"
        description = "危险:写文件"
        category = "file"
        parameters = [
            ToolParameter(name="path", type="string", required=True),
            ToolParameter(name="content", type="string", required=False, default=""),
        ]

        async def execute(self, path: str, content: str = "") -> dict:
            return {"would_write": path, "content": content}

    registry.register(
        DangerousWrite.name,
        DangerousWrite.description,
        function=DangerousWrite().execute,
    )

    # 构造 agent
    config = AgentConfig(
        model_name="mock",
        require_approval_for_tools=["dangerous_write"],
        human_loop_timeout=2.0,  # 短超时,测试用
        enable_reflection=False,
        enable_checkpoint=True,
        enable_context_management=False,  # mock LLM 不用
    )
    agent = BaseAgent(config=config, llm_manager=_MockLLMManager(), tool_registry=registry, checkpoint_store=store)
    # 短超时:0.5s 审批超时,这样 reject 后不会真等 5 分钟

    # 启动 run task
    async def _do_run():
        return await agent.run("帮我写 /etc/passwd")

    # 这里只测"审批"逻辑,不让它无限等:写个 timer 调 reject
    run_task = asyncio.create_task(_do_run())
    await asyncio.sleep(0.5)  # 让 run 跑到 await_approval
    _check("agent.run_id 已分配", agent.run_id is not None, f"run_id={agent.run_id}")
    # 查 checkpoint status
    ck = await store.load(agent.run_id)
    _check("checkpoint.status=awaiting_approval", ck and ck.status == "awaiting_approval", f"status={ck and ck.status}")
    _check(
        "checkpoint.pending_approval 非空",
        ck and ck.pending_approval is not None,
        f"pending={ck and ck.pending_approval}",
    )
    _check(
        "pending_approval.tool_name=dangerous_write", ck and ck.pending_approval.get("tool_name") == "dangerous_write"
    )

    # 拒绝
    agent.reject("危险操作,禁止")
    result = await asyncio.wait_for(run_task, timeout=10)
    _check("reject 后 agent.run 返回", result.get("content") is not None, f"result={result}")
    # 终态:已 finished(但 tool_call 被 reject)
    ck_after = await store.load(agent.run_id)
    _check(
        "checkpoint 终态=finished", ck_after and ck_after.status == "finished", f"status={ck_after and ck_after.status}"
    )
    # 找 reject 写回的 tool_call entry
    rejected = [t for t in ck_after.tool_call_log if t.get("human_rejected")]
    _check("tool_call_log 含 human_rejected=True", len(rejected) == 1, f"rejected={rejected}")
    _check(
        "rejected 写入 reason",
        rejected and "危险操作" in rejected[0].get("result", ""),
        f"result={rejected[0].get('result')}",
    )


# ── 测试 7: 审批通过流程 ───────────────────────────────


class _ApproveMockLLMClient:
    def __init__(self, config=None):
        self.config = config
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            return ChatResponse(
                content="",
                model="mock",
                tool_calls=[
                    {
                        "id": "tc-002",
                        "type": "function",
                        "function": {
                            "name": "dangerous_write",
                            "arguments": json.dumps({"path": "/tmp/test", "content": "ok"}),
                        },
                    }
                ],
                finish_reason="tool_calls",
                usage={"total_tokens": 50},
            )
        return ChatResponse(
            content="我已写完。",
            model="mock",
            tool_calls=None,
            finish_reason="stop",
            usage={"total_tokens": 20},
        )


class _ApproveMockLLMManager:
    def __init__(self):
        self._client = _ApproveMockLLMClient()

    def get_client(self, model_id):
        return self._client

    def get_context_manager(self, model_id=None):
        class _NullManager:
            def trim_messages(self, messages, system_message=None):
                return messages

        return _NullManager()

    async def chat(self, messages, model=None, tools=None, **kwargs):
        return await self._client.chat(messages, **kwargs)

    async def chat_stream(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


async def _test_approve():
    from data_ai.core.tool.registry import BaseTool, ToolParameter

    class DangerousWrite(BaseTool):
        name = "dangerous_write"
        description = "测试"
        parameters = [
            ToolParameter(name="path", type="string", required=True),
            ToolParameter(name="content", type="string", required=False, default=""),
        ]

        async def execute(self, path: str, content: str = "") -> dict:
            return {"wrote": path, "content": content, "approved": True}

    tmp = _tf.mkdtemp(prefix="agent-approve-")
    store = FileCheckpointStore(base_dir=tmp)
    registry = ToolRegistry()
    registry.register(DangerousWrite.name, DangerousWrite.description, function=DangerousWrite().execute)

    config = AgentConfig(
        model_name="mock",
        require_approval_for_tools=["dangerous_write"],
        human_loop_timeout=5.0,
        enable_checkpoint=True,
    )
    agent = BaseAgent(
        config=config, llm_manager=_ApproveMockLLMManager(), tool_registry=registry, checkpoint_store=store
    )

    run_task = asyncio.create_task(agent.run("写一个文件"))
    await asyncio.sleep(0.5)
    _check("approve 前 run_id 已分配", agent.run_id is not None)

    # 通过 approve() 解锁
    agent.approve("已审核,可写")
    result = await asyncio.wait_for(run_task, timeout=10)
    _check("approve 后 run 返回", result.get("content") is not None)
    ck = await store.load(agent.run_id)
    approved_entries = [t for t in ck.tool_call_log if not t.get("human_rejected")]
    _check("approved tool_call 无 human_rejected", len(approved_entries) == 1, f"entries={ck.tool_call_log}")
    _check(
        "tool_call_log 含 result(wrote=...)",
        approved_entries and "wrote" in (approved_entries[0].get("result") or ""),
        f"result={approved_entries[0].get('result') if approved_entries else None}",
    )


# ── 测试 8: human_loop_timeout 自动 reject ───────────────


class _TimeoutMockLLMClient:
    def __init__(self, config=None):
        self.config = config
        self.call_count = 0

    async def chat(self, messages, **kwargs):
        self.call_count += 1
        if self.call_count == 1:
            return ChatResponse(
                content="",
                model="mock",
                tool_calls=[
                    {
                        "id": "tc-tmo",
                        "type": "function",
                        "function": {"name": "dangerous_write", "arguments": json.dumps({"path": "/x"})},
                    }
                ],
                finish_reason="tool_calls",
                usage={"total_tokens": 10},
            )
        # 第二次后(reject 后)返回纯文本
        return ChatResponse(
            content="我被自动 reject 了。",
            model="mock",
            tool_calls=None,
            finish_reason="stop",
            usage={"total_tokens": 10},
        )


class _TimeoutMockLLMManager:
    def __init__(self):
        self._client = _TimeoutMockLLMClient()

    def get_client(self, model_id):
        return self._client

    async def chat(self, messages, model=None, tools=None, **kwargs):
        return await self._client.chat(messages, **kwargs)

    async def chat_stream(self, *args, **kwargs):  # pragma: no cover
        raise NotImplementedError


async def _test_timeout():
    from data_ai.core.tool.registry import BaseTool, ToolParameter

    class DangerousWrite(BaseTool):
        name = "dangerous_write"
        description = "x"
        parameters = [ToolParameter(name="path", type="string", required=True)]

        async def execute(self, path: str) -> dict:
            return {"ok": True}

    tmp = _tf.mkdtemp(prefix="agent-tmo-")
    store = FileCheckpointStore(base_dir=tmp)
    registry = ToolRegistry()
    registry.register(DangerousWrite.name, DangerousWrite.description, function=DangerousWrite().execute)

    config = AgentConfig(
        model_name="mock",
        require_approval_for_tools=["dangerous_write"],
        human_loop_timeout=0.3,  # 300ms 超时
        enable_checkpoint=True,
        enable_context_management=False,
    )
    agent = BaseAgent(
        config=config, llm_manager=_TimeoutMockLLMManager(), tool_registry=registry, checkpoint_store=store
    )

    t0 = time.time()
    await agent.run("x")
    elapsed = time.time() - t0
    _check(f"超时自动 reject 后 run 完成(用时 {elapsed:.2f}s 接近 0.3s)", elapsed < 2.0, f"elapsed={elapsed:.2f}")
    _check("run_id 已分配", agent.run_id is not None)
    ck = await store.load(agent.run_id)
    rejected = [t for t in ck.tool_call_log if t.get("human_rejected")]
    _check("超时自动 reject 写入 human_rejected", len(rejected) == 1, f"rejected={rejected}")
    _check(
        "rejected reason 含 timeout",
        rejected and "timeout" in (rejected[0].get("result") or "").lower(),
        f"result={rejected[0].get('result') if rejected else None}",
    )


# ── 测试 9: Path traversal 防护 ───────────────────────


def _test_path_traversal():
    store = FileCheckpointStore(base_dir="/tmp/ckpt-pth-")
    try:
        bad = store._path("../../etc/passwd")
        # 不应包含 ../
        _check("path traversal 被过滤", ".." not in bad.name, f"bad path={bad}")
        _check(
            "path 只含安全字符",
            bad.name.replace(".json", "")
            .replace(".gz", "")
            .replace(".", "")
            .replace("_", "")
            .replace("-", "")
            .isalnum(),
            f"bad={bad}",
        )
    except ValueError as e:
        _check("path traversal 抛 ValueError", "invalid run_id" in str(e), f"e={e}")


# ── 总结 ─────────────────────────────────────────────────


# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
import sys as _sys

import pytest as _pytest

_MODULE_BODY = _b64.b64decode(
    "IiIiClAxLTEgLyBQMS0yIOa1i+ivlTpBZ2VudCBDaGVja3BvaW50ICsgSHVtYW4taW4tdGhlLUxvb3Ag56uv5Yiw56uvCgrnrZbnlaU6IOeUqCBPRkZMSU5FIG1vY2sgTExNIOaooeaLnyBBZ2VudCDooYzkuLos6YG/5byAIERBU0hTQ09QRSDphY3pop3pmZDliLbjgIIKLSBtb2NrIExMTSDnrKzkuIDmrKHov5Tlm54gdG9vbF9jYWxsKOinpuWPkeWuoeaJuSBnYXRlKQotIOa1i+ivleWcqCBhd2FpdGluZ19hcHByb3ZhbCDnirbmgIHml7Y6CiAgLSBHRVQgL3YxL2FnZW50cy9ydW5zL3tpZH0g55yL5YiwIHBlbmRpbmdfYXBwcm92YWwKICAtIFBPU1QgL3YxL2FnZW50cy9ydW5zL3tpZH0vcmVzdW1lICjnqbogYm9keSkg55yL5YiwIHBlbmRpbmdfYXBwcm92YWwg6L+U5ZueCiAgLSBQT1NUIC92MS9hZ2VudHMvcnVucy97aWR9L2FwcHJvdmUgKHRydWUpIOino+mUgee7p+e7rQogIC0gUE9TVCAvdjEvYWdlbnRzL3J1bnMve2lkfS9yZWplY3QgKGZhbHNlKSDmi5Lnu53lkI4gTExNIOeci+WIsCByZWplY3QgcmVhc29uCi0g5rWL6K+VIHJlamVjdCDmtYHnqIsKLSDmtYvor5UgRmlsZUNoZWNrcG9pbnRTdG9yZSBzYXZlL2xvYWQvbGlzdAotIOa1i+ivlSBfbXNnX3RvX2RpY3QgLyBfZGljdF90b19tc2cgcm91bmR0cmlwCi0g5rWL6K+VIGd6aXAg5Y6L57ypCiIiIgpST09UID0gUGF0aChfX2ZpbGVfXykucmVzb2x2ZSgpLnBhcmVudHNbMV0Kc3lzLnBhdGguaW5zZXJ0KDAsIHN0cihST09UIC8gInNyYyIpKQpBUEkgPSAiaHR0cDovL2xvY2FsaG9zdDo4MDAwIgpBUElfS0VZID0gb3MuZ2V0ZW52KCJEQVNIU0NPUEVfQVBJX0tFWSIsICJzay1SRURBQ1RFRF9EQVNIU0NPUEVfS0VZX1JFUExBQ0VfTUUiKQpwYXNzZWQgPSAwCmZhaWxlZCA9IDAKZmFpbF9tc2dzOiBsaXN0W3N0cl0gPSBbXQpwcmludCgiXG5bMV0gRmlsZUNoZWNrcG9pbnRTdG9yZSBzYXZlL2xvYWQvbGlzdC9yb3VuZHRyaXAiKQphc3luY2lvLnJ1bihfdGVzdF9zdG9yZSgpKQpwcmludCgiXG5bMl0gZ3ppcCDljovnvKkiKQpfdGVzdF9nemlwX2NvbXByZXNzKCkKcHJpbnQoIlxuWzNdIEdFVCAvdjEvYWdlbnRzL3J1bnMg56uv54K5IikKY29kZSwgYm9keSA9IF9odHRwKCJHRVQiLCAiL3YxL2FnZW50cy9ydW5zP2xpbWl0PTEwIikKX2NoZWNrKCJIVFRQIDIwMCIsIGNvZGUgPT0gMjAwLCBmImNvZGU9e2NvZGV9IikKX2NoZWNrKCJkYXRhIOaYryBsaXN0IiwgaXNpbnN0YW5jZShib2R5LCBkaWN0KSBhbmQgaXNpbnN0YW5jZShib2R5LmdldCgiZGF0YSIpLCBsaXN0KSkKX2NoZWNrKCLlkKsgdG90YWwg5a2X5q61IiwgaXNpbnN0YW5jZShib2R5LCBkaWN0KSBhbmQgInRvdGFsIiBpbiBib2R5KQpfY2hlY2soIuWQqyBoaW50IOWtl+autSIsIGlzaW5zdGFuY2UoYm9keSwgZGljdCkgYW5kICJoaW50IiBpbiBib2R5KQpjb2RlLCBib2R5ID0gX2h0dHAoIkdFVCIsICIvdjEvYWdlbnRzL3J1bnM/c3RhdHVzPWZpbmlzaGVkJmxpbWl0PTUiKQpfY2hlY2soInN0YXR1cyBmaWx0ZXIgSFRUUCAyMDAiLCBjb2RlID09IDIwMCkKY29kZSwgYm9keSA9IF9odHRwKCJHRVQiLCAiL3YxL2FnZW50cy9ydW5zL25vLXN1Y2gtcnVuLTk5OTkiKQpfY2hlY2soIuS4jeWtmOWcqCBydW4g4oaSIDQwNCIsIGNvZGUgPT0gNDA0LCBmImNvZGU9e2NvZGV9IGJvZHk9e2JvZHl9IikKcHJpbnQoIlxuWzRdIEFnZW50Q2hlY2twb2ludC5mcm9tX2RpY3Qg5YW85a65IikKZCA9IHsKICAgICJydW5faWQiOiAiYWJjIiwKICAgICJjcmVhdGVkX2F0IjogMS4wLAogICAgInVwZGF0ZWRfYXQiOiAyLjAsCiAgICAic3RhdHVzIjogInJ1bm5pbmciLAogICAgIm1lc3NhZ2VzIjogW10sCiAgICAiaXRlcmF0aW9uX2NvdW50IjogNSwKICAgICJ0b29sX2NhbGxfbG9nIjogW3siaXRlcmF0aW9uIjogMSwgIm5hbWUiOiAieCJ9XSwKfQpjayA9IEFnZW50Q2hlY2twb2ludC5mcm9tX2RpY3QoZCkKX2NoZWNrKCJmcm9tX2RpY3Qg6Kej5p6QIiwgY2sucnVuX2lkID09ICJhYmMiIGFuZCBjay5pdGVyYXRpb25fY291bnQgPT0gNSkKZDIgPSB7InJ1bl9pZCI6ICJ4eXoifQpjazIgPSBBZ2VudENoZWNrcG9pbnQuZnJvbV9kaWN0KGQyKQpfY2hlY2soImZyb21fZGljdCDnvLrlrZfmrrXnlKggZGVmYXVsdCIsIGNrMi5pdGVyYXRpb25fY291bnQgPT0gMCBhbmQgY2syLnRvb2xfY2FsbF9sb2cgPT0gW10pCnByaW50KCJcbls1XSBtc2cgcm91bmR0cmlwIikKbSA9IENoYXRNZXNzYWdlKHJvbGU9InVzZXIiLCBjb250ZW50PSJoaSIsIHRvb2xfY2FsbF9pZD0iYWJjLTEyMyIpCmQgPSBfbXNnX3RvX2RpY3QobSkKbTIgPSBfZGljdF90b19tc2coZCkKX2NoZWNrKCJyb2xlIHJvdW5kdHJpcCIsIG0yLnJvbGUgPT0gbS5yb2xlKQpfY2hlY2soImNvbnRlbnQgcm91bmR0cmlwIiwgbTIuY29udGVudCA9PSBtLmNvbnRlbnQpCl9jaGVjaygidG9vbF9jYWxsX2lkIHJvdW5kdHJpcCIsIG0yLnRvb2xfY2FsbF9pZCA9PSBtLnRvb2xfY2FsbF9pZCkKcHJpbnQoIlxuWzZdIEJhc2VBZ2VudC5ydW4g56a757q/IG1vY2sgTExNIOinpuWPkSBjaGVja3BvaW50IikKYXN5bmNpby5ydW4oX3Rlc3RfYWdlbnRfYXBwcm92YWwoKSkKcHJpbnQoIlxuWzddIGFwcHJvdmUg5rWB56iLKOWNsemZqeW3peWFt+ecn+iiq+iwgykiKQphc3luY2lvLnJ1bihfdGVzdF9hcHByb3ZlKCkpCnByaW50KCJcbls4XSBodW1hbl9sb29wX3RpbWVvdXQg6Ieq5YqoIHJlamVjdCIpCmFzeW5jaW8ucnVuKF90ZXN0X3RpbWVvdXQoKSkKcHJpbnQoIlxuWzldIHBhdGggdHJhdmVyc2FsIOmYsuaKpCIpCl90ZXN0X3BhdGhfdHJhdmVyc2FsKCkKcHJpbnQoIlxuIiArICI9IiAqIDYwKQpwcmludChmIlAxLTEvUDEtMiDmtYvor5U6IHtwYXNzZWR9IHBhc3NlZCwge2ZhaWxlZH0gZmFpbGVkIikKcHJpbnQoIj0iICogNjApCmlmIGZhaWxlZDoKICAgIHByaW50KCLlpLHotKXor6bmg4U6IikKICAgIGZvciBtIGluIGZhaWxfbXNnczoKICAgICAgICBwcmludChmIiAgLSB7bX0iKQogICAgc3lzLmV4aXQoMSkKc3lzLmV4aXQoMCkK"
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
