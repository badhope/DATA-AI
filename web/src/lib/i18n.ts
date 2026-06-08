import { useSettings } from "@/lib/stores/settings";
/**
 * Lightweight i18n system for the DATA-AI web console.
 * Supports English (default) and Simplified Chinese.
 */
import { useSyncExternalStore } from "react";

export type Locale = "en" | "zh";

export const SUPPORTED_LOCALES: Locale[] = ["en", "zh"];
export const DEFAULT_LOCALE: Locale = "en";

const LOCALE_STORAGE_KEY = "data-ai-locale";
const CHANGE_EVENT = "data-ai:locale-change";

/* ---------- Catalog ---------- */

export type Catalog = {
  common: Record<string, string>;
  nav: Record<string, string>;
  mobile: Record<string, string>;
  search: Record<string, string>;
  status: Record<string, string>;
  provider: Record<string, string>;
  settings: Record<string, string>;
  welcome: string;
};

const EN: Catalog = {
  common: {
    appName: "DATA-AI",
    tagline: "Multi-LLM agent runtime with RAG, memory and 30+ tools",
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    edit: "Edit",
    create: "Create",
    refresh: "Refresh",
    search: "Search",
    loading: "Loading…",
    confirm: "Confirm",
    yes: "Yes",
    no: "No",
    online: "Online",
    offline: "Offline",
    degraded: "Degraded",
    checking: "Checking…",
    health: "Health",
    language: "Language",
    theme: "Theme",
    light: "Light",
    dark: "Dark",
    system: "System",
    settings: "Settings",
    back: "Back",
    next: "Next",
    done: "Done",
    error: "Error",
    success: "Success",
    warning: "Warning",
    info: "Info",
    noData: "No data",
    untitled: "Untitled",
    unknown: "Unknown",
  },
  nav: {
    overview: "Overview",
    overviewDashboard: "Dashboard",
    overviewDashboardDesc: "System status and recent activity",
    convoAndAgents: "Chat & Agents",
    chat: "Chat Console",
    chatDesc: "Multi-model streaming chat",
    agents: "Agents",
    agentsDesc: "Single-agent setup and runs",
    team: "Agent Teams",
    teamDesc: "Multi-agent collaboration and consensus",
    capabilities: "Capabilities",
    tools: "Tool Gallery",
    toolsDesc: "Browse and try 30+ tools",
    sandbox: "Code Sandbox",
    sandboxDesc: "Online execution and file management",
    rag: "Knowledge Base (RAG)",
    ragDesc: "Document retrieval with citations",
    memory: "Memory System",
    memoryDesc: "Short- and long-term memory",
    skills: "Skill Manager",
    skillsDesc: "Skill definitions and execution",
    mcp: "MCP Servers",
    mcpDesc: "Model Context Protocol integrations",
    office: "Office & Files",
    officeWord: "Word",
    officeWordDesc: "Word document processing",
    officePpt: "PPT",
    officePptDesc: "Presentation generation",
    officeExcel: "Excel",
    officeExcelDesc: "Spreadsheet analysis",
    officePdf: "PDF",
    officePdfDesc: "PDF read / write / merge",
    system: "System",
    notifications: "Notifications",
    notificationsDesc: "System events and alerts",
    models: "Model Manager",
    modelsDesc: "Model registration and testing",
    settingsDesc: "API Key, theme and language",
    governance: "Governance",
    audit: "Audit Log",
    auditDesc: "Compliance and forensic trail",
    quota: "Quota & Usage",
    quotaDesc: "Per-key limits and rate gates",
    webhooks: "Webhooks",
    webhooksDesc: "Event subscriptions and deliveries",
    scheduler: "Scheduler",
    schedulerDesc: "Cron jobs and automation",
    enterprise: "Enterprise",
    tenants: "Tenants",
    tenantsDesc: "Multi-tenant isolation & quotas",
    rbac: "RBAC & Policies",
    rbacDesc: "Roles, ABAC and delegation",
    billing: "Cost Center",
    billingDesc: "Pricing, budgets and invoices",
    sla: "SLA & Status",
    slaDesc: "SLO evaluation, incidents, status page",
    sso: "SSO / IdP",
    ssoDesc: "OIDC / SAML / SCIM integration",
    residency: "Data Residency",
    residencyDesc: "Region routing and compliance",
    auditChain: "Audit Chain",
    auditChainDesc: "Merkle-rooted tamper-evidence",
    replication: "Cross-Region Replication",
    replicationDesc: "Streams, lag, failover and quorum",
    recovery: "Backup & Recovery",
    recoveryDesc: "Schedules, restores and DR drills",
    compensation: "SLA Compensation",
    compensationDesc: "Breach detection and credit calculation",

    // Page titles
    tenants_title: "Tenants",
    tenants_subtitle: "Multi-tenant isolation with quotas, members and lifecycle",
    rbac_title: "RBAC & ABAC",
    rbac_subtitle: "Roles, conditions, delegation and decision log",
    billing_title: "Cost Center",
    billing_subtitle: "Per-model pricing, budgets, cost centers and invoices",
    sla_title: "SLA & Status",
    sla_subtitle: "SLO evaluation, incidents and public status page",
    sso_title: "SSO / IdP",
    sso_subtitle: "OIDC / SAML providers, SCIM provisioning and sessions",
    residency_title: "Data Residency",
    residency_subtitle: "Region routing, residency policies and assignments",
    auditChain_title: "Audit Chain",
    auditChain_subtitle: "Merkle-rooted tamper-evidence for audit logs",
    replication_title: "Cross-Region Replication",
    replication_subtitle: "Multi-region streams, lag tracking and failover",
    recovery_title: "Backup & Recovery",
    recovery_subtitle: "Schedules, restore points, DR drills and retention",
    compensation_title: "SLA Compensation",
    compensation_subtitle: "Breach detection, credit calculation and dispute",
    collapse: "Collapse sidebar",
    openMenu: "Open menu",
    closeMenu: "Close menu",
  },
  mobile: {
    chat: "Chat",
    agents: "Agents",
    tools: "Tools",
    sandbox: "Sandbox",
    rag: "Knowledge",
    settings: "Settings",
  },
  search: {
    placeholder: "Search pages, tools, settings…",
    title: "Search",
    description: "Quick navigation across pages, tools and settings.",
    noResults: "No results",
  },
  status: {
    healthy: "Healthy",
    degraded: "Degraded",
    down: "Down",
    checking: "Checking…",
  },
  provider: {
    openai: "OpenAI",
    anthropic: "Anthropic",
    google: "Google Gemini",
    azure: "Azure OpenAI",
    aws: "AWS Bedrock",
    deepseek: "DeepSeek",
    siliconflow: "SiliconFlow",
    qwen: "Qwen (通义千问)",
    dashscope: "Alibaba DashScope",
    zhipu: "Zhipu GLM (智谱)",
    moonshot: "Moonshot (月之暗面 Kimi)",
    yi: "Yi (零一万物)",
    baichuan: "Baichuan (百川)",
    doubao: "Doubao (字节豆包)",
    stepfun: "StepFun (阶跃星辰)",
    ollama: "Ollama (local)",
    vllm: "vLLM (local)",
    lmstudio: "LM Studio (local)",
    offline: "Offline (built-in)",
  },
  settings: {
    title: "Settings",
    tabsOverview: "Overview",
    tabsConnection: "Connection",
    tabsAppearance: "Appearance",
    tabsBehavior: "Behavior",
    tabsAbout: "About",
    sectionConnection: "Connection",
    sectionProvider: "Provider",
    sectionProfile: "Connection Profile",
    sectionProfiles: "Profiles",
    sectionTest: "Test & Diagnostics",
    sectionExport: "Backup & Restore",
    profilesTitle: "Connection Profiles",
    profilesDesc: "Switch quickly between providers. The active profile is used for all API calls.",
    profileName: "Profile name",
    profileActive: "Active",
    profileAdd: "New Profile",
    profileDuplicate: "Duplicate",
    profileDelete: "Delete",
    profileDeleteConfirm: "Delete this profile?",
    profileImport: "Import",
    profileExport: "Export",
    profileImportOk: "Imported {n} profile(s).",
    profileImportErr: "Invalid profile JSON.",
    fieldProvider: "Provider preset",
    fieldBaseUrl: "Base URL",
    fieldApiKey: "API Key",
    fieldApiKeyPlaceholder: "sk-… (leave empty for dev-mode)",
    fieldAuthScheme: "Auth scheme",
    fieldDefaultModel: "Default model",
    fieldTimeout: "Timeout (ms)",
    fieldShowKey: "Show key",
    fieldHideKey: "Hide key",
    fieldCustomHeaders: "Custom headers",
    fieldCustomHeadersDesc: "Optional. e.g. X-Org-Id, OpenAI-Organization, Anthropic-Version",
    fieldHeaderKey: "Header",
    fieldHeaderValue: "Value",
    fieldHeaderAdd: "Add header",
    fieldHeaderRemove: "Remove",
    testButton: "Test Connection",
    testRunning: "Testing…",
    testOk: "Connection OK",
    testFail: "Connection failed",
    testHint: 'Click "Test" to verify backend reachability, auth and capabilities.',
    testLatency: "Latency",
    testStatus: "Status",
    testVersion: "Backend",
    testApiVersion: "API",
    testPython: "Python",
    testUptime: "Uptime",
    testModelsCount: "Models",
    testToolsCount: "Tools",
    testCapabilities: "Capabilities",
    testCapabilitiesNone: "(none reported)",
    testNoDiagnostic: "No diagnostic yet.",
    testSavedOk: "Connection settings saved.",
    providerDataAi: "DATA-AI (built-in)",
    providerCustom: "Custom OpenAI-compatible",
    authBearer: "Bearer (Authorization)",
    authXApiKey: "x-api-key header",
    authNone: "No auth (dev/ollama)",
    profileReset: "Reset to defaults",
    profileResetConfirm: "Reset all settings? This clears profiles and preferences.",
    ok: "OK",
    fail: "Failed",
  },
  welcome: "Welcome to DATA-AI",
};

