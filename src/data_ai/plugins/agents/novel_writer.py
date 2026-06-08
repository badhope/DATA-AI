"""
小说写作 Agent 预设

解决"长篇创作中,人物/大纲/章节/设定容易乱"的痛点。
强调 ContextStore 持久化:大纲、人物档案、章节草稿独立命名空间,跨会话不丢。

用法:
    from data_ai.plugins.agents.novel_writer import build_agent
    agent = build_agent(llm_manager=llm_mgr, store=ctx_store,
                        novel_namespace="novel_red_blue",
                        genre="悬疑")
    await agent.run("帮我想一下第三章的情节走向")
"""

from __future__ import annotations

from typing import Any

ROLE = "novel_writer"
DISPLAY_NAME = "小说写作 Agent"
DESCRIPTION = "长篇创作助手,ContextStore 持久化大纲/人物/章节,跨会话不丢"

SYSTEM_PROMPT = """你是一位资深小说写作助手,擅长长篇创作,负责帮用户「{author}」推进小说《{title}》({genre})。

【当前进度】
- 已写章节: {chapters_written}
- 当前字数: {word_count}
- 上下文文件数: {context_count}

【核心能力】
1. **大纲管理**: 维护总大纲(主题、主线、起承转合),不偏离主题
2. **人物档案**: 主要人物的性格、动机、人物关系,前后一致
3. **章节规划**: 拆章、节奏控制、伏笔与回收
4. **风格保持**: 模仿用户的写作风格,不擅自改变文体
5. **草稿迭代**: 接受反馈、改写、润色,不擅自发布

【严格纪律】
- **绝不编造已有设定**: 人物关系、时间线、地点,必须先从 ContextStore 读取
- **风格一致**: 第一人称/第三人称、白话/文白、严肃/轻喜剧,要保持
- **保留伏笔**: 用户提到的伏笔要登记到 ContextStore,后面回收
- **长对话兼容**: 多轮对话要呼应上文,不重复生成相同内容
- **不在主线外自创**: 跑题是写作大忌,新想法先入"支线候选"

【输出格式】
- 大纲: 一级标题(章节) + 二级(场景) + 三级(节拍)
- 章节草稿: 标题 + 场景(时间/地点/人物) + 正文 + 备注(本节新增人物/伏笔)
- 人物: 姓名 + 外貌 + 性格 + 背景 + 关系网 + 弧光(成长轨迹)
- 改稿: 标出修改前后(用 [改前] / [改后] 块)

【工具使用】
- 读上下文: context_store_load(name, namespace=...)  — 必先读再写
- 写设定: context_store_save(名字, 内容, namespace="novel_xxx", tags=["character" | "plot" | "draft"])
- 搜索: context_store_search(关键词) 找之前提过的设定
- 长度控制: 单次回答不超过 1500 字,长内容分块

【禁用】
- 不替用户做决定(选 A 还是选 B 情节,先给两个方案让用户挑)
- 不主动给政治/色情/暴力具体描写
- 不假装写过用户没写过的章节
"""

# ─── 工具集 ────────────────────────────────────────────

TOOLS: list[str] = [
    "context_store_save", "context_store_load", "context_store_list",
    "context_store_search", "context_store_delete", "context_store_history",
    "file_read", "file_write", "file_search",
    "web_search",          # 查资料(历史/风土/科学)
    "polish_text",         # 润色
    "word_read",           # 读 docx 草稿
    "write_docx",          # 写章节
    "write_md",            # 写大纲/人物档案
]

# ─── 默认上下文(命名空间内部的结构) ────────────────────

DEFAULT_NAMESPACE = "novel"        # 实际使用时改为 novel_<title>
DEFAULT_TAGS = ["preset", "novel-writer"]
DEFAULT_CONTEXT_NAMES = [
    "outline",              # 总大纲
    "characters",           # 人物档案
    "world_settings",       # 世界观/设定
    "foreshadowing",        # 伏笔登记
    "chapters",             # 章节索引(不含正文,正文在独立文件)
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
    "max_iterations": 12,
    "temperature": 0.8,        # 创作要灵活
    "reflection": True,
    "memory_lifetime": "forever",   # 创作记忆要永久
    "user_facing_traits": [
        "consistency_first",    # 一致性优先
        "no_self_decide",       # 不替用户决定
        "context_aware",        # 强上下文
        "long_chat_friendly",   # 适合长对话
    ],
}


# ─── 构建函数 ──────────────────────────────────────────


def build_agent(
    llm_manager: Any,
    memory: Any | None = None,
    context_store: Any | None = None,
    novel_namespace: str = "novel_my_story",
    title: str = "我的小说",
    author: str = "作者",
    genre: str = "小说",
) -> Any:
    """
    构建小说写作 Agent

    Args:
        llm_manager: LLM 管理器
        memory: 记忆管理器(强烈建议传入)
        context_store: ContextStore(必传,用于持久化大纲/人物/章节)
        novel_namespace: 命名空间,推荐 novel_<title_slug>
        title: 小说名
        author: 作者称呼
        genre: 类型(悬疑/言情/科幻/历史...)
    """
    from data_ai.core.agent.base import AgentConfig, BaseAgent

    # 读取已有上下文,统计进度
    chapters_written = "0"
    word_count = "0"
    context_count = 0
    loaded = []

    if context_store:
        try:
            # 实际是直接 list
            metas = context_store.list(namespace=novel_namespace)
            context_count = len(metas)
            for m in metas:
                if m.name.startswith("chapter_"):
                    chapters_written = str(int(chapters_written) + 1)
                # 简化统计:总字符数
            # 累计字数(遍历 chapter_ 文件)
            total = 0
            for m in metas:
                ctx = context_store.load(m.name, namespace=novel_namespace)
                if ctx:
                    total += len(ctx.content)
            word_count = f"{total:,}"
        except Exception:
            pass

    config = AgentConfig(
        name=DISPLAY_NAME,
        role=ROLE,
        system_prompt=SYSTEM_PROMPT.format(
            author=author,
            title=title,
            genre=genre,
            chapters_written=chapters_written,
            word_count=word_count,
            context_count=context_count,
        ),
        tools=TOOLS,
        max_iterations=PRESET["max_iterations"],
        temperature=PRESET["temperature"],
        metadata={
            "preset": ROLE,
            "default_namespace": novel_namespace,
            "title": title,
            "genre": genre,
            "loaded_contexts": loaded,
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
    print(f"\n默认命名空间: {DEFAULT_NAMESPACE} (实际用 novel_<title>)")
    print(f"默认上下文结构: {DEFAULT_CONTEXT_NAMES}")
