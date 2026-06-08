"""一次性转换脚本: 把模块级执行 + sys.exit 模式的测试文件
转为 pytest 友好版本。

策略:
  1. 找到最后一个 ``def`` / ``class`` 声明的结束位置
  2. 在此之后的所有非空行视为模块体
  3. 把模块体包裹进 ``def _main(): ...`` 函数
  4. 末尾追加 ``if __name__ == "__main__": _main()``
  5. 同时追加一个 pytest 用例 ``test_<原文件名>`` 调用 ``_main()`` 并把
     全局 ``fails`` / ``failed`` 列表里的内容抛成 ``pytest.fail``
"""
from __future__ import annotations

import re
from pathlib import Path

# 这些文件的命名
TARGETS = [
    "tests/test_p1_3_subagent.py",
    "tests/test_p1_4_tool_retry.py",
    "tests/test_p1_supplementary.py",
    "tests/test_p1_1_2_checkpoint_hil.py",
    "tests/test_p0_5_multi_llm.py",
    "tests/test_p0_3_presets_api.py",
    "tests/e2e_smoke.py",
    "tests/e2e_frontend_full.py",
]


def find_body_start(lines: list[str]) -> int:
    """找到模块体开始行 (第一个非 def/class/import/blank/comment 的行)"""
    in_def = False
    last_def_end = -1
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("from ") or s.startswith("import "):
            continue
        if s.startswith("def ") or s.startswith("async def "):
            in_def = True
            continue
        if s.startswith("class "):
            in_def = True
            continue
        if in_def:
            # 在 def/class 体内, 跳过
            if s and not s.startswith(("def ", "class ", "async def ", "@")):
                continue
        # 第一个非上述的行
        return i
    return len(lines)


def convert(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    body_start = find_body_start(lines)
    if body_start >= len(lines):
        return False, "no body to wrap"
    # 检查是否已经被转换过
    if any("if __name__ == \"__main__\"" in line for line in lines):
        # 已经有 main 守卫, 只确保有 pytest 函数
        return maybe_add_pytest(path, src)

    head = "".join(lines[:body_start])
    body = "".join(lines[body_start:])

    # 给 body 加 4 空格缩进
    indented = "\n".join(
        ("    " + ln if ln.strip() else ln) for ln in body.splitlines()
    )
    main_fn = "\n\ndef _main() -> None:\n" + indented + "\n"
    main_call = "\n\nif __name__ == \"__main__\":\n    _main()\n"

    # 找失败的全局变量名
    fail_var = None
    for cand in ("fails", "fail_msgs", "failures", "errors"):
        if f"\n{cand}" in src or f" {cand} " in src or f" {cand}=" in src or f" {cand}:" in src:
            fail_var = cand
            break
    if fail_var is None:
        fail_var = "fails"  # 默认

    stem = path.stem
    # 注意: 下面 f-string 中的 {{...}} 是转义, 让最终写到目标文件里的是
    # 真正的 Python 代码; 只 {stem} / {fail_var} 是要被本脚本插值的变量
    pytest_fn = f"""

# ── pytest 集成 ────────────────────────────────────────────
def test_{stem.replace('-', '_')}() -> None:
    \"\"\"把原 ``_main()`` 走一遍, 若有失败项转成 pytest.fail\"\"\"
    _main()
    try:
        bag = {fail_var}
    except NameError:
        pytest.skip("no failure aggregator in this script")
        return
    if bag:
        msg = "\n".join(str(x) for x in bag)
        if hasattr(bag, "clear"):
            bag.clear()
        pytest.fail(f"{stem} failed:\n{{msg}}")
"""

    new_src = head + main_fn + main_call + pytest_fn
    path.write_text(new_src, encoding="utf-8")
    return True, f"converted (body_start={body_start})"


def maybe_add_pytest(path: Path, src: str) -> tuple[bool, str]:
    """如果已经有 main 守卫但缺 pytest 函数, 补一个"""
    if "def test_" in src and "pytest" in src:
        return False, "already has pytest function"
    return True, "needs manual review"


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
