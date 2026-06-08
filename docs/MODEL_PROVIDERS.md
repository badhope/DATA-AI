# 模型提供商配置指南

本文档汇总了所有支持的模型提供商的 API 密钥规则、认证方式和配置方法。

## 目录

- [国际厂商](#国际厂商)
  - [OpenAI](#openai)
  - [Anthropic Claude](#anthropic-claude)
  - [Google Gemini](#google-gemini)
  - [Azure OpenAI](#azure-openai)
  - [AWS Bedrock](#aws-bedrock)
- [国内厂商](#国内厂商)
  - [DeepSeek](#deepseek)
  - [SiliconFlow (硅基流动)](#siliconflow-硅基流动)
- [本地模型](#本地模型)
  - [Ollama](#ollama)
  - [vLLM](#vllm)
  - [LM Studio](#lm-studio)

---

## 国际厂商

### OpenAI

| 项目 | 说明 |
|------|------|
| **官网** | https://platform.openai.com |
| **密钥前缀** | `sk-` |
| **密钥格式** | `sk-` + 48位字母数字组合，例如：`sk-abcdefghijklmnopqrstuvwxyz123456789ABCDEFGHI` |
| **认证方式** | Bearer Token |
| **请求头** | `Authorization: Bearer <API_KEY>` |
| **默认端点** | `https://api.openai.com/v1` |
| **环境变量** | `OPENAI_API_KEY` 或 `DATA_AI_LLM__API_KEY` |

**密钥获取步骤：**
1. 访问 https://platform.openai.com 注册/登录
2. 进入 Dashboard → API Keys
3. 点击 "Create new secret key"
4. 立即复制保存（密钥只显示一次）

**支持的模型：**
- `gpt-4o` - 多模态旗舰模型
- `gpt-4o-mini` - 快速轻量模型
- `gpt-4-turbo` - 长上下文模型
- `gpt-3.5-turbo` - 经济型模型
- `o1-preview` / `o1-mini` - 推理模型

---

### Anthropic Claude

| 项目 | 说明 |
|------|------|
| **官网** | https://console.anthropic.com |
| **密钥前缀** | `sk-ant-` |
| **密钥格式** | `sk-ant-` + 32位字母数字组合，例如：`sk-ant-api03-abcdefghijklmnopqrstuvwxyz123456` |
| **认证方式** | Bearer Token + x-api-key |
| **请求头** | `Authorization: Bearer <API_KEY>` 或 `x-api-key: <API_KEY>` |
| **默认端点** | `https://api.anthropic.com` |
| **环境变量** | `ANTHROPIC_API_KEY` 或 `DATA_AI_LLM__API_KEY` |

**密钥获取步骤：**
1. 访问 https://console.anthropic.com 注册/登录
2. 进入 Settings → API Keys
3. 点击 "Create Key"
4. 命名密钥并复制保存

**支持的模型：**
- `claude-3-5-sonnet-20250619` - 推荐，综合能力最强
- `claude-3-5-haiku-20241022` - 快速响应
- `claude-3-opus-20240229` - 复杂任务
- `claude-3-sonnet-20240229` - 平衡选择

---

### Google Gemini

| 项目 | 说明 |
|------|------|
| **官网** | https://aistudio.google.com |
| **密钥前缀** | `AIzaSy` |
| **密钥格式** | `AIzaSy` + 35 位字母数字组合，例如：`AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`（请替换为你自己的 key） |
| **认证方式** | URL 参数或 Header |
| **请求方式** | `?key=<API_KEY>` 或 `x-goog-api-key: <API_KEY>` |
| **默认端点** | `https://generativelanguage.googleapis.com/v1beta` |
| **环境变量** | `GOOGLE_API_KEY` 或 `DATA_AI_LLM__API_KEY` |

**密钥获取步骤：**
1. 访问 https://aistudio.google.com 登录 Google 账号
2. 点击左侧 "Get API key"
3. 选择 "Create API key in new project"
4. 复制生成的密钥（39位字符）

**支持的模型：**
- `gemini-2.5-flash` - 快速响应
- `gemini-2.5-pro` - 复杂推理
- `gemini-2.0-flash` - 图像生成
- `gemini-1.5-pro` - 长上下文（200万 tokens）

---

### Azure OpenAI

| 项目 | 说明 |
|------|------|
| **官网** | https://portal.azure.com |
| **密钥格式** | 32位十六进制字符串，无特定前缀，例如：`a1b2c3d4e5f678901234567890123456` |
| **认证方式** | API Key Header |
| **请求头** | `api-key: <API_KEY>` |
| **端点格式** | `https://<RESOURCE_NAME>.openai.azure.com/` |
| **环境变量** | `AZURE_OPENAI_API_KEY` 或 `DATA_AI_LLM__API_KEY` |

**密钥获取步骤：**
1. 登录 Azure Portal (https://portal.azure.com)
2. 找到你的 Azure OpenAI 资源
3. 进入 "Keys and Endpoint"
4. 复制 KEY 1 或 KEY 2

**特殊配置：**
- 需要同时配置 `base_url`（端点）和 `api_version`
- 模型名称使用部署名（非原始模型名）
- 支持 Microsoft Entra ID 认证（企业场景）

**示例配置：**
```toml
[llm]
api_type = "azure"
base_url = "https://my-resource.openai.azure.com/"
api_version = "2024-10-21"
model = "gpt-4-deployment-name"  # 你的部署名
```

---

### AWS Bedrock

| 项目 | 说明 |
|------|------|
| **官网** | https://aws.amazon.com/bedrock |
| **密钥格式** | AWS Access Key ID + Secret Access Key |
| **Access Key ID** | 20位字母数字，例如：`AKIAIOSFODNN7EXAMPLE` |
| **Secret Key** | 40位 base64 编码字符串 |
| **认证方式** | AWS SigV4 签名 |
| **环境变量** | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` |

**密钥获取步骤：**
1. 登录 AWS Console → IAM
2. 创建 IAM 用户并附加 `AmazonBedrockFullAccess` 策略
3. 创建 Access Key（选择 "Third-party service"）
4. 保存 Access Key ID 和 Secret Access Key

**Bedrock API Key（替代方案）：**
- 2025年新增 Bedrock 专属 API Key
- 格式：长字符串（ServiceCredentialSecret）
- 环境变量：`AWS_BEARER_TOKEN_BEDROCK`

**支持的模型：**
- `anthropic.claude-3-5-sonnet-20251022-v1:0`
- `anthropic.claude-3-opus-20240229-v1:0`
- `amazon.nova-pro-v1:0`
- `meta.llama3-70b-instruct-v1:0`

---

## 国内厂商

### DeepSeek

| 项目 | 说明 |
|------|------|
| **官网** | https://platform.deepseek.com |
| **密钥前缀** | `sk-` |
| **密钥格式** | `sk-` + 48位字母数字组合，例如：`sk-1234567890abcdef1234567890abcdef1234567890abcdef` |
| **认证方式** | Bearer Token |
| **请求头** | `Authorization: Bearer <API_KEY>` |
| **默认端点** | `https://api.deepseek.com/v1` |
| **环境变量** | `DEEPSEEK_API_KEY` 或 `DATA_AI_LLM__API_KEY` |

**密钥获取步骤：**
1. 访问 https://platform.deepseek.com 注册/登录
2. 进入左侧 "API Keys"
3. 点击 "Create API Key"
4. 命名并复制密钥

**支持的模型：**
- `deepseek-chat` - 通用对话（V3 模型）
- `deepseek-reasoner` - 推理模式（R1 模型，带思维链）

**特点：**
- 价格极具竞争力
- 推理模型支持 `reasoning_content` 输出
- 与 OpenAI API 格式兼容

---

### SiliconFlow (硅基流动)

| 项目 | 说明 |
|------|------|
| **官网** | https://cloud.siliconflow.cn |
| **密钥前缀** | `sk-` |
| **密钥格式** | `sk-` + 字母数字组合 |
| **认证方式** | Bearer Token |
| **请求头** | `Authorization: Bearer <API_KEY>` |
| **默认端点** | `https://api.siliconflow.cn/v1` |
| **环境变量** | `SILICON_API_KEY` 或 `DATA_AI_LLM__API_KEY` |

**密钥获取步骤：**
1. 访问 https://cloud.siliconflow.cn 注册/登录
2. 进入 "API密钥" 页面
3. 点击 "新建API密钥"
4. 复制生成的密钥

**支持的模型：**
- `deepseek-ai/DeepSeek-V3` - DeepSeek V3
- `deepseek-ai/DeepSeek-R1` - DeepSeek R1
- `Qwen/Qwen2.5-72B-Instruct` - 通义千问
- `Pro/BAAI/bge-m3` - 嵌入模型
- `BAAI/bge-reranker-v2-m3` - 重排序模型

**特点：**
- 聚合多个开源模型
- 提供嵌入、重排序、TTS、STT 等模型
- 价格优惠，适合国内用户

---

## 本地模型

### Ollama

| 项目 | 说明 |
|------|------|
| **官网** | https://ollama.com |
| **密钥要求** | 无（本地运行无需认证） |
| **虚拟密钥** | 可设置为任意字符串，例如：`ollama` |
| **默认端点** | `http://localhost:11434/v1` |
| **环境变量** | `OLLAMA_HOST`（可选，默认 localhost） |

**安装步骤：**
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# 下载安装包：https://ollama.com/download/windows
```

**使用步骤：**
1. 启动 Ollama 服务：`ollama serve`
2. 拉取模型：`ollama pull llama3`
3. 配置 base_url 为 `http://localhost:11434/v1`
4. API key 可设置为任意值（如 `ollama`）

**支持的模型：**
- `llama3` / `llama3.1` / `llama3.2`
- `qwen2` / `qwen2.5`
- `mistral` / `mixtral`
- `gemma` / `gemma2`
- `phi4`
- `deepseek-coder-v2`

---

### vLLM

| 项目 | 说明 |
|------|------|
| **GitHub** | https://github.com/vllm-project/vllm |
| **密钥要求** | 可选（通过 `--api-key` 参数设置） |
| **默认端点** | `http://localhost:8000/v1` |

**启动命令：**
```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-2-7b-hf \
  --api-key your-api-key  # 可选
```

---

### LM Studio

| 项目 | 说明 |
|------|------|
| **官网** | https://lmstudio.ai |
| **密钥要求** | 无 |
| **默认端点** | `http://localhost:1234/v1` |

**使用步骤：**
1. 下载并安装 LM Studio
2. 下载模型（如 Llama、Mistral）
3. 启动本地服务器（Local Server 标签页）
4. 配置 base_url 为 `http://localhost:1234/v1`

---

## 配置示例

### TOML 配置文件

```toml
# OpenAI 示例
[llm]
api_type = "openai"
base_url = "https://api.openai.com/v1"
api_key = "sk-your-openai-key"
model = "gpt-4o"

# Anthropic 示例
[llm]
api_type = "anthropic"
base_url = "https://api.anthropic.com"
api_key = "sk-ant-your-anthropic-key"
model = "claude-3-5-sonnet-20250619"

# DeepSeek 示例
[llm]
api_type = "deepseek"
base_url = "https://api.deepseek.com/v1"
api_key = "sk-your-deepseek-key"
model = "deepseek-chat"

# Ollama 本地示例
[llm]
api_type = "ollama"
base_url = "http://localhost:11434/v1"
api_key = "ollama"  # 任意值
model = "llama3.2"
```

### 环境变量配置

```bash
# OpenAI
export DATA_AI_LLM__API_KEY="sk-your-openai-key"
export DATA_AI_LLM__MODEL="gpt-4o"

# Anthropic
export DATA_AI_LLM__API_KEY="sk-ant-your-anthropic-key"
export DATA_AI_LLM__MODEL="claude-3-5-sonnet-20250619"

# DeepSeek
export DATA_AI_LLM__API_KEY="sk-your-deepseek-key"
export DATA_AI_LLM__MODEL="deepseek-chat"

# Azure OpenAI
export DATA_AI_LLM__API_KEY="your-azure-key"
export DATA_AI_LLM__BASE_URL="https://your-resource.openai.azure.com/"
export DATA_AI_LLM__API_TYPE="azure"
export DATA_AI_LLM__API_VERSION="2024-10-21"

# AWS Bedrock
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"
```

---

## 密钥安全最佳实践

1. **永远不要将密钥提交到代码仓库**
   - 使用 `.gitignore` 排除配置文件
   - 使用环境变量或密钥管理服务

2. **定期轮换密钥**
   - 建议每 90 天更换一次
   - 发现泄露立即撤销

3. **使用最小权限原则**
   - 为不同用途创建不同密钥
   - 限制密钥的模型访问范围

4. **监控使用情况**
   - 定期检查 API 调用日志
   - 设置使用限额和告警

5. **本地开发安全**
   - 使用 `.env` 文件存储密钥
   - 生产环境使用密钥管理服务（如 AWS Secrets Manager、Azure Key Vault）
