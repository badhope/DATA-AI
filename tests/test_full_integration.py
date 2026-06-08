"""
DATA-AI Full Integration Tests (v2.0 API)

Test how components work together across the full stack:
tool registry, LLM manager, RAG pipeline, memory, sessions, and SDK.
"""

import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from data_ai.core.llm.manager import (
    LLMManager,
    ModelConfig,
    ModelProvider,
    get_llm_manager,
)
from data_ai.core.memory.manager import (
    MemoryEntry,
    MemoryManager,
    MemoryStore,
    MemoryType,
    get_memory_manager,
)
from data_ai.core.rag.pipeline import (
    BaseEmbedder,
    Document,
    InMemoryVectorStore,
    RAGPipeline,
    RetrievalResult,
    TextSplitter,
)
from data_ai.core.tool.registry import (
    ToolDefinition,
    ToolRegistry,
    get_tool_registry,
)
from data_ai.sdk import DataAI, create_client
from data_ai.session import SessionManager


class MockEmbedder(BaseEmbedder):
    @property
    def dimension(self):
        return 128

    def embed(self, texts):
        return [[0.0] * 128 for _ in texts]

    async def aembed(self, texts):
        return [[0.0] * 128 for _ in texts]


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def clean_tool_registry():
    reg = ToolRegistry()
    yield reg
    reg.clear()


@pytest.fixture
def clean_session_manager():
    mgr = SessionManager()
    yield mgr
    mgr.clear_all()


@pytest.fixture
def clean_memory_manager():
    mgr = MemoryManager()
    yield mgr
    mgr.clear()


@pytest.fixture
def mock_embedder():
    return MockEmbedder()


@pytest.fixture
def vector_store():
    store = InMemoryVectorStore()
    yield store
    store.clear()


# ─── TestFullToolIntegration ─────────────────────────────────────────────────


