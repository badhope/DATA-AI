from __future__ import annotations

# Playwright sync API
from playwright.sync_api import sync_playwright


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


# ── 1. 加载 / Dashboard ──────────────────────


def test_dashboard() -> None:
    print("\n[1] / Dashboard")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(1500)

        title = page.title()
        _check("页面加载, title 非空", bool(title), f"title={title!r}")

        # 侧边栏存在
        sidebar = page.locator("aside, nav").first
        _check("侧边栏存在", sidebar.is_visible())

        # 主内容
        body_text = page.locator("body").inner_text()
        _check("body 文本非空", len(body_text) > 50, f"body len={len(body_text)}")

        browser.close()


# ── 2. /chat 输入 → 发送 → 流式输出 ────────


def test_chat_streaming() -> None:
    print("\n[2] /chat 流式聊天 (模拟用户输入+点击发送)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/chat", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)

        # 找输入框 (textarea)
        textarea = page.locator("textarea").first
        _check("输入框存在", textarea.is_visible(timeout=5000))
        textarea.fill("用一句话介绍一下上海")
        page.wait_for_timeout(300)

        # 找发送按钮
        send_btn = page.locator("button[aria-label*='send' i], button:has-text('Send'), button:has(svg)").last
        # fallback: 用 Enter
        if not send_btn.is_visible(timeout=2000):
            textarea.press("Enter")
        else:
            send_btn.click()

        # 等流式响应 — 找 assistant message bubble
        page.wait_for_timeout(5000)
        body = page.locator("body").inner_text()
        has_response = any(c in body for c in ["上海", "Shanghai", "国际", "都市", "经济", "中国"])
        _check("流式响应到达 + 含上海相关词", has_response, f"body 头 200 字: {body[:200]!r}")

        browser.close()


# ── 3. /agents 列表 + 详情 ────────────────


def test_agents_page() -> None:
    print("\n[3] /agents 列表")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/agents", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Agents 页加载, body>200", len(body) > 200, f"len={len(body)}")
        _check("含 'Agent' 文本", "Agent" in body or "agent" in body, "no 'Agent' text")

        # 列表项
        cards = page.locator("[class*='card'], [role='button'], button, a").all()
        _check("页面有可交互元素 (cards/buttons/links)", len(cards) > 3, f"got {len(cards)}")

        browser.close()


# ── 4. /team 列表 ──────────────────────


def test_team_page() -> None:
    print("\n[4] /team 列表")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/team", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Team 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 5. /tools 列表 ─────────────────────


def test_tools_page() -> None:
    print("\n[5] /tools 列表")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/tools", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Tools 页加载", len(body) > 100, f"len={len(body)}")
        # 应含 tool 名
        has_tool_keyword = any(t in body for t in ["Tool", "file", "search", "python", "shell", "http"])
        _check("含 tool 关键字", has_tool_keyword, f"body 头 200 字: {body[:200]!r}")
        browser.close()


# ── 6. /sandbox ────────────────────────


def test_sandbox_page() -> None:
    print("\n[6] /sandbox")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/sandbox", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Sandbox 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 7. /rag ───────────────────────────


def test_rag_page() -> None:
    print("\n[7] /rag 知识库")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/rag", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("RAG 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 8. /memory ───────────────────────


def test_memory_page() -> None:
    print("\n[8] /memory 记忆")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/memory", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Memory 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 9. /skills ───────────────────────


def test_skills_page() -> None:
    print("\n[9] /skills")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/skills", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Skills 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 10. /office/word ─────────────────


def test_office_word() -> None:
    print("\n[10] /office/word")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/office/word", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Word 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 11. /office/ppt ──────────────────


def test_office_ppt() -> None:
    print("\n[11] /office/ppt")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/office/ppt", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("PPT 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 12. /office/excel ────────────────


def test_office_excel() -> None:
    print("\n[12] /office/excel")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/office/excel", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Excel 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 13. /office/pdf ─────────────────


def test_office_pdf() -> None:
    print("\n[13] /office/pdf")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/office/pdf", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("PDF 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 14. /models ────────────────────


