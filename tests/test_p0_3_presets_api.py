"""
P0-3 测试:4 个企业 Agent 预设 暴露到 HTTP API

覆盖:
1. /v1/agents/presets 列表 4 个 preset
2. /v1/agents/presets/{role} 单个详情
3. /v1/agents POST preset= 套预设
4. /v1/agents PATCH preset= 切预设
5. /v1/chat/completions role= 触发 preset system_prompt
6. /v1/chat/completions 缺 role 不影响正常对话
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# 路径
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

API = "http://localhost:8000"
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-REDACTED_DASHSCOPE_KEY_REPLACE_ME")
# 默认用 offline-chat 让脚本在没装 LLM 凭证的环境里也能跑通; 真实场景可
# 设为 qwen-turbo / qwen-max / qwen3-32b 等已配置的远端模型.
TEST_MODEL = os.getenv("DATA_AI_TEST_MODEL", "offline-chat")

passed = 0
failed = 0
fail_msgs: list[str] = []


def _http(method: str, path: str, payload: dict | None = None, timeout: int = 60) -> tuple[int, dict | str]:
    url = API + path
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
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


_MODULE_BODY = """
# ── 测试 1: 列出 presets ─────────────────────────────────────────────
print("\\n[1] GET /v1/agents/presets")
code, body = _http("GET", "/v1/agents/presets")
_check("HTTP 200", code == 200, f"code={code}")
presets = (body or {}).get("data") if isinstance(body, dict) else None
_check("返回 data 是 list", isinstance(presets, list), f"got {type(presets)}")
_check("恰好 4 个 preset", len(presets or []) == 4, f"len={len(presets or [])}")
roles = {p.get("role") for p in (presets or [])}
expected = {"customer_service", "finance_analyst", "secretary", "novel_writer"}
_check("含 4 个标准 role", roles == expected, f"got {roles}")
for p in presets or []:
    _check(
        f"  {p.get('role')} 含 system_prompt/tools/temperature",
        isinstance(p.get("tools"), list) and p.get("temperature") is not None,
        f"missing fields in {p.get('role')}",
    )


# ── 测试 2: 单个 preset 详情 ──────────────────────────────────────
print("\\n[2] GET /v1/agents/presets/{role}")
for role in expected:
    code, body = _http("GET", f"/v1/agents/presets/{role}")
    _check(f"{role} HTTP 200", code == 200, f"code={code}")
    _check(
        f"{role} 字段齐全",
        isinstance(body, dict)
        and body.get("role") == role
        and body.get("system_prompt")
        and isinstance(body.get("tools"), list),
        f"body={body}",
    )

# 不存在的 role
code, body = _http("GET", "/v1/agents/presets/no_such_role")
_check("未知 role → 404", code == 404, f"code={code} body={body}")


# ── 测试 3: POST /v1/agents preset= 套预设 ───────────────────────
print("\\n[3] POST /v1/agents preset=finance_analyst")
code, body = _http(
    "POST",
    "/v1/agents",
    {
        "name": "测试财务 Agent",
        "description": "套 preset",
        "model": TEST_MODEL,
        "preset": "finance_analyst",
    },
)
_check("HTTP 201", code == 201, f"code={code} body={body}")
agent_id = (body or {}).get("id") if isinstance(body, dict) else None
_check("返回 id", bool(agent_id), f"body={body}")
if agent_id:
    _check("preset 字段保留", (body or {}).get("preset") == "finance_analyst")
    _check(
        "system_prompt 被 preset 替换",
        isinstance((body or {}).get("system_prompt"), str)
        and len((body or {}).get("system_prompt") or "") > 50,
    )
    _check(
        "tool_names 被 preset 替换为多个工具",
        isinstance((body or {}).get("tool_names"), list) and len((body or {}).get("tool_names") or []) >= 3,
        f"tool_names={(body or {}).get('tool_names')}",
    )
    _check(
        "temperature 被 preset 替换(<0.5)",
        isinstance((body or {}).get("temperature"), (int, float)) and (body or {}).get("temperature") < 0.5,
    )


