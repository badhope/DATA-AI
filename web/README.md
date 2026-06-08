# DATA-AI Web

AI 智能体一体化控制台的前端。基于 **Vite 6 + React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui**。

## 启动

```bash
npm install
npm run dev        # 开发模式（http://localhost:5173）
npm run build      # 生产构建
npm run preview    # 预览生产构建
npm run typecheck  # 类型检查
npm run lint       # 代码检查
```

> 也支持 `pnpm` / `yarn`，把 `npm` 替换即可。

## 后端

需要 DATA-AI 后端在 `http://localhost:8000` 提供 OpenAI 兼容 API：

```bash
cd ..
python -m data_ai.core.api.server --port 8000
```

可在 `Settings` 页面配置后端地址和 API Key。

## 特性

- **12 个核心模块**：Dashboard / Chat / Agents / Team / Tools / Memory / RAG / Sandbox / Office (Word/PPT/Excel/PDF) / Models / Skills / Settings
- **响应式设计**：桌面、平板、手机全适配
- **暗色优先**：可在 Settings 切换浅色/跟随系统
- **流式聊天**：SSE 实时渲染，工具调用可视化
- **键盘快捷键**：`⌘K` 搜索，`⌘/` 切换侧边栏，`⌘Enter` 发送
- **shadcn/ui 风格组件**：15+ 高质量组件，全部可定制
- **TanStack Query**：服务端状态缓存
- **Zustand**：本地状态持久化到 localStorage
- **framer-motion**：流畅的页面切换和微交互
- **Sonner Toast**：优雅的提示系统
