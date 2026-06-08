/**
 * 统一错误处理：分类 + i18n + 去重。
 *
 * 设计目标：
 * 1. 把各种来源（fetch 抛错、APIError 抛错、AbortError、status code）
 *    归类成稳定的 ErrorCode，便于 UI 决定报什么 toast。
 * 2. 每类错误都有 i18n 化的标题 + 详情 + 修复建议。
 * 3. 同一条错误（msg + context）短时间内只报一次（用稳定 toast id）。
 * 4. 保留原始 cause 方便排查。
 *
 * 用法：
 *   try { await api.x() } catch (e) { reportError(e, "加载智能体") }
 *
 *   // 静默错误（仍然去重但只在 console 打 log）
 *   reportError(e, "models query", { silent: true })
 */
import { toast } from "@/components/ui/toaster";
import { APIError } from "@/lib/api/client";
import { getLocale } from "@/lib/i18n";
import * as React from "react";

/* ───────── ErrorCode 枚举 ───────── */

export type ErrorCode =
  | "ABORTED" // 用户主动停止
  | "TIMEOUT" // 请求超时
  | "NETWORK" // 网络不通（CORS、DNS、连接拒绝等）
  | "OFFLINE" // 浏览器离线
  | "UNAUTHORIZED" // 401
  | "FORBIDDEN" // 403
  | "NOT_FOUND" // 404
  | "VALIDATION" // 400/422
  | "RATE_LIMIT" // 429
  | "CONFLICT" // 409
  | "SERVER" // 5xx
  | "PARSER" // 后端返回无法解析
  | "UNKNOWN"; // 兜底

/* ───────── i18n 错误文案 ───────── */

type ErrorText = { title: string; detail: string; action?: string };

const EN: Record<ErrorCode, ErrorText> = {
  ABORTED: { title: "Stopped", detail: "The request was stopped by the user." },
  TIMEOUT: {
    title: "Request timed out",
    detail: "The backend did not respond in time.",
    action: "Check the network, or increase the timeout in Settings → Connection.",
  },
  NETWORK: {
    title: "Network error",
    detail: "Could not reach the backend.",
    action: "Check Base URL, CORS, and that the backend is running.",
  },
  OFFLINE: {
    title: "You are offline",
    detail: "Your browser has no network connection.",
  },
  UNAUTHORIZED: {
    title: "Not authenticated",
    detail: "The backend rejected the API key.",
    action: "Fill a valid API Key in Settings → Connection, or enable dev-mode on the backend.",
  },
  FORBIDDEN: {
    title: "Forbidden",
    detail: "You do not have permission for this action.",
    action: "Check the API Key's scope / role.",
  },
  NOT_FOUND: {
    title: "Not found",
    detail: "The resource does not exist or has been removed.",
  },
  VALIDATION: {
    title: "Invalid request",
    detail: "The request was rejected by the backend.",
    action: "Check the input fields and required parameters.",
  },
  RATE_LIMIT: {
    title: "Rate limited",
    detail: "Too many requests in a short period.",
    action: "Wait a moment and retry.",
  },
  CONFLICT: {
    title: "Conflict",
    detail: "The resource already exists or is in use.",
  },
  SERVER: {
    title: "Server error",
    detail: "The backend encountered an internal error.",
    action: "Retry later, or check backend logs.",
  },
  PARSER: {
    title: "Bad response",
    detail: "The backend returned a non-JSON / malformed response.",
  },
  UNKNOWN: {
    title: "Unexpected error",
    detail: "Something went wrong.",
  },
};

