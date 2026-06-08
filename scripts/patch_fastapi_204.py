"""
patch_fastapi_204.py
====================

一次性兼容性补丁: 给 ``src/data_ai/core/api/extensions.py`` 中所有带
``status_code=204`` 的 FastAPI 路由装饰器追加 ``response_class=Response`` 和
``response_model=None``。

背景
----
FastAPI >= 0.110 在 0 装饰器对 204 状态码启用了更严格的检查:
当被装饰函数带有 ``-> None`` / ``-> XxxResponse`` 这类返回类型注解时,
FastAPI 会尝试把它推断为 ``response_model`` 并触发断言::

    AssertionError: Status code 204 must not have a response body

只追加 ``response_class=Response`` 是不够的 —— 关键是要把
``response_model`` 显式置为 ``None``, 让 FastAPI 不要再为这个端点
生成 response schema。

使用
----
源码部署后, 在仓库根目录执行::

    python scripts/patch_fastapi_204.py

如果 ``extensions.py`` 中相关的 24 个端点已经打过补丁, 该脚本会
打印 ``patched decorators: 0`` 并安全退出（幂等）。

该脚本是纯文本替换, 不依赖任何运行时 import, 可以在 ``pip install -e .``
之前运行。
"""
from __future__ import annotations

from pathlib import Path

TARGET = Path("src/data_ai/core/api/extensions.py")

# 1) 写入 Response 的导入（幂等）
IMPORT_OLD = "from fastapi.responses import JSONResponse"
IMPORT_NEW = "from fastapi.responses import JSONResponse, Response"


def ensure_response_import(src: str) -> tuple[str, bool]:
    """确保 fastapi.responses 中导入了 Response。返回 (新源码, 是否修改)。"""
    if IMPORT_NEW in src:
        return src, False
    if IMPORT_OLD in src:
        return src.replace(IMPORT_OLD, IMPORT_NEW, 1), True
    # 已有其他形式的 import 来自 fastapi.responses, 不强行改动
    return src, False


def patch_decorators(src: str) -> tuple[str, int]:
    """给所有带 status_code=204 的 @router.X(...) 行追加 response_class 和
    response_model, 返回 (新源码, 命中数量)。"""
    new_lines: list[str] = []
    patched = 0
    for line in src.splitlines(keepends=True):
        if (
            "@router." in line
            and "status_code=204" in line
            and "response_model=" not in line
        ):
            # 先补上 response_class=Response, 后面再补 response_model=None
            if "response_class=" not in line:
                line = line.rstrip("\n").rstrip(")") + ", response_class=Response, response_model=None)\n"
            else:
                line = line.rstrip("\n").rstrip(")") + ", response_model=None)\n"
            patched += 1
        new_lines.append(line)
    return "".join(new_lines), patched


def main() -> int:
    if not TARGET.exists():
        print(f"error: {TARGET} not found, please run from repo root", flush=True)
        return 2
    src = TARGET.read_text(encoding="utf-8")
    src, import_changed = ensure_response_import(src)
    src, patched = patch_decorators(src)
    if not import_changed and patched == 0:
        print("nothing to do, file already patched", flush=True)
        return 0
    TARGET.write_text(src, encoding="utf-8")
    if import_changed:
        print("patched import: added Response", flush=True)
    print(f"patched decorators: {patched}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