class TestFullToolIntegration:
    def test_register_tools_and_verify_schemas(self, clean_tool_registry):
        clean_tool_registry.register(
            name="add_numbers",
            description="Add two numbers together",
            parameters={
                "a": {"type": "number", "description": "First number"},
                "b": {"type": "number", "description": "Second number"},
            },
            required=["a", "b"],
            function=lambda a, b: a + b,
        )

        clean_tool_registry.register(
            name="greet",
            description="Greet a user by name",
            parameters={
                "name": {"type": "string", "description": "User name"},
            },
            required=["name"],
            function=lambda name: f"Hello, {name}!",
        )

        assert clean_tool_registry.get_tool_count() == 2
        assert "add_numbers" in clean_tool_registry.list_tools()
        assert "greet" in clean_tool_registry.list_tools()

        schemas = clean_tool_registry.get_openai_tool_schemas()
        assert len(schemas) == 2

        for schema in schemas:
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]

    def test_tool_schemas_work_with_llm_model_config(self, clean_tool_registry):
        clean_tool_registry.register(
            name="search",
            description="Search the web for information",
            parameters={
                "query": {"type": "string", "description": "Search query"},
            },
            required=["query"],
        )

        llm = LLMManager()
        config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
            api_key="test-key",
            temperature=0.7,
            max_tokens=1024,
        )
        llm.register_model("test-model", config, set_default=True)

        assert llm.get_default_model() == "test-model"
        assert "test-model" in llm.list_models()

        tool_schemas = clean_tool_registry.get_openai_tool_schemas()
        assert len(tool_schemas) == 1
        assert tool_schemas[0]["function"]["name"] == "search"

    def test_register_builtin_tools_integration(self, clean_tool_registry):
        clean_tool_registry.register_builtin_tools()

        tools = clean_tool_registry.list_tools()
        assert "get_current_time" in tools
        assert "calculate" in tools
        assert "read_file" in tools
        assert "write_file" in tools
        assert "list_directory" in tools

        schemas = clean_tool_registry.get_openai_tool_schemas()
        assert len(schemas) == 5

    def test_register_function_via_registry(self, clean_tool_registry):
        def echo(message: str) -> str:
            return message

        clean_tool_registry.register_function(
            echo,
            name="echo",
            description="Echo back the input message",
        )

        assert clean_tool_registry.get_tool_count() == 1
        tool = clean_tool_registry.get("echo")
        assert tool is not None
        assert tool.name == "echo"
        assert tool.description == "Echo back the input message"

        schemas = clean_tool_registry.get_openai_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["parameters"]["properties"]["message"]["type"] == "string"

    def test_tool_definition(self):
        tool_def = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"p1": {"type": "string"}},
            required=["p1"],
        )

        openai_schema = tool_def.to_openai_tool()
        assert openai_schema["type"] == "function"
        assert openai_schema["function"]["name"] == "test_tool"
        assert openai_schema["function"]["parameters"]["required"] == ["p1"]

    def test_llm_manager_with_multiple_providers(self):
        llm = LLMManager()

        openai_config = ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
            api_key="key-openai",
        )
        deepseek_config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="key-deepseek",
        )
        siliconflow_config = ModelConfig(
            provider=ModelProvider.SILICONFLOW,
            model_name="Qwen/Qwen2.5-7B-Instruct",
            api_key="key-siliconflow",
            base_url="https://api.siliconflow.cn/v1",
        )

        llm.register_model("openai", openai_config, set_default=True)
        llm.register_model("deepseek", deepseek_config, fallback_priority=1)
        llm.register_model("siliconflow", siliconflow_config, fallback_priority=2)

        assert llm.get_default_model() == "openai"
        assert set(llm.list_models()) == {"openai", "deepseek", "siliconflow"}

        client = llm.get_client("openai")
        assert client is not None
        assert client.config.provider == ModelProvider.OPENAI
        assert client.config.model_name == "gpt-4o"

    def test_register_model_helper_function(self):

        llm = LLMManager()
        config = ModelConfig(
            provider=ModelProvider.DEEPSEEK,
            model_name="deepseek-chat",
            api_key="test-key",
        )
        llm.register_model("deepseek", config, set_default=True)

        assert llm.get_default_model() == "deepseek"
        assert "deepseek" in llm.list_models()

    def test_tool_registry_singleton(self):
        reg1 = get_tool_registry()
        reg2 = get_tool_registry()
        assert reg1 is reg2

    def test_llm_manager_singleton(self):
        mgr1 = get_llm_manager()
        mgr2 = get_llm_manager()
        assert mgr1 is mgr2


# ─── TestFullRAGIntegration ──────────────────────────────────────────────────


