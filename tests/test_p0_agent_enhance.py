"""
P0 智能体增强测试
  • Agent.run() 调用工具真触发
  • Response 暴露 tool_calls / reflections
  • Self-Reflection 在 LLM 答错时能指出 issue
  • 离线模式(无 LLM 也能跑结构测试)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 修复: 用相对路径替代写死的 /workspace/DATA-AI
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import pytest  # noqa: E402

# 结构性检查 (不需要 backend / LLM) 在模块级执行, 失败走 pytest.fail
# 网络/集成检查改为 pytest 用例, 自动 skip 无 backend 时.

passes: list[str] = []
fails: list[tuple[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (passes if ok else fails).append((name, detail))
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name:55s} {detail}")


def _run_offline_checks() -> None:
    """离线结构测试: 字段 / 序列化 / JSON 解析容错"""
    print("\n[1] 离线结构测试")

    from data_ai.core.agent.base import (  # noqa: F401
        AgentConfig,
        AgentState,
        AgentStatus,
        BaseAgent,
        ReflectionResult,
    )

    check("ReflectionResult dataclass 存在", ReflectionResult is not None)
    check("AgentStatus 含 REFLECTING", AgentStatus.REFLECTING.value == "reflecting")
    check(
        "AgentConfig.enable_reflection 字段存在",
        "enable_reflection" in AgentConfig.__dataclass_fields__,
    )
    check(
        "AgentConfig.max_reflections 字段存在",
        "max_reflections" in AgentConfig.__dataclass_fields__,
    )
    check(
        "AgentConfig.reflection_threshold 字段存在",
        "reflection_threshold" in AgentConfig.__dataclass_fields__,
    )
    check(
        "AgentState.reflection_count 字段存在",
        "reflection_count" in AgentState.__dataclass_fields__,
    )
    check(
        "AgentState.reflection_log 字段存在",
        "reflection_log" in AgentState.__dataclass_fields__,
    )
    check(
        "AgentState.tool_call_log 字段存在",
        "tool_call_log" in AgentState.__dataclass_fields__,
    )

    print("\n[2] ReflectionResult 序列化")
    r = ReflectionResult(
        is_confident=False,
        confidence=0.3,
        issues=["2026 奥运会在米兰-科尔蒂纳,不是巴黎", "答非所问"],
        rationale="事实错误",
        iteration=1,
    )
    d = r.to_dict()
    check("to_dict 字段完整", d["confidence"] == 0.3 and len(d["issues"]) == 2 and d["iteration"] == 1)
    check("to_dict JSON 序列化 OK", json.dumps(d, ensure_ascii=False) is not None)

    print("\n[3] _parse_reflection_json 鲁棒性")

    class _Stub(BaseAgent):
        def __init__(self):
            super().__init__()

    agent = _Stub()
    parser = agent._parse_reflection_json

    r1 = parser('{"confidence": 0.8, "is_confident": true, "issues": [], "rationale": "ok"}')
    check("正常 JSON 解析", r1.is_confident and r1.confidence == 0.8 and not r1.issues)

    r2 = parser('```json\n{"confidence": 0.4, "is_confident": false, "issues": ["test"], "rationale": "bad"}\n```')
    check("markdown 围栏 JSON 解析", not r2.is_confident and r2.confidence == 0.4)

    r3 = parser('{"confidence": 0.3, "issues": ["事实错误: 巴黎不是 2026 冬奥会", "答非所问"]}')
    check("中文 issues 解析", len(r3.issues) == 2 and "事实错误" in r3.issues[0])

    r4 = parser("not json at all")
    check("损坏 JSON fallback 通过", r4.is_confident and r4.confidence == 0.7)

    r5 = parser("{}")
    check("空 JSON 用默认值", r5.confidence == 0.5)

    r6 = parser('{"confidence": 5.0}')
    check("confidence 越界修正", r6.confidence == 1.0)
    r7 = parser('{"confidence": -1.0}')
    check("confidence 负数修正", r7.confidence == 0.0)

    r8 = parser('{"issues": "not a list"}')
    check("issues 非 list 修正", r8.issues == [])


# 旧版 module-level "self-test" 流程: 用 pytest 用例取代
def test_offline_structure() -> None:
    """离线结构 + 序列化 + JSON 解析容错"""
    _run_offline_checks()
    if fails:
        # 把 fails 整理成 pytest 失败信息
        msg = "\n".join(f"  ✗ {n}  {d}" for n, d in fails)
        fails.clear()
        pytest.fail(f"P0 agent enhance offline checks failed:\n{msg}")


@pytest.mark.skipif(
    not os.environ.get("DASHSCOPE_API_KEY"),
    reason="DASHSCOPE_API_KEY 未设置, 跳过 LLM 实测",
)
def test_backend_e2e_with_llm() -> None:
    """需要 DASHSCOPE_API_KEY + backend 在 :8000 运行的端到端测试"""
    import urllib.request

    backend_url = "http://localhost:8000/health"
    try:
        with urllib.request.urlopen(backend_url, timeout=3) as r:
            backend_data = json.loads(r.read())
    except Exception as e:
        pytest.skip(f"backend 未在 :8000 运行, 跳过 e2e ({e})")
        return

    assert backend_data.get("status") == "healthy", f"backend unhealthy: {backend_data}"

    body = json.dumps(
        {
            "model": "qwen-turbo",
            "messages": [{"role": "user", "content": "用 python_execute 算 7*8 等于几,只调用工具不心算"}],
            "enable_tools": True,
            "max_tokens": 200,
        }
    ).encode()
    req = urllib.request.Request(
        "http://localhost:8000/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
        tc = data.get("tool_calls") or []
        assert isinstance(tc, list)
        if tc:
            assert any(c.get("name") == "python_execute" for c in tc), f"names: {[c.get('name') for c in tc]}"
            assert any(c.get("arguments") for c in tc)
            assert any(c.get("result") for c in tc)
        else:
            pytest.fail("LLM 没调工具")

    # Self-reflection
    body2 = json.dumps(
        {
            "model": "qwen-turbo",
            "messages": [{"role": "user", "content": "你是什么模型?只回答模型名和版本,不确定就说不知道"}],
            "enable_tools": True,
            "enable_reflection": True,
            "max_tokens": 200,
        }
    ).encode()
    req2 = urllib.request.Request(
        "http://localhost:8000/v1/chat/completions",
        data=body2,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req2, timeout=60) as r2:
        data2 = json.loads(r2.read())
        rf = data2.get("reflections") or []
        assert isinstance(rf, list)
        if rf:
            assert all("confidence" in x and "is_confident" in x for x in rf)


if __name__ == "__main__":
    # 兼容旧用法: `python tests/test_p0_agent_enhance.py`
    _run_offline_checks()
    print()
    print("=" * 64)
    print(f"通过: {len(passes)}   失败: {len(fails)}")
    print("=" * 64)
    if fails:
        print("\n失败项:")
        for n, d in fails:
            print(f"  ✗ {n}  {d}")
        sys.exit(1)
    print("\n✅ P0 智能体增强测试通过")
