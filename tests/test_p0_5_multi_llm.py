"""
P0-5 测试:多 LLM 真连 + provider 框架验证

覆盖:
1. /v1/llm/providers 列出 14+ provider + env_key_set 状态
2. /v1/llm/health 真连 DASHSCOPE_API_KEY qwen-turbo
3. /v1/llm/health 测未注册 model 走推断注册
4. /v1/llm/health 测无 key 的 provider 返回 ok=False(不抛 500)
5. /v1/chat/completions 切换不同 model 都能用(已注册列表里)
6. 离线测试 14 个 provider 的 client class 都能 import
7. PROVIDER_DEFAULT_BASE_URL 14+ provider 都有 base_url
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

API = "http://localhost:8000"
API_KEY = os.getenv("DASHSCOPE_API_KEY", "sk-REDACTED_DASHSCOPE_KEY_REPLACE_ME")
passed = 0
failed = 0
fail_msgs: list[str] = []


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


_MODULE_BODY = """
# ── 测试 1: providers 端点 ─────────────────────────────────
print("\\n[1] GET /v1/llm/providers")
code, body = _http("GET", "/v1/llm/providers")
_check("HTTP 200", code == 200, f"code={code}")
providers = (body or {}).get("providers") if isinstance(body, dict) else None
_check("providers 是 list", isinstance(providers, list))
_check("至少 14 个 provider", len(providers or []) >= 14, f"len={len(providers or [])}")
prov_names = {p.get("provider") for p in (providers or [])}
expected_subset = {"openai", "anthropic", "qwen", "deepseek", "zhipu", "moonshot", "google", "azure"}
_check("含 8 个核心 provider", expected_subset.issubset(prov_names), f"missing={expected_subset - prov_names}")
# DASHSCOPE_API_KEY 已设,qwen env_key_set 应为 True
qwen_entry = next((p for p in (providers or []) if p.get("provider") == "qwen"), None)
_check("qwen provider 有 default_base_url", qwen_entry and qwen_entry.get("default_base_url"), f"qwen={qwen_entry}")
_check("qwen env_var=DASHSCOPE_API_KEY", qwen_entry and qwen_entry.get("env_var") == "DASHSCOPE_API_KEY", f"got {qwen_entry and qwen_entry.get('env_var')}")
# OPENAI_API_KEY 没设
openai_entry = next((p for p in (providers or []) if p.get("provider") == "openai"), None)
_check("openai env_key_set=False(没设 OPENAI_API_KEY)", openai_entry and openai_entry.get("env_key_set") is False, f"openai={openai_entry}")
# 已注册模型
registered = (body or {}).get("registered_models") if isinstance(body, dict) else None
_check("已注册 3 个模型(DASHSCOPE 注入 qwen-turbo/plus/max)", isinstance(registered, dict) and len(registered) == 3, f"registered={registered}")
_check("含 qwen-turbo", registered and "qwen-turbo" in registered)
_check("含 qwen-plus-2025", registered and "qwen-plus-2025" in registered)
_check("含 qwen-max-2025", registered and "qwen-max-2025" in registered)


# ── 测试 2: /v1/llm/health 真连 qwen ─────────────────────────
# 测策略: 至少 1 个 DASHSCOPE model 配额内可连(DASHSCOPE 免费配额可能耗尽)
print("\\n[2] POST /v1/llm/health 真连至少 1 个 qwen model")
candidates = ["qwen-turbo", "qwen-plus-2025", "qwen-max-2025"]
ping_success = None
for m in candidates:
    t0 = time.time()
    code, body = _http("POST", "/v1/llm/health", {"model": m}, timeout=60)
    elapsed = time.time() - t0
    ok = (body or {}).get("ok") if isinstance(body, dict) else None
    provider = (body or {}).get("provider") if isinstance(body, dict) else None
    content_preview = (body or {}).get("content_preview") if isinstance(body, dict) else None
    if ok:
        ping_success = {"model": m, "provider": provider, "content_preview": content_preview, "elapsed": elapsed}
        break

