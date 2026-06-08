"""最后一次清理: 把被错误提升到顶部的 import 行去掉多余缩进,
把被 ``_main()`` 切掉的 docstring 三引号补回来.

这版假设前一轮 _lift_future_import.py 已运行过, 文件结构为:
  1. \"\"\"Auto-fixed: imports lifted to module level.\"\"\"
  2. from __future__ import annotations
  3. 空行
  4-N. 4空格缩进的 import / from 行
  N+1. 空行
  def _main() -> None:
      P0-3 测试:...     <- 这里少了开头的三引号
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


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if '"""Auto-fixed: imports lifted to module level."""' not in src:
        return False, "no auto-fixed header"
    lines = src.splitlines(keepends=True)

    # 1. 把所有以 4 空格开头且是 import / from 的行的缩进去掉
    new_lines: list[str] = []
    for ln in lines:
        if re.match(r"^    (import |from )", ln):
            new_lines.append(ln[4:])
        else:
            new_lines.append(ln)

    # 2. 找到 ``def _main() -> None:`` 之后, 紧跟的 ``    """`` 行
    # 把它替换成 ``    """`` 然后查找 ``    """`` 闭合, 在闭合后插入
    # 空行. 如果没有闭合, 在第一个 ``    # ──`` 或 ``    def _http``
    # 等具体代码行的前面补一个 ``    """``.
    out: list[str] = []
    inserted = False
    for ln in new_lines:
        out.append(ln)
        if not inserted and ln.rstrip() == "def _main() -> None:":
            # 等下一行是 `    """`, 自动确保闭合
            out.append('    """\n')
            inserted = True
        elif inserted and ln.startswith("    ") and not ln.startswith("    \"\"\""):
            # 这是 docstring 内容或闭合边界
            stripped = ln.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("\"\"\"") and stripped != "'''":
                # 闭合 docstring 并正常化本行
                out[-1] = '    """\n'  # 替换
                out.append(ln)
                inserted = False
                break
            # 如果是注释行, 继续; 真正闭合由 elif 完成
        elif inserted and ln.strip() == '"""':
            out[-1] = '    """\n'  # 替换
            inserted = False
            break

    if not inserted:
        return False, "no _main def"

    new_src = "".join(out)
    path.write_text(new_src, encoding="utf-8")
    return True, "indentation fixed + docstring restored"


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
