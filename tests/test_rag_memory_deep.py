"""
DATA-AI 深度测试套件 — RAG / Memory / Reasoning 层
"""


class TestTextSplitterBoundary:
    def test_empty_text(self):
        from data_ai.core.rag.pipeline import TextSplitter

        s = TextSplitter(chunk_size=100, chunk_overlap=20)
        chunks = s.split_text("")
        assert chunks == [""]

    def test_single_char(self):
        from data_ai.core.rag.pipeline import TextSplitter

        s = TextSplitter(chunk_size=100, chunk_overlap=20)
        chunks = s.split_text("A")
        assert chunks == ["A"]

    def test_exact_chunk_size(self):
        from data_ai.core.rag.pipeline import TextSplitter

        s = TextSplitter(chunk_size=10, chunk_overlap=2)
        text = "0123456789"
        chunks = s.split_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "0123456789"

    def test_custom_separators(self):
        from data_ai.core.rag.pipeline import TextSplitter

        s = TextSplitter(chunk_size=50, chunk_overlap=5, separators=["|", ",", " "])
        text = "hello world|this is a test|final section"
        chunks = s.split_text(text)
        assert len(chunks) >= 1

    def test_multilingual_text(self):
        from data_ai.core.rag.pipeline import TextSplitter

        s = TextSplitter(chunk_size=100, chunk_overlap=20)
        text = "这是中文。This is English。混合文本测试。" * 10
        chunks = s.split_text(text)
        assert len(chunks) > 1

    def test_chunk_size_1(self):
        from data_ai.core.rag.pipeline import TextSplitter

        s = TextSplitter(chunk_size=10, chunk_overlap=5)
        text = "ABCDEFGHIJKLMNOP"
        chunks = s.split_text(text)
        assert all(len(c) <= 10 + 5 for c in chunks)

    def test_overlap_consistency(self):
        from data_ai.core.rag.pipeline import TextSplitter

        s = TextSplitter(chunk_size=50, chunk_overlap=10)
        text = "a" * 200
        chunks = s.split_text(text)
        for i in range(len(chunks) - 1):
            assert chunks[i][-10:] == chunks[i + 1][:10]


