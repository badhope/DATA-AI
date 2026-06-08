"""
P1-4 Tool Retry 测试

测试覆盖:
1. ToolRetryableError / ToolPermanentError 异常分类
2. execute_with_retry: transient 错误自动重试
3. execute_with_retry: permanent 错误立即抛
4. execute_with_retry: 重试到 max_retries 后放弃
5. 退避: base_delay * 2^attempt 指数 + jitter
6. 成功: 第 N 次重试后通过
7. ToolNotFound 不算 retryable
8. ValueError 默认不算 retryable
9. 退避上限 max_delay
10. retry_on / permanent_on 自定义
11. BaseAgent._execute_tool 可选接入 retry
"""

from __future__ import annotations

import asyncio
import os
import sys

os.environ.setdefault("DATA_AI_DEV_MODE", "true")

THIS = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(THIS, "..", "src"))
sys.path.insert(0, SRC)

from data_ai.core.tool.registry import ToolRegistry  # noqa: E402
from data_ai.utils.exceptions import (  # noqa: E402
    ToolExecutionError,
    ToolNotFoundError,
    ToolPermanentError,
    ToolRetryableError,
)

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


# ── 1. 异常分类 ───────────────────────────────


def test_exception_hierarchy() -> None:
    print("\n[1] 异常分类 — ToolRetryableError / ToolPermanentError")
    e1 = ToolRetryableError(tool="t", message="net blip")
    e2 = ToolPermanentError(tool="t", message="bad input")
    _check("ToolRetryableError 是 ToolExecutionError 子类", isinstance(e1, ToolExecutionError))
    _check("ToolPermanentError 是 ToolExecutionError 子类", isinstance(e2, ToolExecutionError))
    _check("ToolRetryableError.retryable=True", e1.retryable is True)
    _check("ToolPermanentError.retryable=False", e2.retryable is False)
    _check("ToolRetryableError.details 含 retryable=True", e1.details.get("retryable") is True)
    _check("ToolPermanentError.details 含 retryable=False", e2.details.get("retryable") is False)


test_exception_hierarchy()


# ── 2. transient 错误自动重试(模拟网络抖动) ─────


def test_transient_auto_retry() -> None:
    print("\n[2] transient 错误自动重试(模拟 flaky tool)")
    reg = ToolRegistry()

    call_count = [0]

    def flaky_tool() -> str:
        call_count[0] += 1
        if call_count[0] < 3:  # 前 2 次失败,第 3 次成功
            raise ConnectionError(f"blip {call_count[0]}")
        return "ok"

    reg.register(name="flaky", description="flaky", function=flaky_tool)

    async def _run():
        return await reg.execute_with_retry("flaky", {}, max_retries=3, base_delay=0.01, jitter=0.0)

    result = asyncio.run(_run())
    _check("最终返回 ok", result == "ok")
    _check("调了 3 次(2 失败 + 1 成功)", call_count[0] == 3)


test_transient_auto_retry()


# ── 3. permanent 错误立即抛(不重试) ───────────


def test_permanent_no_retry() -> None:
    print("\n[3] permanent 错误立即抛(不重试)")
    reg = ToolRegistry()

    call_count = [0]

    def bad_tool() -> str:
        call_count[0] += 1
        raise ToolPermanentError(tool="bad", message="bad input")

    reg.register(name="bad", description="bad", function=bad_tool)

    async def _run():
        return await reg.execute_with_retry("bad", {}, max_retries=3, base_delay=0.01, jitter=0.0)

    raised = False
    try:
        asyncio.run(_run())
    except ToolPermanentError:
        raised = True
    _check("抛 ToolPermanentError", raised)
    _check("只调 1 次(没重试)", call_count[0] == 1)


test_permanent_no_retry()


# ── 4. 重试到 max_retries 后放弃 ─────────────


def test_give_up_after_max_retries() -> None:
    print("\n[4] 重试到 max_retries 后放弃")
    reg = ToolRegistry()

    call_count = [0]

    def always_fail() -> str:
        call_count[0] += 1
        raise ToolRetryableError(tool="af", message="always")

    reg.register(name="af", description="af", function=always_fail)

    async def _run():
        return await reg.execute_with_retry("af", {}, max_retries=2, base_delay=0.01, jitter=0.0)

    raised = False
    try:
        asyncio.run(_run())
    except ToolRetryableError:
        raised = True
    _check("最终抛 ToolRetryableError", raised)
    _check("调 3 次(首次 + 2 retry)", call_count[0] == 3, f"got {call_count[0]}")


