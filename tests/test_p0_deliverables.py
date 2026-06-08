"""
DATA-AI P0 交付物综合测试

覆盖:
  1. ContextStore 完整 CRUD + 边界 + 3 Agent 场景
  2. 4 个 Preset 配置完整性
  3. IntentRecognizer 口语化归一化
  4. setup.sh 文件存在 + 可执行 + bash 语法正确

运行:
    python -m pytest tests/test_p0_deliverables.py -v
    # 或旧用法: PYTHONPATH=src python3 tests/test_p0_deliverables.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 修复: 用相对路径替代写死的 /workspace/DATA-AI
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

import pytest  # noqa: E402

passes: list[str] = []
fails: list[tuple[str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (passes if ok else fails).append((name, detail))
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name:48} {detail}")


def _run_setup_sh_checks() -> None:
    print("\n[1] setup_sandbox.sh 静态检查")
    setup_sh = REPO / "scripts" / "setup_sandbox.sh"
    check("setup.sh 文件存在", setup_sh.exists(), str(setup_sh))
    check("setup.sh 可执行", os.access(setup_sh, os.X_OK) if setup_sh.exists() else False)
    if setup_sh.exists():
        import shutil

        bash_bin = shutil.which("bash")
        # shutil.which 在 Windows 上偶尔会返回 WSL 的 "bash.exe" 路径, 但实际
        # 启动会因 WSL relay 失败而抛 FileNotFoundError. 这里加 try 兜底.
        bash_ok = False
        bash_err = ""
        if bash_bin:
            try:
                r = subprocess.run(
                    [bash_bin, "-n", str(setup_sh)],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                bash_ok = r.returncode == 0
                bash_err = r.stderr[:80]
            except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as e:
                bash_err = f"bash 不可执行 ({e!r})"
        if bash_ok:
            check("setup.sh bash 语法", True, "无错误")
        else:
            # 无 bash / bash 跑不起来时降级为纯静态扫描
            content = setup_sh.read_text()
            has_shebang = content.startswith("#!/")
            balanced = content.count("{") == content.count("}")
            ok = has_shebang and balanced
            detail = f"无 bash ({bash_err}), 仅做 shebang+括号配对静态检查" if not ok else "无 bash, 静态检查通过"
            check("setup.sh bash 语法 (静态降级)", ok, detail)
        content = setup_sh.read_text()
        check("setup.sh 装 libreoffice", "libreoffice" in content)
        check("setup.sh 装 pandoc", "pandoc" in content)
        check("setup.sh 装 fonts-wqy-microhei", "fonts-wqy-microhei" in content)
        check("setup.sh 装 fonts-noto-cjk", "fonts-noto-cjk" in content)
        check("setup.sh 装 pandas", "pandas" in content)
        check("setup.sh 装 PyMuPDF", "PyMuPDF" in content)
        check("setup.sh 装 pdfplumber", "pdfplumber" in content)
        check("setup.sh 有验证段", "验证" in content)
        check("setup.sh 使用 set -e", "set -e" in content)


def _run_context_store_checks() -> None:
    print("\n[2] ContextStore 核心 CRUD")
    from data_ai.core.context_store import ContextStore  # noqa: E402

    tmpdir = tempfile.mkdtemp(prefix="ctx_test_")
    store = ContextStore(base_dir=tmpdir)

    ctx1 = store.save("main_character", "陈默,28岁,前刑警", namespace="novel", tags=["character", "main"])
    check("save 首次", ctx1.version == 1, f"v{ctx1.version}")

    ctx2 = store.save("main_character", "陈默,28岁,前刑警,左眼有疤", namespace="novel", tags=["character", "main"])
    check(
        "save 更新触发版本", ctx2.version == 2 and len(ctx2.history) == 1, f"v{ctx2.version}, hist={len(ctx2.history)}"
    )

    loaded = store.load("main_character", namespace="novel")
    check("load 读到最新内容", loaded is not None and "左眼有疤" in loaded.content)

    check("load 不存在返回 None", store.load("nonexistent", namespace="novel") is None)

    store.save("plot_ch1", "雨夜", namespace="novel", tags=["plot"])
    store.save("company", "蓝海科技", namespace="finance", tags=["company"])
    all_metas = store.list()
    check("list 全量", len(all_metas) == 3, f"{len(all_metas)} 个")

    ns_metas = store.list(namespace="novel")
    check("list 按 namespace 过滤", len(ns_metas) == 2)

    tag_metas = store.list(tag="plot")
    check("list 按 tag 过滤", len(tag_metas) == 1)

    empty_metas = store.list(namespace="nonexistent")
    check("list 空命名空间返回空列表", len(empty_metas) == 0)

    results = store.search("刑警")
    check("search 命中", len(results) == 1)

    no_results = store.search("完全找不到的关键词xyz")
    check("search 未命中返回空", len(no_results) == 0)

    hist = store.history("main_character", namespace="novel")
    check("history 返回旧版本", len(hist) >= 1)

    big = "x" * 100000
    big_ctx = store.save("big", big, namespace="t")
    check("save 极长内容", big_ctx.version == 1 and len(big_ctx.content) == 100000)

    ok_del = store.delete("plot_ch1", namespace="novel")
    check("delete 存在", ok_del is True)

    no_del = store.delete("nonexistent", namespace="novel")
    check("delete 不存在返回 False", no_del is False)

    check("load 删除后为 None", store.load("plot_ch1", namespace="novel") is None)

    ns = store.namespaces()
    check("namespaces 列出", "novel" in ns and "finance" in ns)

    files = list(Path(tmpdir).rglob("*.json"))
    check("实际落盘 JSON 文件", len(files) == 3, f"{len(files)} 个文件")

    sample = files[0].read_text(encoding="utf-8")
    check("落盘文件含 namespace 字段", '"namespace"' in sample)
    check("落盘文件含 version 字段", '"version"' in sample)
    check("落盘文件含 history 数组", '"history"' in sample)


def _run_preset_checks() -> None:
    print("\n[3] 4 个 Preset 配置完整性")
    from data_ai.plugins.agents import REGISTERED_PRESETS, list_presets  # noqa: E402

    briefs = list_presets()
    check("4 个 preset 注册", len(briefs) == 4, f"实际 {len(briefs)} 个")

    expected_roles = {"secretary", "customer_service", "novel_writer", "finance_analyst"}
    actual_roles = {p["role"] for p in briefs}
    check("4 个 role 名正确", actual_roles == expected_roles, f"差异 {actual_roles ^ expected_roles}")

    for role in expected_roles:
        p = REGISTERED_PRESETS[role]
        check(f"{role}: system_prompt 存在", bool(p.get("system_prompt")))
        check(
            f"{role}: system_prompt 长度>200",
            len(p.get("system_prompt", "")) > 200,
            f"{len(p.get('system_prompt', ''))} 字",
        )
        check(f"{role}: tools 列表非空", len(p.get("tools", [])) > 0, f"{len(p.get('tools', []))} 个")
        check(f"{role}: default_namespace 设置", bool(p.get("default_namespace")))
        check(f"{role}: max_iterations 设置", p.get("max_iterations", 0) > 0)
        check(f"{role}: temperature 在 [0,1]", 0.0 <= p.get("temperature", 0) <= 1.0, f"{p.get('temperature')}")


def _run_intent_checks() -> None:
    print("\n[4] IntentRecognizer 口语化归一化")
    from data_ai.core.intent.recognizer import IntentRecognizer  # noqa: E402

    rec = IntentRecognizer()
    norm = rec._normalize_colloquial

    check("错别字: 帐单→账单", "账单" in norm("我的帐单有问题"))
    check("错别字: 帐号→账号", "账号" in norm("我的帐号"))
    check("错别字: 登陆→登录", "登录" in norm("我要登陆"))
    check("口语化: 帮我一下→帮我", "帮我" in norm("帮我一下"))
    check("口语化: 弄一下→处理", "处理" in norm("弄一下"))
    check("口语化: 搞一下→处理", "处理" in norm("搞一下"))
    check("中英混输: 打开 app→打开应用", "应用" in norm("打开 app"))
    check("中英混输: send 邮件→发邮件", "发邮件" in norm("send 邮件"))
    check("啰嗦前缀: 请问一下→请问", "请问" in norm("请问一下"))
    check("啰嗦前缀: 能不能→可以", "可以" in norm("能不能"))
    check(
        "老板口语: 给我弄→帮我(含串行替换)",
        norm("给我弄一下").startswith("帮我"),
        f"'{norm('给我弄一下')}' 应以'帮我'开头",
    )
    check("空字符串不崩", norm("") == "")
    check("不替换时不变", norm("你好") == "你好")

    intent = rec.recognize("帮我一下,弄一下这个文件,我的帐单有问题")
    check("recognize 调用没崩", intent is not None)
    check("recognize raw_query 保留原文", intent.raw_query == "帮我一下,弄一下这个文件,我的帐单有问题")
    check(
        "recognize normalized 走过口语化",
        "处理" in intent.normalized_query and "账单" in intent.normalized_query,
        intent.normalized_query,
    )


def _run_all() -> None:
    _run_setup_sh_checks()
    _run_context_store_checks()
    _run_preset_checks()
    _run_intent_checks()
    print()
    print("=" * 64)
    print(f"通过: {len(passes)}   失败: {len(fails)}")
    print("=" * 64)
    if fails:
        print("\n失败项:")
        for n, d in fails:
            print(f"  ✗ {n}  {d}")


# ── pytest 用例 ───────────────────────────────────────────
def test_p0_deliverables() -> None:
    """聚合的 P0 交付物自检"""
    _run_all()
    if fails:
        msg = "\n".join(f"  ✗ {n}  {d}" for n, d in fails)
        fails.clear()
        pytest.fail(f"P0 deliverables failed:\n{msg}")


if __name__ == "__main__":
    _run_all()
    if fails:
        sys.exit(1)
    print("\n✅ P0 全部交付物端到端测试通过")
