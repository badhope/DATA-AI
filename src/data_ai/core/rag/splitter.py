"""
文本分割器

将长文档分割为适合检索的小块。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ...utils.logging import get_logger
from .loader import Document

logger = get_logger(__name__)


@dataclass
class TextSplitter(ABC):
    """文本分割器基类"""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    length_function: callable = len
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", " ", ""])

    @abstractmethod
    def split_text(self, text: str) -> list[str]:
        """分割文本"""
        pass

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """分割文档列表"""
        result = []
        for doc in documents:
            chunks = self.split_text(doc.content)
            for i, chunk in enumerate(chunks):
                new_metadata = doc.metadata.copy()
                new_metadata["chunk_index"] = i
                new_metadata["chunk_total"] = len(chunks)
                result.append(Document(content=chunk, metadata=new_metadata))
        return result

    def _merge_splits(self, splits: list[str]) -> list[str]:
        """合并分割结果，确保不超过 chunk_size"""
        chunks = []
        current_chunk = []
        current_length = 0

        for split in splits:
            split_len = self.length_function(split)

            if current_length + split_len > self.chunk_size and current_chunk:
                chunks.append("".join(current_chunk).strip())
                # 保留 overlap
                overlap_text = self._get_overlap("".join(current_chunk))
                current_chunk = [overlap_text] if overlap_text else []
                current_length = self.length_function(overlap_text) if overlap_text else 0

            current_chunk.append(split)
            current_length += split_len

        if current_chunk:
            chunks.append("".join(current_chunk).strip())

        return [c for c in chunks if c]


class RecursiveCharacterSplitter(TextSplitter):
    """递归字符分割器"""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        separators: list[str] | None = None,
        separator: str | None = None,
    ):
        """初始化分割器

        Args:
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            separators: 分隔符列表
            separator: 单个分隔符（兼容性参数）
        """
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        if separator:
            self.separators = [separator, "\n", " ", ""]
        else:
            self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split_text(self, text: str) -> list[str]:
        """递归分割文本"""
        return self._recursive_split(text, self.separators)

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """递归分割"""
        if not text:
            return []

        if self.length_function(text) <= self.chunk_size:
            return [text]

        for sep in separators:
            if sep == "":
                # 最后手段：按字符分割
                chunks = []
                for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
                    chunks.append(text[i : i + self.chunk_size])
                return chunks

            if sep in text:
                splits = text.split(sep)
                return self._merge_splits(splits)

        return [text]

    def _get_overlap(self, text: str) -> str:
        """获取重叠部分"""
        if self.chunk_overlap <= 0:
            return ""
        return text[-self.chunk_overlap :] if len(text) > self.chunk_overlap else ""


class TokenSplitter(TextSplitter):
    """基于 Token 的分割器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.separators = ["\n\n", "\n", " ", ""]

    def _count_tokens(self, text: str) -> int:
        """估算 token 数量（简单按字符/4估算）"""
        return len(text) // 4

    def split_text(self, text: str) -> list[str]:
        """按 token 数分割"""
        self.length_function = self._count_tokens
        return self._recursive_split(text, self.separators)

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if not text:
            return []
        if self._count_tokens(text) <= self.chunk_size:
            return [text]

        for sep in separators:
            if sep == "":
                chunks = []
                words = text.split()
                current = []
                current_tokens = 0
                for word in words:
                    word_tokens = self._count_tokens(word) + 1
                    if current_tokens + word_tokens > self.chunk_size and current:
                        chunks.append(" ".join(current))
                        overlap_words = current[-self.chunk_overlap :] if self.chunk_overlap > 0 else []
                        current = overlap_words + [word]
                        current_tokens = sum(self._count_tokens(w) + 1 for w in current)
                    else:
                        current.append(word)
                        current_tokens += word_tokens
                if current:
                    chunks.append(" ".join(current))
                return chunks
            if sep in text:
                splits = text.split(sep)
                return self._merge_splits(splits)
        return [text]

    def _get_overlap(self, text: str) -> str:
        if self.chunk_overlap <= 0:
            return ""
        words = text.split()
        return " ".join(words[-self.chunk_overlap :]) if len(words) > self.chunk_overlap else ""


# 别名兼容
BaseTextSplitter = TextSplitter
