import { type Locale, getLocale } from "@/lib/i18n";
import { getActiveProfile, getSettings } from "@/lib/stores/settings";
import type {
  AgentConfig,
  AgentCreateRequest,
  AgentRunRequest,
  AgentRunResponse,
  AgentRunsListResponse,
  AgentUpdateRequest,
  AgentsListResponse,
  Assignment,
  AssignmentCreateRequest,
  AuditChainBlock,
  AuditChainIntegrity,
  AuditChainProof,
  AuditEntry,
  AuditStats,
  BackupRecord,
  BackupSchedule,
  BackupType,
  BackupStatus,
  BillingSummary,
  BreachEvent,
  BreachSeverity,
  Budget,
  BudgetAlert,
  BudgetCreate,
  ChatCompletionRequest,
  ChatCompletionResponse,
  ConsensusMethod,
  CompensationPolicy,
  CompensationStats,
  CompensationTier,
  CostCenter,
  CostCenterCreate,
  CostDaySeries,
  Credit,
  CreditStatus,
  DataClass,
  Decision,
  Dispute,
  DisputeStatus,
  DRDrill,
  DrillResult,
  ExcelAnalyzePayload,
  ExcelAnalyzeResponse,
  ExcelChartPayload,
  ExcelChartResponse,
  ExcelReadPayload,
  ExcelReadResponse,
  ExcelWritePayload,
  ExcelWriteResponse,
  ExtensionsHealthResponse,
  HealthResponse,
  FailoverEvent,
  FailoverMode,
  FailoverState,
  IdentityProvider,
  IdentityProviderCreate,
  IdpType,
  Incident,
  IncidentCreate,
  IncidentUpdate,
  JobCreate,
  JobExecution,
  JobStats,
  MCPHealthResponse,
  MCPInvokeRequest,
  MCPInvokeResponse,
  MCPPreset,
  MCPPresetsListResponse,
  MCPServer,
  MCPServerCreateRequest,
  MCPServersListResponse,
  MCPTool,
  MCPToolsAllResponse,
  MCPToolsListResponse,
  MemberRole,
  MemoriesListResponse,
  MemoryCreateRequest,
  MemoryItem,
  MemorySearchRequest,
  MemorySearchResponse,
  MemoryType,
  MemoryUpdateRequest,
  ModelsResponse,
  Notification,
  NotificationsListResponse,
  PdfMergePayload,
  PdfMergeResponse,
  PdfReadPayload,
  PdfReadResponse,
  PdfSplitPayload,
  PdfSplitResponse,
  PlanTier,
  Policy,
  PolicyCreateRequest,
  PptReadPayload,
  PptReadResponse,
  PptWritePayload,
  PptWriteResponse,
  PricingModel,
  PricingModelCreate,
  QuotaActorStatus,
  QuotaPolicy,
  QuotaPolicyCreate,
  QuotaSummary,
  RagDocDetailResponse,
  RagDocsListResponse,
  RagDocument,
  RagSearchRequest,
  RagSearchResponse,
  RagSearchResult,
  RbacCheckRequest,
  ReplicaStream,
  RecoveryStats,
  ReplicationMode,
  ReplicationPolicy,
  ReplicationStats,
  Region,
  RegionCreate,
  ResidencyAssignment,
  ResidencyPolicy,
  ResidencyPolicyCreate,
  ResidencyRouteRequest,
  ResidencyStats,
  RestoreJob,
  RestoreStatus,
  RetentionHold,
  Role,
  RBACRole,
  RoleCreateRequest,
  SandboxCreateRequest,
  SandboxExecuteRequest,
  SandboxExecuteResponse,
  SandboxFileContent,
  SandboxFileNode,
  SandboxInfo,
  SandboxSnapshot,
  SandboxesListResponse,
  ScheduledJob,
  SchedulePayload,
  SCIMUser,
  SCIMUserCreate,
  SessionHistoryListResponse,
  SLAComponent,
  SLAMonthlyReport,
  SLAStatusPage,
  SLIProbe,
  SLIProbeCreate,
  SLO,
  SLOCreate,
  SLOResult,
  StreamState,
  SSOLoginResult,
  SSOSession,
  Skill,
  SkillCreateRequest,
  SkillExecuteRequest,
  SkillExecuteResponse,
  SkillExtractionRequest,
  SkillExtractionResponse,
  SkillsListResponse,
  TeamConfig,
  TeamCreateRequest,
  TeamMember,
  TeamMessage,
  TeamMode,
  TeamRunRequest,
  TeamRunResponse,
  TeamsListResponse,
  Tenant,
  TenantCreateRequest,
  TenantMember,
  TenantStats,
  TenantUpdateRequest,
  Tool,
  ToolExecuteRequest,
  ToolExecuteResponse,
  ToolsListResponse,
  TopSpender,
  UsageRecord,
  UsageRecordCreate,
  WebhookCreate,
  WebhookDelivery,
  WebhookSubscription,
  WordEditPayload,
  WordEditResponse,
  WordReadPayload,
  WordReadResponse,
  WordTemplatePayload,
  WordTemplateResponse,
  WordWritePayload,
  WordWriteResponse,
} from "@/lib/types/api";

// 后端别名兼容：把"Payload"形式映射到"Request"形式
export type RagSearchPayload = RagSearchRequest;
export type TeamRunPayload = TeamRunRequest;

/**
 * 读当前 i18n locale 并生成要发给后端的语言头。
 * - X-Locale: 强信号（后端优先用它）
 * - Accept-Language: 标准化头，兼容没有 X-Locale 的中间件
 */
function localeHeaders(): Record<string, string> {
  const locale: Locale = (getLocale?.() as Locale) ?? "en";
  // Accept-Language 用规范 tag：zh → zh-CN, en → en
  const accept = locale === "zh" ? "zh-CN,zh;q=0.9" : "en-US,en;q=0.9";
  return {
    "X-Locale": locale,
    "Accept-Language": accept,
  };
}

export type APIErrorCode =
  | "ABORTED"
  | "TIMEOUT"
  | "NETWORK"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "VALIDATION"
  | "RATE_LIMIT"
  | "CONFLICT"
  | "SERVER"
  | "PARSER"
  | "UNKNOWN";

export class APIError extends Error {
  status: number;
  detail?: unknown;
  code: APIErrorCode;
  retryable: boolean;
  constructor(
    status: number,
    message: string,
    detail?: unknown,
    opts: { code?: APIErrorCode; retryable?: boolean } = {},
  ) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.detail = detail;
    this.code = opts.code ?? inferCode(status, message);
    this.retryable =
      opts.retryable ??
      (this.code === "SERVER" ||
        this.code === "RATE_LIMIT" ||
        this.code === "TIMEOUT" ||
        this.code === "NETWORK");
  }
}

function inferCode(status: number, message: string): APIErrorCode {
  if (status === 0)
    return /timeout/i.test(message)
      ? "TIMEOUT"
      : /stop|abort/i.test(message)
        ? "ABORTED"
        : "NETWORK";
  if (status === 401) return "UNAUTHORIZED";
  if (status === 403) return "FORBIDDEN";
  if (status === 404) return "NOT_FOUND";
  if (status === 409) return "CONFLICT";
  if (status === 429) return "RATE_LIMIT";
  if (status >= 400 && status < 500) return "VALIDATION";
  if (status >= 500) return "SERVER";
  return "UNKNOWN";
}

type FetchOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | object | null;
  params?: Record<string, string | number | boolean | undefined | null>;
};

