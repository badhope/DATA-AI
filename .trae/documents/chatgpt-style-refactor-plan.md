# DATA-AI 前端 ChatGPT 风格重构计划

## 目标
将 DATA-AI 前端界面完全重构为 ChatGPT 风格的现代化 UI，**保持所有现有功能不变**，仅重写 HTML 布局和 CSS 样式体系。

---

## ChatGPT 风格设计原则

1. **极简主义**：隐藏复杂性，默认只展示核心对话界面
2. **左侧折叠侧边栏**：对话历史列表，可完全折叠，hover 展开
3. **居中对话流**：消息在页面中央纵向排列，最大宽度 ~768px
4. **清晰的消息角色区分**：用户消息靠右/深色背景，AI 消息靠左/无背景
5. **底部固定输入区**：输入框居中，带附件/搜索等可展开按钮
6. **顶部轻量导航**：模型选择器 + 新建对话 + 折叠侧边栏按钮
7. **暗色/亮色主题无缝切换**
8. **微妙的动画过渡**：hover 状态、消息出现动画、面板滑入

---

## 实施步骤

### 步骤 1：创建全新 CSS 体系（ChatGPT 风格）

**文件：`/workspace/static/css/chatgpt-style.css`**（新文件）

创建全新的 CSS 变量和基础样式体系：

#### 1.1 CSS 变量（暗色主题默认）
```
--bg-primary: #212121       (类似 ChatGPT 深色背景)
--bg-secondary: #2f2f2f     (侧边栏/卡片背景)
--bg-tertiary: #171717      (更深背景)
--bg-user-bubble: #303030   (用户消息气泡)
--bg-hover: #2a2a2a         (hover 高亮)
--text-primary: #ECECF1     (主文字色)
--text-secondary: #B4B4B4   (次要文字)
--text-tertiary: #8E8E8E    (更弱文字)
--accent-color: #10a37f     (品牌绿色)
--border-color: #444444     (边框)
--border-light: #333333     (细边框)
--sidebar-width: 260px      (侧边栏宽度)
--chat-max-width: 768px     (对话最大宽度)
--input-max-width: 768px    (输入区最大宽度)
--radius-sm: 6px
--radius-md: 12px
--radius-lg: 18px
--radius-xl: 24px
--font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
--font-mono: 'JetBrains Mono', 'Fira Code', monospace
```

亮色主题变量同理（反转）。

#### 1.2 全局重置
- 去除所有默认 margin/padding
- box-sizing: border-box
- 设置 body 字体、背景色、文字色
- 平滑滚动 `scroll-behavior: smooth`

#### 1.3 布局系统
```
.app-container {
    display: flex;
    height: 100vh;
    overflow: hidden;
}
```

---

### 步骤 2：重构 HTML 布局结构

**文件：`/workspace/static/index.html`**

完全重写 HTML DOM 结构，保持所有数据属性和 ID 不变，只改变布局层级。

#### 2.1 新布局结构（自上而下）

