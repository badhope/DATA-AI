# 前端界面问题修复 Spec

## Why
通过全面诊断发现前端界面存在 6 个问题，包括 CDN 资源加载失败、缺少 favicon、UI 面板重叠等，影响用户体验和部分功能可用性。

## What Changes
- 修复 Dropzone.js CDN 加载失败问题（影响文件上传功能）
- 修复 PDF.js CDN 加载失败问题（影响 PDF 导出/预览功能）
- 添加缺失的 favicon.ico 文件
- 移除或修复不可用的外部脚本（previewer-tools）
- 优化右侧面板默认状态（避免 UI 拥挤）
- 处理禁用状态的语音按钮展示

## Impact
- Affected specs: 无
- Affected code: `static/index.html`, `static/css/style.css`, `static/css/components.css`

## ADDED Requirements

### Requirement: CDN 资源本地化
系统 SHALL 将关键的外部 CDN 资源本地化，确保在网络受限环境下功能正常。

#### Scenario: 文件上传功能正常
- **WHEN** 用户点击附件上传按钮
- **THEN** Dropzone.js 正确加载，文件选择对话框正常弹出

#### Scenario: PDF 导出功能正常
- **WHEN** 用户点击导出 PDF 按钮
- **THEN** PDF.js 正确加载，PDF 生成功能正常工作

### Requirement: Favicon 显示
系统 SHALL 提供正确的网站图标文件。

#### Scenario: 浏览器标签页显示图标
- **WHEN** 用户在浏览器中打开页面
- **THEN** 浏览器标签页显示 DATA-AI 的网站图标

### Requirement: 右侧面板 UI 优化
系统 SHALL 默认隐藏右侧面板，避免页面初始状态过于拥挤。

#### Scenario: 页面加载时面板状态
- **WHEN** 用户首次打开页面
- **THEN** 所有右侧面板（设置、润色、会议纪要等）处于收起状态

## MODIFIED Requirements

### Requirement: 外部资源加载策略
将 index.html 中的外部 CDN 资源改为使用可靠的 CDN 或本地备用方案：
1. Dropzone.js - 使用备用 CDN 或本地化
2. PDF.js - 使用备用 CDN 或本地化
3. previewer-tools - 移除不可靠的外部依赖

### Requirement: 禁用按钮处理
对于"开发中"的功能按钮，添加视觉上的弱化处理或隐藏，避免用户困惑。