async function request<T = unknown>(
  path: string,
  options: FetchOptions = {},
  extra: { timeoutMs?: number; profileId?: string } = {},
): Promise<T> {
  const { apiKey, baseUrl } = getSettings();
  const profile = getActiveProfile();
  let url = `${baseUrl.replace(/\/$/, "")}${path}`;
  // 把 params 拼到 URL
  if (options.params) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(options.params)) {
      if (v === undefined || v === null) continue;
      sp.set(k, String(v));
    }
    const qs = sp.toString();
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }
  const headers = new Headers(options.headers);

  // 鉴权：按 authScheme 决定 (bearer / x-api-key)
  if (apiKey) {
    const scheme = profile?.authScheme || "bearer";
    if (scheme === "x-api-key") {
      headers.set("x-api-key", apiKey);
    } else {
      headers.set("Authorization", `Bearer ${apiKey}`);
    }
  }
  // 自定义请求头
  for (const h of profile?.customHeaders || []) {
    if (h && h.enabled && h.key && h.value) headers.set(h.key, h.value);
  }

  // i18n: 注入当前 locale 到 X-Locale + Accept-Language
  const lh = localeHeaders();
  if (!headers.has("X-Locale")) headers.set("X-Locale", lh["X-Locale"]);
  if (!headers.has("Accept-Language")) headers.set("Accept-Language", lh["Accept-Language"]);

  let body: BodyInit | undefined;
  if (options.body !== undefined && options.body !== null) {
    if (options.body instanceof FormData) {
      body = options.body as unknown as BodyInit;
    } else if (typeof options.body === "string") {
      body = options.body as BodyInit;
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
    } else {
      body = JSON.stringify(options.body);
      if (!headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
    }
  }

  const init: RequestInit = { method: options.method ?? "GET" };
  if (options.cache !== undefined) init.cache = options.cache;
  if (options.credentials !== undefined) init.credentials = options.credentials;
  if (options.mode !== undefined) init.mode = options.mode;
  if (options.redirect !== undefined) init.redirect = options.redirect;
  if (body !== undefined) init.body = body;
  init.headers = headers;

  // 超时控制：合并外部 signal 与内部 AbortController
  const timeout = extra.timeoutMs || profile?.timeoutMs || 30000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  if (options.signal) {
    options.signal.addEventListener("abort", () => controller.abort());
  }
  init.signal = controller.signal;

  // P1-7: 自动重试 — 只重试 retryable 错误 (5xx / NETWORK / TIMEOUT)
  // 不重试 4xx (用户错误) 和 ABORTED
  const method = (options.method ?? "GET").toUpperCase();
  const RETRYABLE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);  // 写操作不重试
  const MAX_RETRIES = 3;
  let attempt = 0;
  let lastErr: APIError | null = null;

  while (attempt <= MAX_RETRIES) {
    let res: Response;
    try {
      res = await fetch(url, init);
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof DOMException && e.name === "AbortError") {
        const isUserAbort = options.signal?.aborted === true;
        if (isUserAbort) {
          throw new APIError(0, "请求已停止", undefined, { code: "ABORTED", retryable: false });
        }
        // P1-7: 超时也重试
        const err = new APIError(0, `请求超时 (${timeout}ms): ${url}`, undefined, { code: "TIMEOUT" });
        if (err.retryable && attempt < MAX_RETRIES && RETRYABLE_METHODS.has(method)) {
          attempt++;
          await new Promise((r) => setTimeout(r, Math.min(2 ** attempt * 200, 3000)));
          continue;
        }
        throw err;
      }
      const msg = (e as Error).message || String(e);
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        throw new APIError(0, "浏览器已离线", undefined, { code: "NETWORK" });
      }
      // P1-7: 网络错误也重试
      const err = new APIError(0, `网络错误: ${msg}`, undefined, { code: "NETWORK" });
      if (err.retryable && attempt < MAX_RETRIES && RETRYABLE_METHODS.has(method)) {
        attempt++;
        await new Promise((r) => setTimeout(r, Math.min(2 ** attempt * 200, 3000)));
        continue;
      }
      throw err;
    }
    clearTimeout(timer);

    if (res.status === 204) return undefined as T;
    const text = await res.text();
    let json: unknown = null;
    if (text) {
      try {
        json = JSON.parse(text);
      } catch {
        json = text;
      }
    }
    if (!res.ok) {
      const errObj =
        json && typeof json === "object" && "error" in (json as object)
          ? (json as { error: unknown }).error
          : null;
      const detail =
        errObj && typeof errObj === "object" && "detail" in (errObj as object)
          ? (errObj as { detail: unknown }).detail
          : json && typeof json === "object" && "detail" in (json as object)
            ? (json as { detail: unknown }).detail
            : json;
      const message = (typeof detail === "string" ? detail : res.statusText) || "Request failed";
      // P1-7: 提取后端 trace_id 和 fix 建议
      const traceId =
        errObj && typeof errObj === "object" && "trace_id" in (errObj as object)
          ? String((errObj as { trace_id: unknown }).trace_id)
          : undefined;
      const fixHint =
        errObj && typeof errObj === "object" && "fix" in (errObj as object)
          ? String((errObj as { fix: unknown }).fix)
          : undefined;
      const enrichedMessage = fixHint ? `${message}\n\n💡 ${fixHint}${traceId ? `\n🔍 trace_id: ${traceId}` : ""}` : message;
      lastErr = new APIError(res.status, enrichedMessage, detail ?? errObj);
      // P1-7: 5xx 自动重试, 4xx 不重试
      if (lastErr.retryable && attempt < MAX_RETRIES && RETRYABLE_METHODS.has(method)) {
        attempt++;
        await new Promise((r) => setTimeout(r, Math.min(2 ** attempt * 200, 3000)));
        continue;
      }
      throw lastErr;
    }
    return json as T;
  }
  // 兜底 — 不应该到这里
  throw lastErr ?? new APIError(0, "请求失败", undefined);
}

export interface ChatStreamChunk {
  choices: Array<{
    delta: {
      content?: string;
      tool_calls?: Array<{
        index?: number;
        id?: string;
        function?: { name?: string; arguments?: string };
      }>;
    };
    finish_reason?: string | null;
  }>;
}

