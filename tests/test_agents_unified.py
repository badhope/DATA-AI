"""
DATA-AI Agent System Tests (v2.0 API)

Test BaseAgent, AgentConfig, AgentState, AgentStatus, event callbacks,
async context manager, and concrete subclass implementation.
"""

import sys
from pathlib import Path

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


# ─── AgentConfig Tests ───────────────────────────────────────────────────────


class TestAgentConfig:
    """AgentConfig dataclass tests."""

    def test_default_values(self):
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

    def test_custom_values(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(
            model_name="gpt-4",
            system_prompt="Be concise.",
            max_iterations=5,
            max_tool_calls=10,
            timeout=120.0,
            temperature=0.3,
            stream=False,
            enable_context_management=False,
            reserve_output_tokens=2048,
            metadata={"project": "test"},
        )
        assert config.model_name == "gpt-4"
        assert config.system_prompt == "Be concise."
        assert config.max_iterations == 5
        assert config.max_tool_calls == 10
        assert config.timeout == 120.0
        assert config.temperature == 0.3
        assert config.stream is False
        assert config.enable_context_management is False
        assert config.reserve_output_tokens == 2048
        assert config.metadata == {"project": "test"}

    def test_partial_custom_values(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(model_name="claude-3", temperature=0.0)
        assert config.model_name == "claude-3"
        assert config.temperature == 0.0
        assert config.max_iterations == 10
        assert config.timeout == 300.0

    def test_max_iterations_boundary(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(max_iterations=1)
        assert config.max_iterations == 1

        config = AgentConfig(max_iterations=1000)
        assert config.max_iterations == 1000

    def test_metadata_is_independent(self):
        from data_ai.core.agent.base import AgentConfig

        config1 = AgentConfig(metadata={"a": 1})
        config2 = AgentConfig(metadata={"b": 2})
        assert config1.metadata == {"a": 1}
        assert config2.metadata == {"b": 2}
        assert config1.metadata is not config2.metadata


# ─── AgentStatus Tests ───────────────────────────────────────────────────────


class TestAgentStatus:
    """AgentStatus enum tests."""

    def test_all_status_values(self):
        from data_ai.core.agent.base import AgentStatus

        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.THINKING.value == "thinking"
        assert AgentStatus.EXECUTING.value == "executing"
        assert AgentStatus.STREAMING.value == "streaming"
        assert AgentStatus.FINISHED.value == "finished"
        assert AgentStatus.ERROR.value == "error"

    def test_status_count(self):
        from data_ai.core.agent.base import AgentStatus

        assert len(AgentStatus) == 7

    def test_status_membership(self):
        from data_ai.core.agent.base import AgentStatus

        assert AgentStatus.IDLE in AgentStatus
        assert AgentStatus.THINKING in AgentStatus
        assert AgentStatus.FINISHED in AgentStatus
        assert AgentStatus.ERROR in AgentStatus
        assert AgentStatus.REFLECTING in AgentStatus

    def test_status_comparison(self):
        from data_ai.core.agent.base import AgentStatus

        idle1 = AgentStatus.IDLE
        idle2 = AgentStatus.IDLE
        assert idle1 == idle2
        assert AgentStatus.IDLE != AgentStatus.FINISHED


# ─── AgentState Tests ────────────────────────────────────────────────────────


class TestAgentState:
    """AgentState dataclass tests."""

    def test_default_initialization(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState()
        assert state.messages == []
        assert state.system_message is None
        assert state.tool_results == {}
        assert state.iteration_count == 0
        assert state.status == AgentStatus.IDLE
        assert state.total_tokens == 0
        assert state.metadata == {}

    def test_custom_initialization(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState(
            status=AgentStatus.THINKING,
            iteration_count=3,
            total_tokens=1500,
            metadata={"session": "abc"},
        )
        assert state.status == AgentStatus.THINKING
        assert state.iteration_count == 3
        assert state.total_tokens == 1500
        assert state.metadata == {"session": "abc"}

    def test_mutable_fields_independent(self):
        from data_ai.core.agent.base import AgentState

        state1 = AgentState()
        state2 = AgentState()
        state1.messages.append("msg1")
        state1.tool_results["key"] = "val"
        assert len(state2.messages) == 0
        assert state2.tool_results == {}

    def test_status_transitions(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState()
        assert state.status == AgentStatus.IDLE

        state.status = AgentStatus.THINKING
        assert state.status == AgentStatus.THINKING

        state.status = AgentStatus.FINISHED
        assert state.status == AgentStatus.FINISHED

        state.status = AgentStatus.ERROR
        assert state.status == AgentStatus.ERROR


# ─── BaseAgent Tests ─────────────────────────────────────────────────────────


class TestBaseAgentConstruction:
    """BaseAgent construction tests."""

    def test_default_construction(self):
        from data_ai.core.agent.base import AgentConfig, AgentState, AgentStatus, BaseAgent

        class SimpleAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are helpful."

        agent = SimpleAgent()
        assert isinstance(agent.config, AgentConfig)
        assert isinstance(agent.state, AgentState)
        assert agent.state.status == AgentStatus.IDLE
        assert agent.config.model_name == "default"

    def test_custom_config_construction(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class SimpleAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are helpful."

        config = AgentConfig(
            model_name="gpt-4",
            max_iterations=5,
            temperature=0.3,
        )
        agent = SimpleAgent(config=config)
        assert agent.config.model_name == "gpt-4"
        assert agent.config.max_iterations == 5
        assert agent.config.temperature == 0.3

    def test_get_system_prompt_has_default(self):
        # BaseAgent 现在有默认 system prompt，可独立实例化。
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        config = AgentConfig(model_name="offline-chat")
        agent = BaseAgent(config=config)
        prompt = agent.get_system_prompt()
        assert isinstance(prompt, str) and prompt

    def test_subclass_can_override_system_prompt(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class CustomAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "CUSTOM_PERSONA_TOKEN"

        config = AgentConfig(model_name="offline-chat")
        agent = CustomAgent(config=config)
        assert agent.get_system_prompt() == "CUSTOM_PERSONA_TOKEN"

    def test_config_is_owned_by_agent(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class SimpleAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are helpful."

        config = AgentConfig(model_name="shared")
        agent1 = SimpleAgent(config=config)
        agent2 = SimpleAgent(config=config)
        assert agent1.config is agent2.config
        agent1.config = AgentConfig(model_name="unique")
        assert agent1.config is not agent2.config


class TestBaseAgentSubclass:
    """Concrete agent subclass implementation tests."""

    def test_subclass_system_prompt(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        assert agent.get_system_prompt() == "You are a helpful test agent."

    def test_subclass_custom_prompt(self):
        from data_ai.core.agent.base import BaseAgent

        class CodeReviewAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a code review expert. Find bugs and suggest improvements."

        agent = CodeReviewAgent()
        prompt = agent.get_system_prompt()
        assert "code review" in prompt.lower()
        assert "bugs" in prompt.lower()

    def test_subclass_with_custom_config(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        config = AgentConfig(
            model_name="claude-3-opus",
            system_prompt="Always respond in JSON.",
            max_iterations=3,
            temperature=0.0,
        )
        agent = TestAgent(config=config)
        assert agent.config.model_name == "claude-3-opus"
        assert agent.config.system_prompt == "Always respond in JSON."
        assert agent.config.max_iterations == 3

    def test_build_system_message(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Base system prompt."

        config = AgentConfig(system_prompt="Additional instructions.")
        agent = TestAgent(config=config)
        msg = agent._build_system_message()
        assert msg.role == "system"
        assert "Base system prompt." in msg.content
        assert "Additional instructions." in msg.content

    def test_build_system_message_no_config_prompt(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Only base prompt."

        agent = TestAgent()
        msg = agent._build_system_message()
        assert msg.role == "system"
        assert msg.content == "Only base prompt."

    def test_reset_clears_state(self):
        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        agent.state.status = AgentStatus.FINISHED
        agent.state.iteration_count = 5
        agent.state.total_tokens = 1000

        agent.reset()
        assert agent.state.status == AgentStatus.IDLE
        assert agent.state.iteration_count == 0
        assert agent.state.total_tokens == 0

    def test_get_initial_state(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        state = agent.get_state()
        assert state is agent.state

    def test_get_empty_messages_initially(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        assert agent.get_messages() == []

    def test_get_empty_tool_results_initially(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        assert agent.get_tool_results() == {}


# ─── Agent Event Callbacks Tests ─────────────────────────────────────────────


class TestAgentEventCallbacks:
    """Agent event callback tests."""

    def test_on_event_registration(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        handler_called = []

        def on_thinking_handler(**kwargs):
            handler_called.append(("thinking", kwargs))

        agent.on("on_thinking", on_thinking_handler)
        assert len(agent._event_handlers["on_thinking"]) == 1

    def test_emit_calls_registered_handler(self):
        import asyncio

        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        handler_called = []

        def on_finish_handler(**kwargs):
            handler_called.append(kwargs)

        agent.on("on_finish", on_finish_handler)

        async def run_emit():
            await agent._emit("on_finish", content="test result", iterations=3)

        asyncio.run(run_emit())
        assert len(handler_called) == 1
        assert handler_called[0]["content"] == "test result"
        assert handler_called[0]["iterations"] == 3

    def test_emit_multiple_handlers(self):
        import asyncio

        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        calls = []

        def handler1(**kwargs):
            calls.append("handler1")

        def handler2(**kwargs):
            calls.append("handler2")

        agent.on("on_tool_call", handler1)
        agent.on("on_tool_call", handler2)

        async def run_emit():
            await agent._emit("on_tool_call", tool_name="search")

        asyncio.run(run_emit())
        assert calls == ["handler1", "handler2"]

    def test_emit_unknown_event_does_not_error(self):
        import asyncio

        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()

        async def run_emit():
            await agent._emit("nonexistent_event", data="test")

        asyncio.run(run_emit())

    def test_emit_handler_error_does_not_propagate(self):
        import asyncio

        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        good_calls = []

        def bad_handler(**kwargs):
            raise RuntimeError("handler error")

        def good_handler(**kwargs):
            good_calls.append("good")

        agent.on("on_tool_result", bad_handler)
        agent.on("on_tool_result", good_handler)

        async def run_emit():
            await agent._emit("on_tool_result", result="data")

        asyncio.run(run_emit())
        assert good_calls == ["good"]

    def test_all_supported_events(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        expected_events = [
            "on_thinking",
            "on_tool_call",
            "on_tool_result",
            "on_finish",
            "on_error",
        ]
        for event in expected_events:
            assert event in agent._event_handlers

    def test_async_handler_support(self):
        import asyncio

        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        async_calls = []

        async def async_handler(**kwargs):
            await asyncio.sleep(0)
            async_calls.append(kwargs)

        agent.on("on_thinking", async_handler)

        async def run_emit():
            await agent._emit("on_thinking", iteration=1)

        asyncio.run(run_emit())
        assert len(async_calls) == 1
        assert async_calls[0]["iteration"] == 1


# ─── Agent Context Manager Tests ─────────────────────────────────────────────


class TestAgentContextManager:
    """Agent async context manager tests."""

    def test_async_context_manager_enter(self):
        import asyncio

        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        async def run_test():
            async with TestAgent() as agent:
                assert isinstance(agent, BaseAgent)
                assert agent.state.status == AgentStatus.IDLE

        asyncio.run(run_test())

    def test_async_context_manager_exit_resets(self):
        import asyncio

        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()

        async def run_test():
            async with agent as a:
                a.state.status = AgentStatus.THINKING
                a.state.iteration_count = 10

        asyncio.run(run_test())
        assert agent.state.status == AgentStatus.IDLE
        assert agent.state.iteration_count == 0

    def test_async_context_manager_clears_event_handlers(self):
        import asyncio

        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()

        def handler(**kwargs):
            pass

        agent.on("on_finish", handler)

        async def run_test():
            async with agent:
                pass

        asyncio.run(run_test())
        assert agent._event_handlers["on_finish"] == []

    def test_nested_context_managers(self):
        import asyncio

        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        async def run_test():
            agent1 = TestAgent()
            agent2 = TestAgent()
            async with agent1 as a1, agent2 as a2:
                assert a1 is not a2

        asyncio.run(run_test())

    def test_cleanup_method(self):
        import asyncio

        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        agent.state.status = AgentStatus.FINISHED
        agent.state.iteration_count = 8

        async def run_cleanup():
            await agent.cleanup()

        asyncio.run(run_cleanup())
        assert agent.state.status == AgentStatus.IDLE
        assert agent.state.iteration_count == 0


# ─── AgentConfig Validation Tests ────────────────────────────────────────────


class TestAgentConfigValidation:
    """AgentConfig edge case and validation tests."""

    def test_zero_max_iterations(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(max_iterations=0)
        assert config.max_iterations == 0

    def test_zero_timeout(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(timeout=0.0)
        assert config.timeout == 0.0

    def test_temperature_extremes(self):
        from data_ai.core.agent.base import AgentConfig

        config_min = AgentConfig(temperature=0.0)
        assert config_min.temperature == 0.0

        config_max = AgentConfig(temperature=2.0)
        assert config_max.temperature == 2.0

    def test_negative_max_iterations(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(max_iterations=-1)
        assert config.max_iterations == -1

    def test_empty_model_name(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(model_name="")
        assert config.model_name == ""

    def test_metadata_persistence(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(metadata={"key": "value"})
        assert config.metadata["key"] == "value"
        config.metadata["new_key"] = "new_value"
        assert config.metadata["new_key"] == "new_value"
        assert len(config.metadata) == 2

    def test_multiple_agents_with_different_configs(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        config_a = AgentConfig(model_name="gpt-4", temperature=0.2)
        config_b = AgentConfig(model_name="claude-3", temperature=0.8)

        agent_a = TestAgent(config=config_a)
        agent_b = TestAgent(config=config_b)

        assert agent_a.config.model_name == "gpt-4"
        assert agent_b.config.model_name == "claude-3"
        assert agent_a.config.temperature == 0.2
        assert agent_b.config.temperature == 0.8


# ─── Config-Driven Behavior Tests ────────────────────────────────────────────


class TestAgentConfigDrivenBehavior:
    """Tests verifying config values drive agent behavior."""

    def test_build_context_message_returns_none_by_default(self):
        from data_ai.core.agent.base import BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        assert agent._build_context_message() is None

    def test_config_system_prompt_appended_to_prompt(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "Core instructions."

        config = AgentConfig(system_prompt="Extra rules.")
        agent = TestAgent(config=config)
        msg = agent._build_system_message()
        assert "Core instructions." in msg.content
        assert "Extra rules." in msg.content
        assert msg.content.startswith("Core instructions.")

    def test_state_reset_on_new_run(self):
        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent = TestAgent()
        agent.state.iteration_count = 5

        agent.reset()
        assert agent.state.iteration_count == 0
        assert agent.state.status == AgentStatus.IDLE
        assert agent.state.total_tokens == 0


# ─── Multi-Agent Interaction Tests ───────────────────────────────────────────


class TestMultiAgentInteraction:
    """Tests for multiple agents working together."""

    def test_agents_have_independent_states(self):
        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        agent1 = TestAgent()
        agent2 = TestAgent()

        agent1.state.status = AgentStatus.THINKING
        assert agent2.state.status == AgentStatus.IDLE
        assert agent1.state is not agent2.state

    def test_agents_with_different_prompts(self):
        from data_ai.core.agent.base import BaseAgent

        class ResearchAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a research agent."

        class CodeAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a coding agent."

        research = ResearchAgent()
        code = CodeAgent()

        assert research.get_system_prompt() != code.get_system_prompt()
        assert "research" in research.get_system_prompt().lower()
        assert "coding" in code.get_system_prompt().lower()

    def test_agents_share_config_not_state(self):
        from data_ai.core.agent.base import AgentConfig, BaseAgent

        class TestAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a helpful test agent."

        shared_config = AgentConfig(model_name="shared-model", temperature=0.5)

        agent1 = TestAgent(config=shared_config)
        agent2 = TestAgent(config=shared_config)

        assert agent1.config is agent2.config
        assert agent1.state is not agent2.state
