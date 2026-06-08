"use client";

import { Markdown } from "@/components/chat/markdown";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { getClient } from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import type { AgentConfig, AgentRunsListResponse, ToolCall } from "@/lib/types/api";
import { cn } from "@/lib/utils";
import { type AgentStatus, StatusBadge } from "@/pages/agents";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Bot, ChevronRight, Cog, Loader2, Play, Save, Send, Wrench } from "lucide-react";
import * as React from "react";
import { Link, useParams } from "react-router-dom";

const STATE_FLOW: AgentStatus[] = ["idle", "thinking", "executing", "streaming", "finished"];

interface AgentEvent {
  type: "thinking" | "tool_call" | "tool_result" | "token" | "finish" | "error";
  ts: number;
  content?: string;
  toolCall?: ToolCall;
  toolResult?: unknown;
  error?: string;
}

const STATE_LABEL: Record<AgentStatus, string> = {
  idle: "空闲",
  thinking: "思考",
  executing: "执行工具",
  streaming: "输出",
  finished: "完成",
  error: "错误",
};

export function AgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>();

  const [agent, setAgent] = React.useState<AgentConfig | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!agentId) return;
    let mounted = true;
    setLoading(true);
    getClient()
      .getAgent(agentId)
      .then((a) => {
        if (!mounted) return;
        setAgent(a);
        setEditName(a.name);
        setEditModel(a.model);
        setEditMaxIter(a.max_iterations);
        setEditTemp(a.temperature);
        setEditSystemPrompt(a.system_prompt);
        setEditReflection(a.enable_reflection);
        setEditToolNames(a.tool_names);
      })
      .catch((e) => reportError(e, "加载智能体"))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [agentId]);

  async function saveEdit() {
    if (!agentId) return;
    if (!editName.trim()) {
      toast.error("名称不能为空");
      return;
    }
    setSaving(true);
    try {
      const updated = await getClient().updateAgent(agentId, {
        name: editName.trim(),
        model: editModel,
        max_iterations: editMaxIter,
        temperature: editTemp,
        system_prompt: editSystemPrompt,
        enable_reflection: editReflection,
        tool_names: editToolNames,
      });
      setAgent(updated);
      setEditing(false);
      toast.success("配置已保存", { description: updated.name });
    } catch (e) {
      reportError(e, "保存智能体配置");
    } finally {
      setSaving(false);
    }
  }

  const [events, setEvents] = React.useState<AgentEvent[]>([]);
  const [input, setInput] = React.useState("");
  const [running, setRunning] = React.useState(false);
  const [status, setStatus] = React.useState<AgentStatus>("idle");
  const [runs, setRuns] = React.useState<AgentRunsListResponse["data"]>([]);
  const [runsLoading, setRunsLoading] = React.useState(false);

  // 编辑配置
  const [editing, setEditing] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [editName, setEditName] = React.useState("");
  const [editModel, setEditModel] = React.useState("");
  const [editMaxIter, setEditMaxIter] = React.useState(10);
  const [editTemp, setEditTemp] = React.useState(0.7);
  const [editSystemPrompt, setEditSystemPrompt] = React.useState("");
  const [editReflection, setEditReflection] = React.useState(true);
  const [editToolNames, setEditToolNames] = React.useState<string[]>([]);

  const modelsQuery = useQuery({
    queryKey: ["models"],
    queryFn: () => getClient().listModels(),
  });
  const toolsQuery = useQuery({
    queryKey: ["tools"],
    queryFn: () => getClient().listTools(),
  });

  const loadRuns = React.useCallback(async () => {
    if (!agentId) return;
    setRunsLoading(true);
    try {
      const res = await getClient().listAgentRuns(agentId);
      setRuns(res.data);
    } catch (e) {
      reportError(e, "加载历史运行");
    } finally {
      setRunsLoading(false);
    }
  }, [agentId]);

  React.useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  async function run() {
    if (!agentId || !input.trim()) return;
    setRunning(true);
    setStatus("thinking");
    setEvents([{ type: "thinking", ts: Date.now(), content: "正在处理用户输入..." }]);
    try {
      setEvents((e) => [
        ...e,
        { type: "thinking", ts: Date.now(), content: "调用 LLM 思考下一步" },
      ]);
      setStatus("executing");
      const res = await getClient().runAgent(agentId, { input: input.trim() });
      setEvents((e) => [
        ...e,
        ...res.tool_calls.map((tc) => ({
          type: "tool_call" as const,
          ts: Date.now(),
          toolCall: tc,
        })),
        { type: "token", ts: Date.now(), content: res.output || "(空响应)" },
        { type: "finish" as const, ts: Date.now() },
      ]);
      setStatus("finished");
      if (res.error) {
        toast.warning("运行完成但有错误", { description: res.error });
      } else {
        toast.success("运行完成", {
          description: `${res.iterations} 轮迭代 · ${res.duration_ms}ms`,
        });
      }
    } catch (e) {
      setStatus("error");
      const msg = e instanceof Error ? e.message : String(e);
      setEvents((ev) => [...ev, { type: "error", ts: Date.now(), error: msg }]);
      reportError(e, "运行智能体");
    } finally {
      setRunning(false);
      loadRuns();
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (!agent) {
    return <div className="py-24 text-center text-sm text-muted-foreground">智能体不存在</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Button asChild variant="ghost" size="sm">
          <Link to="/agents">
            <ArrowLeft className="h-3 w-3" /> 智能体列表
          </Link>
        </Button>
      </div>

      <PageHeader
        title={agent.name}
        description={`${agent.model} · ${agent.tool_names.length} 个工具 · 最大 ${agent.max_iterations} 轮迭代`}
        icon={<Bot className="h-5 w-5" />}
        actions={<StatusBadge status={status} />}
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">状态机</CardTitle>
          <CardDescription>Agent 当前执行阶段</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-1">
            {STATE_FLOW.map((s, i) => {
              const idx = STATE_FLOW.indexOf(status);
              const reached = i <= idx;
              return (
                <React.Fragment key={s}>
                  <div
                    className={cn(
                      "flex flex-1 flex-col items-center gap-1 rounded-md border p-2 text-center text-xs transition-colors",
                      reached
                        ? "border-primary/30 bg-primary/10 text-foreground"
                        : "border-border bg-card text-muted-foreground",
                    )}
                  >
                    <span
                      className={cn(
                        "h-2 w-2 rounded-full",
                        reached ? "bg-primary" : "bg-muted-foreground/30",
                        status === s && "pulse-dot",
                      )}
                    />
                    <span className="font-medium">{STATE_LABEL[s]}</span>
                  </div>
                  {i < STATE_FLOW.length - 1 && (
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/50" />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">运行 / 事件流</CardTitle>
            <CardDescription>token-by-token 重放</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="events">
              <TabsList>
                <TabsTrigger value="events">事件流</TabsTrigger>
                <TabsTrigger value="messages">消息</TabsTrigger>
                <TabsTrigger value="input">输入</TabsTrigger>
              </TabsList>
              <TabsContent value="events" className="mt-3">
                <ScrollArea className="h-[420px] rounded-md border border-border bg-muted/20 p-3">
                  <ul className="space-y-1.5 text-xs">
                    {events.map((e, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                          {new Date(e.ts).toLocaleTimeString("zh-CN", { hour12: false })}
                        </span>
                        <Badge
                          variant={
                            e.type === "error"
                              ? "error"
                              : e.type === "finish"
                                ? "success"
                                : e.type === "tool_call"
                                  ? "info"
                                  : "outline"
                          }
                          className="shrink-0"
                        >
                          {e.type}
                        </Badge>
                        <span className="min-w-0 flex-1 break-all">
                          {e.type === "thinking" && e.content}
                          {e.type === "tool_call" && e.toolCall && (
                            <code className="font-mono text-foreground">
                              {e.toolCall.function.name}({e.toolCall.function.arguments})
                            </code>
                          )}
                          {e.type === "tool_result" && (
                            <code className="font-mono text-success">
                              {JSON.stringify(e.toolResult)}
                            </code>
                          )}
                          {e.type === "token" && e.content}
                          {e.type === "error" && <span className="text-destructive">{e.error}</span>}
                        </span>
                      </li>
                    ))}
                  </ul>
                </ScrollArea>
              </TabsContent>
              <TabsContent value="messages" className="mt-3">
                {runsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Spinner className="h-4 w-4" />
                  </div>
                ) : runs.length === 0 ? (
                  <div className="flex flex-col items-center justify-center rounded-md border border-border bg-muted/20 py-10 text-sm text-muted-foreground">
                    <Bot className="mb-2 h-6 w-6 opacity-30" />
                    还没有运行记录
                    <p className="mt-1 text-xs">运行后会在这里显示历史记录</p>
                  </div>
                ) : (
                  <div className="max-h-[420px] space-y-3 overflow-y-auto rounded-md border border-border bg-muted/20 p-3">
                    {runs.map((r) => {
                      const rInput =
                        typeof r.input === "string" ? r.input : JSON.stringify(r.input);
                      return (
                        <div
                          key={r.run_id}
                          className="rounded-md border border-border/40 bg-background p-3 text-sm"
                        >
                          <div className="mb-2 flex items-center gap-2 text-[10px] text-muted-foreground">
                            <span className="font-mono">
                              {new Date(r.started_at * 1000).toLocaleString("zh-CN")}
                            </span>
                            <span>·</span>
                            <span>{r.iterations} 轮迭代</span>
                            <span>·</span>
                            <span>{r.duration_ms}ms</span>
                            {r.error && (
                              <span className="ml-auto rounded bg-destructive/15 px-1.5 py-0.5 text-[10px] text-destructive">
                                error
                              </span>
                            )}
                          </div>
                          <div className="mb-2 rounded-md bg-primary/5 p-2 text-xs">
                            <p className="text-[10px] font-semibold text-foreground">用户</p>
                            <p className="mt-0.5 whitespace-pre-wrap">{rInput}</p>
                          </div>
                          {r.output && (
                            <div className="rounded-md bg-info/5 p-2 text-xs">
                              <p className="text-[10px] font-semibold text-info">智能体</p>
                              <p className="mt-0.5 whitespace-pre-wrap">{r.output}</p>
                            </div>
                          )}
                          {r.tool_calls && r.tool_calls.length > 0 && (
                            <div className="mt-2 space-y-1">
                              <p className="text-[10px] font-semibold text-muted-foreground">
                                工具调用 ({r.tool_calls.length})
                              </p>
                              {r.tool_calls.map((tc, i) => (
                                <code
                                  key={i}
                                  className="block truncate rounded bg-black/30 px-2 py-1 font-mono text-[10px] text-success"
                                >
                                  {tc.function.name}({tc.function.arguments})
                                </code>
                              ))}
                            </div>
                          )}
                          {r.error && (
                            <div className="mt-2 rounded bg-destructive/10 p-2 text-xs text-destructive">
                              {r.error}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </TabsContent>
              <TabsContent value="input" className="mt-3">
                <div className="space-y-2">
                  <Textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="向 Agent 提问..."
                    rows={6}
                  />
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => setInput("")}>
                      清空
                    </Button>
                    <Button
                      variant="default"
                      size="sm"
                      disabled={running || !input.trim()}
                      onClick={run}
                    >
                      {running ? (
                        "运行中..."
                      ) : (
                        <>
                          <Send className="h-3 w-3" /> 发送给 Agent
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-sm">
              <span className="flex items-center gap-2">
                <Cog className="h-4 w-4" /> 配置
              </span>
              {editing ? (
                <div className="flex gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (!agent) return;
                      setEditName(agent.name);
                      setEditModel(agent.model);
                      setEditMaxIter(agent.max_iterations);
                      setEditTemp(agent.temperature);
                      setEditSystemPrompt(agent.system_prompt);
                      setEditReflection(agent.enable_reflection);
                      setEditToolNames(agent.tool_names);
                      setEditing(false);
                    }}
                    disabled={saving}
                  >
                    取消
                  </Button>
                  <Button size="sm" onClick={saveEdit} disabled={saving}>
                    {saving ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Save className="h-3.5 w-3.5" />
                    )}
                    保存
                  </Button>
                </div>
              ) : (
                <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                  <Cog className="h-3.5 w-3.5" /> 编辑
                </Button>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">名称</Label>
              <Input
                value={editing ? editName : agent.name}
                readOnly={!editing}
                onChange={(e) => setEditName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">模型</Label>
              {editing ? (
                <Select value={editModel} onValueChange={setEditModel}>
                  <SelectTrigger className="font-mono">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelsQuery.data?.data.map((m) => (
                      <SelectItem key={m.id} value={m.id}>
                        {m.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input value={agent.model} readOnly className="font-mono" />
              )}
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label className="text-xs">最大迭代</Label>
                <Input
                  type="number"
                  min={1}
                  max={50}
                  value={editing ? editMaxIter : agent.max_iterations}
                  readOnly={!editing}
                  onChange={(e) => setEditMaxIter(Number(e.target.value) || 1)}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">温度</Label>
                {editing ? (
                  <div className="space-y-1">
                    <input
                      type="range"
                      min={0}
                      max={2}
                      step={0.05}
                      value={editTemp}
                      onChange={(e) => setEditTemp(Number(e.target.value))}
                      className="w-full accent-primary"
                    />
                    <p className="text-[10px] text-muted-foreground text-right">
                      {editTemp.toFixed(2)}
                    </p>
                  </div>
                ) : (
                  <Input value={agent.temperature.toFixed(2)} readOnly />
                )}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">系统提示词</Label>
              <Textarea
                value={editing ? editSystemPrompt : agent.system_prompt}
                readOnly={!editing}
                onChange={(e) => setEditSystemPrompt(e.target.value)}
                rows={4}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">启用反思</Label>
              <Switch
                checked={editing ? editReflection : agent.enable_reflection}
                onCheckedChange={setEditReflection}
                disabled={!editing}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">
                工具 ({editing ? editToolNames.length : agent.tool_names.length})
              </Label>
              {editing ? (
                <div className="max-h-40 overflow-y-auto rounded-md border border-border p-2">
                  <div className="grid grid-cols-1 gap-1">
                    {toolsQuery.data?.data.map((t) => (
                      <label
                        key={t.name}
                        className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 text-xs hover:bg-accent"
                      >
                        <input
                          type="checkbox"
                          checked={editToolNames.includes(t.name)}
                          onChange={(e) =>
                            setEditToolNames(
                              e.target.checked
                                ? [...editToolNames, t.name]
                                : editToolNames.filter((x) => x !== t.name),
                            )
                          }
                          className="h-3 w-3 accent-primary"
                        />
                        <span className="truncate font-mono">{t.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="flex flex-wrap gap-1">
                  {agent.tool_names.length === 0 ? (
                    <span className="text-xs text-muted-foreground">无</span>
                  ) : (
                    agent.tool_names.map((t) => (
                      <Badge key={t} variant="outline" className="font-mono text-[10px]">
                        {t}
                      </Badge>
                    ))
                  )}
                </div>
              )}
            </div>
            <Button
              className="w-full"
              variant="default"
              onClick={run}
              disabled={running || !input.trim()}
            >
              <Play className="h-4 w-4" /> {running ? "运行中..." : "运行"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
