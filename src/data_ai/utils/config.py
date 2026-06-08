"""
DATA-AI 配置管理系统

使用 Pydantic Settings v2 管理配置，支持：
- 环境变量（最高优先级）
- TOML 配置文件
- 默认值（最低优先级）

配置优先级（从高到低）：
1. 环境变量
2. config.toml 文件
3. 默认值

TOML 文件路径：
- config/config.toml
- ~/.data-ai/config.toml
- 当前目录的 config.toml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─── TOML 文件加载工具 ──────────────────────────────────────────────────────


def _load_toml_file(file_path: Path) -> dict[str, Any]:
    """安全加载 TOML 文件"""
    if not file_path.exists():
        return {}
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(file_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _find_config_file() -> Path | None:
    """查找配置文件，按优先级返回第一个存在的"""
    candidates = [
        Path("config/config.toml"),
        Path.home() / ".data-ai" / "config.toml",
        Path.cwd() / "config.toml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """将嵌套字典展平为扁平字典，键用 sep 分隔"""
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


# ─── LLM 配置 ────────────────────────────────────────────────────────────────


class LLMConfig(BaseSettings):
    """LLM 模型配置"""

    model: str = Field(
        default="claude-3-5-sonnet-20250619",
        description="默认使用的 LLM 模型",
    )
    base_url: str | None = Field(default=None, description="API 端点 URL")
    api_key: str | None = Field(default=None, description="API 密钥")
    max_tokens: int = Field(default=8192, ge=1, le=100000)
    max_input_tokens: int | None = Field(default=None, ge=1)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    api_type: str = Field(default="anthropic")
    api_version: str | None = Field(default=None)

    model_config = SettingsConfigDict(
        env_prefix="DATA_AI_LLM_",
        env_ignore_empty=True,
        extra="ignore",
    )


class VisionConfig(BaseSettings):
    """视觉模型配置"""

    model: str = Field(default="claude-3-5-sonnet-20250619")
    base_url: str | None = Field(default=None)
    api_key: str | None = Field(default=None)
    max_tokens: int = Field(default=8192)
    temperature: float = Field(default=0.0)

    model_config = SettingsConfigDict(
        env_prefix="DATA_AI_VISION_",
        env_ignore_empty=True,
        extra="ignore",
    )


# ─── 搜索配置 ────────────────────────────────────────────────────────────────


class SearchConfig(BaseSettings):
    """搜索引擎配置"""

    engine: str = Field(default="DuckDuckGo")
    fallback_engines: list[str] = Field(default_factory=lambda: ["DuckDuckGo", "Baidu"])
    retry_delay: int = Field(default=60, ge=0)
    max_retries: int = Field(default=3, ge=0)
    lang: str = Field(default="en")
    country: str = Field(default="us")

    model_config = SettingsConfigDict(
        env_prefix="DATA_AI_SEARCH_",
        env_ignore_empty=True,
        extra="ignore",
    )


# ─── 沙箱配置 ───────────────────────────────────────────────────────────────


class SandboxConfig(BaseSettings):
    """沙箱执行环境配置"""

    enabled: bool = Field(default=True)
    sandbox_type: Literal["local", "docker", "daytona", "remote"] = Field(default="local")
    work_dir: str = Field(default="/tmp/data-ai-sandbox")
    timeout: int = Field(default=300, ge=1, le=3600)
    network_enabled: bool = Field(default=True)
    docker_image: str = Field(default="python:3.11-slim")
    docker_memory_limit: str = Field(default="1g")
    docker_cpu_limit: float = Field(default=2.0, ge=0.1)

    model_config = SettingsConfigDict(
        env_prefix="DATA_AI_SANDBOX_",
        env_ignore_empty=True,
        extra="ignore",
    )


# ─── 记忆配置 ───────────────────────────────────────────────────────────────


class MemoryConfig(BaseSettings):
    """记忆系统配置"""

    enabled: bool = Field(default=True)
    enable_long_term_memory: bool = Field(default=True)
    enable_conversation_summarization: bool = Field(default=True)
    keep_recent_messages: int = Field(default=20, ge=1)
    summary_interval: int = Field(default=10, ge=1)
    max_summary_length: int = Field(default=1000, ge=100)
    memory_dir: str = Field(default="")
    auto_save_interval: int = Field(default=30, ge=1)

    model_config = SettingsConfigDict(
        env_prefix="DATA_AI_MEMORY_",
        env_ignore_empty=True,
        extra="ignore",
    )


class VectorConfig(BaseSettings):
    """向量存储配置"""

    enabled: bool = Field(default=False)
    store_type: Literal["chroma", "faiss", "lance"] = Field(default="chroma")
    collection_name: str = Field(default="data-ai-memory")
    persist_directory: str = Field(default="")
    embedding_model: str = Field(default="all-MiniLM-L6-v2")

    model_config = SettingsConfigDict(
        env_prefix="DATA_AI_VECTOR_",
        env_ignore_empty=True,
        extra="ignore",
    )


# ─── 主配置 ─────────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """
    DATA-AI 全局配置

    配置优先级（从高到低）：
    1. 环境变量（DATA_AI_* 前缀）
    2. config.toml 文件
    3. 默认值

    环境变量示例：
        DATA_AI_API_KEY=sk-xxx
        DATA_AI_MODEL=claude-3-5-sonnet
        DATA_AI_LOG_LEVEL=INFO
        DATA_AI_DEBUG=1
    """

    debug: bool = Field(default=False)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    log_file: str | None = Field(default=None)

    llm: LLMConfig = Field(default_factory=LLMConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    vector: VectorConfig = Field(default_factory=VectorConfig)

    mcp_server_reference: str = Field(default="data_ai.core.mcp.server")

    model_config = SettingsConfigDict(
        env_prefix="DATA_AI_",
        env_ignore_empty=True,
        env_nested_delimiter="__",
        extra="ignore",
    )

    @model_validator(mode="after")
    def _resolve_dirs_and_load_toml(self) -> Settings:
        """解析目录路径并加载 TOML 配置"""
        # 1. 解析相对路径为绝对路径
        if self.memory.memory_dir:
            self.memory.memory_dir = str(Path(self.memory.memory_dir).expanduser().resolve())
        else:
            default_mem_dir = Path.home() / ".data-ai" / "memory"
            self.memory.memory_dir = str(default_mem_dir)

        self.sandbox.work_dir = str(Path(self.sandbox.work_dir).expanduser().resolve())

        if self.vector.persist_directory:
            self.vector.persist_directory = str(Path(self.vector.persist_directory).expanduser().resolve())
        else:
            default_vec_dir = Path.home() / ".data-ai" / "vectorstore"
            self.vector.persist_directory = str(default_vec_dir)

        # 2. 加载 TOML 配置（如果存在）
        toml_path = _find_config_file()
        if toml_path:
            toml_data = _load_toml_file(toml_path)
            self._merge_toml_config(toml_data)

        return self

    def _merge_toml_config(self, toml_data: dict[str, Any]) -> None:
        """从 TOML 数据合并配置到当前设置"""
        if "llm" in toml_data:
            llm_data = toml_data["llm"]
            if isinstance(llm_data, dict):
                if "model" in llm_data:
                    self.llm.model = str(llm_data["model"])
                if "base_url" in llm_data:
                    self.llm.base_url = str(llm_data["base_url"]) if llm_data["base_url"] else None
                if "api_key" in llm_data:
                    api_key = llm_data["api_key"]
                    if api_key and not str(api_key).startswith("YOUR_"):
                        self.llm.api_key = str(api_key)
                if "max_tokens" in llm_data:
                    self.llm.max_tokens = int(llm_data["max_tokens"])
                if "temperature" in llm_data:
                    self.llm.temperature = float(llm_data["temperature"])
                if "api_type" in llm_data:
                    self.llm.api_type = str(llm_data["api_type"])

        if "sandbox" in toml_data:
            sandbox_data = toml_data["sandbox"]
            if isinstance(sandbox_data, dict):
                if "use_sandbox" in sandbox_data or "enabled" in sandbox_data:
                    self.sandbox.enabled = sandbox_data.get("use_sandbox", sandbox_data.get("enabled", True))
                if "sandbox_type" in sandbox_data:
                    self.sandbox.sandbox_type = str(sandbox_data["sandbox_type"])
                if "work_dir" in sandbox_data:
                    self.sandbox.work_dir = str(sandbox_data["work_dir"])
                if "timeout" in sandbox_data:
                    self.sandbox.timeout = int(sandbox_data["timeout"])
                if "network_enabled" in sandbox_data:
                    self.sandbox.network_enabled = bool(sandbox_data["network_enabled"])

        if "memory" in toml_data:
            memory_data = toml_data["memory"]
            if isinstance(memory_data, dict):
                if "enable_long_term_memory" in memory_data:
                    self.memory.enable_long_term_memory = bool(memory_data["enable_long_term_memory"])
                if "memory_dir" in memory_data and memory_data["memory_dir"]:
                    self.memory.memory_dir = str(memory_data["memory_dir"])

        if "search" in toml_data:
            search_data = toml_data["search"]
            if isinstance(search_data, dict):
                if "engine" in search_data:
                    self.search.engine = str(search_data["engine"])
                if "fallback_engines" in search_data:
                    self.search.fallback_engines = list(search_data["fallback_engines"])


# ─── 全局配置实例 ────────────────────────────────────────────────────────────

_settings_cache: Settings | None = None


def get_settings(reload: bool = False) -> Settings:
    """获取全局配置单例"""
    global _settings_cache
    if _settings_cache is None or reload:
        _settings_cache = Settings()
    return _settings_cache


def reload_settings() -> Settings:
    """重新加载配置"""
    global _settings_cache
    _settings_cache = Settings()
    return _settings_cache


# ─── 便捷访问 ───────────────────────────────────────────────────────────────

llm_config = LLMConfig()
sandbox_config = SandboxConfig()
memory_config = MemoryConfig()


# ─── 配置验证工具 ────────────────────────────────────────────────────────────


def validate_api_key(api_key: str | None, provider: str) -> str:
    """
    验证 API 密钥是否已配置

    Args:
        api_key: API 密钥
        provider: 提供商名称

    Returns:
        验证通过的 API 密钥

    Raises:
        ConfigValidationError: 密钥未配置时抛出
    """
    from data_ai.utils.exceptions import ConfigValidationError

    if not api_key or str(api_key).startswith("YOUR_") or api_key == "sk-xxx":
        raise ConfigValidationError(
            f"{provider} API key not configured. "
            f"Please set DATA_AI_API_KEY environment variable "
            f"or configure in config.toml.",
            field="llm.api_key",
        )
    return api_key
