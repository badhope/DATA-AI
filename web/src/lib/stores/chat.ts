import type { ChatMessage, ToolCall } from "@/lib/types/api";
/**
 * 聊天 Store - 会话管理、消息流
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface ChatSession {
  id: string;
  title: string;
  model: string;
  systemPrompt: string;
  temperature: number;
  maxTokens?: number;
  topP: number;
  enableTools: boolean;
  toolNames: string[];
  /** 单轮发送中，工具调用 → 工具结果 → 再次 LLM 的最大循环轮数（防无限循环） */
  maxIterations: number;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

interface ChatState {
  sessions: Record<string, ChatSession>;
  sessionOrder: string[];
  currentSessionId: string | null;
  streaming: boolean;
  abortController: AbortController | null;

  createSession: (model: string) => string;
  removeSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;
  setCurrent: (id: string | null) => void;
  updateSession: (id: string, partial: Partial<ChatSession>) => void;
  appendMessage: (sessionId: string, msg: ChatMessage) => void;
  updateLastMessage: (sessionId: string, updater: (m: ChatMessage) => ChatMessage) => void;
  appendToken: (sessionId: string, token: string) => void;
  appendToolCall: (sessionId: string, toolCall: ToolCall) => void;
  clearMessages: (sessionId: string) => void;
  setStreaming: (b: boolean, controller?: AbortController | null) => void;
  abort: () => void;
}

function newId(): string {
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export const useChat = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: {},
      sessionOrder: [],
      currentSessionId: null,
      streaming: false,
      abortController: null,

      createSession: (model) => {
        const id = newId();
        const session: ChatSession = {
          id,
          title: "新对话",
          model,
          systemPrompt: "",
          temperature: 0.7,
          topP: 1,
          enableTools: true,
          toolNames: [],
          maxIterations: 5,
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        set((s) => ({
          sessions: { ...s.sessions, [id]: session },
          sessionOrder: [id, ...s.sessionOrder],
          currentSessionId: id,
        }));
        return id;
      },

      removeSession: (id) =>
        set((s) => {
          const { [id]: _, ...rest } = s.sessions;
          return {
            sessions: rest,
            sessionOrder: s.sessionOrder.filter((x) => x !== id),
            currentSessionId: s.currentSessionId === id ? null : s.currentSessionId,
          };
        }),

      renameSession: (id, title) =>
        set((s) => {
          const session = s.sessions[id];
          if (!session) return s;
          return {
            sessions: {
              ...s.sessions,
              [id]: { ...session, title, updatedAt: Date.now() },
            },
          };
        }),

      setCurrent: (id) => set({ currentSessionId: id }),

      updateSession: (id, partial) =>
        set((s) => {
          const session = s.sessions[id];
          if (!session) return s;
          return {
            sessions: {
              ...s.sessions,
              [id]: { ...session, ...partial, updatedAt: Date.now() },
            },
          };
        }),

      appendMessage: (sessionId, msg) =>
        set((s) => {
          const session = s.sessions[sessionId];
          if (!session) return s;
          // 自动从首条 user 消息生成标题
          let title = session.title;
          if (title === "新对话" && msg.role === "user" && msg.content) {
            title = msg.content.slice(0, 30) + (msg.content.length > 30 ? "..." : "");
          }
          return {
            sessions: {
              ...s.sessions,
              [sessionId]: {
                ...session,
                title,
                messages: [...session.messages, msg],
                updatedAt: Date.now(),
              },
            },
          };
        }),

      updateLastMessage: (sessionId, updater) =>
        set((s) => {
          const session = s.sessions[sessionId];
          if (!session || session.messages.length === 0) return s;
          const messages = [...session.messages];
          messages[messages.length - 1] = updater(messages[messages.length - 1]);
          return {
            sessions: {
              ...s.sessions,
              [sessionId]: { ...session, messages, updatedAt: Date.now() },
            },
          };
        }),

      appendToken: (sessionId, token) =>
        set((s) => {
          const session = s.sessions[sessionId];
          if (!session || session.messages.length === 0) return s;
          const messages = [...session.messages];
          const last = { ...messages[messages.length - 1] };
          last.content = (last.content || "") + token;
          messages[messages.length - 1] = last;
          return {
            sessions: {
              ...s.sessions,
              [sessionId]: { ...session, messages, updatedAt: Date.now() },
            },
          };
        }),

      appendToolCall: (sessionId, toolCall) =>
        set((s) => {
          const session = s.sessions[sessionId];
          if (!session || session.messages.length === 0) return s;
          const messages = [...session.messages];
          const last = { ...messages[messages.length - 1] };
          last.tool_calls = [...(last.tool_calls ?? []), toolCall];
          messages[messages.length - 1] = last;
          return {
            sessions: {
              ...s.sessions,
              [sessionId]: { ...session, messages, updatedAt: Date.now() },
            },
          };
        }),

      clearMessages: (sessionId) =>
        set((s) => {
          const session = s.sessions[sessionId];
          if (!session) return s;
          return {
            sessions: {
              ...s.sessions,
              [sessionId]: { ...session, messages: [], updatedAt: Date.now() },
            },
          };
        }),

      setStreaming: (b, controller) => set({ streaming: b, abortController: controller ?? null }),

      abort: () => {
        const c = get().abortController;
        if (c) c.abort();
        set({ streaming: false, abortController: null });
      },
    }),
    {
      name: "data-ai-chat",
      version: 2,
      migrate: (persistedState: unknown, fromVersion: number) => {
        const s = (persistedState || {}) as { sessions?: Record<string, ChatSession> };
        if (fromVersion < 2) {
          // v1 → v2: 旧 session 缺 maxIterations 字段
          const sessions = s.sessions || {};
          for (const id in sessions) {
            const sess = sessions[id];
            if (sess && (sess as { maxIterations?: number }).maxIterations === undefined) {
              (sess as { maxIterations: number }).maxIterations = 5;
            }
          }
          return persistedState;
        }
        return persistedState;
      },
      partialize: (s) => ({
        sessions: s.sessions,
        sessionOrder: s.sessionOrder,
        currentSessionId: s.currentSessionId,
      }),
    },
  ),
);