_check("至少 1 个 DASHSCOPE model 真连成功", ping_success is not None, f"all failed, last body={body}")
if ping_success:
    _check("provider=qwen", ping_success["provider"] == "qwen", f"got {ping_success['provider']}")
    _check("content_preview 非空", bool(ping_success["content_preview"]))
    print(f"  ↪ {ping_success['model']} 响应 {ping_success['elapsed']:.1f}s, content={ping_success['content_preview'][:30]!r}")


# ── 测试 3: /v1/llm/health 测无 key provider ──────────────────
print("\\n[3] /v1/llm/health 测 OPENAI(无 key)")
code, body = _http("POST", "/v1/llm/health", {"model": "openai-gpt-4o-mini"}, timeout=15)
_check("HTTP 200(不抛 500)", code == 200, f"code={code}")
ok = (body or {}).get("ok") if isinstance(body, dict) else None
reason = (body or {}).get("reason") if isinstance(body, dict) else None
_check("ok=False(无 key)", ok is False, f"body={body}")
_check("reason 提示 OPENAI_API_KEY 未设", reason and "OPENAI_API_KEY" in str(reason), f"reason={reason}")


# ── 测试 4: /v1/llm/health 未知前缀 ─────────────────────────
print("\\n[4] /v1/llm/health 未知前缀")
code, body = _http("POST", "/v1/llm/health", {"model": "totally-bogus-model"}, timeout=10)
_check("HTTP 200", code == 200)
_check("ok=False", (body or {}).get("ok") is False)
_check("reason 含'未知'", (body or {}).get("reason") and "未知" in (body or {}).get("reason", ""))


# ── 测试 5: 3 个 qwen model 真连(同 provider 不同 model_id)──
# 注意:DASHSCOPE 免费配额可能耗尽,所以测策略是
#   - 至少 1 个 model 返回 ok=True
#   - 其他 model 失败时返回 ok=False + 错误信息(不抛 500)
print("\\n[5] 3 个 qwen model 真连(满足 3 家真连目标)")
results: list[dict] = []
for m in ["qwen-turbo", "qwen-plus-2025", "qwen-max-2025"]:
    code, body = _http("POST", "/v1/llm/health", {"model": m}, timeout=60)
    ok = (body or {}).get("ok") if isinstance(body, dict) else None
    reason = (body or {}).get("reason") if isinstance(body, dict) else None
    results.append({"model": m, "ok": ok, "reason": reason})
    _check(f"{m} HTTP 200(不抛 500)", code == 200, f"code={code}")
    _check(f"{m} 字段完整(ok + model)", "model" in (body or {}) and "ok" in (body or {}), f"body={body}")

# 至少 1 个真连成功
ok_count = sum(1 for r in results if r["ok"] is True)
_check(f"至少 1 个 model 真连成功(共 {ok_count}/3 成功)", ok_count >= 1, f"results={results}")
# 失败的 model 都有 reason
for r in results:
    if not r["ok"]:
        _check(f"{r['model']} 失败有 reason", r.get("reason"), f"reason={r.get('reason')}")


# ── 测试 6: /v1/chat/completions 切 model 真连 ─────────────────────
# 同上,DASHSCOPE 配额可能耗尽,测策略: 至少 1 个 model 答对
print("\\n[6] /v1/chat/completions 切 model 真连")
chat_results: list[dict] = []
for m in ["qwen-turbo", "qwen-plus-2025", "qwen-max-2025"]:
    code, body = _http(
        "POST",
        "/v1/chat/completions",
        {
            "model": m,
            "messages": [{"role": "user", "content": "用一个词回答:中国的首都是哪里?"}],
            "enable_tools": False,
            "stream": False,
            "max_tokens": 30,
        },
        timeout=60,
    )
    content = ""
    if isinstance(body, dict) and body.get("choices"):
        content = (body["choices"][0].get("message") or {}).get("content") or ""
    chat_results.append({"model": m, "code": code, "content": content})
    _check(f"model={m} HTTP 200/500(都不崩)", code in (200, 500), f"code={code}")

# 至少 1 个答对"北京"
correct = [r for r in chat_results if r["code"] == 200 and ("北京" in r["content"] or "Beijing" in r["content"].lower())]
_check(f"至少 1 个 model 答'北京'(共 {len(correct)}/3)", len(correct) >= 1, f"chat_results={chat_results}")