class TestInMemoryVectorStore:
    def test_add_and_count(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        store.add([Document(content="doc1"), Document(content="doc2")], [[0.1] * 10, [0.2] * 10])
        assert store.count() == 2

    def test_search_returns_correct_count(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        store.add([Document(content=f"doc{i}") for i in range(10)], [[float(i) / 10] * 10 for i in range(10)])
        results = store.search([0.5] * 10, top_k=3)
        assert len(results) == 3

    def test_search_empty_store(self):
        from data_ai.core.rag.pipeline import InMemoryVectorStore

        store = InMemoryVectorStore()
        results = store.search([0.5] * 10)
        assert results == []

    def test_clear(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        store.add([Document(content="test")], [[0.1] * 10])
        assert store.count() == 1
        store.clear()
        assert store.count() == 0

    def test_cosine_similarity_perfect_match(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        emb = [1.0, 0.0, 0.0]
        store.add([Document(content="perfect")], [emb])
        results = store.search(emb, top_k=1)
        assert abs(results[0][1] - 1.0) < 0.001

    def test_cosine_similarity_orthogonal(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        store.add([Document(content="doc")], [[1.0, 0.0]])
        results = store.search([0.0, 1.0], top_k=1)
        assert abs(results[0][1] - 0.0) < 0.001

    def test_add_batch_large(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        n = 100
        docs = [Document(content=f"doc{i}") for i in range(n)]
        embs = [[float(i) / 1000] * 10 for i in range(n)]
        store.add(docs, embs)
        assert store.count() == n

    def test_search_zero_vector(self):
        from data_ai.core.rag.pipeline import Document, InMemoryVectorStore

        store = InMemoryVectorStore()
        store.add([Document(content="test")], [[0.0] * 10])
        results = store.search([0.0] * 10, top_k=1)
        assert results[0][1] == 0.0


class TestRAGPipelineErrors:
    def test_add_zero_documents(self):
        from data_ai.core.rag.pipeline import BaseEmbedder, InMemoryVectorStore, RAGPipeline

        class MockEmbedder(BaseEmbedder):
            @property
            def dimension(self):
                return 128

            def embed(self, texts):
                return [[0.0] * 128 for _ in texts]

            async def aembed(self, texts):
                return [[0.0] * 128 for _ in texts]

        pipeline = RAGPipeline(vector_store=InMemoryVectorStore(), embedder=MockEmbedder())
        count = pipeline.add_documents([])
        assert count == 0

    def test_search_empty_store(self):
        from data_ai.core.rag.pipeline import BaseEmbedder, InMemoryVectorStore, RAGPipeline

        class MockEmbedder(BaseEmbedder):
            @property
            def dimension(self):
                return 128

            def embed(self, texts):
                return [[0.0] * 128 for _ in texts]

            async def aembed(self, texts):
                return [[0.0] * 128 for _ in texts]

        pipeline = RAGPipeline(vector_store=InMemoryVectorStore(), embedder=MockEmbedder())
        result = pipeline.query("test query")
        assert result == ""

    def test_get_stats_empty(self):
        from data_ai.core.rag.pipeline import BaseEmbedder, InMemoryVectorStore, RAGPipeline

        class MockEmbedder(BaseEmbedder):
            @property
            def dimension(self):
                return 128

            def embed(self, texts):
                return [[0.0] * 128 for _ in texts]

            async def aembed(self, texts):
                return [[0.0] * 128 for _ in texts]

        pipeline = RAGPipeline(vector_store=InMemoryVectorStore(), embedder=MockEmbedder())
        stats = pipeline.get_stats()
        assert stats["document_count"] == 0

    def test_retrieval_history(self):
        from data_ai.core.rag.pipeline import BaseEmbedder, InMemoryVectorStore, RAGPipeline

        class MockEmbedder(BaseEmbedder):
            @property
            def dimension(self):
                return 128

            def embed(self, texts):
                return [[0.0] * 128 for _ in texts]

            async def aembed(self, texts):
                return [[0.0] * 128 for _ in texts]

        pipeline = RAGPipeline(vector_store=InMemoryVectorStore(), embedder=MockEmbedder())
        pipeline.add_texts(["doc1 content", "doc2 content"])
        pipeline.search("doc1")
        pipeline.search("doc2")
        assert len(pipeline.get_retrieval_history()) == 2

    def test_clear(self):
        from data_ai.core.rag.pipeline import BaseEmbedder, InMemoryVectorStore, RAGPipeline

        class MockEmbedder(BaseEmbedder):
            @property
            def dimension(self):
                return 128

            def embed(self, texts):
                return [[0.0] * 128 for _ in texts]

            async def aembed(self, texts):
                return [[0.0] * 128 for _ in texts]

        pipeline = RAGPipeline(vector_store=InMemoryVectorStore(), embedder=MockEmbedder())
        pipeline.add_texts(["test content"])
        assert pipeline.get_stats()["document_count"] > 0
        pipeline.clear()
        assert pipeline.get_stats()["document_count"] == 0


class TestMemoryStoreSharding:
    def test_short_term_eviction(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore(max_short_term=3)
        for i in range(5):
            store.add_short_term(f"Memory {i}")
        entries = store.get_short_term()
        assert len(entries) == 3
        contents = [e.content for e in entries]
        assert "Memory 0" not in contents

    def test_long_term_eviction(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore(max_long_term=3)
        for i in range(5):
            store.add_long_term(f"LT {i}")
        assert len(store.get_long_term()) == 3

    def test_importance_sorting(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore(max_short_term=100)
        store.add_short_term("Low priority", importance=0.1)
        store.add_short_term("High priority", importance=0.95)
        store.add_short_term("Medium priority", importance=0.5)
        entries = store.get_short_term(limit=3)
        assert entries[0].importance >= entries[1].importance >= entries[2].importance

    def test_search_case_insensitive(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        store.add_long_term("PYTHON IS GREAT")
        results = store.search("python")
        assert len(results) >= 1

    def test_search_partial_match(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        store.add_long_term("Python programming language")
        results = store.search("prog")
        assert len(results) >= 1

    def test_search_no_match(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        store.add_long_term("Python")
        results = store.search("xyznotfound")
        assert results == []

    def test_get_all(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        store.add_short_term("ST")
        store.add_long_term("LT")
        all_entries = store.get_all()
        assert len(all_entries) == 2

    def test_clear_all(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        store.add_short_term("test")
        store.add_long_term("test")
        store.clear_all()
        assert len(store.get_all()) == 0

    def test_clear_short_term_only(self):
        from data_ai.core.memory.manager import MemoryStore

        store = MemoryStore()
        store.add_short_term("ST")
        store.add_long_term("LT")
        store.clear_short_term()
        assert len(store.get_short_term()) == 0
        assert len(store.get_long_term()) == 1


class TestMemoryManager:
    def test_remember_default_short_term(self):
        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        mgr.remember("fact")
        assert mgr.store.get_short_term()[0].content == "fact"

    def test_remember_long_term(self):
        from data_ai.core.memory.manager import MemoryManager, MemoryType

        mgr = MemoryManager()
        mgr.remember("important", importance=1.0, memory_type=MemoryType.LONG_TERM)
        assert len(mgr.store.get_long_term()) == 1

    def test_recall_short_term(self):
        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        mgr.remember("fact 1")
        mgr.remember("fact 2")
        result = mgr.recall_short_term()
        assert "fact 1" in result
        assert "fact 2" in result

    def test_recall_long_term_empty(self):
        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        assert mgr.recall_long_term() == ""

    def test_recall_relevant_empty(self):
        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        assert mgr.recall_relevant("nothing") == ""

    def test_stats(self):
        from data_ai.core.memory.manager import MemoryManager, MemoryType

        mgr = MemoryManager()
        mgr.remember("ST1")
        mgr.remember("ST2")
        mgr.remember("LT1", memory_type=MemoryType.LONG_TERM)
        stats = mgr.get_stats()
        assert stats["short_term_count"] == 2
        assert stats["long_term_count"] == 1
        assert stats["total"] == 3

    def test_clear(self):
        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        mgr.remember("fact")
        mgr.clear()
        assert mgr.get_stats()["total"] == 0

    def test_summarize_fallback_no_llm(self):
        import asyncio

        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        for i in range(5):
            mgr.remember(f"Conversation point {i} about AI and technology.")
        result = asyncio.run(mgr.summarize(llm_manager=None))
        assert len(result) > 0
        assert mgr.get_stats()["long_term_count"] == 1
        assert mgr.get_stats()["short_term_count"] == 0

    def test_summarize_empty_memory(self):
        import asyncio

        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        result = asyncio.run(mgr.summarize())
        assert result == ""

    def test_memory_entry_metadata(self):
        from data_ai.core.memory.manager import MemoryManager

        mgr = MemoryManager()
        entry = mgr.remember("fact", source="user", confidence=0.9)
        assert entry.metadata.get("source") == "user"
        assert entry.metadata.get("confidence") == 0.9


class TestReasoningEdgeCases:
    async def test_fallback_no_llm(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        thinker = SequentialThinking(max_steps=3)
        chain = await thinker.think("")
        assert chain.final_answer is not None
        assert len(chain.thoughts) > 0

    async def test_llm_empty_response(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        async def empty_llm(prompt: str) -> str:
            return ""

        thinker = SequentialThinking()
        chain = await thinker.think("What?", llm_fn=empty_llm)
        assert chain.final_answer == ""
        assert len(chain.thoughts) > 0

    async def test_llm_structured_response(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        async def structured_llm(prompt: str) -> str:
            return (
                "Step 1: Understand the question.\n"
                "Step 2: Break it down into components.\n"
                "Step 3: Analyze each component.\n"
                "FINAL ANSWER: The answer is 42."
            )

        thinker = SequentialThinking()
        chain = await thinker.think("Life, universe, everything?", llm_fn=structured_llm)
        assert "42" in chain.final_answer
        assert len(chain.thoughts) == 3

    async def test_llm_response_chinese(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        async def chinese_llm(prompt: str) -> str:
            return "第一步：理解问题。\n第二步：分析数据。\n结论：答案是北京。"

        thinker = SequentialThinking()
        chain = await thinker.think("中国首都是哪里？", llm_fn=chinese_llm)
        assert "北京" in chain.final_answer

    async def test_llm_single_line(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        async def single_llm(prompt: str) -> str:
            return "FINAL ANSWER: Yes"

        thinker = SequentialThinking()
        chain = await thinker.think("Is this working?", llm_fn=single_llm)
        assert chain.final_answer.strip() == "Yes"

    async def test_max_steps_limit(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        async def many_steps_llm(prompt: str) -> str:
            steps = "\n".join([f"Step {i}: Doing analysis {i}." for i in range(1, 11)])
            return f"{steps}\nFINAL ANSWER: Done"

        thinker = SequentialThinking(max_steps=4)
        chain = await thinker.think("Test", llm_fn=many_steps_llm)
        assert len(chain.thoughts) == 4

    async def test_history_accumulation(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        async def simple_llm(prompt: str) -> str:
            return "FINAL ANSWER: OK"

        thinker = SequentialThinking()
        await thinker.think("Q1", llm_fn=simple_llm)
        await thinker.think("Q2", llm_fn=simple_llm)
        assert len(thinker.get_history()) == 2

    def test_clear_history(self):
        from data_ai.core.reasoning.sequential import SequentialThinking

        thinker = SequentialThinking()
        thinker._history = [thinker._think_fallback("test")]
        thinker.clear_history()
        assert len(thinker.get_history()) == 0

    def test_reasoning_chain_to_dict(self):
        from data_ai.core.reasoning.sequential import ReasoningChain, Thought

        chain = ReasoningChain(
            question="Test Q",
            thoughts=[Thought(content="Step 1", confidence=0.8, is_hypothesis=True)],
            final_answer="Answer",
            metadata={"key": "val"},
        )
        d = chain.to_dict()
        assert d["metadata"]["key"] == "val"
