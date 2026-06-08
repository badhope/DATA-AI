/**
 * 内置模板预设：agent / team / skill / sandbox 一键加载
 */

import type { AgentCreateRequest } from "@/lib/types/api";
import type { TeamCreateRequest } from "@/lib/types/api";

export interface AgentTemplate {
	id: string;
	name: string;
	emoji: string;
	description: string;
	build: (model: string) => Omit<AgentCreateRequest, "name"> & { name: string };
}

export const AGENT_TEMPLATES: AgentTemplate[] = [
	{
		id: "code-assistant",
		name: "代码助手",
		emoji: "💻",
		description: "Python / JS / Shell 多语言代码生成 + 执行 + 调试",
		build: (model) => ({
			name: "代码助手",
			description: "代码生成与执行验证",
			model,
			system_prompt:
				"你是一位资深软件工程师，擅长 Python / JavaScript / Bash。\n回答时：\n1. 先用 1-2 句话分析问题；\n2. 直接给出可运行代码；\n3. 调用 python_execute 实际运行验证结果；\n4. 报错时自行 debug 直到通过。\n风格简洁、代码优先。",
			tool_names: ["file_read", "file_write", "python_execute", "bash"],
			max_iterations: 8,
			temperature: 0.2,
			enable_reflection: true,
		}),
	},
	{
		id: "data-analyst",
		name: "数据分析师",
		emoji: "📊",
		description: "读 Excel/CSV、统计分析、生成图表",
		build: (model) => ({
			name: "数据分析师",
			description: "表格数据洞察与可视化",
			model,
			system_prompt:
				"你是数据分析师，擅长读取 Excel/CSV 并做统计与可视化。\n当用户提供表格文件路径时：\n1. 用 file_read 读取数据；\n2. 用 python_execute 做 describe / corr / groupby；\n3. 用 chart 工具生成柱状/折线/饼图；\n4. 最后给出业务洞察与结论。\n回答用中文。",
			tool_names: ["file_read", "python_execute", "bash"],
			max_iterations: 6,
			temperature: 0.3,
			enable_reflection: true,
		}),
	},
	{
		id: "translator",
		name: "翻译专家",
		emoji: "🌐",
		description: "中英日韩多语种互译 + 风格调整",
		build: (model) => ({
			name: "翻译专家",
			description: "多语种高质量翻译",
			model,
			system_prompt:
				"你是专业翻译，精通中英日韩法德西俄 8 国语言。\n规则：\n1. 保留原文格式（Markdown / 代码 / 数字不动）；\n2. 专业术语给出 1-2 个候选译法；\n3. 遇到歧义主动问澄清问题；\n4. 译文末尾用 () 标注文体（正式 / 口语 / 学术）。",
			tool_names: [],
			max_iterations: 3,
			temperature: 0.2,
			enable_reflection: false,
		}),
	},
	{
		id: "writer",
		name: "写作助理",
		emoji: "✍️",
		description: "文章 / 邮件 / 营销文案创作",
		build: (model) => ({
			name: "写作助理",
			description: "创意与商业写作",
			model,
			system_prompt:
				"你是资深文案，擅长中英双语写作。\n根据用户要求产出：\n- 文章：结构清晰、段落分明、500-1500 字；\n- 邮件：主题 + 称谓 + 正文 + 落款；\n- 营销：标题 + 价值点 + CTA。\n风格可调：专业 / 幽默 / 简洁。",
			tool_names: [],
			max_iterations: 3,
			temperature: 0.8,
			enable_reflection: true,
		}),
	},
	{
		id: "debugger",
		name: "调试专家",
		emoji: "🐞",
		description: "读取日志 + 复现 + 修复 bug",
		build: (model) => ({
			name: "调试专家",
			description: "日志分析 + 错误定位 + 修复",
			model,
			system_prompt:
				"你是 SRE 调试专家。接到 bug 报告时：\n1. 让用户提供日志/堆栈；\n2. 用 file_read / bash 读日志；\n3. 推理根因（不要瞎猜，给出依据）；\n4. 给出最小修复 patch；\n5. 提供回归测试用例。\n回答使用中文。",
			tool_names: ["file_read", "python_execute", "bash"],
			max_iterations: 10,
			temperature: 0.3,
			enable_reflection: true,
		}),
	},
	{
		id: "researcher",
		name: "研究助理",
		emoji: "🔬",
		description: "多源检索 + 总结 + 引用",
		build: (model) => ({
			name: "研究助理",
			description: "信息检索与综合",
			model,
			system_prompt:
				"你是研究助理，擅长多源信息综合。\n面对研究问题时：\n1. 先列 3-5 个关键子问题；\n2. 逐个回答并标注信息源；\n3. 给出综合结论 + 局限性；\n4. 推荐 3 篇延伸阅读。\n使用中文。",
			tool_names: [],
			max_iterations: 5,
			temperature: 0.5,
			enable_reflection: true,
		}),
	},
];

