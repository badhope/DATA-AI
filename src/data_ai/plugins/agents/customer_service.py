"""
客服 Agent 预设

解决"重复问题浪费人工,直接问 LLM 又怕瞎编"的痛点。
启动后自动加载 FAQ/订单知识,只用查到的数据回答,不知道的引导人工。

用法:
    from data_ai.plugins.agents.customer_service import PRESET, build_agent
    agent = build_agent(llm_manager=llm_mgr, memory=mem, store=ctx_store)
    response = await agent.run("我的订单 #12345 怎么还没到?")
"""

from __future__ import annotations

from typing import Any

# ─── 元数据 ────────────────────────────────────────────

ROLE = "customer_service"
DISPLAY_NAME = "客服 Agent"
DESCRIPTION = "基于知识库/订单系统回答客户问题,不知道的引导人工,语气友好短句优先"

SYSTEM_PROMPT = """你是「{company_name}」的专业客服,服务客户。

【行为准则】
1. **只基于已知信息回答**。所有订单/物流/产品问题必须先用工具查询,严禁编造订单号、物流状态、价格。
2. **不知道就说不确定**,并引导转人工:"我帮您转接资深客服,请稍等"。
3. **短句优先,不用专业术语**。客户不需要听"FBA 履约""SKU 编码"。
4. **先共情再处理**。客户抱怨时,先说"非常理解您的心情",再说解决方案。
5. **退款/投诉/二选一**问题,必须先确认订单号,再走流程,不允许当场承诺退款金额。

【输出格式】
- 称呼客户:"亲"或"您好"
- 确认问题:复述一遍客户的问题
- 给出方案:1-2 步可执行的操作
- 询问是否解决:"请问还有其他可以帮您的吗?"

【禁用】
- 不使用"亲爱的""亲亲"等过度亲昵词汇
- 不承诺未在系统里查到的内容
- 不使用专业术语英文缩写

【工具调用规则】
- 订单状态:用 search_orders(order_id) 查,返回什么说什么
- 退款流程:必须先 search_orders → 查政策 → 询问客户是否继续
- 物流问题:用 track_shipment(order_id)
- 投诉升级:用 escalate_human(reason, customer_id),记录完整上下文
"""

# ─── 工具集 ────────────────────────────────────────────

TOOLS: list[str] = [
    "search_orders",       # 查订单(需业务方实现)
    "track_shipment",      # 查物流
    "search_kb",           # 知识库/FAQ
    "escalate_human",      # 转人工
    "send_email",          # 发邮件
    "context_store_save",  # 存客户档案/对话要点
    "context_store_load",
]

# ─── 默认上下文 ────────────────────────────────────────

DEFAULT_NAMESPACE = "customer_service"
DEFAULT_TAGS = ["preset", "customer-service"]
DEFAULT_CONTEXT_NAMES = [
    "company_info",        # 公司简介、退换货政策、联系方式
    "faq",                 # 常见问答
    "product_catalog",     # 产品目录(可选)
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
    "max_iterations": 6,
    "temperature": 0.3,  # 客服回答要稳,温度低
    "reflection": True,
    "user_facing_traits": [
        "empathy_first",        # 先共情
        "short_sentences",      # 短句
        "no_jargon",            # 不用术语
        "never_fabricate",      # 绝不编造
    ],
}


# ─── 构建函数 ──────────────────────────────────────────


def build_agent(
    llm_manager: Any,
    memory: Any | None = None,
    context_store: Any | None = None,
    company_name: str = "本公司",
    extra_context: dict[str, str] | None = None,
) -> Any:
    """
    构建客服 Agent 实例

    Args:
        llm_manager: LLM 管理器
        memory: 记忆管理器(可选)
        context_store: ContextStore(可选)
        company_name: 公司名,会填进 system prompt
        extra_context: 额外上下文,会保存到 ContextStore

    Returns:
        BaseAgent 实例
    """
    from data_ai.core.agent.base import AgentConfig, BaseAgent

    # 加载默认上下文
    loaded_contexts: list[str] = []
    if context_store and extra_context:
        for cname, content in extra_context.items():
            context_store.save(
                cname,
                content,
                namespace=DEFAULT_NAMESPACE,
                tags=DEFAULT_TAGS,
            )
            loaded_contexts.append(cname)

    config = AgentConfig(
        name=DISPLAY_NAME,
        role=ROLE,
        system_prompt=SYSTEM_PROMPT.format(company_name=company_name),
        tools=TOOLS,
        max_iterations=PRESET["max_iterations"],
        temperature=PRESET["temperature"],
        metadata={
            "preset": ROLE,
            "default_namespace": DEFAULT_NAMESPACE,
            "loaded_contexts": loaded_contexts,
        },
    )
    agent = BaseAgent(config=config, llm_manager=llm_manager, memory=memory)
    logger_msg = f"客服 Agent 已构建: {company_name}"
    if loaded_contexts:
        logger_msg += f" (已加载 {len(loaded_contexts)} 个上下文)"
    return agent


# ─── 演示 ──────────────────────────────────────────────


if __name__ == "__main__":
    # 演示:不连 LLM,只打印配置

    print("=" * 60)
    print(f"Agent: {DISPLAY_NAME} ({ROLE})")
    print("=" * 60)
    print(f"描述: {DESCRIPTION}")
    print()
    print("工具集:")
    for t in TOOLS:
        print(f"  - {t}")
    print()
    print("默认命名空间:", DEFAULT_NAMESPACE)
    print("默认加载的上下文:", DEFAULT_CONTEXT_NAMES)
    print()
    print("System Prompt 前 200 字:")
    print(SYSTEM_PROMPT[:200] + "...")
