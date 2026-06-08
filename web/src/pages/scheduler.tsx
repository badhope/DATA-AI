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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import {
  type JobCreate,
  type JobExecution,
  type ScheduledJob,
  api,
} from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { formatDuration, formatRelativeTime } from "@/lib/utils";
import {
  Activity,
  AlertCircle,
  Calendar,
  CheckCircle2,
  Clock,
  Cog,
  Globe,
  Loader2,
  Pause,
  Play,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Search,
  Sparkles,
  Terminal,
  Timer,
  Trash2,
  XCircle,
  Zap,
} from "lucide-react";
import * as React from "react";

const ACTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  http: Globe,
  agent_run: Sparkles,
  memory_cleanup: Cog,
  rag_reindex: Activity,
  shell: Terminal,
};

const STATUS_STYLES: Record<string, string> = {
  success: "border-success/40 bg-success/10 text-success",
  failed: "border-destructive/40 bg-destructive/10 text-destructive",
  running: "border-info/40 bg-info/10 text-info",
  timeout: "border-warning/40 bg-warning/10 text-warning",
  never: "border-border bg-muted/30 text-muted-foreground",
  skipped: "border-border bg-muted/30 text-muted-foreground",
};

export function SchedulerPage() {
  const [jobs, setJobs] = React.useState<ScheduledJob[]>([]);
  const [stats, setStats] = React.useState<{ total_jobs: number; enabled_jobs: number; total_executions: number; by_status: Record<string, number> } | null>(null);
  const [executions, setExecutions] = React.useState<JobExecution[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<ScheduledJob | null>(null);
  const [filterJob, setFilterJob] = React.useState("");
  const [filterStatus, setFilterStatus] = React.useState("all");

  // form
  const [formName, setFormName] = React.useState("");
  const [formDesc, setFormDesc] = React.useState("");
  const [formAction, setFormAction] = React.useState<JobCreate["action_type"]>("http");
  const [formPayload, setFormPayload] = React.useState("{}");
  const [formKind, setFormKind] = React.useState<"cron" | "at" | "every">("cron");
  const [formExpression, setFormExpression] = React.useState("");
  const [formTimeout, setFormTimeout] = React.useState("60");
  const [formEnabled, setFormEnabled] = React.useState(true);

  async function load() {
    setLoading(true);
    try {
      const [j, e] = await Promise.all([
        api.listJobs(),
        api.listJobExecutions({ limit: 100 }),
      ]);
      setJobs(j.jobs);
      setStats(j.stats);
      setExecutions(e.executions);
    } catch (err) {
      reportError(err, "加载定时任务失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
    const t = setInterval(load, 8_000);
    return () => clearInterval(t);
  }, []);

  function resetForm() {
    setFormName("");
    setFormDesc("");
    setFormAction("http");
    setFormPayload("{}");
    setFormKind("cron");
    setFormExpression("");
    setFormTimeout("60");
    setFormEnabled(true);
    setEditing(null);
  }

  function openEdit(j: ScheduledJob) {
    setEditing(j);
    setFormName(j.name);
    setFormDesc(j.description);
    setFormAction(j.action_type as JobCreate["action_type"]);
    setFormPayload(JSON.stringify(j.action_payload || {}, null, 2));
    setFormKind(j.schedule.kind);
    setFormExpression(j.schedule.expression);
    setFormTimeout(String(j.timeout_sec));
    setFormEnabled(j.enabled);
    setCreateOpen(true);
  }

  async function handleSubmit() {
    if (!formName || !formExpression) {
      toast.error("请填写 名称 / 表达式");
      return;
    }
    let parsedPayload: Record<string, unknown> = {};
    try {
      parsedPayload = formPayload.trim() ? JSON.parse(formPayload) : {};
    } catch (e) {
      toast.error("Payload JSON 解析失败");
      return;
    }
    const payload: JobCreate = {
      name: formName,
      description: formDesc || undefined,
      action_type: formAction,
      action_payload: parsedPayload,
      schedule: { kind: formKind, expression: formExpression },
      enabled: formEnabled,
      timeout_sec: Number(formTimeout) || 60,
    };
    try {
      if (editing) {
        await api.updateJob(editing.id, payload);
        toast.success("任务已更新");
      } else {
        await api.createJob(payload);
        toast.success("任务已创建", { description: `下次执行: ${formExpression}` });
      }
      setCreateOpen(false);
      resetForm();
      load();
    } catch (err) {
      reportError(err, editing ? "更新任务失败" : "创建任务失败");
    }
  }

  async function handleDelete(j: ScheduledJob) {
    if (!confirm(`删除任务 ${j.name}？执行历史将保留。`)) return;
    try {
      await api.deleteJob(j.id);
      toast.success("任务已删除");
      load();
    } catch (err) {
      reportError(err, "删除任务失败");
    }
  }

  async function handleTrigger(j: ScheduledJob) {
    try {
      const res = await api.triggerJob(j.id);
      toast.info("已触发执行", { description: `execution ${res.execution.id.slice(0, 12)}` });
      load();
    } catch (err) {
      reportError(err, "触发执行失败");
    }
  }

  async function handleToggle(j: ScheduledJob) {
    try {
      await api.updateJob(j.id, { enabled: !j.enabled });
      toast.success(j.enabled ? "已暂停" : "已启用", { description: j.name });
      load();
    } catch (err) {
      reportError(err, "切换状态失败");
    }
  }

  const filteredExecutions = React.useMemo(() => {
    return executions.filter((e) => {
      if (filterJob && e.job_id !== filterJob) return false;
      if (filterStatus !== "all" && e.status !== filterStatus) return false;
      return true;
    });
  }, [executions, filterJob, filterStatus]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="定时任务"
        description="cron / at / every — 周期任务、报告生成、清理作业"
        icon={<Timer className="h-5 w-5" />}
        number="§12"
        eyebrow="Enterprise / Automation"
        actions={
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={load} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              刷新
            </Button>
            <Button
              size="sm"
              onClick={() => {
                resetForm();
                setCreateOpen(true);
              }}
            >
              <Plus className="h-4 w-4" /> 新建任务
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          icon={<Calendar className="h-4 w-4" />}
          label="任务总数"
          value={(stats?.total_jobs ?? jobs.length).toString()}
          hint={`启用 ${stats?.enabled_jobs ?? 0}`}
        />
        <StatCard
          icon={<Activity className="h-4 w-4" />}
          label="总执行"
          value={(stats?.total_executions ?? 0).toLocaleString()}
          hint="所有任务累计"
        />
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4 text-success" />}
          label="成功"
          value={(stats?.by_status.success ?? 0).toString()}
          hint="累计成功执行"
        />
        <StatCard
          icon={<XCircle className="h-4 w-4 text-destructive" />}
          label="失败"
          value={(stats?.by_status.failed ?? 0).toString()}
          hint="累计失败 / 超时"
        />
      </div>

      <Tabs defaultValue="jobs">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="jobs">任务列表</TabsTrigger>
          <TabsTrigger value="executions">执行历史</TabsTrigger>
        </TabsList>

        <TabsContent value="jobs" className="mt-4">
          {loading ? (
            <div className="flex items-center gap-2 py-12 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> 加载中…
            </div>
          ) : jobs.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                暂无定时任务。点击「新建任务」开始。
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {jobs.map((j) => {
                const Icon = ACTION_ICONS[j.action_type] || Zap;
                return (
                  <Card key={j.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <CardTitle className="flex items-center gap-2 text-base">
                            <Icon className="h-4 w-4" />
                            <span className="truncate">{j.name}</span>
                            {j.enabled ? (
                              <Badge variant="outline" className="border-success/40 bg-success/10 text-success">
                                ENABLED
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="border-muted bg-muted text-muted-foreground">
                                PAUSED
                              </Badge>
                            )}
                          </CardTitle>
                          <CardDescription className="mt-1 truncate">{j.description || "（无描述）"}</CardDescription>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2 text-xs">
                        <div className="grid grid-cols-2 gap-2">
                          <KV label="动作" value={j.action_type} mono />
                          <KV
                            label="调度"
                            value={`${j.schedule.kind}: ${j.schedule.expression}`}
                            mono
                          />
                          <KV
                            label="下次"
                            value={
                              j.next_run_at
                                ? new Date(j.next_run_at).toLocaleString("zh-CN")
                                : "—"
                            }
                          />
                          <KV
                            label="上次"
                            value={
                              j.last_run_at ? formatRelativeTime(j.last_run_at) : "—"
                            }
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={STATUS_STYLES[j.last_status]} variant="outline">
                            last: {j.last_status}
                          </Badge>
                          <span className="text-muted-foreground">
                            运行 {j.run_count} · 失败 {j.failure_count} · 超时 {j.timeout_sec}s
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-1 pt-2">
                          <Button size="sm" variant="outline" onClick={() => handleTrigger(j)}>
                            <Zap className="h-3 w-3" /> 立即执行
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => handleToggle(j)}>
                            {j.enabled ? (
                              <>
                                <Pause className="h-3 w-3" /> 暂停
                              </>
                            ) : (
                              <>
                                <Play className="h-3 w-3" /> 启用
                              </>
                            )}
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => openEdit(j)}>
                            编辑
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => handleDelete(j)}
                            className="text-destructive"
                          >
                            <Trash2 className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="executions" className="mt-4 space-y-3">
          <Card>
            <CardContent className="pt-6">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <Label className="text-xs">任务</Label>
                  <Select value={filterJob} onValueChange={setFilterJob}>
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="全部任务" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">全部任务</SelectItem>
                      {jobs.map((j) => (
                        <SelectItem key={j.id} value={j.id}>
                          {j.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs">状态</Label>
                  <Select value={filterStatus} onValueChange={setFilterStatus}>
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">全部</SelectItem>
                      <SelectItem value="running">运行中</SelectItem>
                      <SelectItem value="success">成功</SelectItem>
                      <SelectItem value="failed">失败</SelectItem>
                      <SelectItem value="timeout">超时</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-end">
                  <span className="text-xs text-muted-foreground">
                    共 {filteredExecutions.length} 条
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">执行历史</CardTitle>
              <CardDescription>按开始时间倒序</CardDescription>
            </CardHeader>
            <CardContent>
              {filteredExecutions.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  暂无执行记录。
                </div>
              ) : (
                <div className="max-h-[640px] overflow-y-auto">
                  <ul className="divide-y divide-border">
                    {filteredExecutions.map((e) => {
                      const job = jobs.find((j) => j.id === e.job_id);
                      return (
                        <li key={e.id} className="grid grid-cols-12 gap-2 px-2 py-2.5 text-xs">
                          <Badge className={`col-span-2 ${STATUS_STYLES[e.status]}`} variant="outline">
                            {e.status.toUpperCase()}
                          </Badge>
                          <span className="col-span-3 truncate font-mono">
                            {job?.name || e.job_id.slice(0, 12)}
                          </span>
                          <span className="num col-span-2 tabular-nums text-muted-foreground">
                            {formatRelativeTime(e.started_at)}
                          </span>
                          <span className="num col-span-2 tabular-nums text-muted-foreground">
                            {formatDuration(e.duration_ms)}
                          </span>
                          <span className="col-span-3 truncate text-muted-foreground">
                            {e.error || (e.output ? e.output.slice(0, 80) : "—")}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog
        open={createOpen}
        onOpenChange={(o) => {
          if (!o) resetForm();
          setCreateOpen(o);
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "编辑任务" : "新建定时任务"}</DialogTitle>
            <DialogDescription>支持 cron / at / every 三种调度</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">名称</Label>
              <Input
                className="mt-1"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="daily-report"
              />
            </div>
            <div>
              <Label className="text-xs">动作</Label>
              <Select
                value={formAction}
                onValueChange={(v) => setFormAction(v as JobCreate["action_type"])}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="http">HTTP 请求</SelectItem>
                  <SelectItem value="agent_run">Agent 执行</SelectItem>
                  <SelectItem value="memory_cleanup">记忆清理</SelectItem>
                  <SelectItem value="rag_reindex">RAG 重建索引</SelectItem>
                  <SelectItem value="shell">Shell 命令</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="col-span-2">
              <Label className="text-xs">描述</Label>
              <Input
                className="mt-1"
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                placeholder="可选"
              />
            </div>
            <div>
              <Label className="text-xs">调度类型</Label>
              <Select value={formKind} onValueChange={(v) => setFormKind(v as typeof formKind)}>
                <SelectTrigger className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="cron">cron (周期)</SelectItem>
                  <SelectItem value="at">at (单次时间戳)</SelectItem>
                  <SelectItem value="every">every (间隔秒)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs">
                表达式 {formKind === "cron" && <span className="text-muted-foreground">例: 0 9 * * *</span>}
                {formKind === "at" && <span className="text-muted-foreground">ISO 8601</span>}
                {formKind === "every" && <span className="text-muted-foreground">秒数</span>}
              </Label>
              <Input
                className="mt-1 font-mono"
                value={formExpression}
                onChange={(e) => setFormExpression(e.target.value)}
                placeholder={formKind === "cron" ? "0 9 * * *" : formKind === "at" ? "2026-06-08T09:00:00" : "3600"}
              />
            </div>
            <div>
              <Label className="text-xs">超时 (秒)</Label>
              <Input
                className="mt-1"
                type="number"
                value={formTimeout}
                onChange={(e) => setFormTimeout(e.target.value)}
              />
            </div>
            <div className="flex items-center justify-between rounded border border-border p-2">
              <Label className="text-xs">启用</Label>
              <Switch checked={formEnabled} onCheckedChange={setFormEnabled} />
            </div>
            <div className="col-span-2">
              <Label className="text-xs">Action Payload (JSON)</Label>
              <Textarea
                className="mt-1 font-mono text-xs"
                rows={5}
                value={formPayload}
                onChange={(e) => setFormPayload(e.target.value)}
                placeholder='{"url": "https://example.com", "method": "POST"}'
              />
              <div className="mt-1 text-[10px] text-muted-foreground">
                {formAction === "http" && "建议字段: url, method, headers, body"}
                {formAction === "agent_run" && "建议字段: agent_id, input"}
                {formAction === "memory_cleanup" && "建议字段: older_than_days, type"}
                {formAction === "rag_reindex" && "建议字段: doc_ids (可选全部)"}
                {formAction === "shell" && "建议字段: command"}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setCreateOpen(false);
                resetForm();
              }}
            >
              取消
            </Button>
            <Button onClick={handleSubmit}>
              <CheckCircle2 className="h-4 w-4" /> {editing ? "保存" : "创建"}
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

function KV({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-2 gap-2 border border-border p-2">
      <span className="text-muted-foreground">{label}</span>
      <span className={`truncate ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}
