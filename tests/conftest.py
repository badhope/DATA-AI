"""
Pytest 全局配置和 fixtures

为所有测试提供共享的 fixtures 和配置
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# 将 src 目录加入路径以便直接导入 data_ai
_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# 设置测试环境变量（避免读取真实配置）
os.environ.setdefault("DATA_AI_API_KEY", "test-api-key")
os.environ.setdefault("DATA_AI_MODEL", "claude-3-5-sonnet-20250619")
os.environ.setdefault("DATA_AI_LOG_LEVEL", "DEBUG")


# ─── Session Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def project_root() -> Path:
    """项目根目录"""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def src_dir() -> Path:
    """src 目录"""
    return Path(__file__).parent.parent / "src"


# ─── Temp Dir Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录，测试后自动清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir: Path) -> Path:
    """创建临时配置文件"""
    config_path = temp_dir / "config.toml"
    config_path.write_text(
        '[llm]\napi_key = "test-key"\nmodel = "claude-3-5-sonnet"\n',
        encoding="utf-8",
    )
    return config_path


# ─── Config Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """使用模拟配置覆盖真实配置"""
    monkeypatch.setenv("DATA_AI_API_KEY", "test-key-for-unit-tests")
    monkeypatch.setenv("DATA_AI_MODEL", "test-model")


# ─── Logging Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def capture_logs(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """捕获日志输出"""
    caplog.set_level("DEBUG")
    return caplog


# ─── Sandbox Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def sandbox_workspace(temp_dir: Path) -> Path:
    """沙箱工作目录"""
    workspace = temp_dir / "sandbox_workspace"
    workspace.mkdir()
    return workspace


# ─── Mock LLM Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def mock_llm_response() -> dict[str, Any]:
    """模拟 LLM 响应"""
    return {
        "id": "test-message-001",
        "model": "claude-3-5-sonnet",
        "content": [
            {
                "type": "text",
                "text": "This is a test response from the LLM.",
            }
        ],
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
        },
    }


# ─── 参数化标记 ─────────────────────────────────────────────────────────────

pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.e2e = pytest.mark.e2e
pytest.mark.slow = pytest.mark.slow
pytest.mark.flaky = pytest.mark.flaky