class TestFullRAGIntegration:
    def test_rag_pipeline_with_mock_embedder(self, mock_embedder, vector_store):
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            vector_store=vector_store,
            top_k=3,
        )

        docs = [
            Document(content="Python is a high-level programming language.", metadata={"source": "python"}),
            Document(content="Machine learning uses algorithms to learn from data.", metadata={"source": "ml"}),
            Document(content="Data science combines statistics and programming.", metadata={"source": "ds"}),
        ]
        count = pipeline.add_documents(docs)
        assert count == 3

        result = pipeline.search("programming", top_k=2)
        assert isinstance(result, RetrievalResult)
        assert len(result.documents) == 2
        assert len(result.scores) == 2
        assert result.query == "programming"

    def test_rag_pipeline_query_returns_formatted_text(self, mock_embedder, vector_store):
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            vector_store=vector_store,
        )

        pipeline.add_texts(["Python is a programming language."], metadata={"source": "test"})

        formatted = pipeline.query("Python", top_k=1)
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        assert "Python" in formatted

    def test_rag_pipeline_add_texts(self, mock_embedder, vector_store):
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            vector_store=vector_store,
        )

        count = pipeline.add_texts(
            ["Hello world", "Goodbye world"],
            metadata={"category": "greetings"},
        )
        assert count == 2

        stats = pipeline.get_stats()
        assert stats["document_count"] == 2
        assert stats["embedder"] == "MockEmbedder"
        assert stats["store"] == "InMemoryVectorStore"
        assert stats["dimension"] == 128

    def test_rag_with_text_splitter(self, mock_embedder, vector_store):
        splitter = TextSplitter(chunk_size=30, chunk_overlap=5)
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            vector_store=vector_store,
            text_splitter=splitter,
        )

        long_text = "This is a long document. It has many sentences. We need to split it appropriately."
        count = pipeline.add_texts([long_text])
        assert count > 0

        result = pipeline.search("long document", top_k=3)
        assert len(result.documents) > 0

    def test_rag_integration_with_memory_manager(self, mock_embedder, vector_store, clean_memory_manager):
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            vector_store=vector_store,
        )

        pipeline.add_texts(["Python is a programming language."], metadata={"source": "docs"})

        result = pipeline.search("Python", top_k=1)
        assert len(result.documents) == 1

        clean_memory_manager.remember(
            f"RAG search: found {len(result.documents)} documents for 'Python'",
            importance=0.7,
            memory_type=MemoryType.LONG_TERM,
            source="rag_integration",
        )

        stats = clean_memory_manager.get_stats()
        assert stats["long_term_count"] == 1
        assert stats["total"] == 1

        recalled = clean_memory_manager.recall_relevant("Python", limit=5)
        assert "RAG search" in recalled

    def test_rag_pipeline_document_metadata(self, mock_embedder, vector_store):
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            vector_store=vector_store,
        )

        doc = Document(
            content="FastAPI is a modern web framework for Python.",
            metadata={"source": "docs", "version": "1.0", "author": "test"},
        )
        pipeline.add_documents([doc])

        result = pipeline.search("FastAPI", top_k=1)
        assert len(result.documents) == 1
        retrieved = result.documents[0]
        assert retrieved.metadata["source"] == "docs"
        assert retrieved.metadata["version"] == "1.0"
        assert "chunk_index" in retrieved.metadata

    def test_rag_pipeline_clear(self, mock_embedder, vector_store):
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            vector_store=vector_store,
        )

        pipeline.add_texts(["Document one", "Document two"])
        assert pipeline.get_stats()["document_count"] == 2

        pipeline.clear()
        assert pipeline.get_stats()["document_count"] == 0

    def test_in_memory_vector_store_operations(self):
        store = InMemoryVectorStore()

        doc = Document(content="test content", metadata={"id": "1"})
        embedding = [[0.0] * 128]
        store.add([doc], embedding)

        assert store.count() == 1

        query_embedding = [0.0] * 128
        results = store.search(query_embedding, top_k=1)
        assert len(results) == 1
        assert results[0][0].content == "test content"

        store.clear()
        assert store.count() == 0


# ─── TestFullSessionIntegration ───────────────────────────────────────────────


