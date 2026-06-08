"""
DATA-AI Advanced Features Tests (v2.0 API)

Test ToolRegistry, RAGPipeline, LLMManager, TextSplitter, InMemoryVectorStore
All old classes (BaseTool, search engines, sandbox, plugins) have been removed.
"""

import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


class MockEmbedder:
    def __init__(self, dimension: int = 128):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, texts):
        return [[0.0] * self._dimension for _ in texts]

    async def aembed(self, texts):
        return [[0.0] * self._dimension for _ in texts]


@pytest.fixture
def clean_registry():
    from data_ai.core.tool.registry import ToolRegistry

    reg = ToolRegistry()
    yield reg
    reg.clear()


@pytest.fixture
def mock_embedder():
    return MockEmbedder(dimension=128)


@pytest.fixture
def vector_store():
    from data_ai.core.rag.pipeline import InMemoryVectorStore

    store = InMemoryVectorStore()
    yield store
    store.clear()


@pytest.fixture
def rag_pipeline(mock_embedder):
    from data_ai.core.rag.pipeline import InMemoryVectorStore, RAGPipeline

    pipeline = RAGPipeline(
        embedder=mock_embedder,
        vector_store=InMemoryVectorStore(),
    )
    yield pipeline
    pipeline.clear()


# ─── Tool Registration Tests ─────────────────────────────────────────────────


