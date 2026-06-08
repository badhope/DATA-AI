"""
DATA-AI ToolRegistry v2.0 Tests

Test the new ToolRegistry API:
- register_function with auto-generated schemas
- register from dict definitions
- get, list_tools, get_openai_tool_schemas
- execute (sync and async)
- clear and copy
- builtin tools count and names
- duplicate registration handling
- ToolDefinition structure
"""

import asyncio
import copy
import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def registry():
    from data_ai.core.tool.registry import ToolRegistry

    reg = ToolRegistry()
    yield reg
    reg.clear()


# ─── Helper for running async tests ──────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


# ─── Test register_function with auto-generated schemas ─────────────────────


def add(a: int, b: int) -> int:
    return a + b


def greet(name: str, greeting: str = "Hello") -> str:
    return f"{greeting}, {name}!"


def concat(items: list, sep: str = ", ") -> str:
    return sep.join(str(x) for x in items)


class TestRegisterFunction:
    """Test register_function auto-generates schemas from signatures."""

    def test_register_simple_function(self, registry):
        registry.register_function(add)

        tool = registry.get("add")
        assert tool is not None
        assert tool.name == "add"
        assert tool.description == "Execute add"
        assert tool.parameters == {
            "a": {"type": "integer", "description": "Parameter: a"},
            "b": {"type": "integer", "description": "Parameter: b"},
        }
        assert tool.required == ["a", "b"]
        assert tool.is_async is False
        assert tool.function is add

    def test_register_with_custom_name(self, registry):
        registry.register_function(add, name="my_add")

        assert registry.get("my_add") is not None
        assert registry.get("add") is None

    def test_register_with_custom_description(self, registry):
        registry.register_function(add, description="Add two integers together")

        tool = registry.get("add")
        assert tool.description == "Add two integers together"

    def test_register_with_optional_params(self, registry):
        registry.register_function(greet)

        tool = registry.get("greet")
        assert tool.parameters == {
            "name": {"type": "string", "description": "Parameter: name"},
            "greeting": {"type": "string", "description": "Parameter: greeting"},
        }
        assert tool.required == ["name"]

    def test_register_list_annotation(self, registry):
        registry.register_function(concat)

        tool = registry.get("concat")
        assert tool.parameters["items"]["type"] == "array"
        assert tool.parameters["sep"]["type"] == "string"


# ─── Test register from dict definitions ────────────────────────────────────


class TestRegisterFromDict:
    """Test explicit register() method with manual parameter schemas."""

    def test_register_with_explicit_schema(self, registry):
        def echo(text: str) -> str:
            return text

        registry.register(
            name="echo",
            description="Echo back the input text",
            parameters={
                "text": {"type": "string", "description": "Text to echo back"},
            },
            required=["text"],
            function=echo,
        )

        tool = registry.get("echo")
        assert tool is not None
        assert tool.name == "echo"
        assert tool.description == "Echo back the input text"
        assert tool.parameters["text"]["type"] == "string"
        assert tool.required == ["text"]

    def test_register_with_metadata_kwargs(self, registry):
        registry.register(
            name="meta_tool",
            description="A tool with metadata",
            parameters={"x": {"type": "integer", "description": "Value"}},
            function=lambda x: x * 2,
            category="math",
            risk="low",
            version="1.0",
        )

        tool = registry.get("meta_tool")
        assert tool.name == "meta_tool"
        assert tool.metadata == {"category": "math", "risk": "low", "version": "1.0"}


# ─── Test get, list_tools, get_openai_tool_schemas ──────────────────────────


class TestQuery:
    """Test query methods: get, list_tools, get_openai_tool_schemas."""

    def test_get_existing_tool(self, registry):
        registry.register(name="t1", description="desc", parameters={}, function=lambda: 1)
        assert registry.get("t1") is not None

    def test_get_missing_tool(self, registry):
        assert registry.get("nonexistent") is None

    def test_list_tools_empty(self, registry):
        assert registry.list_tools() == []

    def test_list_tools_nonempty(self, registry):
        registry.register(name="a", description="", function=lambda: 1)
        registry.register(name="b", description="", function=lambda: 2)
        assert sorted(registry.list_tools()) == ["a", "b"]

    def test_get_tool_count(self, registry):
        assert registry.get_tool_count() == 0
        registry.register(name="t1", description="", function=lambda: 1)
        assert registry.get_tool_count() == 1
        registry.register(name="t2", description="", function=lambda: 2)
        assert registry.get_tool_count() == 2

    def test_get_openai_tool_schemas(self, registry):
        registry.register(
            name="my_func",
            description="Do something",
            parameters={
                "input": {"type": "string", "description": "The input"},
            },
            required=["input"],
            function=lambda input: input,
        )

        schemas = registry.get_openai_tool_schemas()
        assert len(schemas) == 1

        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "my_func"
        assert schema["function"]["description"] == "Do something"
        assert "input" in schema["function"]["parameters"]["properties"]
        assert "input" in schema["function"]["parameters"]["required"]


