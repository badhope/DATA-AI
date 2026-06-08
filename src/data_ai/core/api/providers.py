"""
DATA-AI API 提供商配置

预配置的模型提供商 API 设置
"""

from typing import Any

# 预配置的提供商设置
PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    # OpenAI
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "timeout": 60.0,
        "default_headers": {
            "Content-Type": "application/json",
        },
    },
    # Anthropic
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "timeout": 60.0,
        "default_headers": {
            "Content-Type": "application/json",
            "Anthropic-Version": "2023-06-01",
        },
    },
    # DeepSeek
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "timeout": 60.0,
        "default_headers": {
            "Content-Type": "application/json",
        },
    },
    # SiliconFlow
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "timeout": 60.0,
        "default_headers": {
            "Content-Type": "application/json",
        },
    },
    # Google Gemini
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "timeout": 60.0,
        "default_headers": {
            "Content-Type": "application/json",
        },
    },
    # Azure OpenAI
    "azure": {
        "base_url": "",  # 需要用户配置: https://{resource}.openai.azure.com/openai/deployments/{deployment}
        "timeout": 60.0,
        "default_headers": {
            "Content-Type": "application/json",
            "api-key": "",  # 通过 api_key 参数传入
        },
    },
    # AWS Bedrock
    "aws": {
        "base_url": "",  # 通过 boto3 调用，不需要直接配置
        "timeout": 60.0,
    },
    # Ollama (本地)
    "ollama": {
        "base_url": "http://localhost:11434/api",
        "timeout": 120.0,
        "default_headers": {
            "Content-Type": "application/json",
        },
    },
    # vLLM (本地)
    "vllm": {
        "base_url": "http://localhost:8000/v1",
        "timeout": 120.0,
        "default_headers": {
            "Content-Type": "application/json",
        },
    },
    # LM Studio (本地)
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "timeout": 120.0,
        "default_headers": {
            "Content-Type": "application/json",
        },
    },
}


def get_provider_config(provider: str) -> dict[str, Any]:
    """
    获取提供商配置

    Args:
        provider: 提供商名称

    Returns:
        提供商配置字典

    Raises:
        ValueError: 未知的提供商
    """
    if provider not in PROVIDER_CONFIGS:
        raise ValueError(f"未知的提供商: {provider}. 支持的提供商: {', '.join(PROVIDER_CONFIGS.keys())}")
    return PROVIDER_CONFIGS[provider].copy()


def register_provider(
    name: str,
    base_url: str,
    **kwargs,
) -> None:
    """
    注册新的提供商

    Args:
        name: 提供商名称
        base_url: 基础 URL
        **kwargs: 其他配置
    """
    PROVIDER_CONFIGS[name] = {
        "base_url": base_url,
        **kwargs,
    }
