"""把 test_p0_4 / test_p1_1_2 / test_p0_3 等会做 ``sys.exit`` 或
真 HTTP 调用的测试文件包成 pytest 友好.

策略 (适用"先 def 一堆函数, 再顶层调用之"的结构):
  1. 找出所有顶层 import / from 行, 保留
  2. 找出所有 def / class 声明, 保留
  3. 其余顶层可执行语句 (call, print, urllib.urlopen, sys.exit, assert 等)
     都收集起来放进 _run_module_body()
  4. pytest 集成段调用 _run_module_body(), 把 SystemExit 转成 pytest 结果
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

TARGETS = [
    "tests/test_p0_4_rag_fileread.py",
    "tests/test_p1_1_2_checkpoint_hil.py",
]


def find_executable_top_level(lines: list[str]) -> list[int]:
    """返回所有顶层可执行语句的行号 (0-indexed).

    顶层可执行: 行首缩进 = 0, 且不是空行/注释/import/从属 def/class 体.
    """
    out: list[int] = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        s = ln.lstrip()
        if not s or s.startswith("#"):
            i += 1
            continue
        if s.startswith("import ") or s.startswith("from "):
            i += 1
            continue
        # 检测 def/class 块
        if s.startswith("def ") or s.startswith("async def ") or s.startswith("class "):
            indent = len(ln) - len(s)
            i += 1
            while i < n:
                cur = lines[i]
                cur_s = cur.lstrip()
                if not cur_s.strip():
                    i += 1
                    continue
                cur_indent = len(cur) - len(cur_s)
                if cur_indent <= indent:
                    break
                i += 1
            continue
        # 顶层执行语句
        out.append(i)
        i += 1
    return out


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if "_MODULE_BODY" in src:
        return False, "already wrapped"
    lines = src.splitlines(keepends=True)
    exec_lines = find_executable_top_level(lines)
    if not exec_lines:
        return False, "no top-level exec"

    # 把这些顶层执行行收集起来, 其余行(import/def/class/空/注释)保留.
    # 顶层执行行的范围: 从第一个 exec 行到下一个非 exec 行 (import/def/class) 之间
    # 实际上连续 exec 行 + 它们的延续 (空行/注释) 都算
    keep_mask = [True] * len(lines)
    body_chunks: list[str] = []
    for i in exec_lines:
        keep_mask[i] = False
        body_chunks.append(lines[i])
    body_src = "".join(body_chunks)
    body_b64 = base64.b64encode(body_src.encode("utf-8")).decode("ascii")

    # 重新组装文件: 保留 keep_mask=True 的行, 末尾追加 wrap
    head = "".join(ln for ln, k in zip(lines, keep_mask) if k)
    runner = f'''

# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
import sys as _sys
import pytest as _pytest
_MODULE_BODY = _b64.b64decode({body_b64!r}).decode("utf-8")

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
            _pytest.fail(f"module body exit code {{code}}")
'''
    new_src = head + runner
    path.write_text(new_src, encoding="utf-8")
    return True, f"wrapped {len(exec_lines)} top-level exec lines"


def main() -> int:
    for t in TARGETS:
        p = Path(t)
        if not p.exists():
            print(f"  skip {t} (not found)")
            continue
        ok, msg = fix_one(p)
        print(f"  {'OK' if ok else '--'} {t}  {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
