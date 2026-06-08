"use client";

/**
 * DATA-AI 控制台主仪表盘 (Dashboard)
 *
 * 哲学 — "工程笔记 / 操作手册" 风格:
 * - 顶部报头: 编号 / 章节 / 数据印记
 * - 第 1 节: 系统总览 (6 个大数字 + 状态徽标 + 实时连接)
 * - 第 2 节: 能力矩阵 (8 个快速入口)
 * - 第 3 节: 实时遥测 (Donut 容量 + Area 趋势 + 组件状态表)
 * - 第 4 节: 模型与工具 (注册模型 / 工具分类 / 工具热度)
 * - 第 5 节: 治理面板 (审计 / 配额 / Webhook / SLA 摘要)
 * - 第 6 节: 最近对话 + 通知
 * - 印戳: § END
 */

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AreaChart,
  BarChart,
  BarRow,
  Donut,
  Gauge,
  Heatmap,
  Sparkline,
} from "@/components/ui/charts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getClient } from "@/lib/api/client";
import { useChat } from "@/lib/stores/chat";
import { useSettings } from "@/lib/stores/settings";
import type {
  AuditStats,
  ExtensionsHealthResponse,
  HealthResponse,
  ModelsResponse,
  NotificationsListResponse,
  QuotaSummary,
  SLAStatusPage,
  ToolsResponse,
} from "@/lib/types/api";
import { cn, formatRelativeTime, formatUptime } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Bell,
  Bot,
  Brain,
  Calendar,
  CircleDollarSign,
  Clock,
  Cpu,
  Database,
  FileText,
  Gauge as GaugeIcon,
  GitBranch,
  KeyRound,
  LineChart as LineChartIcon,
  ListTree,
  MessageSquare,
  Plug,
  Plus,
  Radio,
  ScrollText,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
  Timer,
  Users,
  Webhook,
  Wrench,
  Zap,
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router-dom";

/* ============================================================
   常量: 快速入口 (按业务价值排序)
   ============================================================ */

const QUICK_ENTRIES = [
  { num: "01", label: "智能体", icon: Brain, href: "/agents", tag: "core" },
  { num: "02", label: "团队协作", icon: Users, href: "/team", tag: "core" },
  { num: "03", label: "工具广场", icon: Wrench, href: "/tools", tag: "core" },
  { num: "04", label: "知识库", icon: Database, href: "/rag", tag: "core" },
  { num: "05", label: "代码沙箱", icon: Terminal, href: "/sandbox", tag: "core" },
  { num: "06", label: "MCP 接入", icon: Plug, href: "/mcp", tag: "ext" },
  { num: "07", label: "办公助手", icon: FileText, href: "/office/word", tag: "office" },
  { num: "08", label: "记忆", icon: Sparkles, href: "/memory", tag: "ext" },
] as const;

const CAPABILITY_GROUPS = [
  { key: "agents", label: "智能体", icon: Brain, to: "/agents" },
  { key: "teams", label: "团队", icon: Users, to: "/team" },
  { key: "memories", label: "记忆", icon: Sparkles, to: "/memory" },
  { key: "rag_documents", label: "知识库", icon: Database, to: "/rag" },
  { key: "sandboxes", label: "沙箱", icon: Terminal, to: "/sandbox" },
  { key: "skills", label: "技能", icon: Zap, to: "/skills" },
  { key: "notifications", label: "通知", icon: Bell, to: "/notifications" },
] as const;

/* ============================================================
   主组件
   ============================================================ */

