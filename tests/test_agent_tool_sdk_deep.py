"""
DATA-AI 深度测试套件 — Agent / Tool / Session / SDK / 边界条件
"""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest


class TestAgentDeep:
    def test_agent_config_full(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(
            model_name="gpt-4o",
            system_prompt="Custom prompt",
            max_iterations=5,
            max_tool_calls=10,
            timeout=60.0,
            temperature=0.3,
            stream=False,
            enable_context_management=True,
            reserve_output_tokens=2048,
            metadata={"version": "1.0"},
        )
        assert config.max_iterations == 5
        assert config.max_tool_calls == 10
        assert config.temperature == 0.3
        assert config.stream is False
        assert config.reserve_output_tokens == 2048
        assert config.metadata["version"] == "1.0"

    def test_agent_state_initial(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState()
        assert state.status == AgentStatus.IDLE
        assert state.messages == []
        assert state.iteration_count == 0
        assert state.total_tokens == 0
        assert state.metadata == {}

    def test_agent_reset(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState()
        state.status = AgentStatus.FINISHED
        state.iteration_count = 5
        state.total_tokens = 1000
        state = AgentState()
        assert state.status == AgentStatus.IDLE
        assert state.iteration_count == 0

    def test_agent_status_all_values(self):
        from data_ai.core.agent.base import AgentStatus

        values = {s.value for s in AgentStatus}
        expected = {"idle", "thinking", "executing", "streaming", "finished", "error", "reflecting"}
        assert values == expected

    async def test_agent_event_handlers(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Test."

        agent = TestAgent()
        events = []

        def on_thinking(**kwargs):
            events.append(("thinking", kwargs))

        agent.on("on_thinking", on_thinking)
        await agent._emit("on_thinking", iteration=1)
        assert len(events) == 1
        assert events[0][0] == "thinking"
        assert events[0][1]["iteration"] == 1

    async def test_agent_event_handler_error_does_not_propagate(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Test."

        agent = TestAgent()

        def bad_handler(**kwargs):
            raise RuntimeError("Handler crash")

        agent.on("on_thinking", bad_handler)
        await agent._emit("on_thinking", iteration=1)

    async def test_agent_cleanup_resets(self):
        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Test."

        agent = TestAgent()
        agent.state.status = AgentStatus.FINISHED
        await agent.cleanup()
        assert agent.state.status == AgentStatus.IDLE

    def test_agent_default_system_prompt(self):
        # BaseAgent 自身可实例化并提供默认 system prompt；
        # 子类可重写 get_system_prompt 定制 persona。
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class PlainAgent(BaseAgent):
            pass

        cfg = AgentConfig(model_name="offline-chat")
        agent = PlainAgent(config=cfg)
        try:
            prompt = agent.get_system_prompt()
        finally:
            import asyncio

            try:
                asyncio.get_event_loop().run_until_complete(agent.cleanup())
            except Exception:
                pass
        assert "DATA-AI" in prompt or "assistant" in prompt.lower()


class TestToolRegistryDeep:
    def test_register_overwrite(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register("t", "desc1", function=lambda: 1)
        registry.register("t", "desc2", function=lambda: 2)
        assert registry.get_tool_count() == 1

    def test_unregister(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register("t", "desc", function=lambda: 1)
        assert registry.get_tool_count() == 1
        registry.unregister("t")
        assert registry.get_tool_count() == 0

    def test_unregister_nonexistent(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.unregister("ghost")

    def test_register_function_auto_name(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()

        def my_custom_tool():
            """Does something."""
            return "ok"

        registry.register_function(my_custom_tool)
        assert "my_custom_tool" in registry.list_tools()

    def test_register_function_custom_name(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()

        def foo():
            return "bar"

        registry.register_function(foo, name="custom_name", description="Custom desc")
        assert "custom_name" in registry.list_tools()

    def test_register_function_with_types(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()

        def typed_func(x: int, y: float, flag: bool = True) -> str:
            return f"{x} {y} {flag}"

        registry.register_function(typed_func)
        assert "typed_func" in registry.list_tools()

    async def test_execute_counts(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register("echo", "Echo", function=lambda msg: msg)
        await registry.execute("echo", {"msg": "a"})
        await registry.execute("echo", {"msg": "b"})
        await registry.execute("echo", {"msg": "c"})
        stats = registry.get_execution_stats()
        assert stats["echo"] == 3

    async def test_execute_sync_function(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()

        def sync_func(x: int) -> int:
            return x * 2

        registry.register_function(sync_func)
        result = await registry.execute("sync_func", {"x": 21})
        assert result == 42

    async def test_execute_async_function(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()

        async def async_func(delay: float = 0.01) -> str:
            await asyncio.sleep(delay)
            return "done"

        registry.register_function(async_func)
        result = await registry.execute("async_func", {})
        assert result == "done"

    def test_builtin_calculate_complex(self):
        import asyncio

        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        async def run():
            return await registry.execute("calculate", {"expression": "(3 + 5) * 2 ^ 3"})

        result = asyncio.run(run())
        assert "19" in str(result)

    def test_builtin_calculate_disallowed_chars(self):
        import asyncio

        from data_ai.core.tool.registry import ToolExecutionError, ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        async def run():
            with pytest.raises(ToolExecutionError):
                await registry.execute("calculate", {"expression": "__import__('os')"})

        asyncio.run(run())

    def test_builtin_read_file_nonexistent(self):
        import asyncio

        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        async def run():
            result = await registry.execute("read_file", {"path": "/nonexistent/file.txt"})
            assert "not found" in str(result).lower()

        asyncio.run(run())

    def test_builtin_write_and_read_roundtrip(self):
        import tempfile

        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        async def run():
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                path = f.name
            try:
                await registry.execute("write_file", {"path": path, "content": "Hello DATA-AI"})
                result = await registry.execute("read_file", {"path": path})
                assert "Hello DATA-AI" in str(result)
            finally:
                import os

                os.unlink(path)

        asyncio.run(run())

    def test_builtin_list_directory(self):
        import tempfile

        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        async def run():
            with tempfile.TemporaryDirectory() as tmpdir:
                result = await registry.execute("list_directory", {"path": tmpdir})
                assert isinstance(result, str)

        asyncio.run(run())

    def test_builtin_list_directory_nonexistent(self):
        import asyncio

        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        async def run():
            result = await registry.execute("list_directory", {"path": "/nonexistent_dir_xyz"})
            assert "not found" in str(result).lower()

        asyncio.run(run())

    def test_tool_schemas_format(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(
            "test_tool", "A test tool", parameters={"x": {"type": "integer", "description": "Param"}}, required=["x"]
        )
        schemas = registry.get_openai_tool_schemas()
        assert schemas[0]["function"]["parameters"]["required"] == ["x"]

    def test_tool_schemas_empty(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        assert registry.get_openai_tool_schemas() == []

    def test_clear(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register("t", "desc", function=lambda: 1)
        registry.clear()
        assert registry.get_tool_count() == 0
        assert registry.get_execution_stats() == {}


class TestSessionDeep:
    def test_session_unique_ids(self):
        from data_ai.session import Session

        s1 = Session()
        s2 = Session()
        assert s1.id != s2.id

    def test_session_message_ordering(self):
        from data_ai.session import Session

        s = Session()
        s.add_user_message("Q1")
        s.add_assistant_message("A1")
        s.add_user_message("Q2")
        s.add_assistant_message("A2")
        assert s.messages[0].content == "Q1"
        assert s.messages[3].content == "A2"

    def test_session_get_last_n(self):
        from data_ai.session import Session

        s = Session()
        for i in range(10):
            s.add_user_message(f"Msg {i}")
        last = s.get_last_n_messages(3)
        assert len(last) == 3
        assert last[-1].content == "Msg 9"

    def test_session_clear(self):
        from data_ai.session import Session

        s = Session()
        s.add_user_message("Hello")
        s.clear()
        assert len(s.messages) == 0

    def test_session_stats(self):
        from data_ai.session import Session

        s = Session(name="Stats Test")
        s.add_user_message("U1")
        s.add_user_message("U2")
        s.add_assistant_message("A1")
        stats = s.get_stats()
        assert stats["message_count"] == 3
        assert stats["role_distribution"]["user"] == 2
        assert stats["role_distribution"]["assistant"] == 1

    def test_session_manager_list(self):
        from data_ai.session import SessionManager

        mgr = SessionManager()
        mgr.create_session("S1")
        mgr.create_session("S2")
        sessions = mgr.list_sessions()
        assert len(sessions) == 2

    def test_session_manager_delete(self):
        from data_ai.session import SessionManager

        mgr = SessionManager()
        s = mgr.create_session("test")
        mgr.delete_session(s.id)
        assert mgr.get_session(s.id) is None

    def test_session_manager_set_active(self):
        from data_ai.session import SessionManager

        mgr = SessionManager()
        s1 = mgr.create_session("S1")
        s2 = mgr.create_session("S2")
        mgr.set_active_session(s1.id)
        assert mgr.get_active_session().id == s1.id
        mgr.set_active_session(s2.id)
        assert mgr.get_active_session().id == s2.id

    def test_session_manager_clear_all(self):
        from data_ai.session import SessionManager

        mgr = SessionManager()
        mgr.create_session("S1")
        mgr.create_session("S2")
        mgr.clear_all()
        assert len(mgr.list_sessions()) == 0
        assert mgr.get_active_session() is None


class TestSDKDeep:
    def test_create_client_with_custom_params(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        from data_ai.sdk import create_client

        client = create_client(
            model="gpt-4-turbo",
            provider="openai",
            api_key="sk-test",
            system_prompt="You are a test bot.",
            max_iterations=3,
            timeout=30.0,
            temperature=0.1,
        )
        assert client.model == "gpt-4-turbo"
        assert "test bot" in client.get_system_prompt()
        assert client._max_iterations == 3
        assert client._timeout == 30.0
        assert client._temperature == 0.1

    def test_client_chat_with_messages(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        from data_ai.core.llm.manager import ChatResponse
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="sk-test")

        async def run():
            with patch.object(
                client._llm_manager,
                "chat",
                new=AsyncMock(return_value=ChatResponse(content="Reply", model="gpt-4o", usage={"total_tokens": 10})),
            ):
                result = await client.chat(
                    "Hello",
                    messages=[
                        {"role": "user", "content": "Previous"},
                        {"role": "assistant", "content": "Previous reply"},
                    ],
                )
                assert result["content"] == "Reply"

        asyncio.run(run())

    def test_client_chat_stream(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        from data_ai.core.llm.manager import ChatResponse
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="sk-test")

        async def run():
            async def mock_stream(*args, **kwargs):
                yield ChatResponse(content="Hello", model="gpt-4o")
                yield ChatResponse(content=" world", model="gpt-4o")

            with patch.object(client._llm_manager, "chat_stream", new=mock_stream):
                chunks = []
                async for chunk in client.chat_stream("Hi"):
                    chunks.append(chunk["content"])
                assert "".join(chunks) == "Hello world"

        asyncio.run(run())

    def test_client_rag_config(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        from data_ai.core.rag.pipeline import InMemoryVectorStore
        from data_ai.sdk import create_client

        client = create_client(
            model="gpt-4o",
            api_key="sk-test",
            rag_config={"vector_store": InMemoryVectorStore(), "top_k": 10},
        )
        assert client.rag.top_k == 10

    def test_client_think(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        from data_ai.core.llm.manager import ChatResponse
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="sk-test")

        async def run():
            with patch.object(
                client._llm_manager,
                "chat",
                new=AsyncMock(
                    return_value=ChatResponse(
                        content="Step 1: Analysis.\nFINAL ANSWER: The result is 42.",
                        model="gpt-4o",
                    )
                ),
            ):
                chain = await client.think("What is the answer?")
                assert "42" in chain.final_answer

        asyncio.run(run())

    def test_client_async_context_manager(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"
        from data_ai.sdk import create_client

        async def run():
            async with create_client(model="gpt-4o", api_key="sk-test") as client:
                assert client is not None

        asyncio.run(run())


class TestEdgeCasesAndBoundary:
    def test_chat_message_with_name(self):
        from data_ai.core.llm.manager import ChatMessage

        msg = ChatMessage(role="user", content="Hi", name="Alice")
        assert msg.name == "Alice"

    def test_model_config_defaults(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        config = ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o")
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.context_window == 128000
        assert config.timeout == 60.0
        assert config.max_retries == 3

    def test_register_model_with_fallback_priority(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model(
            "first", ModelConfig(provider=ModelProvider.OPENAI, model_name="a", api_key="k"), fallback_priority=0
        )
        manager.register_model(
            "second", ModelConfig(provider=ModelProvider.OPENAI, model_name="b", api_key="k"), fallback_priority=1
        )
        assert manager._fallback_chain == ["first", "second"]

    def test_provider_enum_from_string(self):
        from data_ai.core.llm.manager import ModelProvider

        assert ModelProvider("openai") == ModelProvider.OPENAI
        assert ModelProvider("anthropic") == ModelProvider.ANTHROPIC
        assert ModelProvider("ollama") == ModelProvider.OLLAMA
        assert ModelProvider("deepseek") == ModelProvider.DEEPSEEK

    def test_provider_enum_invalid(self):
        from data_ai.core.llm.manager import ModelProvider

        with pytest.raises(ValueError):
            ModelProvider("invalid_provider")

    def test_empty_tool_registry_execute(self):
        import asyncio

        from data_ai.core.tool.registry import ToolExecutionError, ToolRegistry

        registry = ToolRegistry()

        async def run():
            with pytest.raises(ToolExecutionError):
                await registry.execute("nonexistent", {})

        asyncio.run(run())

    def test_memory_store_timestamp(self):
        import time

        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        before = time.time()
        entry = store.add_short_term("test")
        after = time.time()
        assert before <= entry.timestamp <= after

    def test_reasoning_chain_with_context(self):
        import asyncio

        from data_ai.core.reasoning.sequential import SequentialThinking

        async def run():
            thinker = SequentialThinking()
            chain = await thinker.think("What is AI?", context="AI stands for Artificial Intelligence.")
            assert len(chain.thoughts) > 0
            assert chain.question == "What is AI?"

        asyncio.run(run())


class TestExceptionDetails:
    def test_llm_exception_with_details(self):
        from data_ai.utils.exceptions import LLMException

        exc = LLMException(message="Error", provider="test", model="test-model", extra="data")
        assert exc.details["provider"] == "test"
        assert exc.details["model"] == "test-model"
        assert exc.details["extra"] == "data"

    def test_agent_exception_chain(self):
        from data_ai.utils.exceptions import AgentExecutionError

        ValueError("root cause")
        exc = AgentExecutionError(agent="test_agent", message="root cause")
        assert exc.details["agent"] == "test_agent"
        assert "root cause" in str(exc)

    def test_tool_execution_error(self):
        from data_ai.utils.exceptions import ToolExecutionError

        exc = ToolExecutionError(tool="calculator", message="Division by zero", exit_code=1)
        assert exc.details["tool"] == "calculator"
        assert exc.details["details"]["exit_code"] == 1

    def test_rag_exception(self):
        from data_ai.utils.exceptions import RAGConfigError, RAGIndexError

        idx_err = RAGIndexError(document_id="doc123", reason="corrupted")
        assert "doc123" in str(idx_err)
        assert "corrupted" in str(idx_err)

        cfg_err = RAGConfigError(message="Missing config")
        assert "Missing config" in str(cfg_err)

    def test_memory_exception(self):
        from data_ai.utils.exceptions import MemoryConfigError, MemoryInitError

        init_err = MemoryInitError(reason="OOM")
        assert "OOM" in str(init_err)
        cfg_err = MemoryConfigError(reason="Bad config")
        assert "Bad config" in str(cfg_err)
