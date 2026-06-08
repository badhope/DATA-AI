"""修复 _clean_convert_p0p1.py 留下的问题: 模块体里 ``sys.exit()``
之类的顶层执行语句还在, pytest 收集时 import 就会 SystemExit.

策略: 找到 ``# ── pytest 集成 ────`` 之前的最后一段顶层执行代码,
整段 ``exec()`` 起来, 让模块体只是声明, 不直接执行.
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


PYTEST_MARK = "# \u2500\u2500 pytest 集成"


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if PYTEST_MARK not in src:
        return False, "no pytest marker"

    head, tail = src.split(PYTEST_MARK, 1)
    head_lines = head.splitlines()

    # 在 head 里找最末一个 ``def`` 或 ``class`` 声明的行
    last_decl_end = 0
    for i, ln in enumerate(head_lines):
        s = ln.lstrip()
        if s.startswith("def ") or s.startswith("async def ") or s.startswith("class "):
            indent = len(ln) - len(s)
            j = i + 1
            while j < len(head_lines):
                cur = head_lines[j]
                cur_s = cur.lstrip()
                if not cur_s.strip():
                    j += 1
                    continue
                cur_indent = len(cur) - len(cur_s)
                if cur_indent <= indent:
                    break
                j += 1
            last_decl_end = j

    # last_decl_end 之后的所有非空行是模块体
    body_lines = head_lines[last_decl_end:]
    decl_lines = head_lines[:last_decl_end]

    # 把模块体放进 exec, 让模块体不直接执行
    body_src = "\n".join(body_lines)
    if not body_src.strip():
        return False, "empty body"

    # 模块体替换为 ``_module_body = "..."``, 然后用 _run() 触发
    # 实际触发在 ``if __name__ == \"__main__\":`` 里, 以及 pytest 函数里
    new_decl = "\n".join(decl_lines)
    # 用 triple-quoted string 存 body
    body_escaped = body_src.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
    body_literal = f'\n\n_MODULE_BODY = """\n{body_escaped}\n"""\n\n'
    runner = (
        'def _run_module_body() -> None:\n'
        '    """执行原模块体, 把 ``sys.exit()`` 包装成 ``RuntimeError``."""\n'
        '    import sys as _sys\n'
        '    _orig_exit = _sys.exit\n'
        '    def _safe_exit(code=0):\n'
        '        raise SystemExit(code)\n'
        '    _sys.exit = _safe_exit\n'
        '    try:\n'
        '        exec(compile(_MODULE_BODY, __file__, "exec"), globals())\n'
        '    finally:\n'
        '        _sys.exit = _orig_exit\n\n'
        'if __name__ == "__main__":\n'
        '    _run_module_body()\n'
    )
    new_head = new_decl + body_literal + runner
    new_src = new_head + "\n" + PYTEST_MARK + tail
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