const ZH: Catalog = {
  common: {
    appName: "DATA-AI",
    tagline: "生产级 AI 智能体框架",
    save: "保存",
    cancel: "取消",
    delete: "删除",
    edit: "编辑",
    create: "创建",
    refresh: "刷新",
    search: "搜索",
    loading: "加载中…",
    confirm: "确认",
    yes: "是",
    no: "否",
    online: "在线",
    offline: "离线",
    degraded: "降级",
    checking: "检查中…",
    health: "健康状态",
    language: "语言",
    theme: "主题",
    light: "浅色",
    dark: "深色",
    system: "跟随系统",
    settings: "设置",
    back: "返回",
    next: "下一步",
    done: "完成",
    error: "错误",
    success: "成功",
    warning: "警告",
    info: "提示",
    noData: "暂无数据",
    untitled: "未命名",
    unknown: "未知",
    sessions: "会话",
    session: "会话",
  },
  nav: {
    overview: "总览",
    overviewDashboard: "仪表盘",
    overviewDashboardDesc: "系统状态与最近活动",
    convoAndAgents: "对话与智能体",
    chat: "聊天工作台",
    chatDesc: "多模型流式对话",
    agents: "智能体",
    agentsDesc: "单智能体配置与运行",
    team: "智能体团队",
    teamDesc: "多智能体协作与共识",
    capabilities: "能力",
    tools: "工具广场",
    toolsDesc: "30+ 工具的浏览与试运行",
    sandbox: "代码沙箱",
    sandboxDesc: "在线执行与文件管理",
    rag: "知识库 RAG",
    ragDesc: "文档检索与引用追踪",
    memory: "记忆系统",
    memoryDesc: "短期/长期记忆",
    skills: "技能市场",
    skillsDesc: "技能定义与执行",
    mcp: "MCP 服务",
    mcpDesc: "Model Context Protocol 接入",
    office: "办公与文件",
    officeWord: "Word",
    officeWordDesc: "Word 文档处理",
    officePpt: "PPT",
    officePptDesc: "演示文稿生成",
    officeExcel: "Excel",
    officeExcelDesc: "电子表格分析",
    officePdf: "PDF",
    officePdfDesc: "PDF 读写合并",
    system: "系统",
    notifications: "通知",
    notificationsDesc: "系统事件与告警",
    models: "模型管理",
    modelsDesc: "模型注册与测试",
    settingsDesc: "API Key / 主题 / 语言",
    governance: "企业治理",
    audit: "审计日志",
    auditDesc: "合规追溯与取证",
    quota: "配额用量",
    quotaDesc: "限流与成本控制",
    webhooks: "Webhook 集成",
    webhooksDesc: "出站事件订阅",
    scheduler: "定时任务",
    schedulerDesc: "Cron 调度与自动化",
    enterprise: "企业级",
    tenants: "多租户",
    tenantsDesc: "租户隔离与配额",
    rbac: "角色权限",
    rbacDesc: "RBAC 角色与 ABAC 策略",
    billing: "成本中心",
    billingDesc: "定价、预算、发票",
    sla: "SLA 与状态",
    slaDesc: "SLO 评估、事件、状态页",
    sso: "SSO / IdP",
    ssoDesc: "OIDC / SAML / SCIM 集成",
    residency: "数据驻留",
    residencyDesc: "区域路由与合规",
    auditChain: "审计链",
    auditChainDesc: "Merkle 根防篡改",
    replication: "跨区复制",
    replicationDesc: "复制流、延迟、灾备切换",
    recovery: "备份与恢复",
    recoveryDesc: "计划、恢复点、DR 演练",
    compensation: "SLA 赔付",
    compensationDesc: "违约检测、credit 算、争议",
    collapse: "折叠侧边栏",
    openMenu: "打开菜单",
    closeMenu: "关闭菜单",
  },
  mobile: {
    chat: "聊天",
    agents: "智能体",
    tools: "工具",
    sandbox: "沙箱",
    rag: "知识库",
    settings: "设置",
  },
  search: {
    placeholder: "搜索页面、工具、设置…",
    title: "搜索",
    description: "跨页面快速跳转到工具、设置、对话等。",
    noResults: "无匹配结果",
  },
  status: {
    healthy: "正常",
    degraded: "降级",
    down: "离线",
    checking: "检测中…",
  },
  provider: {
    openai: "OpenAI",
    anthropic: "Anthropic",
    google: "Google Gemini",
    azure: "Azure OpenAI",
    aws: "AWS Bedrock",
    deepseek: "DeepSeek (深度求索)",
    siliconflow: "SiliconFlow (硅基流动)",
    qwen: "通义千问 Qwen",
    dashscope: "阿里 DashScope (灵积)",
    zhipu: "智谱 GLM",
    moonshot: "月之暗面 Moonshot (Kimi)",
    yi: "零一万物 Yi",
    baichuan: "百川智能",
    doubao: "字节豆包 Doubao",
    stepfun: "阶跃星辰 StepFun",
    ollama: "Ollama (本地)",
    vllm: "vLLM (本地)",
    lmstudio: "LM Studio (本地)",
    offline: "内置离线占位",
  },
  settings: {
    title: "设置",
    tabsOverview: "总览",
    tabsConnection: "连接",
    tabsAppearance: "外观",
    tabsBehavior: "行为",
    tabsAbout: "关于",
    sectionConnection: "连接配置",
    sectionProvider: "Provider",
    sectionProfile: "当前连接",
    sectionProfiles: "Profile 列表",
    sectionTest: "测试与诊断",
    sectionExport: "备份与恢复",
    profilesTitle: "连接 Profile",
    profilesDesc: "在多个 Provider 之间快速切换。当前激活的 Profile 用于所有 API 调用。",
    profileName: "Profile 名称",
    profileActive: "当前激活",
    profileAdd: "新建 Profile",
    profileDuplicate: "复制",
    profileDelete: "删除",
    profileDeleteConfirm: "确认删除该 Profile?",
    profileImport: "导入",
    profileExport: "导出",
    profileImportOk: "已导入 {n} 个 Profile。",
    profileImportErr: "Profile JSON 格式无效。",
    fieldProvider: "Provider 预设",
    fieldBaseUrl: "Base URL",
    fieldApiKey: "API Key",
    fieldApiKeyPlaceholder: "sk-… (留空使用 dev-mode)",
    fieldAuthScheme: "鉴权方式",
    fieldDefaultModel: "默认模型",
    fieldTimeout: "超时 (ms)",
    fieldShowKey: "显示 Key",
    fieldHideKey: "隐藏 Key",
    fieldCustomHeaders: "自定义请求头",
    fieldCustomHeadersDesc: "可选。如 X-Org-Id, OpenAI-Organization, Anthropic-Version 等。",
    fieldHeaderKey: "Header 名",
    fieldHeaderValue: "Header 值",
    fieldHeaderAdd: "添加 Header",
    fieldHeaderRemove: "删除",
    testButton: "测试连接",
    testRunning: "测试中…",
    testOk: "连接正常",
    testFail: "连接失败",
    testHint: "点击「测试」验证后端可达性、鉴权与能力列表。",
    testLatency: "延迟",
    testStatus: "状态",
    testVersion: "后端版本",
    testApiVersion: "API 版本",
    testPython: "Python",
    testUptime: "运行时长",
    testModelsCount: "模型数",
    testToolsCount: "工具数",
    testCapabilities: "能力",
    testCapabilitiesNone: "（后端未报告）",
    testNoDiagnostic: "尚未测试。",
    testSavedOk: "连接设置已保存。",
    providerDataAi: "DATA-AI (本项目)",
    providerCustom: "自定义 OpenAI 兼容",
    authBearer: "Bearer (Authorization)",
    authXApiKey: "x-api-key 请求头",
    authNone: "无鉴权 (dev/ollama)",
    profileReset: "重置全部",
    profileResetConfirm: "确认重置所有设置？这会清空 Profile 与偏好。",
    ok: "成功",
    fail: "失败",
  },
  welcome: "欢迎使用 DATA-AI",
};

