"use client";

import { MessageBubble } from "@/components/chat/message-bubble";
import { Button } from "@/components/ui/button";
import { copyToClipboard } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { Check, Copy, Play } from "lucide-react";
import * as React from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";

export { MessageBubble };

interface MarkdownProps {
  content: string;
  className?: string;
}

interface CodeBlockProps {
  language: string;
  value: string;
}

function CodeBlock({ language, value }: CodeBlockProps) {
  const [copied, setCopied] = React.useState(false);
  const handleCopy = async () => {
    await copyToClipboard(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const handleRun = () => {
    // Persist to localStorage so Sandbox page can pick up
    try {
      localStorage.setItem(
        "data-ai-pending-code",
        JSON.stringify({ language, code: value, ts: Date.now() }),
      );
      window.dispatchEvent(
        new CustomEvent("data-ai:run-code", { detail: { language, code: value } }),
      );
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="group relative my-3 overflow-hidden border border-border bg-[#1e1e1e]">
      <div className="flex items-center justify-between border-b border-white/10 bg-[#2a2a2a] px-3 py-1.5 text-xs text-zinc-400">
        <span className="font-mono">{language || "text"}</span>
        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          <Button
            variant="ghost"
            size="xs"
            onClick={handleRun}
            className="h-6 px-2 text-zinc-400 hover:bg-white/10 hover:text-white"
          >
            <Play className="h-3 w-3" /> 运行到沙箱
          </Button>
          <Button
            variant="ghost"
            size="xs"
            onClick={handleCopy}
            className="h-6 px-2 text-zinc-400 hover:bg-white/10 hover:text-white"
          >
            {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? "已复制" : "复制"}
          </Button>
        </div>
      </div>
      <SyntaxHighlighter
        language={language}
        style={vscDarkPlus}
        customStyle={{
          margin: 0,
          padding: "0.75rem 1rem",
          background: "transparent",
          fontSize: "0.8125rem",
          lineHeight: "1.5",
        }}
        wrapLongLines={false}
        PreTag="div"
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}

export function Markdown({ content, className }: MarkdownProps) {
  return (
    <div className={cn("prose prose-invert max-w-none text-sm leading-relaxed", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p({ children }) {
            return <p className="my-2 leading-relaxed">{children}</p>;
          },
          h1({ children }) {
            return <h1 className="mb-2 mt-4 font-display text-2xl font-bold">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="mb-2 mt-3 font-display text-xl font-bold">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="mb-1.5 mt-3 font-display text-lg font-semibold">{children}</h3>;
          },
          ul({ children }) {
            return <ul className="my-2 list-disc space-y-1 pl-6">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="my-2 list-decimal space-y-1 pl-6">{children}</ol>;
          },
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>;
          },
          a({ children, href }) {
            return (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                className="text-primary underline-offset-4 hover:underline"
              >
                {children}
              </a>
            );
          },
          blockquote({ children }) {
            return (
              <blockquote className="my-2 border-l-2 border-primary/50 bg-primary/5 px-3 py-1 italic text-muted-foreground">
                {children}
              </blockquote>
            );
          },
          table({ children }) {
            return (
              <div className="my-3 overflow-x-auto rounded-md border border-border">
                <table className="w-full text-sm">{children}</table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="border-b border-border bg-muted/50 px-3 py-2 text-left font-semibold">
                {children}
              </th>
            );
          },
          td({ children }) {
            return <td className="border-b border-border/50 px-3 py-2">{children}</td>;
          },
          code({ className: cn_, children, ...props }) {
            const match = /language-(\w+)/.exec(cn_ ?? "");
            const value = String(children).replace(/\n$/, "");
            const isBlock = match && value.includes("\n");
            if (isBlock) {
              return <CodeBlock language={match?.[1] ?? ""} value={value} />;
            }
            return (
              <code
                className="rounded bg-muted px-1.5 py-0.5 font-mono text-[0.85em] text-foreground"
                {...props}
              >
                {children}
              </code>
            );
          },
          pre({ children }) {
            return <>{children}</>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
