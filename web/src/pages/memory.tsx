"use client";

import { AIGenerateButton } from "@/components/shared/ai-generate-button";
import { EmptyState } from "@/components/shared/empty-state";
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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import {
  type MemoriesListResponse,
  type MemoryCreateRequest,
  type MemoryItem,
  type MemoryType,
  api,
} from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { cn, formatRelativeTime } from "@/lib/utils";
import { motion } from "framer-motion";
import {
  Brain,
  Clock,
  Database,
  Filter,
  Lightbulb,
  ListChecks,
  Pin,
  Plus,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import * as React from "react";

const TYPE_META: Record<
  MemoryType,
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string; bg: string }
> = {
  short_term: {
    label: "短期",
    icon: Clock,
    color: "text-warning",
    bg: "bg-muted",
  },
  long_term: {
    label: "长期",
    icon: Database,
    color: "text-info",
    bg: "bg-muted",
  },
  episodic: {
    label: "情景",
    icon: ListChecks,
    color: "text-success",
    bg: "bg-muted",
  },
  semantic: {
    label: "语义",
    icon: Lightbulb,
    color: "text-primary",
    bg: "bg-muted",
  },
};

export function MemoryPage() {
  const [memories, setMemories] = React.useState<MemoryItem[]>([]);
  const [stats, setStats] = React.useState<Record<string, number>>({});
  const [loading, setLoading] = React.useState(true);
  const [type, setType] = React.useState<MemoryType | "_all">("_all");
  const [query, setQuery] = React.useState("");
  const [openCreate, setOpenCreate] = React.useState(false);

  async function load() {
    setLoading(true);
    try {
      const res: MemoriesListResponse = await api.listMemories({
        type: type === "_all" ? undefined : type,
        q: query || undefined,
      });
      setMemories(res.data);
      setStats(res.stats);
    } catch (e) {
      reportError(e, "加载记忆");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, [type]);

  async function create(payload: MemoryCreateRequest) {
    try {
      await api.createMemory(payload);
      toast.success("已添加", { description: payload.content.slice(0, 30) });
      setOpenCreate(false);
      await load();
    } catch (e) {
      reportError(e, "创建记忆");
    }
  }

  async function togglePin(m: MemoryItem) {
    try {
      await api.updateMemory(m.id, { pinned: !m.pinned });
      await load();
    } catch (e) {
      reportError(e, "更新记忆");
    }
  }

  async function remove(m: MemoryItem) {
    if (!confirm(`确认删除记忆 "(${m.content.slice(0, 30)})" 吗？`)) return;
    try {
      await api.deleteMemory(m.id);
      toast.success("已删除");
      await load();
    } catch (e) {
      reportError(e, "删除记忆");
    }
  }

  const total = Object.values(stats).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="记忆系统"
        description="短期 / 长期 / 情景 / 语义 四类记忆管理"
        icon={<Brain className="h-5 w-5" />}
        actions={
          <Dialog open={openCreate} onOpenChange={setOpenCreate}>
            <DialogTrigger asChild>
              <Button variant="default">
                <Plus className="h-4 w-4" /> 新建记忆
              </Button>
            </DialogTrigger>
            <DialogContent>
              <CreateMemoryForm onCreate={create} />
            </DialogContent>
          </Dialog>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {(Object.keys(TYPE_META) as MemoryType[]).map((t) => {
          const meta = TYPE_META[t];
          const Icon = meta.icon;
          return (
            <Card
              key={t}
              className={cn(
                "cursor-pointer transition-all hover:border-primary/40",
                type === t && "border-primary/60",
              )}
              onClick={() => setType(type === t ? "_all" : t)}
            >
              <CardContent className="p-4">
                <div
                  className={cn(
                    "mb-2 inline-flex h-9 w-9 items-center justify-center rounded-md ring-1 ring-border",
                    meta.bg,
                  )}
                >
                  <Icon className={cn("h-4 w-4", meta.color)} />
                </div>
                <p className="text-2xl font-semibold">{stats[t] || 0}</p>
                <p className="text-xs text-muted-foreground">{meta.label}记忆</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="搜索内容或标签..."
            className="pl-8"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
          />
        </div>
        <Button variant="outline" onClick={load}>
          <Filter className="h-4 w-4" /> 搜索
        </Button>
        {type !== "_all" && (
          <Button variant="ghost" onClick={() => setType("_all")}>
            显示全部
          </Button>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Spinner className="h-5 w-5" />
        </div>
      ) : memories.length === 0 ? (
        <EmptyState
          icon={<Brain className="h-6 w-6" />}
          title={total === 0 ? "记忆库为空" : "没有匹配的记忆"}
          description={
            total === 0 ? "添加第一条记忆，让 Agent 记住上下文" : "尝试不同的搜索或筛选条件"
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {memories.map((m, i) => {
            const meta = TYPE_META[m.type];
            const Icon = meta.icon;
            return (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i, 10) * 0.03 }}
              >
                <Card
                  className={cn(
                    "group h-full transition-all hover:border-primary/40",
                    m.pinned && "border-warning/40",
                  )}
                >
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div
                        className={cn(
                          "inline-flex h-7 w-7 items-center justify-center rounded-md ring-1 ring-border",
                          meta.bg,
                        )}
                      >
                        <Icon className={cn("h-3.5 w-3.5", meta.color)} />
                      </div>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="icon" onClick={() => togglePin(m)}>
                          <Pin
                            className={cn(
                              "h-3.5 w-3.5",
                              m.pinned ? "fill-warning text-warning" : "text-muted-foreground",
                            )}
                          />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => remove(m)}>
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      </div>
                    </div>
                    <p className="mt-3 line-clamp-3 text-sm">{m.content}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-1.5">
                      <Badge variant="outline" className="text-[10px]">
                        {meta.label}
                      </Badge>
                      <Badge variant="accent" className="text-[10px]">
                        重要性 {m.importance.toFixed(1)}
                      </Badge>
                      {m.tags.slice(0, 2).map((t) => (
                        <Badge key={t} variant="outline" className="text-[10px]">
                          #{t}
                        </Badge>
                      ))}
                    </div>
                    <p className="mt-2 text-[10px] text-muted-foreground">
                      {formatRelativeTime(m.created_at)}
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function CreateMemoryForm({ onCreate }: { onCreate: (req: MemoryCreateRequest) => void }) {
	const [type, setType] = React.useState<MemoryType>("semantic");
	const [content, setContent] = React.useState("");
	const [importance, setImportance] = React.useState(0.5);
	const [tags, setTags] = React.useState("");
	const [pinned, setPinned] = React.useState(false);

	const MEMORY_TEMPLATES: Record<MemoryType, { emoji: string; name: string; text: string; tags: string[] }[]> = {
		short_term: [
			{ emoji: "💬", name: "用户偏好", text: "用户喜欢简洁回答，不喜欢冗长解释。", tags: ["preference"] },
			{ emoji: "📍", name: "当前任务", text: "当前正在为用户实现 X 功能，进度 50%。", tags: ["task", "context"] },
		],
		long_term: [
			{ emoji: "📚", name: "领域知识", text: "DATA-AI 是 AI 智能体编排平台，支持 RAG / 团队 / 沙箱。", tags: ["knowledge", "platform"] },
			{ emoji: "⚙️", name: "配置信息", text: "后端默认模型：qwen-turbo（qwen-plus-2025-01-25）。", tags: ["config"] },
		],
		episodic: [
			{ emoji: "🎬", name: "事件记录", text: "用户于今天 10:30 提出对话界面优化需求。", tags: ["event"] },
		],
		semantic: [
			{ emoji: "🔗", name: "概念关联", text: "Agent 与 Skill 的关系：Agent 通过 tool_names 引用 Skill。", tags: ["concept"] },
		],
	};

	const templates = MEMORY_TEMPLATES[type] || [];

	function applyTemplate(text: string, tgs: string[]) {
		setContent(text);
		setTags(tgs.join(", "));
		toast.success("已加载模板");
	}

	const aiPrompt = React.useMemo(
		() =>
			`请根据以下主题写一条 1-2 句话的简洁记忆。

主题：${content || "未指定"}
记忆类型：${type}
要求：精炼、可直接复用，不要加 markdown / 解释。`,
		[content, type],
	);

	function submit() {
		if (!content.trim()) {
			toast.error("请输入记忆内容");
			return;
		}
		onCreate({
			type,
			content: content.trim(),
			importance,
			tags: tags
				.split(",")
				.map((t) => t.trim())
				.filter(Boolean),
			pinned,
		});
		setContent("");
		setTags("");
	}

	return (
		<>
			<DialogHeader>
				<DialogTitle>新建记忆</DialogTitle>
				<DialogDescription>选模板或 AI 帮写</DialogDescription>
			</DialogHeader>
			<div className="space-y-3">
				<div className="space-y-1.5">
					<Label className="text-xs">类型</Label>
					<Select value={type} onValueChange={(v) => setType(v as MemoryType)}>
						<SelectTrigger>
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							<SelectItem value="short_term">短期</SelectItem>
							<SelectItem value="long_term">长期</SelectItem>
							<SelectItem value="episodic">情景</SelectItem>
							<SelectItem value="semantic">语义</SelectItem>
						</SelectContent>
					</Select>
				</div>

				{/* 模板快捷 */}
				{templates.length > 0 && (
					<div className="space-y-1.5">
						<Label className="text-xs text-muted-foreground">
							<Sparkles className="mr-1 inline h-3 w-3" /> 快捷模板
						</Label>
						<div className="grid grid-cols-2 gap-1.5">
							{templates.map((t, i) => (
								<button
									key={i}
									type="button"
									onClick={() => applyTemplate(t.text, t.tags)}
									className="flex items-center gap-1.5 rounded border border-border bg-card p-1.5 text-left text-[11px] transition-all hover:border-primary/40 hover:bg-primary/5"
								>
									<span>{t.emoji}</span>
									<span className="font-medium">{t.name}</span>
								</button>
							))}
						</div>
					</div>
				)}

				<div className="space-y-1.5">
					<div className="flex items-center justify-between">
						<Label className="text-xs">内容</Label>
						<AIGenerateButton
							prompt={aiPrompt}
							onStream={(text) => setContent(text)}
							label="AI 帮写"
						/>
					</div>
					<Textarea rows={4} value={content} onChange={(e) => setContent(e.target.value)} />
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs">重要性 ({importance.toFixed(2)})</Label>
					<input
						type="range"
						min={0}
						max={1}
						step={0.05}
						value={importance}
						onChange={(e) => setImportance(Number.parseFloat(e.target.value))}
						className="w-full"
					/>
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs">标签（逗号分隔）</Label>
					<Input value={tags} onChange={(e) => setTags(e.target.value)} />
				</div>
				<div className="flex items-center gap-2">
					<input
						type="checkbox"
						id="pin"
						checked={pinned}
						onChange={(e) => setPinned(e.target.checked)}
						className="h-4 w-4"
					/>
					<Label htmlFor="pin" className="text-xs">
						置顶
					</Label>
				</div>
			</div>
			<DialogFooter>
				<Button onClick={submit}>
					<Plus className="h-4 w-4" /> 创建
				</Button>
			</DialogFooter>
		</>
	);
}