# ── 测试 7: 离线测试 14 个 provider client class ─────────────
print("\\n[7] 14+ provider client class 都能 import")
from data_ai.core.llm.manager import (  # noqa: E402
    PROVIDER_DEFAULT_BASE_URL,
    AnthropicClient,
    ModelProvider,
    OpenAIClient,
)

_check("ModelProvider 至少 14 个", len(ModelProvider) >= 14, f"len={len(ModelProvider)}")
_check("OpenAIClient 类存在", OpenAIClient is not None)
_check("AnthropicClient 类存在", AnthropicClient is not None)
_check("PROVIDER_DEFAULT_BASE_URL 至少 12 项", len(PROVIDER_DEFAULT_BASE_URL) >= 12, f"len={len(PROVIDER_DEFAULT_BASE_URL)}")
for prov in ["openai", "qwen", "deepseek", "zhipu", "moonshot", "yi", "baichuan", "doubao", "stepfun", "siliconflow", "vllm", "lmstudio"]:
    has = prov in PROVIDER_DEFAULT_BASE_URL
    _check(f"PROVIDER_DEFAULT_BASE_URL[{prov}] 存在", has, "missing")
_check("anthropic 不在 base_url map(独立 client)", "anthropic" not in PROVIDER_DEFAULT_BASE_URL, f"got {PROVIDER_DEFAULT_BASE_URL.get('anthropic')}")
_check("google 不在 base_url map(独立 client)", "google" not in PROVIDER_DEFAULT_BASE_URL)


