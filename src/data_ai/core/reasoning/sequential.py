"""
DATA-AI 顺序推理引擎

基于 LLM 的多步推理系统，支持：
- 假设生成和验证
- 思维链（Chain of Thought）
- 推理步骤追踪
- 置信度评估
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Thought:
    content: str
    confidence: float = 0.5
    is_hypothesis: bool = False
    is_verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningChain:
    question: str
    thoughts: list[Thought] = field(default_factory=list)
    final_answer: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "thoughts": [
                {"content": t.content, "confidence": t.confidence, "is_hypothesis": t.is_hypothesis}
                for t in self.thoughts
            ],
            "final_answer": self.final_answer,
            "metadata": self.metadata,
        }


class SequentialThinking:
    def __init__(self, max_steps: int = 5):
        self.max_steps = max_steps
        self._history: list[ReasoningChain] = []

    async def think(
        self,
        question: str,
        llm_fn: Callable[..., Awaitable[str]] | None = None,
        context: str | None = None,
    ) -> ReasoningChain:
        chain = ReasoningChain(question=question)

        if llm_fn is None:
            chain = self._think_fallback(question, context)
            self._history.append(chain)
            return chain

        try:
            system_prompt = (
                "You are a logical reasoning engine. "
                "Analyze the question step by step using chain-of-thought reasoning. "
                "For each step, state your thought clearly. "
                "End with a final answer prefixed by 'FINAL ANSWER:'."
            )

            prompt = f"QUESTION: {question}\n\n"
            if context:
                prompt += f"CONTEXT: {context}\n\n"
            prompt += "Think step by step:\n"

            full_prompt = f"{system_prompt}\n\n{prompt}"
            response = await llm_fn(full_prompt)

            thoughts = self._parse_thoughts(response)
            chain.thoughts = thoughts

            final_answer = self._extract_final_answer(response)
            chain.final_answer = final_answer

            self._history.append(chain)
            return chain

        except Exception as e:
            logger.warning(f"LLM reasoning failed, using fallback: {e}")
            chain = self._think_fallback(question, context)
            self._history.append(chain)
            return chain

    def _parse_thoughts(self, response: str) -> list[Thought]:
        thoughts = []
        lines = response.split("\n")

        step_patterns = [
            "step",
            "thought",
            "think",
            "reason",
            "分析",
            "思考",
            "推理",
            "first",
            "second",
            "third",
            "next",
            "then",
            "finally",
            "lastly",
            "首先",
            "其次",
            "然后",
            "最后",
            "接着",
            "第一步",
            "第二步",
            "第三步",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "FINAL ANSWER:" in line.upper() or "结论:" in line or "最终答案:" in line:
                break

            lower_line = line.lower()
            is_step = False
            for prefix in step_patterns:
                if lower_line.startswith(prefix) or f"{prefix} " in lower_line[:15]:
                    is_step = True
                    break
                idx = lower_line.find(f"{prefix}:")
                if 0 <= idx <= 5:
                    is_step = True
                    break

            if is_step:
                confidence = 0.7
            elif len(line) > 30:
                confidence = 0.5
            else:
                continue

            thoughts.append(Thought(content=line, confidence=confidence))

        if not thoughts:
            thoughts.append(Thought(content=response[:500], confidence=0.5))

        return thoughts[: self.max_steps]

    def _extract_final_answer(self, response: str) -> str:
        for marker in ["FINAL ANSWER:", "Final Answer:", "final answer:", "Conclusion:", "In conclusion:"]:
            if marker in response:
                return response.split(marker)[-1].strip()
        return response.strip()

    def _think_fallback(self, question: str, context: str | None = None) -> ReasoningChain:
        chain = ReasoningChain(question=question)

        chain.thoughts.append(
            Thought(
                content=f"Analyzing the question: {question[:200]}",
                confidence=0.6,
            )
        )

        if context:
            chain.thoughts.append(
                Thought(
                    content=f"Considering context: {context[:200]}",
                    confidence=0.5,
                )
            )

        chain.thoughts.append(
            Thought(
                content="The question requires deep analysis. Consider using an LLM for better reasoning.",
                confidence=0.3,
            )
        )

        chain.final_answer = "No LLM available for reasoning. Please provide an LLM function for better results."
        return chain

    def get_history(self) -> list[ReasoningChain]:
        return self._history

    def clear_history(self) -> None:
        self._history = []
