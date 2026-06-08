"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import {
  ArrowRight,
  FileSpreadsheet,
  FileText,
  FileType,
  Presentation,
  Sparkles,
} from "lucide-react";
import type * as React from "react";
import { useNavigate } from "react-router-dom";

interface OfficeLayoutProps {
  active: "word" | "ppt" | "excel" | "pdf";
  children: React.ReactNode;
}

const NAV = [
  {
    v: "word",
    label: "Word",
    href: "/office/word",
    icon: FileText,
    color: "bg-muted",
    textColor: "text-info",
  },
  {
    v: "ppt",
    label: "PPT",
    href: "/office/ppt",
    icon: Presentation,
    color: "bg-muted",
    textColor: "text-warning",
  },
  {
    v: "excel",
    label: "Excel",
    href: "/office/excel",
    icon: FileSpreadsheet,
    color: "bg-muted",
    textColor: "text-success",
  },
  {
    v: "pdf",
    label: "PDF",
    href: "/office/pdf",
    icon: FileType,
    color: "bg-muted",
    textColor: "text-destructive",
  },
] as const;

export function OfficeLayout({ active, children }: OfficeLayoutProps) {
  const navigate = useNavigate();
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {NAV.map((n) => {
          const Icon = n.icon;
          const isActive = n.v === active;
          return (
            <button
              key={n.v}
              onClick={() => navigate(n.href)}
              className={cn(
                "group flex items-center gap-3 border p-3 text-left transition-colors",
                isActive
                  ? "border-primary bg-primary/10"
                  : "border-border hover:border-primary/40",
              )}
            >
              <div
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-md ring-1 ring-border",
                  n.color,
                  n.textColor,
                )}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <p className="font-display font-semibold">{n.label}</p>
                <p className="text-xs text-muted-foreground">
                  {n.v === "word" && "文档读写编辑模板"}
                  {n.v === "ppt" && "演示文稿"}
                  {n.v === "excel" && "表格与图表"}
                  {n.v === "pdf" && "读取合并拆分"}
                </p>
              </div>
              {isActive && (
                <Badge variant="accent" className="ml-auto">
                  当前
                </Badge>
              )}
            </button>
          );
        })}
      </div>
      {children}
    </div>
  );
}
