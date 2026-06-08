"""
DATA-AI LLM 管理器

统一管理所有模型提供商，支持：
- 多模型提供商接入（OpenAI、Anthropic、Google、Azure、DeepSeek、SiliconFlow等）
- 本地模型支持（Ollama、vLLM、LM Studio）
- 模型路由和自动 fallback
- 流式输出（真正的 token 级别）
- 自动重试和指数退避
- 上下文窗口管理和 token 计数
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ...utils.exceptions import (
    LLMAuthError,
    LLMConfigError,
    LLMConnectionError,
    LLMContentFilterError,
    LLMException,
    LLMRateLimitError,
)
from ...utils.logging import get_logger

logger = get_logger(__name__)


class ModelProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    AWS = "aws"
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"
    # ── 中国大陆厂商（OpenAI 兼容 API） ─────────────────────────────
    QWEN = "qwen"  # 阿里通义千问 DashScope
    ZHIPU = "zhipu"  # 智谱 GLM
    MOONSHOT = "moonshot"  # 月之暗面 Kimi
    YI = "yi"  # 零一万物
    BAICHUAN = "baichuan"  # 百川
    DOUBAO = "doubao"  # 字节豆包（火山方舟）
    STEPFUN = "stepfun"  # 阶跃星辰
    # ── 本地 / 自托管 ────────────────────────────────────────────────
    OLLAMA = "ollama"
    VLLM = "vllm"
    LMSTUDIO = "lmstudio"
    OFFLINE = "offline"


@dataclass
class ModelConfig:
    provider: ModelProvider
    model_name: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    context_window: int = 128000
    timeout: float = 60.0
    max_retries: int = 3
    extra_params: dict[str, Any] = field(default_factory=dict)


# OpenAI 兼容厂商的默认 base_url，OpenAIClient 复用
PROVIDER_DEFAULT_BASE_URL: dict[str, str] = {
    ModelProvider.OPENAI.value: "https://api.openai.com/v1",
    ModelProvider.DEEPSEEK.value: "https://api.deepseek.com/v1",
    ModelProvider.SILICONFLOW.value: "https://api.siliconflow.cn/v1",
    ModelProvider.QWEN.value: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ModelProvider.ZHIPU.value: "https://open.bigmodel.cn/api/paas/v4",
    ModelProvider.MOONSHOT.value: "https://api.moonshot.cn/v1",
    ModelProvider.YI.value: "https://api.lingyiwanwu.com/v1",
    ModelProvider.BAICHUAN.value: "https://api.baichuan-ai.com/v1",
    ModelProvider.DOUBAO.value: "https://ark.cn-beijing.volces.com/api/v3",
    ModelProvider.STEPFUN.value: "https://api.stepfun.com/v1",
    ModelProvider.VLLM.value: "http://localhost:8000/v1",
    ModelProvider.LMSTUDIO.value: "http://localhost:1234/v1",
}


def default_base_url_for(provider) -> str | None:
    """根据 provider 返回默认 OpenAI 兼容 base_url。"""
    if isinstance(provider, ModelProvider):
        return PROVIDER_DEFAULT_BASE_URL.get(provider.value)
    if isinstance(provider, str):
        return PROVIDER_DEFAULT_BASE_URL.get(provider)
    return None


@dataclass
class ChatMessage:
    role: str
    content: str
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None
    tool_calls: list[dict] | None = None
    raw_response: Any | None = None


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class ContextWindowManager:
    def __init__(self, model_name: str, context_window: int, reserve_output_tokens: int = 4096):
        self.model_name = model_name
        self.context_window = context_window
        self.reserve_output_tokens = reserve_output_tokens
        self._encoder = self._get_encoder()

    def _get_encoder(self):
        try:
            import tiktoken

            if self.model_name.startswith("gpt-4") or self.model_name.startswith("o"):
                return tiktoken.encoding_for_model("gpt-4")
            elif self.model_name.startswith("gpt-3.5"):
                return tiktoken.encoding_for_model("gpt-3.5-turbo")
            else:
                return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    def count_tokens(self, text: str) -> int:
        if self._encoder:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass
        return len(text) // 4

    def count_message_tokens(self, messages: list[ChatMessage]) -> int:
        total = 0
        for msg in messages:
            total += 4
            for key, val in [("role", msg.role), ("content", msg.content)]:
                total += self.count_tokens(str(val))
            if msg.tool_calls:
                total += self.count_tokens(json.dumps(msg.tool_calls))
        total += 2
        return total

    def estimate_tokens(self, messages: list[ChatMessage]) -> int:
        return self.count_message_tokens(messages)

    def trim_messages(
        self,
        messages: list[ChatMessage],
        system_message: ChatMessage | None = None,
    ) -> list[ChatMessage]:
        available = self.context_window - self.reserve_output_tokens

        trimmed: list[ChatMessage] = []
        current_tokens = 0

        for msg in reversed(messages):
            if system_message is not None and msg is system_message:
                continue
            msg_tokens = self.count_message_tokens([msg])
            if current_tokens + msg_tokens > available:
                break
            trimmed.insert(0, msg)
            current_tokens += msg_tokens

        if system_message:
            trimmed.insert(0, system_message)

        if not trimmed and system_message:
            return [system_message]

        return trimmed


class BaseLLMClient(ABC):
    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = get_logger(f"{__name__}.{config.provider.value}")
        self._context_manager = ContextWindowManager(
            model_name=config.model_name,
            context_window=config.context_window,
        )

    @property
    def context_manager(self) -> ContextWindowManager:
        return self._context_manager

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        pass

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatResponse]:
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        pass

    def _prepare_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        result = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.name:
                entry["name"] = msg.name
            if msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            result.append(entry)
        return result


class OpenAIClient(BaseLLMClient):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        try:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=config.api_key or os.getenv("OPENAI_API_KEY"),
                base_url=config.base_url,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        except ImportError:
            raise LLMConfigError(message="OpenAI client not installed. Run: pip install openai")

    def validate_config(self) -> bool:
        if not self.config.api_key and not os.getenv("OPENAI_API_KEY"):
            raise LLMConfigError(
                message="OpenAI API key not provided",
                details={"provider": "openai"},
            )
        return True

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        try:
            params = {
                "model": self.config.model_name,
                "messages": self._prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                **({"tools": tools} if tools else {}),
                **({"max_tokens": self.config.max_tokens} if self.config.max_tokens else {}),
            }
            # P1-6: 透传 extra_params(支持 enable_thinking / enable_search 等 DashScope 私有参数)
            # openai>=1.0 用 extra_body 装非标准字段
            if self.config.extra_params:
                for k, v in self.config.extra_params.items():
                    if k in {"model", "messages", "stream", "tools", "temperature", "max_tokens", "top_p", "user"}:
                        continue
                    params.setdefault("extra_body", {})[k] = v
            total_chars = sum(len(m.get("content", "") or "") for m in params["messages"])
            logger.info(
                f"[OpenAIClient] provider={self.config.provider.value} model={params['model']!r} msgs={len(params['messages'])} chars={total_chars} base_url={self.config.base_url}"
            )

            response = await self.client.chat.completions.create(**params)
            choice = response.choices[0]

            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ]

            return ChatResponse(
                content=choice.message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
                raw_response=response,
            )
        except Exception as e:
            self._handle_error(e)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatResponse]:
        try:
            params = {
                "model": self.config.model_name,
                "messages": self._prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "stream": True,
                "stream_options": {"include_usage": True},
                **({"tools": tools} if tools else {}),
            }
            # P1-6: 透传 extra_params(走 extra_body)
            if self.config.extra_params:
                for k, v in self.config.extra_params.items():
                    if k in {"model", "messages", "stream", "tools", "stream_options", "temperature", "max_tokens", "top_p", "user"}:
                        continue
                    params.setdefault("extra_body", {})[k] = v

            stream = await self.client.chat.completions.create(**params)

            accumulated_tool_calls: dict[int, dict] = {}
            finish_reason = None

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue

                finish_reason = chunk.choices[0].finish_reason or finish_reason

                if delta.content:
                    yield ChatResponse(
                        content=delta.content,
                        model=chunk.model,
                        finish_reason=finish_reason,
                    )

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments

                if finish_reason == "tool_calls" and accumulated_tool_calls:
                    yield ChatResponse(
                        content="",
                        model=chunk.model,
                        finish_reason="tool_calls",
                        tool_calls=list(accumulated_tool_calls.values()),
                    )

        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error: Exception):
        error_msg = str(error).lower()
        if "rate limit" in error_msg or "rate_limit" in error_msg:
            raise LLMRateLimitError(message="OpenAI rate limit exceeded", cause=error)
        elif "content_filter" in error_msg or "content filter" in error_msg:
            raise LLMContentFilterError(message="Content filtered by OpenAI", cause=error)
        elif "connection" in error_msg or "timeout" in error_msg:
            raise LLMConnectionError(message="Failed to connect to OpenAI", cause=error)
        elif "authentication" in error_msg or "api key" in error_msg or "401" in error_msg:
            raise LLMAuthError(message="OpenAI authentication failed", cause=error)
        else:
            raise LLMException(message=f"OpenAI error: {error}", cause=error)


class AnthropicClient(BaseLLMClient):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        try:
            from anthropic import AsyncAnthropic

            self.client = AsyncAnthropic(
                api_key=config.api_key or os.getenv("ANTHROPIC_API_KEY"),
                base_url=config.base_url,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        except ImportError:
            raise LLMConfigError(message="Anthropic client not installed. Run: pip install anthropic")

    def validate_config(self) -> bool:
        if not self.config.api_key and not os.getenv("ANTHROPIC_API_KEY"):
            raise LLMConfigError(
                message="Anthropic API key not provided",
                details={"provider": "anthropic"},
            )
        return True

    def _convert_messages(self, messages: list[ChatMessage]) -> tuple:
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            elif msg.role == "tool":
                chat_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content,
                            }
                        ],
                    }
                )
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})
        return system_msg, chat_messages

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        converted = []
        for tool in tools:
            func = tool.get("function", tool)
            converted.append(
                {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                }
            )
        return converted

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        try:
            system_msg, chat_messages = self._convert_messages(messages)

            params = {
                "model": self.config.model_name,
                "messages": chat_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": self.config.max_tokens or 4096,
            }
            if system_msg:
                params["system"] = system_msg
            if tools:
                params["tools"] = self._convert_tools(tools)

            response = await self.client.messages.create(**params)

            content = ""
            tool_calls = None

            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    if tool_calls is None:
                        tool_calls = []
                    tool_calls.append(
                        {
                            "id": block.id,
                            "type": "function",
                            "function": {
                                "name": block.name,
                                "arguments": json.dumps(block.input),
                            },
                        }
                    )

            return ChatResponse(
                content=content,
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
                tool_calls=tool_calls,
                raw_response=response,
            )
        except Exception as e:
            self._handle_error(e)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatResponse]:
        try:
            system_msg, chat_messages = self._convert_messages(messages)

            params = {
                "model": self.config.model_name,
                "messages": chat_messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": self.config.max_tokens or 4096,
            }
            if system_msg:
                params["system"] = system_msg
            if tools:
                params["tools"] = self._convert_tools(tools)

            accumulated_tool_calls: list[dict] = []
            accumulated_content = ""

            async with self.client.messages.stream(**params) as stream:
                async for event in stream:
                    if event.type == "text":
                        accumulated_content += event.text
                        yield ChatResponse(
                            content=event.text,
                            model=self.config.model_name,
                        )
                    elif event.type == "message_stop":
                        getattr(event, "stop_reason", "end_turn")
                    elif event.type == "tool_use":
                        accumulated_tool_calls.append(
                            {
                                "id": event.id,
                                "type": "function",
                                "function": {
                                    "name": event.name,
                                    "arguments": json.dumps(event.input),
                                },
                            }
                        )

                if accumulated_tool_calls:
                    yield ChatResponse(
                        content=accumulated_content,
                        model=self.config.model_name,
                        finish_reason="tool_use",
                        tool_calls=accumulated_tool_calls,
                    )

        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error: Exception):
        error_msg = str(error).lower()
        if "rate limit" in error_msg or "rate_limit" in error_msg:
            raise LLMRateLimitError(message="Anthropic rate limit exceeded", cause=error)
        elif "connection" in error_msg or "timeout" in error_msg:
            raise LLMConnectionError(message="Failed to connect to Anthropic", cause=error)
        elif "authentication" in error_msg or "api key" in error_msg or "401" in error_msg:
            raise LLMAuthError(message="Anthropic authentication failed", cause=error)
        else:
            raise LLMException(message=f"Anthropic error: {error}", cause=error)


class OllamaClient(BaseLLMClient):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"

    def validate_config(self) -> bool:
        try:
            import httpx

            response = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            return response.status_code == 200
        except Exception as e:
            raise LLMConnectionError(
                message=f"Cannot connect to Ollama at {self.base_url}",
                cause=e,
            )

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        try:
            import httpx

            params = {
                "model": self.config.model_name,
                "messages": self._prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "stream": False,
            }
            if self.config.max_tokens:
                params["options"] = {"num_predict": self.config.max_tokens}
            if tools:
                params["tools"] = tools

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=params,
                    timeout=self.config.timeout,
                )
                response.raise_for_status()
                data = response.json()

            return ChatResponse(
                content=data["message"]["content"],
                model=self.config.model_name,
                usage={},
                finish_reason="stop" if data.get("done") else None,
                raw_response=data,
            )
        except Exception as e:
            raise LLMConnectionError(message=f"Ollama error: {e}", cause=e)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatResponse]:
        try:
            import httpx

            params = {
                "model": self.config.model_name,
                "messages": self._prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "stream": True,
            }
            if tools:
                params["tools"] = tools

            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=params,
                    timeout=self.config.timeout,
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "message" in data and "content" in data["message"]:
                                    yield ChatResponse(
                                        content=data["message"]["content"],
                                        model=self.config.model_name,
                                        finish_reason="stop" if data.get("done") else None,
                                    )
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            raise LLMConnectionError(message=f"Ollama streaming error: {e}", cause=e)


class GoogleClient(BaseLLMClient):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        try:
            import google.generativeai as genai

            genai.configure(api_key=config.api_key or os.getenv("GOOGLE_API_KEY"))
            self.model = genai.GenerativeModel(config.model_name)
        except ImportError:
            raise LLMConfigError(message="Google Generative AI not installed. Run: pip install google-generativeai")

    def validate_config(self) -> bool:
        if not self.config.api_key and not os.getenv("GOOGLE_API_KEY"):
            raise LLMConfigError(message="Google API key not provided", details={"provider": "google"})
        return True

    async def chat(self, messages: list[ChatMessage], tools: list[dict] | None = None, **kwargs) -> ChatResponse:
        try:
            history = []
            for msg in messages[:-1]:
                if msg.role == "system":
                    continue
                part = {"role": "user" if msg.role == "user" else "model", "parts": [msg.content]}
                history.append(part)

            last_msg = messages[-1].content if messages else ""
            chat = self.model.start_chat(history=history)
            response = chat.send_message(last_msg)
            return ChatResponse(
                content=response.text,
                model=self.config.model_name,
                finish_reason="stop",
            )
        except Exception as e:
            raise LLMException(message=f"Google error: {e}", cause=e)

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None, **kwargs
    ) -> AsyncIterator[ChatResponse]:
        try:
            history = []
            for msg in messages[:-1]:
                if msg.role == "system":
                    continue
                part = {"role": "user" if msg.role == "user" else "model", "parts": [msg.content]}
                history.append(part)

            last_msg = messages[-1].content if messages else ""
            chat = self.model.start_chat(history=history)
            response = chat.send_message(last_msg, stream=True)
            for chunk in response:
                if chunk.text:
                    yield ChatResponse(content=chunk.text, model=self.config.model_name)
        except Exception as e:
            raise LLMException(message=f"Google streaming error: {e}", cause=e)


class AzureOpenAIClient(BaseLLMClient):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        try:
            from openai import AsyncAzureOpenAI

            endpoint = config.base_url or os.getenv("AZURE_OPENAI_ENDPOINT")
            api_key = config.api_key or os.getenv("AZURE_OPENAI_API_KEY")
            api_version = config.extra_params.get("api_version", "2024-10-21")
            self.client = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=endpoint,
                api_version=api_version,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
        except ImportError:
            raise LLMConfigError(message="Azure OpenAI client not installed. Run: pip install openai")

    def validate_config(self) -> bool:
        if not self.config.api_key and not os.getenv("AZURE_OPENAI_API_KEY"):
            raise LLMConfigError(message="Azure OpenAI API key not provided", details={"provider": "azure"})
        return True

    async def chat(self, messages: list[ChatMessage], tools: list[dict] | None = None, **kwargs) -> ChatResponse:
        try:
            params = {
                "model": self.config.model_name,
                "messages": self._prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                **({"tools": tools} if tools else {}),
                **({"max_tokens": self.config.max_tokens} if self.config.max_tokens else {}),
            }
            response = await self.client.chat.completions.create(**params)
            choice = response.choices[0]
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in choice.message.tool_calls
                ]
            return ChatResponse(
                content=choice.message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=choice.finish_reason,
                tool_calls=tool_calls,
                raw_response=response,
            )
        except Exception as e:
            self._handle_error(e)

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None, **kwargs
    ) -> AsyncIterator[ChatResponse]:
        try:
            params = {
                "model": self.config.model_name,
                "messages": self._prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "stream": True,
                "stream_options": {"include_usage": True},
                **({"tools": tools} if tools else {}),
            }
            stream = await self.client.chat.completions.create(**params)
            accumulated_tool_calls: dict[int, dict] = {}
            finish_reason = None
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta is None:
                    continue
                finish_reason = chunk.choices[0].finish_reason or finish_reason
                if delta.content:
                    yield ChatResponse(content=delta.content, model=chunk.model, finish_reason=finish_reason)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in accumulated_tool_calls:
                            accumulated_tool_calls[idx] = {
                                "id": tc.id or "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            accumulated_tool_calls[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                accumulated_tool_calls[idx]["function"]["name"] += tc.function.name
                            if tc.function.arguments:
                                accumulated_tool_calls[idx]["function"]["arguments"] += tc.function.arguments
                if finish_reason == "tool_calls" and accumulated_tool_calls:
                    yield ChatResponse(
                        content="",
                        model=chunk.model,
                        finish_reason="tool_calls",
                        tool_calls=list(accumulated_tool_calls.values()),
                    )
        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error: Exception):
        error_msg = str(error).lower()
        if "rate limit" in error_msg or "rate_limit" in error_msg:
            raise LLMRateLimitError(message="Azure OpenAI rate limit exceeded", cause=error)
        elif "connection" in error_msg or "timeout" in error_msg:
            raise LLMConnectionError(message="Failed to connect to Azure OpenAI", cause=error)
        elif "authentication" in error_msg or "api key" in error_msg or "401" in error_msg:
            raise LLMAuthError(message="Azure OpenAI authentication failed", cause=error)
        else:
            raise LLMException(message=f"Azure OpenAI error: {error}", cause=error)


class AWSBedrockClient(BaseLLMClient):
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        try:
            import boto3

            self.client = boto3.client(
                "bedrock-runtime",
                region_name=config.extra_params.get("region", os.getenv("AWS_REGION", "us-east-1")),
                aws_access_key_id=config.extra_params.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=config.extra_params.get("aws_secret_access_key")
                or os.getenv("AWS_SECRET_ACCESS_KEY"),
            )
        except ImportError:
            raise LLMConfigError(message="boto3 not installed. Run: pip install boto3")

    def validate_config(self) -> bool:
        return True

    async def chat(self, messages: list[ChatMessage], tools: list[dict] | None = None, **kwargs) -> ChatResponse:
        try:
            import asyncio

            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.config.max_tokens or 4096,
                    "messages": [{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
                    "system": next((m.content for m in messages if m.role == "system"), None),
                    "temperature": kwargs.get("temperature", self.config.temperature),
                }
            )
            response = await asyncio.to_thread(
                self.client.invoke_model,
                modelId=self.config.model_name,
                body=body,
            )
            response_body = json.loads(response["body"].read())
            content = ""
            for block in response_body.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            return ChatResponse(content=content, model=self.config.model_name, finish_reason="stop")
        except Exception as e:
            raise LLMException(message=f"AWS Bedrock error: {e}", cause=e)

    async def chat_stream(
        self, messages: list[ChatMessage], tools: list[dict] | None = None, **kwargs
    ) -> AsyncIterator[ChatResponse]:
        try:
            import asyncio

            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": self.config.max_tokens or 4096,
                    "messages": [{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
                    "system": next((m.content for m in messages if m.role == "system"), None),
                    "temperature": kwargs.get("temperature", self.config.temperature),
                }
            )
            response = await asyncio.to_thread(
                self.client.invoke_model_with_response_stream,
                modelId=self.config.model_name,
                body=body,
            )
            for event in response.get("body", []):
                chunk = json.loads(event["chunk"]["bytes"])
                if chunk.get("type") == "content_block_delta":
                    yield ChatResponse(content=chunk.get("delta", {}).get("text", ""), model=self.config.model_name)
        except Exception as e:
            raise LLMException(message=f"AWS Bedrock streaming error: {e}", cause=e)


class OfflineLLMClient(BaseLLMClient):
    """本地离线 LLM 客户端：基于规则的占位实现。

    当后端没有配置任何外部 LLM provider 时（例如 dev 环境、无 API key、
    网络受限），这个客户端保证 chat / chat_stream 仍能返回真实的、有意义的
    响应（不是空字符串、不是错误），让前端 UI、Agent 流程、流式渲染
    都能完整跑通。
    """

    PROVIDER_NAME = "offline"

    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._online = False

    def validate_config(self) -> bool:
        return True

    def _build_reply(self, messages: list[ChatMessage]) -> str:
        last_user = ""
        system_prompt = ""
        for m in reversed(messages):
            if m.role == "user" and m.content and not last_user:
                last_user = m.content.strip()
            if m.role == "system" and m.content and not system_prompt:
                system_prompt = m.content
            if last_user and system_prompt:
                break
        if not last_user:
            last_user = "(空消息)"

        # 从 system prompt 推断目标语言（与前端 i18n 联动）
        reply_zh = "简" in system_prompt or "中文" in system_prompt
        lines = [ln.strip() for ln in last_user.splitlines() if ln.strip()]
        first = lines[0] if lines else last_user

        if any(kw in last_user for kw in ("你好", "您好", "hi", "hello", "嗨")):
            opener = "你好！" if reply_zh else "Hello!"
        elif any(kw in last_user for kw in ("?", "？")):
            opener = "这是一个好问题。" if reply_zh else "That's a good question."
        elif any(kw in last_user for kw in ("谢谢", "感谢", "thx", "thanks")):
            opener = "不客气！" if reply_zh else "You're welcome!"
        elif any(kw in last_user for kw in ("怎么", "如何", "how", "为什么", "why")):
            opener = "关于这个问题，我的理解是：" if reply_zh else "Here's my take on that:"
        elif any(kw in last_user for kw in ("错误", "报错", "bug", "失败", "不工作", "无法")):
            opener = "针对你描述的问题：" if reply_zh else "Regarding the issue you described:"
        else:
            if reply_zh:
                opener = "关于「{}」：".format(first[:30] + ("…" if len(first) > 30 else ""))
            else:
                opener = 'About "{}":'.format(first[:30] + ("..." if len(first) > 30 else ""))

        body_lines = [opener]
        if len(lines) > 1:
            body_lines.append("")
            body_lines.append("你提到了几个要点：" if reply_zh else "You mentioned these points:")
            for i, ln in enumerate(lines[:6], 1):
                body_lines.append(f"  {i}. {ln[:80]}{'…' if len(ln) > 80 else ''}")
            if len(lines) > 6:
                body_lines.append(
                    f"  （还有 {len(lines) - 6} 项未列出）" if reply_zh else f"  (and {len(lines) - 6} more)"
                )

        body_lines.append("")
        if reply_zh:
            body_lines.append(
                "**说明**：当前运行在「离线模式 (offline)」。要获得真正的 LLM 回答，"
                "请在环境变量里设置 OPENAI_API_KEY / ANTHROPIC_API_KEY / DEEPSEEK_API_KEY "
                "等并重启后端；或者在 settings 页面的「后端连接」配置项里指向一个已配置好 LLM 的后端实例。"
            )
        else:
            body_lines.append(
                "**Note**: Running in offline mode (placeholder). To get real LLM replies, set "
                "OPENAI_API_KEY / ANTHROPIC_API_KEY / DEEPSEEK_API_KEY and restart the backend, "
                "or point the frontend's Backend URL to a properly configured instance."
            )
        body_lines.append("")
        body_lines.append(f"（echo: {first[:120]}{'…' if len(first) > 120 else ''}）")

        return "\n".join(body_lines)

    @staticmethod
    def _split_tokens(text: str) -> list[str]:
        out: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\n":
                out.append("\n")
                i += 1
                continue
            if ch.isspace():
                j = i
                while j < n and text[j].isspace() and text[j] != "\n":
                    j += 1
                out.append(text[i:j])
                i = j
                continue
            if ch in "，。！？；：、,!?;:":
                out.append(ch)
                i += 1
                continue
            if "\u4e00" <= ch <= "\u9fff":
                out.append(ch)
                i += 1
                continue
            j = i
            while j < n and not text[j].isspace() and text[j] not in "，。！？；：、,!?;:":
                j += 1
            out.append(text[i:j])
            i = j
        return [t for t in out if t]

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        content = self._build_reply(messages)
        return ChatResponse(
            content=content,
            model=self.config.model_name,
            usage={
                "prompt_tokens": sum(len(m.content) for m in messages) // 4,
                "completion_tokens": len(content) // 4,
                "total_tokens": (sum(len(m.content) for m in messages) + len(content)) // 4,
            },
            finish_reason="stop",
        )

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatResponse]:
        content = self._build_reply(messages)
        tokens = self._split_tokens(content)
        for i, tok in enumerate(tokens):
            await asyncio.sleep(0.01)
            yield ChatResponse(
                content=tok,
                model=self.config.model_name,
                finish_reason="stop" if i == len(tokens) - 1 else None,
            )


class LLMManager:
    def __init__(self):
        self._clients: dict[str, BaseLLMClient] = {}
        self._configs: dict[str, ModelConfig] = {}
        self._default_model: str | None = None
        self._fallback_chain: list[str] = []

    def register_model(
        self,
        name: str,
        config: ModelConfig,
        set_default: bool = False,
        fallback_priority: int | None = None,
    ) -> None:
        self._configs[name] = config

        client_map = {
            ModelProvider.OPENAI: OpenAIClient,
            ModelProvider.ANTHROPIC: AnthropicClient,
            ModelProvider.GOOGLE: GoogleClient,
            ModelProvider.AZURE: AzureOpenAIClient,
            ModelProvider.AWS: AWSBedrockClient,
            ModelProvider.OLLAMA: OllamaClient,
            ModelProvider.VLLM: OpenAIClient,
            ModelProvider.LMSTUDIO: OpenAIClient,
            ModelProvider.DEEPSEEK: OpenAIClient,
            ModelProvider.SILICONFLOW: OpenAIClient,
            # 国内厂商：全部走 OpenAI 兼容协议，复用 OpenAIClient
            ModelProvider.QWEN: OpenAIClient,
            ModelProvider.ZHIPU: OpenAIClient,
            ModelProvider.MOONSHOT: OpenAIClient,
            ModelProvider.YI: OpenAIClient,
            ModelProvider.BAICHUAN: OpenAIClient,
            ModelProvider.DOUBAO: OpenAIClient,
            ModelProvider.STEPFUN: OpenAIClient,
            ModelProvider.OFFLINE: OfflineLLMClient,
        }

        client_class = client_map.get(config.provider)
        if not client_class:
            raise LLMConfigError(message=f"Unsupported provider: {config.provider}")

        # OpenAI 兼容厂商：未显式给 base_url 时填上厂商默认
        if client_class is OpenAIClient and not config.base_url:
            default = default_base_url_for(config.provider)
            if default:
                config.base_url = default
                logger.info(f"Auto-filled base_url for {config.provider.value}: {default}")

        self._clients[name] = client_class(config)

        if set_default or self._default_model is None:
            self._default_model = name

        if fallback_priority is not None:
            if len(self._fallback_chain) <= fallback_priority:
                self._fallback_chain.extend([""] * (fallback_priority + 1 - len(self._fallback_chain)))
            self._fallback_chain[fallback_priority] = name

        logger.info(
            f"Model registered: {name}",
            provider=config.provider.value,
            model=config.model_name,
            is_default=set_default,
        )

    def set_fallback_chain(self, model_names: list[str]) -> None:
        self._fallback_chain = model_names

    def get_client(self, name: str | None = None) -> BaseLLMClient:
        model_name = name or self._default_model
        if not model_name:
            raise LLMConfigError(message="No model registered and no default model set")
        if model_name not in self._clients:
            raise LLMConfigError(
                message=f"Model not found: {model_name}",
                details={"available_models": list(self._clients.keys())},
            )
        return self._clients[model_name]

    def get_context_manager(self, name: str | None = None) -> ContextWindowManager:
        return self.get_client(name).context_manager

    def list_models(self) -> list[str]:
        return list(self._clients.keys())

    def get_default_model(self) -> str | None:
        return self._default_model

    def set_default_model(self, name: str) -> None:
        if name not in self._clients:
            raise LLMConfigError(message=f"Cannot set default: model {name} not found")
        self._default_model = name
        logger.info(f"Default model set to: {name}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((LLMRateLimitError, LLMConnectionError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _chat_with_retry(
        self,
        client: BaseLLMClient,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        return await client.chat(messages, tools, **kwargs)

    async def _chat_with_fallback(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        primary = model or self._default_model
        if not primary:
            raise LLMConfigError(message="No model available")

        candidates = [primary] + [m for m in self._fallback_chain if m and m != primary]

        last_error = None
        for candidate in candidates:
            if candidate not in self._clients:
                continue
            try:
                client = self._clients[candidate]
                return await self._chat_with_retry(client, messages, tools, **kwargs)
            except (LLMRateLimitError, LLMConnectionError, LLMAuthError) as e:
                last_error = e
                logger.warning(
                    f"Model {candidate} failed, trying fallback",
                    error=str(e),
                )
                continue
            except LLMException:
                raise

        raise LLMException(
            message=f"All models failed, last error: {last_error}",
            cause=last_error,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        return await self._chat_with_fallback(messages, model, tools, **kwargs)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatResponse]:
        primary = model or self._default_model
        if not primary:
            raise LLMConfigError(message="No model available")

        candidates = [primary] + [m for m in self._fallback_chain if m and m != primary]

        last_error = None
        for candidate in candidates:
            if candidate not in self._clients:
                continue
            try:
                client = self._clients[candidate]
                async for response in client.chat_stream(messages, tools, **kwargs):
                    yield response
                return
            except (LLMRateLimitError, LLMConnectionError, LLMAuthError) as e:
                last_error = e
                logger.warning(
                    f"Streaming model {candidate} failed, trying fallback",
                    error=str(e),
                )
                continue
            except LLMException:
                raise

        raise LLMException(
            message=f"All streaming models failed, last error: {last_error}",
            cause=last_error,
        )

    def create_chat_message(self, role: str, content: str, **kwargs) -> ChatMessage:
        return ChatMessage(role=role, content=content, **kwargs)


def register_model(
    name: str,
    provider: str | ModelProvider,
    model_name: str,
    api_key: str | None = None,
    **kwargs,
) -> None:
    if isinstance(provider, str):
        provider = ModelProvider(provider)
    config = ModelConfig(provider=provider, model_name=model_name, api_key=api_key, **kwargs)
    _llm_manager.register_model(name, config)


_llm_manager = LLMManager()


def get_llm_manager() -> LLMManager:
    return _llm_manager
