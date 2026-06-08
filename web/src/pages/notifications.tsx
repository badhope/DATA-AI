import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, CheckCheck, Loader2 } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api/client";
import { cn } from "@/lib/utils";

const LEVEL_STYLES: Record<string, string> = {
  info: "border-info/40 bg-info/10 text-info",
  success: "border-success/40 bg-success/10 text-success",
  warning: "border-warning/40 bg-warning/10 text-warning",
  error: "border-destructive/40 bg-destructive/10 text-destructive",
};

const LEVEL_LABELS: Record<string, string> = {
  info: "信息",
  success: "成功",
  warning: "警告",
  error: "错误",
};

export function NotificationsPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "unread">("all");

  const { data, isLoading } = useQuery({
    queryKey: ["notifications", filter],
    queryFn: () => api.listNotifications(filter === "unread"),
    refetchInterval: 10_000,
  });

  const markAll = useMutation({
    mutationFn: () => api.markNotificationsRead("all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const markOne = useMutation({
    mutationFn: (id: string) => api.markNotificationsRead([id]),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const list = data?.data ?? [];
  const unread = data?.unread_count ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="通知中心"
        description="系统事件、任务进度与异常告警的统一视图"
        icon={<Bell className="h-5 w-5" />}
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant={filter === "all" ? "default" : "outline"}
              onClick={() => setFilter("all")}
            >
              全部
            </Button>
            <Button
              size="sm"
              variant={filter === "unread" ? "default" : "outline"}
              onClick={() => setFilter("unread")}
            >
              未读 {unread > 0 ? `(${unread})` : ""}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => markAll.mutate()}
              disabled={markAll.isPending || unread === 0}
            >
              {markAll.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <CheckCheck className="h-4 w-4" />
              )}
              全部已读
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">实时通知 · {list.length} 条</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center gap-2 py-8 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> 加载中…
            </div>
          ) : list.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground">暂无通知</div>
          ) : (
            <ul className="divide-y divide-border">
              {list.map((n) => (
                <li
                  key={n.id}
                  className={cn("flex items-start gap-3 py-3", !n.read && "bg-muted/30")}
                >
                  <span
                    className={cn(
                      "mt-1 inline-flex shrink-0 items-center rounded-md border px-2 py-0.5 text-xs",
                      LEVEL_STYLES[n.level] ?? LEVEL_STYLES.info,
                    )}
                  >
                    {LEVEL_LABELS[n.level] ?? n.level}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{n.title}</span>
                      {!n.read && <span className="h-2 w-2 rounded-full bg-sky-400" />}
                    </div>
                    {n.description && (
                      <p className="mt-1 text-sm text-muted-foreground">{n.description}</p>
                    )}
                    <div className="mt-1 text-xs text-muted-foreground">
                      {new Date(n.ts * 1000).toLocaleString("zh-CN")}
                      {n.category && ` · ${n.category}`}
                    </div>
                  </div>
                  {!n.read && (
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => markOne.mutate(n.id)}
                      title="标记为已读"
                    >
                      <Check className="h-4 w-4" />
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