export interface TeamTemplate {
	id: string;
	name: string;
	emoji: string;
	description: string;
	build: (model: string) => Omit<TeamCreateRequest, "name"> & { name: string };
}

export const TEAM_TEMPLATES: TeamTemplate[] = [
	{
		id: "debate",
		name: "正反辩论队",
		emoji: "⚖️",
		description: "3 个 agent 对辩 + 总结",
		build: (model) => ({
			name: "正反辩论队",
			description: "正方/反方/裁判",
			mode: "collaboration",
			consensus_method: "llm_synthesis",
			members: [
				{ name: "正方", role: "worker", weight: 1.0, model, system_prompt: "你是辩论正方。坚持观点，1-2 句话。" },
				{ name: "反方", role: "worker", weight: 1.0, model, system_prompt: "你是辩论反方。坚持观点，1-2 句话。" },
				{ name: "裁判", role: "synthesizer", weight: 1.5, model, system_prompt: "你是裁判。综合正反方观点，给出 1 句话结论。" },
			],
		}),
	},
	{
		id: "review",
		name: "代码评审团",
		emoji: "🔍",
		description: "3 个角度评审：功能 / 性能 / 安全",
		build: (model) => ({
			name: "代码评审团",
			description: "多角度代码评审",
			mode: "collaboration",
			consensus_method: "llm_synthesis",
			members: [
				{ name: "功能评审", role: "worker", weight: 1.0, model, system_prompt: "从功能正确性、边界条件角度评审代码。1 句话。" },
				{ name: "性能评审", role: "worker", weight: 1.0, model, system_prompt: "从性能、复杂度、可扩展性评审。1 句话。" },
				{ name: "安全评审", role: "worker", weight: 1.0, model, system_prompt: "从安全、注入、权限角度评审。1 句话。" },
				{ name: "总结者", role: "synthesizer", weight: 1.5, model, system_prompt: "综合三人观点，给出 1 句话最终评审。" },
			],
		}),
	},
	{
		id: "brainstorm",
		name: "头脑风暴组",
		emoji: "💡",
		description: "5 个角色发散 + 收敛",
		build: (model) => ({
			name: "头脑风暴组",
			description: "5 角色发散 + 收敛",
			mode: "collaboration",
			consensus_method: "llm_synthesis",
			members: [
				{ name: "激进派", role: "worker", weight: 1.0, model, system_prompt: "给出最激进、最大胆的想法。1 句话。" },
				{ name: "保守派", role: "worker", weight: 1.0, model, system_prompt: "考虑风险与可行性。1 句话。" },
				{ name: "技术派", role: "worker", weight: 1.0, model, system_prompt: "从技术实现角度评估。1 句话。" },
				{ name: "用户派", role: "worker", weight: 1.0, model, system_prompt: "从用户体验角度评估。1 句话。" },
				{ name: "总结者", role: "synthesizer", weight: 1.5, model, system_prompt: "综合 4 人观点，给出最终建议。" },
			],
		}),
	},
];

