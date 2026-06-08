/**
 * DATA-AI 后端 API 类型定义
 * 与 src/data_ai/core/api/server.py 中的 Pydantic schema 一一对应
 */

export type Role = "system" | "user" | "assistant" | "tool";

export interface ChatMessage {
  role: Role;
  content: string;
  name?: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ToolCall {
  id: string;
  index?: number;
  type: "function";
  function: {
    name: string;
    arguments: string;
  };
}

export interface Tool {
  type: "function";
  function: {
    name: string;
    description: string;
    parameters: {
      type: "object";
      properties: Record<string, JsonSchema>;
      required?: string[];
    };
  };
}

export type JsonSchema =
  | { type: "string"; description?: string; enum?: string[]; default?: unknown }
  | { type: "number"; description?: string; default?: number; minimum?: number; maximum?: number }
  | { type: "integer"; description?: string; default?: number }
  | { type: "boolean"; description?: string; default?: boolean }
  | { type: "array"; description?: string; items?: JsonSchema; default?: unknown[] }
  | {
      type: "object";
      description?: string;
      properties?: Record<string, JsonSchema>;
      default?: object;
    };

export interface ChatCompletionRequest {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  stream?: boolean;
  tools?: Tool[];
  tool_choice?: string | object;
  user?: string;
  agent_mode?: "react" | "tool_call";
  enable_tools?: boolean;
  tool_names?: string[];
}

export interface ChatCompletionResponse {
  id: string;
  object: "chat.completion";
  created: number;
  model: string;
  choices: Array<{
    index: number;
    message: ChatMessage;
    finish_reason: string | null;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

export interface ChatCompletionChunk {
  id: string;
  object: "chat.completion.chunk";
  created: number;
  model: string;
  choices: Array<{
    index: number;
    delta: {
      role?: Role;
      content?: string;
      tool_calls?: ToolCall[];
    };
    finish_reason?: string;
  }>;
}

export interface ModelInfo {
  id: string;
  object: "model";
  created: number;
  owned_by: string;
  permission?: object[];
  root?: string;
  parent?: string;
}

export interface ModelsResponse {
  object: "list";
  data: ModelInfo[];
}

export interface ToolInfo {
  name: string;
  description: string;
  category?: string;
  parameters: Tool["function"]["parameters"];
}

export interface ToolsResponse {
  object: "list";
  data: ToolInfo[];
}

export interface ToolExecuteRequest {
  tool: string;
  parameters: Record<string, unknown>;
}

export interface ToolExecuteResponse {
  success: boolean;
  result: unknown;
  error?: string;
  execution_time_ms: number;
}

export interface HealthResponse {
  status: "healthy" | "degraded" | "down";
  version: string;
  timestamp: number;
  components: Record<string, string>;
}

/* ============== Extensions / Diagnostics ============== */

/** 后端 /v1/extensions/health 详细返回 — 供 settings UI 连接诊断 */
export interface ExtensionsHealthResponse {
  status: "ok" | "degraded" | "down";
  version: string;
  api_version: string;
  uptime_ms: number | null;
  ts: number;
  process: { pid: number; python: string; platform: string };
  models_count: number;
  tools_count: number;
  capabilities: string[];
  extensions: {
    agents: number;
    teams: number;
    memories: number;
    rag_documents: number;
    sandboxes: number;
    skills: number;
    notifications: number;
  };
  endpoints: Record<string, string>;
}

/* ============== Office types ============== */

export interface WordReadRequest {
  file_path: string;
  extract_tables?: boolean;
  extract_images?: boolean;
}
export interface WordReadResponse {
  file_path: string;
  file_name: string;
  file_size: number;
  paragraphs: Array<{ text: string; style: string }>;
  tables: Array<{ index: number; rows: number; cols: number; data: string[][] }>;
  images: Array<{ type: string }>;
  metadata: Record<string, string>;
  word_count: number;
  char_count: number;
}

export interface ExcelReadResponse {
  file_path: string;
  file_name: string;
  file_size: number;
  sheets: Array<{
    name: string;
    dimensions: string;
    max_row: number;
    max_column: number;
    headers: unknown[];
    data: Array<Array<{ column: string; row: number; value: unknown; formula?: string }>>;
  }>;
  metadata: Record<string, unknown>;
}

export interface ExcelAnalyzeResponse {
  file_path: string;
  analysis_type: "summary" | "stats" | "correlation";
  results: Record<string, unknown>;
}

export interface PptReadResponse {
  file_path: string;
  file_name: string;
  file_size: number;
  slides: Array<{
    slide_number: number;
    shapes: Array<{ type: string; name: string; text?: string; table?: string[][] }>;
    text: string[];
    notes: string;
  }>;
  metadata: Record<string, string>;
  total_slides: number;
}

export interface PdfReadResponse {
  file_path: string;
  file_name: string;
  file_size: number;
  pages: Array<{ page_number: number; text: string; char_count: number }>;
  total_pages: number;
  metadata: Record<string, string>;
}

export interface WordReadPayload {
  file_path: string;
  extract_tables?: boolean;
  extract_images?: boolean;
}

export interface WordWritePayload {
  file_path: string;
  content: string;
  title?: string;
  author?: string;
  format?: "text" | "markdown" | "html";
}

export interface WordWriteResponse {
  file_path: string;
  file_size: number;
  paragraphs_written: number;
}

export interface WordEditPayload {
  file_path: string;
  operation: "replace" | "append_paragraph" | "add_heading" | "add_table";
  find?: string;
  replace?: string;
  text?: string;
  level?: number;
  table?: string[][];
}

export interface WordEditResponse {
  file_path: string;
  operation: string;
  success: boolean;
  changes: number;
}

export interface WordTemplatePayload {
  template_path: string;
  data: Record<string, unknown>;
  output_path: string;
}

export interface WordTemplateResponse {
  output_path: string;
  file_size: number;
  replacements: number;
}

export interface PptReadPayload {
  file_path: string;
}

export interface PptWritePayload {
  file_path: string;
  title: string;
  slides: Array<{
    title?: string;
    content: string;
    layout?: "title" | "title_and_content" | "section" | "blank";
    notes?: string;
  }>;
}

export interface PptWriteResponse {
  file_path: string;
  file_size: number;
  total_slides: number;
}

export interface ExcelReadPayload {
  file_path: string;
  sheet_name?: string;
}

export interface ExcelAnalyzePayload {
  file_path: string;
  analysis_type: "summary" | "stats" | "correlation";
}

export interface ExcelChartPayload {
  file_path: string;
  chart_type: "bar" | "line" | "pie" | "scatter";
  sheet_name?: string;
  data_range: string;
  output_path?: string;
}

export interface ExcelChartResponse {
  output_path: string;
  file_size: number;
  chart_type: string;
  data_points: number;
}

export interface ExcelWritePayload {
  file_path: string;
  // 二维数组直接作为表格内容写入；
  // 或传入 { headers, rows } 对象；或传 JSON 字符串
  data: string | unknown[][] | { headers: string[]; rows: unknown[][] };
  sheet_name?: string;
}

export interface ExcelWriteResponse {
  file_path: string;
  file_size: number;
  rows: number;
  columns: number;
  success: boolean;
}

export interface PdfMergePayload {
  file_paths: string[];
  output_path: string;
}

export interface PdfMergeResponse {
  output_path: string;
  file_size: number;
  merged_count: number;
}

export interface PdfSplitPayload {
  file_path: string;
  ranges: string;
  output_dir: string;
}

export interface PdfSplitResponse {
  output_dir: string;
  output_files: string[];
  split_count: number;
}

/* ============== Tools (legacy alias) ============== */

export type ToolsListResponse = ToolsResponse;

export interface ChatCompletionRequestPayload {
  model: string;
  messages: ChatMessage[];
  temperature?: number;
  max_tokens?: number;
  top_p?: number;
  stream?: boolean;
  tools?: Tool[];
}

/* ============== Agent types ============== */

export type AgentStatus = "idle" | "thinking" | "executing" | "streaming" | "finished" | "error";

export interface AgentConfig {
  id: string;
  name: string;
  description?: string;
  model: string;
  system_prompt: string;
  tool_names: string[];
  max_iterations: number;
  temperature: number;
  enable_reflection: boolean;
  status?: AgentStatus;
  created_at: number;
  updated_at: number;
}

export interface AgentsListResponse {
  object: "list";
  data: AgentConfig[];
  total: number;
}

export interface AgentCreateRequest {
  name: string;
  description?: string;
  model: string;
  system_prompt: string;
  tool_names: string[];
  max_iterations: number;
  temperature: number;
  enable_reflection: boolean;
}

export type AgentUpdateRequest = Partial<AgentCreateRequest>;

export interface AgentRunRequest {
  input: string;
  session_id?: string;
  stream?: boolean;
}

export interface AgentRunResponse {
  run_id: string;
  agent_id: string;
  input: string;
  status: AgentStatus;
  output: string;
  tool_calls: ToolCall[];
  iterations: number;
  started_at: number;
  finished_at?: number;
  duration_ms?: number;
  usage?: ChatCompletionResponse["usage"];
  error?: string;
}

export interface AgentRunEvent {
  type: "thinking" | "tool_call" | "tool_result" | "token" | "finish" | "error";
  ts: number;
  content?: string;
  tool_call?: ToolCall;
  tool_result?: unknown;
  error?: string;
  status?: AgentStatus;
}

export interface AgentRunsListResponse {
  object: "list";
  data: AgentRunResponse[];
  total: number;
}

/* ============== Team types ============== */

export type TeamMode = "collaboration" | "competition" | "hierarchy";
export type ConsensusMethod =
  | "majority_vote"
  | "llm_synthesis"
  | "concatenation"
  | "semantic"
  | "length_based"
  | "weighted";

export interface TeamMember {
  id: string;
  name: string;
  role: string;
  agent_id?: string;
  weight?: number;
  /** 可选：该成员使用的 LLM 模型（后端 Pydantic 会忽略未声明字段）*/
  model?: string;
  /** 可选：该成员的系统提示词 */
  system_prompt?: string;
}

export interface TeamConfig {
  id: string;
  name: string;
  description?: string;
  mode: TeamMode;
  consensus_method: ConsensusMethod;
  members: TeamMember[];
  created_at: number;
  updated_at: number;
}

export interface TeamsListResponse {
  object: "list";
  data: TeamConfig[];
  total: number;
}

export interface TeamCreateRequest {
  name: string;
  description?: string;
  mode: TeamMode;
  consensus_method: ConsensusMethod;
  members: Array<Omit<TeamMember, "id"> & { id?: string }>;
}

export interface TeamRunRequest {
  input: string;
  consensus_method?: ConsensusMethod;
}

export interface TeamVote {
  member: string;
  answer: string;
  votes: number;
  confidence: number;
}

export interface TeamRunResponse {
  run_id: string;
  team_id: string;
  status: "running" | "finished" | "error";
  consensus_method: ConsensusMethod;
  member_answers: Array<{
    member: string;
    answer: string;
    confidence: number;
    duration_ms: number;
  }>;
  votes: TeamVote[];
  final_answer: string;
  started_at: number;
  finished_at?: number;
  duration_ms?: number;
  error?: string;
}

export interface TeamMessage {
  id: string;
  from: string;
  to: string;
  content: string;
  ts: number;
}

/* ============== Memory types ============== */

export type MemoryType = "short_term" | "long_term" | "episodic" | "semantic";

export interface MemoryItem {
  id: string;
  type: MemoryType;
  content: string;
  importance: number;
  tags: string[];
  created_at: number;
  pinned?: boolean;
  metadata?: Record<string, unknown>;
}

export interface MemoriesListResponse {
  object: "list";
  data: MemoryItem[];
  total: number;
  stats: Record<MemoryType, number>;
}

export interface MemoryCreateRequest {
  type: MemoryType;
  content: string;
  importance: number;
  tags: string[];
  pinned?: boolean;
  metadata?: Record<string, unknown>;
}

export type MemoryUpdateRequest = Partial<MemoryCreateRequest>;

export interface PdfReadPayload {
  file_path: string;
  page_range?: string;
}

export interface MemorySearchRequest {
  query: string;
  type?: MemoryType;
  top_k?: number;
}

export interface MemorySearchResponse {
  query: string;
  results: Array<{ id: string; content: string; score: number; type: MemoryType }>;
}

/* ============== RAG types ============== */

export type RagDocType = "pdf" | "docx" | "txt" | "md" | "html" | "pptx" | "xlsx";
export type RagDocStatus = "processing" | "ready" | "error";

export interface RagDocument {
  id: string;
  name: string;
  type: RagDocType;
  size: number;
  chunks: number;
  uploaded_at: number;
  status: RagDocStatus;
  metadata?: Record<string, unknown>;
  embedder?: string;
  vector_dim?: number;
  store?: string;
}

export interface RagDocsListResponse {
  object: "list";
  data: RagDocument[];
  total: number;
}

export interface RagSearchRequest {
  query: string;
  top_k?: number;
  embedder?: string;
  document_ids?: string[];
}

export interface RagSearchResult {
  id: string;
  content: string;
  score: number;
  document_id: string;
  document_name: string;
  chunk_index: number;
  metadata?: Record<string, unknown>;
}

export interface RagSearchResponse {
  query: string;
  results: RagSearchResult[];
  embedder: string;
  duration_ms: number;
}

export interface RagChunk {
  id: string;
  document_id: string;
  index: number;
  content: string;
  tokens: number;
  metadata?: Record<string, unknown>;
}

export interface RagDocDetailResponse {
  document: RagDocument;
  chunks: RagChunk[];
  total_chunks: number;
}

/* ============== Sandbox types ============== */

export type SandboxType = "local" | "docker";
export type SandboxStatus = "running" | "stopped" | "creating" | "error";

export interface SandboxInfo {
  id: string;
  name: string;
  type: SandboxType;
  status: SandboxStatus;
  cpu: number;
  memory: number;
  network: boolean;
  timeout: number;
  memory_limit?: number;
  cpu_limit?: number;
  image?: string;
  created_at: number;
  uptime: number;
  workspace?: string;
}

export interface SandboxesListResponse {
  object: "list";
  data: SandboxInfo[];
  total: number;
}

export interface SandboxCreateRequest {
  name: string;
  type: SandboxType;
  timeout?: number;
  memory?: number;
  cpu?: number;
  network?: boolean;
  image?: string;
}

export interface SandboxExecuteRequest {
  language: "python" | "javascript" | "bash" | "go" | "rust";
  code: string;
  timeout?: number;
  stdin?: string;
  env?: Record<string, string>;
}

export interface SandboxExecuteResponse {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
  duration_ms: number;
  files_changed?: string[];
}

export interface SandboxFileNode {
  name: string;
  path: string;
  type: "file" | "dir";
  size?: number;
  modified_at?: number;
  children?: SandboxFileNode[];
}

export interface SandboxFilesResponse {
  sandbox_id: string;
  path: string;
  tree: SandboxFileNode[];
}

export interface SandboxFileContent {
  path: string;
  content: string;
  size: number;
  language?: string;
}

export interface SandboxSnapshot {
  name: string;
  created_at: number;
  size: number;
  description?: string;
}

/* ============== Skills types ============== */

export interface Skill {
  name: string;
  description: string;
  version: string;
  tags: string[];
  category: string;
  parameters: Array<{
    name: string;
    type: string;
    required: boolean;
    description: string;
    default?: unknown;
  }>;
  source?: "builtin" | "user" | "extracted";
  yaml?: string;
}

export interface SkillsListResponse {
  object: "list";
  data: Skill[];
  total: number;
}

export interface SkillExecuteRequest {
  parameters: Record<string, unknown>;
}

export interface SkillExecuteResponse {
  success: boolean;
  output: unknown;
  error?: string;
  duration_ms: number;
}

export interface SkillCreateRequest {
  name: string;
  description: string;
  version?: string;
  tags?: string[];
  category?: string;
  parameters: Array<{
    name: string;
    type: string;
    required: boolean;
    description: string;
    default?: unknown;
  }>;
  implementation?: string;
  yaml?: string;
}

export interface SkillExtractionRequest {
  source: string;
  source_type: "text" | "file" | "url";
}

export interface SkillExtractionResponse {
  candidates: Array<{
    name: string;
    description: string;
    parameters: Array<{ name: string; type: string; required: boolean; description: string }>;
    confidence: number;
  }>;
}

/* ============== Notification types ============== */

export type NotificationLevel = "info" | "success" | "warning" | "error";

export interface Notification {
  id: string;
  level: NotificationLevel;
  title: string;
  description?: string;
  ts: number;
  read: boolean;
  link?: string;
  category?: string;
}

export interface NotificationsListResponse {
  object: "list";
  data: Notification[];
  unread_count: number;
}

/* ============== Sessions persistence types ============== */

export interface SessionHistoryItem {
  id: string;
  title: string;
  model: string;
  created_at: number;
  updated_at: number;
  message_count: number;
  preview?: string;
}

export interface SessionHistoryListResponse {
  object: "list";
  data: SessionHistoryItem[];
  total: number;
}

// ====================== P1-10 企业治理 ======================

export interface AuditEntry {
  id: string;
  timestamp: number;
  actor: string;
  actor_type: "api_key" | "user" | "system" | "anonymous";
  action: string;
  resource_type: string;
  resource_id: string;
  method: string;
  path: string;
  status_code: number;
  duration_ms: number;
  ip: string;
  user_agent: string;
  request_body?: Record<string, unknown> | null;
  response_summary?: string;
  extra?: Record<string, unknown>;
}

export interface AuditStats {
  total: number;
  by_status: Record<string, number>;
  top_actions: Array<{ action: string; count: number }>;
}

export interface QuotaPolicy {
  scope: "global" | "key" | "user";
  scope_id: string;
  daily_token_limit: number | null;
  monthly_token_limit: number | null;
  daily_request_limit: number | null;
  qps_limit: number | null;
  max_concurrent: number | null;
  enabled: boolean;
}

export interface QuotaPolicyCreate {
  scope?: "global" | "key" | "user";
  scope_id?: string;
  daily_token_limit?: number;
  monthly_token_limit?: number;
  daily_request_limit?: number;
  qps_limit?: number;
  max_concurrent?: number;
  enabled?: boolean;
}

export interface UsageRecord {
  timestamp: number;
  actor: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
  endpoint: string;
}

export interface QuotaSummary {
  total_requests: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
  by_model: Record<string, { requests: number; tokens: number; cost_usd: number }>;
}

export interface QuotaActorStatus {
  actor: string;
  policies: Array<QuotaPolicy & { daily_token_remaining?: number; daily_token_pct?: number; daily_request_remaining?: number }>;
  usage_today: QuotaSummary;
}

export interface WebhookSubscription {
  id: string;
  name: string;
  url: string;
  secret: string;
  events: string[];
  active: boolean;
  created_at: number;
  description: string;
  custom_headers: Record<string, string>;
  max_retries: number;
  timeout_sec: number;
}

export interface WebhookCreate {
  name: string;
  url: string;
  events: string[];
  description?: string;
  custom_headers?: Record<string, string>;
  max_retries?: number;
  timeout_sec?: number;
  active?: boolean;
}

export interface WebhookDelivery {
  id: string;
  subscription_id: string;
  event: string;
  url: string;
  payload: Record<string, unknown>;
  status: "pending" | "success" | "failed" | "retrying";
  status_code: number;
  response_body: string;
  attempt: number;
  duration_ms: number;
  timestamp: number;
  error: string;
  next_retry_at: number | null;
}

export interface SchedulePayload {
  kind: "cron" | "at" | "every";
  expression: string;
}

export interface JobCreate {
  name: string;
  description?: string;
  action_type: "http" | "agent_run" | "memory_cleanup" | "rag_reindex" | "shell";
  action_payload?: Record<string, unknown>;
  schedule: SchedulePayload;
  enabled?: boolean;
  timeout_sec?: number;
}

export interface ScheduledJob {
  id: string;
  name: string;
  description: string;
  action_type: string;
  action_payload: Record<string, unknown>;
  schedule: SchedulePayload;
  enabled: boolean;
  created_at: number;
  created_by: string;
  last_run_at: number | null;
  last_status: "success" | "failed" | "running" | "skipped" | "never";
  next_run_at: number | null;
  run_count: number;
  failure_count: number;
  timeout_sec: number;
  max_retries: number;
}

export interface JobExecution {
  id: string;
  job_id: string;
  started_at: number;
  ended_at: number | null;
  status: "running" | "success" | "failed" | "timeout";
  output: string;
  error: string;
  duration_ms: number;
  attempt: number;
}

export interface JobStats {
  total_jobs: number;
  enabled_jobs: number;
  total_executions: number;
  by_status: Record<string, number>;
}

// ====================== MCP (Model Context Protocol) ======================

export type MCPServerType = "stdio" | "sse" | "http";
export type MCPServerStatus = "active" | "inactive" | "error";

export interface MCPServer {
  id: string;
  name: string;
  description?: string;
  type: MCPServerType;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  status: MCPServerStatus;
  enabled: boolean;
  icon?: string;
  last_error?: string | null;
  last_check_at?: number | null;
  created_at?: number;
  updated_at?: number;
  is_builtin?: boolean;
  tools?: MCPTool[];
}

export interface MCPServerCreateRequest {
  id?: string;
  name: string;
  description?: string;
  type?: MCPServerType;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  icon?: string;
  enabled?: boolean;
}

export interface MCPServersListResponse {
  object: "list";
  data: MCPServer[];
  total: number;
  builtin_count: number;
  user_count: number;
}

export interface MCPPreset {
  id: string;
  name: string;
  description: string;
  type: MCPServerType;
  command: string;
  args: string[];
  icon: string;
  enabled: boolean;
  is_builtin: boolean;
  tools?: string[];
}

export interface MCPPresetsListResponse {
  object: "list";
  data: MCPPreset[];
  total: number;
  hint?: string;
}

export interface MCPTool {
  name: string;
  description: string;
  inputSchema: {
    type: "object";
    properties: Record<string, JsonSchema>;
    required?: string[];
  };
  server_id: string;
  server_name: string;
}

export interface MCPToolsListResponse {
  object: "list";
  server_id: string;
  server_name: string;
  data: MCPTool[];
  total: number;
  cached: boolean;
  trace_id?: string;
}

export interface MCPToolsAllResponse {
  object: "list";
  data: MCPTool[];
  openai_format: Tool[];
  total: number;
}

export interface MCPInvokeRequest {
  server_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  timeout?: number;
}

export interface MCPInvokeResponse {
  success: boolean;
  content?: unknown;
  error?: string;
  error_class?: string;
  duration_ms: number;
  trace_id: string;
  server_id: string;
  tool_name: string;
}

export interface MCPHealthResponse {
  status: string;
  total_servers: number;
  active_servers: number;
  error_servers: number;
  total_tools: number;
  builtin_servers: number;
  user_servers: number;
  trace_id: string;
  checks: Record<string, { ok: boolean; value: unknown }>;
  fixes: string[];
}

// ============================================================================
// P1-11 企业治理 Tier 2 — Tenants / RBAC / Billing / SLA / SSO / Residency / Audit Chain
// ============================================================================

// ---------- Tenants ----------
export type PlanTier = "free" | "starter" | "pro" | "enterprise";
export type TenantStatus = "active" | "suspended" | "archived";
export type MemberRole = "owner" | "admin" | "member" | "viewer";

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: PlanTier;
  status: TenantStatus;
  region: string;
  contact_email: string;
  metadata: Record<string, unknown>;
  limits: Record<string, number>;
  created_at: number;
  updated_at: number;
}

export interface TenantMember {
  tenant_id: string;
  user_id: string;
  role: MemberRole;
  invited_by: string;
  joined_at: number;
  last_active_at: number;
}

export interface TenantStats {
  total_tenants: number;
  total_members: number;
  by_plan: Record<string, number>;
  by_status: Record<string, number>;
}

export interface TenantCreateRequest {
  name: string;
  slug?: string;
  plan?: PlanTier;
  region?: string;
  contact_email?: string;
  limits?: Record<string, number>;
  metadata?: Record<string, unknown>;
}

export interface TenantUpdateRequest {
  name?: string;
  plan?: PlanTier;
  status?: TenantStatus;
  region?: string;
  contact_email?: string;
  limits?: Record<string, number>;
}

// ---------- RBAC ----------
export interface Permission {
  resource: string;
  action: string;
  effect?: "allow" | "deny";
  description?: string;
}

export interface RBACRole {
  id: string;
  name: string;
  description: string;
  permissions: Permission[];
  parent_roles: string[];
  tenant_id: string;
  is_system: boolean;
  created_at: number;
}

export interface Policy {
  id: string;
  name: string;
  description: string;
  conditions: Array<{ field: string; op: string; value: unknown }>;
  effect: "allow" | "deny";
  priority: number;
  tenant_id: string;
  enabled: boolean;
  created_at: number;
}

export interface Assignment {
  id: string;
  user_id: string;
  role_id: string;
  tenant_id: string;
  granted_by: string;
  granted_at: number;
  expires_at: number;
  delegation_from: string;
}

export interface Decision {
  allowed: boolean;
  reason: string;
  matched_role: string;
  matched_policy: string;
  evaluated_at: number;
}

export interface RoleCreateRequest {
  name: string;
  description?: string;
  permissions?: Permission[];
  parent_roles?: string[];
  tenant_id?: string;
}

export interface PolicyCreateRequest {
  name: string;
  description?: string;
  conditions: Array<{ field: string; op: string; value: unknown }>;
  effect?: "allow" | "deny";
  priority?: number;
  tenant_id?: string;
  enabled?: boolean;
}

export interface AssignmentCreateRequest {
  user_id: string;
  role_id: string;
  tenant_id?: string;
  granted_by?: string;
  expires_at?: number;
}

export interface RbacCheckRequest {
  user_id: string;
  resource: string;
  action: string;
  tenant_id?: string;
  env?: Record<string, unknown>;
  resource_ctx?: Record<string, unknown>;
}

// ---------- Billing ----------
export interface PricingModel {
  model_id: string;
  input_per_1k: number;
  output_per_1k: number;
  cached_input_per_1k: number;
  currency: string;
  notes?: string;
}

export interface PricingModelCreate {
  model_id: string;
  input_per_1k: number;
  output_per_1k: number;
  cached_input_per_1k?: number;
  currency?: string;
}

export interface UsageRecord {
  id: string;
  tenant_id: string;
  user_id: string;
  cost_center_id: string;
  project: string;
  resource_type: string;
  resource_id: string;
  model_id: string;
  prompt_tokens: number;
  completion_tokens: number;
  cached_tokens: number;
  cost_usd: number;
  currency: string;
  occurred_at: number;
}

export interface UsageRecordCreate {
  tenant_id?: string;
  user_id?: string;
  cost_center_id?: string;
  project?: string;
  resource_type?: string;
  resource_id?: string;
  model_id?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  cached_tokens?: number;
}

export interface Budget {
  id: string;
  name: string;
  scope: "tenant" | "cost_center" | "project" | "user";
  scope_id: string;
  period: "daily" | "weekly" | "monthly" | "quarterly" | "annual" | "custom";
  amount_usd: number;
  hard_limit: boolean;
  warn_threshold: number;
  enabled: boolean;
  created_at: number;
  updated_at: number;
}

export interface BudgetCreate {
  name: string;
  scope?: "tenant" | "cost_center" | "project" | "user";
  scope_id?: string;
  period?: "daily" | "weekly" | "monthly" | "quarterly" | "annual" | "custom";
  amount_usd: number;
  hard_limit?: boolean;
  warn_threshold?: number;
  enabled?: boolean;
}

export interface BudgetAlert {
  budget_id: string;
  budget_name: string;
  used_usd: number;
  limit_usd: number;
  usage_pct: number;
  level: "warning" | "exceeded";
}

export interface CostCenter {
  id: string;
  tenant_id: string;
  name: string;
  code: string;
  parent_id: string;
  manager_user_id: string;
  monthly_budget_usd: number;
  metadata: Record<string, unknown>;
  created_at: number;
}

export interface CostCenterCreate {
  tenant_id?: string;
  name: string;
  code?: string;
  parent_id?: string;
  manager_user_id?: string;
  monthly_budget_usd?: number;
}

export interface BillingSummary {
  total_cost_usd: number;
  total_tokens: number;
  total_requests: number;
  by_model: Record<string, { cost_usd: number; tokens: number; requests: number }>;
  by_cost_center: Record<string, number>;
  by_resource_type: Record<string, number>;
  since: number;
  until: number;
}

export interface CostDaySeries {
  date: string;
  cost_usd: number;
}

export interface TopSpender {
  key: string;
  cost_usd: number;
}

// ---------- SLA ----------
export type SLIType = "availability" | "error_rate" | "latency_p99" | "latency_p95" | "throughput";
export type ComponentHealth = "operational" | "degraded" | "partial_outage" | "major_outage" | "maintenance";
export type SevLevel = "minor" | "major" | "critical";
export type IncidentState = "investigating" | "identified" | "monitoring" | "resolved";

export interface SLO {
  id: string;
  name: string;
  component_id: string;
  sli_type: SLIType;
  target_value: number;
  error_budget_window_days: number;
  description: string;
  enabled: boolean;
}

export interface SLOCreate {
  name: string;
  component_id: string;
  sli_type: SLIType;
  target_value: number;
  error_budget_window_days?: number;
  description?: string;
  enabled?: boolean;
}

export interface SLOResult {
  slo_id: string;
  name: string;
  type: SLIType;
  current_value: number | null;
  target: number;
  status: "ok" | "breach" | "no_data";
  sample_size: number;
  window_sec?: number;
}

export interface SLAComponent {
  id: string;
  name: string;
  description: string;
  status: ComponentHealth;
  updated_at: number;
}

export interface SLIProbe {
  component_id: string;
  timestamp: number;
  success: boolean;
  latency_ms: number;
  error_code: number;
}

export interface SLIProbeCreate {
  component_id: string;
  success: boolean;
  latency_ms?: number;
  error_code?: number;
}

export interface Incident {
  id: string;
  title: string;
  severity: SevLevel;
  status: IncidentState;
  affected_components: string[];
  started_at: number;
  resolved_at: number;
  updates: Array<{ at: number; status: string; message: string; by?: string }>;
  root_cause: string;
  resolution: string;
}

export interface IncidentCreate {
  title: string;
  severity?: SevLevel;
  affected_components?: string[];
  message?: string;
}

export interface IncidentUpdate {
  status: IncidentState;
  message?: string;
  by?: string;
}

export interface SLAStatusPage {
  overall: "operational" | "degraded" | "major_outage";
  components: SLAComponent[];
  active_incidents: Incident[];
  generated_at: number;
}

export interface SLAMonthlyReport {
  year: number;
  month: number;
  period: { start: number; end: number };
  incident_count: number;
  severity_breakdown: Record<string, number>;
  total_downtime_sec: number;
  total_downtime_human: string;
  mttr_sec: number;
  availability_pct: number | null;
  slo_reports: SLOResult[];
  incidents: Incident[];
}

// ---------- SSO ----------
export type IdpType = "oidc" | "saml" | "ldap";

export interface IdentityProvider {
  id: string;
  name: string;
  type: IdpType;
  issuer: string;
  client_id: string;
  client_secret: string;
  authorization_endpoint: string;
  token_endpoint: string;
  userinfo_endpoint: string;
  jwks_uri: string;
  scopes: string[];
  allowed_email_domains: string[];
  default_role: string;
  auto_provision: boolean;
  enabled: boolean;
  metadata: Record<string, unknown>;
  created_at: number;
}

export interface IdentityProviderCreate {
  name: string;
  type?: IdpType;
  issuer?: string;
  client_id?: string;
  client_secret?: string;
  authorization_endpoint?: string;
  token_endpoint?: string;
  userinfo_endpoint?: string;
  jwks_uri?: string;
  scopes?: string[];
  allowed_email_domains?: string[];
  default_role?: string;
  auto_provision?: boolean;
}

export interface SSOSession {
  id: string;
  user_id: string;
  email: string;
  tenant_id: string;
  idp_id: string;
  provider_type: IdpType;
  access_token: string;
  refresh_token: string;
  id_token: string;
  expires_at: number;
  ip: string;
  user_agent: string;
  mfa_verified: boolean;
  created_at: number;
  last_used_at: number;
}

export interface SSOLoginResult {
  ok: boolean;
  session_id: string;
  user_id: string;
  email: string;
  tenant_id: string;
  expires_at: number;
}

export interface SCIMUser {
  id: string;
  user_name: string;
  display_name: string;
  active: boolean;
  emails: Array<{ value: string; primary: boolean }>;
  groups: string[];
  created_at: number;
  last_modified: number;
}

export interface SCIMUserCreate {
  user_name: string;
  display_name?: string;
  active?: boolean;
  groups?: string[];
}

// ---------- Residency ----------
export type DataClass =
  | "user_data"
  | "pii"
  | "phi"
  | "financial"
  | "audit_log"
  | "model_artifact"
  | "embedding"
  | "session"
  | "metric";

export interface Region {
  id: string;
  name: string;
  country: string;
  tier: string;
  status: "active" | "degraded" | "offline";
  storage_backend: string;
  endpoint: string;
  metadata: Record<string, unknown>;
  created_at: number;
}

export interface RegionCreate {
  id: string;
  name?: string;
  country?: string;
  tier?: string;
  storage_backend?: string;
  endpoint?: string;
}

export interface ResidencyPolicy {
  id: string;
  name: string;
  data_class: DataClass;
  allowed_regions: string[];
  forbidden_regions: string[];
  allow_cross_region_transfer: boolean;
  encryption_required: boolean;
  retention_days: number;
  enabled: boolean;
  description: string;
}

export interface ResidencyPolicyCreate {
  name: string;
  data_class: DataClass;
  allowed_regions?: string[];
  forbidden_regions?: string[];
  allow_cross_region_transfer?: boolean;
  encryption_required?: boolean;
  retention_days?: number;
  enabled?: boolean;
  description?: string;
}

export interface ResidencyAssignment {
  id: string;
  resource_id: string;
  data_class: DataClass;
  region_id: string;
  tenant_id: string;
  policy_id: string;
  encrypted: boolean;
  created_at: number;
  transferred_at: number;
  transferred_from: string;
}

export interface ResidencyRouteRequest {
  resource_id: string;
  data_class?: DataClass;
  tenant_id?: string;
  prefer_region?: string;
}

export interface ResidencyStats {
  total_assignments: number;
  by_region: Record<string, number>;
  by_data_class: Record<string, number>;
  regions: number;
  policies: number;
}

// ---------- Audit Chain ----------
export interface AuditChainBlock {
  id: string;
  index: number;
  entry_ids: string[];
  entry_count: number;
  prev_root: string;
  root: string;
  timestamp: number;
  sealed: boolean;
}

export interface AuditChainIntegrity {
  ok: boolean;
  block_count: number;
  issues: string[];
  latest_root: string;
}

export interface AuditChainProof {
  block_id: string;
  entry_id: string;
  entry_index: number;
  root: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// 跨区域复制 (Replication) — Tier 3
// ─────────────────────────────────────────────────────────────────────────────

export type ReplicationMode = "sync" | "async" | "semi_sync";
export type StreamState = "healthy" | "lagging" | "degraded" | "paused" | "failed";
export type FailoverMode = "planned" | "emergency" | "drill";
export type FailoverState = "initiated" | "draining" | "promoting" | "switched" | "rolled_back" | "failed";

export interface ReplicationPolicy {
  id: string;
  name: string;
  source_region: string;
  target_region: string;
  mode: ReplicationMode;
  resource_types: string[];
  max_lag_sec: number;
  encryption: boolean;
  compression: boolean;
  enabled: boolean;
  created_at: number;
  metadata: Record<string, unknown>;
}

export interface ReplicaStream {
  id: string;
  policy_id: string;
  source_region: string;
  target_region: string;
  state: StreamState;
  lag_sec: number;
  bytes_sent: number;
  records_sent: number;
  bytes_failed: number;
  records_failed: number;
  last_error: string;
  last_error_at: number;
  last_sync_at: number;
  consecutive_failures: number;
  started_at: number;
  metadata: Record<string, unknown>;
}

export interface FailoverEvent {
  id: string;
  mode: FailoverMode;
  state: FailoverState;
  from_region: string;
  to_region: string;
  initiated_by: string;
  reason: string;
  affected_resources: string[];
  duration_sec: number;
  data_loss_records: number;
  rollback_supported: boolean;
  started_at: number;
  completed_at: number;
  notes: string;
  metadata: Record<string, unknown>;
}

export interface ReplicationStats {
  total_policies: number;
  total_streams: number;
  total_failovers: number;
  active_region: string;
  stream_states: Record<string, number>;
  total_records_replicated: number;
  total_bytes_replicated: number;
  total_records_failed: number;
  avg_lag_sec: number;
  max_lag_sec: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// 灾备恢复 (Recovery) — Tier 3
// ─────────────────────────────────────────────────────────────────────────────

export type BackupType = "full" | "incremental" | "differential" | "snapshot";
export type BackupStatus = "pending" | "running" | "success" | "failed" | "expired" | "corrupted";
export type RestoreStatus = "pending" | "validating" | "running" | "success" | "failed" | "rolled_back";
export type DrillResult = "pass" | "pass_with_issues" | "fail";

export interface BackupSchedule {
  id: string;
  name: string;
  resource_type: string;
  backup_type: BackupType;
  cron_expr: string;
  retention_days: number;
  target_regions: string[];
  storage_class: string;
  encryption: boolean;
  enabled: boolean;
  next_run_at: number;
  last_run_at: number;
  created_at: number;
  metadata: Record<string, unknown>;
}

export interface BackupRecord {
  id: string;
  schedule_id: string;
  resource_type: string;
  backup_type: BackupType;
  status: BackupStatus;
  size_bytes: number;
  record_count: number;
  checksum: string;
  target_region: string;
  storage_path: string;
  started_at: number;
  completed_at: number;
  duration_sec: number;
  expires_at: number;
  error: string;
  encrypted: boolean;
  metadata: Record<string, unknown>;
}

export interface RestoreJob {
  id: string;
  backup_id: string;
  target_region: string;
  target_resource: string;
  status: RestoreStatus;
  progress_pct: number;
  records_restored: number;
  requested_by: string;
  reason: string;
  started_at: number;
  completed_at: number;
  duration_sec: number;
  validation_passed: boolean;
  error: string;
  metadata: Record<string, unknown>;
}

export interface DRDrill {
  id: string;
  name: string;
  schedule_id: string;
  backup_id: string;
  target_region: string;
  result: DrillResult;
  rto_actual_sec: number;
  rpo_actual_sec: number;
  rto_target_sec: number;
  rpo_target_sec: number;
  records_verified: number;
  records_mismatch: number;
  issues: string[];
  conducted_by: string;
  started_at: number;
  completed_at: number;
  notes: string;
  metadata: Record<string, unknown>;
}

export interface RetentionHold {
  id: string;
  resource_id: string;
  regulation: string;
  action: "preserve" | "erase";
  hold_until: number;
  reason: string;
  requested_by: string;
  created_at: number;
  released_at: number;
  metadata: Record<string, unknown>;
}

export interface RecoveryStats {
  total_schedules: number;
  total_backups: number;
  total_restores: number;
  total_drills: number;
  total_holds: number;
  active_holds: number;
  backup_status: Record<string, number>;
  drill_results: Record<string, number>;
  total_backup_size_bytes: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// SLA 违约赔付 (Compensation) — Tier 3
// ─────────────────────────────────────────────────────────────────────────────

export type BreachSeverity = "low" | "medium" | "high" | "critical";
export type CreditStatus = "pending" | "approved" | "applied" | "paid" | "disputed" | "rejected";
export type DisputeStatus = "open" | "investigating" | "resolved" | "rejected";

export interface CompensationTier {
  min_availability_pct: number;
  max_availability_pct: number;
  credit_pct: number;
  description: string;
}

export interface CompensationPolicy {
  id: string;
  name: string;
  plan_tier: string;
  target_availability_pct: number;
  measurement_window_days: number;
  tiers: CompensationTier[];
  max_credit_pct: number;
  monthly_cap_pct: number;
  auto_apply: boolean;
  created_at: number;
  metadata: Record<string, unknown>;
}

export interface BreachEvent {
  id: string;
  policy_id: string;
  tenant_id: string;
  severity: BreachSeverity;
  target_pct: number;
  actual_pct: number;
  downtime_sec: number;
  measurement_start: number;
  measurement_end: number;
  related_incident_ids: string[];
  affected_components: string[];
  detected_at: number;
  description: string;
  metadata: Record<string, unknown>;
}

export interface Credit {
  id: string;
  breach_id: string;
  policy_id: string;
  tenant_id: string;
  status: CreditStatus;
  base_amount_usd: number;
  credit_pct: number;
  credit_amount_usd: number;
  currency: string;
  period_start: number;
  period_end: number;
  approved_by: string;
  approved_at: number;
  applied_at: number;
  paid_at: number;
  created_at: number;
  notes: string;
  metadata: Record<string, unknown>;
}

export interface Dispute {
  id: string;
  credit_id: string;
  tenant_id: string;
  status: DisputeStatus;
  raised_by: string;
  reason: string;
  evidence: Record<string, unknown>;
  resolution: string;
  resolved_by: string;
  created_at: number;
  resolved_at: number;
  metadata: Record<string, unknown>;
}

export interface CompensationStats {
  total_policies: number;
  total_breaches: number;
  total_credits: number;
  total_disputes: number;
  breach_severity: Record<string, number>;
  credit_status: Record<string, number>;
  total_credit_amount_usd: number;
  applied_credit_amount_usd: number;
}
