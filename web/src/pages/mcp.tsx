("use client");

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
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import {
  type MCPHealthResponse,
  type MCPPreset,
  type MCPServer,
  type MCPTool,
  api,
} from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { formatRelativeTime } from "@/lib/utils";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Download,
  Plug2,
  Play,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Wrench,
  XCircle,
} from "lucide-react";
import * as React from "react";

export function MCPPage() {
  const [servers, setServers] = React.useState<MCPServer[]>([]);
  const [presets, setPresets] = React.useState<MCPPreset[]>([]);
  const [health, setHealth] = React.useState<MCPHealthResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState("");
  const [createOpen, setCreateOpen] = React.useState(false);
  const [invokeOpen, setInvokeOpen] = React.useState(false);
  const [selectedServer, setSelectedServer] = React.useState<MCPServer | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [serversRes, presetsRes, healthRes] = await Promise.all([
        api.listMCPServers(true),
        api.listMCPPresets(),
        api.mcpHealth(),
      ]);
      setServers(serversRes.data);
      setPresets(presetsRes.data);
      setHealth(healthRes);
    } catch (e) {
      reportError(e, "加载 MCP servers 失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  const filteredServers = servers.filter(
    (s) => !search || s.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="MCP 服务"
        description="Model Context Protocol — 接入外部工具生态(文件 / GitHub / Slack / DB ...)"
        icon={<Plug2 className="h-5 w-5" />}
        accent="cyan"
        actions={
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" /> 添加 Server
          </Button>
        }
      />

      {/* 健康卡片 */}
      {health && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard
            label="总 Server"
            value={health.total_servers}
            sub={`${health.builtin_servers} 内置 / ${health.user_servers} 自定义`}
            ok
          />
          <StatCard
            label="已激活"
            value={health.active_servers}
            sub={`${health.total_servers - health.active_servers} 未激活`}
            ok={health.active_servers > 0}
          />
          <StatCard
            label="错误"
            value={health.error_servers}
            sub={health.error_servers > 0 ? "需要排查" : "无错误"}
            ok={health.error_servers === 0}
          />
          <StatCard
            label="可用工具"
            value={health.total_tools}
            sub="跨所有 active server"
            ok
          />
        </div>
      )}

      <Tabs defaultValue="servers">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="servers">已注册 ({servers.length})</TabsTrigger>
          <TabsTrigger value="presets">预设 ({presets.length})</TabsTrigger>
          <TabsTrigger value="tools">工具</TabsTrigger>
        </TabsList>

        <TabsContent value="servers" className="mt-4 space-y-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="搜索 server"
              className="pl-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner className="h-5 w-5" />
            </div>
          ) : filteredServers.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/60 py-12 text-sm text-muted-foreground">
              <Plug2 className="mb-2 h-8 w-8 opacity-30" />
              还没有 MCP server
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {filteredServers.map((s) => (
                <MCPServerCard
                  key={s.id}
                  server={s}
                  onChange={load}
                  onInvoke={(srv) => {
                    setSelectedServer(srv);
                    setInvokeOpen(true);
                  }}
                />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="presets" className="mt-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {presets.map((p) => (
              <PresetCard key={p.id} preset={p} onInstalled={load} installed={servers.find((s) => s.id === p.id)} />
            ))}
          </div>
        </TabsContent>

        <TabsContent value="tools" className="mt-4">
          <AllMCPToolsList />
        </TabsContent>
      </Tabs>

      <CreateMCPServerDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          setCreateOpen(false);
          load();
        }}
      />

      {selectedServer && (
        <InvokeMCPDialog
          open={invokeOpen}
          onOpenChange={setInvokeOpen}
          server={selectedServer}
        />
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  ok,
}: {
  label: string;
  value: number;
  sub: string;
  ok: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="mt-1 text-2xl font-semibold">{value}</p>
        <p className={`mt-0.5 text-[10px] ${ok ? "text-success" : "text-destructive"}`}>
          {ok ? <CheckCircle2 className="mr-1 inline h-3 w-3" /> : <AlertCircle className="mr-1 inline h-3 w-3" />}
          {sub}
        </p>
      </CardContent>
    </Card>
  );
}

