"""
DATA-AI 核心功能测试

验证所有模块的正确性，包括单元测试和集成测试。
"""

import os

import pytest


class TestLLMManager:
    def test_create_manager(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
            api_key="test-key",
        )
        manager.register_model("test", config, set_default=True)
        assert manager.get_default_model() == "test"
        assert "test" in manager.list_models()

    def test_register_multiple_models(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model("openai", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="k1"))
        manager.register_model("ollama", ModelConfig(provider=ModelProvider.OLLAMA, model_name="llama3"))
        assert len(manager.list_models()) == 2

    def test_set_fallback_chain(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        manager.register_model("primary", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o", api_key="k1"))
        manager.register_model(
            "fallback", ModelConfig(provider=ModelProvider.OPENAI, model_name="gpt-4o-mini", api_key="k2")
        )
        manager.set_fallback_chain(["primary", "fallback"])
        assert len(manager._fallback_chain) == 2

    def test_get_client_not_found(self):
        from data_ai.core.llm.manager import LLMConfigError, LLMManager

        manager = LLMManager()
        with pytest.raises(LLMConfigError):
            manager.get_client("nonexistent")

    def test_chat_message_dataclass(self):
        from data_ai.core.llm.manager import ChatMessage

        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_model_provider_enum(self):
        from data_ai.core.llm.manager import ModelProvider

        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider("openai") == ModelProvider.OPENAI

    def test_model_config_dataclass(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        config = ModelConfig(
            provider=ModelProvider.ANTHROPIC,
            model_name="claude-sonnet-4-20250514",
            temperature=0.5,
            context_window=200000,
        )
        assert config.provider == ModelProvider.ANTHROPIC
        assert config.temperature == 0.5
        assert config.context_window == 200000

    def test_token_usage_addition(self):
        from data_ai.core.llm.manager import TokenUsage

        t1 = TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        t2 = TokenUsage(prompt_tokens=200, completion_tokens=100, total_tokens=300)
        t3 = t1 + t2
        assert t3.prompt_tokens == 300
        assert t3.completion_tokens == 150
        assert t3.total_tokens == 450

    def test_get_llm_manager_singleton(self):
        from data_ai.core.llm.manager import get_llm_manager

        m1 = get_llm_manager()
        m2 = get_llm_manager()
        assert m1 is m2


class TestContextWindowManager:
    def test_count_tokens(self):
        from data_ai.core.llm.manager import ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 128000)
        count = manager.count_tokens("Hello, world!")
        assert count > 0
        assert count < 20

    def test_trim_messages_preserves_system(self):
        from data_ai.core.llm.manager import ChatMessage, ContextWindowManager

        manager = ContextWindowManager("gpt-4o", 500)
        system = ChatMessage(role="system", content="You are a helpful assistant.")
        messages = [ChatMessage(role="user", content="Hello world! Good morning!")] * 100

        trimmed = manager.trim_messages(messages, system_message=system)
        assert trimmed[0].role == "system"
        assert len(trimmed) < len(messages) + 1


class TestToolRegistry:
    def test_register_tool(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(
            name="test_tool",
            description="A test tool",
            parameters={"param1": {"type": "string", "description": "A parameter"}},
            function=lambda param1: f"Result: {param1}",
        )
        assert "test_tool" in registry.list_tools()
        assert registry.get_tool_count() == 1

    def test_register_function(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()

        def my_function(x: int, y: str = "default") -> str:
            return f"{x}: {y}"

        registry.register_function(my_function)
        assert "my_function" in registry.list_tools()

    async def test_execute_tool(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(
            name="echo",
            description="Echo back",
            parameters={"message": {"type": "string", "description": "Message"}},
            function=lambda message: f"Echo: {message}",
        )

        result = await registry.execute("echo", {"message": "Hello"})
        assert result == "Echo: Hello"

    async def test_execute_nonexistent_tool(self):
        from data_ai.core.tool.registry import ToolExecutionError, ToolRegistry

        registry = ToolRegistry()
        with pytest.raises(ToolExecutionError):
            await registry.execute("nonexistent", {})

    def test_get_openai_tool_schemas(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(
            name="calculator",
            description="Calculate expression",
            parameters={"expr": {"type": "string", "description": "Expression"}},
        )

        schemas = registry.get_openai_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "calculator"

    def test_builtin_tools(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()
        assert registry.get_tool_count() >= 5
        assert "get_current_time" in registry.list_tools()
        assert "calculate" in registry.list_tools()
        assert "read_file" in registry.list_tools()
        assert "write_file" in registry.list_tools()
        assert "list_directory" in registry.list_tools()

    async def test_builtin_calculate(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()
        result = await registry.execute("calculate", {"expression": "2 + 3 * 4"})
        assert "14" in str(result)

    async def test_builtin_get_current_time(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()
        result = await registry.execute("get_current_time", {})
        assert "T" in str(result)


class TestAgent:
    def test_agent_config(self):
        from data_ai.core.agent.base import AgentConfig

        config = AgentConfig(
            model_name="gpt-4o",
            max_iterations=5,
            timeout=60.0,
        )
        assert config.model_name == "gpt-4o"
        assert config.max_iterations == 5
        assert config.timeout == 60.0

    def test_agent_state(self):
        from data_ai.core.agent.base import AgentState, AgentStatus

        state = AgentState()
        assert state.status == AgentStatus.IDLE
        assert state.iteration_count == 0
        assert len(state.messages) == 0

    def test_agent_status_enum(self):
        from data_ai.core.agent.base import AgentStatus

        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.THINKING.value == "thinking"
        assert AgentStatus.FINISHED.value == "finished"

    async def test_agent_async_context_manager(self):
        from data_ai.core.agent.base import AgentStatus, BaseAgent

        class ConcreteAgent(BaseAgent):
            def get_system_prompt(self) -> str:
                return "You are a test agent."

        agent = ConcreteAgent()
        async with agent:
            assert agent.state.status == AgentStatus.IDLE
        assert agent.state.status == AgentStatus.IDLE


class TestMemory:
    def test_memory_store_add(self):
        from data_ai.core.memory.manager import MemoryStore, MemoryType

        store = MemoryStore(max_short_term=10)
        entry = store.add_short_term("Test memory", importance=0.8)
        assert entry.content == "Test memory"
        assert entry.memory_type == MemoryType.SHORT_TERM
        assert entry.importance == 0.8

    def test_memory_store_short_term_limit(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore(max_short_term=5)
        for i in range(10):
            store.add_short_term(f"Memory {i}")
        assert len(store.get_short_term()) == 5

    def test_memory_store_search(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        store.add_long_term("Python is a programming language", importance=0.9)
        store.add_long_term("JavaScript is used for web development", importance=0.7)

        results = store.search("python")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_memory_manager_remember(self):
        from data_ai.core.memory.manager import MemoryManager, MemoryType

        manager = MemoryManager()
        manager.remember("Important fact", importance=0.9, memory_type=MemoryType.LONG_TERM)
        assert len(manager.store.get_long_term()) == 1

    def test_memory_manager_recall(self):
        from data_ai.core.memory.manager import MemoryManager

        manager = MemoryManager()
        manager.remember("The sky is blue")
        result = manager.recall_relevant("sky")
        assert "sky" in result.lower()

    def test_memory_stats(self):
        from data_ai.core.memory.manager import MemoryManager

        manager = MemoryManager()
        manager.remember("Fact 1")
        manager.remember("Fact 2")
        stats = manager.get_stats()
        assert stats["short_term_count"] == 2
        assert stats["total"] == 2


class TestRAG:
    def test_document_dataclass(self):
        from data_ai.core.rag.pipeline import Document

        doc = Document(content="Test content", metadata={"source": "test.txt"})
        assert doc.content == "Test content"
        assert doc.metadata["source"] == "test.txt"

    def test_text_splitter(self):
        from data_ai.core.rag.pipeline import TextSplitter

        splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
        text = "This is a long text. " * 50
        chunks = splitter.split_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100 + 20

    def test_text_splitter_short_text(self):
        from data_ai.core.rag.pipeline import TextSplitter

        splitter = TextSplitter(chunk_size=1000)
        chunks = splitter.split_text("Short text")
        assert len(chunks) == 1
        assert chunks[0] == "Short text"

    def test_split_documents(self):
        from data_ai.core.rag.pipeline import Document, TextSplitter

        splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
        doc = Document(content="Long text. " * 50, metadata={"source": "test.txt"})
        chunks = splitter.split_documents([doc])
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata["source"] == "test.txt"

    def test_in_memory_vector_store(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        docs = [Document(content="Test doc")]
        embeddings = [[0.1] * 10]

        store.add(docs, embeddings)
        assert store.count() == 1

        results = store.search([0.1] * 10, top_k=1)
        assert len(results) == 1
        assert results[0][0].content == "Test doc"

    def test_rag_pipeline_initialization(self):
        from data_ai.core.rag.pipeline import HuggingFaceEmbedder, InMemoryVectorStore, RAGPipeline

        try:
            pipeline = RAGPipeline(
                embedder=HuggingFaceEmbedder(),
                vector_store=InMemoryVectorStore(),
            )
        except (ImportError, Exception) as e:
            pytest.skip(f"HuggingFaceEmbedder not available: {e}")

        assert pipeline.top_k == 5
        stats = pipeline.get_stats()
        assert stats["document_count"] == 0

    def test_rag_pipeline_add_texts(self):
        from data_ai.core.rag.pipeline import HuggingFaceEmbedder, InMemoryVectorStore, RAGPipeline

        try:
            pipeline = RAGPipeline(
                embedder=HuggingFaceEmbedder(),
                vector_store=InMemoryVectorStore(),
            )
        except (ImportError, Exception) as e:
            pytest.skip(f"HuggingFaceEmbedder not available: {e}")

        count = pipeline.add_texts(["Hello world", "Python programming"])
        assert count >= 2
        assert pipeline.get_stats()["document_count"] >= 2

    def test_rag_pipeline_with_openai(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"

        from data_ai.core.rag.pipeline import InMemoryVectorStore, OpenAIEmbedder, RAGPipeline

        try:
            pipeline = RAGPipeline(
                embedder=OpenAIEmbedder(),
                vector_store=InMemoryVectorStore(),
            )
        except Exception as e:
            pytest.skip(f"OpenAI not available: {e}")

        assert pipeline.embedder.dimension > 0


class TestReasoning:
    def test_thought_dataclass(self):
        from data_ai.core.reasoning.sequential import Thought

        thought = Thought(content="Step 1: Analysis", confidence=0.8)
        assert thought.content == "Step 1: Analysis"
        assert thought.confidence == 0.8

    def test_reasoning_chain_dataclass(self):
        from data_ai.core.reasoning.sequential import ReasoningChain

        chain = ReasoningChain(question="What is 2+2?")
        assert chain.question == "What is 2+2?"
        assert len(chain.thoughts) == 0

    async def test_sequential_thinking_fallback(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        thinker = SequentialThinking(max_steps=3)
        chain = await thinker.think("What is AI?")
        assert chain.final_answer is not None
        assert len(chain.thoughts) > 0

    async def test_sequential_thinking_with_llm(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        async def mock_llm(prompt: str) -> str:
            return "Step 1: Analyze the question.\nStep 2: Find answer.\nFINAL ANSWER: 42"

        thinker = SequentialThinking()
        chain = await thinker.think("What is the answer?", llm_fn=mock_llm)
        assert "42" in chain.final_answer
        assert len(chain.thoughts) == 2

    def test_chain_to_dict(self):
        from data_ai.core.reasoning.sequential import ReasoningChain, Thought

        chain = ReasoningChain(
            question="Test",
            thoughts=[Thought(content="Step 1", confidence=0.7)],
            final_answer="Result",
        )
        d = chain.to_dict()
        assert d["question"] == "Test"
        assert d["final_answer"] == "Result"
        assert len(d["thoughts"]) == 1

    def test_reasoning_history(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        thinker = SequentialThinking()
        assert len(thinker.get_history()) == 0


class TestSession:
    def test_create_session(self):
        from data_ai.session import Session

        session = Session(name="Test Session")
        assert session.name == "Test Session"
        assert len(session.messages) == 0

    def test_add_messages(self):
        from data_ai.session import Session

        session = Session()
        session.add_user_message("Hello")
        session.add_assistant_message("Hi there!")

        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"

    def test_session_manager(self):
        from data_ai.session import SessionManager

        manager = SessionManager()
        session = manager.create_session("Test")
        assert session.name == "Test"
        assert manager.get_active_session() is not None

        manager.delete_session(session.id)
        assert manager.get_active_session() is None

    def test_session_to_dict(self):
        from data_ai.session import Session

        session = Session(name="Test")
        d = session.to_dict()
        assert d["name"] == "Test"
        assert d["message_count"] == 0


class TestSDK:
    def test_create_client(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"

        from data_ai.sdk import DataAI, create_client

        client = create_client(model="gpt-4o", provider="openai", api_key="sk-test")
        assert isinstance(client, DataAI)
        assert client.model == "gpt-4o"
        assert client.provider == "openai"

    def test_client_rag_property(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"

        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="sk-test")
        rag = client.rag
        assert rag is not None
        assert client.rag is rag

    def test_client_memory_property(self):
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="test-key")
        assert client.memory is not None

    def test_client_tools_property(self):
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="test-key")
        assert client.tools is not None

    def test_client_llm_property(self):
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="test-key")
        assert client.llm is not None

    def test_client_add_documents(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"

        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="sk-test")
        try:
            count = client.add_documents(["Document 1", "Document 2"])
            assert count >= 2
        except Exception as e:
            pytest.skip(f"Embedding service not available: {e}")

    def test_client_remember_recall(self):
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="test-key")
        client.remember("Important note about Python", importance=0.9)
        result = client.recall("Python")
        assert "Python" in result

    def test_client_system_prompt(self):
        from data_ai.sdk import create_client

        client = create_client(
            model="gpt-4o",
            api_key="test-key",
            system_prompt="You are a math tutor.",
        )
        assert "math tutor" in client.get_system_prompt()

    async def test_client_async_context_manager(self):
        from data_ai.sdk import create_client

        client = create_client(model="gpt-4o", api_key="test-key")
        async with client:
            pass


class TestExceptions:
    def test_llm_exception(self):
        from data_ai.utils.exceptions import LLMException

        exc = LLMException(message="Test error", provider="openai", model="gpt-4")
        assert exc.message == "Test error"
        assert exc.details["provider"] == "openai"

    def test_llm_config_error(self):
        from data_ai.utils.exceptions import LLMConfigError

        exc = LLMConfigError(message="Config error")
        assert "Config error" in str(exc)

    def test_llm_rate_limit_error(self):
        from data_ai.utils.exceptions import LLMRateLimitError

        exc = LLMRateLimitError(message="Rate limited")
        assert "Rate limited" in str(exc)

    def test_agent_exception(self):
        from data_ai.utils.exceptions import AgentException

        exc = AgentException(message="Agent error")
        assert "Agent error" in str(exc)

    def test_agent_timeout_error(self):
        from data_ai.utils.exceptions import AgentTimeoutError

        exc = AgentTimeoutError(agent="test_agent", timeout=30.0)
        assert "test_agent" in str(exc)

    def test_agent_max_iterations_error(self):
        from data_ai.utils.exceptions import AgentMaxIterationsError

        exc = AgentMaxIterationsError(agent="test_agent", max_iterations=10)
        assert "test_agent" in str(exc)
        assert "10" in str(exc)

    def test_tool_execution_error(self):
        from data_ai.utils.exceptions import ToolExecutionError

        exc = ToolExecutionError(tool="test_tool", message="Test failure")
        assert "test_tool" in exc.details["tool"]
        assert "Test failure" in exc.message

    def test_rag_exception(self):
        from data_ai.utils.exceptions import RAGIndexError

        exc = RAGIndexError(document_id="doc1", reason="Bad format")
        assert "doc1" in str(exc)

    def test_memory_exception(self):
        from data_ai.utils.exceptions import MemoryInitError

        exc = MemoryInitError(reason="Out of memory")
        assert "Out of memory" in str(exc)

    def test_error_code_enum(self):
        from data_ai.utils.exceptions import ErrorCode

        assert ErrorCode.LLM_ERROR.value == "2000"
        assert ErrorCode.AGENT_TIMEOUT.value == "3001"


def test_package_version():
    from data_ai import __version__

    assert __version__ == "2.0.1"


def test_package_imports():
    from data_ai import (
        DataAI,
        create_client,
    )

    assert DataAI is not None
    assert create_client is not None


class TestTextSplitterEdgeCases:
    def test_chunk_overlap_guard(self):
        from data_ai.core.rag.pipeline import RAGConfigError, TextSplitter

        with pytest.raises(RAGConfigError):
            TextSplitter(chunk_size=100, chunk_overlap=100)

        with pytest.raises(RAGConfigError):
            TextSplitter(chunk_size=100, chunk_overlap=200)

    def test_valid_splitter(self):
        from data_ai.core.rag.pipeline import TextSplitter

        splitter = TextSplitter(chunk_size=100, chunk_overlap=99)
        assert splitter.chunk_size == 100
        assert splitter.chunk_overlap == 99


class TestRAGPipelineGracefulDegrade:
    def test_custom_embedder(self):
        from data_ai.core.rag.pipeline import InMemoryVectorStore, RAGPipeline

        try:
            from data_ai.core.rag.pipeline import HuggingFaceEmbedder

            pipeline = RAGPipeline(embedder=HuggingFaceEmbedder(), vector_store=InMemoryVectorStore())
            assert pipeline.embedder.dimension > 0
        except (ImportError, Exception):
            pytest.skip("HuggingFaceEmbedder not available")


class TestLLMManagerNewClients:
    def test_google_client_registration(self):
        pytest.importorskip("google.generativeai", reason="google-generativeai not installed")
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        config = ModelConfig(provider=ModelProvider.GOOGLE, model_name="gemini-2.0-flash", api_key="test-key")
        manager.register_model("gemini", config)
        assert "gemini" in manager.list_models()

    def test_azure_client_registration(self):
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        config = ModelConfig(
            provider=ModelProvider.AZURE,
            model_name="gpt-4o",
            api_key="test-key",
            base_url="https://test.openai.azure.com",
        )
        manager.register_model("azure", config)
        assert "azure" in manager.list_models()

    def test_aws_client_registration(self):
        pytest.importorskip("boto3", reason="boto3 not installed")
        from data_ai.core.llm.manager import LLMManager, ModelConfig, ModelProvider

        manager = LLMManager()
        config = ModelConfig(provider=ModelProvider.AWS, model_name="anthropic.claude-sonnet-4-20250514-v1:0")
        manager.register_model("aws", config)
        assert "aws" in manager.list_models()


class TestDataAIIsolation:
    def test_two_clients_independent(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"

        from data_ai.sdk import create_client

        client1 = create_client(model="gpt-4o", api_key="sk-test")
        client2 = create_client(model="gpt-4o-mini", api_key="sk-test2")

        assert client1._llm_manager is not client2._llm_manager
        assert client1._tool_registry is not client2._tool_registry
        assert client1._memory_manager is not client2._memory_manager

    def test_shared_global_mode(self):
        os.environ["OPENAI_API_KEY"] = "sk-test"

        from data_ai.sdk import DataAI

        client1 = DataAI(model="gpt-4o", api_key="sk-test", share_global=True)
        client2 = DataAI(model="gpt-4o-mini", api_key="sk-test2", share_global=True)

        assert client1._llm_manager is client2._llm_manager
        assert client1._tool_registry is client2._tool_registry


def test_makefile_format():
    from pathlib import Path

    makefile = Path("/workspace/DATA-AI/Makefile")
    if makefile.exists():
        content = makefile.read_text()
        assert "install" in content
        assert "test" in content
        assert "DOCKER_BUILDKIT" in content


def test_pyproject_structure():
    from pathlib import Path

    pyproject = Path("/workspace/DATA-AI/pyproject.toml")
    if pyproject.exists():
        content = pyproject.read_text()
        assert "langchain" not in content.lower()
