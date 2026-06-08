"use client";

import type { ReactNode } from "react";

/**
 * 背景层 — 印刷质感:
 * 1. 基础: 暖墨色 + 极淡纸纹
 * 2. 32px 网格: 工程笔记纸感
 * 3. 角落 1px 边角规: 编辑的"出血位"
 * 4. 不再使用 aurora / 渐变斑
 */
interface BackgroundFXProps {
  children: ReactNode;
}

export function BackgroundFX({ children }: BackgroundFXProps) {
  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* 基础色 (由 body 设置) */}
      <div className="pointer-events-none fixed inset-0 -z-30 bg-background" />

      {/* 32px 网格 — 极淡 */}
      <div className="pointer-events-none fixed inset-0 -z-20 grid-bg opacity-30" />

      {/* 印刷出血规 — 4 角 1px 标线 */}
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute left-3 top-3 h-4 w-4 border-l border-t border-foreground/30" />
        <div className="absolute right-3 top-3 h-4 w-4 border-r border-t border-foreground/30" />
        <div className="absolute bottom-3 left-3 h-4 w-4 border-b border-l border-foreground/30" />
        <div className="absolute bottom-3 right-3 h-4 w-4 border-b border-r border-foreground/30" />
      </div>

      {children}
    </div>
  );
}
