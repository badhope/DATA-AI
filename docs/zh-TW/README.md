# DATA-AI

> 一個終於看得懂你公司資料的 AI 智能體。

講真的——我們太熟悉這個畫面了。每家公司都有一堆財務報告、內部文件、客戶資料、專案檔案,還有一個誰都不敢動的神秘資料夾,加上幾張根本是公司命脈的 Excel 表。這些東西彼此不通,誰也找不到,而真正看得懂的人,早就被需求淹沒了。

**DATA-AI** 就是為了解決這個。

**DATA-AI** 是一個可以自架的 AI 智能體,直接住進你的企業資料裡——財務、內部知識、那些重要資料——替你做那些沒人想做的活。問個問題,它就在你的檔案裡翻一翻,給你答案,還附上來源。指派一個任務給它,它就跑。需要 `/finance/2025-Q4/` 的週報?兩分鐘搞定,不是兩天。

## 你能拿到什麼

- **真的懂你業務的知識庫** —— 把 PDF、Word、表格、Notion 匯出、內部 wiki、純文字丟進去,它會建索引、學習,然後像一個待了十年的老同事那樣回答問題。
- **畫出來的工作流程,不用寫程式** —— 拖幾個方塊,接上線,儲存。資料清洗、每月報告、「總結 `/legal/` 裡的新東西」、「標記這季到期的合約」,隨便你。
- **真的會把事做完的 Agent** —— 丟一個目標給它,自己拆步驟、自己呼叫工具、自己檢查,最後跟你回報做了什麼。少操點心,多出點貨。
- **模型任你選** —— OpenAI、Claude、DeepSeek、本地 Llama、你們團隊偏愛的那個冷門的,接上來就能用。
- **向量資料庫任你挑** —— pgvector、Milvus、Weaviate、Qdrant、Elasticsearch,你已經在跑哪個就用哪個。
- **不反人類的 Web 介面** —— 管理員用控制台,一般使用者用聊天,工程師用 API,誰都不用看廣告。

## 為什麼做這個

我們試過 SaaS 方案,試過「開源核心 + 付費加值」,也試過直接用 OpenAI API 自己刻一個,刻到第四遍寫一樣的樣板程式碼的時候,我們累了。

所以做了一個我們自己真的會用的:

- **自架** —— 一台 Linux 伺服器就夠,不用 Kubernetes。
- **資料不出門** —— 不傳到外網,每次模型呼叫都能稽核。
- **不用打電話找業務** —— 開源的,程式碼就在這。
- **不畫大餅** —— 誰需要什麼功能,我們就寫。

## 跑起來

最簡單的方式(Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI/docker
cp .env.example .env
docker compose up -d
```

純手動方式(不安裝 Docker):

```bash
git clone https://github.com/<your-org>/DATA-AI.git
cd DATA-AI
./dev/setup
./dev/start-api    # 一個終端
./dev/start-web    # 另一個
```

然後打開 <http://localhost:3000>。完整安裝指南在 [`docs/`](./docs/)。

## 架構,一句話講完

後端 Python + Flask,按領域分好包,找東西方便。前端 Next.js(新版本那種,不是 2018 年的老古董)。結構化資料丟 PostgreSQL,向量用你選的向量資料庫。背景任務走 Celery + Redis。外掛機制讓你可以加模型、工具、整合,不用 fork 整個 repo。

## 一起來

我們收 PR。先看 [CONTRIBUTING.md](./CONTRIBUTING.md),別讓你週六白忙一場。

## 授權

[Apache 2.0](./LICENSE)。愛怎麼用怎麼用,留個版權聲明就好。
