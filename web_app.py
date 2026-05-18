"""
DATA-AI - 万能智能助手 Web Interface
完整的系统化架构，包括知识库、技能系统、MCP工具、数据清洗等功能
"""

import asyncio
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import traceback
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiofiles
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Agent framework imports (lazy-loaded to avoid breaking if unavailable)
AGENT_FRAMEWORK_AVAILABLE = False
try:
    from app.agent.toolcall import ToolCallAgent
    from app.config import config as app_config
    from app.llm import LLM
    from app.prompt.data import SYSTEM_PROMPT as DATA_SYSTEM_PROMPT
    from app.schema import AgentState, Memory, Message, ToolChoice
    from app.tool import (
        PythonExecute,
        StrReplaceEditor,
        Terminate,
        ToolCollection,
        WebSearch,
    )

    AGENT_FRAMEWORK_AVAILABLE = True
except Exception as e:
    print(f"[Agent Framework] Import failed, will use fallback: {e}")

try:
    from openai import AsyncOpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# RAG module import
from app.rag import TFIDFRetriever, retriever

app = FastAPI(
    title="DATA-AI - 万能智能助手",
    description="完整的系统化智能助手：知识库、技能系统、MCP工具、数据清洗",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge_bases"
SKILLS_DIR = DATA_DIR / "skills"
MCP_CONFIG_FILE = CONFIG_DIR / "mcp.json"
SETTINGS_FILE = CONFIG_DIR / "web_config.json"

for dir_path in [CONFIG_DIR, DATA_DIR, KNOWLEDGE_DIR, SKILLS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


# ==================== 安全中间件 ====================

# --- 简易 Token 认证 ---
AUTH_TOKEN_FILE = CONFIG_DIR / "auth_token.txt"
_auth_token: Optional[str] = None


def _get_auth_token() -> Optional[str]:
    """获取认证 token（首次启动自动生成）"""
    global _auth_token
    if _auth_token is not None:
        return _auth_token
    if AUTH_TOKEN_FILE.exists():
        _auth_token = AUTH_TOKEN_FILE.read_text().strip()
    else:
        _auth_token = hashlib.sha256(os.urandom(32)).hexdigest()[:24]
        AUTH_TOKEN_FILE.write_text(_auth_token)
        print(f"[Auth] 首次启动，已生成访问令牌: {_auth_token}")
        print(f"[Auth] 令牌已保存到: {AUTH_TOKEN_FILE}")
    return _auth_token


def verify_token(request: Request) -> bool:
    """验证请求中的认证 token"""
    token = request.headers.get("X-Auth-Token", "") or request.query_params.get("token", "")
    expected = _get_auth_token()
    if not expected:
        return True
    return token == expected


# --- 速率限制器 ---
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)
_RATE_LIMIT_MAX_CLIENTS = 10000  # Max tracked clients to prevent unbounded growth


def check_rate_limit(client_id: str, max_requests: int = 60, window_seconds: int = 60) -> bool:
    """检查请求频率是否超限"""
    now = time.time()
    cutoff = now - window_seconds
    _rate_limit_store[client_id] = [
        t for t in _rate_limit_store[client_id] if t > cutoff
    ]
    if len(_rate_limit_store[client_id]) >= max_requests:
        return False
    _rate_limit_store[client_id].append(now)
    # Prevent unbounded growth: remove oldest clients if too many
    if len(_rate_limit_store) > _RATE_LIMIT_MAX_CLIENTS:
        oldest_clients = sorted(_rate_limit_store.keys(),
                                key=lambda k: max(_rate_limit_store[k]) if _rate_limit_store[k] else 0)
        for k in oldest_clients[:len(_rate_limit_store) - _RATE_LIMIT_MAX_CLIENTS]:
            del _rate_limit_store[k]
    return True


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """安全中间件：认证 + 速率限制"""
    path = request.url.path

    # 豁免路径
    skip_paths = {"/", "/favicon.ico", "/docs", "/openapi.json", "/health"}
    if path.startswith("/static") or path.startswith("/share") or path in skip_paths:
        return await call_next(request)

    # 认证检查（可选，通过环境变量启用）
    if os.environ.get("DATA_AI_AUTH_ENABLED", "false").lower() == "true":
        if not verify_token(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "未授权访问，请提供有效的认证令牌"},
            )

    # 速率限制
    client_id = request.client.host if request.client else "unknown"
    if path == "/ws":
        if not check_rate_limit(client_id, max_requests=10, window_seconds=60):
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁"})
    elif path.startswith("/api/model/test") or path.startswith("/api/sandbox"):
        if not check_rate_limit(client_id, max_requests=10, window_seconds=60):
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁"})
    else:
        if not check_rate_limit(client_id, max_requests=120, window_seconds=60):
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁"})

    response = await call_next(request)
    return response

# ==================== 配置 ====================


class Settings(BaseModel):
    llm: Dict[str, Any] = Field(
        default_factory=lambda: {
            "provider": "aliyun",
            "model": "qwen-plus-latest",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "",
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 0.9,
            "stream": False,
        }
    )
    sandbox: Dict[str, Any] = Field(
        default_factory=lambda: {"enabled": True, "timeout": 60, "allow_network": False}
    )
    knowledge_base: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": True,
            "vector_db": "sqlite",
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "embedding_model": "text-embedding-v3",
        }
    )
    conversation: Dict[str, Any] = Field(
        default_factory=lambda: {
            "history_enabled": True,
            "max_history": 50,
            "auto_title": True,
        }
    )
    display: Dict[str, Any] = Field(
        default_factory=lambda: {
            "theme": "dark",
            "thinking_chain": True,
            "code_highlight": True,
            "markdown_render": True,
        }
    )
    agent: Dict[str, Any] = Field(
        default_factory=lambda: {
            "max_steps": 5,
            "auto_mode": True,
            "reasoning_mode": "auto",
        }
    )
    langsmith: Dict[str, Any] = Field(
        default_factory=lambda: {
            "enabled": False,
            "api_key": "",
            "project": "dataagent",
            "endpoint": "https://api.smith.langchain.com",
        }
    )
    system_prompt: str = ""  # 自定义系统提示词，留空使用默认


class KnowledgeBase(BaseModel):
    id: str
    name: str
    description: str = ""
    created_at: str
    updated_at: str
    embedding_model: str = "text-embedding-v3"
    indexing_technique: str = "high_quality"
    permission: str = "only_me"


class Document(BaseModel):
    id: str
    knowledge_base_id: str
    name: str
    data_source_type: str
    status: str
    file_path: str
    created_at: str
    content: Optional[str] = None
    error: Optional[str] = None


class ProcessingRule(BaseModel):
    mode: str = "automatic"
    rules: Dict[str, Any] = Field(
        default_factory=lambda: {
            "pre_processing_rules": [
                {"id": "remove_extra_spaces", "enabled": True},
                {"id": "remove_urls_emails", "enabled": False},
            ],
            "segmentation": {
                "separator": "\n\n",
                "max_tokens": 1000,
                "chunk_size": 1000,
                "chunk_overlap": 200,
            },
        }
    )


class Skill(BaseModel):
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    category: str = "custom"
    type: str = "custom"
    icon: str = "⚡"
    status: str = "published"
    enabled: bool = True
    created_at: str
    updated_at: str
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    prompts: Dict[str, Any] = Field(default_factory=dict)
    tools: List[Dict[str, Any]] = Field(default_factory=list)


class MCPServer(BaseModel):
    id: str
    name: str
    type: str
    command: str = ""
    args: List[str] = Field(default_factory=list)
    url: str = ""
    env: Dict[str, str] = Field(default_factory=dict)
    status: str = "inactive"
    enabled: bool = True
    icon: str = "🔌"


current_settings: Settings = Settings()
knowledge_bases: Dict[str, KnowledgeBase] = {}
documents: Dict[str, Document] = {}
skills: Dict[str, Skill] = {}
mcp_servers: Dict[str, MCPServer] = {}
# 持久化存储（SQLite）
from app.storage import (
    create_conversation as db_create_conversation,
    get_conversation as db_get_conversation,
    list_conversations as db_list_conversations,
    update_conversation_title as db_update_conversation_title,
    delete_conversation as db_delete_conversation,
    add_message as db_add_message,
    get_conversation_messages as db_get_conversation_messages,
    add_feedback as db_add_feedback,
    get_feedback_stats as db_get_feedback_stats,
    set_preference as db_set_preference,
    get_preference as db_get_preference,
    init_db as db_init,
    migrate_from_memory as db_migrate_from_memory,
)

# 对话数据已迁移到 SQLite 持久化存储（app/storage.py）


def load_settings():
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Settings(**data)
        except Exception as e:
            print(f"Error loading settings: {e}")
    return Settings()


def save_settings(settings: Settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, ensure_ascii=False, indent=2)


current_settings = load_settings()


def load_knowledge_bases():
    index_file = KNOWLEDGE_DIR / "index.json"
    if index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for kb_id, kb_data in data.items():
                    knowledge_bases[kb_id] = KnowledgeBase(**kb_data)
        except Exception as e:
            print(f"Error loading knowledge bases: {e}")


