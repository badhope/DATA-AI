"""
DATA-AI v2.0 RAG + Integration Tests

Tests RAG pipeline, vector store, memory manager, and tool registry integration
using the new v2.0 API.
"""

import sys
from pathlib import Path

import pytest

_SRC_DIR = Path(__file__).parent.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from data_ai.core.rag.pipeline import (
    BaseEmbedder,
    Document,
    InMemoryVectorStore,
    RAGPipeline,
    RetrievalResult,
    TextSplitter,
)


class MockEmbedder(BaseEmbedder):
    @property
    def dimension(self) -> int:
        return 128

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]

    async def aembed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self.dimension for _ in texts]


@pytest.fixture
def sample_documents():
    return [
        Document(content="Python is a high-level programming language.", metadata={"source": "python_intro"}),
        Document(
            content="Machine learning is a subset of artificial intelligence.", metadata={"source": "ai_overview"}
        ),
        Document(content="Deep learning uses neural networks with many layers.", metadata={"source": "ai_overview"}),
        Document(content="Natural language processing deals with text and speech.", metadata={"source": "nlp"}),
        Document(content="Reinforcement learning involves agents and environments.", metadata={"source": "rl"}),
    ]


@pytest.fixture
def mock_embedder():
    return MockEmbedder()


@pytest.fixture
def vector_store():
    return InMemoryVectorStore()


class TestRAGSearchIntegration:
    """Test RAG pipeline and search integration."""

    def test_create_pipeline_with_mock_embedder(self, mock_embedder):
        pipeline = RAGPipeline(embedder=mock_embedder)
        assert pipeline.embedder.dimension == 128
        assert pipeline.vector_store.count() == 0
        assert pipeline.top_k == 5

    def test_add_multiple_documents(self, mock_embedder, sample_documents):
        pipeline = RAGPipeline(embedder=mock_embedder)
        count = pipeline.add_documents(sample_documents)
        assert count > 0
        assert pipeline.vector_store.count() > 0

    def test_add_texts(self, mock_embedder):
        pipeline = RAGPipeline(embedder=mock_embedder)
        texts = ["First document about Python", "Second document about AI"]
        count = pipeline.add_texts(texts)
        assert count > 0

    def test_search_returns_retrieval_result(self, mock_embedder, sample_documents):
        pipeline = RAGPipeline(embedder=mock_embedder)
        pipeline.add_documents(sample_documents)

        result = pipeline.search("Python programming", top_k=2)
        assert isinstance(result, RetrievalResult)
        assert result.query == "Python programming"
        assert len(result.documents) <= 2
        assert len(result.scores) == len(result.documents)

    def test_query_returns_formatted_string(self, mock_embedder, sample_documents):
        pipeline = RAGPipeline(embedder=mock_embedder)
        pipeline.add_documents(sample_documents)

        result = pipeline.query("machine learning", top_k=3)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_query_with_empty_store(self, mock_embedder):
        pipeline = RAGPipeline(embedder=mock_embedder)
        result = pipeline.query("anything")
        assert result == ""

    def test_search_returns_empty_for_no_docs(self, mock_embedder):
        pipeline = RAGPipeline(embedder=mock_embedder)
        result = pipeline.search("anything")
        assert isinstance(result, RetrievalResult)
        assert len(result.documents) == 0

    def test_rag_with_custom_text_splitter(self, mock_embedder, sample_documents):
        pipeline = RAGPipeline(
            embedder=mock_embedder,
            text_splitter=TextSplitter(chunk_size=50, chunk_overlap=10),
        )
        count = pipeline.add_documents(sample_documents)
        assert count > 0

    def test_rag_pipeline_stats(self, mock_embedder, sample_documents):
        pipeline = RAGPipeline(embedder=mock_embedder)
        pipeline.add_documents(sample_documents)

        stats = pipeline.get_stats()
        assert stats["document_count"] == pipeline.vector_store.count()
        assert stats["embedder"] == "MockEmbedder"
        assert stats["dimension"] == 128

    def test_rag_pipeline_clear(self, mock_embedder, sample_documents):
        pipeline = RAGPipeline(embedder=mock_embedder)
        pipeline.add_documents(sample_documents)
        assert pipeline.vector_store.count() > 0

        pipeline.clear()
        assert pipeline.vector_store.count() == 0

    def test_retrieval_history(self, mock_embedder, sample_documents):
        pipeline = RAGPipeline(embedder=mock_embedder)
        pipeline.add_documents(sample_documents)

        pipeline.search("Python", top_k=1)
        pipeline.search("AI", top_k=2)

        history = pipeline.get_retrieval_history()
        assert len(history) == 2
        assert history[0].query == "Python"
        assert history[1].query == "AI"


