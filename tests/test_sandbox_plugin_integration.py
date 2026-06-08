"""
DATA-AI Sandbox + Plugin Integration Tests

Tests sandbox and plugin system integration.
"""

import sys
from pathlib import Path

import pytest

# Ensure src is on path
_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ─── Sandbox Integration Tests ───────────────────────────────────────────────


class TestSandboxPluginIntegration:
    """Test sandbox and plugin system integration."""

    def test_sandbox_manager_singleton(self):
        from data_ai.sandbox import get_sandbox_manager

        mgr1 = get_sandbox_manager()
        mgr2 = get_sandbox_manager()
        assert mgr1 is mgr2

    def test_plugin_registry_singleton(self):
        from data_ai.plugins import get_plugin_registry

        reg1 = get_plugin_registry()
        reg2 = get_plugin_registry()
        assert reg1 is reg2

    @pytest.mark.asyncio
    async def test_sandbox_create_destroy_lifecycle(self):
        from data_ai.sandbox import SandboxManager, SandboxType

        mgr = SandboxManager()
        sb = await mgr.create_sandbox(SandboxType.LOCAL)
        assert sb.sandbox_id is not None

        destroyed = await mgr.destroy_sandbox(sb.sandbox_id)
        assert destroyed is True

    @pytest.mark.asyncio
    async def test_sandbox_execute_in_plugin_context(self):
        """Test that a plugin could theoretically use a sandbox."""
        from data_ai.sandbox import SandboxConfig, SandboxManager, SandboxType

        mgr = SandboxManager()
        config = SandboxConfig(timeout=10)
        sb = await mgr.create_sandbox(SandboxType.LOCAL, config=config)

        # Simulate plugin using sandbox
        result = await sb.execute_code("print(42)")
        assert result.success is True
        assert "42" in result.stdout

        await mgr.destroy_sandbox(sb.sandbox_id)

    @pytest.mark.asyncio
    async def test_multiple_sandboxes(self):
        from data_ai.sandbox import SandboxManager, SandboxType

        mgr = SandboxManager()
        initial = len(mgr.list_sandboxes())

        await mgr.create_sandbox(SandboxType.LOCAL)
        await mgr.create_sandbox(SandboxType.LOCAL)

        assert len(mgr.list_sandboxes()) == initial + 2

        await mgr.destroy_all()
        assert len(mgr.list_sandboxes()) == 0

    def test_sandbox_config_validation(self):
        from data_ai.sandbox import SandboxConfig

        config = SandboxConfig(
            timeout=5,
            max_memory_mb=256,
            max_cpu_percent=50,
            allowed_commands=["python"],
        )
        assert config.timeout == 5
        assert config.max_memory_mb == 256
        assert len(config.allowed_commands) == 1

    def test_plugin_with_sandbox_dependency(self):
        """Test plugin info with sandbox dependency."""
        from data_ai.plugins import PluginInfo

        info = PluginInfo(
            name="sandbox_plugin",
            version="1.0.0",
            dependencies=["data_ai.sandbox"],
            plugin_type="tool",
        )
        assert "data_ai.sandbox" in info.dependencies

    @pytest.mark.asyncio
    async def test_plugin_registry_cleanup(self):
        from data_ai.plugins import BasePlugin, PluginInfo, PluginRegistry

        class CleanupTestPlugin(BasePlugin):
            info = PluginInfo(name="cleanup_test")

            async def initialize(self) -> None:
                self._initialized = True

            async def cleanup(self) -> None:
                self._initialized = False

        reg = PluginRegistry()
        reg._plugins.clear()
        reg._plugin_classes.clear()

        try:
            plugin = CleanupTestPlugin()
            plugin._initialized = True
            reg.register_instance(plugin)

            await reg.cleanup_all()
            assert plugin.is_initialized is False
        finally:
            reg._plugins.clear()
            reg._plugin_classes.clear()


# ─── Sandbox Config Integration ──────────────────────────────────────────────


class TestSandboxConfigIntegration:
    """Test sandbox config with various settings."""

    def test_config_with_env_vars(self):
        from data_ai.sandbox import SandboxConfig

        config = SandboxConfig(
            env_vars={"TEST_VAR": "test_value", "ANOTHER": "123"},
        )
        assert config.env_vars["TEST_VAR"] == "test_value"
        assert config.env_vars["ANOTHER"] == "123"

    def test_config_with_allowed_paths(self):
        from data_ai.sandbox import SandboxConfig

        config = SandboxConfig(
            allowed_paths=["/tmp", "/home/user/workspace"],
        )
        assert len(config.allowed_paths) == 2

    def test_config_network_disabled(self):
        from data_ai.sandbox import SandboxConfig

        config = SandboxConfig(network_enabled=False)
        assert config.network_enabled is False

    def test_execution_result_fields(self):
        from data_ai.sandbox import ExecutionResult

        result = ExecutionResult(
            success=True,
            stdout="output",
            stderr="",
            exit_code=0,
            execution_time_ms=42.5,
            sandbox_id="test_abc",
            resource_usage={"memory_mb": 50, "cpu_percent": 10},
        )
        assert result.resource_usage["memory_mb"] == 50
        assert result.execution_time_ms == 42.5