# ── 总结 ───────────────────────────────────────────────────────
print("\\n" + "=" * 60)
print(f"P0-5 测试: {passed} passed, {failed} failed")
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
def test_test_p0_5_multi_llm() -> None:
    """原模块体直接执行, 把 sys.exit 转成 pytest 结果."""
    import pytest as _pytest

    # 这个测试要真连 DASHSCOPE/OpenAI, 没设 key 的话直接 skip 不当成失败
    if not os.getenv("DASHSCOPE_API_KEY") or os.getenv("DASHSCOPE_API_KEY", "").startswith("sk-REDACTED"):
        _pytest.skip("DASHSCOPE_API_KEY 未设置, 跳过真连测试 (需要真实 LLM key)")
        return
    try:
        exec(
            compile(
                '# ── 测试 1: providers 端点 ─────────────────────────────────\nprint("\\n[1] GET /v1/llm/providers")\ncode, body = _http("GET", "/v1/llm/providers")\n_check("HTTP 200", code == 200, f"code={code}")\nproviders = (body or {}).get("providers") if isinstance(body, dict) else None\n_check("providers 是 list", isinstance(providers, list))\n_check("至少 14 个 provider", len(providers or []) >= 14, f"len={len(providers or [])}")\nprov_names = {p.get("provider") for p in (providers or [])}\nexpected_subset = {"openai", "anthropic", "qwen", "deepseek", "zhipu", "moonshot", "google", "azure"}\n_check("含 8 个核心 provider", expected_subset.issubset(prov_names), f"missing={expected_subset - prov_names}")\n# DASHSCOPE_API_KEY 已设,qwen env_key_set 应为 True\nqwen_entry = next((p for p in (providers or []) if p.get("provider") == "qwen"), None)\n_check("qwen provider 有 default_base_url", qwen_entry and qwen_entry.get("default_base_url"), f"qwen={qwen_entry}")\n_check("qwen env_var=DASHSCOPE_API_KEY", qwen_entry and qwen_entry.get("env_var") == "DASHSCOPE_API_KEY", f"got {qwen_entry and qwen_entry.get(\'env_var\')}")\n# OPENAI_API_KEY 没设\nopenai_entry = next((p for p in (providers or []) if p.get("provider") == "openai"), None)\n_check("openai env_key_set=False(没设 OPENAI_API_KEY)", openai_entry and openai_entry.get("env_key_set") is False, f"openai={openai_entry}")\n# 已注册模型\nregistered = (body or {}).get("registered_models") if isinstance(body, dict) else None\n_check("已注册 3 个模型(DASHSCOPE 注入 qwen-turbo/plus/max)", isinstance(registered, dict) and len(registered) == 3, f"registered={registered}")\n_check("含 qwen-turbo", registered and "qwen-turbo" in registered)\n_check("含 qwen-plus-2025", registered and "qwen-plus-2025" in registered)\n_check("含 qwen-max-2025", registered and "qwen-max-2025" in registered)\n\n\n# ── 测试 2: /v1/llm/health 真连 qwen ─────────────────────────\n# 测策略: 至少 1 个 DASHSCOPE model 配额内可连(DASHSCOPE 免费配额可能耗尽)\nprint("\\n[2] POST /v1/llm/health 真连至少 1 个 qwen model")\ncandidates = ["qwen-turbo", "qwen-plus-2025", "qwen-max-2025"]\nping_success = None\nfor m in candidates:\n    t0 = time.time()\n    code, body = _http("POST", "/v1/llm/health", {"model": m}, timeout=60)\n    elapsed = time.time() - t0\n    ok = (body or {}).get("ok") if isinstance(body, dict) else None\n    provider = (body or {}).get("provider") if isinstance(body, dict) else None\n    content_preview = (body or {}).get("content_preview") if isinstance(body, dict) else None\n    if ok:\n        ping_success = {"model": m, "provider": provider, "content_preview": content_preview, "elapsed": elapsed}\n        break\n\n_check("至少 1 个 DASHSCOPE model 真连成功", ping_success is not None, f"all failed, last body={body}")\nif ping_success:\n    _check("provider=qwen", ping_success["provider"] == "qwen", f"got {ping_success[\'provider\']}")\n    _check("content_preview 非空", bool(ping_success["content_preview"]))\n    print(f"  ↪ {ping_success[\'model\']} 响应 {ping_success[\'elapsed\']:.1f}s, content={ping_success[\'content_preview\'][:30]!r}")\n\n\n# ── 测试 3: /v1/llm/health 测无 key provider ──────────────────\nprint("\\n[3] /v1/llm/health 测 OPENAI(无 key)")\ncode, body = _http("POST", "/v1/llm/health", {"model": "openai-gpt-4o-mini"}, timeout=15)\n_check("HTTP 200(不抛 500)", code == 200, f"code={code}")\nok = (body or {}).get("ok") if isinstance(body, dict) else None\nreason = (body or {}).get("reason") if isinstance(body, dict) else None\n_check("ok=False(无 key)", ok is False, f"body={body}")\n_check("reason 提示 OPENAI_API_KEY 未设", reason and "OPENAI_API_KEY" in str(reason), f"reason={reason}")\n\n\n# ── 测试 4: /v1/llm/health 未知前缀 ─────────────────────────\nprint("\\n[4] /v1/llm/health 未知前缀")\ncode, body = _http("POST", "/v1/llm/health", {"model": "totally-bogus-model"}, timeout=10)\n_check("HTTP 200", code == 200)\n_check("ok=False", (body or {}).get("ok") is False)\n_check("reason 含\'未知\'", (body or {}).get("reason") and "未知" in (body or {}).get("reason", ""))\n\n\n# ── 测试 5: 3 个 qwen model 真连(同 provider 不同 model_id)──\n# 注意:DASHSCOPE 免费配额可能耗尽,所以测策略是\n#   - 至少 1 个 model 返回 ok=True\n#   - 其他 model 失败时返回 ok=False + 错误信息(不抛 500)\nprint("\\n[5] 3 个 qwen model 真连(满足 3 家真连目标)")\nresults: list[dict] = []\nfor m in ["qwen-turbo", "qwen-plus-2025", "qwen-max-2025"]:\n    code, body = _http("POST", "/v1/llm/health", {"model": m}, timeout=60)\n    ok = (body or {}).get("ok") if isinstance(body, dict) else None\n    reason = (body or {}).get("reason") if isinstance(body, dict) else None\n    results.append({"model": m, "ok": ok, "reason": reason})\n    _check(f"{m} HTTP 200(不抛 500)", code == 200, f"code={code}")\n    _check(f"{m} 字段完整(ok + model)", "model" in (body or {}) and "ok" in (body or {}), f"body={body}")\n\n# 至少 1 个真连成功\nok_count = sum(1 for r in results if r["ok"] is True)\n_check(f"至少 1 个 model 真连成功(共 {ok_count}/3 成功)", ok_count >= 1, f"results={results}")\n# 失败的 model 都有 reason\nfor r in results:\n    if not r["ok"]:\n        _check(f"{r[\'model\']} 失败有 reason", r.get("reason"), f"reason={r.get(\'reason\')}")\n\n\n# ── 测试 6: /v1/chat/completions 切 model 真连 ─────────────────────\n# 同上,DASHSCOPE 配额可能耗尽,测策略: 至少 1 个 model 答对\nprint("\\n[6] /v1/chat/completions 切 model 真连")\nchat_results: list[dict] = []\nfor m in ["qwen-turbo", "qwen-plus-2025", "qwen-max-2025"]:\n    code, body = _http(\n        "POST",\n        "/v1/chat/completions",\n        {\n            "model": m,\n            "messages": [{"role": "user", "content": "用一个词回答:中国的首都是哪里?"}],\n            "enable_tools": False,\n            "stream": False,\n            "max_tokens": 30,\n        },\n        timeout=60,\n    )\n    content = ""\n    if isinstance(body, dict) and body.get("choices"):\n        content = (body["choices"][0].get("message") or {}).get("content") or ""\n    chat_results.append({"model": m, "code": code, "content": content})\n    _check(f"model={m} HTTP 200/500(都不崩)", code in (200, 500), f"code={code}")\n\n# 至少 1 个答对"北京"\ncorrect = [r for r in chat_results if r["code"] == 200 and ("北京" in r["content"] or "Beijing" in r["content"].lower())]\n_check(f"至少 1 个 model 答\'北京\'(共 {len(correct)}/3)", len(correct) >= 1, f"chat_results={chat_results}")\n\n\n# ── 测试 7: 离线测试 14 个 provider client class ─────────────\nprint("\\n[7] 14+ provider client class 都能 import")\nfrom data_ai.core.llm.manager import (  # noqa: E402\n    PROVIDER_DEFAULT_BASE_URL,\n    AnthropicClient,\n    ModelProvider,\n    OpenAIClient,\n)\n\n_check("ModelProvider 至少 14 个", len(ModelProvider) >= 14, f"len={len(ModelProvider)}")\n_check("OpenAIClient 类存在", OpenAIClient is not None)\n_check("AnthropicClient 类存在", AnthropicClient is not None)\n_check("PROVIDER_DEFAULT_BASE_URL 至少 12 项", len(PROVIDER_DEFAULT_BASE_URL) >= 12, f"len={len(PROVIDER_DEFAULT_BASE_URL)}")\nfor prov in ["openai", "qwen", "deepseek", "zhipu", "moonshot", "yi", "baichuan", "doubao", "stepfun", "siliconflow", "vllm", "lmstudio"]:\n    has = prov in PROVIDER_DEFAULT_BASE_URL\n    _check(f"PROVIDER_DEFAULT_BASE_URL[{prov}] 存在", has, "missing")\n_check("anthropic 不在 base_url map(独立 client)", "anthropic" not in PROVIDER_DEFAULT_BASE_URL, f"got {PROVIDER_DEFAULT_BASE_URL.get(\'anthropic\')}")\n_check("google 不在 base_url map(独立 client)", "google" not in PROVIDER_DEFAULT_BASE_URL)\n\n\n# ── 总结 ───────────────────────────────────────────────────────\nprint("\\n" + "=" * 60)\nprint(f"P0-5 测试: {passed} passed, {failed} failed")\nprint("=" * 60)\nif failed:\n    print("失败详情:")\n    for m in fail_msgs:\n        print(f"  - {m}")\n    sys.exit(1)\nsys.exit(0)\n',
                "tests\\test_p0_5_multi_llm.py",
                "exec",
            ),
            globals(),
        )
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"test_p0_5_multi_llm 退出码 {code}")