export const api = {
  /* ---------- System ---------- */

  health: () => request<HealthResponse>("/health"),
  extensionsHealth: () => request<ExtensionsHealthResponse>("/v1/extensions/health"),

  /** 主动测连接 + 测延迟 + 解析 backend 元信息。返回 DiagnosticResult。 */
  testConnection: async (
    profile?: Partial<{
      baseUrl: string;
      apiKey: string;
      authScheme: "bearer" | "x-api-key" | "none";
    }>,
  ): Promise<{
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
  }> => {
    const t0 = performance.now();
    const baseUrl = (profile?.baseUrl || getSettings().baseUrl).replace(/\/+$/, "");
    const url = `${baseUrl}/v1/extensions/health`;
    const headers: Record<string, string> = {};
    if (profile?.apiKey) {
      if (profile.authScheme === "x-api-key") headers["x-api-key"] = profile.apiKey;
      else headers["Authorization"] = `Bearer ${profile.apiKey}`;
    } else {
      // 用当前 active profile 的 key
      const s = getSettings();
      if (s.apiKey) {
        const p = getActiveProfile();
        const scheme = profile?.authScheme || p?.authScheme || "bearer";
        if (scheme === "x-api-key") headers["x-api-key"] = s.apiKey;
        else headers["Authorization"] = `Bearer ${s.apiKey}`;
      }
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const res = await fetch(url, { method: "GET", headers, signal: controller.signal });
      const latencyMs = Math.round(performance.now() - t0);
      const text = await res.text();
      let json: Record<string, unknown> = {};
      try {
        json = text ? JSON.parse(text) : {};
      } catch {
        json = {};
      }
      if (!res.ok) {
        return {
          ok: false,
          status: res.status,
          latencyMs,
          error: typeof json?.detail === "string" ? json.detail : res.statusText,
          detail: json,
        };
      }
      return {
        ok: true,
        status: res.status,
        latencyMs,
        version: typeof json?.version === "string" ? json.version : undefined,
        apiVersion: typeof json?.api_version === "string" ? json.api_version : undefined,
        modelsCount: typeof json?.models_count === "number" ? json.models_count : undefined,
        toolsCount: typeof json?.tools_count === "number" ? json.tools_count : undefined,
        capabilities: Array.isArray(json?.capabilities) ? json.capabilities : undefined,
        uptimeMs: typeof json?.uptime_ms === "number" ? json.uptime_ms : undefined,
        python:
          typeof (json as { process?: { python?: string } })?.process?.python === "string"
            ? (json as { process: { python: string } }).process.python
            : undefined,
      };
    } catch (e) {
      const latencyMs = Math.round(performance.now() - t0);
      const isAbort = e instanceof DOMException && e.name === "AbortError";
      return {
        ok: false,
        status: 0,
        latencyMs,
        error: isAbort
          ? "连接超时 (8s)，请检查网络/URL/代理"
          : `网络错误: ${(e as Error)?.message || String(e)}`,
      };
    } finally {
      clearTimeout(timer);
    }
  },

  /* ---------- Models & Tools ---------- */

  listModels: () => request<ModelsResponse>("/v1/models"),
  listTools: () => request<ToolsListResponse>("/v1/tools"),
  executeTool: (payload: ToolExecuteRequest) =>
    request<ToolExecuteResponse>("/v1/tools/execute", {
      method: "POST",
      body: payload,
    }),

  /* ---------- Chat (OpenAI-compatible) ---------- */

  chatCompletion: (payload: ChatCompletionRequest) =>
    request<ChatCompletionResponse>("/v1/chat/completions", {
      method: "POST",
      body: payload,
    }),

  /**
   * 流式 chat completion (SSE)。
   * - 读 active profile 的 authScheme / customHeaders / baseUrl
   * - 接受外部 AbortSignal，真正支持"停止"按钮
   * - 错误时抛 APIError，便于 UI 用 toast 统一处理
   */
  async *chatCompletionStream(
    payload: ChatCompletionRequest,
    options: { signal?: AbortSignal; timeoutMs?: number } = {},
  ): AsyncGenerator<ChatStreamChunk> {
    const s = getSettings();
    const profile = getActiveProfile();
    const baseUrl = s.baseUrl.replace(/\/$/, "");
    const lh = localeHeaders();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      ...lh,
    };
    // 鉴权：按 profile.authScheme
    if (s.apiKey) {
      const scheme = profile?.authScheme || "bearer";
      if (scheme === "x-api-key") headers["x-api-key"] = s.apiKey;
      else if (scheme === "bearer") headers["Authorization"] = `Bearer ${s.apiKey}`;
      // scheme === "none" 时不发送任何鉴权头
    }
    // 自定义 headers
    for (const h of profile?.customHeaders || []) {
      if (h && h.enabled && h.key && h.value) headers[h.key] = h.value;
    }

    // 内部 AbortController + 外部 signal 合并（支持超时 + 主动停止）
    const ctl = new AbortController();
    const timeoutMs = options.timeoutMs || profile?.timeoutMs || 60000;
    const timer = setTimeout(() => ctl.abort(new DOMException("timeout", "AbortError")), timeoutMs);
    if (options.signal) {
      if (options.signal.aborted) ctl.abort(options.signal.reason);
      else
        options.signal.addEventListener("abort", () => ctl.abort(options.signal?.reason), {
          once: true,
        });
    }

    let res: Response;
    try {
      res = await fetch(`${baseUrl}/v1/chat/completions`, {
        method: "POST",
        headers,
        body: JSON.stringify({ ...payload, stream: true }),
        signal: ctl.signal,
      });
    } catch (e) {
      clearTimeout(timer);
      if (e instanceof DOMException && e.name === "AbortError") {
        const isUserAbort = options.signal?.aborted === true;
        if (isUserAbort) {
          throw new APIError(0, "请求已停止", undefined, { code: "ABORTED", retryable: false });
        }
        throw new APIError(0, `流式请求超时 (${timeoutMs}ms)`, undefined, { code: "TIMEOUT" });
      }
      const msg = (e as Error).message || String(e);
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        throw new APIError(0, "浏览器已离线", undefined, { code: "NETWORK" });
      }
      throw new APIError(0, `网络错误: ${msg}`, undefined, { code: "NETWORK" });
    }
    clearTimeout(timer);

    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => "");
      throw new APIError(res.status, text || res.statusText);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          const t = line.trim();
          if (!t || !t.startsWith("data:")) continue;
          const data = t.slice(5).trim();
          if (data === "[DONE]") return;
          try {
            const obj = JSON.parse(data) as ChatStreamChunk;
            if (!obj.choices?.[0] && !obj.choices?.length) continue;
            // 跳过无 delta 的 keep-alive 行
            if (!obj.choices?.[0]?.delta) continue;
            yield obj;
          } catch {
            // 忽略解析错误
          }
        }
      }
    } finally {
      try {
        reader.releaseLock();
      } catch {}
    }
  },

  /* ---------- Agents ---------- */

  listAgents: (q?: string) => {
    const qs = q ? `?q=${encodeURIComponent(q)}` : "";
    return request<AgentsListResponse>(`/v1/agents${qs}`);
  },
  getAgent: (id: string) => request<AgentConfig>(`/v1/agents/${id}`),
  createAgent: (payload: AgentCreateRequest) =>
    request<AgentConfig>("/v1/agents", { method: "POST", body: payload }),
  updateAgent: (id: string, payload: AgentUpdateRequest) =>
    request<AgentConfig>(`/v1/agents/${id}`, { method: "PATCH", body: payload }),
  deleteAgent: (id: string) => request<void>(`/v1/agents/${id}`, { method: "DELETE" }),
  runAgent: (id: string, payload: AgentRunRequest) =>
    request<AgentRunResponse>(`/v1/agents/${id}/run`, { method: "POST", body: payload }),
  listAgentRuns: (id: string) => request<AgentRunsListResponse>(`/v1/agents/${id}/runs`),

  /* ---------- Teams ---------- */

  listTeams: () => request<TeamsListResponse>("/v1/teams"),
  getTeam: (id: string) => request<TeamConfig>(`/v1/teams/${id}`),
  createTeam: (payload: TeamCreateRequest) =>
    request<TeamConfig>("/v1/teams", { method: "POST", body: payload }),
  deleteTeam: (id: string) => request<void>(`/v1/teams/${id}`, { method: "DELETE" }),
  runTeam: (id: string, payload: TeamRunRequest) =>
    request<TeamRunResponse>(`/v1/teams/${id}/run`, { method: "POST", body: payload }),
  getTeamMessages: (id: string) => request<{ data: TeamMessage[] }>(`/v1/teams/${id}/messages`),

  /* ---------- Memory ---------- */

  listMemories: (params?: { type?: string; q?: string }) => {
    const sp = new URLSearchParams();
    if (params?.type) sp.set("type", params.type);
    if (params?.q) sp.set("q", params.q);
    const qs = sp.toString();
    return request<MemoriesListResponse>(`/v1/memory${qs ? `?${qs}` : ""}`);
  },
  createMemory: (payload: MemoryCreateRequest) =>
    request<MemoryItem>("/v1/memory", { method: "POST", body: payload }),
  updateMemory: (id: string, payload: MemoryUpdateRequest) =>
    request<MemoryItem>(`/v1/memory/${id}`, { method: "PATCH", body: payload }),
  deleteMemory: (id: string) => request<void>(`/v1/memory/${id}`, { method: "DELETE" }),
  searchMemory: (payload: MemorySearchRequest) =>
    request<MemorySearchResponse>("/v1/memory/search", { method: "POST", body: payload }),

  /* ---------- RAG ---------- */

  listRagDocuments: () => request<RagDocsListResponse>("/v1/rag/documents"),
  uploadRagDocument: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<RagDocument>("/v1/rag/documents", { method: "POST", body: fd });
  },
  deleteRagDocument: (id: string) => request<void>(`/v1/rag/documents/${id}`, { method: "DELETE" }),
  getRagDocument: (id: string) => request<RagDocDetailResponse>(`/v1/rag/documents/${id}`),
  searchRag: (payload: RagSearchRequest) =>
    request<RagSearchResponse>("/v1/rag/search", { method: "POST", body: payload }),

  /* ---------- Sandbox ---------- */

  listSandboxes: () => request<SandboxesListResponse>("/v1/sandboxes"),
  createSandbox: (payload: SandboxCreateRequest) =>
    request<SandboxInfo>("/v1/sandboxes", { method: "POST", body: payload }),
  getSandbox: (id: string) => request<SandboxInfo>(`/v1/sandboxes/${id}`),
  deleteSandbox: (id: string) => request<void>(`/v1/sandboxes/${id}`, { method: "DELETE" }),
  executeInSandbox: (id: string, payload: SandboxExecuteRequest) =>
    request<SandboxExecuteResponse>(`/v1/sandboxes/${id}/execute`, {
      method: "POST",
      body: payload,
    }),
  listSandboxFiles: (id: string, path = ".") =>
    request<{ sandbox_id: string; path: string; tree: SandboxFileNode[] }>(
      `/v1/sandboxes/${id}/files?path=${encodeURIComponent(path)}`,
    ),
  getSandboxFile: (id: string, path: string) =>
    request<SandboxFileContent>(
      `/v1/sandboxes/${id}/files/content?path=${encodeURIComponent(path)}`,
    ),
  saveSandboxFile: (id: string, path: string, content: string) =>
    request<{ path: string; size: number }>(`/v1/sandboxes/${id}/files/content`, {
      method: "POST",
      body: { path, content },
    }),
  listSandboxSnapshots: (id: string) =>
    request<{ data: SandboxSnapshot[]; total: number }>(`/v1/sandboxes/${id}/snapshots`),
  createSandboxSnapshot: (id: string, name: string, description?: string) =>
    request<SandboxSnapshot>(`/v1/sandboxes/${id}/snapshots`, {
      method: "POST",
      body: { name, description: description || "" },
    }),
  restoreSandboxSnapshot: (id: string, name: string) =>
    request<{ restored: string }>(
      `/v1/sandboxes/${id}/snapshots/${encodeURIComponent(name)}/restore`,
      { method: "POST" },
    ),
  deleteSandboxSnapshot: (id: string, name: string) =>
    request<void>(`/v1/sandboxes/${id}/snapshots/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  /* ---------- Office: Word ---------- */

  wordRead: (payload: WordReadPayload) =>
    request<WordReadResponse>("/v1/office/word/read", { method: "POST", body: payload }),
  wordWrite: (payload: WordWritePayload) =>
    request<WordWriteResponse>("/v1/office/word/write", { method: "POST", body: payload }),
  wordEdit: (payload: WordEditPayload) =>
    request<WordEditResponse>("/v1/office/word/edit", { method: "POST", body: payload }),
  wordTemplate: (payload: WordTemplatePayload) =>
    request<WordTemplateResponse>("/v1/office/word/template", {
      method: "POST",
      body: payload,
    }),

  /* ---------- Office: PPT ---------- */

  pptRead: (payload: PptReadPayload) =>
    request<PptReadResponse>("/v1/office/ppt/read", { method: "POST", body: payload }),
  pptWrite: (payload: PptWritePayload) =>
    request<PptWriteResponse>("/v1/office/ppt/write", { method: "POST", body: payload }),

  /* ---------- Office: Excel ---------- */

  excelRead: (payload: ExcelReadPayload) =>
    request<ExcelReadResponse>("/v1/office/excel/read", { method: "POST", body: payload }),
  excelAnalyze: (payload: ExcelAnalyzePayload) =>
    request<ExcelAnalyzeResponse>("/v1/office/excel/analyze", {
      method: "POST",
      body: payload,
    }),
  excelChart: (payload: ExcelChartPayload) =>
    request<ExcelChartResponse>("/v1/office/excel/chart", {
      method: "POST",
      body: payload,
    }),
  excelWrite: (payload: ExcelWritePayload) =>
    request<ExcelWriteResponse>("/v1/office/excel/write", {
      method: "POST",
      body: payload,
    }),

  /* ---------- Office: PDF ---------- */

  pdfRead: (payload: PdfReadPayload) =>
    request<PdfReadResponse>("/v1/office/pdf/read", { method: "POST", body: payload }),
  pdfMerge: (payload: PdfMergePayload) =>
    request<PdfMergeResponse>("/v1/office/pdf/merge", { method: "POST", body: payload }),
  pdfSplit: (payload: PdfSplitPayload) =>
    request<PdfSplitResponse>("/v1/office/pdf/split", { method: "POST", body: payload }),

  /* ---------- Skills ---------- */

  listSkills: (params?: { category?: string; q?: string }) => {
    const sp = new URLSearchParams();
    if (params?.category) sp.set("category", params.category);
    if (params?.q) sp.set("q", params.q);
    const qs = sp.toString();
    return request<SkillsListResponse>(`/v1/skills${qs ? `?${qs}` : ""}`);
  },
  getSkill: (name: string) => request<Skill>(`/v1/skills/${encodeURIComponent(name)}`),
  createSkill: (payload: SkillCreateRequest) =>
    request<Skill>("/v1/skills", { method: "POST", body: payload }),
  saveSkill: (name: string, payload: SkillCreateRequest) =>
    request<Skill>(`/v1/skills/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: payload,
    }),
  deleteSkill: (name: string) =>
    request<void>(`/v1/skills/${encodeURIComponent(name)}`, { method: "DELETE" }),
  executeSkill: (name: string, payload: SkillExecuteRequest) =>
    request<SkillExecuteResponse>(`/v1/skills/${encodeURIComponent(name)}/execute`, {
      method: "POST",
      body: payload,
    }),
  extractSkill: (payload: SkillExtractionRequest) =>
    request<SkillExtractionResponse>("/v1/skills/extract", {
      method: "POST",
      body: payload,
    }),

  /* ---------- Notifications ---------- */

  listNotifications: (unread_only = false) =>
    request<NotificationsListResponse>(`/v1/notifications?unread_only=${unread_only}`),
  markNotificationsRead: (ids: string[] | "all") => {
    const body = typeof ids === "string" ? { all_read: true } : { ids, all_read: false };
    return request<{ marked: number }>("/v1/notifications/mark-read", {
      method: "POST",
      body,
    });
  },

  /* ---------- Sessions ---------- */

  listSessions: () => request<SessionHistoryListResponse>("/v1/sessions"),
  upsertSession: (id: string, payload: Record<string, unknown>) =>
    request<unknown>(`/v1/sessions/${id}`, { method: "PUT", body: payload }),
  deleteSession: (id: string) => request<void>(`/v1/sessions/${id}`, { method: "DELETE" }),

  /* ---------- P1-10 企业治理: 审计 / 配额 / Webhook / 定时任务 ---------- */

  listAudit: (params?: { actor?: string; action?: string; resource_type?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.actor) q.set("actor", params.actor);
    if (params?.action) q.set("action", params.action);
    if (params?.resource_type) q.set("resource_type", params.resource_type);
    if (params?.limit) q.set("limit", String(params.limit));
    return request<{ total: number; items: AuditEntry[] }>(`/v1/audit?${q.toString()}`);
  },
  auditStats: () => request<AuditStats>("/v1/audit/stats"),
  exportAudit: (fmt: "json" | "csv" = "json") =>
    request<{ format: string; data: string; count: number }>(`/v1/audit/export?fmt=${fmt}`),
  clearAudit: () => request<{ cleared: number }>("/v1/audit", { method: "DELETE" }),

  listQuotaPolicies: () => request<{ policies: QuotaPolicy[] }>("/v1/quota/policies"),
  createQuotaPolicy: (payload: QuotaPolicyCreate) =>
    request<{ policy: QuotaPolicy }>("/v1/quota/policies", { method: "POST", body: payload }),
  deleteQuotaPolicy: (scope: string, scopeId: string) =>
    request<void>(`/v1/quota/policies/${scope}/${scopeId}`, { method: "DELETE" }),
  quotaUsage: (actor?: string) =>
    request<{ summary: QuotaSummary; records: UsageRecord[] }>(
      `/v1/quota/usage${actor ? `?actor=${actor}` : ""}`,
    ),
  quotaStatus: (actor: string) => request<QuotaActorStatus>(`/v1/quota/status/${actor}`),

  listWebhookEvents: () => request<{ events: string[]; total: number }>("/v1/webhooks/events"),
  listWebhooks: () => request<{ subscriptions: WebhookSubscription[] }>("/v1/webhooks"),
  createWebhook: (payload: WebhookCreate) =>
    request<{ subscription: WebhookSubscription }>("/v1/webhooks", { method: "POST", body: payload }),
  getWebhook: (id: string) => request<{ subscription: WebhookSubscription }>(`/v1/webhooks/${id}`),
  updateWebhook: (id: string, payload: Partial<WebhookCreate>) =>
    request<{ subscription: WebhookSubscription }>(`/v1/webhooks/${id}`, {
      method: "PATCH",
      body: payload,
    }),
  deleteWebhook: (id: string) => request<void>(`/v1/webhooks/${id}`, { method: "DELETE" }),
  testWebhook: async (id: string) =>
    request<{ delivery: WebhookDelivery }>(`/v1/webhooks/${id}/test`, { method: "POST" }),
  listWebhookDeliveries: (params?: { sub_id?: string; event?: string; status?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.sub_id) q.set("sub_id", params.sub_id);
    if (params?.event) q.set("event", params.event);
    if (params?.status) q.set("status", params.status);
    if (params?.limit) q.set("limit", String(params.limit));
    return request<{ deliveries: WebhookDelivery[]; stats: { total: number; by_status: Record<string, number> } }>(
      `/v1/webhooks/deliveries?${q.toString()}`,
    );
  },

  listJobs: () => request<{ jobs: ScheduledJob[]; stats: JobStats }>("/v1/jobs"),
  createJob: (payload: JobCreate) =>
    request<{ job: ScheduledJob }>("/v1/jobs", { method: "POST", body: payload }),
  getJob: (id: string) => request<{ job: ScheduledJob }>(`/v1/jobs/${id}`),
  updateJob: (id: string, payload: Partial<JobCreate> & { enabled?: boolean }) =>
    request<{ job: ScheduledJob }>(`/v1/jobs/${id}`, { method: "PATCH", body: payload }),
  deleteJob: (id: string) => request<void>(`/v1/jobs/${id}`, { method: "DELETE" }),
  triggerJob: (id: string) => request<{ execution: JobExecution }>(`/v1/jobs/${id}/trigger`, { method: "POST" }),
  listJobExecutions: (params?: { job_id?: string; status?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.limit) q.set("limit", String(params.limit));
    const path = params?.job_id ? `/v1/jobs/${params.job_id}/executions` : `/v1/jobs/executions/all`;
    return request<{ executions: JobExecution[] }>(`${path}?${q.toString()}`);
  },

  /* ---------- MCP (Model Context Protocol) ---------- */

  listMCPServers: (includeTools = false) =>
    request<MCPServersListResponse>(`/v1/mcp/servers${includeTools ? "?include_tools=true" : ""}`),
  getMCPServer: (id: string) => request<MCPServer>(`/v1/mcp/servers/${encodeURIComponent(id)}`),
  createMCPServer: (payload: MCPServerCreateRequest) =>
    request<MCPServer>("/v1/mcp/servers", { method: "POST", body: payload }),
  updateMCPServer: (id: string, payload: Partial<MCPServerCreateRequest>) =>
    request<MCPServer>(`/v1/mcp/servers/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: payload,
    }),
  deleteMCPServer: (id: string) =>
    request<void>(`/v1/mcp/servers/${encodeURIComponent(id)}`, { method: "DELETE" }),
  installMCPPreset: (id: string) =>
    request<MCPServer>(`/v1/mcp/servers/preset/${encodeURIComponent(id)}`, { method: "POST" }),
  listMCPPresets: () => request<MCPPresetsListResponse>("/v1/mcp/presets"),
  listMCPServerTools: (id: string, refresh = false) =>
    request<MCPToolsListResponse>(
      `/v1/mcp/servers/${encodeURIComponent(id)}/tools${refresh ? "?refresh=true" : ""}`,
    ),
  listAllMCPTools: () => request<MCPToolsAllResponse>("/v1/mcp/tools"),
  invokeMCPTool: (payload: MCPInvokeRequest) =>
    request<MCPInvokeResponse>("/v1/mcp/invoke", { method: "POST", body: payload }),
  mcpHealth: () => request<MCPHealthResponse>("/v1/mcp/health"),

  /* ---------- P1-11 企业治理 Tier 2 ---------- */

  // Tenants
  listTenants: (params?: { status?: string; plan?: string }) =>
    request<{ tenants: Tenant[]; stats: TenantStats }>("/v1/tenants", { params }),
  createTenant: (payload: TenantCreateRequest) =>
    request<{ tenant: Tenant }>("/v1/tenants", { method: "POST", body: payload }),
  getTenant: (id: string) => request<{ tenant: Tenant; members: TenantMember[] }>(`/v1/tenants/${encodeURIComponent(id)}`),
  updateTenant: (id: string, payload: TenantUpdateRequest) =>
    request<{ tenant: Tenant }>(`/v1/tenants/${encodeURIComponent(id)}`, { method: "PATCH", body: payload }),
  deleteTenant: (id: string) => request<void>(`/v1/tenants/${encodeURIComponent(id)}`, { method: "DELETE" }),
  suspendTenant: (id: string) =>
    request<{ tenant: Tenant }>(`/v1/tenants/${encodeURIComponent(id)}/suspend`, { method: "POST" }),
  activateTenant: (id: string) =>
    request<{ tenant: Tenant }>(`/v1/tenants/${encodeURIComponent(id)}/activate`, { method: "POST" }),
  listTenantMembers: (id: string) =>
    request<{ members: TenantMember[] }>(`/v1/tenants/${encodeURIComponent(id)}/members`),
  addTenantMember: (id: string, payload: { user_id: string; role: string }) =>
    request<{ member: TenantMember }>(`/v1/tenants/${encodeURIComponent(id)}/members`, {
      method: "POST",
      body: payload,
    }),
  removeTenantMember: (id: string, userId: string) =>
    request<void>(`/v1/tenants/${encodeURIComponent(id)}/members/${encodeURIComponent(userId)}`, {
      method: "DELETE",
    }),

  // RBAC
  listRoles: (params?: { tenant_id?: string; include_system?: boolean }) =>
    request<{ roles: RBACRole[] }>("/v1/rbac/roles", { params }),
  createRole: (payload: RoleCreateRequest) =>
    request<{ role: RBACRole }>("/v1/rbac/roles", { method: "POST", body: payload }),
  getRole: (id: string) => request<{ role: RBACRole }>(`/v1/rbac/roles/${encodeURIComponent(id)}`),
  deleteRole: (id: string) =>
    request<void>(`/v1/rbac/roles/${encodeURIComponent(id)}`, { method: "DELETE" }),
  listRbacPolicies: (params?: { tenant_id?: string }) =>
    request<{ policies: Policy[] }>("/v1/rbac/policies", { params }),
  createRbacPolicy: (payload: PolicyCreateRequest) =>
    request<{ policy: Policy }>("/v1/rbac/policies", { method: "POST", body: payload }),
  deleteRbacPolicy: (id: string) =>
    request<void>(`/v1/rbac/policies/${encodeURIComponent(id)}`, { method: "DELETE" }),
  listRbacAssignments: (params?: { user_id?: string; tenant_id?: string }) =>
    request<{ assignments: Assignment[] }>("/v1/rbac/assignments", { params }),
  assignRole: (payload: AssignmentCreateRequest) =>
    request<{ assignment: Assignment }>("/v1/rbac/assignments", { method: "POST", body: payload }),
  revokeRole: (params: { user_id: string; role_id: string; tenant_id?: string }) =>
    request<void>("/v1/rbac/assignments", { method: "DELETE", params }),
  rbacCheck: (payload: RbacCheckRequest) =>
    request<{ decision: Decision }>("/v1/rbac/check", { method: "POST", body: payload }),
  rbacDelegate: (params: { from_user: string; to_user: string; role_id: string; tenant_id?: string; expires_in?: number }) =>
    request<{ assignment: Assignment }>("/v1/rbac/delegate", { method: "POST", params }),
  rbacRecentDecisions: (limit = 50) =>
    request<{ decisions: Decision[] }>("/v1/rbac/decisions", { params: { limit } }),

  // Billing
  billingSummary: (params?: { tenant_id?: string; since?: number; until?: number }) =>
    request<{ summary: BillingSummary }>("/v1/billing/summary", { params }),
  billingCostByDay: (params?: { tenant_id?: string; days?: number }) =>
    request<{ series: CostDaySeries[] }>("/v1/billing/cost-by-day", { params }),
  billingTopSpenders: (params?: { by?: "user" | "project"; tenant_id?: string; limit?: number }) =>
    request<{ top: TopSpender[] }>("/v1/billing/top-spenders", { params }),
  listPricing: () => request<{ pricing: PricingModel[] }>("/v1/billing/pricing"),
  setPricing: (payload: PricingModelCreate) =>
    request<{ pricing: PricingModel }>("/v1/billing/pricing", { method: "POST", body: payload }),
  recordUsage: (payload: UsageRecordCreate) =>
    request<{ record: UsageRecord }>("/v1/billing/usage", { method: "POST", body: payload }),
  listUsage: (params?: { tenant_id?: string; cost_center_id?: string; since?: number; until?: number; limit?: number }) =>
    request<{ records: UsageRecord[] }>("/v1/billing/usage", { params }),
  listBudgets: (params?: { scope?: string; scope_id?: string }) =>
    request<{ budgets: Budget[] }>("/v1/billing/budgets", { params }),
  setBudget: (payload: BudgetCreate) =>
    request<{ budget: Budget }>("/v1/billing/budgets", { method: "POST", body: payload }),
  deleteBudget: (id: string) =>
    request<void>(`/v1/billing/budgets/${encodeURIComponent(id)}`, { method: "DELETE" }),
  listCostCenters: (params?: { tenant_id?: string }) =>
    request<{ cost_centers: CostCenter[] }>("/v1/billing/cost-centers", { params }),
  addCostCenter: (payload: CostCenterCreate) =>
    request<{ cost_center: CostCenter }>("/v1/billing/cost-centers", { method: "POST", body: payload }),
  budgetCheck: (params?: { tenant_id?: string; cost_center_id?: string }) =>
    request<{ ok: boolean; alerts: BudgetAlert[] }>("/v1/billing/budget-check", { params }),
  exportInvoice: (params: { tenant_id: string; since: number; until: number; format?: "json" | "csv" }) =>
    request<{ invoice: string }>("/v1/billing/invoice", { params }),

  // SLA
  slaStatus: () => request<SLAStatusPage>("/v1/sla/status"),
  listSLOs: () => request<{ slos: SLO[] }>("/v1/sla/slos"),
  createSLO: (payload: SLOCreate) => request<{ slo: SLO }>("/v1/sla/slos", { method: "POST", body: payload }),
  evaluateSLO: (id: string, window_sec = 86400) =>
    request<{ report: SLOResult }>(`/v1/sla/slos/${encodeURIComponent(id)}/evaluate`, { params: { window_sec } }),
  evaluateAllSLOs: () => request<{ reports: SLOResult[] }>("/v1/sla/slos/evaluate"),
  listSLAComponents: () => request<{ components: SLAComponent[] }>("/v1/sla/components"),
  registerSLAComponent: (payload: { name: string; description?: string }) =>
    request<{ component: SLAComponent }>("/v1/sla/components", { method: "POST", body: payload }),
  slaRecordProbe: (payload: SLIProbeCreate) =>
    request<{ probe: SLIProbe }>("/v1/sla/probe", { method: "POST", body: payload }),
  listIncidents: (params?: { status?: string; limit?: number }) =>
    request<{ incidents: Incident[] }>("/v1/sla/incidents", { params }),
  openIncident: (payload: IncidentCreate) =>
    request<{ incident: Incident }>("/v1/sla/incidents", { method: "POST", body: payload }),
  updateIncident: (id: string, payload: IncidentUpdate) =>
    request<{ incident: Incident }>(`/v1/sla/incidents/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: payload,
    }),
  slaMonthlyReport: (year: number, month: number) =>
    request<{ report: SLAMonthlyReport }>("/v1/sla/report/monthly", { params: { year, month } }),

  // SSO
  listIDPs: () => request<{ idps: IdentityProvider[] }>("/v1/sso/idps"),
  registerIDP: (payload: IdentityProviderCreate) =>
    request<{ idp: IdentityProvider }>("/v1/sso/idps", { method: "POST", body: payload }),
  getIDP: (id: string) => request<{ idp: IdentityProvider }>(`/v1/sso/idps/${encodeURIComponent(id)}`),
  deleteIDP: (id: string) => request<void>(`/v1/sso/idps/${encodeURIComponent(id)}`, { method: "DELETE" }),
  ssoAuthUrl: (idpId: string, redirectUri: string) =>
    request<{ url: string }>("/v1/sso/auth-url", { params: { idp_id: idpId, redirect_uri: redirectUri } }),
  ssoLogin: (idpId: string, payload: { code: string; redirect_uri: string; tenant_id?: string }) =>
    request<SSOLoginResult>("/v1/sso/login", { method: "POST", params: { idp_id: idpId }, body: payload }),
  ssoLogout: (sessionId: string) =>
    request<{ revoked: boolean }>("/v1/sso/logout", { method: "POST", params: { session_id: sessionId } }),
  listSSOSessions: (params?: { user_id?: string }) =>
    request<{ sessions: SSOSession[] }>("/v1/sso/sessions", { params }),
  listSCIMUsers: (params?: { active_only?: boolean }) =>
    request<{ users: SCIMUser[] }>("/v1/sso/scim/users", { params }),
  upsertSCIMUser: (payload: SCIMUserCreate) =>
    request<{ user: SCIMUser }>("/v1/sso/scim/users", { method: "POST", body: payload }),
  deactivateSCIMUser: (userName: string) =>
    request<void>(`/v1/sso/scim/users/${encodeURIComponent(userName)}`, { method: "DELETE" }),

  // Residency
  listRegions: () => request<{ regions: Region[] }>("/v1/residency/regions"),
  addRegion: (payload: RegionCreate) =>
    request<{ region: Region }>("/v1/residency/regions", { method: "POST", body: payload }),
  setRegionStatus: (id: string, status: string) => {
    const sp = new URLSearchParams();
    sp.set("status", status);
    return request<{ region: Region }>(`/v1/residency/regions/${encodeURIComponent(id)}/status?${sp.toString()}`, {
      method: "POST",
    });
  },
  listResidencyPolicies: () => request<{ policies: ResidencyPolicy[] }>("/v1/residency/policies"),
  addResidencyPolicy: (payload: ResidencyPolicyCreate) =>
    request<{ policy: ResidencyPolicy }>("/v1/residency/policies", { method: "POST", body: payload }),
  deleteResidencyPolicy: (id: string) =>
    request<void>(`/v1/residency/policies/${encodeURIComponent(id)}`, { method: "DELETE" }),
  residencyRoute: (payload: ResidencyRouteRequest) =>
    request<{ assignment: ResidencyAssignment }>("/v1/residency/route", { method: "POST", body: payload }),
  residencyCanTransfer: (params: { resource_id: string; from_region: string; to_region: string }) =>
    request<{ ok: boolean; reason: string }>("/v1/residency/can-transfer", { method: "POST", params }),
  listResidencyAssignments: (params?: { tenant_id?: string; data_class?: string; limit?: number }) =>
    request<{ assignments: ResidencyAssignment[] }>("/v1/residency/assignments", { params }),
  residencyStats: () => request<ResidencyStats>("/v1/residency/stats"),

  // Audit Chain
  auditChainIntegrity: () => request<AuditChainIntegrity>("/v1/audit-chain/integrity"),
  listAuditBlocks: () => request<{ blocks: AuditChainBlock[] }>("/v1/audit-chain/blocks"),
  auditChainAdd: (entry: Record<string, unknown>) =>
    request<{ block_sealed: AuditChainBlock | null; pending: number }>("/v1/audit-chain/add", {
      method: "POST",
      body: { entry },
    }),
  auditChainSeal: () => request<{ block: AuditChainBlock }>("/v1/audit-chain/seal", { method: "POST" }),
  auditChainProof: (entryId: string) =>
    request<{ proof: AuditChainProof }>("/v1/audit-chain/proof", { params: { entry_id: entryId } }),

  // ─────────────────────────────────────────────────────────────────────
  // 跨区域复制 (Replication) — Tier 3
  // ─────────────────────────────────────────────────────────────────────
  replicationStats: () => request<ReplicationStats>("/v1/replication/stats"),
  listReplicationPolicies: (params?: { source_region?: string; target_region?: string; enabled?: boolean }) =>
    request<ReplicationListResponse>("/v1/replication/policies", { params }),
  getReplicationPolicy: (id: string) =>
    request<ReplicationPolicyResponse>(`/v1/replication/policies/${encodeURIComponent(id)}`),
  createReplicationPolicy: (data: {
    name: string;
    source_region: string;
    target_region: string;
    mode?: string;
    max_lag_sec?: number;
    encryption?: boolean;
    compression?: boolean;
  }) => request<ReplicationPolicyResponse>("/v1/replication/policies", { method: "POST", body: data }),
  deleteReplicationPolicy: (id: string) =>
    request<void>(`/v1/replication/policies/${encodeURIComponent(id)}`, { method: "DELETE" }),
  listReplicationStreams: (params?: { policy_id?: string; state?: string }) =>
    request<ReplicationStreamListResponse>("/v1/replication/streams", { params }),
  getReplicationStream: (id: string) =>
    request<ReplicationStreamResponse>(`/v1/replication/streams/${encodeURIComponent(id)}`),
  recordReplicationSync: (id: string, data: { records: number; bytes_sent: number; lag_sec?: number }) =>
    request<ReplicationStreamResponse>(`/v1/replication/streams/${encodeURIComponent(id)}/sync`, {
      method: "POST",
      body: data,
    }),
  recordReplicationFailure: (id: string, data: { error: string; records_lost?: number }) =>
    request<ReplicationStreamResponse>(`/v1/replication/streams/${encodeURIComponent(id)}/failure`, {
      method: "POST",
      body: data,
    }),
  pauseReplicationStream: (id: string) =>
    request<ReplicationStreamResponse>(`/v1/replication/streams/${encodeURIComponent(id)}/pause`, {
      method: "POST",
    }),
  resumeReplicationStream: (id: string) =>
    request<ReplicationStreamResponse>(`/v1/replication/streams/${encodeURIComponent(id)}/resume`, {
      method: "POST",
    }),
  listFailovers: (params?: { mode?: string; state?: string; limit?: number }) =>
    request<FailoverListResponse>("/v1/replication/failovers", { params }),
  initiateFailover: (data: {
    from_region: string;
    to_region: string;
    mode?: string;
    initiated_by?: string;
    reason?: string;
  }) => request<FailoverResponse>("/v1/replication/failovers", { method: "POST", body: data }),
  getFailover: (id: string) =>
    request<FailoverResponse>(`/v1/replication/failovers/${encodeURIComponent(id)}`),
  advanceFailover: (id: string, data: { new_state: string; notes?: string }) =>
    request<FailoverResponse>(`/v1/replication/failovers/${encodeURIComponent(id)}/advance`, {
      method: "POST",
      body: data,
    }),
  completeFailover: (id: string, data: { success: boolean; data_loss_records?: number; notes?: string }) =>
    request<FailoverResponse>(`/v1/replication/failovers/${encodeURIComponent(id)}/complete`, {
      method: "POST",
      body: data,
    }),
  replicationQuorumCheck: (data: { region: string; total_replicas: number; reachable_replicas: number }) =>
    request<{ ok: boolean; can_write: boolean; ratio: number; recommendation: string }>(
      "/v1/replication/quorum-check",
      { method: "POST", body: data }
    ),

  // ─────────────────────────────────────────────────────────────────────
  // 灾备恢复 (Recovery) — Tier 3
  // ─────────────────────────────────────────────────────────────────────
  recoveryStats: () => request<RecoveryStats>("/v1/recovery/stats"),
  listBackupSchedules: (params?: { enabled?: boolean }) =>
    request<BackupScheduleListResponse>("/v1/recovery/schedules", { params }),
  getBackupSchedule: (id: string) =>
    request<ScheduleResponse>(`/v1/recovery/schedules/${encodeURIComponent(id)}`),
  createBackupSchedule: (data: {
    name: string;
    backup_type?: string;
    cron_expr?: string;
    retention_days?: number;
    target_regions?: string[];
    encryption?: boolean;
  }) => request<ScheduleResponse>("/v1/recovery/schedules", { method: "POST", body: data }),
  deleteBackupSchedule: (id: string) =>
    request<void>(`/v1/recovery/schedules/${encodeURIComponent(id)}`, { method: "DELETE" }),
  triggerBackup: (id: string, data: { record_count?: number; target_region?: string }) =>
    request<BackupResponse>(`/v1/recovery/schedules/${encodeURIComponent(id)}/trigger`, {
      method: "POST",
      body: data,
    }),
  listBackups: (params?: { schedule_id?: string; status?: string; region?: string; limit?: number }) =>
    request<BackupListResponse>("/v1/recovery/backups", { params }),
  getBackup: (id: string) =>
    request<BackupResponse>(`/v1/recovery/backups/${encodeURIComponent(id)}`),
  verifyBackup: (id: string) =>
    request<{ ok: boolean; error?: string; checksum: string; size_bytes: number; record_count: number }>(
      `/v1/recovery/backups/${encodeURIComponent(id)}/verify`
    ),
  expireOldBackups: () =>
    request<{ expired_count: number }>("/v1/recovery/expire-old", { method: "POST" }),
  createRestore: (data: { backup_id: string; target_region?: string; reason?: string; requested_by?: string }) =>
    request<RestoreResponse>("/v1/recovery/restore", { method: "POST", body: data }),
  advanceRestore: (
    id: string,
    data: { status: string; progress_pct?: number; records_restored?: number; error?: string; validation_passed?: boolean }
  ) =>
    request<RestoreResponse>(`/v1/recovery/restore/${encodeURIComponent(id)}/advance`, {
      method: "POST",
      body: data,
    }),
  listRestores: (params?: { backup_id?: string; status?: string; limit?: number }) =>
    request<RestoreListResponse>("/v1/recovery/restores", { params }),
  runDRDrill: (data: {
    name: string;
    schedule_id?: string;
    backup_id?: string;
    target_region?: string;
    rto_target_sec?: number;
    rpo_target_sec?: number;
    conducted_by?: string;
    notes?: string;
  }) => request<DrillResponse>("/v1/recovery/drill", { method: "POST", body: data }),
  listDRDrills: (params?: { result?: string; limit?: number }) =>
    request<DrillListResponse>("/v1/recovery/drills", { params }),
  createRetentionHold: (data: {
    resource_id: string;
    regulation: string;
    action?: string;
    hold_until?: number;
    reason?: string;
    requested_by?: string;
  }) => request<HoldResponse>("/v1/recovery/holds", { method: "POST", body: data }),
  listRetentionHolds: (params?: { resource_id?: string; regulation?: string; active_only?: boolean }) =>
    request<HoldListResponse>("/v1/recovery/holds", { params }),
  checkResourceAction: (resource_id: string, action: string = "delete") =>
    request<{ blocked: boolean; holds: RetentionHold[]; message?: string }>("/v1/recovery/check-action", {
      params: { resource_id, action },
    }),

  // ─────────────────────────────────────────────────────────────────────
  // SLA 违约赔付 (Compensation) — Tier 3
  // ─────────────────────────────────────────────────────────────────────
  compensationStats: () => request<CompensationStats>("/v1/compensation/stats"),
  listCompensationPolicies: (params?: { plan_tier?: string }) =>
    request<CompensationPolicyListResponse>("/v1/compensation/policies", { params }),
  getCompensationPolicy: (id: string) =>
    request<CompensationPolicyResponse>(`/v1/compensation/policies/${encodeURIComponent(id)}`),
  createCompensationPolicy: (data: {
    name: string;
    plan_tier?: string;
    target_availability_pct?: number;
    tiers?: Array<{ min_availability_pct: number; max_availability_pct: number; credit_pct: number; description?: string }>;
  }) => request<CompensationPolicyResponse>("/v1/compensation/policies", { method: "POST", body: data }),
  detectBreach: (data: {
    policy_id: string;
    tenant_id: string;
    actual_availability_pct: number;
    downtime_sec?: number;
    description?: string;
  }) => request<BreachResponse>("/v1/compensation/breach", { method: "POST", body: data }),
  listBreaches: (params?: { tenant_id?: string; severity?: string; limit?: number }) =>
    request<BreachListResponse>("/v1/compensation/breaches", { params }),
  calculateCredit: (data: { breach_id: string; monthly_fee_usd: number }) =>
    request<CreditResponse>("/v1/compensation/calculate", { method: "POST", body: data }),
  applyCredit: (id: string) =>
    request<CreditResponse>(`/v1/compensation/credits/${encodeURIComponent(id)}/apply`, { method: "POST" }),
  markCreditPaid: (id: string) =>
    request<CreditResponse>(`/v1/compensation/credits/${encodeURIComponent(id)}/pay`, { method: "POST" }),
  rejectCredit: (id: string, reason: string = "") =>
    request<CreditResponse>(`/v1/compensation/credits/${encodeURIComponent(id)}/reject?reason=${encodeURIComponent(reason)}`, {
      method: "POST",
    }),
  listCredits: (params?: { tenant_id?: string; status?: string; limit?: number }) =>
    request<CreditListResponse>("/v1/compensation/credits", { params }),
  raiseDispute: (data: { credit_id: string; tenant_id: string; raised_by: string; reason: string; evidence?: Record<string, unknown> }) =>
    request<DisputeResponse>("/v1/compensation/dispute", { method: "POST", body: data }),
  resolveDispute: (id: string, data: { resolution: string; resolved_by?: string; uphold_credit?: boolean }) =>
    request<DisputeResponse>(`/v1/compensation/dispute/${encodeURIComponent(id)}/resolve`, {
      method: "POST",
      body: data,
    }),
  listDisputes: (params?: { tenant_id?: string; status?: string; limit?: number }) =>
    request<DisputeListResponse>("/v1/compensation/disputes", { params }),
  compensationTenantSummary: (tenant_id: string, period_start: number, period_end: number) =>
    request<{
      tenant_id: string;
      period_start: number;
      period_end: number;
      total_breaches: number;
      total_credits: number;
      total_credit_amount_usd: number;
      applied_credit_amount_usd: number;
      avg_actual_availability_pct: number;
    }>("/v1/compensation/tenant-summary", {
      params: { tenant_id, period_start, period_end },
    }),
};

