"""
DATA-AI Tool Ecosystem Integration Tests (v2.0 API)

Tests the tool ecosystem integration: tools + registry + agent working together
using the new v2.0 API (ToolDefinition, ToolRegistry, BaseAgent).
"""

import asyncio
import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _run(coro):
    return asyncio.run(coro)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def clean_registry():
    from data_ai.core.tool.registry import ToolRegistry

    reg = ToolRegistry()
    yield reg
    reg.clear()


# ─── Test helpers ────────────────────────────────────────────────────────────


def _make_sync_tool(name, result, params=None, required=None):
    def fn(**kwargs):
        return result

    return {
        "name": name,
        "description": f"Sync tool {name}",
        "parameters": params or {},
        "required": required or [],
        "function": fn,
    }


async def _make_async_tool(name, result, params=None, required=None):
    async def fn(**kwargs):
        await asyncio.sleep(0)
        return result

    return {
        "name": name,
        "description": f"Async tool {name}",
        "parameters": params or {},
        "required": required or [],
        "function": fn,
    }


# ─── TestToolRegistryIntegration ─────────────────────────────────────────────


class TestToolRegistryIntegration:
    """Register tools by function, by dict, test execute, list, schema, duplicate handling."""

    # ── Register by function ──────────────────────────────────────────────

    def test_register_function_auto_schema(self, clean_registry):
        def add_numbers(a: int, b: int) -> int:
            return a + b

        clean_registry.register_function(add_numbers)

        tool = clean_registry.get("add_numbers")
        assert tool is not None
        assert tool.name == "add_numbers"
        assert tool.parameters == {
            "a": {"type": "integer", "description": "Parameter: a"},
            "b": {"type": "integer", "description": "Parameter: b"},
        }
        assert tool.required == ["a", "b"]
        assert tool.function is add_numbers
        assert tool.is_async is False

    def test_register_function_custom_name(self, clean_registry):
        def multiply(x: int, y: int) -> int:
            return x * y

        clean_registry.register_function(multiply, name="mult")

        assert clean_registry.get("mult") is not None
        assert clean_registry.get("multiply") is None

    def test_register_function_custom_description(self, clean_registry):
        def echo(text: str) -> str:
            return text

        clean_registry.register_function(echo, description="Repeat the input")

        tool = clean_registry.get("echo")
        assert tool.description == "Repeat the input"

    def test_register_function_optional_params(self, clean_registry):
        def greet(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        clean_registry.register_function(greet)

        tool = clean_registry.get("greet")
        assert tool.required == ["name"]
        assert "greeting" in tool.parameters

    def test_register_function_type_annotations(self, clean_registry):
        def process(data: list, flag: bool, count: float) -> str:
            return "done"

        clean_registry.register_function(process)

        tool = clean_registry.get("process")
        assert tool.parameters["data"]["type"] == "array"
        assert tool.parameters["flag"]["type"] == "boolean"
        assert tool.parameters["count"]["type"] == "number"

    # ── Register by dict ──────────────────────────────────────────────────

    def test_register_by_dict_explicit_schema(self, clean_registry):
        def search(query: str, limit: int = 10) -> str:
            return f"Results for: {query}"

        clean_registry.register(
            name="search",
            description="Search the knowledge base",
            parameters={
                "query": {"type": "string", "description": "Search query string"},
                "limit": {"type": "integer", "description": "Max results to return"},
            },
            required=["query"],
            function=search,
        )

        tool = clean_registry.get("search")
        assert tool is not None
        assert tool.name == "search"
        assert tool.description == "Search the knowledge base"
        assert tool.parameters["query"]["type"] == "string"
        assert tool.parameters["limit"]["type"] == "integer"
        assert tool.required == ["query"]

    def test_register_by_dict_with_metadata(self, clean_registry):
        clean_registry.register(
            name="meta_tool",
            description="Tool with extra metadata",
            parameters={"input": {"type": "string", "description": "Input value"}},
            function=lambda input: input.upper(),
            category="transform",
            risk_level="low",
            version="2.0.0",
        )

        tool = clean_registry.get("meta_tool")
        assert tool.metadata == {"category": "transform", "risk_level": "low", "version": "2.0.0"}

    def test_register_by_dict_no_function(self, clean_registry):
        clean_registry.register(
            name="schema_only",
            description="A tool definition without implementation",
            parameters={"x": {"type": "integer", "description": "A number"}},
        )

        tool = clean_registry.get("schema_only")
        assert tool is not None
        assert tool.name == "schema_only"
        assert tool.function is None

    # ── Execute through registry ──────────────────────────────────────────

    def test_execute_registered_function(self, clean_registry):
        def double(x: int) -> int:
            return x * 2

        clean_registry.register_function(double)
        result = _run(clean_registry.execute("double", {"x": 21}))
        assert result == 42

    def test_execute_async_function(self, clean_registry):
        async def fetch_data(url: str) -> str:
            await asyncio.sleep(0)
            return f"data from {url}"

        clean_registry.register_function(fetch_data)
        result = _run(clean_registry.execute("fetch_data", {"url": "/api/v1"}))
        assert result == "data from /api/v1"

    def test_execute_with_optional_params(self, clean_registry):
        def format_name(first: str, last: str = "", title: str = "") -> str:
            parts = [p for p in [title, first, last] if p]
            return " ".join(parts)

        clean_registry.register_function(format_name)
        result = _run(clean_registry.execute("format_name", {"first": "Jane"}))
        assert result == "Jane"

    # ── List tools ────────────────────────────────────────────────────────

    def test_list_tools_empty(self, clean_registry):
        assert clean_registry.list_tools() == []

    def test_list_tools_after_register(self, clean_registry):
        clean_registry.register(name="alpha", description="A", function=lambda: 1)
        clean_registry.register(name="beta", description="B", function=lambda: 2)
        clean_registry.register(name="gamma", description="C", function=lambda: 3)

        tools = clean_registry.list_tools()
        assert sorted(tools) == ["alpha", "beta", "gamma"]

    def test_get_tool_count(self, clean_registry):
        assert clean_registry.get_tool_count() == 0
        clean_registry.register(name="t1", description="", function=lambda: 1)
        assert clean_registry.get_tool_count() == 1
        clean_registry.register(name="t2", description="", function=lambda: 2)
        assert clean_registry.get_tool_count() == 2

    # ── Schema generation ─────────────────────────────────────────────────

    def test_get_openai_tool_schemas(self, clean_registry):
        clean_registry.register(
            name="get_weather",
            description="Get current weather for a city",
            parameters={
                "city": {"type": "string", "description": "City name"},
                "units": {"type": "string", "description": "Temperature unit"},
            },
            required=["city"],
            function=lambda city, units="celsius": "sunny",
        )

        schemas = clean_registry.get_openai_tool_schemas()
        assert len(schemas) == 1

        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "get_weather"
        assert schema["function"]["description"] == "Get current weather for a city"
        assert "city" in schema["function"]["parameters"]["properties"]
        assert "units" in schema["function"]["parameters"]["properties"]
        assert schema["function"]["parameters"]["required"] == ["city"]

    def test_get_openai_tool_schemas_multiple(self, clean_registry):
        clean_registry.register(name="tool_a", description="First tool", function=lambda: 1)
        clean_registry.register(name="tool_b", description="Second tool", function=lambda: 2)

        schemas = clean_registry.get_openai_tool_schemas()
        assert len(schemas) == 2
        names = [s["function"]["name"] for s in schemas]
        assert sorted(names) == ["tool_a", "tool_b"]

    # ── Duplicate handling ────────────────────────────────────────────────

    def test_duplicate_overwrites(self, clean_registry):
        clean_registry.register(name="dup", description="Original", function=lambda: 1)
        clean_registry.register(name="dup", description="Replacement", function=lambda: 2)

        tool = clean_registry.get("dup")
        assert tool.description == "Replacement"
        assert tool.function() == 2

    def test_duplicate_resets_execution_count(self, clean_registry):
        def inc(x: int) -> int:
            return x + 1

        clean_registry.register_function(inc)
        _run(clean_registry.execute("inc", {"x": 0}))
        assert clean_registry.get_execution_stats()["inc"] == 1

        clean_registry.register_function(inc)
        assert clean_registry.get_execution_stats()["inc"] == 0

    def test_duplicate_count_stays_one(self, clean_registry):
        clean_registry.register(name="only", description="First", function=lambda: 1)
        clean_registry.register(name="only", description="Second", function=lambda: 2)
        assert clean_registry.get_tool_count() == 1

    # ── Unregister ────────────────────────────────────────────────────────

    def test_unregister_removes_tool(self, clean_registry):
        clean_registry.register(name="temp", description="Temporary", function=lambda: 1)
        assert clean_registry.get("temp") is not None

        clean_registry.unregister("temp")
        assert clean_registry.get("temp") is None

    def test_unregister_clears_stats(self, clean_registry):
        def f():
            return 1

        clean_registry.register_function(f)
        _run(clean_registry.execute("f", {}))
        assert "f" in clean_registry.get_execution_stats()

        clean_registry.unregister("f")
        assert "f" not in clean_registry.get_execution_stats()

    def test_unregister_nonexistent_no_error(self, clean_registry):
        clean_registry.unregister("ghost")

    # ── Clear ─────────────────────────────────────────────────────────────

    def test_clear_empties_registry(self, clean_registry):
        clean_registry.register(name="a", description="", function=lambda: 1)
        clean_registry.register(name="b", description="", function=lambda: 2)
        assert clean_registry.get_tool_count() == 2

        clean_registry.clear()
        assert clean_registry.get_tool_count() == 0
        assert clean_registry.list_tools() == []

    # ── Execution stats ───────────────────────────────────────────────────

    def test_execution_stats_tracks_calls(self, clean_registry):
        def echo(x: str) -> str:
            return x

        clean_registry.register_function(echo)
        assert clean_registry.get_execution_stats() == {"echo": 0}

        _run(clean_registry.execute("echo", {"x": "a"}))
        _run(clean_registry.execute("echo", {"x": "b"}))
        _run(clean_registry.execute("echo", {"x": "c"}))

        assert clean_registry.get_execution_stats()["echo"] == 3


# ─── TestToolAgentIntegration ────────────────────────────────────────────────


class TestToolAgentIntegration:
    """Create agent with config, test agent + tool registry interaction."""

    @pytest.fixture
    def agent_registry(self):
        from data_ai.core.tool.registry import ToolRegistry

        reg = ToolRegistry()
        yield reg
        reg.clear()

    def test_agent_config_defaults(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig()
        assert config.model_name == "default"
        assert config.system_prompt == ""
        assert config.max_iterations == 10
        assert config.max_tool_calls == 20
        assert config.timeout == 300.0
        assert config.temperature == 0.7
        assert config.stream is True
        assert config.enable_context_management is True
        assert config.reserve_output_tokens == 4096
        assert config.metadata == {}

    def test_agent_config_custom(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(
            model_name="gpt-4",
            system_prompt="You are a helpful assistant.",
            max_iterations=5,
            max_tool_calls=10,
            timeout=60.0,
            temperature=0.3,
            stream=False,
            enable_context_management=False,
            reserve_output_tokens=2048,
            metadata={"env": "production"},
        )

        assert config.model_name == "gpt-4"
        assert config.system_prompt == "You are a helpful assistant."
        assert config.max_iterations == 5
        assert config.max_tool_calls == 10
        assert config.timeout == 60.0
        assert config.temperature == 0.3
        assert config.stream is False
        assert config.enable_context_management is False
        assert config.reserve_output_tokens == 2048
        assert config.metadata == {"env": "production"}

    def test_agent_state_defaults(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState()
        assert state.messages == []
        assert state.system_message is None
        assert state.tool_results == {}
        assert state.iteration_count == 0
        assert state.status == AgentStatus.IDLE
        assert state.total_tokens == 0
        assert state.metadata == {}

    def test_agent_state_custom(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState(
            iteration_count=5,
            status=AgentStatus.THINKING,
            total_tokens=100,
            metadata={"key": "value"},
        )
        assert state.iteration_count == 5
        assert state.status == AgentStatus.THINKING
        assert state.total_tokens == 100
        assert state.metadata == {"key": "value"}

    def test_agent_status_enum(self):
        from data_ai.core.agent.base import AgentStatus

        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.THINKING.value == "thinking"
        assert AgentStatus.EXECUTING.value == "executing"
        assert AgentStatus.STREAMING.value == "streaming"
        assert AgentStatus.FINISHED.value == "finished"
        assert AgentStatus.ERROR.value == "error"

    def test_agent_uses_tool_registry(self, agent_registry):
        from data_ai.core.agent.base import BaseAgent

        def greet(name: str) -> str:
            return f"Hello, {name}!"

        agent_registry.register_function(greet)

        class SimpleAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a simple agent."

        agent = SimpleAgent(tool_registry=agent_registry)

        assert agent.tools is agent_registry
        assert agent.tools.get("greet") is not None
        assert agent.tools.get_tool_count() == 1

    def test_agent_get_tool_schemas(self, agent_registry):
        from data_ai.core.agent.base import BaseAgent

        agent_registry.register(
            name="calc",
            description="Calculate expression",
            parameters={
                "expression": {"type": "string", "description": "Math expression"},
            },
            required=["expression"],
            function=lambda expression: eval(expression),
        )

        class CalcAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a calculator agent."

        agent = CalcAgent(tool_registry=agent_registry)
        schemas = agent._get_tool_schemas()

        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "calc"

    def test_agent_state_reset(self, agent_registry):
        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Test agent."

        agent = TestAgent(tool_registry=agent_registry)
        agent.state.iteration_count = 5
        agent.state.status = AgentStatus.THINKING
        agent.state.total_tokens = 200

        agent.reset()

        assert agent.state.iteration_count == 0
        assert agent.state.status == AgentStatus.IDLE
        assert agent.state.total_tokens == 0
        assert agent.state.messages == []

    def test_agent_system_prompt_includes_config(self, agent_registry):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class PromptAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Base prompt."

        config = AgentConfig(system_prompt="Additional instructions.")
        agent = PromptAgent(config=config, tool_registry=agent_registry)

        msg = agent._build_system_message()
        assert msg.role == "system"
        assert "Base prompt." in msg.content
        assert "Additional instructions." in msg.content

    def test_agent_event_handlers(self, agent_registry):
        from data_ai.core.agent.base import BaseAgent

        events = []

        class EventAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Event agent."

        agent = EventAgent(tool_registry=agent_registry)
        agent.on("on_thinking", lambda iteration: events.append(("thinking", iteration)))
        agent.on("on_tool_call", lambda tool_name, arguments: events.append(("tool_call", tool_name)))
        agent.on("on_tool_result", lambda tool_name, result: events.append(("tool_result", tool_name)))
        agent.on("on_finish", lambda content: events.append(("finish", content)))
        agent.on("on_error", lambda error: events.append(("error", error)))

        _run(agent._emit("on_thinking", iteration=1))
        _run(agent._emit("on_tool_call", tool_name="test", arguments={}))
        _run(agent._emit("on_tool_result", tool_name="test", result="ok"))
        _run(agent._emit("on_finish", content="done"))
        _run(agent._emit("on_error", error="fail"))

        assert events == [
            ("thinking", 1),
            ("tool_call", "test"),
            ("tool_result", "test"),
            ("finish", "done"),
            ("error", "fail"),
        ]


# ─── TestToolExecutionIntegration ────────────────────────────────────────────


class TestToolExecutionIntegration:
    """Execute tools (sync/async), error handling, missing tool, invalid args."""

    @pytest.fixture
    def exec_registry(self):
        from data_ai.core.tool.registry import ToolRegistry

        reg = ToolRegistry()
        yield reg
        reg.clear()

    # ── Sync execution ────────────────────────────────────────────────────

    def test_execute_sync_success(self, exec_registry):
        def compute(a: int, b: int) -> int:
            return a + b

        exec_registry.register_function(compute)
        result = _run(exec_registry.execute("compute", {"a": 3, "b": 4}))
        assert result == 7

    def test_execute_sync_with_kwargs(self, exec_registry):
        def build_url(base: str, path: str = "/", protocol: str = "https") -> str:
            return f"{protocol}://{base}{path}"

        exec_registry.register_function(build_url)
        result = _run(exec_registry.execute("build_url", {"base": "example.com", "path": "/api"}))
        assert result == "https://example.com/api"

    def test_execute_sync_returns_complex(self, exec_registry):
        def get_data() -> dict:
            return {"name": "test", "values": [1, 2, 3]}

        exec_registry.register_function(get_data)
        result = _run(exec_registry.execute("get_data", {}))
        assert result == {"name": "test", "values": [1, 2, 3]}

    # ── Async execution ───────────────────────────────────────────────────

    def test_execute_async_success(self, exec_registry):
        async def query_db(query: str) -> str:
            await asyncio.sleep(0)
            return f"result for: {query}"

        exec_registry.register_function(query_db)
        result = _run(exec_registry.execute("query_db", {"query": "SELECT 1"}))
        assert result == "result for: SELECT 1"

    def test_execute_async_with_defaults(self, exec_registry):
        async def fetch(url: str, method: str = "GET") -> str:
            await asyncio.sleep(0)
            return f"{method} {url}"

        exec_registry.register_function(fetch)
        result = _run(exec_registry.execute("fetch", {"url": "/api"}))
        assert result == "GET /api"

    # ── Missing tool ──────────────────────────────────────────────────────

    def test_execute_missing_tool_raises(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        with pytest.raises(ToolExecutionError) as exc_info:
            _run(exec_registry.execute("nonexistent_tool", {}))
        assert "not found" in str(exc_info.value).lower()

    def test_execute_missing_tool_error_code(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        with pytest.raises(ToolExecutionError) as exc_info:
            _run(exec_registry.execute("ghost", {"x": 1}))
        assert exc_info.value.code.value == "4002"

    # ── No function implementation ────────────────────────────────────────

    def test_execute_no_function_raises(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        exec_registry.register(
            name="schema_only",
            description="Has schema but no function",
            parameters={"x": {"type": "integer"}},
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            _run(exec_registry.execute("schema_only", {"x": 1}))
        assert "no function" in str(exc_info.value).lower()

    # ── Invalid arguments ─────────────────────────────────────────────────

    def test_execute_invalid_args_raises(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        def require_str(text: str) -> str:
            return text.upper()

        exec_registry.register_function(require_str)

        with pytest.raises(ToolExecutionError) as exc_info:
            _run(exec_registry.execute("require_str", {"text": 123}))
        assert "execution failed" in str(exc_info.value).lower()

    def test_execute_missing_required_arg(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        def require_two(a: str, b: str) -> str:
            return a + b

        exec_registry.register_function(require_two)

        with pytest.raises(ToolExecutionError) as exc_info:
            _run(exec_registry.execute("require_two", {"a": "hello"}))
        assert "missing" in str(exc_info.value).lower()

    def test_execute_extra_kwargs_ok(self, exec_registry):
        def simple(x: int, **kwargs) -> int:
            return x

        exec_registry.register_function(simple)
        result = _run(exec_registry.execute("simple", {"x": 5, "extra": "ignored"}))
        assert result == 5

    # ── Error propagation ─────────────────────────────────────────────────

    def test_execute_runtime_error_wraps(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        def failing_tool():
            raise ValueError("Something went wrong")

        exec_registry.register_function(failing_tool)

        with pytest.raises(ToolExecutionError) as exc_info:
            _run(exec_registry.execute("failing_tool", {}))
        assert "Something went wrong" in str(exc_info.value)

    def test_execute_tool_execution_error_not_rewrapped(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        def raise_tool_error():
            raise ToolExecutionError(tool="inner", message="direct error")

        exec_registry.register_function(raise_tool_error)

        with pytest.raises(ToolExecutionError) as exc_info:
            _run(exec_registry.execute("raise_tool_error", {}))
        assert "direct error" in str(exc_info.value)

    # ── Execution stats ───────────────────────────────────────────────────

    def test_execution_stats_after_success(self, exec_registry):
        def ok():
            return True

        exec_registry.register_function(ok)
        assert exec_registry.get_execution_stats() == {"ok": 0}

        _run(exec_registry.execute("ok", {}))
        assert exec_registry.get_execution_stats()["ok"] == 1

    def test_execution_stats_not_updated_on_error(self, exec_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        def fail():
            raise ValueError("boom")

        exec_registry.register_function(fail)
        assert exec_registry.get_execution_stats() == {"fail": 0}

        with pytest.raises(ToolExecutionError):
            _run(exec_registry.execute("fail", {}))
        assert exec_registry.get_execution_stats()["fail"] == 0

    # ── Multiple tools ────────────────────────────────────────────────────

    def test_execute_multiple_tools(self, exec_registry):
        def tool_a(x: int) -> int:
            return x * 2

        def tool_b(x: int) -> int:
            return x + 10

        exec_registry.register_function(tool_a)
        exec_registry.register_function(tool_b)

        a_result = _run(exec_registry.execute("tool_a", {"x": 5}))
        b_result = _run(exec_registry.execute("tool_b", {"x": 5}))

        assert a_result == 10
        assert b_result == 15
        assert exec_registry.get_execution_stats() == {"tool_a": 1, "tool_b": 1}


# ─── TestToolSchemaIntegration ───────────────────────────────────────────────


class TestToolSchemaIntegration:
    """Test OpenAI schema generation, tool schema formats."""

    @pytest.fixture
    def schema_registry(self):
        from data_ai.core.tool.registry import ToolRegistry

        reg = ToolRegistry()
        yield reg
        reg.clear()

    # ── ToolDefinition.to_openai_tool ─────────────────────────────────────

    def test_tool_definition_to_openai_basic(self):
        from data_ai.core.tool.registry import ToolDefinition

        td = ToolDefinition(name="my_tool", description="A test tool")
        schema = td.to_openai_tool()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "my_tool"
        assert schema["function"]["description"] == "A test tool"
        assert schema["function"]["parameters"]["type"] == "object"
        assert "properties" in schema["function"]["parameters"]
        assert schema["function"]["parameters"]["required"] == []

    def test_tool_definition_to_openai_with_params(self):
        from data_ai.core.tool.registry import ToolDefinition

        td = ToolDefinition(
            name="search",
            description="Search documents",
            parameters={
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
                "fuzzy": {"type": "boolean", "description": "Enable fuzzy matching"},
            },
            required=["query"],
        )
        schema = td.to_openai_tool()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert schema["function"]["parameters"]["type"] == "object"
        assert schema["function"]["parameters"]["required"] == ["query"]

        props = schema["function"]["parameters"]["properties"]
        assert props["query"]["type"] == "string"
        assert props["limit"]["type"] == "integer"
        assert props["fuzzy"]["type"] == "boolean"

    def test_tool_definition_to_openai_no_required(self):
        from data_ai.core.tool.registry import ToolDefinition

        td = ToolDefinition(
            name="optional_tool",
            description="All params optional",
            parameters={
                "a": {"type": "string", "description": "Optional A"},
                "b": {"type": "integer", "description": "Optional B"},
            },
        )
        schema = td.to_openai_tool()
        assert schema["function"]["parameters"]["required"] == []

    def test_tool_definition_to_openai_all_required(self):
        from data_ai.core.tool.registry import ToolDefinition

        td = ToolDefinition(
            name="required_tool",
            description="All params required",
            parameters={
                "x": {"type": "number", "description": "X coordinate"},
                "y": {"type": "number", "description": "Y coordinate"},
            },
            required=["x", "y"],
        )
        schema = td.to_openai_tool()
        assert schema["function"]["parameters"]["required"] == ["x", "y"]

    # ── Registry get_openai_tool_schemas ──────────────────────────────────

    def test_registry_openai_schemas_empty(self, schema_registry):
        schemas = schema_registry.get_openai_tool_schemas()
        assert schemas == []

    def test_registry_openai_schemas_single(self, schema_registry):
        schema_registry.register(
            name="get_time",
            description="Get current time",
            parameters={
                "timezone": {"type": "string", "description": "Timezone name"},
            },
            function=lambda timezone: "now",
        )

        schemas = schema_registry.get_openai_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "get_time"

    def test_registry_openai_schemas_multiple(self, schema_registry):
        schema_registry.register(name="t1", description="Tool 1", function=lambda: 1)
        schema_registry.register(
            name="t2",
            description="Tool 2",
            parameters={"param": {"type": "string", "description": "Param"}},
            required=["param"],
            function=lambda param: param,
        )

        schemas = schema_registry.get_openai_tool_schemas()
        assert len(schemas) == 2

        names = [s["function"]["name"] for s in schemas]
        assert "t1" in names
        assert "t2" in names

    # ── Schema format compliance ──────────────────────────────────────────

    def test_schema_has_function_type(self, schema_registry):
        schema_registry.register(name="test", description="desc", function=lambda: 1)
        schemas = schema_registry.get_openai_tool_schemas()

        for s in schemas:
            assert s["type"] == "function"
            assert "function" in s

    def test_schema_function_has_required_fields(self, schema_registry):
        schema_registry.register(
            name="weather",
            description="Get weather",
            parameters={
                "city": {"type": "string", "description": "City name"},
            },
            required=["city"],
            function=lambda city: "sunny",
        )

        schemas = schema_registry.get_openai_tool_schemas()
        schema = schemas[0]["function"]

        assert "name" in schema
        assert "description" in schema
        assert "parameters" in schema
        assert "type" in schema["parameters"]
        assert "properties" in schema["parameters"]
        assert "required" in schema["parameters"]

    def test_schema_properties_have_type(self, schema_registry):
        schema_registry.register(
            name="complex",
            description="Complex tool",
            parameters={
                "text": {"type": "string", "description": "Text input"},
                "count": {"type": "integer", "description": "Count"},
                "ratio": {"type": "number", "description": "Ratio"},
                "flag": {"type": "boolean", "description": "Flag"},
                "items": {"type": "array", "description": "Items list"},
            },
            function=lambda **kwargs: "ok",
        )

        schemas = schema_registry.get_openai_tool_schemas()
        props = schemas[0]["function"]["parameters"]["properties"]

        assert props["text"]["type"] == "string"
        assert props["count"]["type"] == "integer"
        assert props["ratio"]["type"] == "number"
        assert props["flag"]["type"] == "boolean"
        assert props["items"]["type"] == "array"

    def test_schema_enums_in_parameters(self, schema_registry):
        schema_registry.register(
            name="sort",
            description="Sort data",
            parameters={
                "field": {"type": "string", "description": "Field to sort by"},
                "order": {
                    "type": "string",
                    "description": "Sort order",
                    "enum": ["asc", "desc"],
                },
            },
            required=["field"],
            function=lambda field, order="asc": "sorted",
        )

        schemas = schema_registry.get_openai_tool_schemas()
        props = schemas[0]["function"]["parameters"]["properties"]

        assert props["order"]["enum"] == ["asc", "desc"]

    # ── Schema from register_function ─────────────────────────────────────

    def test_schema_from_register_function(self, schema_registry):
        def analyze(text: str, depth: int = 1) -> dict:
            return {"text": text, "depth": depth}

        schema_registry.register_function(analyze)
        schemas = schema_registry.get_openai_tool_schemas()

        assert len(schemas) == 1
        schema = schemas[0]

        assert schema["function"]["name"] == "analyze"
        assert schema["function"]["parameters"]["required"] == ["text"]

        props = schema["function"]["parameters"]["properties"]
        assert props["text"]["type"] == "string"
        assert props["depth"]["type"] == "integer"

    def test_schema_from_register_function_async(self, schema_registry):
        async def stream(data: str) -> str:
            await asyncio.sleep(0)
            return data

        schema_registry.register_function(stream)
        schemas = schema_registry.get_openai_tool_schemas()

        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "stream"

    # ── Builtin tools schema ──────────────────────────────────────────────

    def test_builtin_tools_schemas(self, schema_registry):
        schema_registry.register_builtin_tools()
        schemas = schema_registry.get_openai_tool_schemas()

        assert len(schemas) == 5
        names = [s["function"]["name"] for s in schemas]
        expected = ["get_current_time", "calculate", "read_file", "write_file", "list_directory"]
        for name in expected:
            assert name in names

    def test_builtin_calculate_schema(self, schema_registry):
        schema_registry.register_builtin_tools()
        schemas = schema_registry.get_openai_tool_schemas()

        calc_schema = None
        for s in schemas:
            if s["function"]["name"] == "calculate":
                calc_schema = s
                break

        assert calc_schema is not None
        assert "expression" in calc_schema["function"]["parameters"]["properties"]
        assert "expression" in calc_schema["function"]["parameters"]["required"]

    def test_builtin_read_file_schema(self, schema_registry):
        schema_registry.register_builtin_tools()
        schemas = schema_registry.get_openai_tool_schemas()

        read_schema = None
        for s in schemas:
            if s["function"]["name"] == "read_file":
                read_schema = s
                break

        assert read_schema is not None
        assert "path" in read_schema["function"]["parameters"]["properties"]
        assert "path" in read_schema["function"]["parameters"]["required"]

    # ── Schema immutability ───────────────────────────────────────────────

    def test_schema_not_affected_by_later_registrations(self, schema_registry):
        schema_registry.register(name="first", description="First", function=lambda: 1)
        schemas_before = schema_registry.get_openai_tool_schemas()

        schema_registry.register(name="second", description="Second", function=lambda: 2)
        schemas_after = schema_registry.get_openai_tool_schemas()

        assert len(schemas_before) == 1
        assert len(schemas_after) == 2

    def test_schema_updates_after_unregister(self, schema_registry):
        schema_registry.register(name="a", description="A", function=lambda: 1)
        schema_registry.register(name="b", description="B", function=lambda: 2)

        assert len(schema_registry.get_openai_tool_schemas()) == 2

        schema_registry.unregister("a")
        assert len(schema_registry.get_openai_tool_schemas()) == 1
        assert schema_registry.get_openai_tool_schemas()[0]["function"]["name"] == "b"
