"use client";

import { cn } from "@/lib/utils";
import type * as React from "react";

/**
 * PageHeader — 编辑式报头:
 * - 顶部 eyebrow 标签 (chapter / section)
 * - 大标题: 衬线 display
 * - 1px rule bottom
 * - 描述: 副文小字
 * - 右上 actions (chips / numbers)
 */
interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  icon?: React.ReactNode;
  eyebrow?: string;
  number?: string;
  className?: string;
  rule?: "single" | "double" | "thick" | "none";
  /** @deprecated kept for backward compat, no-op */
  accent?: string;
}

export function PageHeader({
  title,
  description,
  actions,
  className,
  icon,
  eyebrow,
  number,
  rule = "single",
  accent: _accent,
}: PageHeaderProps) {
  const ruleClass = {
    single: "border-b border-border",
    double: "rule-double",
    thick: "rule-thick",
    none: "",
  }[rule];

  return (
    <div
      className={cn(
        "flex flex-col gap-4 pb-5 sm:flex-row sm:items-end sm:justify-between",
        ruleClass,
        className,
      )}
    >
      <div className="min-w-0 flex-1">
        {(eyebrow || number) && (
          <div className="mb-2 flex items-baseline gap-2">
            {number && (
              <span className="num text-[11px] font-medium text-muted-foreground/60">
                {number}
              </span>
            )}
            {eyebrow && (
              <span className="eyebrow">{eyebrow}</span>
            )}
          </div>
        )}
        <div className="flex items-baseline gap-3">
          {icon && (
            <span className="flex h-7 w-7 shrink-0 items-center justify-center border border-foreground bg-foreground text-background">
              {icon}
            </span>
          )}
          <h1 className="font-display text-[28px] font-semibold leading-[1.1] tracking-tight text-balance sm:text-[32px]">
            {title}
          </h1>
        </div>
        {description && (
          <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-muted-foreground text-pretty">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
