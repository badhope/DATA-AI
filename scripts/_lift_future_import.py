"""把被错误地塞进 _main() 里的 ``from __future__ import annotations``
挪到文件最顶部, 同时把对应的 ``import json/os/sys/...`` 等也提到
模块级 (因为 pytest 收集时只跑模块体, 不调用 _main, 这些 import
就缺失了).
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

# 匹配 ``def _main() -> None:`` 之后第一个非空行
MAIN_RE = re.compile(r"^def _main\(\) -> None:\s*$", re.M)


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if "from __future__ import annotations" in src.split("def _main()")[0]:
        return False, "already at top"
    if 'from __future__ import annotations' not in src:
        return False, "no future import found"

    # 1. 把所有 _main() 体内的 ``from __future__ import annotations`` 行去掉
    main_match = MAIN_RE.search(src)
    if not main_match:
        return False, "no _main def found"
    head, body = src[: main_match.end()], src[main_match.end():]
    body_lines = body.splitlines(keepends=True)
    cleaned = [
        ln for ln in body_lines
        if ln.strip() != "from __future__ import annotations"
        and ln.strip() != '"""'  # 文件首 docstring 已被 body 包裹, 不动它
    ]
    body = "".join(cleaned)

    # 2. 提取 body 里的所有 ``import x`` / ``from x import y`` 提到顶部
    imports: list[str] = []
    other: list[str] = []
    for ln in body.splitlines(keepends=True):
        s = ln.strip()
        if s.startswith("import ") or s.startswith("from "):
            imports.append(ln)
        else:
            other.append(ln)
    new_top = (
        '"""Auto-fixed: imports lifted to module level."""\n'
        "from __future__ import annotations\n\n"
        + "".join(imports)
        + "\n\n"
    )
    new_src = new_top + head + "".join(other)
    path.write_text(new_src, encoding="utf-8")
    return True, f"lifted {len(imports)} import lines"


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
