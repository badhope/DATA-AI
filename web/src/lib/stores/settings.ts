/**
 * 全局设置 Store - 多 Profile 连接管理 + 主题/语言/行为偏好
 *
 * 设计参考：
 * - Lobe Chat / Open WebUI / LibreChat 的多 Provider 配置
 * - TypingMind 的 Connection Profile 切换
 * - ChatGPT-Next-Web 的连接测试 + 错误诊断
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemeMode = "dark" | "light" | "system";
export type Language = "zh" | "en";
export type LogLevel = "debug" | "info" | "warn" | "error";

/** Provider 预设：决定默认 baseUrl + 默认 auth scheme */
export type ProviderPreset =
  | "data-ai" // DATA-AI FastAPI（默认）
  | "openai" // OpenAI
  | "anthropic" // Anthropic Claude
  | "deepseek" // DeepSeek
  | "siliconflow" // SiliconFlow（DeepSeek/Qwen 代理）
  | "qwen" // 通义千问 DashScope（OpenAI 兼容）
  | "moonshot" // Moonshot Kimi
  | "zhipu" // 智谱 GLM
  | "yi" // 零一万物
  | "google" // Google Gemini
  | "ollama" // 本地 Ollama
  | "custom"; // 自定义 OpenAI 兼容端点

/** 鉴权方案 */
export type AuthScheme = "bearer" | "x-api-key" | "none";

/** 自定义请求头（用于 proxy / org-id / X-Locale 等） */
export interface CustomHeader {
  id: string;
  key: string;
  value: string;
  enabled: boolean;
}

/** 单个连接配置 */
export interface ConnectionProfile {
  id: string;
  name: string;
  provider: ProviderPreset;
  baseUrl: string;
  apiKey: string;
  authScheme: AuthScheme;
  customHeaders: CustomHeader[];
  defaultModel: string;
  /** 测试延迟上限（ms）— 防止长时间挂起 */
  timeoutMs: number;
  createdAt: number;
  updatedAt: number;
}

/** 连接测试结果（UI 直接展示） */
export interface DiagnosticResult {
  ok: boolean;
  status: number;
  latencyMs: number;
  version?: string;
  apiVersion?: string;
  modelsCount?: number;
  toolsCount?: number;
  capabilities?: string[];
  uptimeMs?: number;
  python?: string;
  error?: string;
  detail?: unknown;
  testedAt: number;
}

interface SettingsState {
  /* 兼容老字段：保持旧 localStorage key 工作 */
  apiKey: string;
  baseUrl: string;
  theme: ThemeMode;
  language: Language;
  logLevel: LogLevel;
  autoScroll: boolean;
  showTokenUsage: boolean;
  saveHistory: boolean;
  enableAutoTitle: boolean;

  /* 新字段：多 Profile */
  profiles: ConnectionProfile[];
  activeProfileId: string;
  diagnostic: DiagnosticResult | null;
  diagnosticLoading: boolean;

  /* Actions */
  set: (partial: Partial<SettingsState>) => void;
  reset: () => void;
  addProfile: (patch?: Partial<ConnectionProfile>) => string;
  updateProfile: (id: string, patch: Partial<ConnectionProfile>) => void;
  deleteProfile: (id: string) => void;
  setActiveProfile: (id: string) => void;
  duplicateProfile: (id: string) => string;
  setDiagnostic: (d: DiagnosticResult | null) => void;
  setDiagnosticLoading: (loading: boolean) => void;
  importProfiles: (profiles: ConnectionProfile[], activeId: string) => void;
}

/* ─── Provider 预设表 ─── */
export const PROVIDER_PRESETS: Record<
  ProviderPreset,
  { label: string; baseUrl: string; authScheme: AuthScheme; defaultModel: string }