def test_models_page() -> None:
    print("\n[14] /models 模型管理")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/models", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2500)
        body = page.locator("body").inner_text()
        _check("Models 页加载", len(body) > 100, f"len={len(body)}")
        # 应有 qwen 相关模型
        has_qwen = "qwen" in body.lower() or "Qwen" in body
        _check("含 qwen 模型", has_qwen, f"body 头 300 字: {body[:300]!r}")
        browser.close()


# ── 15. /settings ──────────────────


def test_settings_page() -> None:
    print("\n[15] /settings")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/settings", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Settings 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 16. /notifications ─────────────


def test_notifications_page() -> None:
    print("\n[16] /notifications")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/notifications", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        _check("Notifications 页加载", len(body) > 100, f"len={len(body)}")
        browser.close()


# ── 17. 复杂场景: 多轮对话 + 工具调用 ──


def _send_chat(page, text: str) -> None:
    """模拟用户输入 + 发送(用 Ctrl+Enter,前端约定)."""
    ta = page.locator("textarea").first
    ta.fill(text)
    page.wait_for_timeout(200)
    # 先试点 send 按钮;若不可见/不工作,则退到 Ctrl+Enter
    btn = page.locator("button:has(svg)").last
    try:
        if btn.is_visible(timeout=500):
            btn.click()
        else:
            ta.press("Control+Enter")
    except Exception:
        ta.press("Control+Enter")
    page.wait_for_timeout(500)


def test_complex_conversation() -> None:
    print("\n[17] 复杂场景: 多轮对话 + 工具调用")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/chat", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3000)

        # 选一个能用的模型(默认可能是 qwen-turbo = 403)
        # 方式 1: 通过 localStorage 直接预置 chat store
        # zustand persist name 实际是 'data-ai-chat',版本 2
        page.evaluate("""
        () => {
            const state = {
                state: {
                    sessions: {
                        'test-1': {
                            id: 'test-1',
                            title: '测试会话',
                            model: 'qwen3-32b',
                            systemPrompt: '',
                            temperature: 0.7,
                            topP: 1,
                            maxTokens: undefined,
                            enableTools: true,
                            toolNames: [],
                            maxIterations: 5,
                            messages: [],
                            createdAt: Date.now(),
                            updatedAt: Date.now(),
                        }
                    },
                    sessionOrder: ['test-1'],
                    currentSessionId: 'test-1',
                },
                version: 2
            };
            localStorage.setItem('data-ai-chat', JSON.stringify(state));
        }
        """)
        page.reload(wait_until="networkidle")
        page.wait_for_timeout(3000)

        # 方式 2: 退路 - 通过 UI 选(若方式 1 未生效)
        try:
            model_btn = page.locator("[role='combobox']").first
            current_model = model_btn.inner_text() if model_btn.is_visible(timeout=1000) else ""
            if "qwen3-32b" not in current_model and "qwen-turbo" in current_model:
                # Radix UI Select: 用 mousedown 事件(因为 onClick 可能被 portal 拦截)
                model_btn.click()
                page.wait_for_timeout(600)
                opt = page.locator("[role='option']:has-text('qwen3-32b')").first
                if opt.is_visible(timeout=1500):
                    # 用 mouse 点击中心点
                    box = opt.bounding_box()
                    if box:
                        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.wait_for_timeout(800)
            current_model2 = (
                page.locator("[role='combobox']").first.inner_text() if model_btn.is_visible(timeout=500) else ""
            )
            print(f"    [setup] model now: {current_model2!r}")
        except Exception as e:
            print(f"    [setup] model select failed: {e}")

        # 第一轮
        _send_chat(page, "用一句话介绍一下上海")
        page.wait_for_timeout(8000)
        body1 = page.locator("body").inner_text()
        # 期望含 "上海" 相关词
        has_shanghai = "上海" in body1
        _check("第 1 轮响应 (含上海)", has_shanghai, f"body len={len(body1)}, snippet={body1[200:400]!r}")

        # 第二轮
        _send_chat(page, "用 Python 写个 hello world")
        page.wait_for_timeout(10000)
        body2 = page.locator("body").inner_text()
        # 期望含 Hello/Python/tool execution
        has_code = any(kw in body2 for kw in ["print", "```python", "def ", "Hello", "python_execute", "Tool:"])
        _check("第 2 轮响应 (代码生成)", has_code, f"body len={len(body2)}, snippet={body2[200:500]!r}")
        # 期望含 Python 代码
        _check("含 Python 代码", has_code, f"body 头 500 字: {body2[:500]!r}")

        # 第三轮: 追问
        _send_chat(page, "现在加上函数注释,说明作用")
        page.wait_for_timeout(10000)
        body3 = page.locator("body").inner_text()
        _check("第 3 轮响应 (追问)", len(body3) > 1100, f"body len={len(body3)}")

        browser.close()


