"""后端文案 catalog — 英文 + 简体中文两套。

所有 key 集中在这里，方便审计 / 翻译。开发时新增文案只需：
1. 在 ``CATALOG_EN`` / ``CATALOG_ZH`` 同时新增条目
2. 调用 ``tr("namespace.key", locale)``
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any


class Locale(str, Enum):
    """支持的语言。字符串值与 HTTP ``Accept-Language`` 一致。"""

    EN = "en"
    ZH = "zh"


DEFAULT_LOCALE: Locale = Locale.EN
SUPPORTED_LOCALES: tuple[Locale, ...] = (Locale.EN, Locale.ZH)


# ── 英文 catalog ─────────────────────────────────────────────────────
CATALOG_EN: dict[str, str] = {
    # API 通用错误
    "api.error.internal": "Internal server error",
    "api.error.not_found": "Resource not found",
    "api.error.unauthorized": "Unauthorized",
    "api.error.forbidden": "Forbidden",
    "api.error.bad_request": "Bad request: {reason}",
    "api.error.model_not_found": "Model '{name}' is not registered",
    "api.error.model_unavailable": "Model '{name}' is unavailable: {reason}",
    "api.error.session_not_found": "Session '{session_id}' not found",
    "api.error.agent_not_found": "Agent '{agent_id}' not found",
    "api.error.preset_not_found": "Agent preset '{role}' not found",
    "api.error.team_not_found": "Agent team '{team_id}' not found",
    "api.error.skill_not_found": "Skill '{skill_name}' not found",
    "api.error.tool_not_found": "Tool '{tool_name}' not found",
    "api.error.sandbox_failed": "Sandbox execution failed: {reason}",
    "api.error.rag_failed": "RAG operation failed: {reason}",
    "api.error.memory_failed": "Memory operation failed: {reason}",
    "api.error.memory_not_found": "Memory '{memory_id}' not found",
    "api.error.stream_not_supported": "Streaming is not supported for this endpoint",
    "api.error.locale_unsupported": "Locale '{locale}' is not supported",
    "api.error.snapshot_exists": "Snapshot '{name}' already exists",
    "api.error.snapshot_not_found": "Snapshot '{name}' not found",
    "api.error.file_path_invalid": "Invalid file path: {path}",
    "api.error.file_read_failed": "Failed to read file: {reason}",
    "api.error.file_write_failed": "Failed to write file: {reason}",
    "api.error.file_not_found": "File not found: {path}",
    "api.error.invalid_state": "Illegal state: {reason}",
    # Chat
    "api.chat.empty_message": "Message content is empty",
    "api.chat.too_long": "Message exceeds maximum length of {limit} characters",
    "api.chat.no_model": "No chat model is available. Please register a model first.",
    # Agent
    "api.agent.invalid_config": "Invalid agent configuration: {reason}",
    "api.agent.run_failed": "Agent run failed: {reason}",
    "api.agent.iteration_limit": "Agent exceeded iteration limit ({limit})",
    # Skill / Tool
    "api.tool.execution_failed": "Tool '{tool_name}' execution failed: {reason}",
    "api.skill.execution_failed": "Skill '{skill_name}' execution failed: {reason}",
    "api.skill.not_found": "Skill '{skill_name}' not found",
    "api.skill.invalid_page_range": "Invalid page range: {ranges}",
    # Sandbox
    "api.sandbox.timeout": "Sandbox execution timed out after {seconds}s",
    "api.sandbox.not_found": "Sandbox '{sandbox_id}' not found",
    "api.sandbox.file_not_found": "File not found: {path}",
    # 系统
    "api.system.starting": "DATA-AI server is starting",
    "api.system.ready": "DATA-AI server is ready",
    "api.system.health_ok": "All systems operational",
    "api.system.health_degraded": "System is degraded: {reason}",
    "api.system.health_down": "System is down: {reason}",
    # 模型 / Provider
    "api.model.registered": "Model '{name}' registered",
    "api.model.list": "Available models: {names}",
    # Agent 回复语言指令
    "agent.locale.system_prompt": "You are the assistant of DATA-AI. Always reply in {language} unless the user explicitly requests another language. Keep your tone professional, friendly, and concise.",
    "agent.locale.language_en": "English",
    "agent.locale.language_zh": "Simplified Chinese",
}


# ── 中文 catalog ─────────────────────────────────────────────────────
CATALOG_ZH: dict[str, str] = {
    # API 通用错误
    "api.error.internal": "服务器内部错误",
    "api.error.not_found": "资源不存在",
    "api.error.unauthorized": "未授权",
    "api.error.forbidden": "无权限",
    "api.error.bad_request": "请求参数错误：{reason}",
    "api.error.model_not_found": "模型「{name}」未注册",
    "api.error.model_unavailable": "模型「{name}」不可用：{reason}",
    "api.error.session_not_found": "会话「{session_id}」不存在",
    "api.error.agent_not_found": "智能体「{agent_id}」不存在",
    "api.error.preset_not_found": "智能体预设「{role}」不存在",
    "api.error.team_not_found": "智能体团队「{team_id}」不存在",
    "api.error.skill_not_found": "技能「{skill_name}」不存在",
    "api.error.tool_not_found": "工具「{tool_name}」不存在",
    "api.error.sandbox_failed": "沙箱执行失败：{reason}",
    "api.error.rag_failed": "RAG 操作失败：{reason}",
    "api.error.memory_failed": "记忆操作失败：{reason}",
    "api.error.memory_not_found": "记忆「{memory_id}」不存在",
    "api.error.stream_not_supported": "当前端点不支持流式响应",
    "api.error.locale_unsupported": "不支持的语言「{locale}」",
    "api.error.snapshot_exists": "快照「{name}」已存在",
    "api.error.snapshot_not_found": "快照「{name}」不存在",
    "api.error.file_path_invalid": "非法的文件路径：{path}",
    "api.error.file_read_failed": "读取文件失败：{reason}",
    "api.error.file_write_failed": "写入文件失败：{reason}",
    "api.error.file_not_found": "文件不存在：{path}",
    "api.error.invalid_state": "非法状态：{reason}",
    # Chat
    "api.chat.empty_message": "消息内容不能为空",
    "api.chat.too_long": "消息超过最大长度 {limit} 字符",
    "api.chat.no_model": "暂无可用的聊天模型，请先注册一个模型。",
    # Agent
    "api.agent.invalid_config": "智能体配置无效：{reason}",
    "api.agent.run_failed": "智能体运行失败：{reason}",
    "api.agent.iteration_limit": "智能体超过最大迭代次数（{limit}）",
    # Skill / Tool
    "api.tool.execution_failed": "工具「{tool_name}」执行失败：{reason}",
    "api.skill.execution_failed": "技能「{skill_name}」执行失败：{reason}",
    "api.skill.not_found": "技能「{skill_name}」不存在",
    "api.skill.invalid_page_range": "无法解析页码范围：{ranges}",
    # Sandbox
    "api.sandbox.timeout": "沙箱执行超时（{seconds}秒）",
    "api.sandbox.not_found": "沙箱「{sandbox_id}」不存在",
    "api.sandbox.file_not_found": "文件不存在：{path}",
    # 系统
    "api.system.starting": "DATA-AI 服务正在启动",
    "api.system.ready": "DATA-AI 服务已就绪",
    "api.system.health_ok": "所有系统运行正常",
    "api.system.health_degraded": "系统降级运行：{reason}",
    "api.system.health_down": "系统不可用：{reason}",
    # 模型 / Provider
    "api.model.registered": "模型「{name}」已注册",
    "api.model.list": "可用模型：{names}",
    # Agent 回复语言指令
    "agent.locale.system_prompt": "你是 DATA-AI 的智能助手，除非用户明确要求其他语言，否则请始终使用{language}回复。保持专业、友好、简洁的语气。",
    "agent.locale.language_en": "英文",
    "agent.locale.language_zh": "简体中文",
}


_CATALOGS: dict[Locale, dict[str, str]] = {
    Locale.EN: CATALOG_EN,
    Locale.ZH: CATALOG_ZH,
}


def _coerce_locale(value: Any) -> Locale:
    """宽松地把任意输入转换成 Locale。"""
    if isinstance(value, Locale):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("en", "en-us", "en-gb"):
            return Locale.EN
        if s in ("zh", "zh-cn", "zh-hans", "zh-hans-cn"):
            return Locale.ZH
    return DEFAULT_LOCALE


def tr(
    key: str,
    locale: Any = DEFAULT_LOCALE,
    /,
    *,
    params: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> str:
    """根据 ``locale`` 翻译 ``key``，缺失时回退到默认 locale 并最终返回 ``[key]``。

    用法::

        tr("api.error.not_found", locale)
        tr("api.error.bad_request", locale, reason="missing field")
        tr("api.error.bad_request", locale, params={"reason": "missing field"})

    占位符使用 Python ``str.format`` 语法。
    """
    loc = _coerce_locale(locale)
    catalog = _CATALOGS.get(loc, _CATALOGS[DEFAULT_LOCALE])
    template = catalog.get(key)
    if template is None:
        # 缺失 → 回退到默认 locale
        if loc != DEFAULT_LOCALE:
            template = _CATALOGS[DEFAULT_LOCALE].get(key)
        if template is None:
            return f"[{key}]"
    fmt = dict(params or {})
    fmt.update(kwargs)
    if not fmt:
        return template
    try:
        return template.format(**fmt)
    except (KeyError, IndexError):
        # 占位符与传入参数不匹配 → 原样返回模板
        return template