> = {
  "data-ai": {
    label: "DATA-AI (本项目)",
    baseUrl: "http://localhost:8000",
    authScheme: "bearer",
    defaultModel: "offline-chat",
  },
  openai: {
    label: "OpenAI",
    baseUrl: "https://api.openai.com/v1",
    authScheme: "bearer",
    defaultModel: "gpt-4o-mini",
  },
  anthropic: {
    label: "Anthropic Claude",
    baseUrl: "https://api.anthropic.com/v1",
    authScheme: "x-api-key",
    defaultModel: "claude-3-5-sonnet-20241022",
  },
  deepseek: {
    label: "DeepSeek",
    baseUrl: "https://api.deepseek.com/v1",
    authScheme: "bearer",
    defaultModel: "deepseek-chat",
  },
  siliconflow: {
    label: "SiliconFlow",
    baseUrl: "https://api.siliconflow.cn/v1",
    authScheme: "bearer",
    defaultModel: "deepseek-ai/DeepSeek-V2.5",
  },
  qwen: {
    label: "通义千问 (阿里百炼 DashScope)",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    authScheme: "bearer",
    // qwen-turbo/qwen-plus free tier 容易触顶 → 改用 qwen3.7-plus（仍可用）
    defaultModel: "qwen3.7-plus",
  },
  moonshot: {
    label: "Moonshot Kimi",
    baseUrl: "https://api.moonshot.cn/v1",
    authScheme: "bearer",
    defaultModel: "moonshot-v1-32k",
  },
  zhipu: {
    label: "智谱 GLM",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    authScheme: "bearer",
    defaultModel: "glm-4-flash",
  },
  yi: {
    label: "零一万物",
    baseUrl: "https://api.lingyiwanwu.com/v1",
    authScheme: "bearer",
    defaultModel: "yi-medium",
  },
  google: {
    label: "Google Gemini",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    authScheme: "bearer",
    defaultModel: "gemini-1.5-flash",
  },
  ollama: {
    label: "Ollama (本地)",
    baseUrl: "http://localhost:11434/v1",
    authScheme: "none",
    defaultModel: "llama3.1",
  },
  custom: {
    label: "自定义 OpenAI 兼容",
    baseUrl: "http://localhost:8000/v1",
    authScheme: "bearer",
    defaultModel: "",
  },
};

/* ─── ID 生成（前端无 crypto.randomUUID 时用） ─── */
function genId(prefix = "p"): string {
  try {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`;
  } catch {
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  }
}

function nowMs(): number {
  return Date.now();
}

/* ─── 默认 Profile（首次启动用） ─── */
function makeDefaultProfile(): ConnectionProfile {
  return {
    id: genId("p"),
    name: "DATA-AI Local",
    provider: "data-ai",
    // 默认走 vite dev proxy (`5173/api` → 8000)，避开 CORS。
    // 生产部署时可改回 `http://localhost:8000`。
    baseUrl:
      typeof window !== "undefined" && window.location.port === "5173"
        ? `${window.location.origin}/api`
        : "http://localhost:8000",
    // 留空：dev mode 后端 (DATA_AI_DEV_MODE=true) 接受无 key 请求；
    // 生产部署时用户应在设置里填实际 key。
    apiKey: "",
    authScheme: "bearer",
    customHeaders: [],
    defaultModel: "offline-chat",
    timeoutMs: 8000,
    createdAt: nowMs(),
    updatedAt: nowMs(),
  };
}

const DEFAULT_PROFILE = makeDefaultProfile();

const DEFAULTS: Omit<
  SettingsState,
  | "set"
  | "reset"
  | "addProfile"
  | "updateProfile"
  | "deleteProfile"
  | "setActiveProfile"
  | "duplicateProfile"
  | "setDiagnostic"
  | "setDiagnosticLoading"
  | "importProfiles"
> = {
  apiKey: DEFAULT_PROFILE.apiKey,
  baseUrl: DEFAULT_PROFILE.baseUrl,
  theme: "dark",
  language: "zh",
  logLevel: "info",
  autoScroll: true,
  showTokenUsage: true,
  saveHistory: true,
  enableAutoTitle: true,
  profiles: [DEFAULT_PROFILE],
  activeProfileId: DEFAULT_PROFILE.id,
  diagnostic: null,
  diagnosticLoading: false,
};

/**
 * 持久化 store。v1 → v2 升级时把老 apiKey/baseUrl 合并到默认 profile 里。
 */