// 兼容旧代码中的 DataAIClient 引用
export class DataAIClient {
  health = api.health;
  listModels = api.listModels;
  listTools = api.listTools;
  executeTool = api.executeTool;
  chatCompletion = api.chatCompletion;
  chatCompletionStream = api.chatCompletionStream;
  listAgents = api.listAgents;
  getAgent = api.getAgent;
  createAgent = api.createAgent;
  updateAgent = api.updateAgent;
  deleteAgent = api.deleteAgent;
  runAgent = api.runAgent;
  listAgentRuns = api.listAgentRuns;
  listTeams = api.listTeams;
  getTeam = api.getTeam;
  createTeam = api.createTeam;
  deleteTeam = api.deleteTeam;
  runTeam = api.runTeam;
  getTeamMessages = api.getTeamMessages;
  listMemories = api.listMemories;
  createMemory = api.createMemory;
  updateMemory = api.updateMemory;
  deleteMemory = api.deleteMemory;
  searchMemory = api.searchMemory;
  listRagDocuments = api.listRagDocuments;
  uploadRagDocument = api.uploadRagDocument;
  deleteRagDocument = api.deleteRagDocument;
  getRagDocument = api.getRagDocument;
  searchRag = api.searchRag;
  listSandboxes = api.listSandboxes;
  createSandbox = api.createSandbox;
  getSandbox = api.getSandbox;
  deleteSandbox = api.deleteSandbox;
  executeInSandbox = api.executeInSandbox;
  listSandboxFiles = api.listSandboxFiles;
  getSandboxFile = api.getSandboxFile;
  saveSandboxFile = api.saveSandboxFile;
  listSandboxSnapshots = api.listSandboxSnapshots;
  createSandboxSnapshot = api.createSandboxSnapshot;
  restoreSandboxSnapshot = api.restoreSandboxSnapshot;
  deleteSandboxSnapshot = api.deleteSandboxSnapshot;
  wordRead = api.wordRead;
  wordWrite = api.wordWrite;
  wordEdit = api.wordEdit;
  wordTemplate = api.wordTemplate;
  pptRead = api.pptRead;
  pptWrite = api.pptWrite;
  excelRead = api.excelRead;
  excelAnalyze = api.excelAnalyze;
  excelChart = api.excelChart;
  excelWrite = api.excelWrite;
  pdfRead = api.pdfRead;
  pdfMerge = api.pdfMerge;
  pdfSplit = api.pdfSplit;
  listSkills = api.listSkills;
  getSkill = api.getSkill;
  createSkill = api.createSkill;
  saveSkill = api.saveSkill;
  deleteSkill = api.deleteSkill;
  executeSkill = api.executeSkill;
  extractSkill = api.extractSkill;
  listNotifications = api.listNotifications;
  markNotificationsRead = api.markNotificationsRead;
  listSessions = api.listSessions;
  upsertSession = api.upsertSession;
  deleteSession = api.deleteSession;
  listMCPServers = api.listMCPServers;
  getMCPServer = api.getMCPServer;
  createMCPServer = api.createMCPServer;
  updateMCPServer = api.updateMCPServer;
  deleteMCPServer = api.deleteMCPServer;
  installMCPPreset = api.installMCPPreset;
  listMCPPresets = api.listMCPPresets;
  listMCPServerTools = api.listMCPServerTools;
  listAllMCPTools = api.listAllMCPTools;
  invokeMCPTool = api.invokeMCPTool;
  mcpHealth = api.mcpHealth;

