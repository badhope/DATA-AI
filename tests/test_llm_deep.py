"""
DATA-AI 深度测试套件 — LLM 层
"""

import os
from unittest.mock import patch

import pytest


class TestOpenAIClientConstruction:
    def test_construct_with_api_key(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider, OpenAIClient

        config = ModelConfig(
            provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test", context_window=128000
        )
        with patch("openai.AsyncOpenAI") as _:
            client = OpenAIClient(config)
            assert client.config.model_name == "gpt-4o"
            assert client.config.context_window == 128000
            assert client.config.temperature == 0.7

    def test_construct_with_env_api_key(self):
        os.environ["OPENAI_API_KEY"] = "sk-env"
        from data_ai.core.llm.manager import ModelConfig, ModelProvider, OpenAIClient

        config = ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o")
        with patch("openai.AsyncOpenAI") as _:
            client = OpenAIClient(config)
            assert client is not None
        del os.environ["OPENAI_API_KEY"]

    def test_custom_base_url(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider, OpenAIClient

        config = ModelConfig(
            provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test", base_url="https://custom.openai.com"
        )
        with patch("openai.AsyncOpenAI") as mock:
            OpenAIClient(config)
            mock_kwargs = mock.call_args[1] if mock.call_args else {}
            assert "base_url" in mock_kwargs

    def test_missing_api_key_does_not_crash_on_construct(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider, OpenAIClient

        config = ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o")
        with patch("openai.AsyncOpenAI") as _:
            client = OpenAIClient(config)
            assert client is not None

    def test_validate_config_no_key(self):
        from data_ai.core.llm.manager import LLMConfigError, ModelConfig, ModelProvider, OpenAIClient

        config = ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o")
        with patch("openai.AsyncOpenAI") as _:
            client = OpenAIClient(config)
            with pytest.raises(LLMConfigError):
                client.validate_config()


class TestAnthropicClientConstruction:
    def test_construct(self):
        pytest.importorskip("anthropic")
        from data_ai.core.llm.manager import AnthropicClient, ModelConfig, ModelProvider

        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        config = ModelConfig(provider=ModelProvider.ANTHROPIC, model_name="claude-sonnet-4-20250514")
        with patch("anthropic.AsyncAnthropic") as _:
            client = AnthropicClient(config)
            assert client.config.model_name.startswith("claude")
        del os.environ["ANTHROPIC_API_KEY"]

    def test_convert_messages_with_system(self):
        pytest.importorskip("anthropic")
        from data_ai.core.llm.manager import AnthropicClient, ChatMessage, ModelConfig, ModelProvider

        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        config = ModelConfig(provider=ModelProvider.ANTHROPIC, model_name="claude-sonnet-4-20250514")
        with patch("anthropic.AsyncAnthropic") as _:
            client = AnthropicClient(config)
            msgs = [
                ChatMessage(role="system", content="You are helpful."),
                ChatMessage(role="user", content="Hello"),
            ]
            system, converted = client._convert_messages(msgs)
            assert system == "You are helpful."
            assert len(converted) == 1
            assert converted[0]["role"] == "user"

    def test_convert_tools(self):
        pytest.importorskip("anthropic")
        from data_ai.core.llm.manager import AnthropicClient, ModelConfig, ModelProvider

        os.environ["ANTHROPIC_API_KEY"] = "sk-test"
        config = ModelConfig(provider=ModelProvider.ANTHROPIC, model_name="claude-sonnet-4-20250514")
        with patch("anthropic.AsyncAnthropic") as _:
            client = AnthropicClient(config)
            tools = [
                {"function": {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object"}}}
            ]
            converted = client._convert_tools(tools)
            assert len(converted) == 1
            assert "input_schema" in converted[0]
            assert converted[0]["name"] == "get_weather"


class TestOllamaClientConstruction:
    def test_construct(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider, OllamaClient

        config = ModelConfig(provider=ModelProvider.OLLAMA, model_name="llama3", base_url="http://localhost:11434")
        client = OllamaClient(config)
        assert client.base_url == "http://localhost:11434"

    def test_custom_base_url(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider, OllamaClient

        config = ModelConfig(provider=ModelProvider.OLLAMA, model_name="llama3", base_url="http://192.168.1.1:11434")
        client = OllamaClient(config)
        assert client.base_url == "http://192.168.1.1:11434"

    def test_validate_config_unreachable(self):
        from data_ai.core.llm.manager import LLMConnectionError, ModelConfig, ModelProvider, OllamaClient

        config = ModelConfig(provider=ModelProvider.OLLAMA, model_name="llama3", base_url="http://127.0.0.1:19999")
        client = OllamaClient(config)
        with pytest.raises(LLMConnectionError):
            client.validate_config()


class TestLLMManagerRegistration:
    def test_register_and_retrieve(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model(
            "main", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test")
        )
        client = manager.get_client("main")
        assert client is not None

    def test_default_model(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model(
            "second", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test")
        )
        manager.register_model(
            "first",
            ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="sk-test"),
            set_default=True,
        )
        assert manager.get_default_model() == "first"

    def test_set_default_explicitly(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model("a", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test"))
        manager.register_model(
            "b", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="sk-test")
        )
        manager.set_default_model("b")
        assert manager.get_default_model() == "b"

    def test_list_models_empty(self):
        from data_ai.core.llm.manager import LLMManager

        manager = LLMManager()
        assert manager.list_models() == []

    def test_fallback_chain_ordering(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model(
            "primary", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test")
        )
        manager.register_model(
            "backup", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="sk-test")
        )
        manager.set_fallback_chain(["primary", "backup"])
        assert len(manager._fallback_chain) == 2

    def test_register_model_overwrite(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model(
            "test", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test")
        )
        manager.register_model(
            "test", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="sk-test")
        )
        client = manager.get_client("test")
        assert client.config.model_name == "gpt-4o-mini"

    def test_get_nonexistent_model(self):
        from data_ai.core.llm.manager import LLMConfigError, LLMManager

        manager = LLMManager()
        with pytest.raises(LLMConfigError):
            manager.get_client("ghost")

    def test_chat_no_model_registered(self):
        from data_ai.core.llm.manager import ChatMessage, LLMConfigError, LLMManager

        manager = LLMManager()
        with pytest.raises(LLMConfigError):
            import asyncio

            asyncio.run(manager.chat([ChatMessage(role="user", content="hi")]))

    def test_register_all_providers(self):
        pytest.importorskip("anthropic")
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        providers = [
            (ModelProvider.OPENAI, "gpt-4o"),
            (ModelProvider.ANTHROPIC, "claude-sonnet-4-20250514"),
            (ModelProvider.OLLAMA, "llama3"),
            (ModelProvider.DEEPSEEK, "deepseek-chat"),
            (ModelProvider.SILICONFLOW, "Qwen/Qwen2.5-72B-Instruct"),
        ]
        for prov, model in providers:
            apikey = "sk-test"
            manager.register_model(prov.value, ModelConfig(provider=prov, model_name=model, api_key=apikey))
        assert len(manager.list_models()) == len(providers)


class TestContextWindowManagerEdgeCases:
    def test_tiktoken_fallback(self):
        from data_ai.core.llm.manager import ContextWindowManager

        manager = ContextWindowManager("unknown-model-xyz", 10000)
        count = manager.count_tokens("Hello world! " * 100)
        assert count > 0
        assert count < 2000

    def test_empty_text(self):
        from data_ai.core.llm.manager import ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 128000)
        assert manager.count_tokens("") == 0

    def test_very_long_text(self):
        from data_ai.core.llm.manager import ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 128000)
        text = "A" * 100000
        count = manager.count_tokens(text)
        assert count > 0
        assert count < len(text)

    def test_messages_with_tool_calls(self):
        from data_ai.core.llm.manager import ChatMessage, ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 128000)
        msgs = [
            ChatMessage(role="user", content="Hello"),
            ChatMessage(
                role="assistant",
                content="",
                tool_calls=[{"id": "1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
            ),
            ChatMessage(role="tool", content="result", tool_call_id="1"),
        ]
        count = manager.count_message_tokens(msgs)
        assert count > 0

    def test_trim_with_only_system(self):
        from data_ai.core.llm.manager import ChatMessage, ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 100)
        system = ChatMessage(role="system", content="Be helpful.")
        trimmed = manager.trim_messages([], system_message=system)
        assert len(trimmed) == 1
        assert trimmed[0].role == "system"

    def test_trim_very_small_window(self):
        from data_ai.core.llm.manager import ChatMessage, ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 100, reserve_output_tokens=80)
        system = ChatMessage(role="system", content="You are helpful.")
        msgs = [system, ChatMessage(role="user", content="Hello world! What is the weather like today?")]
        trimmed = manager.trim_messages(msgs, system_message=system)
        assert trimmed[0].role == "system"

    def test_estimate_vs_count(self):
        from data_ai.core.llm.manager import ChatMessage, ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 128000)
        msgs = [ChatMessage(role="user", content="Hello world!")]
        assert manager.estimate_tokens(msgs) == manager.count_message_tokens(msgs)

    def test_trim_preserves_recent(self):
        from data_ai.core.llm.manager import ChatMessage, ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 10000, reserve_output_tokens=8000)
        system = ChatMessage(role="system", content="System.")
        msgs = [system] + [
            ChatMessage(role="user", content=f"Message {i} is a long one that takes tokens.") for i in range(20)
        ]
        trimmed = manager.trim_messages(msgs, system_message=system)
        last_original = msgs[-1].content
        last_trimmed = trimmed[-1].content
        assert last_original == last_trimmed


class TestChatMessageSerialization:
    def test_to_dict_roundtrip(self):
        from data_ai.core.llm.manager import ChatMessage

        msg = ChatMessage(role="user", content="Hello")
        d = {"role": msg.role, "content": msg.content}
        assert d["role"] == "user"
        assert d["content"] == "Hello"

    def test_tool_call_message(self):
        from data_ai.core.llm.manager import ChatMessage

        msg = ChatMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "call_1", "type": "function", "function": {"name": "test", "arguments": "{}"}}],
        )
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1

    def test_tool_result_message(self):
        from data_ai.core.llm.manager import ChatMessage

        msg = ChatMessage(role="tool", content="result", tool_call_id="call_1")
        assert msg.tool_call_id == "call_1"


class TestFallbackBehavior:
    async def test_fallback_on_rate_limit(self):
        from data_ai.core.llm.manager import (
            ChatMessage,
            ChatResponse,
            LLMManager,
            LLMRateLimitError,
            ModelConfig,
            ModelProvider,
        )

        manager = LLMManager()
        manager.register_model(
            "primary", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test")
        )
        manager.register_model(
            "backup", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="sk-test")
        )
        manager.set_fallback_chain(["primary", "backup"])

        call_count = 0

        async def mock_retry(client, messages, tools=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMRateLimitError(message="Rate limited")
            return ChatResponse(content="Fallback success", model="gpt-4o-mini")

        with patch.object(manager, "_chat_with_retry", new=mock_retry):
            response = await manager.chat([ChatMessage(role="user", content="hi")], model="primary")
            assert response.content == "Fallback success"

    async def test_fallback_on_connection_error(self):
        from data_ai.core.llm.manager import (
            ChatMessage,
            ChatResponse,
            LLMConnectionError,
            LLMManager,
            ModelConfig,
            ModelProvider,
        )

        manager = LLMManager()
        manager.register_model(
            "main", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test")
        )
        manager.register_model(
            "backup", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="sk-test")
        )
        manager.set_fallback_chain(["main", "backup"])

        call_count = 0

        async def mock_retry(client, messages, tools=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise LLMConnectionError(message="Connection failed")
            return ChatResponse(content="Backup working", model="backup")

        with patch.object(manager, "_chat_with_retry", new=mock_retry):
            response = await manager.chat([ChatMessage(role="user", content="test")], model="main")
            assert "Backup working" in response.content

    async def test_no_fallback_on_regular_error(self):
        from data_ai.core.llm.manager import ChatMessage, LLMException, LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model(
            "main", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="sk-test")
        )
        manager.register_model(
            "backup", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="sk-test")
        )
        manager.set_fallback_chain(["main", "backup"])

        async def mock_retry(client, messages, tools=None, **kwargs):
            raise LLMException(message="Some other error")

        with patch.object(manager, "_chat_with_retry", new=mock_retry):
            with pytest.raises(LLMException):
                await manager.chat([ChatMessage(role="user", content="test")], model="main")


class TestTokenUsage:
    def test_usage_addition_zero(self):
        from data_ai.core.llm.manager import TokenUsage

        t1 = TokenUsage()
        t2 = TokenUsage()
        t3 = t1 + t2
        assert t3.prompt_tokens == 0
        assert t3.completion_tokens == 0
        assert t3.total_tokens == 0

    def test_usage_addition_multiple(self):
        from data_ai.core.llm.manager import TokenUsage

        t = TokenUsage(10, 20, 30)
        for _ in range(5):
            t = t + TokenUsage(10, 20, 30)
        assert t.prompt_tokens == 60
        assert t.completion_tokens == 120
        assert t.total_tokens == 180
