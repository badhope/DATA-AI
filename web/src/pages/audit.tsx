"use client";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "@/components/ui/toaster";
import { type AuditEntry, type AuditStats, api } from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { copyToClipboard, downloadFile, formatDuration, formatRelativeTime, truncate } from "@/lib/utils";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  Filter,
  FileText,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  XCircle,
} from "lucide-react";
import * as React from "react";

const STATUS_STYLES: Record<number, string> = {
  200: "border-success/40 bg-success/10 text-success",
  201: "border-success/40 bg-success/10 text-success",
  204: "border-success/40 bg-success/10 text-success",
  400: "border-warning/40 bg-warning/10 text-warning",
  401: "border-destructive/40 bg-destructive/10 text-destructive",
  403: "border-destructive/40 bg-destructive/10 text-destructive",
  404: "border-warning/40 bg-warning/10 text-warning",
  422: "border-warning/40 bg-warning/10 text-warning",
  429: "border-destructive/40 bg-destructive/10 text-destructive",
  500: "border-destructive/40 bg-destructive/10 text-destructive",
  502: "border-destructive/40 bg-destructive/10 text-destructive",
};

function statusClass(code: number): string {
  if (code >= 200 && code < 300) return STATUS_STYLES[200];
  if (code === 401 || code === 403 || code === 429) return STATUS_STYLES[code];
  if (code >= 400 && code < 500) return STATUS_STYLES[400];
  if (code >= 500) return STATUS_STYLES[500];
  return "border-border bg-muted/30 text-muted-foreground";
}

function methodColor(m: string): string {
  if (m === "GET") return "border-info/40 bg-info/10 text-info";
  if (m === "POST") return "border-success/40 bg-success/10 text-success";
  if (m === "PUT" || m === "PATCH") return "border-warning/40 bg-warning/10 text-warning";
  if (m === "DELETE") return "border-destructive/40 bg-destructive/10 text-destructive";
  return "border-border bg-muted/30 text-muted-foreground";
}