  /* ---------- P1-10 企业治理 ---------- */
  listAudit = api.listAudit;
  auditStats = api.auditStats;
  exportAudit = api.exportAudit;
  clearAudit = api.clearAudit;
  listQuotaPolicies = api.listQuotaPolicies;
  createQuotaPolicy = api.createQuotaPolicy;
  deleteQuotaPolicy = api.deleteQuotaPolicy;
  quotaUsage = api.quotaUsage;
  quotaStatus = api.quotaStatus;
  listWebhookEvents = api.listWebhookEvents;
  listWebhooks = api.listWebhooks;
  createWebhook = api.createWebhook;
  getWebhook = api.getWebhook;
  updateWebhook = api.updateWebhook;
  deleteWebhook = api.deleteWebhook;
  testWebhook = api.testWebhook;
  listWebhookDeliveries = api.listWebhookDeliveries;
  listJobs = api.listJobs;
  createJob = api.createJob;
  getJob = api.getJob;
  updateJob = api.updateJob;
  deleteJob = api.deleteJob;
  triggerJob = api.triggerJob;
  listJobExecutions = api.listJobExecutions;

  /* ---------- P1-11 企业治理 Tier 2 ---------- */
  // Tenants
  listTenants = api.listTenants;
  createTenant = api.createTenant;
  getTenant = api.getTenant;
  updateTenant = api.updateTenant;
  deleteTenant = api.deleteTenant;
  suspendTenant = api.suspendTenant;
  activateTenant = api.activateTenant;
  listTenantMembers = api.listTenantMembers;
  addTenantMember = api.addTenantMember;
  removeTenantMember = api.removeTenantMember;
  // RBAC
  listRoles = api.listRoles;
  createRole = api.createRole;
  getRole = api.getRole;
  deleteRole = api.deleteRole;
  listRbacPolicies = api.listRbacPolicies;
  createRbacPolicy = api.createRbacPolicy;
  deleteRbacPolicy = api.deleteRbacPolicy;
  listRbacAssignments = api.listRbacAssignments;
  assignRole = api.assignRole;
  revokeRole = api.revokeRole;
  rbacCheck = api.rbacCheck;
  rbacDelegate = api.rbacDelegate;
  rbacRecentDecisions = api.rbacRecentDecisions;
  // Billing
  billingSummary = api.billingSummary;
  billingCostByDay = api.billingCostByDay;
  billingTopSpenders = api.billingTopSpenders;
  listPricing = api.listPricing;
  setPricing = api.setPricing;
  recordUsage = api.recordUsage;
  listUsage = api.listUsage;
  listBudgets = api.listBudgets;
  setBudget = api.setBudget;
  deleteBudget = api.deleteBudget;
  listCostCenters = api.listCostCenters;
  addCostCenter = api.addCostCenter;
  budgetCheck = api.budgetCheck;
  exportInvoice = api.exportInvoice;
  // SLA
  slaStatus = api.slaStatus;
  listSLOs = api.listSLOs;
  createSLO = api.createSLO;
  evaluateSLO = api.evaluateSLO;
  evaluateAllSLOs = api.evaluateAllSLOs;
  listSLAComponents = api.listSLAComponents;
  registerSLAComponent = api.registerSLAComponent;
  slaRecordProbe = api.slaRecordProbe;
  listIncidents = api.listIncidents;
  openIncident = api.openIncident;
  updateIncident = api.updateIncident;
  slaMonthlyReport = api.slaMonthlyReport;
  // SSO
  listIDPs = api.listIDPs;
  registerIDP = api.registerIDP;
  getIDP = api.getIDP;
  deleteIDP = api.deleteIDP;
  ssoAuthUrl = api.ssoAuthUrl;
  ssoLogin = api.ssoLogin;
  ssoLogout = api.ssoLogout;
  listSSOSessions = api.listSSOSessions;
  listSCIMUsers = api.listSCIMUsers;
  upsertSCIMUser = api.upsertSCIMUser;
  deactivateSCIMUser = api.deactivateSCIMUser;
  // Residency
  listRegions = api.listRegions;
  addRegion = api.addRegion;
  setRegionStatus = api.setRegionStatus;
  listResidencyPolicies = api.listResidencyPolicies;
  addResidencyPolicy = api.addResidencyPolicy;
  deleteResidencyPolicy = api.deleteResidencyPolicy;
  residencyRoute = api.residencyRoute;
  residencyCanTransfer = api.residencyCanTransfer;
  listResidencyAssignments = api.listResidencyAssignments;
  residencyStats = api.residencyStats;
  // Audit Chain
  auditChainIntegrity = api.auditChainIntegrity;
  listAuditBlocks = api.listAuditBlocks;
  auditChainAdd = api.auditChainAdd;
  auditChainSeal = api.auditChainSeal;
  auditChainProof = api.auditChainProof;

