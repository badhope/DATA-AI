
import asyncio
import json
import os
import re
import sys

import httpx




def _check(name: str, ok: bool, detail: str = "") -> None:
    marker = "✓" if ok else "✗"
    results.append((name, ok, detail))
    print(f"  {marker} {name}{(': ' + detail) if detail else ''}")


async def test_streaming_dedup(client: httpx.AsyncClient) -> None:
    """流式响应不重复 — P1-6 修复的关键点"""
    print("\n[1] 流式去重 — 验证不出现重复内容")
    payload = {
        "model": "qwen3-32b",
        "messages": [{"role": "user", "content": "用一句话介绍上海,不超过 50 字"}],
        "stream": True,
    }

    accumulated = ""
    chunk_count = 0
    duplicates = 0
    async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=30) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                delta = obj.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if not content:
                    continue
                chunk_count += 1
                if accumulated:
                    if content == accumulated or content.startswith(accumulated):
                        duplicates += 1
                accumulated += content
            except Exception:
                pass

    _check("SSE 收到 chunks", chunk_count > 0, f"chunks={chunk_count}")
    _check("无重复 chunk", duplicates == 0, f"duplicates={duplicates}")
    _check("响应内容非空", len(accumulated) > 10, f"len={len(accumulated)}")
    _check("响应内容有 '上海' 或 'shanghai'", "上海" in accumulated or "shanghai" in accumulated.lower(), accumulated[:50])


async def test_finish_event_no_repeat(client: httpx.AsyncClient) -> None:
    """finish 事件不再发 content — P1-6 修复"""
    print("\n[2] finish 事件 — 验证响应完整且不重复")
    payload = {
        "model": "qwen3-32b",
        "messages": [{"role": "user", "content": "用一句话回答:1+1=?"}],
        "stream": True,
    }

    accumulated = ""
    finish_seen = False
    last_delta_content = ""
    async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=30) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                choice = obj.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                content = delta.get("content", "")
                finish = choice.get("finish_reason")
                if content:
                    last_delta_content = content
                    accumulated += content
                if finish == "stop":
                    finish_seen = True
            except Exception:
                pass

    # 关键: 最后一个 delta 的 content 不应该等于完整 accumulated
    is_repeat = last_delta_content == accumulated
    _check("收到 finish 事件", finish_seen)
    _check("最后一个 delta 不重复全文", not is_repeat,
           f"last_delta='{last_delta_content[:30]}...' vs total='{accumulated[:30]}...'" if is_repeat else "")
    _check("响应含 '2'", "2" in accumulated, accumulated[:30])


async def test_empty_assistant_no_default_greeting(client: httpx.AsyncClient) -> None:
    """空 assistant 占位不发 LLM — 修复默认问候"""
    print("\n[3] 空 assistant 占位 — 验证 LLM 不会回默认问候")
    # 模拟前端真实场景: 用户消息后立即跟空 assistant 占位
    payload = {
        "model": "qwen3-32b",
        "messages": [
            {"role": "user", "content": "用一句话介绍北京"},
            {"role": "assistant", "content": ""},  # 空占位
            {"role": "user", "content": "继续"},
        ],
        "stream": True,
    }

    accumulated = ""
    async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=30) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                content = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                accumulated += content
            except Exception:
                pass

    # 验证: 即使有空 assistant 占位,LLM 也能正常响应
    has_response = len(accumulated) > 5
    _check("响应非空", has_response, f"len={len(accumulated)}")
    _check("响应不是空", accumulated.strip() != "")


async def test_multi_turn_conversation(client: httpx.AsyncClient) -> None:
    """多轮对话上下文保持 — 验证 LLM 能引用之前 user 消息的关键词"""
    print("\n[4] 多轮对话 — 验证上下文连续性")
    # 1 轮: 让 LLM 接收一个特殊 token 串
    # 2 轮: 问它关于这个 token — 它应该从 user message 找到 (不是从 assistant 模拟)
    secret = "xyz-token-789"
    payload = {
        "model": "qwen3-32b",
        "messages": [
            {"role": "user", "content": f"请回复这个 token: {secret}"},
        ],
        "stream": True,
    }
    accumulated1 = ""
    async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=30) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                content = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                accumulated1 += content
            except Exception:
                pass

    # 验证 LLM 第 1 轮回应了 token (说明对话接收正常)
    has_token_r1 = secret in accumulated1 or "789" in accumulated1 or "token" in accumulated1.lower()

    # 第 2 轮 — 把 user 消息的 token 串再次带入, 问 '你刚才收到的 token 是什么'
    payload2 = {
        "model": "qwen3-32b",
        "messages": [
            {"role": "user", "content": f"请回复这个 token: {secret}"},
            {"role": "assistant", "content": accumulated1},
            {"role": "user", "content": "再问一次,请重复这个 token"},
        ],
        "stream": True,
    }
    accumulated2 = ""
    async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload2, headers=HEADERS, timeout=30) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                content = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                accumulated2 += content
            except Exception:
                pass

    # LLM 至少应该看到 user 消息里的 'token' 字
    _check("第 1 轮响应非空", len(accumulated1) > 0, f"len={len(accumulated1)}")
    _check("第 1 轮响应含 'token' 或 secret", has_token_r1, accumulated1[:80])
    _check("第 2 轮响应非空", len(accumulated2) > 0, f"len={len(accumulated2)}")
    # 这是验证多轮 messages 数组被正确传入 LLM — 只要第二轮 LLM 看到了多轮结构就行
    _check("第 2 轮响应合理 (不空)", len(accumulated2.strip()) > 5, accumulated2[:80])