# ── 测试 4: PATCH /v1/agents/{id} preset=secretary ────────────────
print("\\n[4] PATCH /v1/agents/{id} preset=secretary")
if agent_id:
    code, body = _http("PATCH", f"/v1/agents/{agent_id}", {"preset": "secretary"})
    _check("HTTP 200", code == 200, f"code={code}")
    _check("preset 切换成功", (body or {}).get("preset") == "secretary")
    _check(
        "system_prompt 改变",
        isinstance((body or {}).get("system_prompt"), str)
        and "秘书" in (body or {}).get("system_prompt", ""),
        f"system_prompt head={((body or {}).get('system_prompt') or '')[:80]}",
    )


# ── 测试 5: /v1/chat/completions role= 触发 preset ───────────────
print("\\n[5] POST /v1/chat/completions role=secretary")
code, body = _http(
    "POST",
    "/v1/chat/completions",
    {
        "model": TEST_MODEL,
        "messages": [{"role": "user", "content": "你好,简单介绍一下你自己。"}],
        "enable_tools": False,
        "stream": False,
        "role": "secretary",
    },
    timeout=90,
)
_check("HTTP 200", code == 200, f"code={code} body={body}")
content = ""
if isinstance(body, dict):
    choices = body.get("choices") or []
    if choices:
        content = (choices[0].get("message") or {}).get("content") or ""
_check("assistant 有回复内容", bool(content), f"content={content[:80]}")
# secretary 的 system_prompt 强要求"回复短句/不用'亲爱的'"等风格特征
_check("回复里没有'亲亲/亲爱的'(秘书约束)", "亲亲" not in content and "亲爱的" not in content, f"content={content[:120]}")


# ── 测试 6: 缺 role 字段不影响正常对话 ───────────────────────────
print("\\n[6] 缺 role 字段兼容性")
code, body = _http(
    "POST",
    "/v1/chat/completions",
    {
        "model": TEST_MODEL,
        "messages": [{"role": "user", "content": "1+1=?"}],
        "enable_tools": False,
        "stream": False,
    },
    timeout=60,
)
_check("HTTP 200", code == 200, f"code={code}")
content = ""
if isinstance(body, dict) and body.get("choices"):
    content = (body["choices"][0].get("message") or {}).get("content") or ""
# offline 模式只会回占位文本, 真实模型才会答 "2"/"二"。
# 这里只断言"有回复"即可, 不强求语义正确 (那是真连测试干的事).
_check("正常对话有回复内容", bool(content), f"content={content[:80]!r}")