const CATALOGS: Record<Locale, Catalog> = { en: EN, zh: ZH };

/* ---------- Locale state ---------- */

let memoryLocale: Locale | null = null;

function readPersisted(): Locale | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (raw && (SUPPORTED_LOCALES as string[]).includes(raw)) return raw as Locale;
  } catch {
    // ignore
  }
  return null;
}

function readBrowserLocale(): Locale {
  if (typeof navigator === "undefined") return DEFAULT_LOCALE;
  const lang = (navigator.language || "en").toLowerCase();
  return lang.startsWith("zh") ? "zh" : DEFAULT_LOCALE;
}

function detectInitial(): Locale {
  const persisted = readPersisted();
  if (persisted) return persisted;
  try {
    const s = useSettings.getState().language as Locale | undefined;
    if (s && SUPPORTED_LOCALES.includes(s)) return s;
  } catch {
    // ignore
  }
  return readBrowserLocale();
}

export function initI18n(): Locale {
  if (memoryLocale) return memoryLocale;
  memoryLocale = detectInitial();
  if (typeof document !== "undefined") {
    document.documentElement.lang = memoryLocale === "zh" ? "zh-CN" : "en";
  }
  return memoryLocale;
}

export function getLocale(): Locale {
  return memoryLocale ?? initI18n();
}