export const useSettings = create<SettingsState>()(
  persist(
    (set, get) => ({
      ...DEFAULTS,
      set: (partial) => set(partial),
      reset: () => set(DEFAULTS),
      addProfile: (patch) => {
        const id = genId("p");
        const preset = patch?.provider ? PROVIDER_PRESETS[patch.provider] : null;
        const profile: ConnectionProfile = {
          id,
          name: patch?.name || `Profile ${get().profiles.length + 1}`,
          provider: patch?.provider || "custom",
          baseUrl: patch?.baseUrl || preset?.baseUrl || "http://localhost:8000",
          apiKey: patch?.apiKey || "",
          authScheme: patch?.authScheme || preset?.authScheme || "bearer",
          customHeaders: patch?.customHeaders || [],
          defaultModel: patch?.defaultModel || preset?.defaultModel || "",
          timeoutMs: patch?.timeoutMs || 8000,
          createdAt: nowMs(),
          updatedAt: nowMs(),
        };
        set({ profiles: [...get().profiles, profile] });
        return id;
      },
      updateProfile: (id, patch) => {
        const profiles = get().profiles.map((p) =>
          p.id === id ? { ...p, ...patch, id: p.id, updatedAt: nowMs() } : p,
        );
        set({ profiles });
        // 同步老字段（active profile）
        if (id === get().activeProfileId) {
          const cur = profiles.find((p) => p.id === id);
          if (cur) set({ baseUrl: cur.baseUrl, apiKey: cur.apiKey });
        }
      },
      deleteProfile: (id) => {
        const profiles = get().profiles.filter((p) => p.id !== id);
        let activeProfileId = get().activeProfileId;
        if (activeProfileId === id) {
          activeProfileId = profiles[0]?.id || "";
        }
        set({ profiles, activeProfileId });
      },
      setActiveProfile: (id) => {
        const cur = get().profiles.find((p) => p.id === id);
        if (!cur) return;
        set({
          activeProfileId: id,
          baseUrl: cur.baseUrl,
          apiKey: cur.apiKey,
          diagnostic: null, // 切换后清空旧诊断
        });
      },
      duplicateProfile: (id) => {
        const src = get().profiles.find((p) => p.id === id);
        if (!src) return "";
        const newId = genId("p");
        const copy: ConnectionProfile = {
          ...src,
          id: newId,
          name: `${src.name} (副本)`,
          createdAt: nowMs(),
          updatedAt: nowMs(),
        };
        set({ profiles: [...get().profiles, copy] });
        return newId;
      },
      setDiagnostic: (d) => set({ diagnostic: d }),
      setDiagnosticLoading: (loading) => set({ diagnosticLoading: loading }),
      importProfiles: (profiles, activeId) => {
        set({ profiles, activeProfileId: activeId });
      },
    }),
    {
      name: "data-ai-settings-v2",
      version: 2,
      // v1 → v2: 把老 apiKey/baseUrl 合并到默认 profile
      migrate: (persistedState: unknown, fromVersion: number) => {
        const s = (persistedState || {}) as Record<string, unknown>;
        if (fromVersion < 2) {
          // 旧的 v1 字段 + 兼容 CORS：dev 模式下 baseUrl 必须走 vite proxy (/api)
          let baseUrl = (s.baseUrl as string) || DEFAULT_PROFILE.baseUrl;
          const isDevPort = typeof window !== "undefined" && window.location.port === "5173";
          if (isDevPort && /^https?:\/\/localhost:8000\/?$/.test(baseUrl.replace(/\/+$/, ""))) {
            baseUrl = `${window.location.origin}/api`;
          }
          const apiKey = (s.apiKey as string) || DEFAULT_PROFILE.apiKey;
          const oldProfile: ConnectionProfile = {
            ...DEFAULT_PROFILE,
            id: genId("p"),
            name: "Migrated",
            baseUrl,
            apiKey,
            updatedAt: nowMs(),
          };
          return {
            ...DEFAULTS,
            ...s,
            baseUrl, // 同步老字段
            apiKey,
            profiles: [oldProfile],
            activeProfileId: oldProfile.id,
            diagnostic: null,
          };
        }
        return s as unknown as SettingsState;
      },
    },
  ),
);

/** 只读当前激活的 profile（注意非响应式，组件内用 useSettings()） */
export function getActiveProfile(): ConnectionProfile | null {
  const s = useSettings.getState();
  return s.profiles.find((p) => p.id === s.activeProfileId) || s.profiles[0] || null;
}

/** 兼容老 getSettings：取当前 active profile 的 baseUrl/apiKey（没有则返回空字符串，绝不返回 "dev-mode"） */
export function getSettings(): Pick<SettingsState, "apiKey" | "baseUrl"> {
  const cur = getActiveProfile();
  return {
    apiKey: cur?.apiKey ?? "",
    baseUrl: cur?.baseUrl ?? "http://localhost:8000",
  };
}
