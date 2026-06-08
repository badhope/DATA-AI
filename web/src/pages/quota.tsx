"use client";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toaster";
import {
  type QuotaActorStatus,
  type QuotaPolicy,
  type QuotaPolicyCreate,
  type QuotaSummary,
  type UsageRecord,
  api,
} from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { formatNumber, formatRelativeTime } from "@/lib/utils";
import {
  AlertTriangle,
  Coins,
  DollarSign,
  Gauge,
  Loader2,
  Plus,
  Power,
  RefreshCw,
  Search,
  ShieldOff,
  Sparkles,
  Trash2,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import * as React from "react";

export function QuotaPage() {
  const [policies, setPolicies] = React.useState<QuotaPolicy[]>([]);
  const [usage, setUsage] = React.useState<{ summary: QuotaSummary; records: UsageRecord[] } | null>(
    null,
  );
  const [actorStatus, setActorStatus] = React.useState<QuotaActorStatus | null>(null);
  const [actorFilter, setActorFilter] = React.useState("");
  const [loading, setLoading] = React.useState(true);
  const [createOpen, setCreateOpen] = React.useState(false);

  // form state
  const [formScope, setFormScope] = React.useState<"global" | "key" | "user">("global");
  const [formScopeId, setFormScopeId] = React.useState("");
  const [formDailyToken, setFormDailyToken] = React.useState("");
  const [formMonthlyToken, setFormMonthlyToken] = React.useState("");
  const [formDailyReq, setFormDailyReq] = React.useState("");
  const [formQps, setFormQps] = React.useState("");
  const [formConcurrent, setFormConcurrent] = React.useState("");
  const [formEnabled, setFormEnabled] = React.useState(true);

  async function load() {
    setLoading(true);
    try {
      const [p, u, a] = await Promise.all([
        api.listQuotaPolicies(),
        api.quotaUsage(actorFilter || undefined),
        actorFilter ? api.quotaStatus(actorFilter) : Promise.resolve(null),
      ]);
      setPolicies(p.policies);
      setUsage(u);
      setActorStatus(a);
    } catch (e) {
      reportError(e, "加载配额数据失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actorFilter]);

  async function handleCreate() {
    const payload: QuotaPolicyCreate = {
      scope: formScope,
      scope_id: formScope === "global" ? "default" : formScopeId || "default",
      daily_token_limit: formDailyToken ? Number(formDailyToken) : undefined,
      monthly_token_limit: formMonthlyToken ? Number(formMonthlyToken) : undefined,
      daily_request_limit: formDailyReq ? Number(formDailyReq) : undefined,
      qps_limit: formQps ? Number(formQps) : undefined,
      max_concurrent: formConcurrent ? Number(formConcurrent) : undefined,
      enabled: formEnabled,
    };
    try {
      await api.createQuotaPolicy(payload);
      toast.success("策略已创建");
      setCreateOpen(false);
      // reset
      setFormScopeId("");
      setFormDailyToken("");
      setFormMonthlyToken("");
      setFormDailyReq("");
      setFormQps("");
      setFormConcurrent("");
      setFormEnabled(true);
      load();
    } catch (e) {
      reportError(e, "创建策略失败");
    }
  }

  async function handleDelete(p: QuotaPolicy) {
    if (!confirm(`删除策略 ${p.scope}:${p.scope_id}？`)) return;
    try {
      await api.deleteQuotaPolicy(p.scope, p.scope_id);
      toast.success("策略已删除");
      load();
    } catch (e) {
      reportError(e, "删除策略失败");
    }
  }

  const summary = usage?.summary;
  const records = usage?.records ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="配额 & 用量"
        description="Token 成本控制、限流策略、按 actor 配额 — 防止账单失控"
        icon={<Gauge className="h-5 w-5" />}
        number="§10"
        eyebrow="Enterprise / Cost"
        actions={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={load} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> 新建策略
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          icon={<Zap className="h-4 w-4" />}
          label="总调用"
          value={formatNumber(summary?.total_requests ?? 0)}
          hint="所有模型累计"
        />
        <StatCard
          icon={<Coins className="h-4 w-4" />}
          label="总 Token"
          value={formatNumber(summary?.total_tokens ?? 0)}
          hint={`prompt ${formatNumber(summary?.prompt_tokens ?? 0)} / completion ${formatNumber(summary?.completion_tokens ?? 0)}`}
        />
        <StatCard
          icon={<DollarSign className="h-4 w-4 text-success" />}
          label="估算成本"
          value={`$${(summary?.cost_usd ?? 0).toFixed(4)}`}
          hint="按模型官方单价"
        />
        <StatCard
          icon={<ShieldOff className="h-4 w-4" />}
          label="策略数"
          value={policies.length.toString()}
          hint={`已启用 ${policies.filter((p) => p.enabled).length}`}
        />
      </div>

      <Tabs defaultValue="dashboard">
        <TabsList className="grid w-full max-w-xl grid-cols-3">
          <TabsTrigger value="dashboard">用量仪表盘</TabsTrigger>
          <TabsTrigger value="policies">策略列表</TabsTrigger>
          <TabsTrigger value="actor">按 Actor 查询</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="mt-4 space-y-4">
          {summary && summary.by_model && Object.keys(summary.by_model).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="h-4 w-4" /> 模型用量分布
                </CardTitle>
                <CardDescription>按模型聚合 — token / 调用 / 成本</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {Object.entries(summary.by_model)
                    .sort(([, a], [, b]) => b.tokens - a.tokens)
                    .map(([model, s]) => {
                      const maxTokens = Math.max(
                        ...Object.values(summary.by_model).map((x) => x.tokens),
                      );
                      const pct = maxTokens ? (s.tokens / maxTokens) * 100 : 0;
                      return (
                        <div key={model} className="space-y-1">
                          <div className="flex items-center justify-between text-sm">
                            <span className="font-mono">{model}</span>
                            <span className="num tabular-nums text-xs text-muted-foreground">
                              {formatNumber(s.tokens)} tok · {s.requests} req · ${s.cost_usd.toFixed(4)}
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-sm bg-muted/40">
                            <div
                              className="h-full bg-foreground/80"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4" /> 最近调用 · {records.length} 条
              </CardTitle>
              <CardDescription>按时间倒序</CardDescription>
            </CardHeader>
            <CardContent>
              {records.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  暂无用量记录。运行 chat / agent / rag 后将出现。
                </div>
              ) : (
                <div className="max-h-[480px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-card text-muted-foreground">
                      <tr className="border-b border-border text-left">
                        <th className="py-2">时间</th>
                        <th className="py-2">actor</th>
                        <th className="py-2">模型</th>
                        <th className="py-2 text-right">prompt</th>
                        <th className="py-2 text-right">completion</th>
                        <th className="py-2 text-right">cost</th>
                        <th className="py-2 text-right">延迟</th>
                      </tr>
                    </thead>
                    <tbody>
                      {records.map((r, i) => (
                        <tr key={i} className="border-b border-border/40">
                          <td className="py-1.5 text-muted-foreground">
                            {formatRelativeTime(r.timestamp)}
                          </td>
                          <td className="py-1.5 font-mono">{r.actor}</td>
                          <td className="py-1.5 font-mono">{r.model}</td>
                          <td className="num py-1.5 text-right tabular-nums">
                            {formatNumber(r.prompt_tokens)}
                          </td>
                          <td className="num py-1.5 text-right tabular-nums">
                            {formatNumber(r.completion_tokens)}
                          </td>
                          <td className="num py-1.5 text-right tabular-nums">
                            ${r.cost_usd.toFixed(4)}
                          </td>
                          <td className="num py-1.5 text-right tabular-nums text-muted-foreground">
                            {r.latency_ms}ms
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="policies" className="mt-4 space-y-3">
          {policies.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                暂无配额策略。点击「新建策略」开始限流。
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {policies.map((p) => (
                <Card key={`${p.scope}:${p.scope_id}`}>
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <CardTitle className="text-base">
                          <Badge variant="outline" className="mr-2">
                            {p.scope}
                          </Badge>
                          {p.scope_id}
                        </CardTitle>
                        <CardDescription className="mt-1">
                          {p.enabled ? (
                            <span className="text-success">● 已启用</span>
                          ) : (
                            <span className="text-muted-foreground">○ 已停用</span>
                          )}
                        </CardDescription>
                      </div>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => handleDelete(p)}
                        className="h-7 w-7 text-destructive"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <dl className="grid grid-cols-2 gap-2 text-xs">
                      <Field
                        icon={<Zap className="h-3 w-3" />}
                        label="日 Token"
                        value={p.daily_token_limit ? formatNumber(p.daily_token_limit) : "—"}
                      />
                      <Field
                        icon={<Coins className="h-3 w-3" />}
                        label="月 Token"
                        value={p.monthly_token_limit ? formatNumber(p.monthly_token_limit) : "—"}
                      />
                      <Field
                        icon={<TrendingUp className="h-3 w-3" />}
                        label="日请求"
                        value={p.daily_request_limit ? formatNumber(p.daily_request_limit) : "—"}
                      />
                      <Field
                        icon={<Gauge className="h-3 w-3" />}
                        label="QPS"
                        value={p.qps_limit ? String(p.qps_limit) : "—"}
                      />
                      <Field
                        icon={<Users className="h-3 w-3" />}
                        label="并发"
                        value={p.max_concurrent ? String(p.max_concurrent) : "—"}
                      />
                    </dl>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="actor" className="mt-4 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">按 Actor 查询</CardTitle>
              <CardDescription>查看某 key / user 的策略匹配与实时用量</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="输入 api-key / user-id"
                    value={actorFilter}
                    onChange={(e) => setActorFilter(e.target.value)}
                    className="pl-8"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {actorFilter && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">actor: {actorFilter}</CardTitle>
                <CardDescription>命中策略 + 今日用量</CardDescription>
              </CardHeader>
              <CardContent>
                {!actorStatus ? (
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    加载中或该 actor 无任何数据
                  </div>
                ) : (
                  <div className="space-y-4">
                    {actorStatus.policies.length === 0 ? (
                      <div className="border-l-2 border-warning bg-warning/5 px-3 py-2 text-xs">
                        <AlertTriangle className="mr-1 inline h-3 w-3" />
                        该 actor 未命中任何限流策略 — 不受配额约束
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <div className="text-xs font-medium text-muted-foreground">命中策略</div>
                        {actorStatus.policies.map((p, i) => (
                          <div
                            key={i}
                            className="flex items-center justify-between border border-border p-2 text-xs"
                          >
                            <Badge variant="outline">
                              {p.scope}:{p.scope_id}
                            </Badge>
                            <div className="num tabular-nums text-muted-foreground">
                              {p.daily_token_limit
                                ? `日 tok ${formatNumber(p.daily_token_limit)}`
                                : ""}
                              {p.qps_limit ? ` · QPS ${p.qps_limit}` : ""}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="space-y-1 border-t border-border pt-3">
                      <div className="text-xs font-medium text-muted-foreground">今日用量</div>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <MiniStat
                          label="请求"
                          value={formatNumber(actorStatus.usage_today.total_requests)}
                        />
                        <MiniStat
                          label="Token"
                          value={formatNumber(actorStatus.usage_today.total_tokens)}
                        />
                        <MiniStat
                          label="成本"
                          value={`$${actorStatus.usage_today.cost_usd.toFixed(4)}`}
                        />
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>新建配额策略</DialogTitle>
            <DialogDescription>留空的字段表示不限制</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">Scope</Label>
              <Select value={formScope} onValueChange={(v) => setFormScope(v as typeof formScope)}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="global">global (全局)</SelectItem>
                  <SelectItem value="key">key (API Key)</SelectItem>
                  <SelectItem value="user">user (用户)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {formScope !== "global" && (
              <div>
                <Label className="text-xs">Scope ID</Label>
                <Input
                  className="mt-1"
                  value={formScopeId}
                  onChange={(e) => setFormScopeId(e.target.value)}
                  placeholder="key-xxx / user-xxx"
                />
              </div>
            )}
            <div>
              <Label className="text-xs">日 Token 上限</Label>
              <Input
                className="mt-1"
                type="number"
                value={formDailyToken}
                onChange={(e) => setFormDailyToken(e.target.value)}
                placeholder="例 1000000"
              />
            </div>
            <div>
              <Label className="text-xs">月 Token 上限</Label>
              <Input
                className="mt-1"
                type="number"
                value={formMonthlyToken}
                onChange={(e) => setFormMonthlyToken(e.target.value)}
                placeholder="例 30000000"
              />
            </div>
            <div>
              <Label className="text-xs">日请求上限</Label>
              <Input
                className="mt-1"
                type="number"
                value={formDailyReq}
                onChange={(e) => setFormDailyReq(e.target.value)}
                placeholder="例 10000"
              />
            </div>
            <div>
              <Label className="text-xs">QPS 上限</Label>
              <Input
                className="mt-1"
                type="number"
                value={formQps}
                onChange={(e) => setFormQps(e.target.value)}
                placeholder="例 50"
              />
            </div>
            <div>
              <Label className="text-xs">最大并发</Label>
              <Input
                className="mt-1"
                type="number"
                value={formConcurrent}
                onChange={(e) => setFormConcurrent(e.target.value)}
                placeholder="例 20"
              />
            </div>
            <div className="flex items-center justify-between rounded border border-border p-2">
              <Label className="text-xs">启用</Label>
              <Switch checked={formEnabled} onCheckedChange={setFormEnabled} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button onClick={handleCreate}>
              <Power className="h-4 w-4" /> 创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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

function Field({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="border border-border p-2">
      <div className="mb-0.5 flex items-center gap-1 text-[10px] text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="num text-sm tabular-nums">{value}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-border p-2">
      <div className="text-[10px] text-muted-foreground">{label}</div>
      <div className="num text-sm tabular-nums">{value}</div>
    </div>
  );
}