  // Tier 3 — Replication
  replicationStats = api.replicationStats;
  listReplicationPolicies = api.listReplicationPolicies;
  getReplicationPolicy = api.getReplicationPolicy;
  createReplicationPolicy = api.createReplicationPolicy;
  deleteReplicationPolicy = api.deleteReplicationPolicy;
  listReplicationStreams = api.listReplicationStreams;
  getReplicationStream = api.getReplicationStream;
  recordReplicationSync = api.recordReplicationSync;
  recordReplicationFailure = api.recordReplicationFailure;
  pauseReplicationStream = api.pauseReplicationStream;
  resumeReplicationStream = api.resumeReplicationStream;
  listFailovers = api.listFailovers;
  initiateFailover = api.initiateFailover;
  getFailover = api.getFailover;
  advanceFailover = api.advanceFailover;
  completeFailover = api.completeFailover;
  replicationQuorumCheck = api.replicationQuorumCheck;

  // Tier 3 — Recovery
  recoveryStats = api.recoveryStats;
  listBackupSchedules = api.listBackupSchedules;
  getBackupSchedule = api.getBackupSchedule;
  createBackupSchedule = api.createBackupSchedule;
  deleteBackupSchedule = api.deleteBackupSchedule;
  triggerBackup = api.triggerBackup;
  listBackups = api.listBackups;
  getBackup = api.getBackup;
  verifyBackup = api.verifyBackup;
  expireOldBackups = api.expireOldBackups;
  createRestore = api.createRestore;
  advanceRestore = api.advanceRestore;
  listRestores = api.listRestores;
  runDRDrill = api.runDRDrill;
  listDRDrills = api.listDRDrills;
  createRetentionHold = api.createRetentionHold;
  listRetentionHolds = api.listRetentionHolds;
  checkResourceAction = api.checkResourceAction;