# ─── Test execute (sync and async) ──────────────────────────────────────────


def sync_tool(x: int) -> str:
    return str(x * 2)


async def async_tool(x: int) -> str:
    await asyncio.sleep(0)
    return str(x * 3)


class TestExecute:
    """Test execute for both sync and async functions."""

    def test_execute_sync_function(self, registry):
        registry.register_function(sync_tool)
        result = _run(registry.execute("sync_tool", {"x": 5}))
        assert result == "10"
        stats = registry.get_execution_stats()
        assert stats["sync_tool"] == 1

    def test_execute_async_function(self, registry):
        registry.register_function(async_tool)
        result = _run(registry.execute("async_tool", {"x": 7}))
        assert result == "21"

    def test_execute_unknown_tool(self, registry):
        from data_ai.utils.exceptions import ToolExecutionError

        with pytest.raises(ToolExecutionError):
            _run(registry.execute("ghost", {}))

    def test_execute_no_function(self, registry):
        from data_ai.utils.exceptions import ToolExecutionError

        registry.register(name="noop", description="does nothing")
        with pytest.raises(ToolExecutionError):
            _run(registry.execute("noop", {}))

    def test_execution_stats_accumulate(self, registry):
        registry.register_function(sync_tool)
        _run(registry.execute("sync_tool", {"x": 1}))
        _run(registry.execute("sync_tool", {"x": 2}))
        stats = registry.get_execution_stats()
        assert stats["sync_tool"] == 2


# ─── Test clear and copy ────────────────────────────────────────────────────


class TestClearAndCopy:
    """Test clear() and copy semantics."""

    def test_clear_empties_registry(self, registry):
        registry.register(name="t1", description="", function=lambda: 1)
        registry.register(name="t2", description="", function=lambda: 2)
        assert registry.get_tool_count() == 2

        registry.clear()
        assert registry.get_tool_count() == 0
        assert registry.list_tools() == []

    def test_clear_resets_execution_stats(self, registry):
        registry.register_function(sync_tool)
        _run(registry.execute("sync_tool", {"x": 1}))
        assert registry.get_execution_stats()["sync_tool"] == 1

        registry.clear()
        assert registry.get_execution_stats() == {}

    def test_deep_copy_independent(self, registry):
        registry.register(name="orig", description="d", function=lambda: 1)
        cloned = copy.deepcopy(registry)

        registry.clear()
        assert registry.get_tool_count() == 0

        assert cloned.get_tool_count() == 1
        assert cloned.get("orig") is not None

    def test_deep_copy_mutation_isolation(self, registry):
        registry.register(name="orig", description="d", function=lambda: 1)
        cloned = copy.deepcopy(registry)

        cloned.register(name="extra", description="e", function=lambda: 2)

        assert registry.get_tool_count() == 1
        assert cloned.get_tool_count() == 2
        assert registry.get("extra") is None
        assert cloned.get("extra") is not None


# ─── Test builtin tools count and names ─────────────────────────────────────


class TestBuiltinTools:
    """Test register_builtin_tools."""

    BUILTIN_NAMES = [
        "get_current_time",
        "calculate",
        "read_file",
        "write_file",
        "list_directory",
    ]

    def test_count(self, registry):
        registry.register_builtin_tools()
        assert registry.get_tool_count() == 5

    def test_names(self, registry):
        registry.register_builtin_tools()
        names = registry.list_tools()
        for expected in self.BUILTIN_NAMES:
            assert expected in names, f"Missing builtin: {expected}"

    def test_each_has_function(self, registry):
        registry.register_builtin_tools()
        for name in self.BUILTIN_NAMES:
            tool = registry.get(name)
            assert tool is not None
            assert tool.function is not None, f"Builtin {name} has no function"
            assert callable(tool.function), f"Builtin {name} function is not callable"

    def test_calculate_execute(self, registry):
        registry.register_builtin_tools()
        result = _run(registry.execute("calculate", {"expression": "2 + 3 * 4"}))
        assert "14" in result

    def test_calculate_rejects_unsafe(self, registry):
        registry.register_builtin_tools()
        from data_ai.utils.exceptions import ToolExecutionError

        with pytest.raises(ToolExecutionError):
            _run(registry.execute("calculate", {"expression": "__import__('os')"}))

    def test_get_current_time_execute(self, registry):
        registry.register_builtin_tools()
        result = _run(registry.execute("get_current_time", {}))
        assert "T" in result

    def test_openai_schemas(self, registry):
        registry.register_builtin_tools()
        schemas = registry.get_openai_tool_schemas()
        assert len(schemas) == 5
        names = [s["function"]["name"] for s in schemas]
        for expected in self.BUILTIN_NAMES:
            assert expected in names


