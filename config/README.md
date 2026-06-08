# DATA-AI 配置指南

## 📁 配置目录结构

```
config/
├── config.toml              # 主配置文件（实际使用）
├── config.example.toml      # 完整配置模板（参考）
├── config.example.json      # JSON 格式配置示例
├── examples/                # 其他模型配置示例
│   ├── config.example-model-anthropic.toml   # Anthropic Claude
│   ├── config.example-model-azure.toml       # Azure OpenAI
│   ├── config.example-model-google.toml      # Google Gemini
│   ├── config.example-model-jiekouai.toml   # Jiekou.AI
│   ├── config.example-model-ollama.toml      # Ollama (本地)
│   ├── config.example-model-ppio.toml        # PPIO
│   └── config.example-daytona.toml          # Daytona 沙箱
├── schema/                  # 配置 schema 定义
│   ├── knowledge_base_schema.json
│   ├── mcp_schema.json
│   └── skill_schema.json
└── README.md               # 本文档
```

## 🔧 配置优先级

配置文件加载优先级（从高到低）：
1. **config.toml** - 实际使用的配置文件
2. **config.example.toml** - 完整模板参考
3. **环境变量** - 可通过环境变量覆盖
4. **config.example-*.toml** - 特定模型配置参考

## 🚀 快速开始

### 1. 复制配置模板
```bash
cp config/config.example.toml config/config.toml
```

### 2. 编辑配置文件
编辑 `config.toml` 填入你的 API 密钥：
```toml
[llm]
model = "claude-3-7-sonnet-20250219"
base_url = "https://api.anthropic.com/v1/"
api_key = "YOUR_API_KEY_HERE"  # 填入你的 API 密钥
```

### 3. 验证配置
```bash
python scripts/validate_config.py
```

## 📝 配置节说明

### LLM 配置
```toml
[llm]
model = "claude-3-7-sonnet-20250219"
base_url = "https://api.anthropic.com/v1/"
api_key = "YOUR_API_KEY"
max_tokens = 8192
temperature = 0.0
```

### 记忆系统配置
```toml
[memory]
enable_long_term_memory = true
enable_conversation_summarization = true
keep_recent_messages = 20
summary_interval = 10
```

### 沙箱配置
```toml
[sandbox]
use_sandbox = true
sandbox_type = "local"
work_dir = "/workspace"
timeout = 300
```

### 浏览器配置
```toml
[browser]
headless = false
disable_security = true
max_content_length = 2000
```

### 搜索配置
```toml
[search]
engine = "Google"
fallback_engines = ["DuckDuckGo", "Baidu", "Bing"]
```

## 🔍 配置验证

使用验证脚本检查配置：
```bash
python scripts/validate_config.py
```

验证内容包括：
- TOML 语法正确性
- 必需字段存在性
- 值类型正确性

## 📚 其他配置资源

- [CONFIGURATION.md](../docs/CONFIGURATION.md) - 详细配置文档
- [config.example.toml](config.example.toml) - 完整配置示例
- [examples/](examples/) - 各种模型配置参考

## ⚠️ 注意事项

1. **API 密钥安全**：不要将 config.toml 提交到版本控制
2. **配置同步**：修改配置后需要重启应用
3. **版本兼容**：不同版本的配置可能不兼容，请参考对应版本的配置模板

## 🔧 故障排除

### 配置不生效
1. 检查配置文件路径是否正确
2. 确认配置文件格式（TOML）无语法错误
3. 查看应用启动日志中的配置加载信息

### API 密钥错误
1. 确认 API 密钥正确且未过期
2. 检查 base_url 是否正确
3. 确认账户有足够的 API 调用配额

---

**文档版本**: v1.0
**最后更新**: 2026-05-25
