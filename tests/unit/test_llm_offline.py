"""Unit tests for the offline LLM client.

The offline client is what every CI / demo / sandbox smoke test runs against,
so its behaviour is the public contract for "the project works without
external credentials". Keep these tests small and deterministic.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from data_ai.core.llm.manager import (
    ChatMessage,
    ChatResponse,
    ModelConfig,
    ModelProvider,
    OfflineLLMClient,
)


def _build_client() -> OfflineLLMClient:
    return OfflineLLMClient(
        ModelConfig(
            provider=ModelProvider.OFFLINE,
            model_name="offline-test",
            api_key=None,
        )
    )


def _run(coro: Any) -> Any:
    """Run a coroutine on a fresh loop. Avoids global loop state leakage."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _collect(aiter: AsyncIterator[ChatResponse]) -> list[ChatResponse]:
    out: list[ChatResponse] = []
    async for piece in aiter:
        out.append(piece)
    return out


class TestOfflineChat:
    def test_chat_returns_response(self) -> None:
        client = _build_client()
        response = _run(
            client.chat(
                messages=[ChatMessage(role="user", content="hello world")],
            )
        )
        assert isinstance(response, ChatResponse)
        assert response.content  # non-empty
        assert response.model == "offline-test"
        assert response.finish_reason == "stop"
        # The offline client should not echo the input verbatim; the
        # acknowledgement template is the contract.
        assert response.content.strip().lower() != "hello world"

    def test_chat_uses_system_prompt_for_language(self) -> None:
        client = _build_client()
        # The offline client switches to Chinese when the system prompt
        # mentions "中文" or "简".
        response_zh = _run(
            client.chat(
                messages=[
                    ChatMessage(role="system", content="请用简体中文回答"),
                    ChatMessage(role="user", content="hi"),
                ],
            )
        )
        assert "说明" in response_zh.content or "离线模式" in response_zh.content

        response_en = _run(
            client.chat(
                messages=[
                    ChatMessage(role="system", content="answer in english"),
                    ChatMessage(role="user", content="hi"),
                ],
            )
        )
        # English template mentions "Note" / "offline mode"
        assert "Note" in response_en.content or "offline" in response_en.content

    def test_chat_reports_token_usage(self) -> None:
        client = _build_client()
        response = _run(
            client.chat(
                messages=[ChatMessage(role="user", content="hello world")],
            )
        )
        assert response.usage.get("completion_tokens", 0) > 0
        assert response.usage.get("prompt_tokens", 0) > 0

    def test_stream_yields_chunks(self) -> None:
        client = _build_client()

        async def go() -> list[ChatResponse]:
            return await _collect(
                client.chat_stream(
                    messages=[ChatMessage(role="user", content="hi")],
                )
            )

        chunks = _run(go())
        assert chunks, "offline stream yielded nothing"
        joined = "".join(c.content for c in chunks)
        assert joined.strip(), "aggregated stream content is empty"
        # The final chunk should carry finish_reason=stop.
        assert chunks[-1].finish_reason == "stop"
