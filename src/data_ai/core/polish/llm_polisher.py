"""
LLM 润色器模块。

本模块提供基于大语言模型的文本润色功能。

主要组件:
- LLMPolisher: LLM润色器
- PromptTemplate: 提示词模板
- LLMBackend: LLM后端抽象
"""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from .diff import TextDiffer
from .polisher import BasePolisher
from .types import (
    PolishConfig,
    PolishException,
    PolishLevel,
    PolishResult,
    PolishScore,
    PolishStyle,
    TextChange,
)


@dataclass
class PromptTemplate:
    """
    提示词模板。

    用于生成润色任务的提示词。

    Attributes:
        system_prompt: 系统提示词
        user_prompt_template: 用户提示词模板
        examples: 示例列表
    """

    system_prompt: str = """你是一位专业的文字编辑，擅长润色和优化文本。
你的任务是改进文本的表达方式，使其更加清晰、流畅、专业。

润色原则：
1. 保持原文的核心意思不变
2. 改善语法和表达方式
3. 调整文本风格以符合目标要求
4. 提升文本的可读性和专业性

请直接输出润色后的文本，不要添加任何解释或说明。"""

    user_prompt_template: str = """请润色以下文本：

原文：
{text}

润色要求：
- 润色等级：{level}
- 润色风格：{style}
{additional_requirements}

请输出润色后的文本："""

    examples: list[dict[str, str]] = field(default_factory=list)

    def format(
        self,
        text: str,
        level: PolishLevel,
        style: PolishStyle,
        additional_requirements: str | None = None,
    ) -> list[dict[str, str]]:
        """
        格式化提示词。

        Args:
            text: 待润色文本
            level: 润色等级
            style: 润色风格
            additional_requirements: 额外要求

        Returns:
            消息列表
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
        ]

        # 添加示例
        for example in self.examples:
            messages.append(
                {
                    "role": "user",
                    "content": example.get("input", ""),
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": example.get("output", ""),
                }
            )

        # 格式化用户提示词
        user_content = self.user_prompt_template.format(
            text=text,
            level=level.get_description(),
            style=style.get_prompt_modifier(),
            additional_requirements=additional_requirements or "",
        )

        messages.append({"role": "user", "content": user_content})

        return messages

    def add_example(
        self,
        input_text: str,
        output_text: str,
    ) -> None:
        """
        添加示例。

        Args:
            input_text: 输入文本
            output_text: 输出文本
        """
        self.examples.append(
            {
                "input": input_text,
                "output": output_text,
            }
        )


@dataclass
class LLMConfig:
    """
    LLM 配置。

    Attributes:
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大生成 token 数
        top_p: Top-p 采样参数
        timeout: 超时时间
        retry_count: 重试次数
        retry_delay: 重试延迟
    """

    model: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    timeout: float = 60.0
    retry_count: int = 3
    retry_delay: float = 1.0


class LLMBackend(ABC):
    """
    LLM 后端抽象基类。

    定义 LLM 后端的通用接口。
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> str:
        """
        生成文本。

        Args:
            messages: 消息列表
            config: LLM 配置

        Returns:
            生成的文本
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """
        流式生成文本。

        Args:
            messages: 消息列表
            config: LLM 配置

        Yields:
            生成的文本片段
        """
        pass


class OpenAIBackend(LLMBackend):
    """
    OpenAI 后端。

    使用 OpenAI API 进行文本生成。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """
        初始化 OpenAI 后端。

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
        """
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        """获取 OpenAI 客户端。"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise PolishException(
                    message="OpenAI 库未安装，请运行: pip install openai",
                    code="OPENAI_NOT_INSTALLED",
                )
        return self._client

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> str:
        """生成文本。"""
        client = self._get_client()

        try:
            response = await client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                timeout=config.timeout,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise PolishException(
                message=f"OpenAI API 调用失败: {e}",
                code="OPENAI_API_ERROR",
                details={"error": str(e)},
            )

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """流式生成文本。"""
        client = self._get_client()

        try:
            stream = await client.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                top_p=config.top_p,
                stream=True,
                timeout=config.timeout,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            raise PolishException(
                message=f"OpenAI API 流式调用失败: {e}",
                code="OPENAI_STREAM_ERROR",
                details={"error": str(e)},
            )


class AnthropicBackend(LLMBackend):
    """
    Anthropic 后端。

    使用 Anthropic Claude API 进行文本生成。
    """

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        """
        初始化 Anthropic 后端。

        Args:
            api_key: API 密钥
        """
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        """获取 Anthropic 客户端。"""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise PolishException(
                    message="Anthropic 库未安装，请运行: pip install anthropic",
                    code="ANTHROPIC_NOT_INSTALLED",
                )
        return self._client

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> str:
        """生成文本。"""
        client = self._get_client()

        # 转换消息格式
        system_msg = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        try:
            params = {
                "model": config.model,
                "messages": chat_messages,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            }

            if system_msg:
                params["system"] = system_msg

            response = await client.messages.create(**params)

            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            return content

        except Exception as e:
            raise PolishException(
                message=f"Anthropic API 调用失败: {e}",
                code="ANTHROPIC_API_ERROR",
                details={"error": str(e)},
            )

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """流式生成文本。"""
        client = self._get_client()

        system_msg = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                chat_messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        try:
            params = {
                "model": config.model,
                "messages": chat_messages,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            }

            if system_msg:
                params["system"] = system_msg

            async with client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    yield text

        except Exception as e:
            raise PolishException(
                message=f"Anthropic API 流式调用失败: {e}",
                code="ANTHROPIC_STREAM_ERROR",
                details={"error": str(e)},
            )


class MockBackend(LLMBackend):
    """
    模拟后端。

    用于测试和开发环境。
    """

    async def generate(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> str:
        """生成模拟响应。"""
        # 从最后一条用户消息中提取文本
        last_user_msg = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        # 简单模拟：返回原文加上润色标记
        return f"[润色后] {last_user_msg}"

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> AsyncIterator[str]:
        """流式生成模拟响应。"""
        result = await self.generate(messages, config)
        for char in result:
            yield char
            await asyncio.sleep(0.01)


class LLMPolisher(BasePolisher):
    """
    LLM 润色器。

    使用大语言模型进行文本润色，支持多种后端和自定义提示词。

    Example:
        >>> polisher = LLMPolisher(backend=OpenAIBackend(api_key="..."))
        >>> result = await polisher.polish_async("这个很好看")
        >>> print(result.polished)
        这件物品外观非常精美
    """

    def __init__(
        self,
        config: PolishConfig | None = None,
        backend: LLMBackend | None = None,
        llm_config: LLMConfig | None = None,
        prompt_template: PromptTemplate | None = None,
    ) -> None:
        """
        初始化 LLM 润色器。

        Args:
            config: 润色配置
            backend: LLM 后端
            llm_config: LLM 配置
            prompt_template: 提示词模板
        """
        super().__init__(config)
        self._backend = backend or MockBackend()
        self._llm_config = llm_config or LLMConfig()
        self._prompt_template = prompt_template or PromptTemplate()
        self._differ = TextDiffer()

    @property
    def backend(self) -> LLMBackend:
        """获取 LLM 后端。"""
        return self._backend

    @property
    def llm_config(self) -> LLMConfig:
        """获取 LLM 配置。"""
        return self._llm_config

    def set_backend(self, backend: LLMBackend) -> None:
        """
        设置 LLM 后端。

        Args:
            backend: LLM 后端
        """
        self._backend = backend

    def set_llm_config(self, config: LLMConfig) -> None:
        """
        设置 LLM 配置。

        Args:
            config: LLM 配置
        """
        self._llm_config = config

    def set_prompt_template(self, template: PromptTemplate) -> None:
        """
        设置提示词模板。

        Args:
            template: 提示词模板
        """
        self._prompt_template = template

    def add_example(
        self,
        input_text: str,
        output_text: str,
    ) -> None:
        """
        添加示例到提示词模板。

        Args:
            input_text: 输入文本
            output_text: 输出文本
        """
        self._prompt_template.add_example(input_text, output_text)

    def polish(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> PolishResult:
        """
        同步润色文本。

        注意：此方法会在内部创建事件循环运行异步方法。
        在已有事件循环的环境中，建议使用 polish_async。

        Args:
            text: 待润色文本
            level: 润色等级
            style: 润色风格

        Returns:
            润色结果
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在异步环境中，创建新线程运行
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.polish_async(text, level, style),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(self.polish_async(text, level, style))
        except RuntimeError:
            return asyncio.run(self.polish_async(text, level, style))

    async def polish_async(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> PolishResult:
        """
        异步润色文本。

        Args:
            text: 待润色文本
            level: 润色等级
            style: 润色风格

        Returns:
            润色结果
        """
        start_time = time.time()

        polish_level = level or self.config.level
        polish_style = style or self.config.style

        if not text:
            return PolishResult(
                original=text,
                polished=text,
                changes=[],
                score=PolishScore(),
                level=polish_level,
                style=polish_style,
                processing_time=time.time() - start_time,
            )

        try:
            # 生成提示词
            messages = self._prompt_template.format(
                text=text,
                level=polish_level,
                style=polish_style,
            )

            # 调用 LLM
            polished = await self._call_llm_with_retry(messages)

            # 清理输出
            polished = self._clean_output(polished)

            # 计算差异
            changes = self._differ.find_changes(text, polished)

            # 计算评分
            score = self._calculate_score(text, polished, changes)

            processing_time = time.time() - start_time

            return PolishResult(
                original=text,
                polished=polished,
                changes=changes,
                score=score,
                level=polish_level,
                style=polish_style,
                processing_time=processing_time,
                metadata={
                    "model": self._llm_config.model,
                    "temperature": self._llm_config.temperature,
                },
            )

        except Exception as e:
            raise PolishException(
                message=f"LLM 润色失败: {e}",
                code="LLM_POLISH_ERROR",
                details={"error": str(e)},
            )

    async def _call_llm_with_retry(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        带重试的 LLM 调用。

        Args:
            messages: 消息列表

        Returns:
            生成的文本
        """
        last_error = None

        for attempt in range(self._llm_config.retry_count):
            try:
                return await self._backend.generate(messages, self._llm_config)
            except Exception as e:
                last_error = e
                if attempt < self._llm_config.retry_count - 1:
                    await asyncio.sleep(self._llm_config.retry_delay * (attempt + 1))

        raise last_error or PolishException(
            message="LLM 调用失败",
            code="LLM_CALL_FAILED",
        )

    def _clean_output(self, text: str) -> str:
        """
        清理 LLM 输出。

        Args:
            text: 原始输出

        Returns:
            清理后的文本
        """
        # 移除可能的前缀标记
        prefixes = ["[润色后]", "润色后：", "润色结果：", "```", "```text"]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()

        # 移除可能的代码块标记
        if text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()

        return text.strip()

    async def polish_stream(
        self,
        text: str,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> AsyncIterator[str]:
        """
        流式润色文本。

        Args:
            text: 待润色文本
            level: 润色等级
            style: 润色风格

        Yields:
            润色后的文本片段
        """
        polish_level = level or self.config.level
        polish_style = style or self.config.style

        messages = self._prompt_template.format(
            text=text,
            level=polish_level,
            style=polish_style,
        )

        async for chunk in self._backend.generate_stream(messages, self._llm_config):
            yield chunk

    async def polish_multi_round(
        self,
        text: str,
        rounds: int = 2,
        level: PolishLevel | None = None,
        style: PolishStyle | None = None,
    ) -> PolishResult:
        """
        多轮润色。

        Args:
            text: 待润色文本
            rounds: 润色轮数
            level: 润色等级
            style: 润色风格

        Returns:
            最终润色结果
        """
        current_text = text
        all_changes: list[TextChange] = []
        start_time = time.time()

        polish_level = level or self.config.level
        polish_style = style or self.config.style

        for round_num in range(rounds):
            result = await self.polish_async(current_text, level, style)
            current_text = result.polished
            all_changes.extend(result.changes)

        # 计算最终评分
        score = self._calculate_score(text, current_text, all_changes)

        return PolishResult(
            original=text,
            polished=current_text,
            changes=all_changes,
            score=score,
            level=polish_level,
            style=polish_style,
            processing_time=time.time() - start_time,
            metadata={"rounds": rounds},
        )

    async def compare_polish(
        self,
        text: str,
        styles: list[PolishStyle],
        level: PolishLevel | None = None,
    ) -> dict[str, PolishResult]:
        """
        对比不同风格的润色结果。

        Args:
            text: 待润色文本
            styles: 风格列表
            level: 润色等级

        Returns:
            风格名称到润色结果的映射
        """
        results = {}

        for style in styles:
            result = await self.polish_async(text, level, style)
            results[style.value] = result

        return results


class LLMPolisherBuilder:
    """
    LLM 润色器构建器。

    提供流畅的 API 来构建 LLM 润色器。

    Example:
        >>> polisher = (
        ...     LLMPolisherBuilder()
        ...     .with_openai_backend(api_key="...")
        ...     .with_model("gpt-4")
        ...     .with_level(PolishLevel.DEEP)
        ...     .build()
        ... )
    """

    def __init__(self) -> None:
        """初始化构建器。"""
        self._config = PolishConfig()
        self._llm_config = LLMConfig()
        self._backend: LLMBackend | None = None
        self._prompt_template: PromptTemplate | None = None

    def with_level(self, level: PolishLevel) -> LLMPolisherBuilder:
        """设置润色等级。"""
        self._config.level = level
        return self

    def with_style(self, style: PolishStyle) -> LLMPolisherBuilder:
        """设置润色风格。"""
        self._config.style = style
        return self

    def with_model(self, model: str) -> LLMPolisherBuilder:
        """设置模型名称。"""
        self._llm_config.model = model
        return self

    def with_temperature(self, temperature: float) -> LLMPolisherBuilder:
        """设置温度参数。"""
        self._llm_config.temperature = temperature
        return self

    def with_max_tokens(self, max_tokens: int) -> LLMPolisherBuilder:
        """设置最大生成 token 数。"""
        self._llm_config.max_tokens = max_tokens
        return self

    def with_timeout(self, timeout: float) -> LLMPolisherBuilder:
        """设置超时时间。"""
        self._llm_config.timeout = timeout
        return self

    def with_retry(self, count: int, delay: float = 1.0) -> LLMPolisherBuilder:
        """设置重试参数。"""
        self._llm_config.retry_count = count
        self._llm_config.retry_delay = delay
        return self

    def with_openai_backend(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> LLMPolisherBuilder:
        """设置 OpenAI 后端。"""
        self._backend = OpenAIBackend(api_key=api_key, base_url=base_url)
        return self

    def with_anthropic_backend(
        self,
        api_key: str | None = None,
    ) -> LLMPolisherBuilder:
        """设置 Anthropic 后端。"""
        self._backend = AnthropicBackend(api_key=api_key)
        return self

    def with_mock_backend(self) -> LLMPolisherBuilder:
        """设置模拟后端（用于测试）。"""
        self._backend = MockBackend()
        return self

    def with_custom_backend(
        self,
        backend: LLMBackend,
    ) -> LLMPolisherBuilder:
        """设置自定义后端。"""
        self._backend = backend
        return self

    def with_prompt_template(
        self,
        template: PromptTemplate,
    ) -> LLMPolisherBuilder:
        """设置提示词模板。"""
        self._prompt_template = template
        return self

    def with_custom_system_prompt(
        self,
        prompt: str,
    ) -> LLMPolisherBuilder:
        """设置自定义系统提示词。"""
        if self._prompt_template is None:
            self._prompt_template = PromptTemplate()
        self._prompt_template.system_prompt = prompt
        return self

    def add_example(
        self,
        input_text: str,
        output_text: str,
    ) -> LLMPolisherBuilder:
        """添加示例。"""
        if self._prompt_template is None:
            self._prompt_template = PromptTemplate()
        self._prompt_template.add_example(input_text, output_text)
        return self

    def build(self) -> LLMPolisher:
        """
        构建 LLM 润色器。

        Returns:
            配置好的 LLM 润色器实例
        """
        return LLMPolisher(
            config=self._config,
            backend=self._backend or MockBackend(),
            llm_config=self._llm_config,
            prompt_template=self._prompt_template,
        )


# 预定义的提示词模板
class PromptTemplates:
    """预定义的提示词模板集合。"""

    @staticmethod
    def default() -> PromptTemplate:
        """默认模板。"""
        return PromptTemplate()

    @staticmethod
    def academic() -> PromptTemplate:
        """学术论文模板。"""
        return PromptTemplate(
            system_prompt="""你是一位专业的学术编辑，擅长润色学术论文。
请确保润色后的文本：
1. 使用规范的学术语言
2. 表达准确、严谨
3. 逻辑清晰
4. 符合学术写作规范

请直接输出润色后的文本。""",
        )

    @staticmethod
    def business() -> PromptTemplate:
        """商务文档模板。"""
        return PromptTemplate(
            system_prompt="""你是一位专业的商务文案编辑。
请确保润色后的文本：
1. 语言简洁有力
2. 表达专业得体
3. 突出重点信息
4. 适合商务场景

请直接输出润色后的文本。""",
        )

    @staticmethod
    def creative() -> PromptTemplate:
        """创意写作模板。"""
        return PromptTemplate(
            system_prompt="""你是一位富有创意的文字编辑。
请确保润色后的文本：
1. 语言生动有趣
2. 富有感染力
3. 适当运用修辞手法
4. 保持原文的情感基调

请直接输出润色后的文本。""",
        )

    @staticmethod
    def technical() -> PromptTemplate:
        """技术文档模板。"""
        return PromptTemplate(
            system_prompt="""你是一位专业的技术文档编辑。
请确保润色后的文本：
1. 术语使用准确
2. 表达清晰明了
3. 逻辑结构严谨
4. 易于技术读者理解

请直接输出润色后的文本。""",
        )


# 便捷函数
async def polish_with_llm(
    text: str,
    model: str = "gpt-3.5-turbo",
    api_key: str | None = None,
    level: PolishLevel = PolishLevel.MODERATE,
    style: PolishStyle = PolishStyle.FORMAL,
) -> PolishResult:
    """
    便捷函数：使用 LLM 润色文本。

    Args:
        text: 待润色文本
        model: 模型名称
        api_key: API 密钥
        level: 润色等级
        style: 润色风格

    Returns:
        润色结果
    """
    polisher = (
        LLMPolisherBuilder()
        .with_openai_backend(api_key=api_key)
        .with_model(model)
        .with_level(level)
        .with_style(style)
        .build()
    )
    return await polisher.polish_async(text)