  // Tier 3 — Compensation
  compensationStats = api.compensationStats;
  listCompensationPolicies = api.listCompensationPolicies;
  getCompensationPolicy = api.getCompensationPolicy;
  createCompensationPolicy = api.createCompensationPolicy;
  detectBreach = api.detectBreach;
  listBreaches = api.listBreaches;
  calculateCredit = api.calculateCredit;
  applyCredit = api.applyCredit;
  markCreditPaid = api.markCreditPaid;
  rejectCredit = api.rejectCredit;
  listCredits = api.listCredits;
  raiseDispute = api.raiseDispute;
  resolveDispute = api.resolveDispute;
  listDisputes = api.listDisputes;
  compensationTenantSummary = api.compensationTenantSummary;
}

export function getClient() {
  return api;
}

// 重新导出类型（让页面只用 import {api, type Xxx} 就行）
export type {
  AgentConfig,
  AgentCreateRequest,
  AgentRunRequest,
  AgentRunResponse,
  AgentUpdateRequest,
  AgentsListResponse,
  ChatCompletionRequest,
  ChatCompletionResponse,
  HealthResponse,
  MemoryItem,
  MemoryType,
  MemoryCreateRequest,
  MemoryUpdateRequest,
  MemorySearchRequest,
  MemoriesListResponse,
  MemorySearchResponse,
  Notification,
  NotificationsListResponse,
  PdfReadPayload,
  PdfReadResponse,
  PdfMergePayload,
  PdfMergeResponse,
  PdfSplitPayload,
  PdfSplitResponse,
  RagDocument,
  RagSearchResult,
  RagDocsListResponse,
  RagSearchRequest,
  RagSearchResponse,
  RagDocDetailResponse,
  SandboxInfo,
  SandboxesListResponse,
  SandboxExecuteRequest,
  SandboxExecuteResponse,
  SandboxFileNode,
  SandboxSnapshot,
  SessionHistoryListResponse,
  Skill,
  SkillCreateRequest,
  SkillExecuteRequest,
  SkillExecuteResponse,
  SkillExtractionRequest,
  SkillExtractionResponse,
  SkillsListResponse,
  TeamConfig,
  TeamCreateRequest,
  TeamMode,
  ConsensusMethod,
  TeamMember,
  TeamMessage,
  TeamRunRequest,
  TeamRunResponse,
  TeamsListResponse,
  Tool,
  ToolExecuteRequest,
  ToolExecuteResponse,
  ToolsListResponse,
  WordReadPayload,
  WordReadResponse,
  WordWritePayload,
  WordWriteResponse,
  WordEditPayload,
  WordEditResponse,
  WordTemplatePayload,
  WordTemplateResponse,
  PptReadPayload,
  PptReadResponse,
  PptWritePayload,
  PptWriteResponse,
  ExcelReadPayload,
  ExcelReadResponse,
  ExcelAnalyzePayload,
  ExcelAnalyzeResponse,
  ExcelChartPayload,
  ExcelChartResponse,
  ExcelWritePayload,
  ExcelWriteResponse,
  MCPHealthResponse,
  MCPInvokeRequest,
  MCPInvokeResponse,
  MCPPreset,
  MCPPresetsListResponse,
  MCPServer,
  MCPServerCreateRequest,
  MCPServersListResponse,
  MCPTool,
  MCPToolsAllResponse,
  MCPToolsListResponse,
  AuditEntry,
  AuditStats,
  QuotaPolicy,
  QuotaPolicyCreate,
  QuotaActorStatus,
  QuotaSummary,
  UsageRecord,
  WebhookSubscription,
  WebhookCreate,
  WebhookDelivery,
  SchedulePayload,
  JobCreate,
  ScheduledJob,
  // Tier 3
  ReplicationPolicy,
  ReplicaStream,
  FailoverEvent,
  ReplicationStats,
  BackupSchedule,
  BackupRecord,
  RestoreJob,
  DRDrill,
  RetentionHold,
  RecoveryStats,
  CompensationPolicy,
  BreachEvent,
  Credit,
  Dispute,
  CompensationStats,
  JobExecution,
  JobStats,
};

