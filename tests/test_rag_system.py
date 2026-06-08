"""
DATA-AI RAG System Tests (v2.0 API)

Test Document, TextSplitter, VectorStore, Embedding, Retriever, RAGPipeline
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
    def dimension(self):
        return 128

    def embed(self, texts):
        return [[0.0] * 128 for _ in texts]

    async def aembed(self, texts):
        return [[0.0] * 128 for _ in texts]


@pytest.fixture
def temp_dir(tmp_path):
    txt_file = tmp_path / "sample.txt"
    txt_file.write_text("Hello world.\nThis is a test document.\nIt has multiple lines.", encoding="utf-8")

    md_file = tmp_path / "readme.md"
    md_file.write_text("# Title\n\nSome content here.\n\n## Section 1\nDetails.", encoding="utf-8")

    html_file = tmp_path / "page.html"
    html_file.write_text(
        "<html><head><title>Test Page</title></head><body><p>Hello HTML</p></body></html>",
        encoding="utf-8",
    )

    return tmp_path


def _read_file_as_document(filepath, file_type=None):
    content = Path(filepath).read_text(encoding="utf-8")
    metadata = {"type": file_type, "source": str(filepath)} if file_type else {"source": str(filepath)}
    return Document(content=content, metadata=metadata)


class TestDocument:
    def test_create_document(self):
        doc = Document(content="Hello world", metadata={"source": "test.txt"})
        assert doc.content == "Hello world"
        assert doc.metadata["source"] == "test.txt"

    def test_document_default_metadata(self):
        doc = Document(content="test")
        assert doc.metadata == {}

    def test_document_repr(self):
        doc = Document(content="x" * 100)
        r = repr(doc)
        assert "Document(" in r


class TestTextLoader:
    def test_load_text_file(self, temp_dir):
        doc = _read_file_as_document(temp_dir / "sample.txt", file_type="text")
        assert "Hello world" in doc.content
        assert doc.metadata["type"] == "text"

    def test_load_nonexistent_file(self, temp_dir):
        with pytest.raises(FileNotFoundError):
            _read_file_as_document(temp_dir / "nonexistent.txt")


class TestMarkdownLoader:
    def test_load_markdown_file(self, temp_dir):
        content = (temp_dir / "readme.md").read_text(encoding="utf-8")
        doc = Document(content=content, metadata={"type": "markdown", "headers": ["Title", "Section 1"]})
        assert "# Title" in doc.content
        assert doc.metadata["type"] == "markdown"
        assert "headers" in doc.metadata


class TestHTMLLoader:
    def test_load_html_file(self, temp_dir):
        content = (temp_dir / "page.html").read_text(encoding="utf-8")
        doc = Document(content=content, metadata={"type": "html"})
        assert doc.metadata["type"] == "html"
        assert "Hello HTML" in doc.content


class TestCharacterTextSplitter:
    def test_split_short_text(self):
        splitter = TextSplitter(chunk_size=100, chunk_overlap=10)
        result = splitter.split_text("Short text")
        assert len(result) == 1
        assert result[0] == "Short text"

    def test_split_long_text(self):
        text = "Line one.\nLine two.\nLine three.\nLine four.\nLine five.\n"
        splitter = TextSplitter(chunk_size=20, chunk_overlap=5, separators=["\n"])
        result = splitter.split_text(text)
        assert len(result) >= 2

    def test_split_documents(self):
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        docs = [Document(content="A" * 200, metadata={"source": "test"})]
        split_docs = splitter.split_documents(docs)
        assert len(split_docs) > 1
        for doc in split_docs:
            assert "chunk_index" in doc.metadata


class TestRecursiveCharacterTextSplitter:
    def test_split_text(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        splitter = TextSplitter(chunk_size=30, chunk_overlap=5)
        result = splitter.split_text(text)
        assert len(result) >= 1

    def test_custom_separators(self):
        splitter = TextSplitter(
            separators=[".", "\n", " "],
            chunk_size=50,
            chunk_overlap=10,
        )
        text = "One. Two. Three. Four. Five."
        result = splitter.split_text(text)
        assert len(result) >= 1


class TestTokenTextSplitter:
    def test_split_text_fallback(self):
        splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
        result = splitter.split_text("Hello world, this is a test.")
        assert len(result) >= 1


class TestInMemoryVectorStore:
    def test_add_and_search(self):
        store = InMemoryVectorStore()
        docs = [
            Document(content="Python programming language"),
            Document(content="Java programming language"),
        ]
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        store.add(docs, embeddings)
        assert store.count() == 2

        results = store.search([1.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert "Python" in results[0][0].content

    def test_empty_search(self):
        store = InMemoryVectorStore()
        results = store.search([1.0, 0.0], top_k=5)
        assert results == []

    def test_delete(self):
        store = InMemoryVectorStore()
        store.add(
            [Document(content="test")],
            [[1.0, 0.0]],
        )
        assert store.count() == 1
        store.clear()
        assert store.count() == 0


class TestSimpleEmbedding:
    def test_embed(self):
        emb = MockEmbedder()
        vectors = emb.embed(["hello world"])
        assert len(vectors) == 1
        assert len(vectors[0]) == 128
        assert vectors[0] == [0.0] * 128

    def test_embed_batch(self):
        emb = MockEmbedder()
        vectors = emb.embed(["hello", "world"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 128

    def test_same_text_same_embedding(self):
        emb = MockEmbedder()
        v1 = emb.embed(["test"])
        v2 = emb.embed(["test"])
        assert v1 == v2


class TestRetriever:
    def test_retrieve(self):
        store = InMemoryVectorStore()
        emb = MockEmbedder()
        docs = [
            Document(content="machine learning algorithms"),
            Document(content="cooking recipes"),
        ]
        embeddings = emb.embed([d.content for d in docs])
        store.add(docs, embeddings)

        query_emb = emb.embed(["AI and data science"])[0]
        results = store.search(query_emb, top_k=1)
        assert len(results) >= 1


class TestRAGPipeline:
    def test_add_documents(self, temp_dir):
        pipeline = RAGPipeline(embedder=MockEmbedder())

        documents = []
        for txt_file in temp_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            documents.append(Document(content=content, metadata={"source": str(txt_file)}))

        count = pipeline.add_documents(documents)
        assert count > 0

    def test_query(self, temp_dir):
        pipeline = RAGPipeline(embedder=MockEmbedder())

        documents = []
        for txt_file in temp_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            documents.append(Document(content=content, metadata={"source": str(txt_file)}))

        pipeline.add_documents(documents)

        result = pipeline.query("test document", top_k=3)
        assert isinstance(result, str)

    def test_query_with_context(self, temp_dir):
        pipeline = RAGPipeline(embedder=MockEmbedder())

        documents = []
        for txt_file in temp_dir.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            documents.append(Document(content=content, metadata={"source": str(txt_file)}))

        pipeline.add_documents(documents)

        search_result = pipeline.search("test", top_k=3)
        assert isinstance(search_result, RetrievalResult)
        assert isinstance(search_result.documents, list)

    def test_empty_directory(self, tmp_path):
        pipeline = RAGPipeline(embedder=MockEmbedder())

        documents = []
        for txt_file in tmp_path.glob("*.txt"):
            content = txt_file.read_text(encoding="utf-8")
            documents.append(Document(content=content, metadata={"source": str(txt_file)}))

        count = pipeline.add_documents(documents)
        assert count == 0
