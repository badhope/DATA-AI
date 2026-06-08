"use client";

import { MessageBubble } from "@/components/chat/message-bubble";
import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { APIError, getClient } from "@/lib/api/client";
import { reportError, useErrorOnce } from "@/lib/errors";
import { useChat } from "@/lib/stores/chat";
import type { ChatMessage, ToolCall, ToolExecuteResponse } from "@/lib/types/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import {
  Bot,
  Check,
  MessageSquarePlus,
  Paperclip,
  Pencil,
  Plus,
  Send,
  Settings2,
  Square,
  Trash2,
  Wrench,
} from "lucide-react";
import * as React from "react";
import { useNavigate, useParams } from "react-router-dom";

/** 兜底默认模型（模型列表尚未加载时用） */
const FALLBACK_MODEL = "qwen3-32b";

/** 优先使用的模型列表(都必须是已验证可连的,空降级到首个后端模型) */
const PREFERRED_MODELS = [
  "qwen3-32b",
  "qwen3-30b-a3b",
  "qwen-max",
  "qwen3-8b",
  "qwen3-coder-flash",
  "qwen-long",
  "qwen-coder-turbo",
];

/** 选择第一个可用模型 id: 优先 PREFERRED_MODELS,后端列表都找不到再退到首个后端模型 */
function pickFirstModel(list: { id: string }[] | undefined): string {
  const ids = new Set((list ?? []).map((m) => m.id));
  for (const m of PREFERRED_MODELS) {
    if (ids.has(m)) return m;
  }
  return list?.[0]?.id ?? FALLBACK_MODEL;
}