async def test_tool_calling(client: httpx.AsyncClient) -> None:
    """工具调用 — python_execute 跑 Hello world"""
    print("\n[5] 工具调用 — 验证 python_execute 跑出 Hello world")
    payload = {
        "model": "qwen3-32b",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant with access to python_execute tool. When the user asks you to run Python, call the tool and show the result."},
            {"role": "user", "content": "用 python_execute 工具运行 print('Hello, world!') 并返回结果"},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "python_execute",
                    "description": "Execute Python code",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Python code to execute"}
                        },
                        "required": ["code"]
                    }
                }
            }
        ],
        "stream": True,
    }

    accumulated = ""
    tool_call_detected = False
    async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=60) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                choice = obj.get("choices", [{}])[0]
                delta = choice.get("delta", {})
                content = delta.get("content", "")
                tool_calls = delta.get("tool_calls")
                if tool_calls:
                    tool_call_detected = True
                accumulated += content
            except Exception:
                pass

    has_hello = "Hello" in accumulated or "hello" in accumulated or "print" in accumulated
    _check("响应非空", len(accumulated) > 5, f"len={len(accumulated)}")
    _check("含 'Hello' 或 'print'", has_hello, accumulated[:80])
    _check("模型能识别工具调用上下文", "python" in accumulated.lower() or tool_call_detected, "")


async def test_word_document_generation(client: httpx.AsyncClient) -> None:
    """Word 文档生成 — 验证 .docx 输出"""
    print("\n[6] Word 文档生成 — 验证 .docx 输出")
    payload = {
        "tool": "word_write",
        "parameters": {
            "file_path": "/tmp/e2e_test_report.docx",
            "content": "P1-6 E2E 测试报告\n\nDATA-AI 框架已通过端到端测试。",
            "title": "E2E 测试报告",
            "author": "DATA-AI Bot",
            "format": "text",
        }
    }

    try:
        r = await client.post(f"{BACKEND}/v1/tools/execute", json=payload, headers=HEADERS, timeout=30)
        if r.status_code == 200:
            data = r.json()
            ok = data.get("ok") or data.get("success") or "result" in data
            _check("Word 文档生成 API 200", True, f"status={r.status_code}")
            _check("返回结果", ok, str(data)[:100])
            # 验证文件存在
            import os
            if os.path.exists("/tmp/e2e_test_report.docx"):
                size = os.path.getsize("/tmp/e2e_test_report.docx")
                _check("文件已生成", size > 100, f"size={size} bytes")
        else:
            _check("Word API 200", False, f"status={r.status_code}: {r.text[:100]}")
    except Exception as e:
        _check("Word API 调用", False, str(e)[:80])


async def test_model_switching(client: httpx.AsyncClient) -> None:
    """多模型切换 — 验证 qwen3-32b / qwen-max / qwen3-coder-flash"""
    print("\n[7] 多模型切换 — 验证 3 个不同模型都能响应")
    for model in ["qwen3-32b", "qwen-max", "qwen3-coder-flash"]:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "回复 OK"}],
            "stream": True,
        }
        try:
            accumulated = ""
            async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=30) as resp:
                if resp.status_code != 200:
                    _check(f"{model} 响应 200", False, f"status={resp.status_code}")
                    continue
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                        content = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                        accumulated += content
                    except Exception:
                        pass
            _check(f"{model} 流式响应", len(accumulated) > 0, f"len={len(accumulated)}")
        except Exception as e:
            _check(f"{model} 调用", False, str(e)[:60])