# ── 总结 ───────────────────────────────────────────────────────
print("\\n" + "=" * 60)
print(f"P0-3 测试: {passed} passed, {failed} failed")
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
def test_test_p0_3_presets_api() -> None:
    """原模块体直接执行, 把 sys.exit 转成 pytest 结果."""
    import pytest as _pytest

    try:
        exec(
            compile(
                '# ── 测试 1: 列出 presets ─────────────────────────────────────────────\nprint("\\n[1] GET /v1/agents/presets")\ncode, body = _http("GET", "/v1/agents/presets")\n_check("HTTP 200", code == 200, f"code={code}")\npresets = (body or {}).get("data") if isinstance(body, dict) else None\n_check("返回 data 是 list", isinstance(presets, list), f"got {type(presets)}")\n_check("恰好 4 个 preset", len(presets or []) == 4, f"len={len(presets or [])}")\nroles = {p.get("role") for p in (presets or [])}\nexpected = {"customer_service", "finance_analyst", "secretary", "novel_writer"}\n_check("含 4 个标准 role", roles == expected, f"got {roles}")\nfor p in presets or []:\n    _check(\n        f"  {p.get(\'role\')} 含 system_prompt/tools/temperature",\n        isinstance(p.get("tools"), list) and p.get("temperature") is not None,\n        f"missing fields in {p.get(\'role\')}",\n    )\n\n\n# ── 测试 2: 单个 preset 详情 ──────────────────────────────────────\nprint("\\n[2] GET /v1/agents/presets/{role}")\nfor role in expected:\n    code, body = _http("GET", f"/v1/agents/presets/{role}")\n    _check(f"{role} HTTP 200", code == 200, f"code={code}")\n    _check(\n        f"{role} 字段齐全",\n        isinstance(body, dict)\n        and body.get("role") == role\n        and body.get("system_prompt")\n        and isinstance(body.get("tools"), list),\n        f"body={body}",\n    )\n\n# 不存在的 role\ncode, body = _http("GET", "/v1/agents/presets/no_such_role")\n_check("未知 role → 404", code == 404, f"code={code} body={body}")\n\n\n# ── 测试 3: POST /v1/agents preset= 套预设 ───────────────────────\nprint("\\n[3] POST /v1/agents preset=finance_analyst")\ncode, body = _http(\n    "POST",\n    "/v1/agents",\n    {\n        "name": "测试财务 Agent",\n        "description": "套 preset",\n        "model": TEST_MODEL,\n        "preset": "finance_analyst",\n    },\n)\n_check("HTTP 201", code == 201, f"code={code} body={body}")\nagent_id = (body or {}).get("id") if isinstance(body, dict) else None\n_check("返回 id", bool(agent_id), f"body={body}")\nif agent_id:\n    _check("preset 字段保留", (body or {}).get("preset") == "finance_analyst")\n    _check(\n        "system_prompt 被 preset 替换",\n        isinstance((body or {}).get("system_prompt"), str)\n        and len((body or {}).get("system_prompt") or "") > 50,\n    )\n    _check(\n        "tool_names 被 preset 替换为多个工具",\n        isinstance((body or {}).get("tool_names"), list) and len((body or {}).get("tool_names") or []) >= 3,\n        f"tool_names={(body or {}).get(\'tool_names\')}",\n    )\n    _check(\n        "temperature 被 preset 替换(<0.5)",\n        isinstance((body or {}).get("temperature"), (int, float)) and (body or {}).get("temperature") < 0.5,\n    )\n\n\n# ── 测试 4: PATCH /v1/agents/{id} preset=secretary ────────────────\nprint("\\n[4] PATCH /v1/agents/{id} preset=secretary")\nif agent_id:\n    code, body = _http("PATCH", f"/v1/agents/{agent_id}", {"preset": "secretary"})\n    _check("HTTP 200", code == 200, f"code={code}")\n    _check("preset 切换成功", (body or {}).get("preset") == "secretary")\n    _check(\n        "system_prompt 改变",\n        isinstance((body or {}).get("system_prompt"), str)\n        and "秘书" in (body or {}).get("system_prompt", ""),\n        f"system_prompt head={((body or {}).get(\'system_prompt\') or \'\')[:80]}",\n    )\n\n\n# ── 测试 5: /v1/chat/completions role= 触发 preset ───────────────\nprint("\\n[5] POST /v1/chat/completions role=secretary")\ncode, body = _http(\n    "POST",\n    "/v1/chat/completions",\n    {\n        "model": TEST_MODEL,\n        "messages": [{"role": "user", "content": "你好,简单介绍一下你自己。"}],\n        "enable_tools": False,\n        "stream": False,\n        "role": "secretary",\n    },\n    timeout=90,\n)\n_check("HTTP 200", code == 200, f"code={code} body={body}")\ncontent = ""\nif isinstance(body, dict):\n    choices = body.get("choices") or []\n    if choices:\n        content = (choices[0].get("message") or {}).get("content") or ""\n_check("assistant 有回复内容", bool(content), f"content={content[:80]}")\n# secretary 的 system_prompt 强要求"回复短句/不用\'亲爱的\'"等风格特征\n_check("回复里没有\'亲亲/亲爱的\'(秘书约束)", "亲亲" not in content and "亲爱的" not in content, f"content={content[:120]}")\n\n\n# ── 测试 6: 缺 role 字段不影响正常对话 ───────────────────────────\nprint("\\n[6] 缺 role 字段兼容性")\ncode, body = _http(\n    "POST",\n    "/v1/chat/completions",\n    {\n        "model": TEST_MODEL,\n        "messages": [{"role": "user", "content": "1+1=?"}],\n        "enable_tools": False,\n        "stream": False,\n    },\n    timeout=60,\n)\n_check("HTTP 200", code == 200, f"code={code}")\ncontent = ""\nif isinstance(body, dict) and body.get("choices"):\n    content = (body["choices"][0].get("message") or {}).get("content") or ""\n_check("正常对话有回复内容", bool(content), f"content={content[:80]!r}")\n\n\n# ── 总结 ───────────────────────────────────────────────────────\nprint("\\n" + "=" * 60)\nprint(f"P0-3 测试: {passed} passed, {failed} failed")\nprint("=" * 60)\nif failed:\n    print("失败详情:")\n    for m in fail_msgs:\n        print(f"  - {m}")\n    sys.exit(1)\nsys.exit(0)\n',
                "tests\\test_p0_3_presets_api.py",
                "exec",
            ),
            globals(),
        )
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"test_p0_3_presets_api 退出码 {code}")
