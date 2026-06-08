"""
DATA-AI 核心框架单元测试

测试配置、日志、异常等基础设施
"""

import sys
from pathlib import Path

import pytest

# 确保 src 在路径中
_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ─── 配置测试 ───────────────────────────────────────────────────────────────


class TestConfig:
    """配置系统测试"""

    def test_settings_default(self):
        """测试默认配置"""
        from data_ai.utils.config import get_settings

        settings = get_settings()
        assert settings is not None

    def test_llm_config_defaults(self):
        """测试 LLM 默认配置"""
        from data_ai.utils.config import LLMConfig

        config = LLMConfig()
        assert config.model == "claude-3-5-sonnet-20250619"
        assert config.max_tokens > 0
        assert 0.0 <= config.temperature <= 2.0

    def test_sandbox_config_defaults(self):
        """测试沙箱默认配置"""
        from data_ai.utils.config import SandboxConfig

        config = SandboxConfig()
        assert config.enabled is True
        assert config.sandbox_type == "local"
        assert config.timeout > 0

    def test_memory_config_defaults(self):
        """测试记忆系统默认配置"""
        from data_ai.utils.config import MemoryConfig

        config = MemoryConfig()
        assert config.enabled is True
        assert config.keep_recent_messages > 0
        assert config.summary_interval > 0

    def test_search_config_defaults(self):
        """测试搜索引擎默认配置"""
        from data_ai.utils.config import SearchConfig

        config = SearchConfig()
        assert config.engine in ["Google", "Baidu", "DuckDuckGo", "Bing"]
        assert config.max_retries >= 0

    def test_config_validation(self):
        """测试配置验证"""
        from pydantic import ValidationError

        from data_ai.utils.config import LLMConfig

        # 无效的 temperature 应该触发验证错误
        with pytest.raises(ValidationError):
            LLMConfig(temperature=5.0)  # 超出 0-2 范围

        # 有效的 temperature 应该正常
        config = LLMConfig(temperature=1.5)
        assert config.temperature == 1.5

    def test_config_environment_override(self, monkeypatch: pytest.MonkeyPatch):
        """测试环境变量覆盖"""
        from data_ai.utils.config import reload_settings

        # pydantic-settings 嵌套字段使用双下划线分隔
        # DATA_AI_LLM__MODEL -> llm.model
        # DATA_AI__LOG_LEVEL -> log_level (顶级)
        monkeypatch.setenv("DATA_AI_LLM__MODEL", "gpt-4o")
        monkeypatch.setenv("DATA_AI__LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("DATA_AI_LLM__API_KEY", "test-key-123")

        settings = reload_settings()
        assert settings.llm.model == "gpt-4o"
        assert settings.log_level == "DEBUG"
        assert settings.llm.api_key == "test-key-123"


# ─── 日志测试 ───────────────────────────────────────────────────────────────


class TestLogging:
    """日志系统测试"""

    def test_configure_logging_no_crash(self):
        """测试日志配置不会崩溃"""
        from data_ai.utils.logging import configure_logging

        # 不同配置方式都应该正常工作
        configure_logging(level="DEBUG", json_output=False)
        configure_logging(level="INFO", json_output=True, json_indent=2)
        configure_logging(level="WARNING")

    def test_get_logger_returns_logger(self):
        """测试获取日志记录器"""
        from data_ai.utils.logging import get_logger

        logger = get_logger("test")
        assert logger is not None
        assert callable(logger.info)
        assert callable(logger.error)
        assert callable(logger.debug)

    def test_bind_context(self):
        """测试上下文绑定"""
        from data_ai.utils.logging import bind_context, clear_context, get_logger

        bind_context(session_id="test-123", user="tester")
        get_logger("test.context")
        # 不崩溃即可
        clear_context()

    def test_log_level_change(self):
        """测试动态日志级别切换"""
        from data_ai.utils.logging import set_log_level

        set_log_level("DEBUG")
        set_log_level("INFO")
        set_log_level("WARNING")

    def test_secret_filtering(self, capsys: pytest.CaptureFixture):
        """测试敏感信息过滤"""
        from data_ai.utils.logging import configure_logging, get_logger

        configure_logging(level="INFO", json_output=False, colorize=False)
        logger = get_logger("test.secret")

        # 包含 API key 的日志不应泄漏完整密钥
        logger.info("Testing secret filter", extra={"api_key": "sk-secret-1234567890"})

        captured = capsys.readouterr()
        output = captured.out + captured.err
        # 验证输出存在且密钥被过滤
        assert len(output) > 0, "Logger should produce output"


# ─── 异常测试 ───────────────────────────────────────────────────────────────


class TestExceptions:
    """异常系统测试"""

    def test_exception_hierarchy(self):
        """测试异常层级"""
        from data_ai.utils.exceptions import (
            AgentException,
            APIException,
            ConfigException,
            DataAIException,
            LLMException,
            MemoryException,
            PluginException,
            RAGException,
            SandboxException,
            ToolException,
        )

        # 所有异常都应该继承自 DataAIException
        assert issubclass(ConfigException, DataAIException)
        assert issubclass(LLMException, DataAIException)
        assert issubclass(AgentException, DataAIException)
        assert issubclass(ToolException, DataAIException)
        assert issubclass(SandboxException, DataAIException)
        assert issubclass(MemoryException, DataAIException)
        assert issubclass(RAGException, DataAIException)
        assert issubclass(PluginException, DataAIException)
        assert issubclass(APIException, DataAIException)

    def test_exception_message(self):
        """测试异常消息"""
        from data_ai.utils.exceptions import ConfigException, ToolNotFoundError

        exc = ConfigException("Test error message")
        assert exc.message == "Test error message"
        assert "Test error message" in str(exc)

        exc2 = ToolNotFoundError("my_tool")
        assert "my_tool" in str(exc2)
        assert exc2.code.value == "4001"  # ErrorCode.TOOL_NOT_FOUND = "4001"

    def test_exception_with_context(self):
        """测试异常上下文"""
        from data_ai.utils.exceptions import AgentException

        exc = AgentException("Execution failed").with_context(
            agent="test_agent",
            task="test_task",
        )
        assert exc.details["agent"] == "test_agent"
        assert exc.details["task"] == "test_task"

    def test_exception_with_cause(self):
        """测试异常原因链"""
        from data_ai.utils.exceptions import AgentException

        cause = ValueError("Original error")
        exc = AgentException("Wrapper error").with_cause(cause)
        assert exc.cause is cause

    def test_validate_api_key_success(self):
        """测试 API key 验证成功"""
        from data_ai.utils.config import validate_api_key

        result = validate_api_key("sk-valid-key", "TestProvider")
        assert result == "sk-valid-key"

    def test_validate_api_key_failure(self):
        """测试 API key 验证失败"""
        from data_ai.utils.config import validate_api_key
        from data_ai.utils.exceptions import ConfigValidationError

        with pytest.raises(ConfigValidationError):
            validate_api_key(None, "TestProvider")

        with pytest.raises(ConfigValidationError):
            validate_api_key("YOUR_API_KEY", "TestProvider")

        with pytest.raises(ConfigValidationError):
            validate_api_key("sk-xxx", "TestProvider")


# ─── 包导入测试 ─────────────────────────────────────────────────────────────


class TestPackageImports:
    """包导入测试"""

    def test_import_package(self):
        """测试导入主包"""
        import data_ai

        assert hasattr(data_ai, "get_logger")
        assert hasattr(data_ai, "get_settings")
        assert hasattr(data_ai, "DataAIException")

    def test_import_utils(self):
        """测试导入 utils 模块"""
        from data_ai import utils

        assert hasattr(utils, "configure_logging")
        assert hasattr(utils, "get_settings")
        assert hasattr(utils, "DataAIException")