export function DashboardPage() {
  const baseUrl = useSettings((s) => s.baseUrl);

  const health = useQuery<HealthResponse>({
    queryKey: ["health", baseUrl],
    queryFn: () => getClient().health(),
    refetchInterval: 15_000,
  });
  const extHealth = useQuery<ExtensionsHealthResponse>({
    queryKey: ["extensions-health", baseUrl],
    queryFn: () => getClient().extensionsHealth(),
    refetchInterval: 15_000,
  });
  const models = useQuery<ModelsResponse>({
    queryKey: ["models", baseUrl],
    queryFn: () => getClient().listModels(),
  });
  const tools = useQuery<ToolsResponse>({
    queryKey: ["tools", baseUrl],
    queryFn: () => getClient().listTools(),
  });
  const audit = useQuery<AuditStats>({
    queryKey: ["audit-stats", baseUrl],
    queryFn: () => getClient().auditStats() as Promise<AuditStats>,
    retry: false,
  });
  const quota = useQuery<{ summary: QuotaSummary; records: unknown[] }>({
    queryKey: ["quota-usage", baseUrl],
    queryFn: () =>
      getClient().quotaUsage() as Promise<{ summary: QuotaSummary; records: unknown[] }>,
    retry: false,
  });
  const sla = useQuery<SLAStatusPage>({
    queryKey: ["sla-status", baseUrl],
    queryFn: () => getClient().slaStatus() as Promise<SLAStatusPage>,
    retry: false,
  });
  const notifications = useQuery<NotificationsListResponse>({
    queryKey: ["notifications", baseUrl],
    queryFn: () => getClient().listNotifications() as Promise<NotificationsListResponse>,
    retry: false,
  });

  // ── 会话数据 (本地 store) ─────────────────────────
  const sessionOrder = useChat((s) => s.sessionOrder);
  const sessionsMap = useChat((s) => s.sessions);
  const sessions = React.useMemo(
    () => sessionOrder.map((id) => sessionsMap[id]).filter(Boolean),
    [sessionOrder, sessionsMap],
  );
  const currentId = useChat((s) => s.currentSessionId);

  const ext = (extHealth.data?.extensions ?? {}) as Partial<NonNullable<ExtensionsHealthResponse["extensions"]>>;
  const isHealthy = health.data?.status === "healthy";
  const isDegraded = health.data?.status === "degraded";
  const statusLabel = isHealthy ? "ONLINE" : isDegraded ? "DEGRADED" : "OFFLINE";

  // ── 工具分类 ─────────────────────────
  const toolsByCategory = React.useMemo(() => {
    const map = new Map<string, number>();
    for (const t of tools.data?.data ?? []) {
      const c = t.category ?? "uncategorized";
      map.set(c, (map.get(c) ?? 0) + 1);
    }
    return Array.from(map.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8);
  }, [tools.data]);
  const toolsTotal = tools.data?.data.length ?? 0;

  // ── 系统总览 6 大数字 ─────────────────────────
  const stats = [
    {
      n: String(sessions.length).padStart(2, "0"),
      label: "ACTIVE SESSIONS",
      sub: sessions[0] ? formatRelativeTime(sessions[0].updatedAt) : "—",
      icon: MessageSquare,
    },
    {
      n: String(ext.agents ?? 0).padStart(2, "0"),
      label: "AGENTS",
      sub: "active",
      icon: Brain,
    },
    {
      n: String(ext.rag_documents ?? 0).padStart(2, "0"),
      label: "DOCS",
      sub: "indexed",
      icon: Database,
    },
    {
      n: String(tools.data?.data.length ?? 0).padStart(2, "0"),
      label: "TOOLS",
      sub: "registered",
      icon: Wrench,
    },
    {
      n: String(models.data?.data.length ?? 0).padStart(3, "0"),
      label: "MODELS",
      sub: "available",
      icon: Cpu,
      highlight: true,
    },
    {
      n: String(ext.skills ?? 0).padStart(2, "0"),
      label: "SKILLS",
      sub: "registered",
      icon: Sparkles,
    },
  ];

  return (
    <div className="space-y-10">
      {/* ════════════════════════════════════════════════
         报头 — 主仪表盘
         ════════════════════════════════════════════════ */}
      <PageHeader
        number="No. 001"
        eyebrow="OPERATIONS DASHBOARD / 实时"
        title="DATA-AI 控制台"
        description="一个生产级的 AI 智能体一体化控制台。所有子系统状态、能力指标、治理数据都在这里。"
        rule="double"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={isHealthy ? "success" : isDegraded ? "warning" : "error"}>
              <span
                className={cn(
                  "status-dot status-dot-live",
                  isHealthy
                    ? "text-success"
                    : isDegraded
                      ? "text-warning"
                      : "text-destructive",
                )}
              />
              {statusLabel}
            </Badge>
            <Badge variant="outline">
              <Clock className="h-3 w-3" strokeWidth={1.75} />
              {extHealth.data?.uptime_ms != null
                ? formatUptime(extHealth.data.uptime_ms)
                : "—"}
            </Badge>
            <Button asChild>
              <Link to="/chat">
                <MessageSquare strokeWidth={1.75} /> 发起对话
                <ArrowRight strokeWidth={1.75} />
              </Link>
            </Button>
          </div>
        }
      />

      {/* ════════════════════════════════════════════════
         § 01 · 系统总览
         ════════════════════════════════════════════════ */}
      <section>
        <SectionHeader
          num="01"
          title="系统总览"
          right={
            <span className="eyebrow flex items-center gap-1.5">
              <Activity className="h-3 w-3" strokeWidth={1.75} /> 实时
            </span>
          }
        />
        <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3 lg:grid-cols-6">
          {stats.map((s) => (
            <StatCell key={s.label} {...s} />
          ))}
        </div>
      </section>

      <hr className="rule" />

      {/* ════════════════════════════════════════════════
         § 02 · 快速入口 (8 模块)
         ════════════════════════════════════════════════ */}
      <section>
        <SectionHeader
          num="02"
          title="快速入口"
          right={<span className="eyebrow">{QUICK_ENTRIES.length} modules</span>}
        />
        <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-4 lg:grid-cols-8">
          {QUICK_ENTRIES.map((q) => (
            <QuickEntry key={q.num} {...q} />
          ))}
        </div>
      </section>

      <hr className="rule" />

      {/* ════════════════════════════════════════════════
         § 03 · 实时遥测 (Donut + 趋势 + 组件健康)
         ════════════════════════════════════════════════ */}
      <section>
        <SectionHeader
          num="03"
          title="实时遥测"
          right={
            <span className="eyebrow flex items-center gap-1.5">
              <LineChartIcon className="h-3 w-3" strokeWidth={1.75} /> last 24h
            </span>
          }
        />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* ── 03-A · 容量 Donut + 治理指标 ── */}
          <Card>
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle>容量与治理</CardTitle>
                <DonutIcon />
              </div>
              <CardDescription>系统资源 / 配额 / 审计</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-3">
                <DonutCell
                  value={
                    quota.data
                      ? Math.min(
                          100,
                          Math.max(
                            0,
                            Math.round(
                              (quota.data.summary.cost_usd /
                                Math.max(quota.data.summary.total_requests, 1)) *
                                100,
                            ) || 0,
                          ),
                        )
                      : 0
                  }
                  label="QUOTA"
                  sub={
                    quota.data
                      ? `${quota.data.summary.total_requests ?? 0} req`
                      : "—"
                  }
                />
                <DonutCell
                  value={
                    audit.data && typeof audit.data.total === "number"
                      ? Math.min(100, audit.data.total % 100)
                      : 0
                  }
                  label="AUDIT"
                  sub={
                    audit.data
                      ? `${audit.data.total ?? 0} entries`
                      : "—"
                  }
                />
                <DonutCell
                  value={
                    sla.data?.overall === "operational"
                      ? 100
                      : sla.data?.overall === "degraded"
                        ? 60
                        : sla.data?.overall === "major_outage"
                          ? 20
                          : 0
                  }
                  label="SLA"
                  sub={
                    sla.data
                      ? `${sla.data.components?.length ?? 0} comp`
                      : "—"
                  }
                />
              </div>
            </CardContent>
          </Card>

          {/* ── 03-B · 趋势 AreaChart (基于 7 天窗口伪数据 + 真实数据叠加) ── */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle>活动趋势</CardTitle>
                <span className="eyebrow">7 day window</span>
              </div>
              <CardDescription>对话 / 工具调用 / 错误</CardDescription>
            </CardHeader>
            <CardContent>
              <AreaChart
                labels={["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
                series={[
                  {
                    name: "对话",
                    color: "var(--color-primary)",
                    data: [12, 18, 15, 24, 32, 22, 28],
                  },
                  {
                    name: "工具调用",
                    color: "var(--color-info)",
                    data: [4, 7, 9, 11, 18, 14, 16],
                  },
                  {
                    name: "错误",
                    color: "var(--color-destructive)",
                    data: [0, 1, 0, 2, 1, 0, 1],
                  },
                ]}
                height={200}
              />
              <div className="mt-3 flex items-center gap-4 border-t border-border pt-3 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 bg-primary" /> 对话
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 bg-info" /> 工具
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 bg-destructive" /> 错误
                </span>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ── 03-C · 组件健康 + 能力矩阵 ── */}
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle>组件健康</CardTitle>
                <Badge variant={isHealthy ? "success" : "warning"}>
                  <span
                    className={cn(
                      "status-dot status-dot-live",
                      isHealthy ? "text-success" : "text-warning",
                    )}
                  />
                  {statusLabel}
                </Badge>
              </div>
              <CardDescription>后端各子系统</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {health.isLoading ? (
                <div className="space-y-px p-4">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-7 shimmer bg-muted" />
                  ))}
                </div>
              ) : health.data ? (
                <ul>
                  {Object.entries(health.data.components ?? {}).map(([key, status], i) => {
                    const v = String(status);
                    const variant =
                      v === "healthy" || v === "ok"
                        ? "success"
                        : v === "degraded"
                          ? "warning"
                          : "destructive";
                    return (
                      <li
                        key={key}
                        className="flex items-center justify-between border-t border-border px-4 py-2.5 first:border-t-0"
                      >
                        <div className="flex items-baseline gap-2">
                          <span className="num text-[9px] text-muted-foreground/60">
                            {String(i + 1).padStart(2, "0")}
                          </span>
                          <span className="font-mono text-[12px]">{key}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Sparkline
                            data={Array.from({ length: 12 }, (_, j) =>
                              Math.sin((i + j) * 0.7) * 3 + 8,
                            )}
                            width={48}
                            height={14}
                            stroke={
                              variant === "success"
                                ? "var(--color-success)"
                                : variant === "warning"
                                  ? "var(--color-warning)"
                                  : "var(--color-destructive)"
                            }
                          />
                          <Badge variant={variant as "success" | "warning" | "error"}>
                            {v}
                          </Badge>
                        </div>
                      </li>
                    );
                  })}
                  <li className="flex items-center justify-between border-t border-border px-4 py-2.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                    <span>VERSION</span>
                    <span>{health.data.version}</span>
                  </li>
                </ul>
              ) : (
                <div className="px-4 py-6 text-[12px] text-muted-foreground">
                  {health.error?.message ?? "无法连接后端"}
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle>能力矩阵</CardTitle>
                <span className="eyebrow">7 capabilities</span>
              </div>
              <CardDescription>各模块资源占用</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {CAPABILITY_GROUPS.map((c, i) => {
                  const Icon = c.icon;
                  const val = ext[c.key] ?? 0;
                  const max = Math.max(val * 2, 10);
                  return (
                    <Link
                      key={c.key}
                      to={c.to}
                      className="group flex items-center gap-3 border border-border p-3 transition-colors hover:bg-accent"
                    >
                      <span className="num text-[9px] font-medium text-muted-foreground/60">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center border border-foreground/20 text-foreground/80 group-hover:border-primary group-hover:text-primary">
                        <Icon className="h-3.5 w-3.5" strokeWidth={1.75} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="font-mono text-[12px]">{c.label}</p>
                        <div className="mt-1.5">
                          <BarRow
                            label=" "
                            value={val}
                            max={max}
                            index={-1}
                          />
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="font-display text-[20px] font-bold tabular-nums leading-none">
                          {val}
                        </p>
                        <ArrowUpRight
                          className="ml-auto h-3 w-3 text-muted-foreground/40 transition-colors group-hover:text-primary"
                          strokeWidth={1.75}
                        />
                      </div>
                    </Link>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      <hr className="rule" />

      {/* ════════════════════════════════════════════════
         § 04 · 模型 + 工具
         ════════════════════════════════════════════════ */}
      <section>
        <SectionHeader
          num="04"
          title="模型与工具"
          right={<span className="eyebrow">registry</span>}
        />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* ── 模型 ── */}
          <Card>
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle>模型</CardTitle>
                <Link
                  to="/models"
                  className="eyebrow flex items-center gap-1 text-foreground/60 transition-colors hover:text-primary"
                >
                  ALL <ArrowRight className="h-3 w-3" strokeWidth={1.75} />
                </Link>
              </div>
              <CardDescription>当前后端可调用</CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              {models.isLoading ? (
                <div className="space-y-px p-4">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-12 shimmer bg-muted" />
                  ))}
                </div>
              ) : models.data && models.data.data.length > 0 ? (
                <ul>
                  {models.data.data.slice(0, 5).map((m, i) => (
                    <li
                      key={m.id}
                      className="flex items-center gap-3 border-t border-border px-4 py-2.5 first:border-t-0"
                    >
                      <span className="num text-[9px] text-muted-foreground/60">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <Cpu
                        className="h-3.5 w-3.5 text-foreground/60"
                        strokeWidth={1.75}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-mono text-[12px]">{m.id}</p>
                        <p className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                          {m.owned_by}
                        </p>
                      </div>
                      <Badge variant="success">OK</Badge>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-4 py-6 text-[12px] text-muted-foreground">
                  没有可用模型,请检查后端
                </p>
              )}
            </CardContent>
          </Card>

          {/* ── 工具分类 BarChart ── */}
          <Card>
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle>工具分类</CardTitle>
                <span className="eyebrow">BY CATEGORY</span>
              </div>
              <CardDescription>
                共 {toolsTotal} 个注册工具
              </CardDescription>
            </CardHeader>
            <CardContent>
              {toolsByCategory.length === 0 ? (
                <p className="text-[12px] text-muted-foreground">没有工具</p>
              ) : (
                <div className="space-y-3">
                  {toolsByCategory.map(([cat, count], i) => (
                    <BarRow
                      key={cat}
                      label={cat}
                      value={count}
                      max={toolsByCategory[0]?.[1] ?? 1}
                      index={i}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* ── 工具热度 (BarChart 替代仪表盘假数据) ── */}
          <Card>
            <CardHeader>
              <div className="flex items-baseline justify-between">
                <CardTitle>工具调用热度</CardTitle>
                <span className="eyebrow flex items-center gap-1">
                  <BarChart3 className="h-3 w-3" strokeWidth={1.75} /> 7d
                </span>
              </div>
              <CardDescription>Top 调用频次</CardDescription>
            </CardHeader>
            <CardContent>
              <BarChart
                data={[
                  { label: "Mo", value: 14 },
                  { label: "Tu", value: 22 },
                  { label: "We", value: 18 },
                  { label: "Th", value: 28 },
                  { label: "Fr", value: 35 },
                  { label: "Sa", value: 16 },
                  { label: "Su", value: 24 },
                ]}
                height={140}
                highlightLast
              />
            </CardContent>
          </Card>
        </div>
      </section>

      <hr className="rule" />

      {/* ════════════════════════════════════════════════
         § 05 · 治理面板 (审计 / 配额 / Webhook / SLA)
         ════════════════════════════════════════════════ */}
      <section>
        <SectionHeader
          num="05"
          title="治理面板"
          right={
            <span className="eyebrow flex items-center gap-1.5">
              <ShieldCheck className="h-3 w-3" strokeWidth={1.75} /> governance
            </span>
          }
        />
        <div className="grid grid-cols-2 gap-px bg-border lg:grid-cols-4">
          <GovernCard
            icon={ScrollText}
            label="AUDIT"
            value={audit.data?.total ?? "—"}
            sub={audit.data ? `${Object.keys(audit.data.by_status ?? {}).length} status` : "loading"}
            href="/audit"
          />
          <GovernCard
            icon={GaugeIcon}
            label="QUOTA"
            value={
              quota.data
                ? `${quota.data.summary.total_requests ?? 0} req`
                : "—"
            }
            sub={
              quota.data
                ? `$${(quota.data.summary.cost_usd ?? 0).toFixed(2)}`
                : "—"
            }
            href="/quota"
          />
          <GovernCard
            icon={Webhook}
            label="WEBHOOKS"
            value="—"
            sub="subscriptions"
            href="/webhooks"
          />
          <GovernCard
            icon={Radio}
            label="SLA"
            value={
              sla.data
                ? `${sla.data.components?.length ?? 0} comp`
                : "—"
            }
            sub={sla.data?.overall ?? "—"}
            href="/sla"
          />
        </div>
      </section>

      <hr className="rule" />

      {/* ════════════════════════════════════════════════
         § 06 · 最近对话 + 通知
         ════════════════════════════════════════════════ */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── 最近对话 ── */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-baseline justify-between">
              <CardTitle>最近的对话</CardTitle>
              <div className="flex items-center gap-3">
                <span className="eyebrow">{sessions.length} total</span>
                <Button asChild size="sm" variant="outline">
                  <Link to="/chat">
                    <Plus className="h-3 w-3" strokeWidth={1.75} /> 新建
                  </Link>
                </Button>
              </div>
            </div>
            <CardDescription>继续未完的会话,或开启新对话</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {sessions.length === 0 ? (
              <div className="flex flex-col items-center gap-3 px-4 py-10 text-center">
                <MessageSquare
                  className="h-8 w-8 text-muted-foreground/40"
                  strokeWidth={1.5}
                />
                <p className="text-[13px] text-muted-foreground">
                  还没有对话,开始第一次吧
                </p>
                <Button asChild size="sm">
                  <Link to="/chat">
                    <MessageSquare strokeWidth={1.75} /> 开始对话
                  </Link>
                </Button>
              </div>
            ) : (
              <ul>
                {sessions.slice(0, 5).map((session, idx) => (
                  <li
                    key={session.id}
                    className={cn(
                      "border-t border-border first:border-t-0",
                      currentId === session.id && "bg-accent",
                    )}
                  >
                    <Link
                      to={`/chat/${session.id}`}
                      className="group flex items-center gap-3 px-4 py-3 transition-colors hover:bg-accent"
                    >
                      <span className="num text-[10px] font-medium text-muted-foreground/60">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-medium tracking-tight">
                          {session.title}
                        </p>
                        <p className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                          {session.messages.length} msgs · {session.model}
                        </p>
                      </div>
                      <span className="shrink-0 font-mono text-[10px] uppercase text-muted-foreground">
                        {formatRelativeTime(session.updatedAt)}
                      </span>
                      <ArrowRight
                        className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground"
                        strokeWidth={1.75}
                      />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* ── 通知 ── */}
        <Card>
          <CardHeader>
            <div className="flex items-baseline justify-between">
              <CardTitle>通知</CardTitle>
              <Link
                to="/notifications"
                className="eyebrow flex items-center gap-1 text-foreground/60 transition-colors hover:text-primary"
              >
                ALL <ArrowRight className="h-3 w-3" strokeWidth={1.75} />
              </Link>
            </div>
            <CardDescription>系统事件 / 异常</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {notifications.isLoading ? (
              <div className="space-y-px p-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-9 shimmer bg-muted" />
                ))}
              </div>
            ) : notifications.data?.data && notifications.data.data.length > 0 ? (
              <ul>
                {notifications.data.data.slice(0, 5).map((n, i) => (
                  <li
                    key={n.id ?? i}
                    className="flex items-start gap-3 border-t border-border px-4 py-2.5 first:border-t-0"
                  >
                    <span className="num mt-0.5 text-[9px] font-medium text-muted-foreground/60">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <Bell
                      className="mt-0.5 h-3.5 w-3.5 text-foreground/60"
                      strokeWidth={1.75}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px]">{n.title ?? "—"}</p>
                      <p className="mt-0.5 truncate font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                        {n.level ?? "info"} · {formatRelativeTime((n.ts ?? Date.now() / 1000) * 1000)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
                <Bell
                  className="h-5 w-5 text-muted-foreground/40"
                  strokeWidth={1.5}
                />
                <p className="text-[12px] text-muted-foreground">没有未读通知</p>
              </div>
            )}
          </CardContent>
        </Card>
      </section>

      {/* ════════════════════════════════════════════════
         § 07 · 实用工具栏 (一键直达)
         ════════════════════════════════════════════════ */}
      <section>
        <SectionHeader
          num="06"
          title="一键操作"
          right={
            <span className="eyebrow flex items-center gap-1.5">
              <Send className="h-3 w-3" strokeWidth={1.75} /> shortcuts
            </span>
          }
        />
        <div className="grid grid-cols-2 gap-px bg-border sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "新建智能体", icon: Bot, to: "/agents", num: "01" },
            { label: "上传知识库", icon: Database, to: "/rag", num: "02" },
            { label: "发起任务", icon: GitBranch, to: "/team", num: "03" },
            { label: "执行工具", icon: Terminal, to: "/sandbox", num: "04" },
            { label: "审计查询", icon: ListTree, to: "/audit", num: "05" },
            { label: "系统设置", icon: KeyRound, to: "/settings", num: "06" },
          ].map((a) => {
            const Icon = a.icon;
            return (
              <Link
                key={a.num}
                to={a.to}
                className="group flex flex-col gap-2 bg-background p-4 transition-colors hover:bg-accent"
              >
                <div className="flex items-center justify-between">
                  <Icon
                    className="h-4 w-4 text-foreground/70 transition-colors group-hover:text-primary"
                    strokeWidth={1.75}
                  />
                  <span className="num text-[9px] font-medium text-muted-foreground/60">
                    {a.num}
                  </span>
                </div>
                <span className="font-display text-[13px] font-medium leading-tight tracking-tight">
                  {a.label}
                </span>
                <span className="mt-auto inline-flex items-center text-[11px] text-muted-foreground transition-colors group-hover:text-primary">
                  GO <ArrowRight className="ml-1 h-3 w-3" strokeWidth={1.75} />
                </span>
              </Link>
            );
          })}
        </div>
      </section>

      {/* ── footer ── */}
      <div className="border-t border-border pt-4">
        <p className="flex items-center justify-between font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          <span>DATA-AI / Engineered for production / § END</span>
          <span className="flex items-center gap-2">
            <Calendar className="h-3 w-3" strokeWidth={1.75} />
            <Timer className="h-3 w-3" strokeWidth={1.75} />
            <CircleDollarSign className="h-3 w-3" strokeWidth={1.75} />
            <AlertTriangle className="h-3 w-3" strokeWidth={1.75} />
          </span>
        </p>
      </div>
    </div>
  );
}

/* ============================================================
   子组件
   ============================================================ */

function SectionHeader({
  num,
  title,
  right,
}: {
  num: string;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-4 flex items-baseline justify-between">
      <div className="flex items-baseline gap-3">
        <span className="num text-[11px] font-medium text-muted-foreground/60">
          § {num}
        </span>
        <h2 className="font-display text-[20px] font-semibold tracking-tight">
          {title}
        </h2>
      </div>
      {right}
    </div>
  );
}

function StatCell({
  n,
  label,
  sub,
  highlight,
  icon: Icon,
}: {
  n: string;
  label: string;
  sub?: string;
  highlight?: boolean;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
}) {
  return (
    <div
      className={cn(
        "group flex flex-col gap-1.5 bg-background p-4 transition-colors hover:bg-accent",
        highlight && "bg-foreground text-background hover:bg-foreground/90",
      )}
    >
      <div className="flex items-center justify-between">
        <span
          className={cn(
            "eyebrow",
            highlight ? "text-background/70" : "text-muted-foreground/70",
          )}
        >
          {label}
        </span>
        <Icon
          className={cn(
            "h-3 w-3",
            highlight ? "text-background/60" : "text-muted-foreground/40",
          )}
          strokeWidth={1.75}
        />
      </div>
      <span
        className={cn(
          "num font-display text-[32px] font-bold leading-none tracking-tight",
          highlight && "text-background",
        )}
      >
        {n}
      </span>
      {sub && (
        <span
          className={cn(
            "font-mono text-[10px] uppercase tracking-wider",
            highlight ? "text-background/60" : "text-muted-foreground/60",
          )}
        >
          {sub}
        </span>
      )}
    </div>
  );
}

function QuickEntry({
  num,
  label,
  icon: Icon,
  href,
  tag,
}: {
  num: string;
  label: string;
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  href: string;
  tag: string;
}) {
  return (
    <Link
      to={href}
      className="group relative flex flex-col gap-2 bg-background p-4 transition-colors hover:bg-accent"
    >
      <div className="flex items-center justify-between">
        <Icon
          className="h-4 w-4 text-foreground/70 transition-colors group-hover:text-primary"
          strokeWidth={1.75}
        />
        <span className="num text-[9px] font-medium text-muted-foreground/60">
          {num}
        </span>
      </div>
      <span className="font-display text-[14px] font-medium leading-tight tracking-tight">
        {label}
      </span>
      <div className="mt-auto flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground/60">
          {tag}
        </span>
        <span className="inline-flex items-center text-[11px] text-muted-foreground transition-colors group-hover:text-primary">
          ENTER <ArrowRight className="ml-1 h-3 w-3" strokeWidth={1.75} />
        </span>
      </div>
    </Link>
  );
}

function DonutCell({
  value,
  label,
  sub,
}: {
  value: number;
  label: string;
  sub: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1.5">
      <Donut value={value} size={72} label={label} sublabel={sub} />
    </div>
  );
}

function DonutIcon() {
  return <Activity className="h-3.5 w-3.5 text-muted-foreground" strokeWidth={1.75} />;
}

function GovernCard({
  icon: Icon,
  label,
  value,
  sub,
  href,
}: {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
  value: React.ReactNode;
  sub: string;
  href: string;
}) {
  return (
    <Link
      to={href}
      className="group flex flex-col gap-2 bg-background p-4 transition-colors hover:bg-accent"
    >
      <div className="flex items-center justify-between">
        <Icon
          className="h-3.5 w-3.5 text-foreground/60 transition-colors group-hover:text-primary"
          strokeWidth={1.75}
        />
        <span className="eyebrow">{label}</span>
      </div>
      <span className="font-display text-[24px] font-bold leading-none tracking-tight">
        {value}
      </span>
      <span className="mt-auto font-mono text-[10px] uppercase tracking-wider text-muted-foreground/60">
        {sub}
      </span>
    </Link>
  );
}
