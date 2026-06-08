"""一次性转换 test_p0_4_rag_fileread.py 为 pytest 友好.

这个文件特殊: 模块体里直接 urllib.request.urlopen 一个本地后端,
没启动服务时会在 import 期就抛 ConnectionRefusedError 导致 pytest
collection 失败.

策略: 整段模块体塞进 _main(), 末尾追加 pytest test, 后者用
socket.create_connection 先探一下 127.0.0.1:8000, 不可达就 skip.
"""
from __future__ import annotations

import socket
from pathlib import Path

TARGET = Path("tests/test_p0_4_rag_fileread.py")


def _server_reachable(host: str = "127.0.0.1", port: int = 8000, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    if not TARGET.exists():
        print(f"  -- {TARGET} not found")
        return 0
    src = TARGET.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)

    # 找 ``# ── file_read 修复 ─────`` 之后的模块体起点
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("# ── file_read 修复"):
            body_start = i
            break

    head = "".join(lines[:body_start])
    body = "".join(lines[body_start:])

    indented = "\n".join(
        ("    " + ln if ln.strip() else ln) for ln in body.splitlines()
    )
    main_fn = "\n\ndef _main() -> None:\n" + indented + "\n"
    main_call = "\n\nif __name__ == \"__main__\":\n    _main()\n"
    pytest_fn = '''


# ── pytest 集成 ────────────────────────────────────────────
def test_test_p0_4_rag_fileread() -> None:
    """原模块直接跑一遍; 后端不可达时整段 skip."""
    import pytest as _pytest
    if not _server_reachable():
        _pytest.skip("后端服务 127.0.0.1:8000 不可达, 跳过需要真 HTTP 的断言")
        return
    _main()
'''
    # 补 import socket + helper (放在文件顶)
    new_src = (
        "import socket\n\n"
        "def _server_reachable(host: str = '127.0.0.1', port: int = 8000, timeout: float = 0.3) -> bool:\n"
        "    try:\n"
        "        with socket.create_connection((host, port), timeout=timeout):\n"
        "            return True\n"
        "    except OSError:\n"
        "        return False\n\n"
        + head
        + main_fn
        + main_call
        + pytest_fn
    )
    TARGET.write_text(new_src, encoding="utf-8")
    print(f"  OK {TARGET} converted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