class TestFullSessionIntegration:
    def test_create_and_manage_sessions(self, clean_session_manager):
        session1 = clean_session_manager.create_session(name="Session Alpha")
        session2 = clean_session_manager.create_session(name="Session Beta")

        assert session1.name == "Session Alpha"
        assert session2.name == "Session Beta"
        assert session1.id != session2.id

        sessions = clean_session_manager.list_sessions()
        assert len(sessions) == 2

    def test_session_message_operations(self, clean_session_manager):
        session = clean_session_manager.create_session(name="Chat Session")

        session.add_user_message("Hello, AI!")
        session.add_assistant_message("Hello! How can I help you?")
        session.add_message("system", "You are a helpful assistant.")

        msgs = session.get_messages()
        assert len(msgs) == 3

        non_system = session.get_messages(include_system=False)
        assert len(non_system) == 2

        last = session.get_last_n_messages(2)
        assert len(last) == 2

    def test_session_switch_and_active(self, clean_session_manager):
        s1 = clean_session_manager.create_session(name="First")
        s2 = clean_session_manager.create_session(name="Second")

        active = clean_session_manager.get_active_session()
        assert active is not None
        assert active.id == s2.id

        clean_session_manager.set_active_session(s1.id)
        active = clean_session_manager.get_active_session()
        assert active.id == s1.id

    def test_session_message_with_tool_calls(self, clean_session_manager):
        session = clean_session_manager.create_session(name="Tool Session")

        session.add_user_message("Search for Python docs")
        session.add_assistant_message(
            content="Let me search for that.",
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search", "arguments": '{"query": "Python docs"}'},
                }
            ],
        )
        session.add_tool_message(
            content="Found 3 results about Python documentation.",
            tool_call_id="call_1",
        )

        msgs = session.get_messages()
        assert len(msgs) == 3

        tool_msgs = [m for m in msgs if m.role == "tool"]
        assert len(tool_msgs) == 1
        assert tool_msgs[0].tool_call_id == "call_1"

    def test_session_stats(self, clean_session_manager):
        session = clean_session_manager.create_session(name="Stats Session")

        session.add_user_message("Hello")
        session.add_assistant_message("Hi there")
        session.add_user_message("How are you?")

        stats = session.get_stats()
        assert stats["message_count"] == 3
        assert stats["name"] == "Stats Session"
        assert "role_distribution" in stats
        assert stats["role_distribution"]["user"] == 2
        assert stats["role_distribution"]["assistant"] == 1

    def test_session_delete_and_clear(self, clean_session_manager):
        session = clean_session_manager.create_session(name="To Delete")
        session.add_user_message("Test message")

        sessions = clean_session_manager.list_sessions()
        assert len(sessions) == 1

        clean_session_manager.delete_session(session.id)
        assert len(clean_session_manager.list_sessions()) == 0

    def test_session_with_system_prompt(self, clean_session_manager):
        session = clean_session_manager.create_session(
            name="Prompt Session",
            system_prompt="You are a Python expert.",
        )

        msgs = session.get_messages()
        assert len(msgs) == 1
        assert msgs[0].role == "system"
        assert "Python" in msgs[0].content

    def test_session_to_dict(self, clean_session_manager):
        session = clean_session_manager.create_session(name="Dict Session")
        session.add_user_message("Hello")

        d = session.to_dict()
        assert d["name"] == "Dict Session"
        assert d["message_count"] == 1
        assert "id" in d
        assert "created_at" in d

    def test_session_role_helpers(self, clean_session_manager):
        session = clean_session_manager.create_session(name="Helper Session")

        msg1 = session.add_user_message("User says hi")
        msg2 = session.add_assistant_message("Assistant replies")

        assert msg1.role == "user"
        assert msg1.content == "User says hi"
        assert msg2.role == "assistant"
        assert msg2.content == "Assistant replies"


# ─── TestFullMemoryIntegration ────────────────────────────────────────────────