def save_knowledge_bases():
    index_file = KNOWLEDGE_DIR / "index.json"
    data = {kb_id: kb.model_dump() for kb_id, kb in knowledge_bases.items()}
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_skills():
    index_file = SKILLS_DIR / "index.json"
    if index_file.exists():
        try:
            with open(index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for skill_id, skill_data in data.items():
                    skills[skill_id] = Skill(**skill_data)
        except Exception as e:
            print(f"Error loading skills: {e}")
    if not skills:
        init_builtin_skills()


def save_skills():
    index_file = SKILLS_DIR / "index.json"
    data = {skill_id: skill.model_dump() for skill_id, skill in skills.items()}
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_builtin_skills():
    now = datetime.datetime.now().isoformat()
    builtin = [
        Skill(
            id="code_reviewer",
            name="代码审查专家",
            description="智能代码审查，发现潜在问题并提供优化建议",
            version="1.0.0",
            author="DATA-AI Team",
            category="code_generation",
            type="built_in",
            icon="🔍",
            created_at=now,
            updated_at=now,
            parameters=[
                {
                    "name": "code",
                    "type": "string",
                    "description": "待审查的代码",
                    "required": True,
                },
                {
                    "name": "language",
                    "type": "string",
                    "description": "编程语言",
                    "required": False,
                    "enum": ["python", "javascript", "typescript"],
                },
            ],
            prompts={
                "system_prompt": "你是一位资深的代码审查专家，请按照以下标准审查代码：\n1. 检查语法错误和潜在bug\n2. 评估代码风格和最佳实践\n3. 提供性能优化建议\n4. 指出安全隐患"
            },
        ),
        Skill(
            id="data_analyzer",
            name="数据分析助手",
            description="执行数据分析和可视化",
            version="1.0.0",
            author="DATA-AI Team",
            category="data_analysis",
            type="built_in",
            icon="📊",
            created_at=now,
            updated_at=now,
            parameters=[
                {
                    "name": "data",
                    "type": "string",
                    "description": "数据",
                    "required": True,
                },
                {
                    "name": "analysis_type",
                    "type": "string",
                    "description": "分析类型",
                    "required": True,
                    "enum": ["summary", "statistics", "visualization"],
                },
            ],
        ),
        Skill(
            id="document_processor",
            name="文档处理助手",
            description="提取、总结和分析文档内容",
            version="1.0.0",
            author="DATA-AI Team",
            category="document_processing",
            type="built_in",
            icon="📄",
            created_at=now,
            updated_at=now,
            parameters=[
                {
                    "name": "content",
                    "type": "string",
                    "description": "文档内容",
                    "required": True,
                },
                {
                    "name": "task",
                    "type": "string",
                    "description": "任务类型",
                    "required": True,
                    "enum": ["summary", "key_points", "translation"],
                },
            ],
        ),
        Skill(
            id="meeting_summarizer",
            name="会议纪要专家",
            description="分析会议记录，提取要点、行动项和决策事项",
            version="1.0.0",
            author="DATA-AI Team",
            category="document_processing",
            type="built_in",
            icon="📋",
            created_at=now,
            updated_at=now,
            parameters=[
                {
                    "name": "meeting_content",
                    "type": "string",
                    "description": "会议记录内容",
                    "required": True,
                },
                {
                    "name": "output_format",
                    "type": "string",
                    "description": "输出格式",
                    "required": False,
                    "enum": ["full", "action_items", "summary"],
                },
            ],
            prompts={
                "system_prompt": "你是一位专业的会议纪要分析师，擅长从会议记录中提取关键信息。请按照以下结构化格式输出会议纪要：\n\n### 📋 会议基本信息\n- **会议主题**: [会议主题]\n- **时间**: [会议时间]\n- **参会人员**: [参会人员列表]\n\n### 📝 讨论要点\n1. [要点1]\n2. [要点2]\n\n### ✅ 行动项\n| 任务 | 负责人 | 截止日期 |\n|------|--------|----------|\n| [任务描述] | [负责人] | [日期] |\n\n### 🎯 决策事项\n- [决策1]\n\n### ❓ 待解决问题\n- [问题1]",
                "user_prompt_template": "请分析以下会议记录并生成结构化的会议纪要：\n\n---\n{{meeting_content}}\n---\n\n输出格式: {{output_format}}",
                "examples": [
                    {
                        "input": "会议主题：项目进度审查\n时间：2024年1月15日\n参会人员：张三、李四、王五\n讨论内容：\n1. 张三报告了前端开发进度\n2. 李四提出了后端接口问题\n3. 决定下周进行测试\n行动项：\n- 张三：完成用户模块开发（1月20日前）\n- 李四：修复API接口问题（1月18日前）",
                        "output": "### 📋 会议基本信息\n- **会议主题**: 项目进度审查\n- **时间**: 2024年1月15日\n- **参会人员**: 张三、李四、王五\n\n### 📝 讨论要点\n1. 张三报告了前端开发进度\n2. 李四提出了后端接口问题\n3. 决定下周进行测试\n\n### ✅ 行动项\n| 任务 | 负责人 | 截止日期 |\n|------|--------|----------|\n| 完成用户模块开发 | 张三 | 1月20日 |\n| 修复API接口问题 | 李四 | 1月18日 |",
                    }
                ],
            },
        ),
        Skill(
            id="literature_summarizer",
            name="文献摘要专家",
            description="分析学术文献，提取研究目的、方法、结果和结论",
            version="1.0.0",
            author="DATA-AI Team",
            category="document_processing",
            type="built_in",
            icon="📚",
            created_at=now,
            updated_at=now,
            parameters=[
                {
                    "name": "literature_content",
                    "type": "string",
                    "description": "文献内容",
                    "required": True,
                },
                {
                    "name": "extract_type",
                    "type": "string",
                    "description": "提取类型",
                    "required": False,
                    "enum": ["full", "findings", "methods"],
                },
            ],
            prompts={
                "system_prompt": "你是一位专业的学术文献分析专家，擅长从学术论文和研究报告中提取关键信息。请按照以下结构化格式输出文献摘要：\n\n### 📚 文献信息\n- **标题**: [文献标题]\n- **作者**: [作者列表]\n- **发表期刊/会议**: [期刊/会议名称]\n\n### 🎯 研究目的\n[作者的研究动机和目标]\n\n### 🔬 研究方法\n[研究采用的方法、实验设计、数据分析方法]\n\n### 📊 主要结果\n- [结果1]\n- [结果2]\n\n### 💡 核心结论\n[研究得出的主要结论和发现]\n\n### 🔍 研究亮点\n- [创新点和贡献]",
                "user_prompt_template": "请分析以下学术文献并生成结构化的摘要：\n\n---\n{{literature_content}}\n---\n\n提取类型: {{extract_type}}",
                "examples": [
                    {
                        "input": "论文标题：深度学习在图像分类中的应用研究\n作者：李明, 王华\n期刊：计算机学报, 2024\n摘要：本研究提出了一种基于Transformer架构的图像分类方法。通过在ImageNet数据集上的实验，证明了该方法在分类准确率上优于传统方法15%。",
                        "output": "### 📚 文献信息\n- **标题**: 深度学习在图像分类中的应用研究\n- **作者**: 李明, 王华\n- **发表期刊/会议**: 计算机学报\n\n### 🎯 研究目的\n探索深度学习方法在图像分类任务中的应用\n\n### 🔬 研究方法\n基于Transformer架构的图像分类方法\n\n### 📊 主要结果\n- 在ImageNet数据集上进行实验\n- 分类准确率优于传统方法15%\n\n### 💡 核心结论\nTransformer架构在图像分类任务中具有显著优势",
                    }
                ],
            },
        ),
        Skill(
            id="translation_expert",
            name="多语言翻译专家",
            description="支持多种语言互译，提供专业术语处理和文本润色",
            version="1.0.0",
            author="DATA-AI Team",
            category="custom",
            type="built_in",
            icon="🌐",
            created_at=now,
            updated_at=now,
            parameters=[
                {
                    "name": "text",
                    "type": "string",
                    "description": "待翻译文本",
                    "required": True,
                },
                {
                    "name": "source_lang",
                    "type": "string",
                    "description": "源语言",
                    "required": False,
                    "default": "auto",
                },
                {
                    "name": "target_lang",
                    "type": "string",
                    "description": "目标语言",
                    "required": True,
                },
                {
                    "name": "domain",
                    "type": "string",
                    "description": "专业领域",
                    "required": False,
                    "enum": ["general", "technical", "medical", "legal", "business"],
                },
                {
                    "name": "polish",
                    "type": "boolean",
                    "description": "是否润色",
                    "required": False,
                    "default": false,
                },
            ],
            prompts={
                "system_prompt": "你是一位专业的多语言翻译专家，精通多种语言互译和文本润色。\n\n## 翻译规则\n1. **准确性**: 确保翻译准确传达原意\n2. **完整性**: 不遗漏任何重要信息\n3. **丰富性**: 提供必要的背景解释\n4. **回复话术自然**: 使用自然流畅的语言\n\n## 文本润色规则\n1. **语法修正**: 纠正语法错误和拼写错误\n2. **表达优化**: 提升句子表达质量\n3. **风格统一**: 保持整体风格一致\n4. **专业术语**: 正确使用专业术语\n\n支持语言：中文、英语、日语、韩语、法语、德语、西班牙语、葡萄牙语、俄语、阿拉伯语",
                "user_prompt_template": "请将以下文本从{{source_lang}}翻译成{{target_lang}}：\n\n---\n{{text}}\n---\n\n领域：{{domain}}\n润色：{{polish}}\n\n请提供准确、完整的翻译，并根据需要进行润色。",
                "examples": [
                    {
                        "input": "text: Hello world, this is a test. source_lang: English target_lang: Chinese",
                        "output": "你好世界，这是一个测试。",
                    },
                    {
                        "input": "text: 人工智能正在改变世界。 source_lang: Chinese target_lang: English domain: technical",
                        "output": "Artificial intelligence is transforming the world.",
                    },
                ],
            },
        ),
        Skill(
            id="presentation_generator",
            name="PPT生成专家",
            description="根据主题创建演示文稿大纲，包含内容组织和视觉建议",
            version="1.0.0",
            author="DATA-AI Team",
            category="custom",
            type="built_in",
            icon="🎤",
            created_at=now,
            updated_at=now,
            parameters=[
                {
                    "name": "topic",
                    "type": "string",
                    "description": "演示文稿主题",
                    "required": True,
                },
                {
                    "name": "audience",
                    "type": "string",
                    "description": "目标受众",
                    "required": False,
                    "default": "general",
                },
                {
                    "name": "duration",
                    "type": "integer",
                    "description": "时长（分钟）",
                    "required": False,
                    "default": 15,
                },
                {
                    "name": "style",
                    "type": "string",
                    "description": "风格",
                    "required": False,
                    "enum": ["professional", "creative", "academic", "technical"],
                },
            ],
            prompts={
                "system_prompt": "你是一位专业的演示文稿专家，擅长创建高质量的PPT内容和结构。\n\n## 演示文稿结构\n1. **封面页**: 标题、副标题、演讲者信息\n2. **目录页**: 内容大纲\n3. **内容页**: 详细内容展示\n4. **总结页**: 核心要点回顾\n5. **Q&A页**: 问答环节\n\n## 视觉建议\n- 📊 数据图表\n- 🖼️ 图片/插图\n- 📈 趋势图\n- 📋 列表/表格\n- 🎯 流程图/架构图\n\n## 注意事项\n1. 保持每页内容简洁，避免过多文字\n2. 使用清晰的标题和层级结构\n3. 合理使用视觉元素增强表达\n4. 确保逻辑连贯，重点突出",
                "user_prompt_template": "请为以下主题创建一份完整的演示文稿大纲：\n\n**主题**: {{topic}}\n\n**要求**:\n- 目标受众: {{audience}}\n- 时长: {{duration}} 分钟\n- 风格: {{style}}\n\n请提供详细的幻灯片结构和内容建议。",
                "examples": [
                    {
                        "input": "topic: 人工智能简介 audience: 大学生 duration: 10 style: academic",
                        "output": "## 📊 演示文稿大纲\n\n### 1. 封面页\n**标题**: 人工智能简介\n**副标题**: 从基础到应用\n\n### 2. 目录页\n- 什么是人工智能\n- AI的发展历程\n- AI的核心技术\n- AI的应用领域\n\n### 3. 内容页\n**幻灯片3**: 什么是人工智能\n- 定义和概念\n- 核心目标\n\n**幻灯片4**: AI的发展历程\n- 早期阶段\n- 深度学习革命\n- 当前发展\n\n**幻灯片5**: AI的核心技术\n- 机器学习\n- 深度学习\n- 自然语言处理\n\n**幻灯片6**: AI的应用领域\n- 医疗健康\n- 自动驾驶\n- 金融科技\n\n### 4. 总结页\n**核心要点**:\n- AI是模拟人类智能的技术\n- 深度学习推动了AI的快速发展\n- AI应用广泛，前景广阔",
                    }
                ],
            },
        ),
    ]
    for skill in builtin:
        skills[skill.id] = skill
    save_skills()


def load_mcp_servers():
    if MCP_CONFIG_FILE.exists():
        try:
            with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "mcpServers" in data:
                    for server_id, server_data in data["mcpServers"].items():
                        mcp_servers[server_id] = MCPServer(
                            id=server_id,
                            name=server_data.get("name", server_id),
                            type=server_data.get("type", "stdio"),
                            command=server_data.get("command", ""),
                            args=server_data.get("args", []),
                            url=server_data.get("url", ""),
                            env=server_data.get("env", {}),
                            enabled=server_data.get("enabled", True),
                            icon="🔌",
                        )
        except Exception as e:
            print(f"Error loading MCP servers: {e}")


def save_mcp_servers():
    data = {
        "mcpServers": {
            server_id: {
                "type": server.type,
                "command": server.command,
                "args": server.args,
                "url": server.url,
                "env": server.env,
                "enabled": server.enabled,
            }
            for server_id, server in mcp_servers.items()
        }
    }
    with open(MCP_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


load_knowledge_bases()
load_skills()
load_mcp_servers()


async def execute_python(code: str, timeout: int = 30) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="dataagent_")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
            env={**os.environ, "MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8"},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "success": True,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
            "returncode": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"success": False, "error": "执行超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


async def call_llm(prompt: str, settings: Settings) -> str:
    if not OPENAI_AVAILABLE:
        return "错误: 未安装 openai 库，请运行 pip install openai"
    if not settings.llm.get("api_key"):
        return "请先在设置中配置 API Key"
    try:
        client = AsyncOpenAI(
            api_key=settings.llm["api_key"], base_url=settings.llm["base_url"]
        )
        response = await client.chat.completions.create(
            model=settings.llm["model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=settings.llm.get("max_tokens", 4096),
            temperature=settings.llm.get("temperature", 0.7),
            top_p=settings.llm.get("top_p", 0.9),
        )
        if not response.choices:
            return "模型返回了空响应"
        return response.choices[0].message.content
    except Exception as e:
        error_msg = str(e)
        print(f"[LLM调用失败] {error_msg}")
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            return "❌ API Key无效，请检查配置"
        elif "403" in error_msg or "forbidden" in error_msg.lower():
            return "❌ API权限不足或余额不足"
        elif "429" in error_msg:
            return "❌ 请求过于频繁，请稍后再试"
        elif "timeout" in error_msg.lower():
            return "❌ 请求超时，请检查网络连接"
        elif "connection" in error_msg.lower():
            return f"❌ 无法连接到API服务，请检查网络和API地址是否正确\n错误: {error_msg[:200]}"
        else:
            return f"❌ LLM调用失败: {error_msg[:300]}"


async def clean_text(text: str, rules: dict) -> str:
    result = text
    pre_rules = rules.get("pre_processing_rules", [])
    for rule in pre_rules:
        if rule.get("enabled"):
            rule_id = rule.get("id")
            if rule_id == "remove_extra_spaces":
                result = re.sub(r"\s+", " ", result).strip()
            elif rule_id == "remove_urls_emails":
                result = re.sub(r"https?://\S+", "", result)
                result = re.sub(r"\S+@\S+", "", result)
    return result


@app.get("/api/settings")
async def get_settings():
    settings_data = current_settings.model_dump()
    # Mask API key for security
    if settings_data.get("llm") and settings_data["llm"].get("api_key"):
        key = settings_data["llm"]["api_key"]
        if key and len(key) > 8:
            settings_data["llm"]["api_key"] = key[:4] + "****" + key[-4:]
        elif key:
            settings_data["llm"]["api_key"] = "****"
    return JSONResponse(settings_data)


@app.post("/api/settings")
async def update_settings(request: Request):
    global current_settings
    try:
        data = await request.json()
        current_settings = Settings(**data)
        save_settings(current_settings)
        return JSONResponse({"success": True, "settings": current_settings.model_dump()})
    except Exception as e:
        return JSONResponse({"success": False, "error": f"设置更新失败: {str(e)}"}, status_code=400)


@app.get("/api/knowledge-bases")
async def list_knowledge_bases():
    result = []
    for kb in knowledge_bases.values():
        kb_data = kb.model_dump()
        # 计算文档数量
        doc_count = sum(
            1 for doc in documents.values() if doc.knowledge_base_id == kb.id
        )
        kb_data["document_count"] = doc_count
        result.append(kb_data)
    return JSONResponse(result)


@app.post("/api/knowledge-bases")
async def create_knowledge_base(request: Request):
    data = await request.json()
    kb_id = str(uuid.uuid4())
    now = datetime.datetime.now().isoformat()
    kb = KnowledgeBase(
        id=kb_id,
        name=data.get("name", "未命名知识库"),
        description=data.get("description", ""),
        created_at=now,
        updated_at=now,
        embedding_model=data.get("embedding_model", "text-embedding-v3"),
        indexing_technique=data.get("indexing_technique", "high_quality"),
    )
    knowledge_bases[kb_id] = kb
    save_knowledge_bases()
    (KNOWLEDGE_DIR / kb_id).mkdir(exist_ok=True)
    return JSONResponse(kb.model_dump())


@app.get("/api/knowledge-bases/rag/stats")
async def get_rag_stats():
    """获取 RAG 检索库统计信息"""
    return JSONResponse(retriever.get_stats())


@app.get("/api/knowledge-bases/{kb_id}")
async def get_knowledge_base(kb_id: str):
    if kb_id not in knowledge_bases:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return JSONResponse(knowledge_bases[kb_id].model_dump())


@app.post("/api/upload")
async def general_upload(file: UploadFile = File(...)):
    """通用文件上传端点（兼容 Dropzone 默认 URL）"""
    allowed_extensions = {
        ".pdf", ".txt", ".md", ".docx", ".csv", ".xlsx", ".xls", ".ppt", ".pptx",
    }
    max_size = 50 * 1024 * 1024  # 50MB

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}",
        )

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大: {size / 1024 / 1024:.2f}MB。最大支持 {max_size / 1024 / 1024}MB",
        )

    upload_dir = DATA_DIR / "uploads" / "general"
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    file_path = upload_dir / f"{doc_id}{file_ext}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return JSONResponse({
            "success": True,
            "id": doc_id,
            "filename": file.filename,
            "file_path": str(file_path),
            "size": size,
            "message": "文件上传成功",
        })
    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@app.post("/api/knowledge-bases/{kb_id}/documents")
