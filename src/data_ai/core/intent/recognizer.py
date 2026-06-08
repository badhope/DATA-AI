"""
意图识别器

分析用户查询，识别意图类型，提取关键实体。
支持关键词/正则匹配 + LLM 兜底（可选）。
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...utils.logging import get_logger

logger = get_logger(__name__)


class IntentType(Enum):
    """意图类型"""

    # 代码相关
    CODE_GENERATION = "code_generation"
    CODE_EXPLANATION = "code_explanation"
    CODE_REFACTORING = "code_refactoring"
    CODE_DEBUGGING = "code_debugging"
    CODE_REVIEW = "code_review"

    # 文件操作
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_SEARCH = "file_search"
    FILE_MODIFY = "file_modify"

    # 搜索查询
    WEB_SEARCH = "web_search"
    KNOWLEDGE_QUERY = "knowledge_query"
    DOCUMENT_SEARCH = "document_search"

    # 数据分析
    DATA_ANALYSIS = "data_analysis"
    DATA_VISUALIZATION = "data_visualization"
    DATA_PROCESSING = "data_processing"

    # 系统操作
    SHELL_COMMAND = "shell_command"
    SYSTEM_INFO = "system_info"
    PROCESS_MANAGEMENT = "process_management"

    # Agent 任务
    COMPLEX_TASK = "complex_task"
    PLANNING = "planning"
    AUTOMATION = "automation"

    # 对话交互
    CONVERSATION = "conversation"
    QUESTION_ANSWERING = "question_answering"
    CLARIFICATION = "clarification"

    # 工具使用
    TOOL_USAGE = "tool_usage"
    BROWSER_AUTOMATION = "browser_automation"

    # 其他
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """提取的实体"""

    name: str
    value: str
    entity_type: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Intent:
    """识别出的意图"""

    intent_type: IntentType
    confidence: float
    entities: list[Entity] = field(default_factory=list)
    sub_intents: list[Intent] = field(default_factory=list)
    raw_query: str = ""
    normalized_query: str = ""
    context_hints: dict[str, Any] = field(default_factory=dict)

    @property
    def is_complex(self) -> bool:
        """是否为复杂意图（需要多步骤处理）"""
        return self.intent_type in (
            IntentType.COMPLEX_TASK,
            IntentType.PLANNING,
            IntentType.AUTOMATION,
            IntentType.CODE_REFACTORING,
            IntentType.DATA_ANALYSIS,
        )

    @property
    def requires_tools(self) -> bool:
        """是否需要工具支持"""
        return self.intent_type not in (
            IntentType.CONVERSATION,
            IntentType.QUESTION_ANSWERING,
            IntentType.UNKNOWN,
        )

    def get_primary_entity(self, entity_type: str | None = None) -> Entity | None:
        """获取主要实体"""
        if not self.entities:
            return None
        if entity_type:
            for e in self.entities:
                if e.entity_type == entity_type:
                    return e
            return None
        return self.entities[0]


@dataclass
class IntentContext:
    """意图识别上下文"""

    session_id: str = ""
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    available_tools: list[str] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    working_directory: str = ""
    recent_files: list[str] = field(default_factory=list)
    environment: dict[str, str] = field(default_factory=dict)


class IntentRecognizer:
    """
    意图识别器

    支持多种识别策略：
    1. 关键词匹配（快速）
    2. 模式匹配（正则）
    3. LLM 分类（精确）
    4. 混合策略（推荐）

    典型的使用方式：

    >>> recognizer = IntentRecognizer(use_llm=True)
    >>> recognizer.set_llm_manager(llm_manager)
    >>> intent = recognizer.recognize("帮我写一个 Python 排序函数")
    >>> intent.intent_type
    <IntentType.CODE_GENERATION: 'code_generation'>
    """

    _LLM_INTENT_TYPES = [
        "question",
        "command",
        "code_generation",
        "web_search",
        "file_operation",
        "conversation",
    ]

    def __init__(self, use_llm: bool = True, llm_manager: Any | None = None):
        self._use_llm = use_llm
        self._llm_manager = llm_manager
        self._patterns = self._build_patterns()
        self._keywords = self._build_keywords()
        self._llm_classifier = None

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def set_llm_manager(self, manager: Any) -> None:
        """设置 LLM 管理器（用于在 LLM 兜底时进行更精确的分类）"""
        self._llm_manager = manager
        if manager is not None:
            self._use_llm = True
        logger.debug("IntentRecognizer 已设置 LLM 管理器")

    @property
    def use_llm(self) -> bool:
        return self._use_llm

    @use_llm.setter
    def use_llm(self, value: bool) -> None:
        self._use_llm = value

    def recognize(
        self,
        query: str,
        context: IntentContext | None = None,
    ) -> Intent:
        """
        识别用户意图

        1. 关键词/正则匹配给出 baseline 分数
        2. 若分数 < 0.6 且 use_llm=True 且 LLM 可用，回退到 LLM
        3. 提取实体

        Args:
            query: 用户查询
            context: 上下文信息

        Returns:
            识别出的意图
        """
        raw_query = query or ""
        normalized_query = self._normalize_query(raw_query)
        # 口语化 / 错别字归一化(失败时静默回退)
        try:
            colloquial = self._normalize_colloquial(normalized_query)
        except Exception as e:
            logger.debug(f"口语化归一化失败,使用原文本: {e}")
            colloquial = normalized_query
        if colloquial != normalized_query:
            logger.debug(f"口语化归一化: {normalized_query!r} -> {colloquial!r}")
        normalized_query = colloquial  # 关键: 后续关键词匹配用归一化后的文本

        # 空查询
        if not normalized_query:
            return Intent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                entities=[],
                raw_query=raw_query,
                normalized_query="",
                context_hints={},
            )

        # 1. 关键词匹配
        intent_scores = self._keyword_match(normalized_query)

        # 2. 模式匹配
        pattern_scores = self._pattern_match(normalized_query)

        # 3. 合并分数
        final_scores = self._merge_scores(intent_scores, pattern_scores)

        # 4. 取最佳
        best_type, best_score = self._get_best_intent(final_scores)

        # 5. LLM 兜底
        used_llm = False
        if self._use_llm and self._llm_manager is not None and best_score < 0.6:
            try:
                llm_intent = self._llm_classify_sync(raw_query, context)
                if llm_intent is not None and llm_intent.confidence > best_score:
                    best_type = llm_intent.intent_type
                    best_score = llm_intent.confidence
                    used_llm = True
            except Exception as e:
                logger.warning(f"LLM 意图分类失败，使用规则结果: {e}")

        # 6. 提取实体
        entities = self._extract_entities(raw_query, best_type)

        # 7. 构建意图对象
        intent = Intent(
            intent_type=best_type,
            confidence=float(min(max(best_score, 0.0), 1.0)),
            entities=entities,
            raw_query=raw_query,
            normalized_query=normalized_query,
            context_hints=self._get_context_hints(raw_query, context),
        )

        # 8. 检测子意图
        intent.sub_intents = self._detect_sub_intents(raw_query, intent)

        logger.debug(f"意图识别完成: {best_type.value} (conf={intent.confidence:.2f}, llm={used_llm})")

        return intent

    async def recognize_async(
        self,
        query: str,
        context: IntentContext | None = None,
    ) -> Intent:
        """
        异步识别用户意图，LLM 分类不会阻塞事件循环
        """
        raw_query = query or ""
        normalized_query = self._normalize_query(raw_query)

        if not normalized_query:
            return Intent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.0,
                entities=[],
                raw_query=raw_query,
                normalized_query="",
                context_hints={},
            )

        intent_scores = self._keyword_match(normalized_query)
        pattern_scores = self._pattern_match(normalized_query)
        final_scores = self._merge_scores(intent_scores, pattern_scores)
        best_type, best_score = self._get_best_intent(final_scores)

        if self._use_llm and self._llm_manager is not None and best_score < 0.6:
            try:
                llm_intent = await self._llm_classify_async(raw_query, context)
                if llm_intent is not None and llm_intent.confidence > best_score:
                    best_type = llm_intent.intent_type
                    best_score = llm_intent.confidence
            except Exception as e:
                logger.warning(f"LLM 意图分类失败，使用规则结果: {e}")

        entities = self._extract_entities(raw_query, best_type)

        intent = Intent(
            intent_type=best_type,
            confidence=float(min(max(best_score, 0.0), 1.0)),
            entities=entities,
            raw_query=raw_query,
            normalized_query=normalized_query,
            context_hints=self._get_context_hints(raw_query, context),
        )
        intent.sub_intents = self._detect_sub_intents(raw_query, intent)
        return intent

    def batch_recognize(
        self,
        queries: list[str],
        context: IntentContext | None = None,
    ) -> list[Intent]:
        """批量识别意图"""
        return [self.recognize(q, context) for q in queries]

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _normalize_query(self, query: str) -> str:
        """标准化查询(空格 + 中英标点)"""
        if not query:
            return ""
        query = " ".join(query.split())
        query = query.replace("？", "?").replace("！", "!")
        return query.strip()

    # 中文常见口语化误用 / 错别字归一化字典
    # 顺序敏感: 长的/特化的先匹配(避免被短的吞掉),例如 "给我弄" 应在 "弄一下" 之前
    _COLLOQUIAL_FIXES: list[tuple[str, str]] = [
        # ── 错别字(高优先级) ──
        ("帐单", "账单"),
        ("帐号", "账号"),
        ("其它", "其他"),
        ("图象", "图像"),
        ("帐户", "账户"),
        ("登陆", "登录"),
        ("做为", "作为"),
        ("部份", "部分"),
        ("记忆体", "内存"),
        # ── 啰嗦前缀(长串优先) ──
        ("请问一下", "请问"),
        ("我想问一下", "请问"),
        ("能不能", "可以"),
        ("可不可以", "可以"),
        # ── 老板/秘书高频口语(长的优先,避免被短的吞) ──
        ("给我弄", "帮我"),
        ("给我搞", "帮我"),
        ("帮我一下", "帮我"),
        ("弄一下", "处理"),
        ("搞一下", "处理"),
        ("整一下", "处理"),
        # ── 助词 / 嗯啊 ──
        ("那个那个", "那个"),
        ("这个这个", "这个"),
        # ── 中英混输 ──
        ("打开 app", "打开应用"),
        ("打开APP", "打开应用"),
        ("send 邮件", "发邮件"),
        ("写个 mail", "写邮件"),
        # ── 老板自称 ──
        ("俺", "我"),
        ("咱", "我们"),
    ]

    def _normalize_colloquial(self, query: str) -> str:
        """
        中文口语化 / 错别字归一化(轻量级,基于字典)

        适用场景: 用户说话随意,夹杂错别字/口语词,需要先清洗再交给意图识别。
        严格: 不会改变语义,只做替换;长字符串先匹配避免误替换。
        """
        if not query:
            return query
        result = query
        for old, new in self._COLLOQUIAL_FIXES:
            if old in result:
                result = result.replace(old, new)
        return result

    def _build_patterns(self) -> dict[IntentType, list[re.Pattern]]:
        """构建正则模式"""
        return {
            IntentType.CODE_GENERATION: [
                re.compile(r"(写|生成|创建|编写|实现).*(代码|函数|类|脚本|程序)", re.I),
                re.compile(r"(write|generate|create|implement)\s+(\w+\s+)?(code|function|class|script|program)", re.I),
                re.compile(r"帮我写", re.I),
                re.compile(r"(写|生成|创建|写一个)\s*(?:一个|段)?\s*\w+\s*(函数|方法|类|脚本)", re.I),
                re.compile(
                    r"\b(write|create|generate|implement|build|develop)\s+.{0,30}?\b(code|function|method|class|script|program|module|api|component)\b",
                    re.I,
                ),
                re.compile(
                    r"\b(write|create|implement)\s+(?:a|an)\s+\w+\s+(function|method|class|script|program)\b", re.I
                ),
            ],
            IntentType.CODE_EXPLANATION: [
                re.compile(r"(解释|说明|讲解|分析).*(代码|函数|这段)", re.I),
                re.compile(r"(explain|what does|how does).*(code|function|this)", re.I),
                re.compile(r"这段代码.*什么", re.I),
                re.compile(r"(解释|说明).*(这段|这个|下面)", re.I),
            ],
            IntentType.CODE_DEBUGGING: [
                re.compile(r"(调试|debug|修复|解决).*(错误|bug|问题|报错)", re.I),
                re.compile(r"(fix|debug|solve).*(error|bug|issue|problem)", re.I),
                re.compile(r"为什么.*不工作", re.I),
                re.compile(r"(报错|错误)\s*(信息|原因)?", re.I),
            ],
            IntentType.CODE_REFACTORING: [
                re.compile(r"(重构|优化|改进).*(代码|函数|结构)", re.I),
                re.compile(r"(refactor|optimize|improve).*(code|function)", re.I),
            ],
            IntentType.FILE_READ: [
                re.compile(r"(读取|查看|打开|显示).*(文件|内容)", re.I),
                re.compile(r"(read|view|open|show|cat)\s+\S+\.\w+", re.I),
                re.compile(r"查看\s+\S+\.(py|js|ts|java|go|rs|cpp|c|h|json|yaml|yml|md|txt|csv|xlsx)", re.I),
            ],
            IntentType.FILE_WRITE: [
                re.compile(r"(写入|保存|创建|修改).*(文件|内容)", re.I),
                re.compile(r"(write|save|create|modify).*(file|content)", re.I),
            ],
            IntentType.FILE_SEARCH: [
                re.compile(r"(搜索|查找|寻找).*(文件|目录)", re.I),
                re.compile(r"(search|find|locate).*(file|directory)", re.I),
                re.compile(r"(glob|grep|find)\s+", re.I),
            ],
            IntentType.WEB_SEARCH: [
                re.compile(r"(搜索|查询|查找).*(网络|网上|百度|谷歌)", re.I),
                re.compile(r"(search|query|google|bing)", re.I),
                re.compile(r"帮我搜", re.I),
            ],
            IntentType.SHELL_COMMAND: [
                re.compile(r"(运行|执行|跑).*(命令|脚本|程序)", re.I),
                re.compile(r"(run|execute).*(command|script)", re.I),
                re.compile(r"^\s*(python|node|bash|sh|npm|pip|git|docker|make|cargo|go)\s+", re.I),
            ],
            IntentType.DATA_ANALYSIS: [
                re.compile(r"(分析|统计).*(数据|表格|csv|excel)", re.I),
                re.compile(r"(analyze|analysis).*(data|csv|excel)", re.I),
            ],
            IntentType.BROWSER_AUTOMATION: [
                re.compile(r"(打开|访问|浏览).*(网页|网站|浏览器)", re.I),
                re.compile(r"(open|visit|browse).*(webpage|website|browser)", re.I),
                re.compile(r"(点击|截图|填表)", re.I),
            ],
            IntentType.COMPLEX_TASK: [
                re.compile(r"(帮我|请).*(完成|实现|做)", re.I),
                re.compile(r"(完成|实现).*(项目|应用|系统)", re.I),
                re.compile(r"(build|create|implement).*(project|app|system)", re.I),
            ],
            IntentType.QUESTION_ANSWERING: [
                re.compile(r"^(什么|为什么|怎么|如何|谁|哪|哪个|哪些)", re.I),
                re.compile(r"^(what|why|how|who|where|when|which)", re.I),
                re.compile(r"\?$", re.I),
            ],
            IntentType.PLANNING: [
                re.compile(r"(规划|计划|方案|步骤)", re.I),
                re.compile(r"(plan|planning)", re.I),
            ],
            IntentType.AUTOMATION: [
                re.compile(r"(自动|自动化)", re.I),
                re.compile(r"(automate|automation)", re.I),
            ],
        }

    def _build_keywords(self) -> dict[IntentType, list[str]]:
        """构建关键词映射"""
        return {
            IntentType.CODE_GENERATION: [
                "写代码",
                "生成",
                "实现",
                "编写",
                "开发",
                "create",
                "generate",
                "implement",
                "写一个函数",
                "写个函数",
                "写个方法",
            ],
            IntentType.CODE_EXPLANATION: ["解释", "说明", "讲解", "explain", "what does", "这段代码", "解释代码"],
            IntentType.CODE_DEBUGGING: ["调试", "debug", "修复", "fix", "错误", "error", "bug", "报错"],
            IntentType.CODE_REFACTORING: ["重构", "优化代码", "refactor", "优化"],
            IntentType.FILE_READ: ["读取", "查看", "打开", "read", "view", "open", "cat", "看一下", "打开文件"],
            IntentType.FILE_WRITE: ["写入", "保存", "save", "write", "写文件"],
            IntentType.FILE_SEARCH: ["搜索", "查找", "find", "search", "glob", "找文件"],
            IntentType.WEB_SEARCH: ["搜索", "查询", "search", "google", "百度", "网上", "搜一下"],
            IntentType.SHELL_COMMAND: ["运行", "执行", "run", "execute", "bash", "shell", "命令"],
            IntentType.DATA_ANALYSIS: ["分析", "统计", "analyze", "analysis", "分析数据"],
            IntentType.BROWSER_AUTOMATION: ["浏览器", "网页", "browser", "click", "screenshot", "截图", "打开网页"],
            IntentType.COMPLEX_TASK: ["帮我", "完成", "实现", "build", "create project", "做一个"],
            IntentType.CONVERSATION: ["你好", "hello", "hi", "谢谢", "thanks", "在吗", "你是谁"],
            IntentType.QUESTION_ANSWERING: ["什么是", "怎么", "如何", "为什么", "what is", "how", "why", "who"],
            IntentType.PLANNING: ["规划", "计划", "plan", "方案"],
            IntentType.AUTOMATION: ["自动", "自动化", "automate"],
        }

    def _keyword_match(self, query: str) -> dict[IntentType, float]:
        """关键词匹配"""
        scores: dict[IntentType, float] = {}
        query_lower = query.lower()

        for intent_type, keywords in self._keywords.items():
            score = 0.0
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    score += 0.25
            scores[intent_type] = min(score, 1.0)

        return scores

    def _pattern_match(self, query: str) -> dict[IntentType, float]:
        """模式匹配"""
        scores: dict[IntentType, float] = {}

        for intent_type, patterns in self._patterns.items():
            matched = False
            for pattern in patterns:
                if pattern.search(query):
                    matched = True
                    break
            scores[intent_type] = 0.9 if matched else 0.0

        return scores

    def _merge_scores(
        self,
        keyword_scores: dict[IntentType, float],
        pattern_scores: dict[IntentType, float],
    ) -> dict[IntentType, float]:
        """合并分数"""
        all_types = set(keyword_scores.keys()) | set(pattern_scores.keys())
        merged: dict[IntentType, float] = {}

        for intent_type in all_types:
            kw = keyword_scores.get(intent_type, 0.0)
            pt = pattern_scores.get(intent_type, 0.0)
            merged[intent_type] = max(pt, kw * 0.5 + pt * 0.5)

        # 对话/问候语给一个温和的兜底
        if not any(v > 0.3 for v in merged.values()):
            query_lower = sum(merged.values())
            if query_lower < 0.5:
                # 没有明显匹配，但存在关键词命中
                for t, v in list(merged.items()):
                    if v > 0:
                        merged[t] = max(v, 0.4)

        return merged

    def _get_best_intent(self, scores: dict[IntentType, float]) -> tuple[IntentType, float]:
        """获取最佳意图"""
        if not scores:
            return IntentType.UNKNOWN, 0.0

        best_type = max(scores, key=scores.get)
        return best_type, scores[best_type]

    def _extract_entities(self, query: str, intent_type: IntentType) -> list[Entity]:
        """提取实体：文件路径、URL、邮箱、代码块、编程语言、引号字符串、shell 命令、文件扩展名等"""
        entities: list[Entity] = []

        if not query:
            return entities

        # 文件路径
        file_patterns = [
            r"(?:[\w\-]+/)*[\w\-\.]+\.(py|js|ts|jsx|tsx|java|go|rs|cpp|c|h|hpp|json|yaml|yml|toml|md|txt|csv|xlsx|sql|sh|rb|php|html|css)",
            r"~/[\w/\-\.]+",
            r"(?<![\w/])/(?:[\w/\-\.]+)+",
            r"\./[\w/\-\.]+",
            r"\.\./[\w/\-\.]+",
        ]
        seen: set = set()
        for pattern in file_patterns:
            for match in re.finditer(pattern, query):
                value = match.group()
                if value in seen:
                    continue
                seen.add(value)
                entities.append(
                    Entity(
                        name="file_path",
                        value=value,
                        entity_type="file",
                        confidence=0.85,
                    )
                )

        # URL
        url_pattern = r"https?://[^\s\)\]\}\>]+"
        for match in re.finditer(url_pattern, query):
            entities.append(
                Entity(
                    name="url",
                    value=match.group(),
                    entity_type="url",
                    confidence=0.95,
                )
            )

        # 邮箱
        email_pattern = r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"
        for match in re.finditer(email_pattern, query):
            entities.append(
                Entity(
                    name="email",
                    value=match.group(),
                    entity_type="email",
                    confidence=0.9,
                )
            )

        # 编程语言
        languages = {
            "python": "python",
            "py": "python",
            "javascript": "javascript",
            "js": "javascript",
            "typescript": "typescript",
            "ts": "typescript",
            "java": "java",
            "go": "go",
            "golang": "go",
            "rust": "rust",
            "rs": "rust",
            "cpp": "cpp",
            "c++": "cpp",
            "c": "c",
            "ruby": "ruby",
            "rb": "ruby",
            "php": "php",
            "shell": "shell",
            "bash": "shell",
            "sh": "shell",
            "sql": "sql",
            "html": "html",
            "css": "css",
        }
        query_lower = query.lower()
        for token, lang in languages.items():
            # 仅匹配独立的 token（避免 "type" 中匹配到 "py"）
            if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", query_lower):
                # 避免与文件路径重复（如果已经有 .py 文件，这里就不再添加语言实体）
                if not any(e.entity_type == "file" and e.value.endswith(f".{token}") for e in entities):
                    entities.append(
                        Entity(
                            name="language",
                            value=lang,
                            entity_type="programming_language",
                            confidence=0.7,
                        )
                    )

        # 代码块（```xxx ... ``` 或 `xxx`）
        code_block = re.search(r"```[\w]*\n([\s\S]+?)```", query)
        if code_block:
            entities.append(
                Entity(
                    name="code_block",
                    value=code_block.group(1),
                    entity_type="code",
                    confidence=0.95,
                    metadata={"language": ""},
                )
            )

        inline_code = re.findall(r"`([^`\n]+)`", query)
        for snippet in inline_code:
            if len(snippet.strip()) < 2:
                continue
            entities.append(
                Entity(
                    name="inline_code",
                    value=snippet,
                    entity_type="code",
                    confidence=0.8,
                )
            )

        # Shell 命令（如 git status、npm install xxx）
        shell_cmd = re.search(
            r"^\s*(git|docker|npm|pip|conda|brew|cargo|make|curl|wget|ssh|scp|rsync|ls|cd|cp|mv|rm|mkdir|cat|grep|find|awk|sed|tar|zip|unzip)\s+[^\n]+",
            query,
            re.M,
        )
        if shell_cmd:
            entities.append(
                Entity(
                    name="shell_command",
                    value=shell_cmd.group().strip(),
                    entity_type="command",
                    confidence=0.85,
                )
            )

        # 引号字符串
        quoted = re.findall(r'"([^"]{2,})"|\'([^\']{2,})\'', query)
        for q in quoted:
            value = q[0] or q[1]
            if value and not value.startswith(("http", "/", ".")):
                entities.append(
                    Entity(
                        name="quoted_string",
                        value=value,
                        entity_type="string",
                        confidence=0.6,
                    )
                )

        # 数字（含单位）
        num_match = re.findall(r"\b\d+(?:\.\d+)?\s*(?:kb|mb|gb|tb|ms|s|min|h|%|行|个|次)?\b", query, re.I)
        for n in num_match:
            entities.append(
                Entity(
                    name="number",
                    value=n.strip(),
                    entity_type="number",
                    confidence=0.7,
                )
            )

        # 时间相关
        if re.search(r"(今天|昨天|明天|前天|后天|上周|本周|下周|上月|本月|下月|去年|今年|明年)", query):
            entities.append(
                Entity(
                    name="time_reference",
                    value="relative_time",
                    entity_type="time",
                    confidence=0.75,
                )
            )

        return entities

    def _get_context_hints(self, query: str, context: IntentContext | None) -> dict[str, Any]:
        """获取上下文提示"""
        hints: dict[str, Any] = {}

        if context:
            if context.recent_files:
                hints["recent_files"] = context.recent_files[:5]
            if context.available_tools:
                hints["available_tools"] = context.available_tools
            if context.working_directory:
                hints["working_directory"] = context.working_directory
            if context.conversation_history:
                last_msgs = context.conversation_history[-3:]
                hints["recent_topics"] = [m.get("content", "")[:100] for m in last_msgs]

        return hints

    def _detect_sub_intents(self, query: str, main_intent: Intent) -> list[Intent]:
        """检测子意图"""
        sub_intents: list[Intent] = []
        if not query:
            return sub_intents

        if main_intent.is_complex:
            if "文件" in query or "file" in query.lower():
                sub_intents.append(
                    Intent(
                        intent_type=IntentType.FILE_READ,
                        confidence=0.6,
                        raw_query=query,
                    )
                )
            if "代码" in query or "code" in query.lower():
                sub_intents.append(
                    Intent(
                        intent_type=IntentType.CODE_GENERATION,
                        confidence=0.6,
                        raw_query=query,
                    )
                )
            if "搜索" in query or "search" in query.lower() or "查询" in query:
                sub_intents.append(
                    Intent(
                        intent_type=IntentType.WEB_SEARCH,
                        confidence=0.55,
                        raw_query=query,
                    )
                )
            if "运行" in query or "执行" in query or "run" in query.lower():
                sub_intents.append(
                    Intent(
                        intent_type=IntentType.SHELL_COMMAND,
                        confidence=0.55,
                        raw_query=query,
                    )
                )

        return sub_intents

    # ------------------------------------------------------------------
    # LLM 分类（兜底）
    # ------------------------------------------------------------------

    def _llm_classify_sync(
        self,
        query: str,
        context: IntentContext | None = None,
    ) -> Intent | None:
        """同步封装（仅在没有事件循环时使用）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 当前正在事件循环里，无法同步等待
                return None
            return loop.run_until_complete(self._llm_classify_async(query, context))
        except RuntimeError:
            return asyncio.run(self._llm_classify_async(query, context))
        except Exception as e:
            logger.warning(f"LLM 同步分类失败: {e}")
            return None

    async def _llm_classify_async(
        self,
        query: str,
        context: IntentContext | None = None,
    ) -> Intent | None:
        """使用 LLM 进行意图分类（仅作为兜底）"""
        if self._llm_manager is None:
            return None

        prompt = (
            f"Classify the intent of this user query into one of: "
            f"{', '.join(self._LLM_INTENT_TYPES)}.\n"
            f"Query: {query}\n"
            f'Return JSON: {{"intent_type": "...", "confidence": 0.0-1.0, "reasoning": "..."}}'
        )

        try:
            from ..llm.manager import ChatMessage

            messages = [
                ChatMessage(
                    role="system",
                    content="You are an intent classification assistant. Always respond with valid JSON.",
                ),
                ChatMessage(role="user", content=prompt),
            ]
            response = await self._llm_manager.chat(
                messages=messages,
                temperature=0.0,
            )
            return self._parse_llm_intent(response.content or "", query)
        except Exception as e:
            logger.warning(f"LLM 分类调用失败: {e}")
            return None

    def _parse_llm_intent(self, content: str, query: str) -> Intent | None:
        """解析 LLM 返回的 JSON 分类结果"""
        if not content:
            return None

        # 尝试提取 JSON 块
        json_match = re.search(r"\{[\s\S]*\}", content)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return None

        intent_str = data.get("intent_type", "").lower().strip()
        try:
            intent_type = IntentType(intent_str)
        except ValueError:
            # 兼容 LLM 自由文本标签到枚举的映射
            alias_map = {
                "question": IntentType.QUESTION_ANSWERING,
                "qa": IntentType.QUESTION_ANSWERING,
                "command": IntentType.SHELL_COMMAND,
                "shell": IntentType.SHELL_COMMAND,
                "shell_command": IntentType.SHELL_COMMAND,
                "code_generation": IntentType.CODE_GENERATION,
                "code": IntentType.CODE_GENERATION,
                "web_search": IntentType.WEB_SEARCH,
                "search": IntentType.WEB_SEARCH,
                "file_operation": IntentType.FILE_READ,
                "file": IntentType.FILE_READ,
                "file_read": IntentType.FILE_READ,
                "conversation": IntentType.CONVERSATION,
                "chat": IntentType.CONVERSATION,
            }
            intent_type = alias_map.get(intent_str)
            if intent_type is None:
                return None

        try:
            confidence = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(1.0, confidence))

        return Intent(
            intent_type=intent_type,
            confidence=confidence,
            raw_query=query,
            normalized_query=self._normalize_query(query),
            context_hints={"llm_reasoning": data.get("reasoning", "")},
        )