```
<body>
  ├── <div class="app-wrapper">
  │   ├── <!-- 可折叠侧边栏 -->
  │   ├── <aside class="sidebar" id="sidebar">
  │   │   ├── <div class="sidebar-header">
  │   │   │   ├── 折叠按钮 (汉堡菜单)
  │   │   │   └── 新建对话按钮 (+)
  │   │   ├── <div class="sidebar-conversations">
  │   │   │   └── 对话列表 (按日期分组: 今天/昨天/更早)
  │   │   ├── <div class="sidebar-footer">
  │   │   │   └── 用户信息/设置入口
  │   │   
  │   ├── <!-- 主区域 -->
  │   ├── <div class="main-panel">
  │   │   ├── <!-- 顶部导航条（极简） -->
  │   │   ├── <nav class="top-bar">
  │   │   │   ├── 左侧：折叠侧边栏按钮 (三明治图标)
  │   │   │   ├── 中间：模型选择器下拉 (小号，紧凑)
  │   │   │   └── 右侧：新建对话 / 分享 / 导出
  │   │   │
  │   │   ├── <!-- 对话区域（核心） -->
  │   │   ├── <main class="chat-main" id="chat-area">
  │   │   │   ├── <!-- 消息流 -->
  │   │   │   ├── <div class="messages-container">
  │   │   │   │   ├── 欢迎页 (首次进入)
  │   │   │   │   └── 消息列表
  │   │   │   ├── <!-- 滚动到底部按钮 -->
  │   │   │   └── <!-- 思考动画层 -->
  │   │   │
  │   │   ├── <!-- 底部输入区 -->
  │   │   ├── <footer class="input-area" id="input-area">
  │   │   │   ├── <div class="input-container">
  │   │   │   │   ├── 附件预览区
  │   │   │   │   ├── 输入框 (多行 auto-resize)
  │   │   │   │   └── 发送/停止按钮
  │   │   │   ├── <div class="input-footer">
  │   │   │   │   ├── 附件上传按钮
  │   │   │   │   ├── 联网搜索开关
  │   │   │   │   ├── 技能按钮
  │   │   │   │   ├── 更多功能按钮 (图表/PPT/流程图/润色/会议/摘要/记忆)
  │   │   │   │   └── 免责声明文字
  │   │   
  │   ├── <!-- 抽屉叠加层（右侧滑出，按需显示） -->
  │   ├── <div class="drawers-overlay">
  │   │   ├── <div class="drawer-backdrop" id="drawer-backdrop">
  │   │   ├── <!-- 设置抽屉 -->
  │   │   ├── <div class="drawer-panel" id="settings-drawer">
  │   │   ├── ... (保留原 settings-drawer 全部结构)
  │   │   ├── <!-- 知识库抽屉 -->
  │   │   ├── <div class="drawer-panel" id="kb-drawer">
  │   │   ├── ... (保留原 kb-drawer 全部结构)
  │   │   ├── <!-- 技能抽屉 -->
  │   │   ├── <div class="drawer-panel" id="skill-drawer">
  │   │   ├── ... (保留原 skill-drawer 全部结构)
  │   │   
  │   ├── <!-- 功能面板（右侧滑出，更小尺寸） -->
  │   ├── <div class="drawer-panel panel-sm" id="polish-panel">
  │   ├── <div class="drawer-panel panel-sm" id="meeting-panel">
  │   ├── <div class="drawer-panel panel-sm" id="summary-panel">
  │   ├── <div class="drawer-panel panel-sm" id="memory-panel">
  │   ├── ...
  │   
  │   ├── <!-- 模态框 -->
  │   ├── <div id="help-modal"> ... 
  │   ├── <div id="shortcuts-modal"> ...
  │   ├── ... (保留所有原有 ID)
  │   
  │   ├── <!-- Toast / Artifacts / 图表 -->
  │   ├── <div id="artifacts-panel"> ...
  │   ├── <div id="generated-chart"> ...
  │   ├── <div id="toast-container"> ...
  │   ├── <div id="image-preview-overlay"> ...
  │   ├── <div id="offline-banner"> ...
```

#### 2.2 保留不变的元素（通过 ID 匹配）

所有以下元素的 ID 必须保持不变，确保 JavaScript 功能不受影响：
- `#sidebar`, `#sidebar-overlay`, `#sidebar-toggle`, `#sidebar-close`
- `#chat-area`, `#chat-header`
- `#input-area`, `#user-input`, `#send-btn`, `#stop-btn`
- `#attach-btn`, `#web-search-toggle`, `#web-search-btn`
- `#more-actions-btn`, `#more-actions-panel`
- `#settings-drawer`, `#kb-drawer`, `#skill-drawer`
- `#settings-btn`, `#sidebar-settings-btn`, `#sidebar-kb-btn`
- `#polish-panel`, `#meeting-panel`, `#summary-panel`, `#memory-panel`
- `#polish-btn`, `#meeting-btn`, `#summary-btn`, `#memory-btn`
- `#model-selector`, `#model-dropdown`
- `#share-btn`, `#export-pdf-btn`, `#export-md-btn`
- `#artifacts-panel`, `#generated-chart`
- `#help-modal`, `#shortcuts-modal`
- `#toast-container`, `#image-preview-overlay`, `#offline-banner`
- `#scroll-to-bottom-btn`
- `#skill-quick-btn`
- `#welcome-screen` (欢迎页)