async def upload_document(kb_id: str, file: UploadFile = File(...)):
    if kb_id not in knowledge_bases:
        raise HTTPException(status_code=404, detail="知识库不存在")

    allowed_extensions = {
        ".pdf",
        ".txt",
        ".md",
        ".docx",
        ".csv",
        ".xlsx",
        ".xls",
        ".ppt",
        ".pptx",
    }
    max_size = 50 * 1024 * 1024  # 50MB

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}",
        )

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大: {size / 1024 / 1024:.2f}MB。最大支持 {max_size / 1024 / 1024}MB",
        )

    upload_dir = DATA_DIR / "uploads" / kb_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    doc_id = str(uuid.uuid4())
    file_path = upload_dir / f"{doc_id}{file_ext}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        now = datetime.datetime.now().isoformat()
        doc = Document(
            id=doc_id,
            knowledge_base_id=kb_id,
            name=file.filename or "文档",
            data_source_type="upload",
            status="processing",
            file_path=str(file_path),
            created_at=now,
        )
        documents[doc_id] = doc

        asyncio.create_task(process_document(doc_id, file_path, file_ext))

        return JSONResponse(
            {**doc.model_dump(), "message": f"文件上传成功，正在处理..."}
        )

    except Exception as e:
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


async def process_document(doc_id: str, file_path: Path, file_ext: str):
    try:
        content = ""

        if file_ext == ".txt" or file_ext == ".md":
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()

        elif file_ext == ".csv":
            import pandas as pd

            df = await asyncio.to_thread(pd.read_csv, file_path)
            content = df.to_string()

        if doc_id in documents:
            documents[doc_id].status = "available"
            documents[doc_id].content = (
                content[:10000] if len(content) > 10000 else content
            )

            # 将文档内容添加到 RAG 检索器
            if content.strip():
                kb_id = documents[doc_id].knowledge_base_id
                doc_name = documents[doc_id].name
                try:
                    retriever.add_document(
                        doc_id=doc_id,
                        content=content,
                        metadata={"name": doc_name, "kb_id": kb_id},
                    )
                    print(
                        f"[RAG] 文档 {doc_name} ({doc_id}) 已添加到检索库，共 {len(retriever.documents.get(doc_id, []))} 个片段"
                    )
                except Exception as rag_err:
                    print(f"[RAG] 添加文档到检索库失败: {rag_err}")

    except Exception as e:
        if doc_id in documents:
            documents[doc_id].status = "failed"
            documents[doc_id].error = str(e)