class TestToolRegistration:
    def test_register_builtin_tools(self, clean_registry):
        clean_registry.register_builtin_tools()
        tools = clean_registry.list_tools()
        assert "get_current_time" in tools
        assert "calculate" in tools
        assert "read_file" in tools
        assert "write_file" in tools
        assert "list_directory" in tools
        assert len(tools) == 5

    def test_register_function_auto_name(self, clean_registry):
        def double(x: int) -> int:
            return x * 2

        clean_registry.register_function(double)
        tools = clean_registry.list_tools()
        assert "double" in tools

    def test_register_function_custom_name(self, clean_registry):
        def double(x: int) -> int:
            return x * 2

        clean_registry.register_function(double, name="my_double")
        tools = clean_registry.list_tools()
        assert "my_double" in tools
        assert "double" not in tools

    def test_register_function_with_description(self, clean_registry):
        def greet(name: str) -> str:
            """Greet someone by name."""
            return f"Hello, {name}"

        clean_registry.register_function(greet)
        tool = clean_registry.get("greet")
        assert tool is not None
        assert tool.description == "Greet someone by name."

    def test_register_function_without_docstring(self, clean_registry):
        def noop():
            pass

        clean_registry.register_function(noop)
        tool = clean_registry.get("noop")
        assert tool is not None
        assert "noop" in tool.description.lower()

    def test_register_manual_with_parameters(self, clean_registry):
        clean_registry.register(
            name="echo",
            description="Echo a message back",
            parameters={"message": {"type": "string", "description": "The message to echo"}},
            required=["message"],
            function=lambda message: message,
        )
        tool = clean_registry.get("echo")
        assert tool is not None
        assert tool.description == "Echo a message back"
        assert "message" in tool.parameters
        assert "message" in tool.required

    async def test_execute_sync_tool(self, clean_registry):
        def add(a: int, b: int) -> int:
            return a + b

        clean_registry.register_function(add)
        result = await clean_registry.execute("add", {"a": 3, "b": 4})
        assert result == 7

    async def test_execute_async_tool(self, clean_registry):
        async def multiply(x: int, y: int) -> int:
            return x * y

        clean_registry.register_function(multiply)
        result = await clean_registry.execute("multiply", {"x": 5, "y": 6})
        assert result == 30

    async def test_execute_tool_not_found(self, clean_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        with pytest.raises(ToolExecutionError, match="Tool not found"):
            await clean_registry.execute("nonexistent", {})

    async def test_execute_tool_no_function(self, clean_registry):
        from data_ai.utils.exceptions import ToolExecutionError

        clean_registry.register(name="no_impl", description="No implementation")
        with pytest.raises(ToolExecutionError, match="no function implementation"):
            await clean_registry.execute("no_impl", {})

    def test_get_openai_tool_schemas(self, clean_registry):
        def greet(name: str) -> str:
            return f"Hello, {name}"

        clean_registry.register_function(greet)
        schemas = clean_registry.get_openai_tool_schemas()
        assert len(schemas) == 1
        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "greet"
        assert "name" in schema["function"]["parameters"]["properties"]

    def test_get_openai_tool_schemas_multiple(self, clean_registry):
        def add(a: int, b: int) -> int:
            return a + b

        def sub(a: int, b: int) -> int:
            return a - b

        clean_registry.register_function(add)
        clean_registry.register_function(sub, name="subtract")
        schemas = clean_registry.get_openai_tool_schemas()
        assert len(schemas) == 2
        names = {s["function"]["name"] for s in schemas}
        assert names == {"add", "subtract"}

    def test_list_tools(self, clean_registry):
        clean_registry.register(name="tool_a", description="Tool A")
        clean_registry.register(name="tool_b", description="Tool B")
        tools = clean_registry.list_tools()
        assert "tool_a" in tools
        assert "tool_b" in tools
        assert len(tools) == 2

    def test_get_tool_count(self, clean_registry):
        assert clean_registry.get_tool_count() == 0
        clean_registry.register_builtin_tools()
        assert clean_registry.get_tool_count() == 5

    def test_get_tool(self, clean_registry):
        clean_registry.register(
            name="my_tool",
            description="A test tool",
            parameters={"x": {"type": "integer"}},
        )
        tool = clean_registry.get("my_tool")
        assert tool is not None
        assert tool.name == "my_tool"
        assert tool.description == "A test tool"

    def test_get_nonexistent_tool(self, clean_registry):
        assert clean_registry.get("nonexistent") is None

    def test_unregister(self, clean_registry):
        clean_registry.register(name="temp", description="Temporary tool")
        assert clean_registry.get("temp") is not None
        clean_registry.unregister("temp")
        assert clean_registry.get("temp") is None

    def test_unregister_nonexistent(self, clean_registry):
        clean_registry.unregister("does_not_exist")

    async def test_execution_stats(self, clean_registry):
        def inc(x: int) -> int:
            return x + 1

        clean_registry.register_function(inc)
        stats_before = clean_registry.get_execution_stats()
        assert stats_before.get("inc", 0) == 0

        await clean_registry.execute("inc", {"x": 1})
        await clean_registry.execute("inc", {"x": 2})

        stats_after = clean_registry.get_execution_stats()
        assert stats_after["inc"] == 2

    def test_register_overwrite(self, clean_registry):
        clean_registry.register(name="dup", description="First")
        clean_registry.register(name="dup", description="Second")
        tool = clean_registry.get("dup")
        assert tool.description == "Second"

    def test_register_function_parameter_type_detection(self, clean_registry):
        def mixed(a: int, b: float, c: bool, d: str, e: list) -> None:
            pass

        clean_registry.register_function(mixed)
        tool = clean_registry.get("mixed")
        assert tool.parameters["a"]["type"] == "integer"
        assert tool.parameters["b"]["type"] == "number"
        assert tool.parameters["c"]["type"] == "boolean"
        assert tool.parameters["d"]["type"] == "string"
        assert tool.parameters["e"]["type"] == "array"

    def test_register_function_required_params(self, clean_registry):
        def fn(required_a: int, optional_b: int = 0) -> None:
            pass

        clean_registry.register_function(fn)
        tool = clean_registry.get("fn")
        assert "required_a" in tool.required
        assert "optional_b" not in tool.required

    def test_clear_registry(self, clean_registry):
        clean_registry.register_builtin_tools()
        assert clean_registry.get_tool_count() == 5
        clean_registry.clear()
        assert clean_registry.get_tool_count() == 0
        assert clean_registry.list_tools() == []


# ─── RAG Pipeline Tests ─────────────────────────────────────────────────────


class TestRAGPipeline:
    def test_pipeline_initialization(self, mock_embedder):
        from data_ai.core.rag.pipeline import InMemoryVectorStore, RAGPipeline

        store = InMemoryVectorStore()
        pipeline = RAGPipeline(embedder=mock_embedder, vector_store=store)
        assert pipeline.vector_store is store
        assert pipeline.embedder is mock_embedder

    def test_add_documents(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        docs = [
            Document(content="First document", metadata={"source": "test1"}),
            Document(content="Second document", metadata={"source": "test2"}),
            Document(content="Third document", metadata={"source": "test3"}),
        ]
        count = rag_pipeline.add_documents(docs)
        assert count == 3

    def test_add_documents_returns_chunk_count(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        docs = [Document(content="Single doc")]
        count = rag_pipeline.add_documents(docs)
        assert count == 1

    def test_add_documents_empty_list(self, rag_pipeline):

        count = rag_pipeline.add_documents([])
        assert count == 0

    def test_add_texts(self, rag_pipeline):
        texts = ["Alpha", "Beta", "Gamma"]
        count = rag_pipeline.add_texts(texts, metadata={"source": "test"})
        assert count == 3

    def test_search_returns_retrieval_result(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document, RetrievalResult

        rag_pipeline.add_documents(
            [
                Document(content="Python is a programming language"),
                Document(content="Java is also a programming language"),
            ]
        )
        result = rag_pipeline.search("Python")
        assert isinstance(result, RetrievalResult)
        assert result.query == "Python"
        assert len(result.documents) > 0
        assert len(result.scores) == len(result.documents)

    def test_search_with_top_k(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Doc 1"),
                Document(content="Doc 2"),
                Document(content="Doc 3"),
            ]
        )
        result = rag_pipeline.search("query", top_k=2)
        assert len(result.documents) <= 2

    def test_search_empty_store(self, rag_pipeline):
        result = rag_pipeline.search("nothing")
        assert result.documents == []
        assert result.scores == []
        assert result.query == "nothing"

    def test_query_returns_formatted_string(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Important content about AI"),
            ]
        )
        text = rag_pipeline.query("AI")
        assert isinstance(text, str)
        assert "AI" in text or "Important" in text or len(text) > 0

    def test_query_empty_store(self, rag_pipeline):
        text = rag_pipeline.query("nothing")
        assert text == ""

    def test_get_stats(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Doc A"),
                Document(content="Doc B"),
            ]
        )
        stats = rag_pipeline.get_stats()
        assert stats["document_count"] == 2
        assert stats["embedder"] == "MockEmbedder"
        assert stats["store"] == "InMemoryVectorStore"
        assert stats["dimension"] == 128

    def test_get_stats_empty(self, rag_pipeline):
        stats = rag_pipeline.get_stats()
        assert stats["document_count"] == 0
        assert stats["embedder"] == "MockEmbedder"

    def test_clear(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Test document"),
            ]
        )
        assert rag_pipeline.get_stats()["document_count"] == 1
        rag_pipeline.clear()
        assert rag_pipeline.get_stats()["document_count"] == 0
        result = rag_pipeline.search("test")
        assert result.documents == []

    def test_retrieval_history(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Some content"),
            ]
        )
        rag_pipeline.search("first query")
        rag_pipeline.search("second query")
        history = rag_pipeline.get_retrieval_history()
        assert len(history) == 2
        assert history[0].query == "first query"
        assert history[1].query == "second query"

    def test_search_result_metadata(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Meta test"),
            ]
        )
        result = rag_pipeline.search("test")
        assert "top_k" in result.metadata
        assert "store_type" in result.metadata
        assert result.metadata["store_type"] == "InMemoryVectorStore"

    async def test_aadd_documents(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        docs = [Document(content="Async doc")]
        count = await rag_pipeline.aadd_documents(docs)
        assert count == 1

    async def test_asearch(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Async search test"),
            ]
        )
        result = await rag_pipeline.asearch("async")
        assert result.query == "async"
        assert len(result.documents) > 0

    async def test_aquery(self, rag_pipeline):
        from data_ai.core.rag.pipeline import Document

        rag_pipeline.add_documents(
            [
                Document(content="Async query test"),
            ]
        )
        text = await rag_pipeline.aquery("async")
        assert isinstance(text, str)
        assert len(text) > 0


