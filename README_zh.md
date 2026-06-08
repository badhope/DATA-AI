<div align="center">

# DATA-AI

一个 Python 智能体运行时 + OpenAI 兼容的聊天后端 + React Web 控制台，
面向办公场景：聊天、智能体、RAG、记忆、代码沙箱、30+ 工具，全在一个
进程里。

</div>

---

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node 18+](https://img.shields.io/badge/node-18%2B-339933.svg)](https://nodejs.org)
[![CI](https://github.com/badhope/DATA-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/badhope/DATA-AI/actions/workflows/ci.yml)
[![Last commit](https://img.shields.io/github/last-commit/badhope/DATA-AI)](https://github.com/badhope/DATA-AI/commits/main)
[![Issues](https://img.shields.io/github/issues/badhope/DATA-AI)](https://github.com/badhope/DATA-AI/issues)
[![Stars](https://img.shields.io/github/stars/badhope/DATA-AI)](https://github.com/badhope/DATA-AI/stargazers)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19-149eca.svg)](https://react.dev)
[![Vite 6](https://img.shields.io/badge/Vite-6-646cff.svg)](https://vitejs.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178c6.svg)](https://www.typescriptlang.org)

[**English**](README.md) · [**中文**](README_zh.md)

[快速开始](#快速开始) · [功能特性](#功能特性) · [Web 控制台](#web-控制台) · [架构](#架构) · [文档](docs/) · [贡献指南](CONTRIBUTING.md)

---

## 这是什么

DATA-AI 是一个单进程后端，暴露 OpenAI 兼容的 HTTP 接口和静态 Web UI。
定位是自托管：克隆、设一个 API key、跑 `python -m data_ai.core.api.server`，
不到一分钟就有一个能跑的多模型智能体。

值得看的几个点：

- **真正的智能体运行时。** 单智能体和多智能体团队，支持共识（LLM
  合成、多数投票、语义、拼接）、反思、迭代上限。不是 prompt 套壳。
- **一个注册表背后 19 家 LLM。** OpenAI、Anthropic、Google、Azure、AWS
  Bedrock、DeepSeek、SiliconFlow、通义千问、智谱、月之暗面、零一万物、
  百川、豆包、阶跃星辰、Ollama、vLLM、LM Studio，加一个用于测试和
  Demo 的内置离线模型。
- **30+ 工具。** 文件操作、Python / Bash / Node 沙箱、浏览器自动化、
  网页搜索、PDF / Word / Excel / PPT 处理、数据分析、系统工具。
- **RAG 和记忆跑在同一个进程里。** 内存、FAISS、Chroma、LanceDB 任选。
  长期记忆和摘要直接接在 chat 循环里，不是外挂。
- **ContextStore — 命名化、文件化的项目记忆。** 草稿/大纲/人物档案
  等任意长文本都能 save/load/版本/搜索，存成透明 JSON 树，git 友
  好，跟会话解耦。详见
  [`core/context_store.py`](src/data_ai/core/context_store.py)。
- **四个开箱即用的企业 Agent 预设。** 客服、财务分析、秘书、小说写
  作，每个都配好 system prompt、工具集和默认上下文命名空间，一行
  加载。详见 [`plugins/agents/`](src/data_ai/plugins/agents/)。
- **中文口语化归一化。** 错别字/口语助词/中英混输（如 帐单→账单、
  给我弄→帮我、打开 app→打开应用）在意图匹配前先清洗。详见
  [`_normalize_colloquial`](src/data_ai/core/intent/recognizer.py)。
- **沙箱环境一键装齐。** `bash scripts/setup_sandbox.sh` 自动装所
  有系统包、Python 库、中文字体，新容器 5 分钟可用。
- **能用的 Web 控制台。** Vite + React 19，SSE 流式聊天，明暗主题，
  顶栏一键 English / 简体中文，没有遥测。

后端代码量够少，一个下午能读完。最值得看的三个文件：
`src/data_ai/core/llm/manager.py`（LLM 注册表）、
`src/data_ai/core/agent/base.py`（智能体循环）、
`src/data_ai/core/api/server.py`（HTTP 层，70+ 路由）。

## 快速开始

### 只要 CLI（最小安装）

```bash
pip install -e .
data-ai chat --model offline-chat
```

`offline-chat` 是内置的，不需要 API key。能完整跑通智能体循环、工具
注册表和记忆。

### Web 控制台（推荐）

```bash
# 1) 后端 — http://127.0.0.1:8000
pip install -e .
python -m data_ai.core.api.server

# 2) 前端 — http://127.0.0.1:5173
cd web
npm install
npm run dev
```

打开 <http://127.0.0.1:5173>，默认就是 **Chat Console**：选模型、发
消息、看 token 一段段流出来。

要用真模型，启动后端前设环境变量：

```bash
export DEEPSEEK_API_KEY="sk-..."      # 任意 OPENAI_* / ANTHROPIC_* / DEEPSEEK_* ...
# 开启入站鉴权
export DATA_AI_API_KEYS="任意-token"
# 或者开发模式直接跳过鉴权
export DATA_AI_DEV_MODE=true
```

完整说明见 [`docs/INSTALLATION.md`](docs/INSTALLATION.md) 和
[`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)。

## Web 控制台

| 页面              | 路径                          | 干啥                                    |
|-------------------|-------------------------------|-----------------------------------------|
| Chat Console      | `/chat`                       | 多模型流式聊天（SSE）                   |
| Agents            | `/agents`                     | 单智能体定义 + 运行历史                 |
| Agent Teams       | `/teams`                      | 多智能体协作 + 共识                     |
| Memory            | `/memory`                     | 短期 / 长期记忆管理                     |
| Knowledge Base    | `/rag`                        | 文档上传、切分、检索                    |
| Sandbox           | `/sandbox`                    | 在线跑 Python / Bash / Node             |
| Tools             | `/tools`                      | 浏览和试用内置工具                      |
| Skills            | `/skills`                     | 技能定义和执行                          |
| Office（Word/PPT/Excel/PDF） | `/office/*`       | Office 文件处理                         |
| Models            | `/models`                     | 模型注册和测试                          |
| Settings          | `/settings`                   | API key、base URL、主题、语言           |

### 企业治理 (自托管 SaaS 控制台)

| 页面              | 路径                          | 干啥                                    |
|-------------------|-------------------------------|-----------------------------------------|
| 审计日志          | `/audit`                      | 可检索审计日志 + 统计                   |
| 配额              | `/quota`                      | 按主体的速率 / token 软硬限流           |
| Webhook           | `/webhooks`                   | 事件订阅、签名投递、重试、死信          |
| 调度器            | `/scheduler`                  | Cron 任务、执行记录、重试策略           |
| 租户              | `/tenants`                    | 多租户隔离 + 成员                       |
| 权限              | `/rbac`                       | 角色、ABAC 策略、委派日志               |
| 成本中心          | `/billing`                    | 按模型计费、预算、发票                  |
| SLA & 状态页      | `/sla`                        | SLO 评估、事件、对外状态                |
| SSO / IdP         | `/sso`                        | OIDC / SAML、SCIM、会话                 |
| 数据驻留          | `/residency`                  | 区域路由、合规策略                      |
| 审计链            | `/audit-chain`                | Merkle 锚定的防篡改日志                 |
| 跨区复制          | `/replication`                | 复制流、延迟、failover、quorum          |
| 备份与恢复        | `/recovery`                   | 计划、还原、DR 演练、保留 / legal hold  |
| SLA 赔付          | `/compensation`               | 违约检测、credit 赔付、争议 / 退款      |

顶栏一键切换 **English / 简体中文**，不刷新页面。

## 功能特性

### LLM 提供商

- **全球**：OpenAI、Anthropic、Google Gemini、Azure OpenAI、AWS Bedrock
- **国内**：DeepSeek、通义千问、智谱、月之暗面、零一万物、百川、豆包、
  阶跃星辰、SiliconFlow
- **本地 / 自托管**：Ollama、vLLM、LM Studio
- **内置**：`offline-chat`、`offline-fast`、`offline-mini` —— 模板式
  回复，给 CI、测试、Demo 用，不发外部请求。

除 Anthropic 和 Google 之外，所有国内 / 全球厂商都是 OpenAI 兼容协议，
共用同一个 client 实现，`base_url` 自动推断。详见
[`PROVIDER_DEFAULT_BASE_URL`](src/data_ai/core/llm/manager.py)。

启动时检测到以下任意环境变量会自动注册模型（逻辑在
[`src/data_ai/core/api/server.py`](src/data_ai/core/api/server.py) 的
lifespan 钩子里）：

| 提供商      | 环境变量                                | Model id（默认）            |
|-------------|------------------------------------------|-----------------------------|
| OpenAI      | `OPENAI_API_KEY`                         | `openai-gpt-4o-mini`        |
| Anthropic   | `ANTHROPIC_API_KEY`                      | `anthropic-claude-3-5-sonnet` |
| DeepSeek    | `DEEPSEEK_API_KEY`                       | `deepseek-chat`             |
| SiliconFlow | `SILICONFLOW_API_KEY`                    | `siliconflow-deepseek`      |
| 通义千问    | `QWEN_API_KEY` / `DASHSCOPE_API_KEY`     | `qwen-plus`                 |
| 智谱 GLM    | `ZHIPU_API_KEY` / `GLM_API_KEY`          | `zhipu-glm-4-flash`         |
| 月之暗面    | `MOONSHOT_API_KEY`                       | `moonshot-v1-32k`           |
| 零一万物    | `YI_API_KEY`                             | `yi-medium`                 |
| 百川        | `BAICHUAN_API_KEY`                       | `baichuan4`                 |
| 豆包        | `DOUBAO_API_KEY`                         | `doubao-lite-32k`           |
| 阶跃星辰    | `STEPFUN_API_KEY`                        | `step-1-flash`              |

### 智能体

- `BaseAgent`：工具调用、反思、迭代上限
- **Self-Reflection** (P0-2)：LLM 评估自己答案的 confidence，issues 注入回 messages
- **Checkpoint 持久化** (P1-1)：每轮 iteration 自动存盘，支持 resume，gzip 压缩
- **Human-in-the-Loop** (P1-2)：危险工具触发暂停，等人工 approve / reject（5min 超时自动 reject）
- **Sub-Agent 委派** (P1-3)：`delegate(query, role)` spawn sub-agent，套 preset（customer_service / finance_analyst / secretary / novel_writer），`delegate_many` 并行
- **Tool Retry** (P1-4)：异常分类（retryable / permanent），指数退避 + jitter，防 thundering herd
- `AgentTeam`：**LLM 合成 / 多数投票 / 语义 / 拼接** 四种共识策略
- 顺序思考和闭环学习是同一个循环的一部分，不是单独"模式"

### 工具

- 文件：读 / 写 / 搜 / 替换 / 批量
- 代码执行：Python 沙箱、Bash、Node.js（带真实 stdout 捕获）
- 浏览器自动化：导航、点击、截图、填表（Playwright，可选）
- 文档：PDF、Word、Excel、PPT、Markdown、HTML
- 数据分析：Pandas、Matplotlib、Plotly
- Office 工作流：`.docx` / `.pptx` / `.xlsx` / `.pdf` 真往返

### RAG

- Loader：PDF、Word、Markdown、HTML、TXT
- Splitter：递归字符、token
- Store：内存、FAISS、Chroma、LanceDB
- 检索：相似度、MMR 多样性、带引用

### 记忆

- 会话 / 语义 / 短期 / 长期
- 窗口膨胀时自动摘要
- 闭环：执行 → 评估 → 提取 → 检索

## 企业治理

三层企业级能力，全部已发布、可自托管。每一层对应一个反复出现的
企业痛点（审计盲区、访问控制、合规、业务连续性、合同 SLA）。

### Tier 1 — 可观测与控制（已发布）

| 模块                  | 作用                                                                  |
|-----------------------|-----------------------------------------------------------------------|
| `core/audit`          | 结构化审计日志，记录主体、资源、IP、payload 哈希、统计                |
| `core/quota`          | 按主体的速率 / token 软硬限流，Top-N 报表                             |
| `core/webhooks`       | 事件订阅 + HMAC 签名 + 重试 + 死信 + 投递记录                        |
| `core/scheduler`      | Cron 风格任务执行 + 重试 + 退避 + 执行历史                            |

### Tier 2 — 多租户与合规（已发布）

| 模块                  | 作用                                                                  |
|-----------------------|-----------------------------------------------------------------------|
| `core/tenants`        | 租户 + 成员生命周期、每租户配额、套餐分层                             |
| `core/rbac`           | 角色 + 权限 + ABAC 条件、角色继承、委派                               |
| `core/billing`        | 按模型定价、软硬预算上限、成本中心分摊                                |
| `core/sla`            | SLO 评估、组件健康、事件生命周期、对外状态页                          |
| `core/sso`            | OIDC + SAML 身份源、SCIM 预配、会话存储                               |
| `core/residency`      | 区域感知数据路由、6 类策略、驻留分配                                  |
| `core/audit_chain`    | Merkle 锚定的 append-only 链，含 inclusion proof 验证                 |

### Tier 3 — 韧性与服务承诺（已发布）

| 模块                       | 作用                                                              |
|----------------------------|-------------------------------------------------------------------|
| `core/replication`         | 同步 / 异步 / 半同步流，延迟，failover，quorum 防护               |
| `core/recovery`            | 备份计划、还原、DR 演练、保留 / 法定挂起                          |
| `core/sla/compensation`    | 违约检测、credit 计算、争议 / 退款流程                            |

三层共享同一架构形态：

- 纯 Python core 模块位于 `data_ai.core.<module>/`，不依赖 API 即可用
  （`from data_ai.core.tenants import get_tenant_store`）
- REST 接口挂在 `/v1/...` 下（见 `api/extensions.py`）
- 类型化 Python SDK 客户端（`from data_ai.sdk_client import DataAIClient`）
- 类型化 TypeScript 客户端（`web/src/lib/api/client.ts`）
- Web 控制台页面 + 侧边栏 + `i18n` 文案
- 单元测试位于 `tests/test_enterprise_tier*.py`（当前共 423 通过）

## 架构

```
src/data_ai/
├── core/
│   ├── llm/manager.py            LLM 注册表，19 家厂商，流式
│   ├── agent/base.py             BaseAgent、AgentTeam、共识
│   ├── api/server.py             FastAPI app，70+ 路由
│   ├── api/extensions.py         资源路由（agents、memory、...）
│   ├── api/auth.py               Bearer key 校验
│   ├── tool/                     30+ 工具
│   ├── memory/                   短期 / 长期记忆
│   ├── rag/                      Loader、splitter、向量库
│   ├── sandbox/                  本地 + docker 沙箱
│   ├── office/                   Word / PPT / Excel / PDF 处理
│   └── i18n/                     catalog + locale 协商
├── utils/                        config、exceptions、logging、platform
├── cli/                          typer 命令（data-ai ...）
└── __main__.py                   data-ai 入口
```

完整版见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

## 配置

下面是简化版，完整说明在 [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)。

| 环境变量                 | 作用                                                       |
|--------------------------|------------------------------------------------------------|
| `DATA_AI_API_KEYS`       | 逗号分隔的 bearer key。空 = 全部拒绝（401）。              |
| `DATA_AI_DEV_MODE`       | `true` 跳过鉴权。仅本地开发用。                            |
| `DATA_AI_CORS_ORIGINS`   | 逗号分隔的允许 origin。空 = 不带 CORS 头。                 |
| `DATA_AI_SKILL_EXEC`     | `1` 开启技能执行端点。默认关闭。                           |
| `DATA_AI_LLM__MODEL`     | 默认 chat 模型 id。                                        |
| `DATA_AI_LLM__BASE_URL`  | 默认 API endpoint。                                        |
| `DATA_AI_LLM__API_KEY`   | 默认 API key。                                             |

也可以用 TOML 文件 `config/config.toml`，模板见
[`config/config.example.toml`](config/config.example.toml)。

## 安全

- 代码沙箱带 CPU / 内存 / 时间限制
- 三档权限策略：strict / moderate / permissive
- 所有路由默认走 Bearer key 鉴权
- 技能执行需要显式开环境变量，默认安装即使绕过鉴权也不会乱执行命令
- 没有遥测，不联网上报，除了你配的 provider 之外不向第三方发请求

## 项目状态

DATA-AI 适合自托管和实验，**不是**托管 SaaS。智能体 API 还在稳定
期，大约每月有一次 breaking change。

## 路线图

企业治理按编号分批交付。**Tier 1、2、3 已经发布**（见上文 *企业治理*）。
后续 tier 列在这里方便客户和贡献者提前规划。

### Tier 4 — 实时同步与 Runbook 自动化  *(计划中,未启动)*

| 计划项                                              | 为什么                                                            |
|-----------------------------------------------------|-------------------------------------------------------------------|
| 双向 WebSocket 跨区复制                             | 用真正能在区域间流 WAL 的传输层替换内存版复制引擎                 |
|   `core/replication/ws.py`                          |                                                                   |
| 一键 DR Runbook                                     | 把 detect → snapshot → failover → verify 串成一个可演练剧本       |
|   `core/recovery/runbook.py`                        |                                                                   |
| 赔付自动入账                                        | `Credit` 一旦通过，下一周期发票自动扣减                            |
|   `core/billing/credit_apply.py`                    |                                                                   |
| 按租户的 API 配额 (读 `tenants.limits`)             | 让 `tenants` 的 limit 真正驱动 `quota` 引擎,超额就拒,不只是统计   |
|   `core/quota/tenant_bridge.py`                     |                                                                   |
| SOC 2 / ISO 27001 取证导出                          | 把审计 + 保留 + DR 历史打包成 ZIP 给审计用                        |
|   `core/compliance/evidence.py`                     |                                                                   |

### Tier 5 — 联邦与市场  *(待办)*

| 计划项                                              | 为什么                                                            |
|-----------------------------------------------------|-------------------------------------------------------------------|
| 多模型路由 + 厂商 failover                          | 按成本/延迟/质量路由,5xx 自动切备                                  |
|   `core/llm/router.py`                              |                                                                   |
| 技能市场 (发布 + 签名安装)                          | 让合作伙伴发布带版本号的 Skill                                    |
|   `core/marketplace/`                               |                                                                   |
| BYO 身份 (LinkedIn、GitHub Org、企业微信)           | 在已有 SSO 引擎上补非企业 IdP                                     |
|   `core/sso/providers/linkedin.py` 等               |                                                                   |
| 独立 DATA-AI 实例间联邦                             | 跨组织智能体委派 + mTLS                                            |
|   `core/federation/`                                |                                                                   |

### Tier 6 — AI 原生运维  *(远景)*

| 计划项                                              | 为什么                                                            |
|-----------------------------------------------------|-------------------------------------------------------------------|
| 异常感知的审计告警                                  | 在 `audit` 流里挑出离群主体 / 时间 / payload                      |
| 自然语言 DR 演练 (`"演练上周那次"`)                 | 在 runbook 引擎上做 ChatOps 入口                                  |
| 预测性 SLA 违约模型                                 | 用事件历史预测未来 30 天的 SLO                                    |
| 自调优配额                                          | 根据租户增长趋势自动调高/调低限额                                |

最新进度跟踪在 [`ROADMAP.md`](ROADMAP.md) (每次 tier commit 同步)。

## 贡献

见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。简短版：fork、开分支、
`make install-dev`、`make test`、提 PR。改动尽量小、可证伪。

## 许可

[MIT](LICENSE)。
