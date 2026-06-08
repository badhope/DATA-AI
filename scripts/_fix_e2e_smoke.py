"""修复 e2e_smoke.py 和 e2e_frontend_full.py 里的 ``\\n`` 被错误解释
为真换行的问题.

适用 _convert_test_module_exec.py 第一版的产物: 文件末尾的
``msg = "\\n".join(...)`` 和 ``pytest.fail(f"...\\n{msg}")`` 被错误
写成了真换行.
"""
from __future__ import annotations

from pathlib import Path

TARGETS = [
    "tests/e2e_smoke.py",
    "tests/e2e_frontend_full.py",
]


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
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
        if 'pytest.fail(f"' in cur and cur.count('"') % 2 == 1 and i + 1 < n and lines[i + 1].strip().startswith('{msg}")'):
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