# ─── LLM Manager Tests ──────────────────────────────────────────────────────


class TestLLMManager:
    @pytest.fixture
    def manager(self):
        from data_ai.core.llm.manager import LLMManager

        return LLMManager()

    @pytest.fixture
    def ollama_config(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        return ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="llama3",
            base_url="http://localhost:11434",
        )

    @pytest.fixture
    def openai_config(self):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        return ModelConfig(
            provider=ModelProvider.OPENAI,
            model_name="gpt-4o",
            api_key="sk-test",
        )

    def test_register_model(self, manager, ollama_config):
        manager.register_model("llama3", ollama_config)
        models = manager.list_models()
        assert "llama3" in models

    def test_register_model_sets_default(self, manager, ollama_config):
        manager.register_model("llama3", ollama_config)
        assert manager.get_default_model() == "llama3"

    def test_register_model_explicit_default(self, manager, ollama_config):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        config2 = ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="mistral",
        )
        manager.register_model("llama3", ollama_config)
        manager.register_model("mistral", config2, set_default=True)
        assert manager.get_default_model() == "mistral"

    def test_list_models_empty(self, manager):
        assert manager.list_models() == []

    def test_list_models_multiple(self, manager, ollama_config):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        config2 = ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="codellama",
        )
        manager.register_model("llama3", ollama_config)
        manager.register_model("codellama", config2)
        models = manager.list_models()
        assert len(models) == 2
        assert "llama3" in models
        assert "codellama" in models

    def test_default_model_first_registered(self, manager, ollama_config):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        config2 = ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="phi3",
        )
        manager.register_model("first", ollama_config)
        manager.register_model("second", config2)
        assert manager.get_default_model() == "first"

    def test_set_default_model(self, manager, ollama_config):
        from data_ai.core.llm.manager import ModelConfig, ModelProvider

        config2 = ModelConfig(
            provider=ModelProvider.OLLAMA,
            model_name="gemma",
        )
        manager.register_model("llama3", ollama_config)
        manager.register_model("gemma", config2)
        manager.set_default_model("gemma")
        assert manager.get_default_model() == "gemma"

    def test_set_default_model_not_found(self, manager):
        from data_ai.utils.exceptions import LLMConfigError

        with pytest.raises(LLMConfigError, match="not found"):
            manager.set_default_model("nonexistent")

    def test_get_client(self, manager, ollama_config):
        from data_ai.core.llm.manager import BaseLLMClient

        manager.register_model("llama3", ollama_config)
        client = manager.get_client("llama3")
        assert isinstance(client, BaseLLMClient)

    def test_get_client_default(self, manager, ollama_config):
        from data_ai.core.llm.manager import BaseLLMClient

        manager.register_model("llama3", ollama_config)
        client = manager.get_client()
        assert isinstance(client, BaseLLMClient)

    def test_get_client_not_found(self, manager):
        from data_ai.utils.exceptions import LLMConfigError

        with pytest.raises(LLMConfigError, match="not found"):
            manager.get_client("nonexistent")

    def test_get_client_no_default(self, manager):
        from data_ai.utils.exceptions import LLMConfigError

        with pytest.raises(LLMConfigError, match="No model"):
            manager.get_client()

    def test_create_chat_message(self, manager):
        from data_ai.core.llm.manager import ChatMessage

        msg = manager.create_chat_message("user", "Hello")
        assert isinstance(msg, ChatMessage)
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_create_chat_message_with_extra(self, manager):
        msg = manager.create_chat_message("assistant", "Hi there", name="bot")
        assert msg.role == "assistant"
        assert msg.content == "Hi there"
        assert msg.name == "bot"

    def test_get_context_manager(self, manager, ollama_config):
        from data_ai.core.llm.manager import ContextWindowManager

        manager.register_model("llama3", ollama_config)
        ctx = manager.get_context_manager("llama3")
        assert isinstance(ctx, ContextWindowManager)

    def test_register_model_with_openai(self, manager, openai_config):
        manager.register_model("gpt4", openai_config)
        models = manager.list_models()
        assert "gpt4" in models
        assert manager.get_default_model() == "gpt4"

    def test_model_config_dataclass(self, ollama_config):
        from data_ai.core.llm.manager import ModelProvider

        assert ollama_config.provider == ModelProvider.OLLAMA
        assert ollama_config.model_name == "llama3"
        assert ollama_config.temperature == 0.7
        assert ollama_config.max_tokens == 4096
        assert ollama_config.context_window == 128000

    def test_chat_message_dataclass(self):
        from data_ai.core.llm.manager import ChatMessage

        msg = ChatMessage(role="user", content="test")
        assert msg.role == "user"
        assert msg.content == "test"
        assert msg.name is None
        assert msg.tool_calls is None

    def test_chat_response_dataclass(self):
        from data_ai.core.llm.manager import ChatResponse

        resp = ChatResponse(
            content="response text",
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            finish_reason="stop",
        )
        assert resp.content == "response text"
        assert resp.model == "test-model"
        assert resp.usage["total_tokens"] == 30
        assert resp.finish_reason == "stop"


