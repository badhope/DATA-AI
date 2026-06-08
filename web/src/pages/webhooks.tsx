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
import { ScrollArea } from "@/components/ui/scroll-area";
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
  type WebhookCreate,
  type WebhookDelivery,
  type WebhookSubscription,
  api,
} from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { copyToClipboard, formatDuration, formatRelativeTime, truncate } from "@/lib/utils";
import {
  Activity,
  Bell,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  Copy,
  ExternalLink,
  Globe,
  Loader2,
  Pause,
  Play,
  Plus,
  PowerOff,
  Radio,
  RefreshCw,
  Send,
  TestTube2,
  Trash2,
  Webhook,
  X,
  XCircle,
} from "lucide-react";
import * as React from "react";

const STATUS_COLORS: Record<string, string> = {
  success: "border-success/40 bg-success/10 text-success",
  failed: "border-destructive/40 bg-destructive/10 text-destructive",
  retrying: "border-warning/40 bg-warning/10 text-warning",
  pending: "border-info/40 bg-info/10 text-info",
};

export function WebhooksPage() {
  const [subs, setSubs] = React.useState<WebhookSubscription[]>([]);
  const [events, setEvents] = React.useState<string[]>([]);
  const [deliveries, setDeliveries] = React.useState<WebhookDelivery[]>([]);
  const [deliveryStats, setDeliveryStats] = React.useState<{
    total: number;
    by_status: Record<string, number>;
  } | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<WebhookSubscription | null>(null);
  const [viewing, setViewing] = React.useState<WebhookSubscription | null>(null);

  // form state
  const [formName, setFormName] = React.useState("");
  const [formUrl, setFormUrl] = React.useState("");
  const [formDesc, setFormDesc] = React.useState("");
  const [formEvents, setFormEvents] = React.useState<string[]>([]);
  const [formActive, setFormActive] = React.useState(true);
  const [formRetries, setFormRetries] = React.useState("5");
  const [formTimeout, setFormTimeout] = React.useState("30");

  async function load() {
    setLoading(true);
    try {
      const [s, e, d] = await Promise.all([
        api.listWebhooks(),
        api.listWebhookEvents(),
        api.listWebhookDeliveries({ limit: 100 }),
      ]);
      setSubs(s.subscriptions);
      setEvents(e.events);
      setDeliveries(d.deliveries);
      setDeliveryStats(d.stats);
    } catch (err) {
      reportError(err, "加载 Webhook 数据失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
    const t = setInterval(load, 10_000);
    return () => clearInterval(t);
  }, []);

  function resetForm() {
    setFormName("");
    setFormUrl("");
    setFormDesc("");
    setFormEvents([]);
    setFormActive(true);
    setFormRetries("5");
    setFormTimeout("30");
    setEditing(null);
  }

  function openEdit(s: WebhookSubscription) {
    setEditing(s);
    setFormName(s.name);
    setFormUrl(s.url);
    setFormDesc(s.description || "");
    setFormEvents(s.events);
    setFormActive(s.active);
    setFormRetries(String(s.max_retries));
    setFormTimeout(String(s.timeout_sec));
    setCreateOpen(true);
  }

  async function handleSubmit() {
    if (!formName || !formUrl || formEvents.length === 0) {
      toast.error("请填写 名称 / URL / 至少一个事件");
      return;
    }
    const payload: WebhookCreate = {
      name: formName,
      url: formUrl,
      description: formDesc || undefined,
      events: formEvents,
      active: formActive,
      max_retries: Number(formRetries) || 5,
      timeout_sec: Number(formTimeout) || 30,
    };
    try {
      if (editing) {
        await api.updateWebhook(editing.id, payload);
        toast.success("订阅已更新", { description: editing.id });
      } else {
        const res = await api.createWebhook(payload);
        toast.success("订阅已创建", {
          description: `secret: ${truncate(res.subscription.secret, 28)}`,
        });
      }
      setCreateOpen(false);
      resetForm();
      load();
    } catch (err) {
      reportError(err, editing ? "更新订阅失败" : "创建订阅失败");
    }
  }

  async function handleDelete(s: WebhookSubscription) {
    if (!confirm(`删除订阅 ${s.name}？关联投递历史保留。`)) return;
    try {
      await api.deleteWebhook(s.id);
      toast.success("订阅已删除");
      load();
    } catch (err) {
      reportError(err, "删除订阅失败");
    }
  }

  async function handleTest(s: WebhookSubscription) {
    try {
      const res = await api.testWebhook(s.id);
      toast.info("测试投递已发出", {
        description: `状态 ${res.delivery.status} · ${res.delivery.status_code || "—"}`,
      });
      load();
    } catch (err) {
      reportError(err, "测试投递失败");
    }
  }

  async function handleToggle(s: WebhookSubscription) {
    try {
      await api.updateWebhook(s.id, { active: !s.active });
      toast.success(s.active ? "已暂停" : "已启用", { description: s.name });
      load();
    } catch (err) {
      reportError(err, "切换状态失败");
    }
  }

  const total = deliveryStats?.total ?? 0;
  const successN = deliveryStats?.by_status.success ?? 0;
  const failedN = deliveryStats?.by_status.failed ?? 0;
  const retryN = deliveryStats?.by_status.retrying ?? 0;
  const successRate = total > 0 ? (successN / total) * 100 : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Webhook 集成"
        description="业务系统集成出口 — 订阅事件、HMAC 签名、指数退避重试"
        icon={<Webhook className="h-5 w-5" />}
        number="§11"
        eyebrow="Enterprise / Integration"
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
              <Plus className="h-4 w-4" /> 新建订阅
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard
          icon={<Radio className="h-4 w-4" />}
          label="订阅"
          value={subs.length.toString()}
          hint={`启用 ${subs.filter((s) => s.active).length}`}
        />
        <StatCard
          icon={<Send className="h-4 w-4" />}
          label="投递总数"
          value={total.toLocaleString()}
          hint="最近 100 条"
        />
        <StatCard
          icon={<CheckCircle2 className="h-4 w-4 text-success" />}
          label="成功率"
          value={`${successRate.toFixed(1)}%`}
          hint={`成功 ${successN} / 失败 ${failedN}`}
        />
        <StatCard
          icon={<Activity className="h-4 w-4 text-warning" />}
          label="重试中"
          value={retryN.toString()}
          hint="指数退避 1→60s"
        />
      </div>

      <Tabs defaultValue="subs">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="subs">订阅列表</TabsTrigger>
          <TabsTrigger value="deliveries">投递日志</TabsTrigger>
        </TabsList>

        <TabsContent value="subs" className="mt-4">
          {loading ? (
            <div className="flex items-center gap-2 py-12 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> 加载中…
            </div>
          ) : subs.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-sm text-muted-foreground">
                暂无 Webhook 订阅。点击「新建订阅」开始接入。
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
              {subs.map((s) => (
                <Card
                  key={s.id}
                  className="cursor-pointer transition-colors hover:border-foreground/40"
                  onClick={() => setViewing(s)}
                >
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <CardTitle className="flex items-center gap-2 text-base">
                          <Bell className="h-4 w-4" />
                          <span className="truncate">{s.name}</span>
                          {s.active ? (
                            <Badge variant="outline" className="border-success/40 bg-success/10 text-success">
                              ACTIVE
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="border-muted bg-muted text-muted-foreground">
                              PAUSED
                            </Badge>
                          )}
                        </CardTitle>
                        <CardDescription className="mt-1 truncate font-mono text-xs">
                          {s.url}
                        </CardDescription>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      <div className="flex flex-wrap gap-1">
                        {s.events.slice(0, 4).map((e) => (
                          <Badge key={e} variant="secondary" className="font-mono text-[10px]">
                            {e}
                          </Badge>
                        ))}
                        {s.events.length > 4 && (
                          <Badge variant="secondary" className="text-[10px]">
                            +{s.events.length - 4}
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>retry: {s.max_retries}</span>
                        <span>·</span>
                        <span>timeout: {s.timeout_sec}s</span>
                        <span>·</span>
                        <span>{formatRelativeTime(s.created_at)}</span>
                      </div>
                      <div className="flex flex-wrap gap-1 pt-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleTest(s);
                          }}
                        >
                          <TestTube2 className="h-3 w-3" /> 测试
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleToggle(s);
                          }}
                        >
                          {s.active ? (
                            <>
                              <Pause className="h-3 w-3" /> 暂停
                            </>
                          ) : (
                            <>
                              <Play className="h-3 w-3" /> 启用
                            </>
                          )}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            openEdit(s);
                          }}
                        >
                          编辑
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(s);
                          }}
                          className="text-destructive"
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="deliveries" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">投递日志 · 最近 100 条</CardTitle>
              <CardDescription>按时间倒序</CardDescription>
            </CardHeader>
            <CardContent>
              {deliveries.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  暂无投递记录。创建订阅后调用触发事件将出现。
                </div>
              ) : (
                <div className="max-h-[640px] overflow-y-auto">
                  <ul className="divide-y divide-border">
                    {deliveries.map((d) => (
                      <li key={d.id} className="grid grid-cols-12 gap-2 px-2 py-2.5 text-xs">
                        <Badge className={`col-span-2 ${STATUS_COLORS[d.status]}`} variant="outline">
                          {d.status.toUpperCase()}
                        </Badge>
                        <code className="num col-span-1 tabular-nums text-muted-foreground">
                          {d.status_code || "—"}
                        </code>
                        <span className="col-span-2 truncate font-mono">{d.event}</span>
                        <span className="num col-span-1 tabular-nums text-muted-foreground">
                          #{d.attempt}
                        </span>
                        <span className="num col-span-1 tabular-nums text-muted-foreground">
                          {formatDuration(d.duration_ms)}
                        </span>
                        <span className="col-span-3 truncate text-muted-foreground">
                          {truncate(d.url, 50)}
                        </span>
                        <span className="num col-span-2 text-right tabular-nums text-muted-foreground">
                          {formatRelativeTime(d.timestamp)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* create / edit dialog */}
      <Dialog
        open={createOpen}
        onOpenChange={(o) => {
          if (!o) resetForm();
          setCreateOpen(o);
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "编辑订阅" : "新建 Webhook 订阅"}</DialogTitle>
            <DialogDescription>
              接收端需校验 <code className="text-xs">X-Signature-256</code> HMAC-SHA256 签名
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs">名称</Label>
              <Input
                className="mt-1"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="例：order-service"
              />
            </div>
            <div>
              <Label className="text-xs">URL</Label>
              <Input
                className="mt-1"
                value={formUrl}
                onChange={(e) => setFormUrl(e.target.value)}
                placeholder="https://example.com/hook"
              />
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
              <Label className="text-xs">最大重试</Label>
              <Input
                className="mt-1"
                type="number"
                value={formRetries}
                onChange={(e) => setFormRetries(e.target.value)}
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
            <div className="col-span-2">
              <Label className="text-xs">订阅事件</Label>
              <div className="mt-1 max-h-48 overflow-y-auto rounded border border-border p-2">
                <div className="grid grid-cols-2 gap-1.5">
                  {events.map((e) => {
                    const checked = formEvents.includes(e);
                    return (
                      <label
                        key={e}
                        className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-muted/40"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            if (checked) setFormEvents(formEvents.filter((x) => x !== e));
                            else setFormEvents([...formEvents, e]);
                          }}
                          className="h-3 w-3"
                        />
                        <code className="truncate">{e}</code>
                      </label>
                    );
                  })}
                </div>
              </div>
              <div className="mt-1 flex items-center gap-1 text-[10px] text-muted-foreground">
                已选 {formEvents.length} / {events.length} 个事件
              </div>
            </div>
            <div className="col-span-2 flex items-center justify-between rounded border border-border p-2">
              <Label className="text-xs">启用</Label>
              <Switch checked={formActive} onCheckedChange={setFormActive} />
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
              <Check className="h-4 w-4" /> {editing ? "保存" : "创建"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* detail dialog */}
      <Dialog open={!!viewing} onOpenChange={(o) => !o && setViewing(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Webhook className="h-4 w-4" /> {viewing?.name}
            </DialogTitle>
            <DialogDescription>{viewing?.description || "（无描述）"}</DialogDescription>
          </DialogHeader>
          {viewing && (
            <div className="space-y-3 text-xs">
              <div className="grid grid-cols-2 gap-2">
                <KV label="ID" value={viewing.id} mono />
                <KV label="URL" value={viewing.url} mono />
                <KV label="状态" value={viewing.active ? "ACTIVE" : "PAUSED"} />
                <KV label="重试 / 超时" value={`${viewing.max_retries} 次 / ${viewing.timeout_sec}s`} />
              </div>
              <div>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-muted-foreground">Secret (HMAC 签名密钥)</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-5 px-2 text-[10px]"
                    onClick={() => copyToClipboard(viewing.secret)}
                  >
                    <Copy className="h-3 w-3" /> 复制
                  </Button>
                </div>
                <pre className="rounded border border-border bg-muted/30 p-2 font-mono text-[11px]">
                  {viewing.secret}
                </pre>
              </div>
              <div>
                <span className="text-muted-foreground">订阅事件</span>
                <div className="mt-1 flex flex-wrap gap-1">
                  {viewing.events.map((e) => (
                    <Badge key={e} variant="secondary" className="font-mono text-[10px]">
                      {e}
                    </Badge>
                  ))}
                </div>
              </div>
              {Object.keys(viewing.custom_headers || {}).length > 0 && (
                <div>
                  <span className="text-muted-foreground">自定义 Header</span>
                  <pre className="mt-1 rounded border border-border bg-muted/30 p-2 font-mono text-[11px]">
                    {JSON.stringify(viewing.custom_headers, null, 2)}
                  </pre>
                </div>
              )}
              <div className="text-muted-foreground">
                创建于 {new Date(viewing.created_at).toLocaleString("zh-CN")}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => viewing && window.open(viewing.url, "_blank", "noopener,noreferrer")}
              disabled={!viewing}
            >
              <ExternalLink className="h-3 w-3" /> 打开 URL
            </Button>
            <Button onClick={() => setViewing(null)}>
              <X className="h-3 w-3" /> 关闭
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