# ── 18. 侧边栏点击切换 ─────────────


def test_sidebar_navigation() -> None:
    print("\n[18] 侧边栏点击切换各功能页")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)

        # 找侧边栏的所有链接
        links = page.locator("aside a, nav a").all()
        _check("侧边栏有链接", len(links) > 5, f"got {len(links)} links")

        # 打印所有链接的 href
        hrefs = [link.get_attribute("href") for link in links]
        unique_routes = set([h for h in hrefs if h and h.startswith("/")])
        _check("侧边栏含 ≥10 个不同路由", len(unique_routes) >= 10, f"got {len(unique_routes)}: {unique_routes}")

        # 跳到 /chat 通过侧边栏
        chat_link = page.locator("a[href='/chat']").first
        if chat_link.is_visible(timeout=2000):
            chat_link.click()
            page.wait_for_timeout(2000)
            _check("点击 /chat 后 URL 变化", "/chat" in page.url, f"url={page.url}")

        # 跳到 /models
        models_link = page.locator("a[href='/models']").first
        if models_link.is_visible(timeout=2000):
            models_link.click()
            page.wait_for_timeout(2000)
            _check("点击 /models 后 URL 变化", "/models" in page.url, f"url={page.url}")

        browser.close()


# ── 19. 控制台无 JS 错误 ───────────