function MCPServerCard({
  server,
  onChange,
  onInvoke,
}: {
  server: MCPServer;
  onChange: () => void;
  onInvoke: (s: MCPServer) => void;
}) {
  const [busy, setBusy] = React.useState(false);
  const [toolsOpen, setToolsOpen] = React.useState(false);
  const [tools, setTools] = React.useState<MCPTool[]>(server.tools || []);
  const [toolsLoading, setToolsLoading] = React.useState(false);

  async function toggleEnabled() {
    setBusy(true);
    try {
      await api.updateMCPServer(server.id, { enabled: !server.enabled });
      toast.success(server.enabled ? "已停用" : "已启用");
      onChange();
    } catch (e) {
      reportError(e, "操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function deleteServer() {
    if (!confirm(`确认删除 MCP server "${server.name}"?`)) return;
    setBusy(true);
    try {
      await api.deleteMCPServer(server.id);
      toast.success("已删除");
      onChange();
    } catch (e) {
      reportError(e, "删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function refreshTools() {
    setToolsLoading(true);
    try {
      const res = await api.listMCPServerTools(server.id, true);
      setTools(res.data);
      toast.success(`刷新到 ${res.data.length} 个工具`);
    } catch (e) {
      reportError(e, "刷新工具失败");
    } finally {
      setToolsLoading(false);
    }
  }

  return (
    <>
      <Card>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className="text-base">{server.icon || "🔌"}</span>
                <p className="truncate text-sm font-medium">{server.name}</p>
                {server.is_builtin && (
                  <Badge variant="accent" className="text-[9px]">
                    内置
                  </Badge>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                {server.description || `${server.type} · ${server.command || server.url || "(无 command/url)"}`}
              </p>
              <div className="mt-2 flex flex-wrap gap-1">
                <Badge
                  variant={
                    server.status === "active" ? "default" : server.status === "error" ? "error" : "outline"
                  }
                  className="text-[10px]"
                >
                  {server.status === "active" && <CheckCircle2 className="mr-0.5 h-3 w-3" />}
                  {server.status === "error" && <XCircle className="mr-0.5 h-3 w-3" />}
                  {server.status}
                </Badge>
                <Badge variant="outline" className="text-[10px]">
                  {server.type}
                </Badge>
                <Badge variant="outline" className="text-[10px]">
                  {(server.tools || []).length || tools.length} 工具
                </Badge>
              </div>
              {server.last_error && (
                <p className="mt-1 truncate text-[10px] text-destructive">⚠ {server.last_error}</p>
              )}
              {server.last_check_at && (
                <p className="mt-0.5 text-[10px] text-muted-foreground">
                  上次检查:{formatRelativeTime(server.last_check_at)}
                </p>
              )}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Button size="icon" variant="ghost" disabled={busy} onClick={toggleEnabled}>
                {server.enabled ? (
                  <Power className="h-4 w-4 text-success" />
                ) : (
                  <PowerOff className="h-4 w-4 text-muted-foreground" />
                )}
              </Button>
              <Button size="icon" variant="ghost" onClick={() => setToolsOpen(true)}>
                <Wrench className="h-4 w-4 text-cyan-400" />
              </Button>
              {!server.is_builtin && (
                <Button size="icon" variant="ghost" disabled={busy} onClick={deleteServer}>
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              )}
            </div>
          </div>
          <div className="mt-2 flex gap-1">
            <Button
              size="sm"
              variant="outline"
              className="flex-1"
              disabled={!server.enabled}
              onClick={() => onInvoke(server)}
            >
              <Play className="h-3.5 w-3.5" /> 调用
            </Button>
            <Button size="sm" variant="ghost" onClick={refreshTools} disabled={toolsLoading}>
              {toolsLoading ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw className="h-3.5 w-3.5" />}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Dialog open={toolsOpen} onOpenChange={setToolsOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{server.name} · 工具列表</DialogTitle>
            <DialogDescription>
              {server.type} server · {tools.length} 个工具
            </DialogDescription>
          </DialogHeader>
          <ScrollArea className="max-h-[400px]">
            <div className="space-y-2">
              {tools.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  暂无工具缓存。点击刷新按钮主动从 server 拉取。
                </p>
              )}
              {tools.map((t) => (
                <div key={t.name} className="rounded-md border border-border/40 bg-muted/20 p-3 text-xs">
                  <p className="font-mono font-medium text-cyan-300">{t.name}</p>
                  <p className="mt-1 text-muted-foreground">{t.description}</p>
                  {Object.keys(t.inputSchema?.properties || {}).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {Object.entries(t.inputSchema.properties).map(([k, v]) => (
                        <Badge key={k} variant="outline" className="text-[9px]">
                          {k}: {(v as { type?: string }).type || "any"}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setToolsOpen(false)}>
              关闭
            </Button>
            <Button onClick={refreshTools} disabled={toolsLoading}>
              {toolsLoading ? <Spinner className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
              刷新
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function PresetCard({
  preset,
  onInstalled,
  installed,
}: {
  preset: MCPPreset;
  onInstalled: () => void;
  installed?: MCPServer;
}) {
  const [busy, setBusy] = React.useState(false);
  const isInstalled = !!installed && installed.enabled;

  async function install() {
    setBusy(true);
    try {
      await api.installMCPPreset(preset.id);
      toast.success("已安装", { description: preset.name });
      onInstalled();
    } catch (e) {
      reportError(e, "安装失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="text-base">{preset.icon}</span>
              <p className="truncate text-sm font-medium">{preset.name}</p>
            </div>
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{preset.description}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              <Badge variant="outline" className="text-[10px]">
                {preset.type}
              </Badge>
              {preset.tools && (
                <Badge variant="accent" className="text-[10px]">
                  {preset.tools.length} 工具
                </Badge>
              )}
            </div>
            <p className="mt-1 truncate font-mono text-[10px] text-muted-foreground">
              {preset.command} {preset.args?.slice(0, 2).join(" ")} ...
            </p>
          </div>
        </div>
        <Button
          size="sm"
          variant={isInstalled ? "outline" : "default"}
          className="mt-2 w-full"
          onClick={install}
          disabled={busy}
        >
          {busy ? <Spinner className="h-3.5 w-3.5" /> : isInstalled ? <Check className="h-3.5 w-3.5" /> : <Download className="h-3.5 w-3.5" />}
          {isInstalled ? "已启用" : "一键启用"}
        </Button>
      </CardContent>
    </Card>
  );
}

function AllMCPToolsList() {
  const [tools, setTools] = React.useState<MCPTool[]>([]);
  const [loading, setLoading] = React.useState(true);

  async function load() {
    setLoading(true);
    try {
      const res = await api.listAllMCPTools();
      setTools(res.data);
    } catch (e) {
      reportError(e, "加载失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  if (loading)
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner className="h-5 w-5" />
      </div>
    );

  if (tools.length === 0)
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/60 py-12 text-sm text-muted-foreground">
        <Wrench className="mb-2 h-8 w-8 opacity-30" />
        暂无 active server 的工具
      </div>
    );

  return (
    <div className="space-y-2">
      {tools.map((t) => (
        <div
          key={`${t.server_id}-${t.name}`}
          className="rounded-md border border-border/40 bg-muted/20 p-3 text-xs"
        >
          <div className="flex items-center gap-2">
            <Badge variant="accent" className="text-[10px]">
              {t.server_name}
            </Badge>
            <p className="font-mono font-medium text-cyan-300">{t.name}</p>
          </div>
          <p className="mt-1 text-muted-foreground">{t.description}</p>
          {Object.keys(t.inputSchema?.properties || {}).length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {Object.entries(t.inputSchema.properties).map(([k, v]) => (
                <Badge key={k} variant="outline" className="text-[9px]">
                  {k}: {(v as { type?: string }).type || "any"}
                </Badge>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function CreateMCPServerDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  onCreated: () => void;
}) {
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");
  const [type, setType] = React.useState<"stdio" | "sse" | "http">("stdio");
  const [command, setCommand] = React.useState("");
  const [args, setArgs] = React.useState("");
  const [url, setUrl] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  async function create() {
    if (!name.trim()) {
      toast.error("请填写名称");
      return;
    }
    setBusy(true);
    try {
      await api.createMCPServer({
        name: name.trim(),
        description: description.trim(),
        type,
        command,
        args: args
          .split(/\s+/)
          .map((s) => s.trim())
          .filter(Boolean),
        url,
        enabled: true,
      });
      toast.success("已创建", { description: name });
      setName("");
      setDescription("");
      setCommand("");
      setArgs("");
      setUrl("");
      onCreated();
    } catch (e) {
      reportError(e, "创建失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>注册 MCP Server</DialogTitle>
          <DialogDescription>填写连接信息,启用后 LLM 即可调用其工具</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">名称 *</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-mcp-server" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">描述</Label>
            <Input value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">类型</Label>
            <Select value={type} onValueChange={(v) => setType(v as "stdio" | "sse" | "http")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="stdio">stdio (本地子进程)</SelectItem>
                <SelectItem value="http">http (一次性调用)</SelectItem>
                <SelectItem value="sse">sse (长连接)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {type === "stdio" && (
            <>
              <div className="space-y-1.5">
                <Label className="text-xs">Command</Label>
                <Input
                  value={command}
                  onChange={(e) => setCommand(e.target.value)}
                  placeholder="npx"
                  className="font-mono"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Args (空格分隔)</Label>
                <Textarea
                  rows={2}
                  value={args}
                  onChange={(e) => setArgs(e.target.value)}
                  placeholder="-y @modelcontextprotocol/server-filesystem /tmp"
                  className="font-mono text-xs"
                />
              </div>
            </>
          )}
          {(type === "http" || type === "sse") && (
            <div className="space-y-1.5">
              <Label className="text-xs">URL</Label>
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/mcp"
                className="font-mono"
              />
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={create} disabled={busy}>
            {busy ? <Spinner className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function InvokeMCPDialog({
  open,
  onOpenChange,
  server,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  server: MCPServer;
}) {
  const [tools, setTools] = React.useState<MCPTool[]>(server.tools || []);
  const [selectedTool, setSelectedTool] = React.useState<MCPTool | null>(null);
  const [argsJson, setArgsJson] = React.useState("{}");
  const [result, setResult] = React.useState<unknown>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      // 拉一次工具
      api
        .listMCPServerTools(server.id, false)
        .then((r) => {
          setTools(r.data);
          if (r.data.length > 0) setSelectedTool(r.data[0]);
        })
        .catch((e) => reportError(e, "加载工具失败"));
      setResult(null);
      setError(null);
    }
  }, [open, server.id]);

  React.useEffect(() => {
    if (selectedTool) {
      // 默认参数模板
      const schema = selectedTool.inputSchema || {};
      const def: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(schema.properties || {})) {
        const ty = (v as { type?: string }).type;
        if (ty === "string") def[k] = "";
        else if (ty === "number" || ty === "integer") def[k] = 0;
        else if (ty === "boolean") def[k] = false;
        else if (ty === "array") def[k] = [];
        else def[k] = null;
      }
      setArgsJson(JSON.stringify(def, null, 2));
    }
  }, [selectedTool?.name]);

  async function run() {
    if (!selectedTool) return;
    setBusy(true);
    setError(null);
    setResult(null);
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(argsJson || "{}");
    } catch (e) {
      setError(`参数 JSON 解析失败: ${e instanceof Error ? e.message : e}`);
      setBusy(false);
      return;
    }
    try {
      const res = await api.invokeMCPTool({
        server_id: server.id,
        tool_name: selectedTool.name,
        arguments: parsed,
        timeout: 30,
      });
      if (res.success) {
        setResult(res.content);
        toast.success("调用成功", { description: `${res.duration_ms}ms · ${res.trace_id}` });
      } else {
        setError(res.error || "unknown error");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>调用 {server.name}</DialogTitle>
          <DialogDescription>{server.description}</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">选择工具</Label>
            <Select
              value={selectedTool?.name || ""}
              onValueChange={(v) => {
                const t = tools.find((x) => x.name === v);
                setSelectedTool(t || null);
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择工具" />
              </SelectTrigger>
              <SelectContent>
                {tools.map((t) => (
                  <SelectItem key={t.name} value={t.name}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {selectedTool && (
            <>
              <p className="text-xs text-muted-foreground">{selectedTool.description}</p>
              <div className="space-y-1.5">
                <Label className="text-xs">参数 (JSON)</Label>
                <Textarea
                  rows={6}
                  value={argsJson}
                  onChange={(e) => setArgsJson(e.target.value)}
                  className="font-mono text-xs"
                />
              </div>
            </>
          )}
          <Button onClick={run} disabled={busy || !selectedTool} className="w-full">
            {busy ? <Spinner className="h-4 w-4" /> : <Sparkles className="h-4 w-4" />}
            执行
          </Button>
          {error && (
            <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
              <AlertCircle className="mr-1 inline h-3 w-3" />
              {error}
            </div>
          )}
          {result !== null && (
            <div className="space-y-1.5">
              <Label className="text-xs">结果</Label>
              <pre className="max-h-60 overflow-auto rounded-md bg-muted/30 p-3 text-xs">
                {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
