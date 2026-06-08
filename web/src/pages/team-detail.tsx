import { reportError } from "@/lib/errors";
("use client");

import { EmptyState } from "@/components/shared/empty-state";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { type TeamConfig, type TeamMessage, type TeamRunResponse, api } from "@/lib/api/client";
import { cn, formatDuration } from "@/lib/utils";
import { motion } from "framer-motion";
import {
  ChevronLeft,
  Crown,
  GitBranch,
  Loader2,
  MessageSquare,
  Network,
  Play,
  Send,
  Users,
  Vote,
} from "lucide-react";
import * as React from "react";
import { useNavigate, useParams } from "react-router-dom";

export function TeamDetailPage() {
  const { teamId: id = "" } = useParams();
  const navigate = useNavigate();
  const [team, setTeam] = React.useState<TeamConfig | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [running, setRunning] = React.useState(false);
  const [runResult, setRunResult] = React.useState<TeamRunResponse | null>(null);
  const [input, setInput] = React.useState("");
  const [messages, setMessages] = React.useState<TeamMessage[]>([]);

  React.useEffect(() => {
    let mounted = true;
    setLoading(true);
    api
      .getTeam(id)
      .then((t) => mounted && setTeam(t))
      .catch((e) =>
        toast.error("加载团队失败", { description: e instanceof Error ? e.message : String(e) }),
      )
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [id]);

  async function loadMessages() {
    try {
      const res = await api.getTeamMessages(id);
      setMessages(res.data);
    } catch (e) {
      // 静默
    }
  }

  React.useEffect(() => {
    loadMessages();
  }, [id]);

  async function run() {
    if (!input.trim()) {
      toast.error("请输入任务");
      return;
    }
    setRunning(true);
    setRunResult(null);
    try {
      const res = await api.runTeam(id, { input: input.trim() });
      setRunResult(res);
      toast[res.status === "error" ? "error" : "success"](
        res.status === "error" ? "运行失败" : "团队运行完成",
        { description: `${res.member_answers.length} 个成员 · ${res.duration_ms || 0}ms` },
      );
      loadMessages();
    } catch (e) {
      reportError(e, "请求失败");
    } finally {
      setRunning(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (!team) {
    return <div className="py-24 text-center text-sm text-muted-foreground">团队不存在</div>;
  }

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => navigate("/team")}>
        <ChevronLeft className="h-4 w-4" /> 返回
      </Button>
      <PageHeader
        title={team.name}
        description={team.description}
        icon={<Users className="h-5 w-5" />}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Network className="h-4 w-4 text-primary" /> 通信画布
            </CardTitle>
            <CardDescription>成员之间的消息流转</CardDescription>
          </CardHeader>
          <CardContent>
            <CommunicationCanvas team={team} runResult={runResult} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">运行</CardTitle>
            <CardDescription>输入任务，多个成员协作完成</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              rows={4}
              placeholder="例如：写一篇关于 Web 3.0 的简短分析..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
            />
            <Button onClick={run} disabled={running} className="w-full">
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {running ? "运行中..." : "运行团队"}
            </Button>
            {runResult && (
              <div className="space-y-2">
                <Badge variant={runResult.status === "error" ? "error" : "success"}>
                  {runResult.status}
                </Badge>
                <p className="text-xs text-muted-foreground">
                  {runResult.member_answers.length} 个成员 · 共识: {runResult.consensus_method}
                  {runResult.duration_ms ? ` · ${runResult.duration_ms}ms` : ""}
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {runResult && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">最终答案</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-primary/30 bg-primary/5 p-4 text-sm">
              {runResult.error ? (
                <p className="text-destructive">{runResult.error}</p>
              ) : (
                <p className="whitespace-pre-wrap">{runResult.final_answer}</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {runResult && runResult.votes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Vote className="h-4 w-4 text-warning" /> 投票记录
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {runResult.votes.map((v, i) => (
                <div key={i} className="rounded-md border border-border/40 bg-muted/20 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{v.member}</span>
                    <Badge variant="accent">置信度 {v.confidence.toFixed(2)}</Badge>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{v.answer}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <MessageSquare className="h-4 w-4 text-info" /> 消息流
          </CardTitle>
        </CardHeader>
        <CardContent>
          {messages.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">暂无消息</p>
          ) : (
            <div className="max-h-80 space-y-2 overflow-y-auto">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className="rounded-md border border-border/40 bg-muted/20 p-3 text-sm"
                >
                  <p className="text-xs text-muted-foreground">
                    {m.from} → {m.to}
                  </p>
                  <p className="mt-1 whitespace-pre-wrap">{m.content}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function CommunicationCanvas({
  team,
  runResult,
}: { team: TeamConfig; runResult: TeamRunResponse | null }) {
  const cx = 300;
  const cy = 200;
  const radius = 130;

  const positions = team.members.map((m, i) => {
    const angle = (i / Math.max(team.members.length, 1)) * Math.PI * 2 - Math.PI / 2;
    return {
      ...m,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
    };
  });

  return (
    <div className="relative aspect-[3/2] w-full overflow-hidden border border-border bg-muted">
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 600 400">
        {/* 协调器中心节点 */}
        <line x1={cx} y1={cy} x2={cx} y2={cy} />
        <circle
          cx={cx}
          cy={cy}
          r="36"
          className="fill-primary/20 stroke-primary"
          strokeWidth="2"
        />
        <text
          x={cx}
          y={cy - 6}
          textAnchor="middle"
          className="fill-foreground text-xs font-semibold"
        >
          协调器
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" className="fill-primary text-[10px]">
          coordinator
        </text>
        <text x={cx} y={cy + 24} textAnchor="middle" className="fill-primary text-[10px]">
          {team.consensus_method}
        </text>

        {/* 成员节点 + 连线 */}
        {positions.map((p) => {
          const answered = runResult?.member_answers.find((a) => a.member === p.name);
          const stroke = answered ? "#a78bfa" : "#52525b";
          return (
            <g key={p.id}>
              <line
                x1={cx}
                y1={cy}
                x2={p.x}
                y2={p.y}
                className={cn(answered ? "stroke-primary" : "stroke-zinc-700")}
                strokeWidth={answered ? 2 : 1}
                strokeDasharray={runResult ? "none" : "4 4"}
                markerEnd="url(#arrowhead)"
              />
              <circle
                cx={p.x}
                cy={p.y}
                r="28"
                className={cn(
                  "fill-background",
                  answered ? "stroke-primary" : "stroke-zinc-700",
                )}
                strokeWidth="2"
              />
              <text
                x={p.x}
                y={p.y - 4}
                textAnchor="middle"
                className="fill-foreground text-[10px] font-medium"
              >
                {p.name.length > 6 ? p.name.slice(0, 6) + "…" : p.name}
              </text>
              <text
                x={p.x}
                y={p.y + 10}
                textAnchor="middle"
                className="fill-muted-foreground text-[9px]"
              >
                {p.role}
              </text>
              {answered && (
                <text
                  x={p.x}
                  y={p.y + 40}
                  textAnchor="middle"
                  className="fill-foreground text-[9px]"
                >
                  ✓ {answered.duration_ms}ms
                </text>
              )}
            </g>
          );
        })}
        <defs>
          <marker id="arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <polygon points="0 0, 6 3, 0 6" className="fill-primary" />
          </marker>
        </defs>
      </svg>

      {runResult && (
        <div className="absolute right-3 top-3 rounded-md border border-primary/40 bg-primary/10 px-2 py-1 text-xs text-primary">
          {runResult.member_answers.length}/{team.members.length} 已完成
        </div>
      )}
    </div>
  );
}