export function ChatPage() {
  const params = useParams<{ sessionId?: string }>();
  const navigate = useNavigate();
  const sessions = useChat((s) => s.sessions);
  const sessionOrder = useChat((s) => s.sessionOrder);
  const currentId = useChat((s) => s.currentSessionId);
  const streaming = useChat((s) => s.streaming);
  const createSession = useChat((s) => s.createSession);
  const removeSession = useChat((s) => s.removeSession);
  const setCurrent = useChat((s) => s.setCurrent);
  const updateSession = useChat((s) => s.updateSession);
  const appendMessage = useChat((s) => s.appendMessage);
  const updateLastMessage = useChat((s) => s.updateLastMessage);
  const appendToken = useChat((s) => s.appendToken);
  const setStreaming = useChat((s) => s.setStreaming);
  const abort = useChat((s) => s.abort);
  const renameSession = useChat((s) => s.renameSession);

  // Sync URL → store
  React.useEffect(() => {
    if (params.sessionId && sessions[params.sessionId]) {
      setCurrent(params.sessionId);
    }
  }, [params.sessionId, sessions, setCurrent]);

  const session = currentId ? sessions[currentId] : null;
  const messages = session?.messages ?? [];
  const messagesRef = React.useRef<HTMLDivElement>(null);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);

  // Fetch available models + tools
  const modelsQuery = useQuery({
    queryKey: ["models"],
    queryFn: () => getClient().listModels(),
  });
  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: () => getClient().listTools(),
  });

  const availableModels = React.useMemo(
    () => (modelsQuery.data?.data ?? []).map((m) => m.id),
    [modelsQuery.data],
  );

  // 错误：模型列表加载失败时只报一次（hook 内部去重）
  useErrorOnce(modelsQuery.error, "加载模型列表");

  // Auto-scroll
  React.useEffect(() => {
    messagesRef.current?.scrollTo({ top: messagesRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length, streaming]);

  const [toolResults, setToolResults] = React.useState<
    Record<string, { result: unknown; error?: string; durationMs: number }>
  >({});

  // 确认删除 dialog
  const [deleteTarget, setDeleteTarget] = React.useState<string | null>(null);
  // 重命名 dialog
  const [renameTarget, setRenameTarget] = React.useState<string | null>(null);
  const [renameValue, setRenameValue] = React.useState("");

  const ensureSession = (): string => {
    if (currentId && sessions[currentId]) return currentId;
    const id = createSession(pickFirstModel(modelsQuery.data?.data));
    navigate(`/chat/${id}`);
    return id;
  };

  const handleNew = () => {
    const id = createSession(pickFirstModel(modelsQuery.data?.data));
    navigate(`/chat/${id}`);
  };

  /** 把当前 session 的最新状态（messages/systemPrompt/model/...）序列化为 LLM 请求 */
  const buildPayloadFromStore = (sessionId: string, override?: { appendUser?: ChatMessage }) => {
    const cur = useChat.getState().sessions[sessionId];
    if (!cur) return null;
    // 过滤掉末尾的空 assistant 占位消息（UI 显示用,不应发给 LLM,否则 LLM 看到空 content 会回默认问候）
    const filtered = cur.messages.filter(
      (m, i) => !(i === cur.messages.length - 1 && m.role === "assistant" && !m.content && !m.tool_calls?.length),
    );
    const baseMessages: ChatMessage[] = [
      ...(cur.systemPrompt ? [{ role: "system" as const, content: cur.systemPrompt }] : []),
      ...filtered,
    ];
    if (override?.appendUser) baseMessages.push(override.appendUser);
    return {
      model: cur.model,
      messages: baseMessages,
      temperature: cur.temperature,
      top_p: cur.topP,
      max_tokens: cur.maxTokens,
      stream: true,
      enable_tools: cur.enableTools,
      tool_names: cur.enableTools && cur.toolNames.length > 0 ? cur.toolNames : undefined,
    };
  };

  /**
   * 单次流式请求（可能因为 tool calls 触发递归）。
   * 返回是否"被工具调用打断"（true 表示外层应当把工具执行完后再 stream 一次）。
   */
  async function streamOnce(opts: {
    sessionId: string;
    signal: AbortSignal;
  }): Promise<{ toolCalls: ToolCall[]; text: string; aborted: boolean; error?: string }> {
    const payload = buildPayloadFromStore(opts.sessionId);
    if (!payload) return { toolCalls: [], text: "", aborted: false };

    const pendingToolCalls: ToolCall[] = [];
    let text = "";
    let aborted = false;
    let error: string | undefined;

    try {
      for await (const chunk of getClient().chatCompletionStream(payload, {
        signal: opts.signal,
      })) {
        for (const choice of chunk.choices) {
          const delta = choice.delta;
          if (delta?.content) {
            text += delta.content;
            appendToken(opts.sessionId, delta.content);
          }
          if (delta?.tool_calls) {
            for (const tcDelta of delta.tool_calls) {
              const idx = tcDelta.index ?? 0;
              if (!pendingToolCalls[idx]) {
                pendingToolCalls[idx] = {
                  id: tcDelta.id ?? `tc-${Date.now()}-${idx}`,
                  type: "function",
                  function: { name: "", arguments: "" },
                };
              }
              if (tcDelta.function?.name)
                pendingToolCalls[idx].function.name = tcDelta.function.name;
              if (tcDelta.function?.arguments) {
                pendingToolCalls[idx].function.arguments += tcDelta.function.arguments;
              }
            }
            updateLastMessage(opts.sessionId, (m) => ({
              ...m,
              tool_calls: [...pendingToolCalls],
            }));
          }
        }
      }
    } catch (e) {
      if (e instanceof APIError && (e.code === "ABORTED" || e.message.includes("已停止"))) {
        aborted = true;
      } else if (e instanceof DOMException && e.name === "AbortError") {
        aborted = true;
      } else {
        error = (e as Error).message || String(e);
      }
    }
    return { toolCalls: pendingToolCalls, text, aborted, error };
  }

  /**
   * 执行工具调用并把 tool result 追加到消息流，返回是否执行了工具。
   * 没有工具或被中止时返回 false。
   */
  async function executeToolCalls(
    sessionId: string,
    toolCalls: ToolCall[],
    enableTools: boolean,
    signal: AbortSignal,
  ): Promise<boolean> {
    if (toolCalls.length === 0 || !enableTools) return false;
    if (signal.aborted) return false;

    const localResults: typeof toolResults = {};
    for (const tc of toolCalls) {
      if (!tc.function.name) continue;
      if (signal.aborted) break;
      const start = performance.now();
      try {
        const args = JSON.parse(tc.function.arguments || "{}");
        const res: ToolExecuteResponse = await getClient().executeTool({
          tool: tc.function.name,
          parameters: args,
        });
        const dur = performance.now() - start;
        localResults[tc.id] = {
          result: res.result,
          error: res.error,
          durationMs: res.execution_time_ms || dur,
        };
        appendMessage(sessionId, {
          role: "tool",
          tool_call_id: tc.id,
          name: tc.function.name,
          content: JSON.stringify(res.result ?? res.error ?? ""),
        });
      } catch (e) {
        const dur = performance.now() - start;
        localResults[tc.id] = {
          result: null,
          error: String((e as Error).message || e),
          durationMs: dur,
        };
        appendMessage(sessionId, {
          role: "tool",
          tool_call_id: tc.id,
          name: tc.function.name,
          content: `Error: ${(e as Error).message || String(e)}`,
        });
      }
    }
    if (Object.keys(localResults).length > 0) {
      setToolResults((prev) => ({ ...prev, ...localResults }));
      toast.success(`已执行 ${Object.keys(localResults).length} 个工具`);
    }
    return true;
  }

  const send = async (content: string) => {
    if (!content.trim() || streaming) return;

    // 模型列表未加载完时直接提示用户稍候
    if (!modelsQuery.data?.data?.length && modelsQuery.isLoading) {
      toast.warning("正在加载模型列表，请稍候…");
      return;
    }

    const sessionId = ensureSession();
    const userMsg: ChatMessage = { role: "user", content: content.trim() };

    // 1. 追加 user 消息 + assistant 占位
    appendMessage(sessionId, userMsg);
    appendMessage(sessionId, { role: "assistant", content: "" });

    // 2. 创建本地 abort controller
    const controller = new AbortController();
    setStreaming(true, controller);

    try {
      // 3. 第一次 stream（可能被工具调用中断）
      let result = await streamOnce({ sessionId, signal: controller.signal });

      // 4. 如果有工具调用：执行 → 再 stream 一次（最多 N 轮防无限循环）
      const maxRounds = useChat.getState().sessions[sessionId]?.maxIterations ?? 5;
      let rounds = 0;
      while (!result.aborted && result.toolCalls.length > 0 && rounds < maxRounds) {
        const sessionNow = useChat.getState().sessions[sessionId];
        if (!sessionNow?.enableTools) break;

        // 4a. 追加新一轮 assistant 占位（让 LLM 在 tool result 后继续 stream）
        appendMessage(sessionId, { role: "assistant", content: "" });

        const executed = await executeToolCalls(
          sessionId,
          result.toolCalls,
          sessionNow.enableTools,
          controller.signal,
        );
        if (!executed || controller.signal.aborted) break;

        // 4b. 第二轮 stream（如果 LLM 又要调用工具，循环继续）
        result = await streamOnce({ sessionId, signal: controller.signal });
        rounds++;
      }

      if (result.error) {
        // 已经在 streamOnce 内部 try/catch 吞掉，不会抛到这
        // 但 stream 后的 tool_exec 错误会到这
        reportError(new Error(result.error), "对话生成");
      } else if (result.aborted) {
        // 用户主动停止：info 级提示，不报错
        toast.info("已停止生成", { description: "已生成的内容已保留。" });
      }
    } catch (e) {
      // 区分用户主动停止 vs 真错误
      if (e instanceof APIError && e.code === "ABORTED") {
        // 不报，已在 result.aborted 处理
      } else {
        reportError(e, "对话生成");
      }
    } finally {
      // 兜底：如果 assistant 占位仍空（流式未产出任何 token），删掉它
      const cur = useChat.getState().sessions[sessionId];
      if (cur && cur.messages.length > 0) {
        const last = cur.messages[cur.messages.length - 1];
        if (last.role === "assistant" && !last.content && !last.tool_calls?.length) {
          useChat.setState((s) => {
            const c = s.sessions[sessionId];
            if (!c) return s;
            return {
              sessions: {
                ...s.sessions,
                [sessionId]: { ...c, messages: c.messages.slice(0, -1) },
              },
            };
          });
        }
      }
      setStreaming(false, null);
    }
  };

  return (
    <div className="grid h-[calc(100vh-3.5rem-1.5rem)] grid-cols-1 gap-0 md:grid-cols-[280px_1fr]">
      {/* Sessions sidebar */}
      <aside className="hidden border-r border-border bg-card/40 md:flex md:flex-col">
        <div className="flex items-center justify-between border-b border-border p-3">
          <h2 className="font-display text-sm font-semibold">会话</h2>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleNew}
            aria-label="新建会话"
            title="新建会话"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        <ScrollArea className="flex-1 p-2">
          {sessionOrder.length === 0 ? (
            <p className="px-2 py-6 text-center text-xs text-muted-foreground">暂无会话</p>
          ) : (
            <ul className="space-y-0.5">
              {sessionOrder.map((id) => {
                const s = sessions[id];
                if (!s) return null;
                return (
                  <li key={id} className="group relative">
                    <button
                      onClick={() => navigate(`/chat/${id}`)}
                      className={cn(
                        "flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-accent",
                        currentId === id && "bg-accent",
                      )}
                    >
                      <MessageSquarePlus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{s.title || "新对话"}</p>
                        <p className="truncate text-[10px] text-muted-foreground">
                          {s.messages.length} 条 · {formatRelativeTime(s.updatedAt)}
                        </p>
                      </div>
                    </button>
                    <div className="absolute right-1.5 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 group-hover:flex">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setRenameTarget(id);
                          setRenameValue(s.title || "");
                        }}
                        className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                        aria-label="重命名"
                        title="重命名"
                      >
                        <Pencil className="h-3 w-3" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget(id);
                        }}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        aria-label="删除"
                        title="删除"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </ScrollArea>
      </aside>

      {/* Chat area */}
      <div className="flex min-w-0 flex-col">
        <PageHeader
          title={session?.title || "新对话"}
          description={
            session ? `使用模型 ${session.model} · ${messages.length} 条消息` : "开始你的智能体对话"
          }
          icon={<Bot className="h-5 w-5" />}
          actions={
            <>
              <ModelSelector
                value={session?.model ?? pickFirstModel(modelsQuery.data?.data)}
                onChange={(v) => session && updateSession(session.id, { model: v })}
                models={availableModels}
              />
              <ChatSettings
                session={session}
                onUpdate={(p) => session && updateSession(session.id, p)}
                tools={toolsQuery.data?.data ?? []}
              />
            </>
          }
        />

        <ScrollArea ref={messagesRef} className="flex-1 px-3 sm:px-6">
          <div className="mx-auto max-w-3xl space-y-6 py-4">
            {messages.length === 0 ? (
              <EmptyState
                icon={<MessageSquarePlus className="h-6 w-6" />}
                title={session ? "开始对话" : "新建会话"}
                description="向智能体提问，启用工具调用，或粘贴代码块让 AI 帮你运行到沙箱。"
                action={
                  <Button onClick={() => inputRef.current?.focus()}>
                    <Send className="h-4 w-4" /> 输入消息
                  </Button>
                }
              />
            ) : (
              <AnimatePresence initial={false}>
                {messages.map((m, i) => (
                  <MessageBubble
                    key={`${session?.id ?? "x"}-${i}-${m.role}`}
                    message={m}
                    streaming={streaming && i === messages.length - 1 && m.role === "assistant"}
                    toolResults={toolResults}
                  />
                ))}
              </AnimatePresence>
            )}
          </div>
        </ScrollArea>

        <Composer onSend={send} streaming={streaming} onAbort={abort} inputRef={inputRef} />
      </div>

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>删除会话？</DialogTitle>
            <DialogDescription>
              会话 "{sessions[deleteTarget || ""]?.title || "新对话"}" 将被永久删除，操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (deleteTarget) removeSession(deleteTarget);
                setDeleteTarget(null);
              }}
            >
              <Trash2 className="h-4 w-4" /> 删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename dialog */}
      <Dialog
        open={!!renameTarget}
        onOpenChange={(o) => {
          if (!o) {
            setRenameTarget(null);
            setRenameValue("");
          }
        }}
      >
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>重命名会话</DialogTitle>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            placeholder="会话标题"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && renameTarget) {
                renameSession(renameTarget, renameValue.trim() || "新对话");
                setRenameTarget(null);
                setRenameValue("");
              }
            }}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameTarget(null)}>
              取消
            </Button>
            <Button
              onClick={() => {
                if (renameTarget) {
                  renameSession(renameTarget, renameValue.trim() || "新对话");
                  setRenameTarget(null);
                  setRenameValue("");
                }
              }}
            >
              <Check className="h-4 w-4" /> 保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function ModelSelector({
  value,
  onChange,
  models,
}: {
  value: string;
  onChange: (v: string) => void;
  models: string[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-9 w-[200px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {models.length === 0 ? (
          <SelectItem value={value}>{value}</SelectItem>
        ) : (
          models.map((m) => (
            <SelectItem key={m} value={m}>
              {m}
            </SelectItem>
          ))
        )}
      </SelectContent>
    </Select>
  );
}

function ChatSettings({
  session,
  onUpdate,
  tools,
}: {
  session: ReturnType<typeof useChat.getState>["sessions"][string] | null;
  onUpdate: (p: Partial<ReturnType<typeof useChat.getState>["sessions"][string]>) => void;
  tools: { name: string; category?: string }[];
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="icon" aria-label="参数设置" title="参数设置">
          <Settings2 className="h-4 w-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80">
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">对话参数</h4>
          <div className="space-y-1.5">
            <Label className="text-xs">系统提示词</Label>
            <Textarea
              rows={3}
              value={session?.systemPrompt ?? ""}
              onChange={(e) => onUpdate({ systemPrompt: e.target.value })}
              placeholder="你是一个专业的数据分析师..."
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">温度 ({(session?.temperature ?? 0.7).toFixed(2)})</Label>
              <input
                type="range"
                min={0}
                max={2}
                step={0.05}
                value={session?.temperature ?? 0.7}
                onChange={(e) => onUpdate({ temperature: Number(e.target.value) })}
                className="w-full accent-primary"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Top-p ({(session?.topP ?? 1).toFixed(2)})</Label>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={session?.topP ?? 1}
                onChange={(e) => onUpdate({ topP: Number(e.target.value) })}
                className="w-full accent-primary"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">最大 tokens</Label>
            <input
              type="number"
              className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={session?.maxTokens ?? ""}
              placeholder="不限制"
              onChange={(e) =>
                onUpdate({ maxTokens: e.target.value ? Number(e.target.value) : undefined })
              }
            />
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <Label className="flex items-center gap-1.5 text-xs">
                <Wrench className="h-3 w-3" /> 工具调用
              </Label>
              <Switch
                checked={session?.enableTools ?? false}
                onCheckedChange={(v) => onUpdate({ enableTools: v })}
              />
            </div>
            {session?.enableTools && (
              <div className="max-h-32 space-y-1 overflow-y-auto rounded-md border border-border p-2">
                {tools.length === 0 ? (
                  <p className="py-2 text-center text-[10px] text-muted-foreground">暂无可用工具</p>
                ) : (
                  tools.map((t) => {
                    const checked = session.toolNames?.includes(t.name) ?? false;
                    return (
                      <label
                        key={t.name}
                        className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-xs hover:bg-accent"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const next = e.target.checked
                              ? [...(session.toolNames ?? []), t.name]
                              : (session.toolNames ?? []).filter((x) => x !== t.name);
                            onUpdate({ toolNames: next });
                          }}
                          className="h-3 w-3 accent-primary"
                        />
                        <span className="font-mono">{t.name}</span>
                        {t.category && (
                          <Badge variant="outline" className="ml-auto text-[9px]">
                            {t.category}
                          </Badge>
                        )}
                      </label>
                    );
                  })
                )}
              </div>
            )}
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}

interface ComposerProps {
  onSend: (text: string) => void;
  streaming: boolean;
  onAbort: () => void;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}

function Composer({ onSend, streaming, onAbort, inputRef }: ComposerProps) {
  const [value, setValue] = React.useState("");

  const submit = () => {
    if (!value.trim() || streaming) return;
    onSend(value);
    setValue("");
  };

  // 自动撑高
  React.useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 240) + "px";
  }, [value, inputRef]);

  return (
    <div className="border-t border-border bg-background p-3 sm:p-4">
      <div className="mx-auto max-w-3xl">
        <div className="group relative border border-border bg-card transition-colors focus-within:border-primary/60">
          <Textarea
            ref={inputRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="向 AI 提问...  (⌘+Enter 发送)"
            rows={1}
            className="min-h-[44px] resize-none border-0 bg-transparent px-4 py-3 text-sm focus-visible:ring-0 focus-visible:ring-offset-0"
            style={{ maxHeight: 240 }}
          />
          <div className="flex items-center justify-between px-2 pb-2">
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label="附件"
                title="附件（暂未实现）"
              >
                <Paperclip className="h-3.5 w-3.5" />
              </Button>
              <Badge variant="outline" className="text-[10px]">
                {value.length} 字符
              </Badge>
            </div>
            <div className="flex items-center gap-1">
              {streaming ? (
                <Button variant="destructive" size="sm" onClick={onAbort} title="停止当前生成">
                  <Square className="h-3 w-3" /> 停止
                </Button>
              ) : (
                <Button variant="default" size="sm" onClick={submit} disabled={!value.trim()}>
                  <Send className="h-3 w-3" /> 发送
                </Button>
              )}
            </div>
          </div>
        </div>
        <p className="mt-2 text-center text-[10px] text-muted-foreground">
          AI 输出可能不准确，请核实重要信息 · ⌘/Ctrl+Enter 发送
        </p>
      </div>
    </div>
  );
}