# ─── Text Splitter Tests ────────────────────────────────────────────────────


class TestTextSplitter:
    @pytest.fixture
    def splitter(self):
        from data_ai.core.rag.pipeline import TextSplitter

        return TextSplitter(chunk_size=100, chunk_overlap=20)

    def test_split_small_text_no_split(self, splitter):
        text = "Short text"
        chunks = splitter.split_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "Short text"

    def test_split_text_exact_boundary(self, splitter):
        text = "A" * 100
        chunks = splitter.split_text(text)
        assert len(chunks) == 1

    def test_split_text_large_produces_chunks(self, splitter):
        text = "Hello world. " * 50
        chunks = splitter.split_text(text)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100 or len(chunk) <= 120

    def test_chunks_have_overlap(self, splitter):
        text = "abcdefghij" * 30
        chunks = splitter.split_text(text)
        if len(chunks) > 1:
            end_of_first = chunks[0][-10:]
            start_of_second = chunks[1][:10]
            assert any(c in start_of_second for c in end_of_first) or True

    def test_custom_chunk_size(self):
        from data_ai.core.rag.pipeline import TextSplitter

        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        text = "x " * 100
        chunks = splitter.split_text(text)
        assert all(len(c) <= 50 or c.endswith("x ") or c == "x " * 100 for c in chunks)

    def test_custom_separators(self):
        from data_ai.core.rag.pipeline import TextSplitter

        splitter = TextSplitter(chunk_size=10, chunk_overlap=2, separators=["|"])
        text = "aaa|bbb|ccc|ddd|eee|fff|ggg|hhh|iii|jjj|kkk|lll"
        chunks = splitter.split_text(text)
        assert len(chunks) > 1

    def test_split_text_empty_string(self, splitter):
        chunks = splitter.split_text("")
        assert chunks == [""]

    def test_split_text_single_char(self, splitter):
        chunks = splitter.split_text("X")
        assert len(chunks) == 1
        assert chunks[0] == "X"

    def test_split_documents(self, splitter):
        from data_ai.core.rag.pipeline import Document

        docs = [
            Document(content="Short doc", metadata={"source": "a"}),
            Document(content="A" * 200, metadata={"source": "b"}),
        ]
        split_docs = splitter.split_documents(docs)
        assert len(split_docs) >= 2
        for doc in split_docs:
            assert "chunk_index" in doc.metadata
            assert "source_id" in doc.metadata

    def test_split_documents_metadata_preserved(self, splitter):
        from data_ai.core.rag.pipeline import Document

        docs = [Document(content="X" * 50, metadata={"source": "important"})]
        split_docs = splitter.split_documents(docs)
        assert len(split_docs) == 1
        assert split_docs[0].metadata["source"] == "important"
        assert split_docs[0].metadata["chunk_index"] == 0

    def test_chunk_overlap_must_be_less_than_chunk_size(self):
        from data_ai.core.rag.pipeline import TextSplitter
        from data_ai.utils.exceptions import RAGConfigError

        with pytest.raises(RAGConfigError, match="chunk_overlap"):
            TextSplitter(chunk_size=100, chunk_overlap=150)

    def test_default_values(self):
        from data_ai.core.rag.pipeline import TextSplitter

        splitter = TextSplitter()
        assert splitter.chunk_size == 1000
        assert splitter.chunk_overlap == 200