class TestFullMemoryIntegration:
    def test_memory_remember_and_recall(self, clean_memory_manager):
        clean_memory_manager.remember("User prefers dark mode", importance=0.8)
        clean_memory_manager.remember("Project is in Python 3.12", importance=0.9)

        short = clean_memory_manager.recall_short_term()
        assert "dark mode" in short
        assert "Python 3.12" in short

    def test_memory_long_term_storage(self, clean_memory_manager):
        clean_memory_manager.remember("Core architecture decision", importance=0.9, memory_type=MemoryType.LONG_TERM)
        clean_memory_manager.remember("Temporary note", importance=0.3, memory_type=MemoryType.SHORT_TERM)

        long = clean_memory_manager.recall_long_term()
        assert "Core architecture decision" in long

        stats = clean_memory_manager.get_stats()
        assert stats["long_term_count"] == 1
        assert stats["short_term_count"] == 1

    def test_memory_relevant_search(self, clean_memory_manager):
        clean_memory_manager.remember(
            "Python is used for backend development.", importance=0.7, memory_type=MemoryType.LONG_TERM
        )
        clean_memory_manager.remember(
            "JavaScript is used for frontend development.", importance=0.7, memory_type=MemoryType.LONG_TERM
        )
        clean_memory_manager.remember(
            "Rust is a systems programming language.", importance=0.5, memory_type=MemoryType.LONG_TERM
        )

        results = clean_memory_manager.recall_relevant("Python", limit=5)
        assert "Python" in results
        assert "backend" in results

        results_js = clean_memory_manager.recall_relevant("JavaScript", limit=5)
        assert "JavaScript" in results_js

    def test_memory_summarize_fallback(self, clean_memory_manager):
        clean_memory_manager.remember("User: I need help with Python.", importance=0.5)
        clean_memory_manager.remember("Assistant: Sure, what do you need?", importance=0.5)
        clean_memory_manager.remember("User: I want to learn about decorators.", importance=0.6)

        import asyncio

        summary = asyncio.run(clean_memory_manager.summarize(max_summary_tokens=100))
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_memory_store_direct(self):
        store = MemoryStore(max_short_term=5, max_long_term=10)
        entry = store.add_short_term("Test memory", importance=0.8, source="test")
        assert entry.content == "Test memory"
        assert entry.importance == 0.8
        assert entry.memory_type == MemoryType.SHORT_TERM
        assert entry.metadata["source"] == "test"

        short = store.get_short_term()
        assert len(short) == 1

    def test_memory_entry_serialization(self):
        entry = MemoryEntry(
            id="mem_123",
            content="Test content",
            memory_type=MemoryType.SEMANTIC,
            importance=0.75,
            metadata={"key": "value"},
        )

        d = entry.to_dict()
        assert d["id"] == "mem_123"
        assert d["content"] == "Test content"
        assert d["memory_type"] == "semantic"
        assert d["importance"] == 0.75
        assert d["metadata"]["key"] == "value"

    def test_memory_manager_singleton(self):
        mgr1 = get_memory_manager()
        mgr2 = get_memory_manager()
        assert mgr1 is mgr2

    def test_memory_stats(self, clean_memory_manager):
        clean_memory_manager.remember("Entry 1", importance=0.5, memory_type=MemoryType.SHORT_TERM)
        clean_memory_manager.remember("Entry 2", importance=0.7, memory_type=MemoryType.LONG_TERM)
        clean_memory_manager.remember("Entry 3", importance=0.6, memory_type=MemoryType.LONG_TERM)

        stats = clean_memory_manager.get_stats()
        assert stats["short_term_count"] == 1
        assert stats["long_term_count"] == 2
        assert stats["total"] == 3

    def test_memory_clear(self, clean_memory_manager):
        clean_memory_manager.remember("Will be cleared", importance=0.5)
        clean_memory_manager.remember("Also cleared", importance=0.6, memory_type=MemoryType.LONG_TERM)

        assert clean_memory_manager.get_stats()["total"] == 2

        clean_memory_manager.clear()
        assert clean_memory_manager.get_stats()["total"] == 0


# ─── TestDataAISDK ────────────────────────────────────────────────────────────


