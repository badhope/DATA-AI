# DATA-AI

> 一个终于能看懂你公司数据的 AI 智能体。

说真的——我们太熟悉这个场景了。每个公司都有一堆财务报告、内部文档、客户档案、项目文件,还有一个谁都不敢动的神秘文件夹,加几张基本上是公司命脉的 Excel 表。这些东西彼此不通,谁也找不到,而真正能看懂的人,已经被需求淹没了。

**DATA-AI** 就是为这个而生的。

**DATA-AI** 是一个可以自托管的 AI 智能体,直接住进你的企业数据里——财务、内部知识、那些重要数据——替你干那些没人想干的活。问个问题,它在你的文件里翻一遍,给你答案,还附上来源。交给它一个任务,它就跑。需要 `/finance/2025-Q4/` 的周报?两分钟搞定,不是两天。

## 你能拿到什么

- **真的懂你业务的知识库** —— 把 PDF、Word、表格、Notion 导出、内部 wiki、纯文本丢进去,它会建索引、学习,然后像一个干了十年的老同事那样回答问题。
- **画出来的工作流,不用写代码** —— 拖几个块,接上线,保存。数据清洗、月报、"总结 `/legal/` 里的新东西"、"标记这个季度要过期的合同",随便你。
- **真能干活儿的 Agent** —— 丢给它一个目标,自己拆解步骤,自己调用工具,自己检查,最后跟你汇报干完了什么。少操心,多出活。
- **模型随便选** —— OpenAI、Claude、DeepSeek、本地 Llama、你们团队偏爱的那个冷门的,插进来就能用。
- **向量库随便挑** —— pgvector、Milvus、Weaviate、Qdrant、Elasticsearch,你在用哪个就用哪个。
- **不反人类的 Web 界面** —— 管理员用控制台,普通用户用聊天,工程师用 API,谁都不用看广告。

## 为什么做这个

我们试过 SaaS 方案,试过"开源核心 + 收费扩展",也试过直接用 OpenAI API 撸一个,撸到第四遍写同样的样板代码时,我们累了。

于是做了一个我们真的想用的:

- **自托管** —— 一台 Linux 服务器就够,不用 Kubernetes。
- **数据不出门** —— 不发到外网,每次模型调用都能审计。
- **不用打电话给销售** —— 开源的,代码就在这。
- **不画饼** —— 谁需要什么功能,我们就写。

## 跑起来

最简单的方式(Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

纯手动方式(不装 Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # 一个终端
./dev/start-web    # 另一个终端
```

然后打开 <http://localhost:3000>。详细安装见 [`docs/`](./docs/)。

## 架构,一段话讲完

后端 Python + Flask,按领域分好包,找东西方便。前端 Next.js(新版本那种,不是 2018 年的老古董)。结构化数据丢 PostgreSQL,向量走你选的向量库。后台任务用 Celery + Redis。插件机制让你能加模型、工具、集成,不用 fork 整个仓库。

## 一起干

我们收 PR。先看 [CONTRIBUTING.md](./CONTRIBUTING.md),省得你周六白干。

## 协议

[Apache 2.0](./LICENSE)。想干嘛干嘛,留个版权声明就行。
