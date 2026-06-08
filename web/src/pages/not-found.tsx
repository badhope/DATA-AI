"use client";

import { Button } from "@/components/ui/button";
import { ArrowLeft, Home } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-6 text-center">
      <div className="editorial-card px-3 py-1.5">
        <span className="eyebrow">§ 404 / ERR</span>
      </div>
      <h1 className="mt-6 font-display text-7xl font-semibold leading-none tracking-tight">404</h1>
      <div className="mt-3 h-px w-24 bg-foreground" />
      <p className="mt-6 font-display text-xl italic text-foreground">页面未找到</p>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-pretty text-muted-foreground">
        看起来你迷路了。让我把你带回到 DATA-AI 的主控制台。
      </p>
      <div className="mt-8 flex gap-2">
        <Button asChild>
          <Link to="/">
            <Home className="h-4 w-4" /> 返回首页
          </Link>
        </Button>
        <Button asChild variant="outline">
          <Link to="/chat">
            <ArrowLeft className="h-4 w-4" /> 去聊天
          </Link>
        </Button>
      </div>
    </div>
  );
}
