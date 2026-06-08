# DATA-AI 测试指南

本目录是项目 pytest 套件的根目录。所有用例只依赖**核心依赖**
（`pip install -e .`）即可跑，可选依赖（`chromadb`、`sentence-transformers`、
`anthropic`、`google-generativeai`、`PyPDF2` 等）没装时对应测试会 skip 或
xfail，不会报结构错误。

## 📁 测试目录结构

```
tests/
├── conftest.py                       # pytest fixtures (warnings filter, tmp dirs)
├── e2e_*.py                          # 端到端 smoke
├── test_agents_unified.py            # Agent 单/多智能体统一测试
├── test_agent_tool_sdk_deep.py       # Agent ↔ Tool ↔ SDK 深度集成
├── test_advanced_features.py         # 高级工作流、多 agent 协作
├── test_builtin_sandbox.py           # 内置本地沙箱 (Python / Bash / Node)
├── test_core_features.py             # 核心功能基线
├── test_enterprise_governance.py     # Tier-1 治理: audit / quota / webhooks / scheduler
├── test_enterprise_tier2.py          # Tier-2 治理: tenants / rbac / billing / sla / sso / residency
├── test_enterprise_tier3.py          # Tier-3 治理: replication / recovery / compensation
├── test_full_integration.py          # 全栈集成
├── test_llm_deep.py                  # 19 个 LLM provider × 离线模型
├── test_memory_system.py             # 短期 / 长期 / 摘要 记忆
├── test_new_modules.py               # 新增能力
├── test_new_tools.py                 # 30+ 工具
├── test_p0_*.py                      # P0 阶段交付
├── test_p1_*.py                      # P1 阶段交付 (checkpoint / HIL / sub-agent / tool retry)
├── test_plugins.py                   # 插件系统
├── test_rag_system.py                # RAG (loaders / splitters / stores)
├── test_rag_memory_deep.py           # RAG ↔ Memory ↔ Tool 深度
├── test_rag_integration.py           # RAG 集成 (旧 test_office_final)
├── test_sandbox_plugin_integration.py# Sandbox ↔ Plugin 集成 (旧 test_office_standalone)
├── test_session_memory_basic.py      # SessionManager / MemoryConfig (旧 test_memory_explorer)
├── test_session_memory_integration.py# Session ↔ Memory 集成 (旧 test_office_simple)
├── test_tool_ecosystem.py            # Tool 注册 / Agent / 执行 / Schema (旧 test_office_integration)
└── test_*.py                         # 其它按需
```

> 旧 `test_office_*.py` / `test_memory_explorer.py` 命名是早期 office demo
> 阶段遗留下来的，**内部测试的从来都不是 office**，所以按其真实职责
> 重命名了。`pytest` 通过 `python_files = ["test_*.py"]` 自动发现，
> 不需要改 `conftest.py`。

## 🚀 运行测试

### 跑全部

```bash
# 通过本项目自带的 run_tests.py (会过滤 UserWarning)
python run_tests.py

# 或者直接用 pytest
python -m pytest tests/ -v --tb=short
```

### 跑指定文件 / 用例

```bash
python -m pytest tests/test_rag_integration.py -v
python -m pytest tests/test_tool_ecosystem.py::TestToolRegistryIntegration -v
```

### 按 marker 过滤（项目自定义 marker 见 [pyproject.toml](../pyproject.toml)）

```bash
python -m pytest -m "not slow" tests/
```

### 覆盖率

```bash
python -m pytest tests/ --cov=data_ai --cov-report=term-missing
python -m pytest tests/ --cov=data_ai --cov-report=html
# 然后用浏览器打开 htmlcov/index.html
```

## ✏️ 编写测试

### 最小示例（基于当前 `data_ai.sdk`）

```python
from data_ai.sdk import create_sdk  # 真实公开 API


def test_chat_smoke():
    sdk = create_sdk()
    reply = sdk.chat("hi", model="offline-chat", stream=False)
    assert reply and isinstance(reply, str)
```

### Mock 外部依赖

```python
from unittest.mock import patch, MagicMock


def test_with_mock():
    fake = MagicMock()
    fake.invoke.return_value = "mocked"
    with patch("data_ai.core.llm.manager.LLMManager.invoke", fake.invoke):
        # 调用受测函数
        ...
```

### 异步

```python
import pytest

pytestmark = pytest.mark.asyncio


async def test_async_flow():
    ...
```

> 项目的 `pyproject.toml` 已设 `asyncio_mode = "auto"`，所以 async 用例
> 不需要显式加 `@pytest.mark.asyncio`。

## 🔧 测试配置

完整配置见 [pyproject.toml](../pyproject.toml) 中的 `[tool.pytest.ini_options]`：

```ini
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"
asyncio_mode = "auto"
```

## ⚠️ 注意事项

1. **测试隔离** — 每个用例应独立运行；跨用例共享状态走 `conftest.py` 的 fixture。
2. **可选依赖** — 没装 `chromadb` / `sentence-transformers` / `playwright` 时，
   对应测试会 skip。不要因为 skip 报红。
3. **离线模型** — `data-ai chat --model offline-chat` 走内置模板，不需要任何
   API key，是 CI 与本地烟测的稳定来源。
4. **清理资源** — 用 `tmp_path` / `tmp_path_factory` 而不是写死路径。
5. **真实数据** — 不要 commit 大文件或 API key。

## 📚 参考

- [pytest 文档](https://docs.pytest.org/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)

---

**最后更新**: 2026-06-07