@app.get("/api/knowledge-bases/{kb_id}/documents")
async def list_documents(kb_id: str):
    if kb_id not in knowledge_bases:
        raise HTTPException(status_code=404, detail="知识库不存在")
    kb_docs = [
        doc.model_dump() for doc in documents.values() if doc.knowledge_base_id == kb_id
    ]
    return JSONResponse(kb_docs)


@app.post("/api/knowledge-bases/search")
async def search_knowledge_base(request: Request):
    """搜索知识库 - 使用 RAG 语义检索"""
    data = await request.json()
    query = data.get("query", "")
    top_k = data.get("top_k", 5)
    min_score = data.get("min_score", 0.1)

    if not query.strip():
        return JSONResponse([])

    results = retriever.search(query, top_k=top_k, min_score=min_score)
    return JSONResponse(results)





@app.get("/api/skills")
async def list_skills():
    return JSONResponse([skill.model_dump() for skill in skills.values()])


@app.post("/api/skills/generate")
async def generate_skill(request: Request):
    data = await request.json()
    purpose = data.get("purpose", "")

    if not purpose:
        raise HTTPException(status_code=400, detail="请提供技能用途描述")

    if not current_settings.llm.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在设置中配置API Key")

    try:
        client = AsyncOpenAI(
            api_key=current_settings.llm["api_key"],
            base_url=current_settings.llm.get("base_url", "https://api.openai.com/v1"),
        )

        prompt = f"""基于以下需求，生成一个AI技能的建议：

需求：{purpose}

请生成一个JSON对象，包含以下字段：
- name: 技能名称（中文，不超过30字）
- icon: 表情符号图标（一个emoji）
- description: 详细描述（中文，100字以内）
- category: 分类（代码/数据/文档/翻译/写作/学习/创意/其他）

只返回JSON，不要其他内容。"""

        response = await client.chat.completions.create(
            model=current_settings.llm.get("model", "gpt-4o"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7,
        )

        if not response.choices:
            raise HTTPException(status_code=500, detail="模型返回了空响应")
        result_text = response.choices[0].message.content.strip()

        json_match = re.search(r"\{.*\}", result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return JSONResponse(result)
        else:
            raise HTTPException(status_code=500, detail="AI返回格式错误")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI生成失败: {str(e)}")


@app.post("/api/skills")
async def create_skill(request: Request):
    try:
        data = await request.json()
        skill_id = data.get("id", str(uuid.uuid4()))
        now = datetime.datetime.now().isoformat()
        skill = Skill(
            id=skill_id,
            name=data.get("name", "未命名技能"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            category=data.get("category", "custom"),
            type=data.get("type", "custom"),
            icon=data.get("icon", "⚡"),
            created_at=now,
            updated_at=now,
            parameters=data.get("parameters", []),
            prompts=data.get("prompts", {}),
            tools=data.get("tools", []),
        )
        skills[skill_id] = skill
        save_skills()
        return JSONResponse(skill.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建技能失败: {str(e)}")


@app.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="技能不存在")
    return JSONResponse(skills[skill_id].model_dump())


@app.post("/api/skills/{skill_id}/use")
async def use_skill(skill_id: str, request: Request):
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="技能不存在")
    skill = skills[skill_id]
    data = await request.json()
    params = data.get("parameters", {})
    prompt = ""
    if skill.prompts.get("system_prompt"):
        prompt += skill.prompts["system_prompt"] + "\n\n"
    template = skill.prompts.get("user_prompt_template", "{{input}}")
    user_input = params.get("input", str(params))
    prompt += template.replace("{{input}}", user_input)
    for key, value in params.items():
        prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
    response = await call_llm(prompt, current_settings)
    return JSONResponse({"response": response, "skill": skill.name})


@app.get("/api/mcp/servers")
async def list_mcp_servers():
    return JSONResponse([server.model_dump() for server in mcp_servers.values()])


@app.post("/api/mcp/servers")
async def create_mcp_server(request: Request):
    try:
        data = await request.json()
        server_id = data.get("id", str(uuid.uuid4()))
        server = MCPServer(
            id=server_id,
            name=data.get("name", "未命名服务器"),
            type=data.get("type", "stdio"),
            command=data.get("command", ""),
            args=data.get("args", []),
            url=data.get("url", ""),
            env=data.get("env", {}),
            enabled=data.get("enabled", True),
            icon=data.get("icon", "🔌"),
        )
        mcp_servers[server_id] = server
        save_mcp_servers()
        return JSONResponse(server.model_dump())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建MCP服务器失败: {str(e)}")


@app.get("/api/schema/{schema_type}")
async def get_schema(schema_type: str):
    if not re.match(r'^[a-zA-Z0-9_]+$', schema_type):
        raise HTTPException(status_code=400, detail="无效的schema类型名称")
    schema_file = CONFIG_DIR / "schema" / f"{schema_type}_schema.json"
    if not schema_file.exists():
        raise HTTPException(status_code=404, detail="Schema不存在")
    with open(schema_file, "r", encoding="utf-8") as f:
        return JSONResponse(json.load(f))


# ==================== Sandbox Environment API ====================


class SandboxEnvironment(BaseModel):
    name: str
    image: str
    tag: str
    size: int = 0
    status: str = "installed"
    created_at: str = ""


async def get_docker_images():
    try:
        import docker

        def _list_images():
            client = docker.from_env()
            try:
                images = client.images.list()
                result = []
                for img in images:
                    tags = img.tags
                    if tags:
                        full_tag = tags[0]
                        parts = full_tag.split(":")
                        name = parts[0] if len(parts) > 0 else "unknown"
                        tag = parts[1] if len(parts) > 1 else "latest"
                        result.append(
                            {
                                "name": name,
                                "image": full_tag,
                                "tag": tag,
                                "size": img.attrs.get("Size", 0),
                                "status": "installed",
                                "created_at": img.attrs.get("Created", ""),
                            }
                        )
                return result
            finally:
                client.close()
        return await asyncio.to_thread(_list_images)
    except Exception as e:
        print(f"Error getting docker images: {e}")
        return []


async def pull_docker_image(image_name: str):
    try:
        import docker

        def _pull_image():
            client = docker.from_env()
            try:
                client.images.pull(image_name)
                img = client.images.get(image_name)
                parts = image_name.split(":")
                return {
                    "success": True,
                    "error": "",
                    "name": parts[0] if len(parts) > 0 else image_name,
                    "tag": parts[1] if len(parts) > 1 else "latest",
                    "size": img.attrs.get("Size", 0),
                }
            except Exception as e:
                return {"success": False, "error": str(e), "name": image_name}
            finally:
                client.close()

        return await asyncio.to_thread(_pull_image)
    except Exception as e:
        return {"success": False, "error": str(e), "name": image_name}


async def remove_docker_image(image_name: str):
    try:
        import docker

        def _remove_image():
            client = docker.from_env()
            try:
                client.images.remove(image_name, force=True)
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}
            finally:
                client.close()

        return await asyncio.to_thread(_remove_image)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/sandbox/environments")
async def list_sandbox_environments():
    envs = await get_docker_images()
    return JSONResponse(envs)


@app.post("/api/sandbox/environments/pull")
async def pull_sandbox_environment(request: Request):
    data = await request.json()
    image = data.get("image", "")
    if not image:
        raise HTTPException(status_code=400, detail="请提供镜像名称")

    result = await pull_docker_image(image)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return JSONResponse(
        {
            "success": True,
            "name": result.get("name", image),
            "image": image,
            "tag": result.get("tag", "latest"),
            "size": result.get("size", 0),
        }
    )


@app.delete("/api/sandbox/environments/{image_name}")
async def delete_sandbox_environment(image_name: str):
    result = await remove_docker_image(image_name)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return JSONResponse({"success": True})


@app.post("/api/sandbox/environments/delete")
async def delete_sandbox_environment_post(request: Request):
    """POST版本的删除API"""
    data = await request.json()
    image_name = data.get("image", "")
    if not image_name:
        raise HTTPException(status_code=400, detail="image参数不能为空")
    result = await remove_docker_image(image_name)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    return JSONResponse({"success": True})


# ==================== 对话历史 API ====================


@app.get("/api/conversations")
async def list_conversations():
    """获取所有对话列表"""
    return JSONResponse(db_list_conversations())


@app.get("/api/conversations/search")
async def search_conversations(q: str = ""):
    """搜索对话（标题+消息内容）"""
    if not q:
        return JSONResponse(db_list_conversations())
    from app.storage import search_conversations as db_search
    return JSONResponse(db_search(q))


@app.post("/api/conversations")
async def create_conversation(request: Request):
    """创建新对话"""
    data = await request.json()
    conv_id = data.get("id")
    title = data.get("title", "新对话")
    conv = db_create_conversation(conv_id=conv_id, title=title)
    return JSONResponse(conv)


@app.get("/api/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """获取单个对话详情"""
    conv = db_get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    return JSONResponse(conv)


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """删除对话"""
    db_delete_conversation(conv_id)
    return JSONResponse({"success": True})


@app.delete("/api/conversations/{conv_id}/messages")
async def clear_conversation(conv_id: str):
    """清空对话的所有消息"""
    from app.storage import clear_conversation_messages
    clear_conversation_messages(conv_id)
    return JSONResponse({"success": True})


@app.post("/api/conversations/{conv_id}/messages")
async def add_message(conv_id: str, request: Request):
    """向对话添加消息"""
    data = await request.json()
    role = data.get("role", "user")
    content = data.get("content", "")
    # Validate role
    if role not in ("user", "assistant", "system"):
        raise HTTPException(status_code=400, detail=f"无效的角色: {role}")
    if not content or not isinstance(content, str):
        raise HTTPException(status_code=400, detail="消息内容不能为空")
    if len(content) > 100000:
        raise HTTPException(status_code=400, detail="消息内容过长")
    success = db_add_message(conv_id, role, content)
    if not success:
        raise HTTPException(status_code=404, detail="对话不存在")
    # 自动更新标题（用第一条用户消息）
    if role == "user":
        conv = db_get_conversation(conv_id)
        if conv and conv.get("title") == "新对话":
            db_update_conversation_title(conv_id, content[:20])
    msg = {
        "id": str(uuid.uuid4()),
        "role": role,
        "content": content,
        "timestamp": datetime.datetime.now().isoformat(),
    }
    return JSONResponse(msg)


@app.put("/api/conversations/{conv_id}/title")
async def update_conversation_title(conv_id: str, request: Request):
    """更新对话标题"""
    data = await request.json()
    db_update_conversation_title(conv_id, data.get("title", ""))
    return JSONResponse({"success": True})


# ==================== 用户反馈 ====================


@app.post("/api/feedback")
async def submit_feedback(request: Request):
    """提交用户反馈"""
    data = await request.json()
    feedback_type = data.get("feedback_type", "up")
    if feedback_type not in ("up", "down"):
        raise HTTPException(status_code=400, detail=f"无效的反馈类型: {feedback_type}")
    db_add_feedback(
        message_id=data.get("message_id", ""),
        feedback_type=feedback_type,
        comment=data.get("comment", ""),
        conversation_id=data.get("conversation_id", ""),
    )
    return JSONResponse({"success": True})


@app.get("/api/feedback/stats")
async def feedback_stats():
    """获取反馈统计"""
    return JSONResponse(db_get_feedback_stats())


# ==================== 用户偏好设置 ====================


@app.get("/api/preferences/{key}")
async def get_preference_api(key: str):
    """获取用户偏好设置"""
    value = db_get_preference(key)
    if value is None:
        return JSONResponse({"exists": False, "value": None})
    return JSONResponse({"exists": True, "value": value})


@app.post("/api/preferences/{key}")
async def set_preference_api(key: str, request: Request):
    """设置用户偏好设置"""
    data = await request.json()
    db_set_preference(key, data.get("value", ""))
    return JSONResponse({"success": True})


@app.get("/api/preferences")
async def list_preferences_api():
    """获取所有用户偏好设置（用于前端初始化）"""
    # 常用偏好键
    keys = ["theme", "language", "auto_scroll", "font_size", "sidebar_collapsed"]
    prefs = {}
    for key in keys:
        val = db_get_preference(key)
        if val is not None:
            prefs[key] = val
    return JSONResponse(prefs)


# ==================== 数据备份 ====================

from app.storage import backup_database, export_to_json, import_from_json


@app.post("/api/backup")
async def create_backup():
    """创建数据库备份"""
    try:
        backup_path = backup_database()
        return JSONResponse({
            "success": True,
            "backup_path": str(backup_path.name),
            "message": f"备份已创建: {backup_path.name}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"备份失败: {str(e)}")


@app.get("/api/backup/export")
async def export_data():
    """导出数据为JSON"""
    try:
        export_path = export_to_json()
        return JSONResponse({
            "success": True,
            "export_path": str(export_path.name),
            "message": f"数据已导出: {export_path.name}"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.post("/api/backup/import")
async def import_data(request: Request):
    """从JSON导入数据"""
    try:
        data = await request.json()
        import_path = Path(data.get("path", "")).resolve()
        data_dir_resolved = DATA_DIR.resolve()
        if not str(import_path).startswith(str(data_dir_resolved)):
            raise HTTPException(status_code=400, detail="导入文件路径不在允许的目录范围内")
        if not import_path.exists():
            raise HTTPException(status_code=400, detail="导入文件不存在")
        stats = import_from_json(import_path)
        return JSONResponse({
            "success": True,
            "stats": stats,
            "message": f"导入完成: {stats['conversations']}个对话, {stats['messages']}条消息"
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# ==================== 使用统计 ====================

from app.storage import get_usage_stats


@app.get("/api/stats/usage")
async def usage_stats():
    """获取用户使用统计"""
    return JSONResponse(get_usage_stats())


# ==================== 搜索引擎设置 API ====================

from app.storage import (
    get_search_settings as db_get_search_settings,
    update_search_settings as db_update_search_settings,
    add_custom_search_engine as db_add_custom_search_engine,
    remove_custom_search_engine as db_remove_custom_search_engine,
)


@app.get("/api/search/settings")
async def get_search_settings_api():
    """获取搜索引擎设置"""
    settings = db_get_search_settings()
    # 隐藏敏感的API Key
    if settings.get("api_keys"):
        masked_keys = {}
        for key, value in settings["api_keys"].items():
            if value and len(value) > 8:
                masked_keys[key] = value[:4] + "****" + value[-4:]
            elif value:
                masked_keys[key] = "****"
            else:
                masked_keys[key] = ""
        settings["api_keys_masked"] = masked_keys
    return JSONResponse(settings)


@app.post("/api/search/settings")
async def update_search_settings_api(request: Request):
    """更新搜索引擎设置"""
    data = await request.json()
    # 获取现有设置以保留API Keys（如果未提供）
    existing = db_get_search_settings()
    
    # 如果提供了新的API Keys，更新它们
    new_keys = data.get("api_keys", {})
    if new_keys:
        # 合并现有的keys（保留未提供的）
        merged_keys = existing.get("api_keys", {})
        merged_keys.update(new_keys)
        data["api_keys"] = merged_keys
    
    updated = db_update_search_settings(data)
    return JSONResponse({"success": True, "settings": updated})


@app.post("/api/search/custom-engines")
async def add_custom_engine_api(request: Request):
    """添加自定义搜索引擎"""
    data = await request.json()
    engines = db_add_custom_search_engine(data)
    return JSONResponse({"success": True, "custom_engines": engines})


@app.delete("/api/search/custom-engines/{engine_id}")
async def remove_custom_engine_api(engine_id: str):
    """删除自定义搜索引擎"""
    engines = db_remove_custom_search_engine(engine_id)
    return JSONResponse({"success": True, "custom_engines": engines})


@app.post("/api/search/test")
async def test_search_api(request: Request):
    """测试搜索功能"""
    data = await request.json()
    query = data.get("query", "test")
    engine = data.get("engine", "duckduckgo")
    num_results = data.get("num_results", 3)
    
    try:
        from duckduckgo_search import DDGS
        
        def _do_search():
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")[:200] if r.get("body") else ""
                    })
            return results
        
        results = await asyncio.to_thread(_do_search)
        return JSONResponse({"success": True, "results": results, "engine": engine})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


# ==================== 记忆系统 API ====================

from app.storage import (
    create_memory as db_create_memory,
    get_memory as db_get_memory,
    list_memories as db_list_memories,
    update_memory as db_update_memory,
    delete_memory as db_delete_memory,
    search_memories as db_search_memories,
    get_memory_stats as db_get_memory_stats,
)


@app.get("/api/memories")
async def list_memories_api(type: str = None, key: str = None):
    """获取记忆列表"""
    memories = db_list_memories(memory_type=type, key=key)
    return JSONResponse(memories)


@app.post("/api/memories")
async def create_memory_api(request: Request):
    """创建新记忆"""
    data = await request.json()
    memory = db_create_memory(
        memory_type=data.get("type", "long_term"),
        key=data.get("key"),
        content=data.get("content", ""),
        metadata=data.get("metadata"),
        expires_at=data.get("expires_at")
    )
    return JSONResponse(memory)


@app.get("/api/memories/{memory_id}")
async def get_memory_api(memory_id: str):
    """获取单个记忆"""
    memory = db_get_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return JSONResponse(memory)


@app.put("/api/memories/{memory_id}")
async def update_memory_api(memory_id: str, request: Request):
    """更新记忆"""
    data = await request.json()
    memory = db_update_memory(memory_id, content=data.get("content"), metadata=data.get("metadata"))
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return JSONResponse(memory)


@app.delete("/api/memories/{memory_id}")
async def delete_memory_api(memory_id: str):
    """删除记忆"""
    success = db_delete_memory(memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="记忆不存在")
    return JSONResponse({"success": True})


@app.get("/api/memories/search/{query}")
async def search_memories_api(query: str, type: str = None):
    """搜索记忆"""
    memories = db_search_memories(query, memory_type=type)
    return JSONResponse(memories)


@app.get("/api/memories/stats")
async def memory_stats_api():
    """获取记忆统计"""
    stats = db_get_memory_stats()
    return JSONResponse(stats)


# ==================== 系统日志 API ====================

from app.storage import (
    add_log as db_add_log,
    get_logs as db_get_logs,
    get_log_stats as db_get_log_stats,
    clear_logs as db_clear_logs,
)


@app.get("/api/logs")
async def list_logs_api(
    level: str = None,
    source: str = None,
    conversation_id: str = None,
    limit: int = 100,
    offset: int = 0
):
    """获取日志列表"""
    logs = db_get_logs(
        level=level,
        source=source,
        conversation_id=conversation_id,
        limit=min(limit, 1000),
        offset=offset
    )
    return JSONResponse(logs)


@app.post("/api/logs")
async def add_log_api(request: Request):
    """添加日志"""
    data = await request.json()
    log_id = db_add_log(
        level=data.get("level", "info"),
        source=data.get("source", "frontend"),
        message=data.get("message", ""),
        details=data.get("details"),
        conversation_id=data.get("conversation_id")
    )
    return JSONResponse({"success": True, "id": log_id})


@app.get("/api/logs/stats")
async def log_stats_api():
    """获取日志统计"""
    stats = db_get_log_stats()
    return JSONResponse(stats)


@app.delete("/api/logs")
async def clear_logs_api(before_date: str = None, level: str = None):
    """清理日志"""
    count = db_clear_logs(before_date=before_date, level=level)
    return JSONResponse({"success": True, "deleted": count})


# ==================== 分享功能 ====================

from app.storage import create_share_link, get_shared_conversation


@app.post("/api/conversations/{conv_id}/share")
async def share_conversation(conv_id: str):
    """创建分享链接"""
    result = create_share_link(conv_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return JSONResponse(result)


@app.get("/share/{share_id}")
async def view_shared_conversation(share_id: str):
    """查看分享的对话"""
    conv = get_shared_conversation(share_id)
    if not conv:
        raise HTTPException(status_code=404, detail="分享链接不存在或已过期")
    # 返回分享页面（简化版，实际应渲染 HTML）
    return JSONResponse(conv)


# ==================== 联网搜索 ====================


async def web_search(query: str, num_results: int = 5) -> str:
    """执行联网搜索"""
    try:
        from duckduckgo_search import DDGS

        def _do_search():
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append(f"- {r['title']}: {r['href']}\n  {r['body']}")
            if results:
                return "\n".join(results)
            return "未找到相关结果"

        return await asyncio.to_thread(_do_search)
    except Exception as e:
        return f"搜索失败: {str(e)}"


# ==================== Agent Framework Integration ====================

# Keywords for detecting tool needs
_CODE_KEYWORDS = [
    "代码",
    "python",
    "图表",
    "计算",
    "数据",
    "分析",
    "plot",
    "chart",
    "execute",
    "运行",
    "编程",
    "脚本",
    "函数",
    "算法",
    "统计",
    "可视化",
    "visualization",
    "dataframe",
    "pandas",
    "numpy",
]
_FILE_KEYWORDS = [
    "文件",
    "编辑",
    "读取",
    "写入",
    "创建文件",
    "修改文件",
    "file",
    "edit",
    "read",
    "write",
    "create file",
    "modify",
    "目录",
    "folder",
    "查看文件",
    "view file",
]


def _detect_tool_needs(message: str, options: dict = None) -> dict:
    """
    根据用户消息和选项，检测需要的工具集。
    返回: {"web_search": bool, "code_execution": bool, "file_edit": bool}
    """
    if options is None:
        options = {}
    msg_lower = message.lower()
    return {
        "web_search": options.get("web_search", False),
        "code_execution": options.get("code_execution", False)
        or any(kw in msg_lower for kw in _CODE_KEYWORDS),
        "file_edit": any(kw in msg_lower for kw in _FILE_KEYWORDS),
    }


def _detect_and_apply_skill(message: str) -> "Skill | None":
    """
    根据用户消息检测匹配的技能。
    匹配逻辑：
    1. 检查消息中是否包含技能的关键词
    2. 如果匹配，返回技能对象
    """
    if not skills:
        return None

    msg_lower = message.lower()

    for skill in skills.values():
        if not skill.enabled:
            continue

        # 检查技能关键词
        keywords = []
        for param in skill.parameters:
            if isinstance(param, dict) and param.get("name") == "keywords":
                keywords = param.get("value", [])
                break
        if not isinstance(keywords, list):
            keywords = []

        # 检查技能名称是否在消息中
        if skill.name and skill.name.lower() in msg_lower:
            return skill

        # 检查关键词
        for keyword in keywords:
            if keyword.lower() in msg_lower:
                return skill

    return None


def _build_llm_for_webapp() -> "LLM":
    """
    根据 web_app 的 current_settings 构建 LLM 实例。
    优先使用 Agent 框架的配置，如果 web_settings 有自定义 API key 则覆盖。
    """
    try:
        # 尝试使用 Agent 框架的 LLM 配置
        llm = LLM(config_name="default")
        # 如果 web_settings 有自定义的 API key，创建新的 LLM 实例
        if current_settings.llm.get("api_key"):
            web_api_key = current_settings.llm["api_key"]
            web_base_url = current_settings.llm.get("base_url", "")
            web_model = current_settings.llm.get("model", "")
            # 如果 web_settings 的配置与 Agent 框架不同，需要覆盖
            if (web_api_key and web_api_key != llm.api_key) or (
                web_base_url and web_base_url != llm.base_url
            ):
                from app.config import LLMSettings

                custom_settings = LLMSettings(
                    model=web_model or llm.model,
                    base_url=web_base_url or llm.base_url,
                    api_key=web_api_key,
                    max_tokens=current_settings.llm.get("max_tokens", llm.max_tokens),
                    temperature=current_settings.llm.get(
                        "temperature", llm.temperature
                    ),
                    api_type=llm.api_type,
                    api_version=llm.api_version,
                )
                llm = LLM(llm_config=custom_settings)
        return llm
    except Exception as e:
        print(f"[Agent Framework] Failed to build LLM: {e}")
        raise


async def run_agent_task(
    message: str,
    conversation_id: str = None,
    options: dict = None,
    send_func: Callable = None,
):
    """
    使用 Agent 框架处理用户请求。

    Args:
        message: 用户消息
        conversation_id: 对话ID
        options: 选项 {"web_search": bool, "code_execution": bool}
        send_func: 异步发送函数 send_func(data: dict)
    """
    if options is None:
        options = {}

    async def send(data: dict):
        """安全的发送函数"""
        if send_func:
            try:
                await send_func(data)
            except Exception as e:
                print(f"[WebSocket] Send error: {e}")

    try:
        # 1. 检测需要的工具
        tool_needs = _detect_tool_needs(message, options)

        # 2. 构建工具集
        tools = [Terminate()]
        if tool_needs["web_search"]:
            tools.append(WebSearch())
        if tool_needs["code_execution"]:
            tools.append(PythonExecute())
        if tool_needs["file_edit"]:
            tools.append(StrReplaceEditor())

        tool_collection = ToolCollection(*tools)

        # 3. 构建 LLM 实例
        llm = _build_llm_for_webapp()

        # 4. 检测并应用匹配的技能
        matched_skill = _detect_and_apply_skill(message)
        skill_prompt = ""
        if matched_skill:
            await send(
                {
                    "type": "thinking",
                    "title": "技能匹配",
                    "content": f"匹配到技能: {matched_skill.name}",
                }
            )
            if matched_skill.prompts.get("system_prompt"):
                skill_prompt = matched_skill.prompts["system_prompt"] + "\n\n"

        # 5. 构建系统提示词
        custom_prompt = current_settings.system_prompt if hasattr(current_settings, 'system_prompt') and current_settings.system_prompt else ""
        if custom_prompt and custom_prompt.strip():
            system_prompt = custom_prompt.strip()
        else:
            system_prompt = DATA_SYSTEM_PROMPT.format(directory=str(Path.cwd()))
        if skill_prompt:
            system_prompt = skill_prompt + "\n" + system_prompt

        # 6. RAG 知识库检索 - 如果检索库有文档，自动检索相关内容注入 prompt
        rag_context = ""
        if retriever.doc_vectors:
            rag_results = retriever.search(message, top_k=3, min_score=0.05)
            if rag_results:
                rag_context = "\n\n以下是知识库中检索到的相关参考资料：\n"
                for idx, r in enumerate(rag_results):
                    source_name = r.get("metadata", {}).get("name", "未知文档")
                    rag_context += f"\n--- 参考资料 {idx+1} (来源: {source_name}, 相关度: {r['score']}) ---\n"
                    rag_context += r["content"][:500] + "\n"
                rag_context += "\n请参考以上知识库资料回答用户问题。如果资料中没有相关信息，请基于你的知识回答，并说明信息不在知识库中。"
                await send(
                    {
                        "type": "thinking",
                        "title": "知识库检索",
                        "content": f"从知识库中检索到 {len(rag_results)} 条相关内容",
                    }
                )
                # 发送引用来源给前端显示
                await send({"type": "rag_sources", "sources": rag_results})

        # 将 RAG 上下文注入到用户消息中
        effective_message = message
        if rag_context:
            effective_message = message + rag_context

        # 5. 构建对话历史
        memory = Memory()
        if conversation_id:
            history = db_get_conversation_messages(conversation_id, limit=20)
            for h_msg in history:
                role = h_msg["role"]
                content = h_msg.get("content", "")
                if role == "user":
                    memory.add_message(Message.user_message(content))
                elif role == "assistant":
                    memory.add_message(Message.assistant_message(content))

        # 6. 发送初始状态
        tool_names = [t.name for t in tools]
        await send(
            {
                "type": "step",
                "step": 0,
                "max_steps": 10,
                "thinking": f"正在初始化 Agent，可用工具: {', '.join(tool_names)}",
            }
        )

        # 7. 创建 ToolCallAgent 实例
        agent = ToolCallAgent(
            name="web_agent",
            llm=llm,
            memory=memory,
            system_prompt=system_prompt,
            available_tools=tool_collection,
            max_steps=10,
        )

        # 8. 手动执行 Agent 步骤，以便拦截中间状态
        agent.update_memory("user", effective_message)

        final_response = ""
        max_steps = agent.max_steps

        async with agent.state_context(AgentState.RUNNING):
            while agent.current_step < max_steps and agent.state != AgentState.FINISHED:
                agent.current_step += 1
                step_num = agent.current_step

                # --- Think phase ---
                try:
                    should_act = await agent.think()
                except Exception as think_err:
                    await send(
                        {
                            "type": "thinking",
                            "title": f"Step {step_num}/{max_steps}",
                            "content": f"思考阶段出错: {str(think_err)[:200]}",
                        }
                    )
                    break

                # 获取思考内容（最后一条 assistant 消息）
                thinking_content = ""
                if agent.messages:
                    last_assistant = None
                    for msg in reversed(agent.messages):
                        if msg.role == "assistant":
                            last_assistant = msg
                            break
                    if last_assistant:
                        thinking_content = last_assistant.content or ""

                # 发送步骤信息
                await send(
                    {
                        "type": "step",
                        "step": step_num,
                        "max_steps": max_steps,
                        "thinking": (
                            thinking_content[:500]
                            if thinking_content
                            else f"Step {step_num}: 处理中..."
                        ),
                    }
                )

                if not should_act:
                    # 没有工具调用，收集最终回复
                    if thinking_content:
                        final_response = thinking_content
                    break

                # --- Act phase: 执行工具调用 ---
                tool_calls = agent.tool_calls
                for tc in tool_calls:
                    tool_name = tc.function.name
                    tool_input_str = tc.function.arguments or "{}"
                    try:
                        tool_input = json.loads(tool_input_str)
                    except json.JSONDecodeError:
                        tool_input = {}

                    # 发送工具调用消息
                    await send(
                        {
                            "type": "tool_call",
                            "tool": tool_name,
                            "input": tool_input_str[:2000],
                        }
                    )

                # 执行工具
                try:
                    act_result = await agent.act()

                    # 发送工具结果
                    for tc in tool_calls:
                        tool_name = tc.function.name
                        # 从 act_result 中提取对应工具的结果
                        success = (
                            "Error" not in act_result
                            and "error" not in act_result.lower()[:100]
                        )
                        await send(
                            {
                                "type": "tool_result",
                                "tool": tool_name,
                                "output": act_result[:3000] if act_result else "",
                                "success": success,
                            }
                        )
                except Exception as act_err:
                    await send(
                        {
                            "type": "tool_result",
                            "tool": tool_name if tool_calls else "unknown",
                            "output": f"工具执行错误: {str(act_err)[:500]}",
                            "success": False,
                        }
                    )

                # 检查是否卡住
                if agent.is_stuck():
                    agent.handle_stuck_state()

        # 9. 收集最终回复
        if not final_response:
            # 从 agent 的消息中获取最后的 assistant 回复
            for msg in reversed(agent.messages):
                if msg.role == "assistant" and msg.content and not msg.tool_calls:
                    final_response = msg.content
                    break

        if not final_response:
            final_response = "任务已完成，但没有生成文本回复。"

        # 10. 流式输出最终回复
        await send({"type": "stream_start"})
        chunk_size = 50
        for i in range(0, len(final_response), chunk_size):
            chunk = final_response[i : i + chunk_size]
            await send({"type": "stream_data", "content": chunk})
            await asyncio.sleep(0.03)
        await send({"type": "stream_end"})

        # 11. 保存对话历史
        if conversation_id:
            db_add_message(conversation_id, "user", message)
            db_add_message(conversation_id, "assistant", final_response)
            # 自动更新标题
            conv = db_get_conversation(conversation_id)
            if conv and conv.get("title") == "新对话":
                db_update_conversation_title(conversation_id, message[:20])

        # 12. 清理 Agent 资源
        try:
            await agent.cleanup()
        except Exception:
            pass

    except Exception as e:
        error_detail = str(e)[:500]
        await send({"type": "error", "content": f"Agent 执行失败: {error_detail}"})
        print(f"[Agent Framework] Error in run_agent_task: {traceback.format_exc()}")
        raise  # Re-raise so caller can fallback


# ==================== Legacy Agent (Fallback) ====================


async def run_universal_agent(
    websocket: WebSocket,
    message: str,
    conversation_id: str = None,
    options: dict = None,
):
    """运行通用AI Agent，支持联网搜索和对话历史"""
    if options is None:
        options = {}

    try:
        await websocket.send_json(
            {
                "type": "thinking",
                "title": "🤔 理解需求",
                "content": f"正在分析用户需求: {message[:80]}...",
            }
        )

        use_code = False
        kb_related = False
        enable_web_search = options.get("web_search", False)

        if current_settings.knowledge_base.get("enabled"):
            kb_related = any(
                kw in message.lower()
                for kw in ["文档", "知识库", "knowledge", "search", "查找"]
            )

        if any(
            kw in message.lower()
            for kw in [
                "代码",
                "python",
                "图表",
                "计算",
                "数据",
                "分析",
                "plot",
                "chart",
                "execute",
            ]
        ):
            use_code = True

        # 构建对话历史上下文
        context_prompt = ""
        if conversation_id:
            history = db_get_conversation_messages(conversation_id, limit=10)
            if history:
                context_prompt = "\n\n以下是之前的对话历史：\n"
                for h_msg in history:
                    role_label = "用户" if h_msg["role"] == "user" else "助手"
                    context_prompt += f"{role_label}: {h_msg['content']}\n"
                context_prompt += "\n请基于以上对话历史继续回答。\n"

        # 联网搜索
        search_context = ""
        if enable_web_search:
            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "🌐 联网搜索",
                    "content": f"正在搜索: {message[:50]}...",
                }
            )
            search_context = await web_search(message)
            if (
                search_context
                and not search_context.startswith("搜索失败")
                and search_context != "未找到相关结果"
            ):
                await websocket.send_json(
                    {
                        "type": "thinking",
                        "title": "🔍 搜索结果",
                        "content": f"找到相关资料，正在整合分析...",
                    }
                )

        if use_code:
            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "🛠️ 工具选择",
                    "content": "检测到代码/数据需求，准备生成Python代码",
                }
            )

            code_prompt = f"""根据用户需求生成Python代码：
用户需求：{message}"""
            if search_context:
                code_prompt += f"\n\n参考资料：\n{search_context}"
            if context_prompt:
                code_prompt += context_prompt
            code_prompt += "\n请直接输出可执行的Python代码，不需要解释。如果需要图表，保存为PNG文件。"

            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "💬 调用模型",
                    "content": "正在向AI模型请求生成代码...",
                }
            )

            code = await call_llm(code_prompt, current_settings)
            code = re.sub(r"^```python\s*\n?", "", code.strip(), flags=re.MULTILINE)
            code = re.sub(r"\n?```$", "", code.strip(), flags=re.MULTILINE)
            code = code.strip()

            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "📋 生成代码",
                    "content": f"```python\n{code}\n```",
                }
            )

            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "▶️ 执行代码",
                    "content": "正在沙箱环境中执行代码...",
                }
            )

            result = await execute_python(
                code, timeout=current_settings.sandbox["timeout"]
            )

            if result["success"]:
                response = f"✅ 执行成功！\n\n**标准输出:**\n{result['stdout']}\n\n**代码:**\n```python\n{code}\n```"
                if result["stderr"]:
                    response += f"\n\n**警告:**\n{result['stderr']}"
            else:
                response = f"❌ 执行失败: {result.get('error', '未知错误')}\n\n**代码:**\n```python\n{code}\n```"

        elif kb_related and knowledge_bases:
            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "📚 知识库检索",
                    "content": "正在从知识库中检索相关信息...",
                }
            )

            # 使用 RAG 检索器进行语义搜索
            rag_results = retriever.search(message, top_k=5, min_score=0.05)

            if rag_results:
                rag_context_str = ""
                for idx, r in enumerate(rag_results):
                    source_name = r.get("metadata", {}).get("name", "未知文档")
                    rag_context_str += f"\n--- 参考资料 {idx+1} (来源: {source_name}, 相关度: {r['score']}) ---\n"
                    rag_context_str += r["content"][:800] + "\n"

                await websocket.send_json(
                    {
                        "type": "thinking",
                        "title": "🔍 检索结果",
                        "content": f"找到 {len(rag_results)} 条相关内容，正在整合分析...",
                    }
                )

                kb_prompt = f"用户问题：{message}\n\n以下是知识库中检索到的相关参考资料：\n{rag_context_str}\n\n请基于以上参考资料回答用户问题。如果资料中没有相关信息，请基于你的知识回答，并说明信息不在知识库中。"
            else:
                kb_list = ", ".join([kb.name for kb in knowledge_bases.values()])
                await websocket.send_json(
                    {
                        "type": "thinking",
                        "title": "🔍 检索内容",
                        "content": f"未找到相关内容。可用知识库: {kb_list}",
                    }
                )
                kb_prompt = f"用户问题：{message}\n\n可用知识库：{kb_list}\n\n知识库中未找到直接相关的内容，请基于你的知识回答用户问题。"

            if context_prompt:
                kb_prompt += context_prompt
            if search_context:
                kb_prompt += f"\n\n网络搜索参考资料：\n{search_context}\n"
            response = await call_llm(kb_prompt, current_settings)

        else:
            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "🧠 智能分析",
                    "content": "正在处理您的请求...",
                }
            )

            await websocket.send_json(
                {
                    "type": "thinking",
                    "title": "💬 调用模型",
                    "content": "正在向AI模型发送请求...",
                }
            )

            full_prompt = message
            if context_prompt:
                full_prompt = context_prompt + "\n\n当前用户问题：" + message
            if search_context:
                full_prompt += f"\n\n网络搜索参考资料：\n{search_context}\n请参考以上搜索结果回答用户问题。"

            response = await call_llm(full_prompt, current_settings)

        # 保存用户消息到对话历史
        if conversation_id:
            db_add_message(conversation_id, "user", message)
            # 自动更新标题
            conv = db_get_conversation(conversation_id)
            if conv and conv.get("title") == "新对话":
                db_update_conversation_title(conversation_id, message[:20])

        # 流式输出
        await websocket.send_json({"type": "stream_start"})

        chunk_size = 50
        for i in range(0, len(response), chunk_size):
            chunk = response[i : i + chunk_size]
            await websocket.send_json({"type": "stream_data", "content": chunk})
            await asyncio.sleep(0.05)

        await websocket.send_json({"type": "stream_end"})

        # 保存助手回复到对话历史
        if conversation_id:
            db_add_message(conversation_id, "assistant", response)

    except Exception as e:
        error_msg = f"❌ 处理失败: {str(e)[:300]}"
        await websocket.send_json({"type": "error", "content": error_msg})

        print(f"Error in run_universal_agent: {traceback.format_exc()}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "chat")
            if msg_type == "chat":
                content = data.get("content", "")
                conversation_id = data.get("conversation_id")
                options = data.get("options", {})
                # 如果指定了 conversation_id 但对话不存在，自动创建
                if conversation_id and not db_get_conversation(conversation_id):
                    db_create_conversation(conv_id=conversation_id, title="新对话")

                # 优先使用 Agent 框架，失败时回退到旧的 run_universal_agent
                if AGENT_FRAMEWORK_AVAILABLE:
                    try:
                        await run_agent_task(
                            message=content,
                            conversation_id=conversation_id,
                            options=options,
                            send_func=websocket.send_json,
                        )
                    except Exception as agent_err:
                        print(
                            f"[WebSocket] Agent framework failed, falling back: {agent_err}"
                        )
                        try:
                            await websocket.send_json(
                                {
                                    "type": "thinking",
                                    "title": "切换模式",
                                    "content": "Agent 框架执行异常，切换到备用模式...",
                                }
                            )
                        except Exception:
                            pass
                        await run_universal_agent(
                            websocket,
                            content,
                            conversation_id=conversation_id,
                            options=options,
                        )
                else:
                    await run_universal_agent(
                        websocket,
                        content,
                        conversation_id=conversation_id,
                        options=options,
                    )
            else:
                # 兼容旧格式：直接将 data 当作消息内容
                message = data.get("content", str(data))
                conversation_id = data.get("conversation_id")
                options = data.get("options", {})
                if AGENT_FRAMEWORK_AVAILABLE:
                    try:
                        await run_agent_task(
                            message=message,
                            send_func=websocket.send_json,
                            conversation_id=conversation_id,
                            options=options,
                        )
                    except Exception as e:
                        print(f"[Agent Task Error] {e}")
                        await run_universal_agent(
                            websocket,
                            message,
                            conversation_id=conversation_id,
                            options=options,
                        )
                else:
                    await run_universal_agent(
                        websocket,
                        message,
                        conversation_id=conversation_id,
                        options=options,
                    )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": f"服务器错误: {str(e)}"})
        except:
            pass


@app.get("/favicon.ico")
async def favicon():
    svg_path = BASE_DIR / "static" / "favicon.svg"
    if svg_path.exists():
        return FileResponse(svg_path, media_type="image/svg+xml")
    return FileResponse(BASE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")


@app.get("/")
async def get():
    html_file = BASE_DIR / "static" / "index.html"
    return FileResponse(html_file)


@app.get("/health")
async def health_check():
    from datetime import datetime as dt

    return {"status": "healthy", "timestamp": dt.now().isoformat()}


# ==================== Model Test API ====================
class ModelTestRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str = ""
    model: str = ""


@app.post("/api/model/test")
async def test_model_connection(request: ModelTestRequest):
    import httpx

    provider = request.provider
    api_key = request.api_key
    base_url = request.base_url
    model = request.model

    result = {"success": False, "error": "", "balance": None}

    try:
        if provider == "openai":
            url = base_url if base_url else "https://api.openai.com/v1"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{url}/models", headers={"Authorization": f"Bearer {api_key}"}
                )
                if response.status_code == 200:
                    result["success"] = True
                    result["error"] = ""
                elif response.status_code == 401:
                    result["error"] = "API Key无效"
                elif response.status_code == 403:
                    result["error"] = "账号被禁用或权限不足"
                else:
                    result["error"] = f"HTTP错误: {response.status_code}"

        elif provider == "anthropic":
            url = base_url if base_url else "https://api.anthropic.com"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{url}/v1/models", headers={"x-api-key": api_key}
                )
                if response.status_code == 200:
                    result["success"] = True
                elif response.status_code == 401:
                    result["error"] = "API Key无效"
                else:
                    result["error"] = f"HTTP错误: {response.status_code}"

        elif provider == "aliyun":
            url = base_url if base_url else "https://dashscope.aliyuncs.com"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{url}/api/text/chat",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model if model else "qwen-plus-latest",
                        "input": {"messages": [{"role": "user", "content": "hi"}]},
                        "parameters": {"max_tokens": 10},
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status_code") == 200:
                        result["success"] = True
                    else:
                        result["error"] = data.get("message", "模型调用失败")
                elif response.status_code == 401:
                    result["error"] = "API Key无效"
                elif response.status_code == 403:
                    result["error"] = "余额不足或权限不足"
                    result["balance"] = 0
                else:
                    result["error"] = f"HTTP错误: {response.status_code}"

        elif provider == "baidu":
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://aip.baidubce.com/oauth/2.0/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": api_key,
                        "client_secret": "",
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    if "access_token" in data:
                        result["success"] = True
                    else:
                        result["error"] = data.get("error_description", "获取token失败")
                else:
                    result["error"] = f"HTTP错误: {response.status_code}"

        elif provider == "zhipu":
            url = base_url if base_url else "https://open.bigmodel.cn/api/paas/v4"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model if model else "glm-4",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 10,
                    },
                )
                if response.status_code == 200:
                    result["success"] = True
                elif response.status_code == 401:
                    result["error"] = "API Key无效"
                elif response.status_code == 403:
                    result["error"] = "余额不足"
                    result["balance"] = 0
                else:
                    result["error"] = f"HTTP错误: {response.status_code}"

        elif provider == "deepseek":
            url = base_url if base_url else "https://api.deepseek.com/v1"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model if model else "deepseek-chat",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 10,
                    },
                )
                if response.status_code == 200:
                    result["success"] = True
                else:
                    result["error"] = f"HTTP错误: {response.status_code}"

        elif provider == "ollama":
            url = base_url if base_url else "http://localhost:11434/v1"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{url}/models")
                if response.status_code == 200:
                    result["success"] = True
                else:
                    result["error"] = "Ollama服务未启动或连接失败"

        else:
            result["success"] = False
            result["error"] = f"不支持的提供商: {provider}"

    except httpx.TimeoutException:
        result["error"] = "连接超时"
    except httpx.ConnectError:
        result["error"] = "无法连接到服务器"
    except Exception as e:
        result["error"] = str(e)

    return JSONResponse(result)


# ==================== Model Save API ====================
class ModelSaveRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str = ""
    models: list = []
    params: dict = {}


@app.post("/api/model/save")
async def save_model_settings(request: ModelSaveRequest):
    try:
        settings = {
            "provider": request.provider,
            "api_key": request.api_key,
            "base_url": request.base_url,
            "models": request.models,
            "params": request.params,
        }
        with open(CONFIG_DIR / "model_settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting DATA-AI Web Interface...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
