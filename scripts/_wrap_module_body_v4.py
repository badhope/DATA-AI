"""把 test_p0_4 / test_p1_1_2 等会做 ``sys.exit`` 或真 HTTP 调用的
测试文件包成 pytest 友好.

策略改进 (v4): 不再简单地按"缩进=0 判顶层"过滤, 改用 Python AST 解析:
  1. 解析文件得到模块的 top-level 节点列表
  2. 区分 Import / ImportFrom / FunctionDef / ClassDef / Assign / Expr
  3. 收集 Assign / Expr 节点 (顶层可执行代码), 保留其它
  4. 其它节点 (Import / FunctionDef / ClassDef) 原样保留

这样能正确处理多行 import (parenthesized), 不会误删.
"""
from __future__ import annotations

import ast
import base64
from pathlib import Path

TARGETS = [
    "tests/test_p0_4_rag_fileread.py",
    "tests/test_p1_1_2_checkpoint_hil.py",
    "tests/e2e_smoke.py",
    "tests/e2e_frontend_full.py",
    "tests/e2e_user_flow.py",
    "tests/e2e_deep_integration.py",
    "tests/e2e_capability_audit.py",
    "tests/e2e_p1_7.py",
    "tests/e2e_p1_9.py",
]


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if "_MODULE_BODY" in src:
        return False, "already wrapped"

    tree = ast.parse(src, filename=str(path))
    lines = src.splitlines(keepends=True)

    # 收集顶层可执行节点 (Expr / Assign / AnnAssign / AugAssign / Delete / Pass ...)
    # 排除 Import / ImportFrom / FunctionDef / AsyncFunctionDef / ClassDef
    executable_types = (
        ast.Expr, ast.Assign, ast.AnnAssign, ast.AugAssign,
        ast.Delete, ast.Pass, ast.If, ast.For, ast.While, ast.With,
        ast.Try, ast.Raise, ast.Assert, ast.Return, ast.Global, ast.Nonlocal,
    )
    exec_ranges: list[tuple[int, int]] = []
    for node in tree.body:
        if isinstance(node, executable_types):
            start = node.lineno - 1
            end = getattr(node, "end_lineno", None)
            if end is None:
                # fallback: 估算到下一个顶层节点或文件末尾
                end = start + 1
            exec_ranges.append((start, end))

    keep_mask = [True] * len(lines)
    body_chunks: list[str] = []
    for s, e in exec_ranges:
        for i in range(s, min(e, len(lines))):
            keep_mask[i] = False
            body_chunks.append(lines[i])

    if not body_chunks:
        return False, "no executable top-level code"

    body_src = "".join(body_chunks)
    body_b64 = base64.b64encode(body_src.encode("utf-8")).decode("ascii")

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
    return True, f"wrapped {len(body_chunks)} top-level exec lines (AST)"


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