export function AuditPage() {
  const [entries, setEntries] = React.useState<AuditEntry[]>([]);
  const [total, setTotal] = React.useState(0);
  const [stats, setStats] = React.useState<AuditStats | null>(null);
  const [loading, setLoading] = React.useState(true);

  const [filterActor, setFilterActor] = React.useState("");
  const [filterAction, setFilterAction] = React.useState("");
  const [filterResource, setFilterResource] = React.useState("");
  const [filterStatus, setFilterStatus] = React.useState<string>("all");
  const [selected, setSelected] = React.useState<AuditEntry | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [list, st] = await Promise.all([
        api.listAudit({
          actor: filterActor || undefined,
          action: filterAction || undefined,
          resource_type: filterResource || undefined,
          limit: 200,
        }),
        api.auditStats(),
      ]);
      setEntries(list.items);
      setTotal(list.total);
      setStats(st);
    } catch (e) {
      reportError(e, "加载审计日志失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
    const t = setInterval(load, 15_000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterActor, filterAction, filterResource]);

  const filtered = React.useMemo(() => {
    if (filterStatus === "all") return entries;
    if (filterStatus === "2xx") return entries.filter((e) => e.status_code >= 200 && e.status_code < 300);
    if (filterStatus === "4xx") return entries.filter((e) => e.status_code >= 400 && e.status_code < 500);
    if (filterStatus === "5xx") return entries.filter((e) => e.status_code >= 500);
    return entries;
  }, [entries, filterStatus]);

  async function handleExport(fmt: "json" | "csv") {
    try {
      const res = await api.exportAudit(fmt);
      const ext = fmt === "csv" ? "csv" : "json";
      const mime = fmt === "csv" ? "text/csv" : "application/json";
      downloadFile(res.data, `audit-log-${Date.now()}.${ext}`, mime);
      toast.success("已导出", { description: `${res.count} 条记录 → audit-log.${ext}` });
    } catch (e) {
      reportError(e, "导出审计日志失败");
    }
  }

  async function handleClear() {
    if (!confirm("确认清空全部审计日志？此操作不可恢复。")) return;
    try {
      await api.clearAudit();
      toast.success("已清空审计日志");
      load();
    } catch (e) {
      reportError(e, "清空审计日志失败");
    }
  }

  const okCount = entries.filter((e) => e.status_code < 400).length;
  const errCount = entries.filter((e) => e.status_code >= 400).length;
  const avgMs = entries.length
    ? Math.round(entries.reduce((a, b) => a + b.duration_ms, 0) / entries.length)
    : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="审计日志"
        description="全量 API 调用记录 — 谁、什么时间、做了什么、结果如何。可导出可查询。"
        icon={<ShieldCheck className="h-5 w-5" />}
        number="§09"
        eyebrow="Enterprise / Compliance"
        actions={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={load} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新
            </Button>
            <Button size="sm" variant="outline" onClick={() => handleExport("json")}>
              <Download className="h-4 w-4" /> JSON
            </Button>
            <Button size="sm" variant="outline" onClick={() => handleExport("csv")}>
              <FileText className="h-4 w-4" /> CSV
            </Button>
            <Button size="sm" variant="destructive" onClick={handleClear}>
              <Trash2 className="h-4 w-4" /> 清空
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          icon={<Activity className="h-4 w-4" />}
          label="总记录"
          value={total.toLocaleString()}
          hint={`内存 ${entries.length} / 限 200`}
        />
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4 text-success" />}
          label="成功"
          value={okCount.toLocaleString()}
          hint="2xx/3xx"
        />
        <StatCard
          icon={<XCircle className="h-4 w-4 text-destructive" />}
          label="失败"
          value={errCount.toLocaleString()}
          hint="4xx/5xx"
        />
        <StatCard
          icon={<Clock className="h-4 w-4" />}
          label="平均延迟"
          value={formatDuration(avgMs)}
          hint="基于最近 200 条"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Filter className="h-4 w-4" /> 过滤
          </CardTitle>
          <CardDescription>按 调用方 / 动作 / 资源类型 / HTTP 状态 组合过滤</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
            <div>
              <Label className="text-xs">调用方 (actor)</Label>
              <Input
                value={filterActor}
                onChange={(e) => setFilterActor(e.target.value)}
                placeholder="api-key / user-id / system"
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs">动作 (action)</Label>
              <Input
                value={filterAction}
                onChange={(e) => setFilterAction(e.target.value)}
                placeholder="chat / agent.run / rag.search ..."
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs">资源 (resource_type)</Label>
              <Input
                value={filterResource}
                onChange={(e) => setFilterResource(e.target.value)}
                placeholder="agent / rag_document / sandbox ..."
                className="mt-1"
              />
            </div>
            <div>
              <Label className="text-xs">状态</Label>
              <Select value={filterStatus} onValueChange={setFilterStatus}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部</SelectItem>
                  <SelectItem value="2xx">2xx 成功</SelectItem>
                  <SelectItem value="4xx">4xx 客户端</SelectItem>
                  <SelectItem value="5xx">5xx 服务端</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">调用时间线 · {filtered.length} 条</CardTitle>
            <CardDescription>点击任意条目查看完整请求 / 响应</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center gap-2 py-12 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> 加载中…
              </div>
            ) : filtered.length === 0 ? (
              <div className="py-16 text-center text-muted-foreground">
                <Search className="mx-auto mb-3 h-8 w-8 opacity-40" />
                暂无审计记录。触发任意 API 调用后将自动出现。
              </div>
            ) : (
              <div className="max-h-[640px] overflow-y-auto">
                <ul className="divide-y divide-border">
                  {filtered.map((e) => (
                    <li
                      key={e.id}
                      className="flex cursor-pointer items-center gap-3 px-2 py-2.5 transition-colors hover:bg-muted/30"
                      onClick={() => setSelected(e)}
                    >
                      <Badge className={methodColor(e.method)} variant="outline">
                        {e.method}
                      </Badge>
                      <code className="num shrink-0 text-xs text-muted-foreground tabular-nums">
                        {e.status_code}
                      </code>
                      <span className="min-w-0 flex-1 truncate font-mono text-xs">
                        {e.path}
                      </span>
                      <span className="hidden shrink-0 truncate text-xs text-muted-foreground sm:inline">
                        {truncate(e.actor, 24)}
                      </span>
                      <span className="num shrink-0 text-xs text-muted-foreground tabular-nums">
                        {formatDuration(e.duration_ms)}
                      </span>
                      <span className="num shrink-0 text-xs text-muted-foreground tabular-nums">
                        {formatRelativeTime(e.timestamp)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">详情</CardTitle>
            <CardDescription>{selected ? selected.id : "选择一条记录查看详情"}</CardDescription>
          </CardHeader>
          <CardContent>
            {!selected ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                <AlertTriangle className="mx-auto mb-2 h-6 w-6 opacity-40" />
                暂未选中
              </div>
            ) : (
              <div className="space-y-3 text-xs">
                <Detail label="时间" value={new Date(selected.timestamp).toLocaleString("zh-CN")} />
                <Detail label="调用方" value={selected.actor} mono />
                <Detail label="类型" value={selected.actor_type} />
                <Detail label="动作" value={selected.action} mono />
                <Detail label="资源" value={`${selected.resource_type}#${selected.resource_id}`} mono />
                <Detail label="路径" value={selected.path} mono />
                <Detail label="状态" value={String(selected.status_code)} />
                <Detail label="延迟" value={formatDuration(selected.duration_ms)} />
                <Detail label="IP" value={selected.ip} mono />
                <Detail label="UA" value={truncate(selected.user_agent, 80)} mono />
                {selected.response_summary && (
                  <div>
                    <span className="text-muted-foreground">响应摘要</span>
                    <pre className="mt-1 max-h-32 overflow-auto rounded border border-border bg-muted/30 p-2 text-[11px]">
                      {selected.response_summary}
                    </pre>
                  </div>
                )}
                {selected.request_body && (
                  <div>
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-muted-foreground">请求体</span>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-5 px-2 text-[10px]"
                        onClick={() => copyToClipboard(JSON.stringify(selected.request_body, null, 2))}
                      >
                        复制
                      </Button>
                    </div>
                    <pre className="max-h-48 overflow-auto rounded border border-border bg-muted/30 p-2 text-[11px]">
                      {JSON.stringify(selected.request_body, null, 2)}
                    </pre>
                  </div>
                )}
                <div className="pt-2">
                  <Badge className={statusClass(selected.status_code)} variant="outline">
                    HTTP {selected.status_code}
                  </Badge>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {stats && stats.top_actions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">热门动作 Top 10</CardTitle>
            <CardDescription>按调用频次排序</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              {stats.top_actions.map((a) => {
                const pct = (a.count / (stats.top_actions[0]?.count || 1)) * 100;
                return (
                  <div key={a.action} className="flex items-center gap-3">
                    <span className="w-40 shrink-0 truncate font-mono text-xs">{a.action}</span>
                    <div className="relative h-5 flex-1 overflow-hidden rounded-sm bg-muted/40">
                      <div
                        className="h-full bg-foreground/80"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className="num w-16 shrink-0 text-right text-xs tabular-nums">
                      {a.count.toLocaleString()}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div className="font-display text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-[10px] text-muted-foreground/70">{hint}</div>}
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-3 gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={mono ? "col-span-2 truncate font-mono" : "col-span-2"}>{value}</span>
    </div>
  );
}