export interface SkillTemplate {
	id: string;
	name: string;
	emoji: string;
	description: string;
	category: string;
	yaml: string;
}

export const SKILL_TEMPLATES: SkillTemplate[] = [
	{
		id: "echo",
		name: "echo-skill",
		emoji: "📢",
		description: "回声：把入参原样返回（最简 skill）",
		category: "utility",
		yaml: `name: echo-skill
version: 1.0.0
description: 简单回声
parameters:
  text:
    type: string
    description: 要回显的文本
    required: true
steps:
  - name: echo
    type: builtin
    tool: echo
    args:
      text: \${parameters.text}
`,
	},
	{
		id: "summarize",
		name: "summarize-skill",
		emoji: "📝",
		description: "文本摘要（调 LLM 总结）",
		category: "ai",
		yaml: `name: summarize-skill
version: 1.0.0
description: 文本摘要
parameters:
  text:
    type: string
    description: 待摘要文本
    required: true
  max_words:
    type: integer
    description: 摘要最大词数
    default: 100
steps:
  - name: summarize
    type: llm
    prompt: |
      请用中文将以下文本总结为不超过 \${parameters.max_words} 字的摘要：
      \${parameters.text}
`,
	},
	{
		id: "translate-skill",
		name: "translate-skill",
		emoji: "🌐",
		description: "中英互译",
		category: "ai",
		yaml: `name: translate-skill
version: 1.0.0
description: 中英互译
parameters:
  text:
    type: string
    description: 待翻译文本
    required: true
  target_lang:
    type: string
    description: 目标语言
    enum: [zh, en, ja]
    default: en
steps:
  - name: translate
    type: llm
    prompt: |
      请把以下文本翻译为 \${parameters.target_lang}：
      \${parameters.text}
`,
	},
];

export interface SandboxTemplate {
	id: string;
	name: string;
	emoji: string;
	description: string;
	code: string;
	language: "python" | "javascript" | "bash" | "go" | "rust";
}

export const SANDBOX_TEMPLATES: SandboxTemplate[] = [
	{
		id: "hello-py",
		name: "Hello Python",
		emoji: "🐍",
		description: "Python hello world + 列表推导",
		language: "python",
		code: `def fib(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

print("Hello from DATA-AI sandbox!")
print("First 10 Fibonacci:", [fib(i) for i in range(10)])
print("Sum:", sum(range(100)))
`,
	},
	{
		id: "data-py",
		name: "Data Analysis",
		emoji: "📊",
		description: "用 pandas 生成示例数据 + 统计",
		language: "python",
		code: `import json
import random

# 模拟数据
data = [
    {"name": f"user_{i}", "age": random.randint(18, 60), "score": random.randint(0, 100)}
    for i in range(20)
]

# 统计
ages = [d["age"] for d in data]
scores = [d["score"] for d in data]

result = {
    "count": len(data),
    "age_avg": sum(ages) / len(ages),
    "score_avg": sum(scores) / len(scores),
    "score_max": max(scores),
    "top_3": sorted(data, key=lambda d: d["score"], reverse=True)[:3],
}
print(json.dumps(result, ensure_ascii=False, indent=2))
`,
	},
	{
		id: "fetch-js",
		name: "Fetch JSON",
		emoji: "🌐",
		description: "Node.js fetch 示例",
		language: "javascript",
		code: `// 模拟 API 响应
const mock = {
  user: "alice",
  roles: ["admin", "editor"],
  meta: { active: true, score: 99 },
};
console.log(JSON.stringify(mock, null, 2));
console.log("Roles count:", mock.roles.length);
`,
	},
	{
		id: "shell",
		name: "Bash Info",
		emoji: "🐚",
		description: "Bash 系统信息",
		language: "bash",
		code: `echo "=== System Info ==="
echo "Hostname: $(hostname)"
echo "User: $(whoami)"
echo "Date: $(date)"
echo "CWD: $(pwd)"
echo "Files:"
ls -la | head -10
`,
	},
];