#### 2.3 新增 CSS 类（ChatGPT 风格）

为所有新布局添加语义化 CSS 类：

```
.app-wrapper         - 最外层包裹
.main-panel          - 主面板（侧边栏外的区域）
.top-bar             - 顶部导航条
.chat-main           - 对话主区域
.messages-container  - 消息列表容器
.input-container     - 输入框外层容器
.input-footer        - 输入框底部按钮行
.drawers-overlay     - 抽屉叠加层容器
.drawer-backdrop     - 抽屉遮罩
.drawer-panel        - 抽屉面板（通用）
.panel-sm            - 小型功能面板（润色/会议/摘要/记忆）
.sidebar-header      - 侧边栏头部
.sidebar-conversations - 对话列表区
.sidebar-footer      - 侧边栏底部
```

---

### 步骤 3：重新设计 Sidebar 样式

ChatGPT 风格的侧边栏特征：
- 默认展开宽度 260px
- 可完全折叠（宽度 0，或仅显示图标）
- 新建对话按钮在顶部
- 对话列表按时间分组：今天/昨天/本周/更早
- 每个对话项：标题 + 更多操作（hover 显示）
- 底部个人信息区

CSS 实现要点：
```css
.sidebar {
    width: var(--sidebar-width);
    transition: width 0.2s ease;
    flex-shrink: 0;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-light);
    display: flex;
    flex-direction: column;
}

.sidebar.collapsed {
    width: 0;
    overflow: hidden;
}
```

---

### 步骤 4：重新设计 Chat Area（对话区域）

ChatGPT 风格的核心特征：
- 消息垂直居中排列，max-width: 768px，margin: 0 auto
- 用户消息：右对齐或无背景区分，简洁
- AI 消息：左对齐，无背景，纯文本/代码块
- Markdown 渲染：代码块有深色背景和复制按钮
- 思考动画：紧凑、优雅的点动画

```css
.messages-container {
    max-width: var(--chat-max-width);
    margin: 0 auto;
    padding: 20px 16px;
}

.message {
    display: flex;
    padding: 16px 24px;
}

.message.user {
    /* 用户消息风格 */
}

.message.assistant {
    /* AI 消息风格 */
}
```

---

### 步骤 5：重新设计 Input Area（输入区）

ChatGPT 风格：
- 固定在底部
- 输入框圆角大 (24px)
- 居中 max-width: 768px
- 发送按钮在输入框内部右侧
- 底部小字免责声明
- 附件/搜索/技能按钮排列在输入框下方

```css
.input-area {
    position: sticky;
    bottom: 0;
    background: linear-gradient(transparent, var(--bg-primary) 20%);
    padding: 12px 16px 24px;
}

.input-container {
    max-width: var(--input-max-width);
    margin: 0 auto;
    position: relative;
}

#user-input {
    width: 100%;
    border-radius: var(--radius-xl);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    padding: 12px 48px 12px 16px;
    color: var(--text-primary);
    resize: none;
}
```

---

### 步骤 6：重新设计 Model Selector（模型选择器）

ChatGPT 风格：
- 简单的下拉菜单
- 字体更小，更紧凑
- hover 展开，有过渡动画

---

### 步骤 7：重新设计 Messages（消息气泡）

ChatGPT 的消息风格：
- **用户消息**：无气泡背景，仅文字，或轻量灰色
- **AI 消息**：左侧带绿色竖线或完全无装饰
- 代码块：深色背景，带语言标签和复制按钮
- 思考阶段：三点脉动动画

---