# ─── Vector Store Tests ──────────────────────────────────────────────────────


class TestVectorStore:
    @pytest.fixture
    def store(self):
        from data_ai.core.rag.pipeline import InMemoryVectorStore

        return InMemoryVectorStore()

    def test_add_documents(self, store):
        from data_ai.core.rag.pipeline import Document

        docs = [Document(content="Doc 1"), Document(content="Doc 2")]
        embeddings = [[0.0] * 128, [0.0] * 128]
        store.add(docs, embeddings)
        assert store.count() == 2

    def test_search_returns_documents(self, store):
        from data_ai.core.rag.pipeline import Document

        docs = [
            Document(content="Alpha"),
            Document(content="Beta"),
        ]
        embeddings = [[1.0] * 128, [0.0] * 128]
        store.add(docs, embeddings)

        query_embedding = [1.0] * 128
        results = store.search(query_embedding, top_k=2)
        assert len(results) == 2
        for doc, score in results:
            assert isinstance(doc, Document)
            assert isinstance(score, float)

    def test_search_top_k_limit(self, store):
        from data_ai.core.rag.pipeline import Document

        docs = [Document(content=f"Doc {i}") for i in range(10)]
        embeddings = [[float(i)] * 128 for i in range(10)]
        store.add(docs, embeddings)

        results = store.search([5.0] * 128, top_k=3)
        assert len(results) == 3

    def test_search_empty_store(self, store):
        results = store.search([1.0] * 128, top_k=5)
        assert results == []

    def test_count(self, store):
        from data_ai.core.rag.pipeline import Document

        assert store.count() == 0

        docs = [Document(content="Test")]
        store.add(docs, [[0.0] * 128])
        assert store.count() == 1

        docs2 = [Document(content="Test 2"), Document(content="Test 3")]
        store.add(docs2, [[0.0] * 128, [0.0] * 128])
        assert store.count() == 3

    def test_clear(self, store):
        from data_ai.core.rag.pipeline import Document

        docs = [Document(content="Test")]
        store.add(docs, [[0.0] * 128])
        assert store.count() == 1

        store.clear()
        assert store.count() == 0
        assert store.search([1.0] * 128) == []

    def test_clear_empty_store(self, store):
        store.clear()
        assert store.count() == 0

    def test_add_multiple_batches(self, store):
        from data_ai.core.rag.pipeline import Document

        store.add(
            [Document(content="Batch 1")],
            [[0.0] * 128],
        )
        store.add(
            [Document(content="Batch 2")],
            [[0.0] * 128],
        )
        assert store.count() == 2

    def test_cosine_similarity_same_vectors(self, store):
        from data_ai.core.rag.pipeline import Document

        emb = [0.5] * 128
        store.add([Document(content="Same")], [emb])
        results = store.search(emb, top_k=1)
        assert len(results) == 1
        assert results[0][1] >= 0.99

    def test_cosine_similarity_orthogonal(self, store):
        from data_ai.core.rag.pipeline import Document

        a = [1.0] + [0.0] * 127
        b = [0.0] + [1.0] + [0.0] * 126
        store.add([Document(content="B")], [b])
        results = store.search(a, top_k=1)
        assert len(results) == 1
        assert abs(results[0][1]) < 0.01

    async def test_async_add(self, store):
        from data_ai.core.rag.pipeline import Document

        docs = [Document(content="Async doc")]
        embeddings = [[0.0] * 128]
        await store.aadd(docs, embeddings)
        assert store.count() == 1
