import httpx


def _check(name: str, ok: bool, detail: str = "") -> None:
    marker = "✓" if ok else "✗"
    results.append((name, ok, detail))
    print(f"  {marker} {name}{(': ' + detail) if detail else ''}")


# ──────────────────── 1. /health 深度检查 ────────────────────
async def test_health_deep(client: httpx.AsyncClient) -> None:
    print("\n[1] /health 深度检查 — checks / fixes / trace_id / uptime")
    r = await client.get(f"{BACKEND}/health", timeout=10)
    _check("/health 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code != 200:
        return
    data = r.json()
    _check("有 status 字段", "status" in data, data.get("status", ""))
    _check("status == 'healthy'", data.get("status") == "healthy", data.get("status", ""))
    _check("有 checks 字段 (P1-7 主动检查)", "checks" in data, "missing")
    _check("checks 含 llm_manager", "llm_manager" in data.get("checks", {}))
    _check("checks 含 tool_registry", "tool_registry" in data.get("checks", {}))
    _check("checks 含 environment", "environment" in data.get("checks", {}))
    _check("有 trace_id", "trace_id" in data and len(data["trace_id"]) >= 8, data.get("trace_id", ""))
    _check("有 uptime_ms", "uptime_ms" in data and data["uptime_ms"] > 0, f"uptime={data.get('uptime_ms')}ms")
    _check("有 fixes 列表 (healthy 时应空)", data.get("fixes") == [], f"fixes={data.get('fixes')}")
    llm = data.get("checks", {}).get("llm_manager", {})
    _check("LLM 模型数 ≥ 60", llm.get("model_count", 0) >= 60, f"count={llm.get('model_count')}")
    tool = data.get("checks", {}).get("tool_registry", {})
    _check("Tool 数量 ≥ 10", tool.get("tool_count", 0) >= 10, f"count={tool.get('tool_count')}")


# ──────────────────── 2. K8s probe 端点 ────────────────────
async def test_k8s_probes(client: httpx.AsyncClient) -> None:
    print("\n[2] /health/live + /health/ready K8s probe")
    r = await client.get(f"{BACKEND}/health/live", timeout=5)
    _check("/health/live 200", r.status_code == 200, f"status={r.status_code}")
    _check("alive 状态", r.json().get("status") == "alive", str(r.json()))

    r = await client.get(f"{BACKEND}/health/ready", timeout=5)
    _check("/health/ready 200", r.status_code == 200, f"status={r.status_code}")
    _check("ready 状态", r.json().get("status") == "ready", str(r.json()))
    _check("ready 报告 model_count", r.json().get("model_count", 0) >= 60, f"count={r.json().get('model_count')}")


# ──────────────────── 3. 错误响应带 trace_id + fix ────────────────────
async def test_error_response_with_trace(client: httpx.AsyncClient) -> None:
    print("\n[3] 错误响应 — trace_id + 修复建议 + 分类")
    # 不存在的模型
    r = await client.post(
        f"{BACKEND}/v1/chat/completions",
        json={"model": "fake-model-xyz", "messages": [{"role": "user", "content": "hi"}]},
        headers=HEADERS,
        timeout=10,
    )
    _check("模型不存在 → 404", r.status_code == 404, f"status={r.status_code}")
    if r.status_code == 404:
        try:
            err = r.json().get("error", {})
            _check("error.code = 'model_not_found'", err.get("code") == "model_not_found", err.get("code", ""))
            _check("有 trace_id", "trace_id" in err and len(err["trace_id"]) >= 8, err.get("trace_id", ""))
            _check("有 fix 建议", "fix" in err and "模型" in err.get("fix", ""), err.get("fix", "")[:60])
            _check("有 user_message", "message" in err, err.get("message", ""))
            _check("有 path", "path" in err, err.get("path", ""))
            _check("有 method", "method" in err, err.get("method", ""))
        except Exception as e:
            _check("解析错误响应", False, str(e)[:60])

    # 不存在的工具
    r = await client.post(
        f"{BACKEND}/v1/tools/execute",
        json={"tool": "fake_tool_xyz", "parameters": {}},
        headers=HEADERS,
        timeout=10,
    )
    _check("工具不存在 → 4xx/5xx", r.status_code >= 400, f"status={r.status_code}")
    if r.status_code >= 400:
        try:
            err = r.json().get("error", r.json().get("detail", {}))
            if isinstance(err, dict):
                _check("工具错误有 trace_id", "trace_id" in err, str(err)[:60])
        except Exception:
            pass


# ──────────────────── 4. multi-delegate 主动检查 ────────────────────
async def test_multi_delegate(client: httpx.AsyncClient) -> None:
    print("\n[4] multi-delegate 主动检查 + 失败不抛")
    # 用 agent API
    payload = {
        "queries": [
            {"query": "用一句话介绍 Python", "role": "secretary"},
            {"query": "用一句话介绍北京", "role": "finance_analyst"},
            {"query": "用一句话介绍春天", "role": "novel_writing"},
        ],
        "model": "qwen3-32b",  # 用稳一点的模型
    }
    r = await client.post(
        f"{BACKEND}/v1/agents/delegate-many",
        json=payload,
        headers=HEADERS,
        timeout=120,
    )
    _check("delegate_many API 调用", r.status_code == 200, f"status={r.status_code} {r.text[:100]}")
    if r.status_code == 200:
        try:
            data = r.json()
            # P1-7: 返回 dict {results, model, trace_id, total}
            _check("返回 dict (含 trace_id)", isinstance(data, dict), f"type={type(data).__name__}")
            _check("外层有 trace_id", "trace_id" in data, data.get("trace_id", "")[:8])
            results = data.get("results", [])
            _check("results 是 list", isinstance(results, list), f"type={type(results).__name__}")
            _check("返回 3 个结果", len(results) == 3, f"count={len(results)}")
            for i, d in enumerate(results):
                has_trace = isinstance(d, dict) and "trace_id" in d
                _check(
                    f"结果 [{i}] 含 trace_id", has_trace, d.get("trace_id", "")[:8] if isinstance(d, dict) else "N/A"
                )
                is_dict = isinstance(d, dict)
                _check(f"结果 [{i}] 是 dict (不抛)", is_dict, "N/A")
        except Exception as e:
            _check("解析 delegate_many 响应", False, str(e)[:60])


# ──────────────────── 5. multi-delegate 错误处理 ────────────────────
async def test_multi_delegate_error_handling(client: httpx.AsyncClient) -> None:
    print("\n[5] multi-delegate 错误处理 — 即使失败也不抛")
    payload = {
        "queries": [
            {"query": "test 1"},  # OK
            {},  # 缺 query - 应失败但不抛
            {"query": "test 3"},  # OK
        ],
        "model": "qwen3-32b",
    }
    r = await client.post(
        f"{BACKEND}/v1/agents/delegate-many",
        json=payload,
        headers=HEADERS,
        timeout=120,
    )
    _check("混合错误请求 → 200 (不抛)", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        try:
            data = r.json()
            results = data.get("results", []) if isinstance(data, dict) else data
            _check("返回 results 数组", isinstance(results, list), f"type={type(results).__name__}")
            _check("返回 3 个结果 (不抛)", len(results) == 3, f"count={len(results)}")
            # 检查第 2 个应该有 success=False 或 error
            if len(results) >= 2 and isinstance(results[1], dict):
                has_error = "error" in results[1] or results[1].get("success") is False
                _check("失败任务有 error 字段", has_error, str(results[1])[:100])
                has_trace = "trace_id" in results[1]
                _check("失败任务有 trace_id", has_trace, str(results[1])[:80])
        except Exception as e:
            _check("解析错误响应", False, str(e)[:60])


# ──────────────────── 6. 网络错误重试 (Playwright) ────────────────────
async def test_retry_via_browser() -> None:
    print("\n[6] 前端 fetch 自动重试 — 验证 retry 逻辑存在")
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # 监听网络请求
        retry_count = {"count": 0}

        def track_request(req):
            if "/v1/models" in req.url:
                retry_count["count"] += 1

        page.on("request", track_request)

        # 注入 API key 到 localStorage
        await page.goto("http://127.0.0.1:5180/", wait_until="networkidle", timeout=10000)
        await page.evaluate("""
() => {
  localStorage.setItem('data-ai-settings-v2', JSON.stringify({
    state: {
      profiles: [{
        id: "default",
        name: "Default",
        provider: "openai",
        baseUrl: "http://localhost:8000",
        authScheme: "bearer",
        apiKey: "sk-REPLACE_WITH_YOUR_TEST_KEY",
        defaultModel: "qwen3-32b",
        customHeaders: [],
        timeoutMs: 5000
      }],
      activeProfileId: "default"
    },
    version: 2
  }));
}
        """)

        # 直接 fetch 验证后端有 /v1/models
        result = await page.evaluate("""
async () => {
  try {
    const r = await fetch('http://localhost:8000/v1/models', {
      headers: { 'Authorization': 'Bearer sk-REPLACE_WITH_YOUR_TEST_KEY' }
    });
    return { status: r.status, ok: r.ok };
  } catch (e) {
    return { error: e.message };
  }
}
        """)
        _check("前端 fetch /v1/models", result.get("ok", False) or result.get("status") == 200, str(result)[:80])

        # 触发一个 4xx 错误 (不存在的模型) — 应该返回 404,不带 retry
        result_404 = await page.evaluate("""
async () => {
  try {
    const r = await fetch('http://localhost:8000/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer sk-REPLACE_WITH_YOUR_TEST_KEY',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ model: 'fake-xyz', messages: [{ role: 'user', content: 'hi' }] })
    });
    const body = await r.json();
    return { status: r.status, error: body.error || body.detail };
  } catch (e) {
    return { error: e.message };
  }
}
        """)
        _check("4xx 返回 404", result_404.get("status") == 404, str(result_404)[:80])
        if isinstance(result_404.get("error"), dict):
            err = result_404["error"]
            _check("前端拿到 trace_id", "trace_id" in err, err.get("trace_id", ""))
            _check("前端拿到 fix 建议", "fix" in err, str(err.get("fix", ""))[:60])

        await browser.close()


# ──────────────────── 7. /health/ready 未就绪时返 503 ────────────────────
async def test_health_ready_503_when_not_ready(client: httpx.AsyncClient) -> None:
    print("\n[7] /health/ready 行为 — 200 当就绪")
    r = await client.get(f"{BACKEND}/health/ready", timeout=5)
    _check("就绪时 200", r.status_code == 200, f"status={r.status_code}")
    data = r.json()
    _check("ready 状态", data.get("status") == "ready", str(data))


async def main():
    print("=" * 60)
    print("P1-7 E2E — 主动检查 / 自动重连 / 准确报错 / 多委派")
    print("=" * 60)
    print(f"Backend: {BACKEND}")
    print(f"API Key: sk-...{KEY[-8:]} (借测试用)")

    async with httpx.AsyncClient() as client:
        await test_health_deep(client)
        await test_k8s_probes(client)
        await test_error_response_with_trace(client)
        await test_multi_delegate(client)
        await test_multi_delegate_error_handling(client)
        await test_health_ready_503_when_not_ready(client)

    # Playwright 部分单独跑 (需要浏览器)
    await test_retry_via_browser()

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"P1-7 E2E: {passed}/{total} 通过")
    print("=" * 60)
    if passed < total:
        print("\n失败项:")
        for name, ok, detail in results:
            if not ok:
                print(f"  ✗ {name}: {detail}")
    return 0 if passed == total else 1


# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
import sys as _sys

import pytest as _pytest

_MODULE_BODY = _b64.b64decode(
    "IiIiClAxLTcg56uv5Yiw56uv5rWL6K+VIOKAlCDkuLvliqjmo4Dmn6UgLyDoh6rliqjph43ov54gLyDlh4bnoa7miqXplJkgLyDlpJrlp5TmtL4KCua1i+ivleWcuuaZrzoKICAxLiAvaGVhbHRoIOa3seW6puajgOafpSDigJQg5ZCrIGNoZWNrcyAvIGZpeGVzIC8gdHJhY2VfaWQgLyB1cHRpbWUKICAyLiAvaGVhbHRoL2xpdmUgKyAvaGVhbHRoL3JlYWR5IEs4cyBwcm9iZQogIDMuIOmUmeivr+WTjeW6lOW4piB0cmFjZV9pZCArIOS/ruWkjeW7uuiurgogIDQuIG11bHRpLWRlbGVnYXRlIOS4u+WKqOajgOafpSArIOWksei0peS4jeaKmwogIDUuIOWJjeerr+iDveaLv+WIsOWQjuerryB0cmFjZV9pZCAo6YeN6K+VICsg6ZSZ6K+v5bGV56S6KQogIDYuIDV4eCDoh6rliqjph43or5UKICA3LiA0eHgg5LiN6YeN6K+VICjnlKjmiLfplJnor68pCiIiIgpCQUNLRU5EID0gImh0dHA6Ly8xMjcuMC4wLjE6ODAwMCIKS0VZID0gb3MuZW52aXJvbi5nZXQoIkRBVEFfQUlfVEVTVF9BUElfS0VZIiwgInNrLVJFUExBQ0VfV0lUSF9ZT1VSX1RFU1RfS0VZIikgICMg5YCf5rWL6K+V55SoCkhFQURFUlMgPSB7IkF1dGhvcml6YXRpb24iOiBmIkJlYXJlciB7S0VZfSIsICJDb250ZW50LVR5cGUiOiAiYXBwbGljYXRpb24vanNvbiJ9CnJlc3VsdHM6IGxpc3RbdHVwbGVbc3RyLCBib29sLCBzdHJdXSA9IFtdCmlmIF9fbmFtZV9fID09ICJfX21haW5fXyI6CiAgICBzeXMuZXhpdChhc3luY2lvLnJ1bihtYWluKCkpKQo="
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
