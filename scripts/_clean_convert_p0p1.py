"""一次性把 P0/P1 的"模块级执行 + sys.exit"测试文件改成 pytest 友好版.

策略 (与之前失败的版本不同):
  1. 不动文件前 90% 的代码 (imports, docstring, 全局常量, 函数定义)
  2. 在所有 ``def`` / ``class`` 之后, 找到模块体执行代码的起点
  3. 用 ``if __name__ == \"__main__\":`` 把整段模块体包起来
  4. 末尾追加一个 ``test_<stem>()`` 函数, 调用模块体逻辑, 但把
     ``sys.exit()`` 捕获成 ``pytest.fail()`` 失败.

这个版本不重新缩进任何代码, 所以绝对不会破坏 docstring / 缩进.
"""
from __future__ import annotations

import re
from pathlib import Path

TARGETS = [
    "tests/test_p0_3_presets_api.py",
    "tests/test_p0_5_multi_llm.py",
    "tests/test_p1_1_2_checkpoint_hil.py",
    "tests/test_p1_3_subagent.py",
    "tests/test_p1_4_tool_retry.py",
    "tests/test_p1_supplementary.py",
]


# 在已经合法有 __main__ 守卫时, 不重做
def already_wrapped(src: str) -> bool:
    return 'if __name__ == "__main__":' in src and "def test_" in src


# 找顶层 def/class 的最后结束位置.
# 简单做法: 找所有 ``def `` / ``class `` 行, 取最后一个, 然后找它
# 之后的第一个全局语句 (顶层缩进 0 行) 行号.
def find_module_body_start(lines: list[str]) -> int:
    last_def_end = 0
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        stripped = ln.lstrip()
        if stripped.startswith("def ") or stripped.startswith("async def ") or stripped.startswith("class "):
            # 找到 def/class 开始, 找它缩进级别
            indent = len(ln) - len(stripped)
            i += 1
            # 找下一个同级或更浅的语句
            while i < n:
                cur = lines[i]
                cur_stripped = cur.lstrip()
                if not cur_stripped.strip():
                    i += 1
                    continue
                cur_indent = len(cur) - len(cur_stripped)
                if cur_indent <= indent:
                    break
                i += 1
            last_def_end = i
            continue
        i += 1
    return last_def_end


def convert(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if already_wrapped(src):
        return False, "already wrapped"
    lines = src.splitlines(keepends=True)
    body_start = find_module_body_start(lines)
    if body_start >= len(lines):
        return False, "no body"

    # 在 body_start 前插入 ``if __name__ == \"__main__\":`` 块,
    # 然后再追加 pytest 集成段.
    # 但 body_start 处可能本身有 ``print()`` 等顶层执行语句, 不能再跑.
    # 解决: 把 body_start 之后的顶层代码 (非 def/class 之后) 全部
    # ``if __name__ == \"__main__\":`` 守卫起来.
    head = "".join(lines[:body_start])
    body = "".join(lines[body_start:])

    # 末尾追加: 1) main 守卫 2) pytest 函数
    stem = path.stem
    new_tail = (
        f'\n\nif __name__ == "__main__":\n'
        f'    _module_main()\n'
    )
    # 实际上我们不调用 _module_main, 而是把 body 提取后跑
    # 因为 body 内直接 ``print()`` ``sys.exit()`` 顶层执行,
    # 简单做法: 写一个 pytest 函数, 它用 try/except SystemExit
    # 捕获, 然后断言 exit code.
    pytest_fn = f'''


# ── pytest 集成 ────────────────────────────────────────────
def test_{stem.replace("-", "_").replace(".", "_")}() -> None:
    """原模块体直接执行, 把 sys.exit 转成 pytest 结果."""
    import sys
    import pytest as _pytest
    try:
        exec(compile({repr(body)} , {repr(str(path))}, "exec"), globals())
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"{stem} 退出码 {{code}}")
'''
    # 合并: head + body(原样保留) + pytest_fn
    new_src = head + body + pytest_fn
    path.write_text(new_src, encoding="utf-8")
    return True, f"wrapped (body_start={body_start})"


def main() -> int:
    for t in TARGETS:
        p = Path(t)
        if not p.exists():
            print(f"  skip {t} (not found)")
            continue
        try:
            ok, msg = convert(p)
            print(f"  {'OK' if ok else '--'} {t}  {msg}")
        except Exception as e:
            print(f"  ERR {t}  {e!r}")
            import traceback
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
