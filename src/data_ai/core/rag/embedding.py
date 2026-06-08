"""
向量嵌入模块

提供文本嵌入功能。
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable

from ...utils.logging import get_logger

logger = get_logger(__name__)


class SimpleEmbedding:
    """简单的文本嵌入模型（基于哈希的伪嵌入）"""

    def __init__(self, dimension: int = 1536, dim: int | None = None):
        """
        初始化嵌入模型

        Args:
            dimension: 嵌入向量维度
            dim: 兼容性别名
        """
        self.dimension = dim if dim is not None else dimension

    def embed(self, text: str) -> list[float]:
        """
        将文本转换为嵌入向量

        Args:
            text: 输入文本

        Returns:
            嵌入向量
        """
        if not text:
            return [0.0] * self.dimension

        # 使用 MD5 哈希生成伪嵌入
        hash_obj = hashlib.md5(text.encode("utf-8"))
        hash_val = int.from_bytes(hash_obj.digest()[:8], byteorder="big", signed=False)

        # 将哈希值转换为固定维度的伪嵌入
        embedding = []
        for i in range(self.dimension):
            # 提取哈希值的不同位
            value = (hash_val >> (i % 64)) & 0xFF
            normalized = value / 255.0
            embedding.append(normalized)

        # 归一化到单位向量
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        批量嵌入文本

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        return [self.embed(text) for text in texts]

    def __call__(self, text: str) -> list[float]:
        """支持直接调用"""
        return self.embed(text)


class OpenAIEmbedding:
    """OpenAI 嵌入模型（需要 API 密钥）"""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimension: int = 1536):
        """
        初始化 OpenAI 嵌入模型

        Args:
            api_key: OpenAI API 密钥
            model: 模型名称
            dimension: 嵌入向量维度
        """
        self.api_key = api_key
        self.model = model
        self.dimension = dimension
        self._client = None

    def _get_client(self):
        """获取 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("OpenAI 嵌入需要 openai 包: pip install openai")

        return self._client

    def embed(self, text: str) -> list[float]:
        """嵌入单个文本"""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimension,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入文本"""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimension,
        )
        return [item.embedding for item in response.data]


class EmbeddingFactory:
    """嵌入模型工厂"""

    _providers = {
        "simple": SimpleEmbedding,
        "openai": OpenAIEmbedding,
    }

    @classmethod
    def create(cls, provider: str = "simple", **kwargs) -> Callable:
        """
        创建嵌入模型

        Args:
            provider: 提供商名称
            **kwargs: 其他参数

        Returns:
            嵌入模型实例
        """
        if provider not in cls._providers:
            raise ValueError(f"不支持的嵌入提供商: {provider}. 可用选项: {list(cls._providers.keys())}")

        return cls._providers[provider](**kwargs)

    @classmethod
    def register(cls, name: str, embedding_class: type):
        """注册新的嵌入模型"""
        cls._providers[name] = embedding_class