const ZH: Record<ErrorCode, ErrorText> = {
  ABORTED: { title: "已停止", detail: "请求被用户中止。" },
  TIMEOUT: {
    title: "请求超时",
    detail: "后端未在规定时间内响应。",
    action: "检查网络或在「设置 → 连接」中调大超时。",
  },
  NETWORK: {
    title: "网络错误",
    detail: "无法连接到后端。",
    action: "检查 Base URL、CORS 配置，以及后端是否在运行。",
  },
  OFFLINE: {
    title: "网络已断开",
    detail: "浏览器当前没有网络连接。",
  },
  UNAUTHORIZED: {
    title: "鉴权失败",
    detail: "后端拒绝了 API Key。",
    action: "在「设置 → 连接」填入有效的 API Key，或在后端启用 dev-mode。",
  },
  FORBIDDEN: {
    title: "权限不足",
    detail: "当前账号无权访问该资源。",
    action: "检查 API Key 的 scope / 角色。",
  },
  NOT_FOUND: {
    title: "资源不存在",
    detail: "目标资源不存在或已被删除。",
  },
  VALIDATION: {
    title: "请求参数无效",
    detail: "请求被后端校验拒绝。",
    action: "检查输入字段与必填参数。",
  },
  RATE_LIMIT: {
    title: "请求过于频繁",
    detail: "短时间内触发了限流。",
    action: "稍候再试。",
  },
  CONFLICT: {
    title: "资源冲突",
    detail: "资源已存在或正在被使用。",
  },
  SERVER: {
    title: "服务器错误",
    detail: "后端发生内部错误。",
    action: "稍后重试，或查看后端日志。",
  },
  PARSER: {
    title: "响应格式错误",
    detail: "后端返回了无法解析的内容。",
  },
  UNKNOWN: { title: "未知错误", detail: "发生了意外错误。" },
};

const CATALOGS = { en: EN, zh: ZH } as const;

function textOf(code: ErrorCode): ErrorText {
  return CATALOGS[getLocale()][code];
}

/* ───────── 错误归类 ───────── */

export interface ClassifiedError {
  code: ErrorCode;
  message: string; // 后端返回的原文（i18n 之外的具体信息）
  status: number; // 0 = 非 HTTP
  cause?: unknown;
  action?: string; // 后端 detail 里有 action hint 时覆盖
}

/**
 * 把任意 thrown value 归类成 ClassifiedError。
 * - APIError 直接读 status / code
 * - DOMException AbortError → ABORTED
 * - TypeError("Failed to fetch"/"NetworkError"/"Load failed") → NETWORK
 * - navigator.onLine === false → OFFLINE
 * - TimeoutError → TIMEOUT
 * - 其它 → UNKNOWN（但保留 message）
 */
export function classify(err: unknown): ClassifiedError {
  // 1) 我们自己抛的 APIError
  if (err instanceof APIError) {
    return {
      code: statusToCode(err.status, err.message),
      message: err.message,
      status: err.status,
      cause: err.cause,
      action:
        typeof (err.detail as { action?: string } | undefined)?.action === "string"
          ? (err.detail as { action: string }).action
          : undefined,
    };
  }

  // 2) AbortError
  if (err instanceof DOMException && err.name === "AbortError") {
    return { code: "ABORTED", message: "请求已停止", status: 0, cause: err };
  }
  if (err instanceof Error && err.name === "AbortError") {
    return { code: "ABORTED", message: err.message, status: 0, cause: err };
  }

  // 3) 离线
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return { code: "OFFLINE", message: "网络断开", status: 0, cause: err };
  }

  // 4) Timeout
  if (err instanceof Error && /timeout/i.test(err.message)) {
    return { code: "TIMEOUT", message: err.message, status: 0, cause: err };
  }

  // 5) 网络错
  if (err instanceof TypeError) {
    const msg = err.message || "";
    if (
      /Failed to fetch/i.test(msg) ||
      /NetworkError/i.test(msg) ||
      /Load failed/i.test(msg) ||
      /fetch failed/i.test(msg) ||
      /Network request failed/i.test(msg)
    ) {
      return { code: "NETWORK", message: msg, status: 0, cause: err };
    }
  }

  // 6) 其它 Error
  if (err instanceof Error) {
    return { code: "UNKNOWN", message: err.message, status: 0, cause: err };
  }

  // 7) 兜底
  return { code: "UNKNOWN", message: String(err), status: 0, cause: err };
}

