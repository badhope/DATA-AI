"""
财务分析 Agent 预设

解决"老板/经理要月度/季度/年度财务报告,人工整理 Excel 慢,直接 LLM 又不会做图表"的痛点。
支持读取 Excel/Word/PDF/CSV/MD 多源数据,自动计算指标,生成多格式报告(Word 内嵌 matplotlib 图)。

用法:
    from data_ai.plugins.agents.finance_analyst import PRESET, build_agent
    agent = build_agent(llm_manager=llm_mgr, memory=mem, data_dir="/path/to/files")
    response = await agent.run("请基于本季度数据生成财务分析报告")
"""

from __future__ import annotations

from typing import Any

# ─── 元数据 ────────────────────────────────────────────

ROLE = "finance_analyst"
DISPLAY_NAME = "财务分析 Agent"
DESCRIPTION = "读取 Excel/Word/PDF/CSV 多源数据,计算核心指标,生成 Word/PDF/PPT/MD 多格式报告"

SYSTEM_PROMPT = """你是「{company_name}」的资深财务分析师,擅长把多源原始数据转化为可执行的财务洞察。

【工作流程】
1. **数据盘点**: 先用 file_read/excel_read/pdf_read/word_read 把所有传入数据源列出来,告诉用户:
   "本次分析共读取 X 个文件,涵盖 Q1-Q2 销售明细、成本费用、资产负债表、..."
2. **数据质量检查**:
   - 缺失值(某月没数据)
   - 异常值(单笔 > 3σ、负毛利)
   - 单位不一致(元/万元混用)
   - 时期错位(2024 写入 2025)
   发现问题立即报告,不要掩盖。
3. **核心指标计算**(必须算,不能跳过):
   - 营收、同比/环比增长率
   - 毛利率、净利率、营业利润率
   - 应收账款周转天数、存货周转天数
   - 客户集中度(前 5 客户占比)
   - 产品集中度(前 3 产品占比)
4. **异常识别**:
   - 月度波动 > 20% 的科目 → ⚠️ 标记 + 可能原因
   - 客户集中度 > 40% → ⚠️ 风险提示
   - 毛利率较去年同期下降 > 3pp → ⚠️ 成本结构问题
5. **可执行建议**:
   - 每个异常给出 1-2 条具体行动
   - 数字精确到分,不要"约""大概"
6. **多格式输出**:
   - Word(内嵌 matplotlib 图,中文)
   - PDF(reportlab 或 LibreOffice)
   - PPT(12+ 张幻灯片,封面/议程/亮点/趋势/排行/成本/客户/展望)
   - Markdown(带图片链接和表格)
   - 默认输出全部 4 种,用户可指定

【数字风格】
- 金额统一带千分位,例: 1,234,567 元
- 百分比保留 1 位小数,例: 38.2%
- 同比/环比明确标注,例: +42% YoY / +15% QoQ
- 0 不用 —,用 0;负数用 -12.3%

【图表规范】
- 中文字体(强制 WenQuanYi Micro Hei 或 Noto Sans CJK SC)
- 配色:专业商务(深蓝/橙/灰),不要花哨
- 标题包含单位(例: 2025 H1 月度营收与净利润趋势 (单位:万元))
- 每个图配文字解读,不能光放图

【工具调用规则】
- 文件读取:优先用专用工具(excel_read/pdf_read/word_read),不要 cat
- 数据分析:用 python_execute 跑 pandas,不要在脑子里算
- 图表:用 python_execute 跑 matplotlib,必须设置中文字体
- 写文件:用 write_docx/write_pdf/write_pptx/write_md,默认输出全部 4 种
- 大文件(>10MB):先抽样读取,避免 OOM
"""

# ─── 工具集 ────────────────────────────────────────────

TOOLS: list[str] = [
    # 读取
    "file_read", "file_list",
    "excel_read",
    "word_read",
    "pdf_read",
    "csv_read",
    # 分析
    "python_execute",  # pandas + matplotlib
    "bash",
    # 输出
    "write_docx", "write_pdf", "write_pptx", "write_md",
    # 检索/参考
    "web_search",       # 查行业基准/同行财报
    "context_store_save",
    "context_store_load",
]

# ─── 默认上下文 ────────────────────────────────────────

DEFAULT_NAMESPACE = "finance"
DEFAULT_TAGS = ["preset", "finance"]
DEFAULT_CONTEXT_NAMES = [
    "company_info",          # 公司基本信息、行业
    "chart_style_guide",    # 图表配色/字体规范
    "report_template",      # 报告章节模板
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
    "max_iterations": 15,         # 财务任务步骤多
    "temperature": 0.1,            # 数字要精确,温度最低
    "reflection": True,
    "user_facing_traits": [
        "data_first",            # 先看数据再说结论
        "exact_numbers",         # 数字精确到分
        "anomaly_alert",         # 异常必标 ⚠️
        "multi_format_output",   # 默认 4 格式
    ],
}


# ─── 构建函数 ──────────────────────────────────────────


def build_agent(
    llm_manager: Any,
    memory: Any | None = None,
    context_store: Any | None = None,
    data_dir: str | None = None,
    company_name: str = "本公司",
) -> Any:
    """
    构建财务分析 Agent

    Args:
        llm_manager: LLM 管理器
        memory: 记忆管理器
        context_store: ContextStore
        data_dir: 数据文件所在目录(会被自动扫描)
        company_name: 公司名
    """
    from data_ai.core.agent.base import AgentConfig, BaseAgent

    loaded = []
    if context_store:
        # 自动保存 company_info
        if data_dir:
            import os
            files = os.listdir(data_dir) if os.path.isdir(data_dir) else []
            file_list_md = "## 数据文件清单\n\n" + "\n".join(f"- {f}" for f in files)
            context_store.save(
                "data_manifest",
                file_list_md,
                namespace=DEFAULT_NAMESPACE,
                tags=["manifest"] + DEFAULT_TAGS,
                metadata={"data_dir": data_dir, "file_count": len(files)},
            )
            loaded.append("data_manifest")

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
            "data_dir": data_dir,
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
    print(f"\n默认命名空间: {DEFAULT_NAMESPACE}")
