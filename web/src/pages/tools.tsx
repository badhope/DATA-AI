"use client";

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getClient } from "@/lib/api/client";
import type { ToolsResponse } from "@/lib/types/api";
import { cn, formatDuration } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  Boxes,
  Brain,
  ChevronRight,
  Code2,
  FileText,
  Filter,
  Globe,
  Layers,
  Search,
  Sparkles,
  Terminal,
  Wrench,
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router-dom";

const CATEGORY_META: Record<
  string,
  { label: string; color: string; icon: React.ComponentType<{ className?: string }> }
> = {
  system: { label: "系统", color: "bg-muted text-info", icon: Terminal },
  office: {
    label: "办公",
    color: "bg-muted text-success",
    icon: FileText,
  },
  browser: {
    label: "浏览器",
    color: "bg-muted text-warning",
    icon: Globe,
  },
  document: {
    label: "文档",
    color: "bg-muted text-destructive",
    icon: FileText,
  },
  planning: {
    label: "规划",
    color: "bg-muted text-primary",
    icon: Brain,
  },
  extended: {
    label: "扩展",
    color: "bg-muted text-primary",
    icon: Sparkles,
  },
  uncategorized: {
    label: "其他",
    color: "bg-muted text-muted-foreground",
    icon: Boxes,
  },
};

export function ToolsPage() {
  const [search, setSearch] = React.useState("");
  const [activeCategory, setActiveCategory] = React.useState<string | null>(null);
  const query = useQuery<ToolsResponse>({
    queryKey: ["tools"],
    queryFn: () => getClient().listTools(),
  });

  const tools = query.data?.data ?? [];
  const categories = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const t of tools) {
      const c = t.category ?? "uncategorized";
      map.set(c, (map.get(c) ?? 0) + 1);
    }
    return Array.from(map.entries());
  }, [tools]);

  const filtered = React.useMemo(() => {
    const lower = search.toLowerCase();
    return tools.filter((t) => {
      const matchSearch =
        !lower ||
        t.name.toLowerCase().includes(lower) ||
        t.description.toLowerCase().includes(lower);
      const matchCat = !activeCategory || (t.category ?? "uncategorized") === activeCategory;
      return matchSearch && matchCat;
    });
  }, [tools, search, activeCategory]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="工具广场"
        description={`${tools.length} 个内置工具，按类别浏览并试运行`}
        icon={<Wrench className="h-5 w-5" />}
        actions={
          <div className="relative w-72">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索工具..."
              className="pl-8"
            />
          </div>
        }
      />

      {/* Category tabs */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setActiveCategory(null)}
          className={cn(
            "rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
            activeCategory === null
              ? "border-primary bg-primary/10 text-foreground"
              : "border-border text-muted-foreground hover:border-primary/30",
          )}
        >
          <Filter className="mr-1.5 inline h-3 w-3" /> 全部 ({tools.length})
        </button>
        {categories.map(([cat, count]) => {
          const meta = CATEGORY_META[cat] ?? CATEGORY_META.uncategorized;
          const Icon = meta.icon;
          const active = activeCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={cn(
                "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors",
                active
                  ? "border-primary bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground hover:border-primary/30",
              )}
            >
              <Icon className="h-3 w-3" /> {meta.label} ({count})
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<Search className="h-6 w-6" />}
          title="未找到匹配的工具"
          description="尝试更换关键词或选择其他分类"
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((t, i) => (
            <motion.div
              key={t.name}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.02 }}
            >
              <Link to={`/tools/${encodeURIComponent(t.name)}`}>
                <Card className="group h-full transition-colors hover:border-primary/40">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between gap-2">
                      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs font-semibold text-foreground">
                        {t.name}
                      </code>
                      <Badge variant="outline" className="text-[10px]">
                        {CATEGORY_META[t.category ?? "uncategorized"]?.label ?? t.category}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="line-clamp-2 text-xs text-muted-foreground">{t.description}</p>
                    <div className="mt-3 flex items-center justify-between text-xs">
                      <span className="font-mono text-muted-foreground">
                        {Object.keys(t.parameters.properties ?? {}).length} 参数
                      </span>
                      <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform group-hover:translate-x-1" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
