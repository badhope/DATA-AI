"""修复 _convert_test_module_exec.py 转换后被破坏的测试文件 (第二轮).

第一轮脚本的 regex 把 ``\\n`` 当成了 2 个字符的转义序列, 实际
文件里是新行字节 (1 char), 匹配失败. 这一版用更朴素的方式:
扫所有行, 凡 ``msg = "`` 行尾 + 下一行 ``".join`` 行首, 合并
回单行; pytest.fail 里的多行 f-string 同样合并.
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
    lines = src.splitlines()

    # 模式 1: ``msg = "`` 行尾 + ``".join(...)`` 行首 → 合并
    new_lines: list[str] = []
    i = 0
    n = len(lines)
    fixed = 0
    while i < n:
        cur = lines[i]
        if cur.rstrip().endswith('msg = "') and i + 1 < n and lines[i + 1].lstrip().startswith('".join'):
            merged = cur + '\\n' + lines[i + 1].lstrip()
            new_lines.append(merged)
            i += 2
            fixed += 1
            continue
        # 模式 2: ``pytest.fail(f"...`` 行内嵌真换行 + ``{msg}")`` 行首
        if 'pytest.fail(f"' in cur and cur.count('"') % 2 == 1 and i + 1 < n and lines[i + 1].strip().startswith('{msg}")'):
            # 把第 i 行末尾到 \n 的引号闭合后再接 {msg}"), 用 \n 转义
            merged = cur.rstrip() + '\\n' + lines[i + 1].strip()
            new_lines.append(merged)
            i += 2
            fixed += 1
            continue
        new_lines.append(cur)
        i += 1

    if fixed == 0:
        return False, "no broken pattern"
    new_src = "\n".join(new_lines) + "\n"
    path.write_text(new_src, encoding="utf-8")
    return True, f"fixed {fixed} broken line(s)"


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