class TestDataAISDK:
    def test_create_client_defaults(self):
        client = create_client(model="gpt-4o", provider="openai", api_key="test-key")
        assert isinstance(client, DataAI)
        assert client.model == "gpt-4o"
        assert client.provider == "openai"
        assert client.llm.get_default_model() == "default"

    def test_create_client_with_custom_config(self):
        client = create_client(
            model="deepseek-chat",
            provider="deepseek",
            api_key="custom-key",
            base_url="https://custom.api.com",
        )
        assert client.model == "deepseek-chat"
        assert client.provider == "deepseek"

    def test_data_ai_with_system_prompt(self):
        client = DataAI(
            model="gpt-4o",
            provider="openai",
            api_key="test-key",
            system_prompt="You are a Python expert.",
        )

        assert client.get_system_prompt() == "You are a Python expert."

    def test_data_ai_default_system_prompt(self):
        client = DataAI(model="gpt-4o", provider="openai", api_key="test-key")
        assert "helpful" in client.get_system_prompt().lower()

    def test_data_ai_rag_property(self):
        client = DataAI(
            model="gpt-4o",
            provider="openai",
            api_key="test-key",
            rag_config={"embedder": MockEmbedder()},
        )
        rag = client.rag
        assert isinstance(rag, RAGPipeline)
        assert client.rag is rag

    def test_data_ai_memory_property(self):
        client = DataAI(model="gpt-4o", provider="openai", api_key="test-key")
        assert isinstance(client.memory, MemoryManager)

    def test_data_ai_tools_property(self):
        client = DataAI(model="gpt-4o", provider="openai", api_key="test-key")
        assert isinstance(client.tools, ToolRegistry)

    def test_data_ai_llm_property(self):
        client = DataAI(model="gpt-4o", provider="openai", api_key="test-key")
        assert isinstance(client.llm, LLMManager)

    def test_data_ai_add_and_search_documents(self):
        client = DataAI(
            model="gpt-4o",
            provider="openai",
            api_key="test-key",
            rag_config={"embedder": MockEmbedder(), "top_k": 3},
        )

        count = client.add_documents(["Python is a programming language."])
        assert count == 1

        result = client.search_documents("Python", top_k=1)
        assert isinstance(result, str)
        assert "Python" in result

    def test_data_ai_remember_and_recall(self):
        client = DataAI(model="gpt-4o", provider="openai", api_key="test-key")
        client.remember("User is working on a web app.", importance=0.8)

        result = client.recall("web app", limit=5)
        assert "web app" in result

    def test_data_ai_isolated_state(self):
        client1 = DataAI(model="gpt-4o", provider="openai", api_key="key1")
        client2 = DataAI(model="gpt-4o", provider="openai", api_key="key2")

        client1.remember("From client 1", importance=0.5)
        client2.remember("From client 2", importance=0.5)

        assert "From client 1" in client1.recall("client 1", limit=5)
        assert "From client 2" in client2.recall("client 2", limit=5)

    def test_data_ai_share_global_state(self):
        global_mgr = get_memory_manager()
        global_mgr.clear()

        client = DataAI(
            model="gpt-4o",
            provider="openai",
            api_key="test-key",
            share_global=True,
        )
        assert client.memory is global_mgr

        client.remember("Shared memory entry", importance=0.8)
        assert "Shared memory entry" in global_mgr.recall_short_term()

        global_mgr.clear()

    def test_data_ai_with_all_providers(self):
        providers = [
            ("openai", ModelProvider.OPENAI),
            ("deepseek", ModelProvider.DEEPSEEK),
            ("siliconflow", ModelProvider.SILICONFLOW),
            ("azure", ModelProvider.AZURE),
        ]

        for provider_str, provider_enum in providers:
            kwargs = {}
            if provider_str == "azure":
                kwargs["base_url"] = "https://test.openai.azure.com"
            client = DataAI(
                model="test-model",
                provider=provider_str,
                api_key="test-key",
                **kwargs,
            )
            assert client.provider == provider_str
            assert client.llm.get_default_model() == "default"

    def test_data_ai_cleanup(self):
        import asyncio

        client = DataAI(
            model="gpt-4o",
            provider="openai",
            api_key="test-key",
            rag_config={"embedder": MockEmbedder()},
        )
        client.add_documents(["Test document"])
        assert client.rag.get_stats()["document_count"] == 1

        asyncio.run(client.cleanup())
        assert client.rag.get_stats()["document_count"] == 0
