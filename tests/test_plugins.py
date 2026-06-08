"""
DATA-AI Plugin System Tests

Test PluginInfo, BasePlugin, PluginRegistry
"""

import sys
from pathlib import Path

import pytest

# Ensure src is on path
_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ─── PluginInfo Tests ────────────────────────────────────────────────────────


class TestPluginInfo:
    """PluginInfo dataclass tests."""

    def test_create_plugin_info(self):
        from data_ai.plugins import PluginInfo

        info = PluginInfo(
            name="test_plugin",
            version="1.0.0",
            description="A test plugin",
            author="tester",
        )
        assert info.name == "test_plugin"
        assert info.version == "1.0.0"
        assert info.description == "A test plugin"
        assert info.author == "tester"
        assert info.plugin_type == "tool"
        assert info.dependencies == []

    def test_plugin_info_defaults(self):
        from data_ai.plugins import PluginInfo

        info = PluginInfo(name="minimal")
        assert info.version == "0.1.0"
        assert info.description == ""
        assert info.author == ""
        assert info.plugin_type == "tool"
        assert info.dependencies == []

    def test_plugin_info_with_dependencies(self):
        from data_ai.plugins import PluginInfo

        info = PluginInfo(
            name="dep_plugin",
            dependencies=["other_plugin", "base_lib"],
        )
        assert len(info.dependencies) == 2


# ─── BasePlugin Tests ────────────────────────────────────────────────────────


class TestBasePlugin:
    """BasePlugin ABC tests."""

    def test_cannot_instantiate_abstract(self):
        from data_ai.plugins import BasePlugin

        with pytest.raises(TypeError):
            BasePlugin()

    def test_concrete_plugin(self):
        from data_ai.plugins import BasePlugin, PluginInfo

        class MyPlugin(BasePlugin):
            info = PluginInfo(name="my_plugin", version="1.0.0")

            async def initialize(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        plugin = MyPlugin()
        assert plugin.info.name == "my_plugin"
        assert plugin.is_initialized is False

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        from data_ai.plugins import BasePlugin, PluginInfo

        class LifecyclePlugin(BasePlugin):
            info = PluginInfo(name="lifecycle_plugin")

            async def initialize(self) -> None:
                self._initialized = True

            async def cleanup(self) -> None:
                self._initialized = False

        plugin = LifecyclePlugin()
        assert plugin.is_initialized is False

        await plugin.initialize()
        assert plugin.is_initialized is True

        await plugin.cleanup()
        assert plugin.is_initialized is False


# ─── PluginRegistry Tests ────────────────────────────────────────────────────


class TestPluginRegistry:
    """PluginRegistry tests."""

    @pytest.fixture
    def registry(self):
        """Provide a fresh PluginRegistry for each test."""
        from data_ai.plugins import PluginRegistry

        reg = PluginRegistry()
        reg._plugins.clear()
        reg._plugin_classes.clear()
        yield reg
        reg._plugins.clear()
        reg._plugin_classes.clear()

    def test_register_class(self, registry):
        from data_ai.plugins import BasePlugin, PluginInfo

        class TestTool(BasePlugin):
            info = PluginInfo(name="test_tool")

            async def initialize(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        registry.register_class(TestTool)
        assert "test_tool" in registry._plugin_classes

    def test_register_instance(self, registry):
        from data_ai.plugins import BasePlugin, PluginInfo

        class TestTool(BasePlugin):
            info = PluginInfo(name="test_inst")

            async def initialize(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        plugin = TestTool()
        registry.register_instance(plugin)
        assert "test_inst" in registry._plugins

    @pytest.mark.asyncio
    async def test_create_and_initialize(self, registry):
        from data_ai.plugins import BasePlugin, PluginInfo

        class AutoPlugin(BasePlugin):
            info = PluginInfo(name="auto_plugin")

            async def initialize(self) -> None:
                self._initialized = True

            async def cleanup(self) -> None:
                pass

        registry.register_class(AutoPlugin)
        plugin = await registry.create_and_initialize("auto_plugin")
        assert plugin is not None
        assert plugin.is_initialized is True
        assert "auto_plugin" in registry._plugins

    @pytest.mark.asyncio
    async def test_create_nonexistent_plugin(self, registry):
        plugin = await registry.create_and_initialize("nonexistent")
        assert plugin is None

    def test_get_plugin(self, registry):
        from data_ai.plugins import BasePlugin, PluginInfo

        class GetTest(BasePlugin):
            info = PluginInfo(name="get_test")

            async def initialize(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        plugin = GetTest()
        registry.register_instance(plugin)
        fetched = registry.get("get_test")
        assert fetched is plugin

    def test_get_nonexistent_plugin(self, registry):
        result = registry.get("nonexistent")
        assert result is None

    def test_list_plugins(self, registry):
        from data_ai.plugins import BasePlugin, PluginInfo

        class P1(BasePlugin):
            info = PluginInfo(name="p1")

            async def initialize(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        class P2(BasePlugin):
            info = PluginInfo(name="p2")

            async def initialize(self) -> None:
                pass

            async def cleanup(self) -> None:
                pass

        registry.register_instance(P1())
        registry.register_instance(P2())
        names = registry.list_plugins()
        assert "p1" in names
        assert "p2" in names
        assert len(names) == 2

    @pytest.mark.asyncio
    async def test_cleanup_all(self, registry):
        from data_ai.plugins import BasePlugin, PluginInfo

        class CleanPlugin(BasePlugin):
            info = PluginInfo(name="clean_plugin")

            async def initialize(self) -> None:
                self._initialized = True

            async def cleanup(self) -> None:
                self._initialized = False

        plugin = CleanPlugin()
        plugin._initialized = True
        registry.register_instance(plugin)
        await registry.cleanup_all()
        assert plugin.is_initialized is False

    def test_discover_plugins_empty_dir(self, registry, tmp_path):
        discovered = registry.discover_plugins(str(tmp_path))
        assert discovered == []

    def test_discover_plugins_no_plugins(self, registry, tmp_path):
        # Create a Python file without any plugin classes
        (tmp_path / "regular.py").write_text("x = 1\n", encoding="utf-8")
        discovered = registry.discover_plugins(str(tmp_path))
        assert discovered == []
