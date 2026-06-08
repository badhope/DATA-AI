"""把任意测试文件的模块体 (def/class 之后的顶层执行代码) 收进
``_run_module_body()`` + ``_MODULE_BODY = \"\"\"...\"\"\"`` 形式,
避免 pytest 收集时直接执行 sys.exit / urllib.urlopen / 顶层 assert 等.
"""
from __future__ import annotations

from pathlib import Path

TARGETS = [
    "tests/test_p0_4_rag_fileread.py",
    "tests/test_p1_1_2_checkpoint_hil.py",
]


def find_last_def_end(lines: list[str]) -> int:
    last_def_end = 0
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        s = ln.lstrip()
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
            last_def_end = i
            continue
        i += 1
    return last_def_end


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if "_MODULE_BODY" in src:
        return False, "already wrapped"
    lines = src.splitlines()
    last_def_end = find_last_def_end(lines)
    decl_lines = lines[:last_def_end]
    body_lines = lines[last_def_end:]
    body_src = "\n".join(body_lines)
    if not body_src.strip():
        return False, "empty body"

    # 额外保护: 如果体里有 ``import socket`` 等已经在文件顶部的 import,
    # 不重复 import; 但 ``from data_ai.* import`` 等一般不会重复.
    body_escaped = body_src.replace("\\", "\\\\")
    # 不替换 """ 因为我们用单引号字符串存储, 但我们要避免单引号字符串嵌入问题
    # 改用 base64 编码
    import base64
    body_b64 = base64.b64encode(body_src.encode("utf-8")).decode("ascii")
    decl_src = "\n".join(decl_lines)
    runner = f'''

# ── pytest 集成 (auto) ────────────────────────────────────
import base64 as _b64
_MODULE_BODY = _b64.b64decode({body_b64!r}).decode("utf-8")

def _run_module_body() -> None:
    """执行原模块体, 把 ``sys.exit()`` 包装成 ``SystemExit`` 异常."""
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

import pytest as _pytest
def test_run_module_body() -> None:
    """原模块体直接执行, sys.exit(0) 视作通过, 非 0 视作失败."""
    try:
        _run_module_body()
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        if code != 0:
            _pytest.fail(f"module body 退出码 {{code}}")
'''
    new_src = decl_src + runner + "\n"
    path.write_text(new_src, encoding="utf-8")
    return True, f"wrapped {len(body_lines)} body lines"


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
