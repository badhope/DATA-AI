# Dependency Management

## 原则

仓库**不**使用 dependabot。所有依赖变更由维护者手动评估后提 PR。

## 为什么关掉 dependabot

- 2026-06-08 启用后 1 小时内打开 12 个 PR，噪音大、混着跨大版本（`chromadb 0.5→1.5`、`lucide-react 0.x→1.x`、18 个 npm 包一组）和无害 patch；
- 大部分跨大版本升级需要专门回归测试（尤其 RAG / Memory / Embedding 链），不适合自动 PR；
- 我们的 PR 流程要求"做改动 → 开 PR → 用户 review → 合并"，依赖升级也是改动，应走同一流程。

## 当前依赖列表与升级流程

1. 关注上游 release（手动，或在浏览器收藏 [github.com/badhope/DATA-AI/pulls](https://github.com/badhope/DATA-AI/pulls) 等自己开的 issue）；
2. 评估影响：看 changelog、跑本地相关测试、必要时小批量分 PR；
3. 跨大版本：单独 PR、明确写动机、附回归测试。
4. 提 PR，等 review 后 merge。

## 历史

- 2026-06-08 一次性合并 6 个低风险 dependabot PR（python 3.14、GitHub Actions 6 个、python-dotenv、tiktoken、@types/react、sonner），关闭 6 个高风险 PR（`chromadb` / `sentence-transformers` / `rich` 跨大版本、`lucide-react` 0.x→1.x、`@biomejs/biome` 1→2、18 包 npm-production 组）；
- 之后删除 `.github/dependabot.yml`，机器人彻底关闭。
