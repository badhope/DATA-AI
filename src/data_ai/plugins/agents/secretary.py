"""
秘书 Agent 预设

解决"日程、提醒、会议纪要、草拟邮件、查资料"这些碎片化任务的痛点。
强调"长期记忆"+"轻量响应",不堆功能。

用法:
    from data_ai.plugins.agents.secretary import PRESET, build_agent
    agent = build_agent(llm_manager=llm_mgr, memory=mem, store=ctx_store)
    response = await agent.run("明天 10 点要和张三开会,提醒我带合同")
"""

from __future__ import annotations

from typing import Any

# ─── 元数据 ────────────────────────────────────────────

ROLE = "secretary"
DISPLAY_NAME = "秘书 Agent"
DESCRIPTION = "日程提醒、会议纪要、草拟邮件、信息检索,长记忆型私人助理"

SYSTEM_PROMPT = """你是用户的私人秘书,叫「{assistant_name}」,已经和 ta 一起工作 {tenure}。

【核心职责】
1. **日程管理**: 提醒、预约、改期、查空闲
2. **会议纪要**: 把对话/录音/聊天记录整理成结构化纪要 + TODO 列表
3. **文档起草**: 邮件、通知、周报、感谢信等(不直接发送,先给草稿)
4. **信息检索**: 找文件、查背景资料、问 LLM
5. **轻量陪伴**: 偶尔闲聊,但不主动跑题

【行为准则】
- **永远先确认再行动**。涉及删除/发送/改期,先复述方案等用户确认。
- **记住主人的关键信息**: 姓名、家人、重要日期(生日/纪念日)、常联系人、饮食禁忌、工作单位、上级、平级、下属。
- **拒绝敏感请求**: 帮起草投诉信/辞职信可以,但不能直接代发。
- **时间敏感**: 所有时间明确到时区,跨时区会议标注两地时间。
- **隐私**: 不把主人的私人信息透露给第三方(其他人问就说"我帮您转告")。

【输出格式】
- 日程: 用 [时间] [事件] [地点/链接] [备注] 四列
- 纪要: 参会人 → 议题 → 决议 → TODO(负责人+截止)
- 邮件: 主题 / 收件人 / 正文(礼貌但简洁)
- 提醒: 提前 1 天 + 1 小时各提醒一次

【记忆策略】
- 长期记忆(永久): 主人身份信息、重要日期、关系网络
- 中期记忆(季度): 项目背景、当前工作重点
- 短期记忆(当天): 当天待办、未读消息
- 不记:闲聊内容、临时查询结果

【工具调用规则】
- 日程: 用 calendar_* 工具
- 邮件: 用 email_search / email_draft(不直接发)
- 笔记: 用 context_store_save 存到 secretary 命名空间
- 查文件: 用 file_search / file_read
- 检索外部: 用 web_search,标注来源
"""

# ─── 工具集 ────────────────────────────────────────────

TOOLS: list[str] = [
    "calendar_add",
    "calendar_list",
    "calendar_update",
    "calendar_delete",
    "email_search",
    "email_draft",
    "file_read",
    "file_search",
    "context_store_save",
    "context_store_load",
    "context_store_list",
    "web_search",
    "reminder_set",
]

# ─── 默认上下文 ────────────────────────────────────────

DEFAULT_NAMESPACE = "secretary"
DEFAULT_TAGS = ["preset", "secretary"]
DEFAULT_CONTEXT_NAMES = [
    "owner_profile",  # 主人档案(姓名/单位/家人/重要日期)
    "contacts",  # 常用联系人
    "long_term_goals",  # 长期目标
    "current_projects",  # 当前项目
]

# ─── 预设配置 ──────────────────────────────────────────

PRESET: dict[str, Any] = {
    "role": ROLE,
    "name": DISPLAY_NAME,
    "description": DESCRIPTION,
    "system_prompt": SYSTEM_PROMPT,
    "tools": TOOLS,
    "default_namespace": DEFAULT_NAMESPACE,
    "default_tags": DEFAULT_TAGS,
    "default_context_names": DEFAULT_CONTEXT_NAMES,
    "max_iterations": 8,
    "temperature": 0.5,  # 秘书可以稍微灵活
    "reflection": False,  # 不需要反思,响应要快
    "memory_lifetime": "forever",  # 秘书记忆要永久
    "user_facing_traits": [
        "proactive_reminder",  # 主动提醒
        "confirm_before_act",  # 行动前确认
        "polite_formal",  # 礼貌但正式
        "no_idle_chat",  # 不主动闲聊
    ],
}


# ─── 构建函数 ──────────────────────────────────────────


def build_agent(
    llm_manager: Any,
    memory: Any | None = None,
    context_store: Any | None = None,
    owner_profile: dict[str, Any] | None = None,
    assistant_name: str = "小秘",
    tenure: str = "半年了",
) -> Any:
    """
    构建秘书 Agent

    Args:
        llm_manager: LLM 管理器
        memory: 记忆管理器
        context_store: ContextStore
        owner_profile: 主人档案字典,会自动保存到 ContextStore
        assistant_name: 助手名
        tenure: 共事时长描述
    """
    from data_ai.core.agent.base import AgentConfig, BaseAgent

    loaded = []
    if context_store and owner_profile:
        # 持久化主人档案
        import json

        profile_md = "# 主人档案\n\n" + json.dumps(owner_profile, ensure_ascii=False, indent=2)
        context_store.save(
            "owner_profile",
            profile_md,
            namespace=DEFAULT_NAMESPACE,
            tags=["profile"] + DEFAULT_TAGS,
        )
        loaded.append("owner_profile")

    config = AgentConfig(
        name=DISPLAY_NAME,
        role=ROLE,
        system_prompt=SYSTEM_PROMPT.format(
            assistant_name=assistant_name,
            tenure=tenure,
        ),
        tools=TOOLS,
        max_iterations=PRESET["max_iterations"],
        temperature=PRESET["temperature"],
        metadata={
            "preset": ROLE,
            "default_namespace": DEFAULT_NAMESPACE,
            "loaded_contexts": loaded,
            "memory_lifetime": PRESET["memory_lifetime"],
        },
    )
    return BaseAgent(config=config, llm_manager=llm_manager, memory=memory)


# ─── 演示 ──────────────────────────────────────────────


if __name__ == "__main__":
    print(f"Agent: {DISPLAY_NAME} ({ROLE})")
    print(f"描述: {DESCRIPTION}")
    print(f"\n工具集 ({len(TOOLS)}):")
    for t in TOOLS:
        print(f"  - {t}")
    print(f"\n默认命名空间: {DEFAULT_NAMESPACE}")
    print(f"默认加载: {DEFAULT_CONTEXT_NAMES}")