function statusToCode(status: number, message: string): ErrorCode {
  if (status === 0) return /timeout/i.test(message) ? "TIMEOUT" : "NETWORK";
  if (status === 401) return "UNAUTHORIZED";
  if (status === 403) return "FORBIDDEN";
  if (status === 404) return "NOT_FOUND";
  if (status === 409) return "CONFLICT";
  if (status === 429) return "RATE_LIMIT";
  if (status >= 400 && status < 500) return "VALIDATION";
  if (status >= 500) return "SERVER";
  return "UNKNOWN";
}

/* ───────── 报告（toast） ───────── */

const DEDUPE_WINDOW_MS = 4000; // 同一条错误 4s 内只报一次
const recentlyShown = new Map<string, number>(); // key -> timestamp

interface ReportOptions {
  /** 不弹 toast，只 console.warn；用于"已经在 UI 标红"的场景 */
  silent?: boolean;
  /** 覆盖默认 toast 类型 */
  level?: "error" | "warning" | "info";
  /** 强制不带"修复建议"那一行 */
  hideAction?: boolean;
}

function hashKey(code: ErrorCode, message: string, context?: string): string {
  const raw = `${code}|${context || ""}|${message}`;
  // 轻量 hash：避免再引 crypto
  let h = 5381;
  for (let i = 0; i < raw.length; i++) h = ((h << 5) + h) ^ raw.charCodeAt(i);
  return `err-${(h >>> 0).toString(36)}`;
}

/**
 * 统一错误报告：归类 + i18n + 去重 + toast。
 *
 * @param err  任意 thrown value
 * @param context  发生位置（用户能看懂的场景词，如 "加载智能体"）
 * @param opts  silent / level / hideAction
 */
export function reportError(
  err: unknown,
  context?: string,
  opts: ReportOptions = {},
): ClassifiedError {
  const cls = classify(err);
  const t = textOf(cls.code);

  // 静默：只 console 留痕
  if (opts.silent) {
    // eslint-disable-next-line no-console
    console.warn(`[error]${context ? " " + context : ""}:`, cls.code, cls.message, cls.cause);
    return cls;
  }

  // 去重：4s 内同 code + context + message 不重复
  const key = hashKey(cls.code, cls.message, context);
  const now = Date.now();
  const last = recentlyShown.get(key);
  if (last && now - last < DEDUPE_WINDOW_MS) {
    return cls;
  }
  recentlyShown.set(key, now);
  // 清理过期条目
  if (recentlyShown.size > 200) {
    for (const [k, ts] of recentlyShown) {
      if (now - ts > DEDUPE_WINDOW_MS * 2) recentlyShown.delete(k);
    }
  }

  const level = opts.level || (cls.code === "ABORTED" ? "info" : "error");
  const action = opts.hideAction ? undefined : cls.action || t.action;
  const description = [
    context ? `${context}：${cls.message}` : cls.message,
    action ? `\n💡 ${action}` : "",
  ]
    .filter(Boolean)
    .join("");

  const title = t.title;
  // stable id 让 sonner 在去重时合并同一 id 的 toast
  if (level === "info") toast.info(title, { id: key, description });
  else if (level === "warning") toast.warning(title, { id: key, description });
  else toast.error(title, { id: key, description });

  // 同时 console 留完整 cause（开发者排查用）
  if (cls.cause) {
    // eslint-disable-next-line no-console
    console.warn(`[${cls.code}] ${context || "error"}:`, cls.cause);
  }

  return cls;
}

/** 主动清空去重缓存（用于"已修复"后想立刻重报同一条） */
export function clearErrorDedup(): void {
  recentlyShown.clear();
}

/* ───────── 便捷封装 ───────── */

/** 给 React Query 的 onError 用 */
export function reportQueryError(err: unknown, context: string, opts?: { silent?: boolean }): void {
  reportError(err, context, opts);
}

/**
 * 给 useEffect / useQuery 包装一层：
 * - 只在错误对象引用变化时 toast
 * - 卸载时自动跳过
 */
export function useErrorOnce(err: unknown, context: string): void {
  const lastRef = React.useRef<unknown>(undefined);
  React.useEffect(() => {
    if (!err) return;
    if (lastRef.current === err) return;
    lastRef.current = err;
    reportError(err, context);
  }, [err, context]);
}