class TestEmbeddingVectorStoreIntegration:
    """Test embedding and vector store working together."""

    def test_add_documents_to_store(self, mock_embedder, vector_store, sample_documents):
        embeddings = mock_embedder.embed([doc.content for doc in sample_documents])
        vector_store.add(sample_documents, embeddings)

        assert vector_store.count() == len(sample_documents)

    def test_search_in_store(self, mock_embedder, vector_store, sample_documents):
        embeddings = mock_embedder.embed([doc.content for doc in sample_documents])
        vector_store.add(sample_documents, embeddings)

        query_embedding = mock_embedder.embed(["Python"])[0]
        results = vector_store.search(query_embedding, top_k=3)
        assert len(results) <= 3
        assert len(results) > 0
        for doc, score in results:
            assert isinstance(doc, Document)
            assert isinstance(score, float)

    def test_empty_store_search(self, mock_embedder, vector_store):
        query_embedding = mock_embedder.embed(["anything"])[0]
        results = vector_store.search(query_embedding, top_k=5)
        assert results == []

    def test_clear_store(self, mock_embedder, vector_store, sample_documents):
        embeddings = mock_embedder.embed([doc.content for doc in sample_documents])
        vector_store.add(sample_documents, embeddings)
        assert vector_store.count() > 0

        vector_store.clear()
        assert vector_store.count() == 0

    def test_store_with_single_document(self, mock_embedder, vector_store):
        doc = Document(content="Single document", metadata={"source": "test"})
        emb = mock_embedder.embed([doc.content])
        vector_store.add([doc], emb)

        assert vector_store.count() == 1
        results = vector_store.search(emb[0], top_k=1)
        assert len(results) == 1
        assert results[0][0].content == "Single document"

    def test_store_count_after_multiple_adds(self, mock_embedder, vector_store):
        docs_batch1 = [Document(content=f"Doc {i} batch 1") for i in range(3)]
        docs_batch2 = [Document(content=f"Doc {i} batch 2") for i in range(2)]

        emb1 = mock_embedder.embed([d.content for d in docs_batch1])
        emb2 = mock_embedder.embed([d.content for d in docs_batch2])

        vector_store.add(docs_batch1, emb1)
        vector_store.add(docs_batch2, emb2)

        assert vector_store.count() == 5

    def test_rag_pipeline_with_custom_vector_store(self, mock_embedder, vector_store, sample_documents):
        pipeline = RAGPipeline(embedder=mock_embedder, vector_store=vector_store)
        pipeline.add_documents(sample_documents)
        assert pipeline.vector_store.count() == len(sample_documents)


class TestMemoryRAGIntegration:
    """Test memory manager and RAG pipeline integration."""

    def test_memory_and_rag_store_together(self):
        from data_ai.core.memory.manager import MemoryManager, MemoryType

        memory_mgr = MemoryManager()
        memory_mgr.remember(
            "User prefers Python for data science tasks",
            importance=0.9,
            memory_type=MemoryType.LONG_TERM,
        )
        memory_mgr.remember(
            "User is working on a machine learning project",
            importance=0.8,
            memory_type=MemoryType.LONG_TERM,
        )

        pipeline = RAGPipeline(embedder=MockEmbedder())
        pipeline.add_texts(
            [
                "Python has excellent libraries for data science: pandas, numpy, scikit-learn",
                "Machine learning frameworks include TensorFlow, PyTorch, and scikit-learn",
                "Data visualization can be done with matplotlib and seaborn",
            ]
        )

        recalled = memory_mgr.recall_long_term()
        assert "Python" in recalled
        assert "machine learning" in recalled

        rag_result = pipeline.query("data science tools", top_k=2)
        assert isinstance(rag_result, str)
        assert len(rag_result) > 0

        stats = memory_mgr.get_stats()
        assert stats["long_term_count"] == 2
        assert pipeline.vector_store.count() > 0

    def test_memory_recall_used_as_rag_context(self):
        from data_ai.core.memory.manager import MemoryManager, MemoryType

        memory_mgr = MemoryManager()
        memory_mgr.remember(
            "Project focus: natural language processing with transformers",
            importance=0.95,
            memory_type=MemoryType.LONG_TERM,
        )
        memory_mgr.remember(
            "Preferred framework: HuggingFace Transformers",
            importance=0.9,
            memory_type=MemoryType.LONG_TERM,
        )

        pipeline = RAGPipeline(embedder=MockEmbedder())
        pipeline.add_texts(
            [
                "Transformers architecture uses self-attention mechanisms",
                "BERT is a bidirectional transformer model",
                "GPT models use autoregressive transformer architecture",
            ]
        )

        memory_context = memory_mgr.recall_long_term()

        rag_result = pipeline.search("transformer models", top_k=3)
        assert len(rag_result.documents) > 0
        assert isinstance(memory_context, str)
        assert len(memory_context) > 0

    def test_memory_search_and_rag_combined(self):
        from data_ai.core.memory.manager import MemoryManager, MemoryType

        memory_mgr = MemoryManager()
        memory_mgr.remember(
            "User is interested in Python performance optimization",
            importance=0.85,
            memory_type=MemoryType.LONG_TERM,
        )
        memory_mgr.remember(
            "User uses VS Code as primary editor",
            importance=0.6,
        )
        memory_mgr.remember(
            "Project deadline is next month",
            importance=0.9,
            memory_type=MemoryType.LONG_TERM,
        )

        pipeline = RAGPipeline(embedder=MockEmbedder())
        pipeline.add_texts(
            [
                "Python performance can be improved with Cython and Numba",
                "AsyncIO provides asynchronous programming in Python",
                "Profiling tools include cProfile and line_profiler",
            ]
        )

        relevant_memories = memory_mgr.recall_relevant("Python performance", limit=5)
        assert "performance" in relevant_memories.lower()

        rag_result = pipeline.query("Python optimization", top_k=3)
        assert isinstance(rag_result, str)

    def test_memory_manager_singleton(self):
        from data_ai.core.memory.manager import get_memory_manager

        mgr1 = get_memory_manager()
        mgr2 = get_memory_manager()
        assert mgr1 is mgr2