// ─────────────────────────────────────────────────────────────────────────────
// 跨区域复制 (Replication) — Tier 3
// ─────────────────────────────────────────────────────────────────────────────

export interface ReplicationListResponse {
  policies: ReplicationPolicy[];
}

export interface ReplicationStreamListResponse {
  streams: ReplicaStream[];
}

export interface FailoverListResponse {
  failovers: FailoverEvent[];
}

export interface ReplicationPolicyResponse {
  policy: ReplicationPolicy;
}

export interface ReplicationStreamResponse {
  stream: ReplicaStream;
}

export interface FailoverResponse {
  failover: FailoverEvent;
}

// ─────────────────────────────────────────────────────────────────────────────
// 灾备恢复 (Recovery) — Tier 3
// ─────────────────────────────────────────────────────────────────────────────

export interface BackupScheduleListResponse {
  schedules: BackupSchedule[];
}

export interface BackupListResponse {
  backups: BackupRecord[];
}

export interface RestoreListResponse {
  restores: RestoreJob[];
}

export interface DrillListResponse {
  drills: DRDrill[];
}

export interface HoldListResponse {
  holds: RetentionHold[];
}

export interface ScheduleResponse {
  schedule: BackupSchedule;
}

export interface BackupResponse {
  backup: BackupRecord;
}

export interface RestoreResponse {
  restore: RestoreJob;
}

export interface DrillResponse {
  drill: DRDrill;
}

export interface HoldResponse {
  hold: RetentionHold;
}

// ─────────────────────────────────────────────────────────────────────────────
// SLA 违约赔付 (Compensation) — Tier 3
// ─────────────────────────────────────────────────────────────────────────────

export interface CompensationPolicyListResponse {
  policies: CompensationPolicy[];
}

export interface BreachListResponse {
  breaches: BreachEvent[];
}

export interface CreditListResponse {
  credits: Credit[];
}

export interface DisputeListResponse {
  disputes: Dispute[];
}

export interface CompensationPolicyResponse {
  policy: CompensationPolicy;
}

export interface BreachResponse {
  breach: BreachEvent;
}

export interface CreditResponse {
  credit: Credit;
}

export interface DisputeResponse {
  dispute: Dispute;
}

// RagSearchPayload / TeamRunPayload 通过 alias 重新声明在文件顶部（不能放在这里）