### 步骤 8：重新设计 Drawers & Panels（抽屉和面板）

保留原功能的面板，使用 ChatGPT 风格的右侧滑出：
- 面板从右侧滑入，宽度 500px
- 半透明遮罩背景
- 面板内有自己的 header（标题 + 关闭按钮）
- body 区域可滚动
- 过渡动画 0.3s ease

```css
.drawer-panel {
    position: fixed;
    top: 0;
    right: 0;
    width: 500px;
    height: 100vh;
    background: var(--bg-primary);
    border-left: 1px solid var(--border-color);
    transform: translateX(100%);
    transition: transform 0.3s ease;
    z-index: 100;
}

.drawer-panel.open {
    transform: translateX(0);
}
```

---

### 步骤 9：亮色/暗色主题系统

模仿 ChatGPT 的暗色/亮色切换：
- CSS 变量在 `:root` 和 `[data-theme="light"]` 中定义
- 切换按钮在设置面板中
- 过渡平滑（`transition: background-color 0.3s, color 0.3s`）

---

### 步骤 10：动画系统

微妙的动画细节：
- 消息出现：从下方轻微滑入 + fade in
- 发送按钮：hover 缩放/green 高亮
- 侧边栏：折叠/展开平滑过渡
- 下拉菜单：scale + opacity 动画
- 抽屉面板：从右侧滑入
- 思考动画：三点脉动

---

### 步骤 11：响应式适配

移动端适配：
- 侧边栏默认隐藏，点击按钮覆盖显示
- 消息 max-width: 100%
- 输入区全宽
- 适配 768px 以下断点

---

### 步骤 12：JS 适配（最小修改）

**重要**：JavaScript 功能代码基本不需要修改，因为所有 ID 保持不变。可能需要微调的部分：

1. `initSidebar()` - 折叠/展开逻辑可能需要微调
2. `initDrawers()` - 抽屉打开/关闭逻辑可能需要适配新的 CSS 类名
3. `initWelcomeSuggestions()` - welcome-screen 可能需要调整位置

**不改动的部分**（保证功能完整性）：
- WebSocket 通信系统
- 消息处理 `handleWSMessage`
- 对话 CRUD 系统
- 模型选择器 `initModelSelector`
- 输入发送系统
- 所有 API 调用
- 日志/调试/统计/记忆/NLP 系统
- 润色/会议/摘要/记忆面板功能
- PPT/图表/流程图生成
- 语音合成/识别
- 键盘快捷键
- 异常处理/错误捕获

---

## 文件修改清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `/workspace/static/index.html` | **重写** | 重构 DOM 布局，保留所有 ID 和 data 属性 |
| `/workspace/static/css/chatgpt-style.css` | **新建** | 全新 ChatGPT 风格 CSS |
| `/workspace/static/css/style.css` | **替换内容** | 清空并改为导入 chatgpt-style.css，或备份后替换 |
| `/workspace/static/css/components.css` | **备份后重写** | 全部组件样式重新设计 |
| `/workspace/static/js/app.js` | **微调** | 仅适配新 CSS 类名，不改变逻辑 |

---

## 实施顺序

1. **先** 创建 `/workspace/static/css/chatgpt-style.css`（新 CSS 体系）
2. **再** 重写 `/workspace/static/css/components.css`（组件样式）
3. **然后** 重写 `/workspace/static/index.html`（DOM 结构）
4. **再** 修改 `/workspace/static/css/style.css`（导入新样式）
5. **最后** 微调 `/workspace/static/js/app.js`（适配 CSS 类名）
6. **验证** 重启服务器，测试所有功能正常

---

## 风险与注意事项

1. **所有元素 ID 和数据属性必须完全保留**，否则 JS 功能会断裂
2. **CSS 类名变更需同步修改 JS 中的选择器**
3. **外部 CDN 资源引用保持不变**（Font Awesome、highlight.js 等）
4. **pages.css 保持不变**（子页面不需要重构）
5. **先备份原 CSS 文件**，出问题可快速回滚