class TestToolRAGIntegration:
    """Test tool registry and RAG pipeline integration."""

    def test_tool_registry_with_rag_context(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        pipeline = RAGPipeline(embedder=MockEmbedder())
        pipeline.add_texts(
            [
                "Python math operations include addition, subtraction, multiplication, division",
                "Complex calculations can use the math module",
                "Built-in functions include abs, round, pow, sum, min, max",
            ]
        )

        assert registry.get_tool_count() > 0
        assert "calculate" in registry.list_tools()

        rag_result = pipeline.query("math operations in Python", top_k=2)
        assert isinstance(rag_result, str)
        assert len(rag_result) > 0

    def test_tool_registry_custom_function(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()

        def summarize_text(text: str) -> str:
            return text[:100] + "..." if len(text) > 100 else text

        registry.register(
            name="summarize",
            description="Summarize a text to 100 characters",
            parameters={"text": {"type": "string", "description": "Text to summarize"}},
            required=["text"],
            function=summarize_text,
        )

        pipeline = RAGPipeline(embedder=MockEmbedder())
        pipeline.add_texts(
            [
                "Artificial intelligence is transforming industries across the globe",
                "Healthcare AI can diagnose diseases from medical imaging",
                "Autonomous vehicles use AI for navigation and obstacle detection",
            ]
        )

        assert "summarize" in registry.list_tools()
        tool_def = registry.get("summarize")
        assert tool_def is not None
        assert tool_def.name == "summarize"

        rag_result = pipeline.search("AI in healthcare", top_k=2)
        assert len(rag_result.documents) > 0

    def test_tool_registry_singleton(self):
        from data_ai.core.tool.registry import get_tool_registry

        registry1 = get_tool_registry()
        registry2 = get_tool_registry()
        assert registry1 is registry2

    def test_tool_result_as_rag_query(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()

        pipeline = RAGPipeline(embedder=MockEmbedder())
        pipeline.add_texts(
            [
                "Python is a versatile programming language",
                "Python excels in data analysis and machine learning",
                "Python web frameworks include Django, Flask, and FastAPI",
            ]
        )

        tool = registry.get("calculate")
        assert tool is not None
        assert tool.name == "calculate"

        search_result = pipeline.search("Python programming", top_k=2)
        assert len(search_result.documents) > 0

    def test_tool_registry_clear_and_repopulate(self):
        from data_ai.core.tool.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register_builtin_tools()
        assert registry.get_tool_count() > 0

        registry.clear()
        assert registry.get_tool_count() == 0

        registry.register(
            name="rag_search",
            description="Search the RAG knowledge base",
            parameters={"query": {"type": "string", "description": "Search query"}},
            required=["query"],
            function=lambda query: f"Searching for: {query}",
        )

        pipeline = RAGPipeline(embedder=MockEmbedder())
        pipeline.add_texts(["Knowledge base entry one", "Knowledge base entry two"])

        assert "rag_search" in registry.list_tools()
        assert pipeline.vector_store.count() == 2