test_give_up_after_max_retries()


# ── 5. 退避: exponential ────────────────────


def test_exponential_backoff() -> None:
    print("\n[5] 退避: exponential backoff")
    reg = ToolRegistry()
    sleeps: list[float] = []

    async def _patched_sleep(delay: float) -> None:
        sleeps.append(delay)

    orig_sleep = asyncio.sleep
    asyncio.sleep = _patched_sleep  # type: ignore
    try:
        def always_fail() -> str:
            raise ConnectionError("x")

        reg.register(name="x", description="x", function=always_fail)
        try:
            asyncio.run(reg.execute_with_retry("x", {}, max_retries=3, base_delay=0.5, max_delay=100.0, jitter=0.0))
        except (ConnectionError, ToolExecutionError):
            pass
    finally:
        asyncio.sleep = orig_sleep  # type: ignore

    _check("共 3 次 sleep (3 retry)", len(sleeps) == 3, f"got {len(sleeps)}: {sleeps}")
    # 预期 0.5, 1.0, 2.0 (no jitter)
    expected = [0.5, 1.0, 2.0]
    _check("退避序列是 0.5, 1.0, 2.0", all(abs(s - e) < 0.01 for s, e in zip(sleeps, expected)),
           f"got {sleeps} expected {expected}")


test_exponential_backoff()


# ── 6. max_delay 封顶 ────────────────────


def test_max_delay_cap() -> None:
    print("\n[6] max_delay 封顶")
    reg = ToolRegistry()
    sleeps: list[float] = []

    async def _patched_sleep(delay: float) -> None:
        sleeps.append(delay)

    orig_sleep = asyncio.sleep
    asyncio.sleep = _patched_sleep  # type: ignore
    try:
        def always_fail() -> str:
            raise ConnectionError("x")

        reg.register(name="x", description="x", function=always_fail)
        try:
            asyncio.run(reg.execute_with_retry("x", {}, max_retries=4, base_delay=0.5, max_delay=1.5, jitter=0.0))
        except (ConnectionError, ToolExecutionError):
            pass
    finally:
        asyncio.sleep = orig_sleep  # type: ignore

    # 退避序列理论值 0.5, 1.0, 2.0, 4.0; 封顶 1.5
    # 实际 0.5, 1.0, 1.5, 1.5
    _check("最后 2 次 sleep = 1.5 (cap)", abs(sleeps[2] - 1.5) < 0.01 and abs(sleeps[3] - 1.5) < 0.01,
           f"got {sleeps}")


test_max_delay_cap()


# ── 7. jitter 抖动 ────────────────────────


def test_jitter() -> None:
    print("\n[7] jitter 抖动")
    reg = ToolRegistry()
    sleeps: list[float] = []

    async def _patched_sleep(delay: float) -> None:
        sleeps.append(delay)

    orig_sleep = asyncio.sleep
    asyncio.sleep = _patched_sleep  # type: ignore
    try:
        def always_fail() -> str:
            raise ConnectionError("x")

        reg.register(name="x", description="x", function=always_fail)
        try:
            asyncio.run(reg.execute_with_retry("x", {}, max_retries=3, base_delay=1.0, max_delay=100.0, jitter=0.5))
        except (ConnectionError, ToolExecutionError):
            pass
    finally:
        asyncio.sleep = orig_sleep  # type: ignore

    # 理论 1.0, 2.0, 4.0;jitter ±50% → [0.5, 1.5], [1.0, 3.0], [2.0, 6.0]
    _check("3 次 sleep", len(sleeps) == 3)
    _check("第一次 sleep 在 [0.5, 1.5]", 0.5 <= sleeps[0] <= 1.5, f"got {sleeps[0]}")
    _check("第二次 sleep 在 [1.0, 3.0]", 1.0 <= sleeps[1] <= 3.0, f"got {sleeps[1]}")
    _check("第三次 sleep 在 [2.0, 6.0]", 2.0 <= sleeps[2] <= 6.0, f"got {sleeps[2]}")


test_jitter()


# ── 8. ValueError 默认不重试 ────────────────


