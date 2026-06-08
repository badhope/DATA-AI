"""修复 _convert_test_module_exec.py 转换后被破坏的测试文件.

症状: 转换脚本生成的 f-string 模板里有 ``\\n`` 字符, Python 解释时
把 ``\\n`` 解释成换行, 导致文件里实际写入了真换行, 字符串被截断.

修复策略: 把文件末尾 pytest 集成段里 ``\\n`` 重新变成 ``\\n`` 字符.
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

# 匹配两种被破坏的写法:
#   1. msg = "<真换行>".join(...)
#   2. pytest.fail(f"...:<真换行>{msg}")
BAD_MSG_JOIN = re.compile(r'msg = "\n"\.join')
BAD_FAIL = re.compile(r'pytest\.fail\(f"([^"]*?)\n\{msg\}"\)')


def fix_one(path: Path) -> tuple[bool, str]:
    src = path.read_text(encoding="utf-8")
    if BAD_MSG_JOIN.search(src) is None and BAD_FAIL.search(src) is None:
        return False, "no broken pattern"
    new = BAD_MSG_JOIN.sub('msg = "\\n".join', src)
    new = BAD_FAIL.sub(lambda m: f'pytest.fail(f"{m.group(1)}\\n{{msg}}")', new)
    path.write_text(new, encoding="utf-8")
    return True, "fixed"


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
