import { reportError } from "@/lib/errors";
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
  DialogTrigger,
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
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { type SandboxInfo, api } from "@/lib/api/client";
import { formatRelativeTime } from "@/lib/utils";
import { Box, ChevronRight, Clock, Cpu, MemoryStick, Play, Plus, Trash2, Wifi } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router-dom";

export function SandboxPage() {
  const navigate = useNavigate();
  const [items, setItems] = React.useState<SandboxInfo[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [type, setType] = React.useState<"local" | "docker">("local");
  const [timeout, setTimeout_] = React.useState(30);
  const [creating, setCreating] = React.useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await api.listSandboxes();
      setItems(res.data);
    } catch (e) {
      reportError(e, "加载沙箱失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  async function create() {
    if (!name.trim()) {
      toast.error("请输入沙箱名称");
      return;
    }
    setCreating(true);
    try {
      const res = await api.createSandbox({
        name: name.trim(),
        type,
        timeout,
        memory: 512,
        cpu: 50,
        network: true,
      });
      toast.success("沙箱已创建", { description: res.name });
      setOpen(false);
      setName("");
      await load();
      navigate(`/sandbox/${res.id}`);
    } catch (e) {
      reportError(e, "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function remove(id: string, sbName: string) {
    if (!confirm(`确认删除沙箱 "${sbName}" 吗？`)) return;
    try {
      await api.deleteSandbox(id);
      toast.success("已删除", { description: sbName });
      await load();
    } catch (e) {
      reportError(e, "删除失败");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="代码沙箱"
        description="安全执行 Python / JS / Bash · 文件管理 · 快照"
        icon={<Box className="h-5 w-5" />}
        accent="amber"
      />

      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" /> 新建沙箱
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>新建沙箱</DialogTitle>
              <DialogDescription>创建一个隔离的代码执行环境</DialogDescription>
            </DialogHeader>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label className="text-xs">名称</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="my-sandbox"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">类型</Label>
                <Select value={type} onValueChange={(v) => setType(v as typeof type)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="local">本地（受限 Python）</SelectItem>
                    <SelectItem value="docker">Docker 容器</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">默认超时（秒）</Label>
                <Input
                  type="number"
                  min={5}
                  max={3600}
                  value={timeout}
                  onChange={(e) => setTimeout_(Number.parseInt(e.target.value) || 30)}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="ghost" onClick={() => setOpen(false)}>
                取消
              </Button>
              <Button onClick={create} disabled={creating}>
                {creating ? <Spinner className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                创建
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Spinner className="h-5 w-5" />
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/60 py-12 text-sm text-muted-foreground">
          <Box className="mb-2 h-8 w-8 opacity-30" />
          还没有沙箱，点击右上角创建
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((s) => (
            <Card
              key={s.id}
              className="cursor-pointer transition-colors hover:border-primary/40"
              onClick={() => navigate(`/sandbox/${s.id}`)}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant={s.status === "running" ? "success" : "secondary"}>
                        {s.status}
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        {s.type}
                      </Badge>
                    </div>
                    <p className="mt-2 truncate text-sm font-medium">{s.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {s.image || "default"} · 创建于 {formatRelativeTime(s.created_at)}
                    </p>
                    <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Cpu className="h-3 w-3" /> {s.cpu || 0}%
                      </span>
                      <span className="flex items-center gap-1">
                        <MemoryStick className="h-3 w-3" /> {s.memory || 0}MB
                      </span>
                      {s.network && (
                        <span className="flex items-center gap-1">
                          <Wifi className="h-3 w-3" /> 网络
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" /> {s.uptime}s
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/sandbox/${s.id}`);
                      }}
                    >
                      <Play className="h-4 w-4 text-primary" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => {
                        e.stopPropagation();
                        remove(s.id, s.name);
                      }}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
