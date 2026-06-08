"use client";

import { Markdown } from "@/components/chat/markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ChatMessage, ToolCall } from "@/lib/types/api";
import { cn, formatDuration, safeJSON } from "@/lib/utils";
import { motion } from "framer-motion";
import { AlertCircle, Check, ChevronRight, Loader2, Wrench } from "lucide-react";
import * as React from "react";

interface MessageBubbleProps {
  message: ChatMessage;
  streaming?: boolean;
  toolResults?: Record<string, { result: unknown; error?: string; durationMs: number }>;
}

export function MessageBubble({ message, streaming, toolResults }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const isTool = message.role === "tool";

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn("flex w-full gap-3", isUser ? "flex-row-reverse" : "flex-row")}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
          isUser
            ? "bg-primary text-primary-foreground"
            : isTool
              ? "bg-warning/20 text-warning"
              : "border border-primary/30 bg-primary/10 text-primary",
        )}
      >
        {isUser ? "U" : isTool ? <Wrench className="h-4 w-4" /> : "AI"}
      </div>

      <div
        className={cn(
          "flex min-w-0 max-w-[85%] flex-col gap-2",
          isUser ? "items-end" : "items-start",
        )}
      >
        {/* Tool calls */}
        {isAssistant && message.tool_calls && message.tool_calls.length > 0 && (
          <div className="w-full space-y-2">
            {message.tool_calls.map((tc) => (
              <ToolCallCard key={tc.id} toolCall={tc} result={toolResults?.[tc.id]} />
            ))}
          </div>
        )}

        {/* Content */}
        {message.content && (
          <div
            className={cn(
              "px-4 py-2.5 text-sm",
              isUser
                ? "rounded-sm bg-primary text-primary-foreground"
                : isTool
                  ? "rounded-sm border border-warning/30 bg-warning/5 text-warning"
                  : "rounded-sm border border-border bg-card",
            )}
          >
            {isAssistant ? (
              <Markdown content={message.content} />
            ) : (
              <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
            )}
            {streaming && isAssistant && (
              <span className="ml-1 inline-block h-3 w-1.5 translate-y-0.5 animate-pulse bg-primary" />
            )}
          </div>
        )}

        {isTool && message.tool_call_id && (
          <div className="text-[10px] text-muted-foreground">
            tool_call_id: {message.tool_call_id}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function ToolCallCard({
  toolCall,
  result,
}: {
  toolCall: ToolCall;
  result?: { result: unknown; error?: string; durationMs: number };
}) {
  const [open, setOpen] = React.useState(false);
  const args = safeJSON<Record<string, unknown>>(toolCall.function.arguments, {});

  return (
    <div className="overflow-hidden rounded-lg border border-info/30 bg-info/5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition-colors hover:bg-info/10"
      >
        <ChevronRight
          className={cn("h-3 w-3 text-info transition-transform", open && "rotate-90")}
        />
        <Wrench className="h-3 w-3 text-info" />
        <span className="font-mono font-semibold text-info">{toolCall.function.name}</span>
        {result === undefined ? (
          <Badge variant="info" className="ml-1">
            <Loader2 className="mr-1 h-2.5 w-2.5 animate-spin" /> 执行中
          </Badge>
        ) : result.error ? (
          <Badge variant="error" className="ml-1">
            <AlertCircle className="mr-1 h-2.5 w-2.5" /> 错误
          </Badge>
        ) : (
          <Badge variant="success" className="ml-1">
            <Check className="mr-1 h-2.5 w-2.5" /> 完成
          </Badge>
        )}
        {result && (
          <span className="ml-auto font-mono text-[10px] text-muted-foreground">
            {formatDuration(result.durationMs)}
          </span>
        )}
      </button>
      {open && (
        <div className="space-y-2 border-t border-info/20 px-3 py-2 text-xs">
          <div>
            <p className="mb-1 font-semibold text-info">参数</p>
            <pre className="overflow-x-auto bg-black/30 p-2 font-mono text-[11px] text-foreground">
              {JSON.stringify(args, null, 2)}
            </pre>
          </div>
          {result && (
            <div>
              <p className="mb-1 font-semibold text-info">
                {result.error ? "错误信息" : "结果"}
              </p>
              <pre className="overflow-x-auto bg-black/30 p-2 font-mono text-[11px] text-foreground">
                {result.error ?? JSON.stringify(result.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