export function setLocale(locale: Locale): void {
  if (!SUPPORTED_LOCALES.includes(locale)) return;
  memoryLocale = locale;
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    // also persist into settings
    useSettings.getState().set({ language: locale });
  } catch {
    // ignore
  }
  if (typeof document !== "undefined") {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: locale }));
  }
}

/** Lookup a dotted key like "common.save" against the current (or given) locale. */
export function t(key: string, locale?: Locale): string {
  const loc = locale ?? getLocale();
  const parts = key.split(".");
  let cur: unknown = CATALOGS[loc];
  for (const p of parts) {
    if (cur && typeof cur === "object" && p in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[p];
    } else {
      return key;
    }
  }
  return typeof cur === "string" ? cur : key;
}

function subscribe(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const handler = () => listener();
  window.addEventListener(CHANGE_EVENT, handler);
  window.addEventListener("storage", handler);
  return () => {
    window.removeEventListener(CHANGE_EVENT, handler);
    window.removeEventListener("storage", handler);
  };
}

function getSnapshot(): Locale {
  return getLocale();
}

function getServerSnapshot(): Locale {
  return DEFAULT_LOCALE;
}

/** React hook returning `{ t, locale, setLocale }`. */
export function useT() {
  // ensure detection has run at least once
  if (!memoryLocale) initI18n();
  const locale = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return {
    t: (key: string) => t(key, locale),
    locale,
    setLocale,
  };
}

/** Returns just the current locale (lightweight). */
export function useLocale(): Locale {
  if (!memoryLocale) initI18n();
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