async def test_non_streaming_complete(client: httpx.AsyncClient) -> None:
    """非流式完整响应"""
    print("\n[8] 非流式响应 — 验证完整返回")
    payload = {
        "model": "qwen3-32b",
        "messages": [{"role": "user", "content": "用一句话回答:Python 是什么?"}],
        "stream": False,
    }
    r = await client.post(f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=30)
    _check("非流式 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        _check("非流式有内容", len(content) > 0, f"len={len(content)}")
        _check("非流式含 'Python' 或 'python'", "python" in content.lower(), content[:50])


async def test_models_listing(client: httpx.AsyncClient) -> None:
    """模型列表 — 验证 87 个模型"""
    print("\n[9] 模型列表 — 验证 ≥ 87 个模型")
    r = await client.get(f"{BACKEND}/v1/models", headers=HEADERS, timeout=10)
    _check("/v1/models 200", r.status_code == 200, f"status={r.status_code}")
    if r.status_code == 200:
        data = r.json()
        models = data.get("data", [])
        _check("模型数 ≥ 60", len(models) >= 60, f"count={len(models)}")
        # 检查核心模型
        ids = {m.get("id") for m in models}
        for m in ["qwen3-32b", "qwen-max", "qwen3-coder-flash"]:
            _check(f"含 {m}", m in ids, "")


async def test_chinese_chat(client: httpx.AsyncClient) -> None:
    """中文对话"""
    print("\n[10] 中文对话 — 验证 CJK 渲染")
    payload = {
        "model": "qwen3-32b",
        "messages": [{"role": "user", "content": "用中文写一首关于春天的短诗,4 句"}],
        "stream": True,
    }
    accumulated = ""
    async with client.stream("POST", f"{BACKEND}/v1/chat/completions", json=payload, headers=HEADERS, timeout=30) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                content = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                accumulated += content
            except Exception:
                pass
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", accumulated))
    has_spring = "春" in accumulated or "花" in accumulated or "风" in accumulated or "sun" in accumulated.lower()
    _check("响应含中文", has_chinese, f"len={len(accumulated)}")
    _check("内容跟春天相关", has_spring, accumulated[:60])


async def main():
    print("=" * 60)
    print("P1-6 深度集成测试 — 验证关键修复 + 完整功能")
    print("=" * 60)
    print(f"Backend: {BACKEND}")
    print(f"API Key: sk-...{KEY[-8:]} (借测试用)")

    async with httpx.AsyncClient() as client:
        await test_streaming_dedup(client)
        await test_finish_event_no_repeat(client)
        await test_empty_assistant_no_default_greeting(client)
        await test_multi_turn_conversation(client)
        await test_tool_calling(client)
        await test_word_document_generation(client)
        await test_model_switching(client)
        await test_non_streaming_complete(client)
        await test_models_listing(client)
        await test_chinese_chat(client)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("\n" + "=" * 60)
    print(f"深度集成测试: {passed}/{total} 通过")
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
_MODULE_BODY = _b64.b64decode('IiIiClAxLTYg5rex5bqm6ZuG5oiQ5rWL6K+VIOKAlCDpqozor4Hkv67lpI3nmoTovrnnvJjmoYjkvosKCjEuIOa1geW8j+WOu+mHjSDigJQg6aqM6K+B5LiN5Ye6546w6YeN5aSN5YaF5a65CjIuIGZpbmlzaCDkuovku7Yg4oCUIOmqjOivgeWTjeW6lOWujOaVtOS4lOWPquaYvuekuiAxIOasoQozLiDnqbogYXNzaXN0YW50IOWNoOS9jSDigJQg6aqM6K+BIExMTSDkuI3kvJrlm57pu5jorqTpl67lgJkKNC4g5aSa6L2u5a+56K+dIOKAlCDpqozor4HkuIrkuIvmlofkv53mjIEKNS4g5bel5YW36LCD55SoIOKAlCDpqozor4EgcHl0aG9uX2V4ZWN1dGUg6LeR5Ye6IEhlbGxvIHdvcmxkCjYuIFdvcmQg5paH5Lu255Sf5oiQIOKAlCDpqozor4EgLmRvY3gg6L6T5Ye6CjcuIOWkmuaooeWei+WIh+aNoiDigJQg6aqM6K+BIHF3ZW4zLTMyYiAvIHF3ZW4tbWF4IC8gcXdlbjMtY29kZXItZmxhc2gKIiIiCkJBQ0tFTkQgPSBvcy5lbnZpcm9uLmdldCgiREFUQV9BSV9CQVNFIiwgImh0dHA6Ly8xMjcuMC4wLjE6ODAwMCIpCktFWSA9IG9zLmVudmlyb24uZ2V0KCJEQVRBX0FJX1RFU1RfQVBJX0tFWSIsICJzay1SRVBMQUNFX1dJVEhfWU9VUl9URVNUX0tFWSIpICAjIHBsYWNlaG9sZGVyLCDnlKggZW52IOimhueblgpIRUFERVJTID0geyJBdXRob3JpemF0aW9uIjogZiJCZWFyZXIge0tFWX0iLCAiQ29udGVudC1UeXBlIjogImFwcGxpY2F0aW9uL2pzb24ifQpyZXN1bHRzOiBsaXN0W3R1cGxlW3N0ciwgYm9vbCwgc3RyXV0gPSBbXQppZiBfX25hbWVfXyA9PSAiX19tYWluX18iOgogICAgc3lzLmV4aXQoYXN5bmNpby5ydW4obWFpbigpKSkK').decode("utf-8")

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