# ─── Test duplicate registration handling ───────────────────────────────────


class TestDuplicateRegistration:
    """Test behavior when registering a tool name that already exists."""

    def test_overwrite_is_allowed(self, registry):
        registry.register(name="dup", description="first", function=lambda: 1)
        registry.register(name="dup", description="second", function=lambda: 2)
        tool = registry.get("dup")
        assert tool.description == "second"
        assert tool.function() == 2

    def test_overwrite_resets_execution_count(self, registry):
        registry.register_function(sync_tool)
        _run(registry.execute("sync_tool", {"x": 1}))
        assert registry.get_execution_stats()["sync_tool"] == 1

        registry.register_function(sync_tool)
        assert registry.get_execution_stats()["sync_tool"] == 0


# ─── Test ToolDefinition structure ──────────────────────────────────────────


class TestToolDefinitionStructure:
    """Test ToolDefinition dataclass fields and to_openai_tool."""

    def test_default_values(self):
        from data_ai.core.tool.registry import ToolDefinition

        td = ToolDefinition(name="test", description="a test")
        assert td.name == "test"
        assert td.description == "a test"
        assert td.parameters == {"type": "object", "properties": {}}
        assert td.required == []
        assert td.function is None
        assert td.is_async is False
        assert td.metadata == {}

    def test_full_construction(self):
        from data_ai.core.tool.registry import ToolDefinition

        def my_func(x):
            return x

        td = ToolDefinition(
            name="full",
            description="Full tool",
            parameters={"x": {"type": "integer", "description": "Value"}},
            required=["x"],
            function=my_func,
            is_async=False,
            metadata={"tag": "demo"},
        )

        assert td.name == "full"
        assert td.parameters["x"]["type"] == "integer"
        assert td.required == ["x"]
        assert td.function is my_func
        assert td.is_async is False
        assert td.metadata == {"tag": "demo"}

    def test_to_openai_tool(self):
        from data_ai.core.tool.registry import ToolDefinition

        td = ToolDefinition(
            name="my_tool",
            description="Test tool",
            parameters={
                "input": {"type": "string", "description": "Input value"},
                "count": {"type": "integer", "description": "Count"},
            },
            required=["input"],
        )

        schema = td.to_openai_tool()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "my_tool"
        assert schema["function"]["description"] == "Test tool"
        assert schema["function"]["parameters"]["type"] == "object"
        assert "input" in schema["function"]["parameters"]["properties"]
        assert "count" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["input"]

    def test_to_openai_tool_empty_params(self):
        from data_ai.core.tool.registry import ToolDefinition

        td = ToolDefinition(name="empty", description="No params")
        schema = td.to_openai_tool()

        assert schema["function"]["parameters"]["type"] == "object"
        assert "properties" in schema["function"]["parameters"]
        assert schema["function"]["parameters"]["required"] == []

    def test_register_sets_is_async(self, registry):
        registry.register_function(async_tool)

        tool = registry.get("async_tool")
        assert tool.is_async is True

    def test_register_sets_is_sync(self, registry):
        registry.register_function(sync_tool)

        tool = registry.get("sync_tool")
        assert tool.is_async is False


# ─── Test module-level register_tool helper ─────────────────────────────────


class TestModuleLevelRegister:
    """Test the module-level register_tool function."""

    def test_register_tool_global(self, registry):
        from data_ai.core.tool.registry import register_tool

        register_tool(
            name="global_tool",
            description="Registered globally",
            parameters={"x": {"type": "integer", "description": "Value"}},
            function=lambda x: x,
        )

        from data_ai.core.tool.registry import get_tool_registry

        global_reg = get_tool_registry()
        tool = global_reg.get("global_tool")
        assert tool is not None
        assert tool.name == "global_tool"

        global_reg.unregister("global_tool")


# ─── Test unregister ────────────────────────────────────────────────────────


class TestUnregister:
    """Test unregister method."""

    def test_unregister_removes_tool(self, registry):
        registry.register(name="rm_me", description="", function=lambda: 1)
        assert registry.get("rm_me") is not None

        registry.unregister("rm_me")
        assert registry.get("rm_me") is None

    def test_unregister_clears_stats(self, registry):
        registry.register_function(sync_tool)
        _run(registry.execute("sync_tool", {"x": 1}))
        assert "sync_tool" in registry.get_execution_stats()

        registry.unregister("sync_tool")
        assert "sync_tool" not in registry.get_execution_stats()

    def test_unregister_nonexistent_no_error(self, registry):
        registry.unregister("ghost")