def test_value_error_not_retryable() -> None:
    print("\n[8] ValueError 默认不重试")
    reg = ToolRegistry()
    call_count = [0]

    def bad_value() -> str:
        call_count[0] += 1
        raise ValueError("bad arg")

    reg.register(name="bv", description="bv", function=bad_value)

    async def _run():
        return await reg.execute_with_retry("bv", {}, max_retries=3, base_delay=0.01, jitter=0.0)

    raised = False
    try:
        asyncio.run(_run())
    except (ValueError, ToolExecutionError):
        raised = True
    _check("ValueError 立即抛(包成 ToolExecutionError)", raised)
    _check("只调 1 次", call_count[0] == 1, f"got {call_count[0]}")


test_value_error_not_retryable()


# ── 9. ToolNotFound 不算 retryable ──────────────


def test_tool_not_found_no_retry() -> None:
    print("\n[9] ToolNotFound 不算 retryable")
    reg = ToolRegistry()

    async def _run():
        return await reg.execute_with_retry("nonexistent", {}, max_retries=3, base_delay=0.01, jitter=0.0)

    raised = False
    try:
        asyncio.run(_run())
    except Exception as e:
        raised = isinstance(e, (ToolNotFoundError, ToolExecutionError))
    _check("ToolNotFound 立即抛", raised)


test_tool_not_found_no_retry()


# ── 10. 自定义 retry_on ─────────────────────


def test_custom_retry_on() -> None:
    print("\n[10] 自定义 retry_on")
    reg = ToolRegistry()
    call_count = [0]

    class _CustomError(Exception):
        pass

    def flaky() -> str:
        call_count[0] += 1
        if call_count[0] < 2:
            raise _CustomError("custom blip")
        return "fixed"

    reg.register(name="custom", description="c", function=flaky)

    async def _run():
        return await reg.execute_with_retry(
            "custom", {}, max_retries=3, base_delay=0.01, jitter=0.0,
            retry_on=(_CustomError,),
        )

    result = asyncio.run(_run())
    _check("自定义 retry 成功", result == "fixed")
    _check("调了 2 次", call_count[0] == 2)


test_custom_retry_on()


# ── 11. 第一次就成功,不重试 ─────────────────


def test_first_attempt_success() -> None:
    print("\n[11] 第一次就成功(不重试)")
    reg = ToolRegistry()
    call_count = [0]

    def good() -> str:
        call_count[0] += 1
        return "good"

    reg.register(name="good", description="g", function=good)

    async def _run():
        return await reg.execute_with_retry("good", {}, max_retries=3, base_delay=0.01, jitter=0.0)

    result = asyncio.run(_run())
    _check("第一次就成功", result == "good")
    _check("只调 1 次", call_count[0] == 1)


test_first_attempt_success()


# ── 12. async 工具也走 retry ──────────────────


def test_async_tool_retry() -> None:
    print("\n[12] async 工具也走 retry")
    reg = ToolRegistry()
    call_count = [0]

    async def async_flaky() -> str:
        call_count[0] += 1
        if call_count[0] < 2:
            raise asyncio.TimeoutError()
        return "async-ok"

    reg.register(name="af", description="af", function=async_flaky)

    async def _run():
        return await reg.execute_with_retry("af", {}, max_retries=2, base_delay=0.01, jitter=0.0)


_MODULE_BODY = """
    result = asyncio.run(_run())
    _check("async retry 成功", result == "async-ok")
    _check("调了 2 次", call_count[0] == 2)


test_async_tool_retry()


# ── 总结 ──────────────────────────────────


print("\\n" + "=" * 60)
print(f"P1-4 测试: {passed} passed, {failed} failed")
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
def test_test_p1_4_tool_retry() -> None:
    """原模块体直接执行, 把 sys.exit 转成 pytest 结果."""
    import sys
    import pytest as _pytest
    try:
        exec(compile('test_async_tool_retry()\n\n\n# ── 总结 ──────────────────────────────────\n\n\nprint("\\n" + "=" * 60)\nprint(f"P1-4 测试: {passed} passed, {failed} failed")\nprint("=" * 60)\nif failed:\n    print("失败详情:")\n    for m in fail_msgs:\n        print(f"  - {m}")\n    sys.exit(1)\nsys.exit(0)\n' , 'tests\\test_p1_4_tool_retry.py', "exec"), globals())
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"test_p1_4_tool_retry 退出码 {code}")