def test_no_console_errors() -> None:
    print("\n[19] 控制台无 JS 错误")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        for route in ["/", "/chat", "/agents", "/tools", "/rag", "/memory", "/models", "/settings", "/office/word"]:
            page.goto(f"{FRONTEND}{route}", wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(800)

        _check("无 JS 错误 (9 路由)", len(errors) == 0, f"errors: {errors[:5]}")
        browser.close()


# ── 20. /office/word 文件生成 (模拟用户操作) ──


def test_office_word_generate() -> None:
    print("\n[20] /office/word 文件生成 (前端 WordWrite 工具)")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/office/word", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3500)

        # 直接通过后端 API 创建文档,看是否能拿到 docx
        import json as _json

        # WordWritePayload: file_path, content, title, author, format
        # 使用 sandbox 临时目录
        import tempfile
        import urllib.request

        tmp_dir = tempfile.mkdtemp(prefix="e2e_word_")
        file_path = f"{tmp_dir}/test_frontend.docx"
        payload = _json.dumps(
            {
                "file_path": file_path,
                "content": "这是由前端 E2E 测试自动生成的 Word 文档。\n\nDATA-AI 系统: 第 1 段。\n\nDATA-AI 系统: 第 2 段。",
                "title": "E2E 测试文档",
                "format": "text",
            }
        ).encode()
        req = urllib.request.Request(
            f"{BACKEND}/v1/office/word/write",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                result = _json.load(r)
                has_file = (
                    "file" in result
                    or "path" in result
                    or "file_path" in result
                    or "docx_url" in result
                    or "filename" in result
                )
                _check("Word 文档生成 API 成功", has_file, f"result={result}")
        except Exception as e:
            _check("Word 文档生成 API 成功", False, f"err={e}")

        # 验证页面也有相关按钮(用户可视化操作)
        # 按钮文字可能: 生成/写/创建/新建/导出/保存
        write_btn_count = page.locator(
            "button:has-text('生成'), button:has-text('写'), button:has-text('创建'), button:has-text('新建'), button:has-text('导出'), button:has-text('保存')"
        ).count()
        _check("Word 页有生成/写/创建按钮", write_btn_count > 0, f"count={write_btn_count}")
        browser.close()


# ── 21. Models API + 实际生成回答(复杂场景) ──


def test_api_models_and_chat() -> None:
    print("\n[21] 后端 API: /v1/models 60 个 + /v1/chat 真实响应")
    import json
    import urllib.request

    # 1) 拉模型列表
    req = urllib.request.Request(f"{BACKEND}/v1/models")
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.load(r)
        models = d.get("data", d) if isinstance(d, dict) else d
        _check("/v1/models 返回 ≥ 60 模型", len(models) >= 60, f"got {len(models)}")

    # 2) 用 qwen3-32b 真发一次
    payload = {
        "model": "qwen3-32b",
        "messages": [{"role": "user", "content": "用中文写一句问候"}],
        "max_tokens": 30,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{BACKEND}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
            content = d["choices"][0]["message"]["content"]
            _check("qwen3-32b API 调用成功", len(content) > 0, f"content={content!r}")
    except Exception as e:
        _check("qwen3-32b API 调用成功", False, f"err={e}")

    # 3) 流式输出(SSE)
    payload_s = {**payload, "stream": True}
    req = urllib.request.Request(
        f"{BACKEND}/v1/chat/completions",
        data=json.dumps(payload_s).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            chunks = 0
            text_acc = ""
            for line in r:
                line = line.decode().strip()
                if line.startswith("data:") and line != "data: [DONE]":
                    chunks += 1
                    try:
                        d = json.loads(line[5:].strip())
                        delta = d["choices"][0]["delta"].get("content", "")
                        text_acc += delta
                    except Exception:
                        pass
            _check("SSE 流式输出 ≥ 1 chunks", chunks >= 1, f"chunks={chunks}, text_acc={text_acc!r}")
    except Exception as e:
        _check("SSE 流式输出", False, f"err={e}")


# ── 22. /models 页面 + 60 个模型卡片可见 ──


def test_models_page_listing() -> None:
    print("\n[22] /models 页面 + 模型卡片")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        page.goto(f"{FRONTEND}/models", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(3500)
        body = page.locator("body").inner_text()
        # 找到 "0 个模型" / "0 个 provider" / "还没有模型" 表示没加载完
        has_loading = "0 个模型" in body or "还没有模型" in body
        _check("/models 页面已加载真实数据 (非 0 模型)", not has_loading, f"has_loading={has_loading}")
        # 应含 qwen3
        has_qwen3 = "qwen3" in body.lower() or "Qwen" in body
        _check("页面含 qwen3 模型", has_qwen3, f"body 头 500: {body[:500]!r}")
        # 应有 60 个模型相关数字
        # look for "60" or close number
        import re

        nums = re.findall(r"(\d+)\s*个模型", body)
        _check("模型数 ≥ 50", len(nums) > 0 and int(nums[0]) >= 50, f"nums={nums}")
        browser.close()


# ── 总结 ────────────────────────────


# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
import sys as _sys

import pytest as _pytest

_MODULE_BODY = _b64.b64decode(
    "IiIiCkRBVEEtQUkg5rex5bqmIEUyRSDmtYvor5Ug4oCUIOaooeaLn+aZrumAmueUqOaIt+WcqOWJjeerr+WujOaVtOaTjeS9nAoK6KaG55uWOgoxLiDliqDovb0gLyDihpIgZGFzaGJvYXJkCjIuIC9jaGF0IOKGkiDovpPlhaUg4oaSIOWPkemAgSDihpIg5rWB5byP6L6T5Ye6IOKGkiDmlofku7bkuqflh7oKMy4gL2FnZW50cyDihpIg5YiX6KGoIC8g6K+m5oOFCjQuIC90ZWFtIOKGkiDliJfooaggLyDor6bmg4UgLyDlhbHor4bnrZbnlaUKNS4gL3Rvb2xzIOKGkiDliJfooaggLyDmiafooYwKNi4gL3NhbmRib3gg4oaSIOWIl+ihqCAvIOWIm+W7ugo3LiAvcmFnIOKGkiDkuIrkvKAgLyDmo4DntKIKOC4gL21lbW9yeSDihpIg5re75YqgIC8g5pCc57SiCjkuIC9za2lsbHMg4oaSIOWIl+ihqAoxMC4gL29mZmljZS93b3JkIOKGkiDnlJ/miJAgZG9jeAoxMS4gL29mZmljZS9wcHQg4oaSIOeUn+aIkCBwcHR4CjEyLiAvb2ZmaWNlL2V4Y2VsIOKGkiDnlJ/miJAgeGxzeAoxMy4gL29mZmljZS9wZGYg4oaSIOeUn+aIkCBwZGYKMTQuIC9tb2RlbHMg4oaSIOaooeWei+WIl+ihqCArIOWBpeW6twoxNS4gL3NldHRpbmdzIOKGkiDorr7nva4KMTYuIC9ub3RpZmljYXRpb25zIOKGkiDpgJrnn6UKMTcuIOWkjeadguWcuuaZrzog5aSa6L2u5a+56K+dICsg5bel5YW36LCD55SoICsg6ZW/5LiK5LiL5paHICsgc3ViLWFnZW50CiIiIgpCQUNLRU5EID0gImh0dHA6Ly8xMjcuMC4wLjE6ODAwMCIKRlJPTlRFTkQgPSAiaHR0cDovLzEyNy4wLjAuMTo1MTgwIgpwYXNzZWQgPSAwCmZhaWxlZCA9IDAKZmFpbF9tc2dzOiBsaXN0W3N0cl0gPSBbXQp0ZXN0X2Rhc2hib2FyZCgpCnRlc3RfY2hhdF9zdHJlYW1pbmcoKQp0ZXN0X2FnZW50c19wYWdlKCkKdGVzdF90ZWFtX3BhZ2UoKQp0ZXN0X3Rvb2xzX3BhZ2UoKQp0ZXN0X3NhbmRib3hfcGFnZSgpCnRlc3RfcmFnX3BhZ2UoKQp0ZXN0X21lbW9yeV9wYWdlKCkKdGVzdF9za2lsbHNfcGFnZSgpCnRlc3Rfb2ZmaWNlX3dvcmQoKQp0ZXN0X29mZmljZV9wcHQoKQp0ZXN0X29mZmljZV9leGNlbCgpCnRlc3Rfb2ZmaWNlX3BkZigpCnRlc3RfbW9kZWxzX3BhZ2UoKQp0ZXN0X3NldHRpbmdzX3BhZ2UoKQp0ZXN0X25vdGlmaWNhdGlvbnNfcGFnZSgpCnRlc3RfY29tcGxleF9jb252ZXJzYXRpb24oKQp0ZXN0X3NpZGViYXJfbmF2aWdhdGlvbigpCnRlc3Rfbm9fY29uc29sZV9lcnJvcnMoKQp0ZXN0X29mZmljZV93b3JkX2dlbmVyYXRlKCkKdGVzdF9hcGlfbW9kZWxzX2FuZF9jaGF0KCkKdGVzdF9tb2RlbHNfcGFnZV9saXN0aW5nKCkKcHJpbnQoIlxuIiArICI9IiAqIDYwKQpwcmludChmIkUyRSDliY3nq6/mtYvor5U6IHtwYXNzZWR9IHBhc3NlZCwge2ZhaWxlZH0gZmFpbGVkIikKcHJpbnQoIj0iICogNjApCmlmIGZhaWxlZDoKICAgIHByaW50KCLlpLHotKXor6bmg4U6IikKICAgIGZvciBtIGluIGZhaWxfbXNnczoKICAgICAgICBwcmludChmIiAgLSB7bX0iKQogICAgc3lzLmV4aXQoMSkKc3lzLmV4aXQoMCkK"
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
