"""
DATA-AI 新手引导向导

提供交互式设置向导，帮助新用户快速配置系统。
支持首次启动检测和分步配置。
"""

from __future__ import annotations

import getpass
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)


# 首次启动标记文件
FIRST_RUN_MARKER = Path.home() / ".data-ai" / ".first_run_complete"
# 向导生成的配置文件
WIZARD_CONFIG_FILE = Path.home() / ".data-ai" / "config.toml"


class WizardStep(Enum):
    """向导步骤"""

    WELCOME = "welcome"
    PROVIDER = "provider"
    API_KEY = "api_key"
    MODEL = "model"
    MEMORY = "memory"
    SANDBOX = "sandbox"
    COMPLETE = "complete"


@dataclass
class ProviderInfo:
    """提供商信息"""

    name: str
    display_name: str
    description: str
    default_model: str
    models: list[str]
    requires_api_key: bool = True
    base_url: str | None = None


@dataclass
class WizardResult:
    """向导结果"""

    provider: str
    api_key: str
    model: str
    memory_enabled: bool
    sandbox_enabled: bool
    sandbox_type: str


class SetupWizard:
    """
    设置向导

    提供7步交互式配置引导：
    1. 欢迎 - 介绍向导
    2. 选择提供商 - 选择 LLM 提供商
    3. 输入 API Key - 配置 API 密钥
    4. 选择模型 - 选择默认模型
    5. 配置记忆 - 启用/禁用记忆功能
    6. 配置沙箱 - 配置代码执行环境
    7. 生成配置 - 保存配置并完成

    Attributes:
        _providers: 支持的提供商列表
        _results: 配置结果字典
        _current_step: 当前步骤

    Example:
        >>> wizard = SetupWizard()
        >>> if wizard.is_first_run():
        ...     wizard.run()
    """

    def __init__(self):
        """初始化设置向导"""
        self._providers: dict[str, ProviderInfo] = {}
        self._results: dict[str, Any] = {}
        self._current_step: WizardStep = WizardStep.WELCOME
        self._init_providers()
        logger.info("设置向导已初始化")

    def _init_providers(self) -> None:
        """初始化支持的提供商信息"""
        self._providers = {
            "anthropic": ProviderInfo(
                name="anthropic",
                display_name="Anthropic (Claude)",
                description="Claude 系列模型，强大的推理和代码能力",
                default_model="claude-3-5-sonnet-20250619",
                models=[
                    "claude-3-5-sonnet-20250619",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229",
                ],
                requires_api_key=True,
            ),
            "openai": ProviderInfo(
                name="openai",
                display_name="OpenAI (GPT)",
                description="GPT 系列模型，广泛使用的通用模型",
                default_model="gpt-4o",
                models=[
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                    "gpt-3.5-turbo",
                ],
                requires_api_key=True,
            ),
            "deepseek": ProviderInfo(
                name="deepseek",
                display_name="DeepSeek",
                description="国产开源大模型，代码能力强",
                default_model="deepseek-chat",
                models=[
                    "deepseek-chat",
                    "deepseek-coder",
                ],
                requires_api_key=True,
            ),
            "siliconflow": ProviderInfo(
                name="siliconflow",
                display_name="SiliconFlow",
                description="国内模型聚合平台，支持多种开源模型",
                default_model="Qwen/Qwen2.5-72B-Instruct",
                models=[
                    "Qwen/Qwen2.5-72B-Instruct",
                    "meta-llama/Llama-3.3-70B-Instruct",
                    "deepseek-ai/DeepSeek-V3",
                ],
                requires_api_key=True,
            ),
            "ollama": ProviderInfo(
                name="ollama",
                display_name="Ollama (本地)",
                description="本地运行开源模型，无需 API Key",
                default_model="llama3.2",
                models=[
                    "llama3.2",
                    "qwen2.5",
                    "deepseek-coder",
                    "codellama",
                ],
                requires_api_key=False,
                base_url="http://localhost:11434",
            ),
        }

    @staticmethod
    def is_first_run() -> bool:
        """
        检查是否为首次运行

        Returns:
            是否为首次运行
        """
        # 检查标记文件
        if FIRST_RUN_MARKER.exists():
            return False

        # 检查是否已有配置文件
        if WIZARD_CONFIG_FILE.exists():
            return False

        # 检查环境变量是否已配置
        if os.getenv("DATA_AI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"):
            return False

        return True

    @staticmethod
    def mark_first_run_complete() -> None:
        """标记首次运行已完成"""
        FIRST_RUN_MARKER.parent.mkdir(parents=True, exist_ok=True)
        FIRST_RUN_MARKER.touch()
        logger.info("已标记首次运行完成")

    def run(self) -> WizardResult | None:
        """
        运行完整的设置向导

        Returns:
            WizardResult 对象，用户取消返回 None
        """
        print(self._get_welcome_screen())

        try:
            # 步骤 2: 选择提供商
            provider = self._step_provider()
            if provider is None:
                return None
            self._results["provider"] = provider

            # 步骤 3: 输入 API Key
            api_key = self._step_api_key(provider)
            if api_key is None:
                return None
            self._results["api_key"] = api_key

            # 步骤 4: 选择模型
            model = self._step_model(provider)
            if model is None:
                return None
            self._results["model"] = model

            # 步骤 5: 配置记忆
            memory_enabled = self._step_memory()
            self._results["memory_enabled"] = memory_enabled

            # 步骤 6: 配置沙箱
            sandbox_enabled, sandbox_type = self._step_sandbox()
            self._results["sandbox_enabled"] = sandbox_enabled
            self._results["sandbox_type"] = sandbox_type

            # 步骤 7: 生成配置
            result = self._step_complete()

            # 标记首次运行完成
            self.mark_first_run_complete()

            return result

        except KeyboardInterrupt:
            print("\n\n向导已取消。您可以随时运行 :wizard 重新启动。")
            return None
        except Exception as e:
            logger.error(f"向导执行失败: {e}")
            print(f"\n向导执行失败: {e}")
            return None

    def _get_welcome_screen(self) -> str:
        """获取欢迎界面"""
        return """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║                   欢迎使用 DATA-AI 设置向导                       ║
║                                                                  ║
║  本向导将帮助您完成初始配置，大约需要 2-3 分钟。                  ║
║                                                                  ║
║  配置内容包括：                                                   ║
║    1. 选择 AI 提供商 (OpenAI, Anthropic, 本地模型等)             ║
║    2. 配置 API 密钥                                              ║
║    3. 选择默认模型                                               ║
║    4. 配置记忆功能                                               ║
║    5. 配置代码执行沙箱                                           ║
║                                                                  ║
║  您可以随时按 Ctrl+C 取消向导。                                   ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""

    def _step_provider(self) -> str | None:
        """
        步骤 2: 选择提供商

        Returns:
            提供商名称，用户取消返回 None
        """
        print("\n【步骤 1/6】选择 AI 提供商\n")

        providers = list(self._providers.values())
        for i, provider in enumerate(providers, 1):
            print(f"  {i}. {provider.display_name}")
            print(f"     {provider.description}")
            print()

        while True:
            try:
                choice = input(f"请输入选项 (1-{len(providers)}): ").strip()

                if choice.lower() in ("q", "quit", "exit"):
                    return None

                idx = int(choice) - 1
                if 0 <= idx < len(providers):
                    provider = providers[idx]
                    print(f"\n已选择: {provider.display_name}")
                    return provider.name
                else:
                    print("无效选项，请重试")

            except ValueError:
                print("请输入数字")
            except KeyboardInterrupt:
                return None

    def _step_api_key(self, provider_name: str) -> str | None:
        """
        步骤 3: 输入 API Key

        Args:
            provider_name: 提供商名称

        Returns:
            API Key，用户取消返回 None
        """
        provider = self._providers[provider_name]

        print("\n【步骤 2/6】配置 API 密钥\n")
        print(f"提供商: {provider.display_name}")

        if not provider.requires_api_key:
            print("\n该提供商为本地模型，无需 API Key")
            print(f"请确保 Ollama 服务已启动: {provider.base_url}")
            return ""

        print("\n请输入您的 API Key")
        print("  - 输入不会显示在屏幕上")
        print("  - 获取方式请查看提供商官网")
        print()

        while True:
            try:
                api_key = getpass.getpass("API Key: ").strip()

                if not api_key:
                    print("API Key 不能为空")
                    continue

                # 简单验证
                if len(api_key) < 10:
                    print("API Key 似乎太短，请检查")
                    continue

                # 确认
                masked_key = api_key[:8] + "*" * (len(api_key) - 8)
                print(f"\n已输入: {masked_key}")
                confirm = input("确认使用此 API Key? (y/n): ").strip().lower()

                if confirm in ("y", "yes"):
                    return api_key
                else:
                    print("请重新输入")

            except KeyboardInterrupt:
                return None

    def _step_model(self, provider_name: str) -> str | None:
        """
        步骤 4: 选择模型

        Args:
            provider_name: 提供商名称

        Returns:
            模型名称，用户取消返回 None
        """
        provider = self._providers[provider_name]

        print("\n【步骤 3/6】选择默认模型\n")
        print(f"提供商: {provider.display_name}")
        print()

        models = provider.models
        for i, model in enumerate(models, 1):
            default_mark = " (推荐)" if model == provider.default_model else ""
            print(f"  {i}. {model}{default_mark}")

        print()

        while True:
            try:
                choice = input(f"请输入选项 (1-{len(models)}, 直接回车使用推荐): ").strip()

                if choice == "":
                    print(f"\n使用推荐模型: {provider.default_model}")
                    return provider.default_model

                if choice.lower() in ("q", "quit", "exit"):
                    return None

                idx = int(choice) - 1
                if 0 <= idx < len(models):
                    model = models[idx]
                    print(f"\n已选择模型: {model}")
                    return model
                else:
                    print("无效选项，请重试")

            except ValueError:
                print("请输入数字")
            except KeyboardInterrupt:
                return None

    def _step_memory(self) -> bool:
        """
        步骤 5: 配置记忆

        Returns:
            是否启用记忆
        """
        print("\n【步骤 4/6】配置记忆功能\n")
        print("记忆功能可以让 AI 记住之前的对话内容，提供更连贯的交互体验。")
        print()
        print("  1. 启用记忆 (推荐)")
        print("  2. 禁用记忆")
        print()

        while True:
            try:
                choice = input("请选择 (1-2, 直接回车启用): ").strip()

                if choice == "":
                    print("\n已启用记忆功能")
                    return True

                if choice == "1":
                    print("\n已启用记忆功能")
                    return True
                elif choice == "2":
                    print("\n已禁用记忆功能")
                    return False
                else:
                    print("无效选项，请重试")

            except KeyboardInterrupt:
                return True

    def _step_sandbox(self) -> tuple[bool, str]:
        """
        步骤 6: 配置沙箱

        Returns:
            (是否启用沙箱, 沙箱类型)
        """
        print("\n【步骤 5/6】配置代码执行沙箱\n")
        print("沙箱提供安全的代码执行环境，AI 可以运行和测试代码。")
        print()
        print("  1. 启用本地沙箱 (推荐)")
        print("  2. 启用 Docker 沙箱 (需要 Docker)")
        print("  3. 禁用沙箱")
        print()

        while True:
            try:
                choice = input("请选择 (1-3, 直接回车启用本地沙箱): ").strip()

                if choice == "" or choice == "1":
                    print("\n已启用本地沙箱")
                    return True, "local"
                elif choice == "2":
                    print("\n已启用 Docker 沙箱")
                    return True, "docker"
                elif choice == "3":
                    print("\n已禁用沙箱")
                    return False, "local"
                else:
                    print("无效选项，请重试")

            except KeyboardInterrupt:
                return True, "local"

    def _step_complete(self) -> WizardResult:
        """
        步骤 7: 生成配置

        Returns:
            WizardResult 对象
        """
        print("\n【步骤 6/6】生成配置\n")

        # 创建结果对象
        result = WizardResult(
            provider=self._results["provider"],
            api_key=self._results["api_key"],
            model=self._results["model"],
            memory_enabled=self._results["memory_enabled"],
            sandbox_enabled=self._results["sandbox_enabled"],
            sandbox_type=self._results["sandbox_type"],
        )

        # 生成配置文件
        config_content = self._generate_config(result)

        # 保存配置
        WIZARD_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(WIZARD_CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(config_content)

        print("配置已保存到:", WIZARD_CONFIG_FILE)
        print()
        print("配置摘要:")
        print(f"  提供商: {self._providers[result.provider].display_name}")
        print(f"  模型: {result.model}")
        print(f"  记忆功能: {'启用' if result.memory_enabled else '禁用'}")
        print(f"  沙箱: {'启用' if result.sandbox_enabled else '禁用'} ({result.sandbox_type})")
        print()
        print("您可以使用 :config 命令随时修改配置。")
        print()
        print("按 Enter 键开始体验 DATA-AI...")

        try:
            input()
        except KeyboardInterrupt:
            pass

        return result

    def _generate_config(self, result: WizardResult) -> str:
        """
        生成配置文件内容

        Args:
            result: 向导结果

        Returns:
            TOML 格式的配置内容
        """
        provider = self._providers[result.provider]

        lines = [
            "# DATA-AI 配置文件",
            "# 由设置向导生成",
            "",
            "[llm]",
            f'model = "{result.model}"',
        ]

        if result.api_key:
            lines.append(f'api_key = "{result.api_key}"')

        if provider.base_url:
            lines.append(f'base_url = "{provider.base_url}"')

        lines.extend(
            [
                f'api_type = "{result.provider}"',
                "temperature = 0.7",
                "max_tokens = 8192",
                "",
                "[memory]",
                f"enable_long_term_memory = {str(result.memory_enabled).lower()}",
                "keep_recent_messages = 20",
                "",
                "[sandbox]",
                f"enabled = {str(result.sandbox_enabled).lower()}",
                f'sandbox_type = "{result.sandbox_type}"',
                "timeout = 300",
                "network_enabled = true",
                "",
            ]
        )

        return "\n".join(lines)

    def run_quick_setup(self) -> WizardResult | None:
        """
        快速设置模式

        使用默认配置快速完成设置

        Returns:
            WizardResult 对象
        """
        print("\n【快速设置】\n")
        print("将使用以下默认配置:")
        print("  提供商: Anthropic (Claude)")
        print("  模型: claude-3-5-sonnet-20250619")
        print("  记忆功能: 启用")
        print("  沙箱: 启用 (本地)")
        print()

        try:
            api_key = getpass.getpass("请输入 Anthropic API Key (或按 Ctrl+C 取消): ").strip()

            if not api_key:
                print("API Key 不能为空")
                return None

            result = WizardResult(
                provider="anthropic",
                api_key=api_key,
                model="claude-3-5-sonnet-20250619",
                memory_enabled=True,
                sandbox_enabled=True,
                sandbox_type="local",
            )

            # 保存配置
            config_content = self._generate_config(result)
            WIZARD_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(WIZARD_CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(config_content)

            self.mark_first_run_complete()

            print("\n快速设置完成！")
            return result

        except KeyboardInterrupt:
            return None

    def show_setup_status(self) -> str:
        """
        显示当前设置状态

        Returns:
            状态文本
        """
        lines = ["\n【设置状态】\n"]

        # 检查配置文件
        if WIZARD_CONFIG_FILE.exists():
            lines.append(f"配置文件: {WIZARD_CONFIG_FILE} (存在)")
        else:
            lines.append(f"配置文件: {WIZARD_CONFIG_FILE} (不存在)")

        # 检查首次运行标记
        if FIRST_RUN_MARKER.exists():
            lines.append("首次运行: 已完成")
        else:
            lines.append("首次运行: 未完成")

        # 检查环境变量
        env_vars = ["DATA_AI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
        configured = [v for v in env_vars if os.getenv(v)]
        if configured:
            lines.append(f"环境变量: 已配置 ({', '.join(configured)})")
        else:
            lines.append("环境变量: 未配置")

        lines.append("")
        return "\n".join(lines)


# 全局向导实例
_wizard: SetupWizard | None = None


def get_wizard() -> SetupWizard:
    """
    获取全局设置向导实例

    Returns:
        SetupWizard 单例实例
    """
    global _wizard
    if _wizard is None:
        _wizard = SetupWizard()
    return _wizard


def run_wizard() -> WizardResult | None:
    """
    便捷函数：运行设置向导

    Returns:
        WizardResult 对象
    """
    return get_wizard().run()


def run_quick_setup() -> WizardResult | None:
    """
    便捷函数：运行快速设置

    Returns:
        WizardResult 对象
    """
    return get_wizard().run_quick_setup()


def is_first_run() -> bool:
    """
    便捷函数：检查是否为首次运行

    Returns:
        是否为首次运行
    """
    return SetupWizard.is_first_run()


def show_setup_status() -> str:
    """
    便捷函数：显示设置状态

    Returns:
        状态文本
    """
    return get_wizard().show_setup_status()
