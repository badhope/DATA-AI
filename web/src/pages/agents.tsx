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
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { getClient } from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { AGENT_TEMPLATES } from "@/lib/templates";
import type {
	AgentConfig,
	AgentCreateRequest,
	ModelsResponse,
	ToolsResponse,
} from "@/lib/types/api";
import { cn, formatRelativeTime } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
	Activity,
	Bot,
	Brain,
	CheckCircle2,
	ChevronRight,
	Circle,
	Loader2,
	Plus,
	Sparkles,
	Wrench,
	XCircle,
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router-dom";

export type AgentStatus = NonNullable<AgentConfig["status"]>;

const STATUS_META: Record<AgentStatus, { label: string; color: string; icon: React.ReactNode }> = {
  idle: { label: "空闲", color: "bg-muted-foreground", icon: <Circle className="h-3 w-3" /> },
  thinking: {
    label: "思考中",
    color: "bg-primary",
    icon: <Brain className="h-3 w-3 animate-pulse" />,
  },
  executing: {
    label: "执行工具",
    color: "bg-warning",
    icon: <Wrench className="h-3 w-3 animate-pulse" />,
  },
  streaming: {
    label: "流式输出",
    color: "bg-info",
    icon: <Activity className="h-3 w-3 animate-pulse" />,
  },
  finished: {
    label: "已完成",
    color: "bg-success",
    icon: <CheckCircle2 className="h-3 w-3" />,
  },
  error: { label: "错误", color: "bg-destructive", icon: <XCircle className="h-3 w-3" /> },
};

export function AgentsPage() {
  const [agents, setAgents] = React.useState<AgentConfig[]>([]);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(true);

  const modelsQuery = useQuery<ModelsResponse>({
    queryKey: ["models"],
    queryFn: () => getClient().listModels(),
  });
  const toolsQuery = useQuery<ToolsResponse>({
    queryKey: ["tools"],
    queryFn: () => getClient().listTools(),
  });

  async function load() {
    setLoading(true);
    try {
      const res = await getClient().listAgents();
      setAgents(res.data);
    } catch (e) {
      reportError(e, "加载智能体");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  const createAgent = async (data: AgentCreateRequest) => {
    try {
      const res = await getClient().createAgent(data);
      toast.success("智能体已创建", { description: res.name });
      setCreateOpen(false);
      await load();
    } catch (e) {
      reportError(e, "创建智能体");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="智能体"
        description="配置独立的 AI 智能体，绑定模型、工具与系统提示词"
        icon={<Bot className="h-5 w-5" />}
        actions={
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button variant="default">
                <Plus className="h-4 w-4" /> 新建智能体
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>新建智能体</DialogTitle>
                <DialogDescription>配置名称、模型、提示词与可用工具</DialogDescription>
              </DialogHeader>
              <CreateAgentDialog
                models={modelsQuery.data?.data.map((m) => m.id) ?? []}
                tools={toolsQuery.data?.data.map((t) => t.name) ?? []}
                onCreate={createAgent}
              />
            </DialogContent>
          </Dialog>
        }
      />

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Spinner className="h-5 w-5" />
        </div>
      ) : agents.length === 0 ? (
        <EmptyState
          icon={<Bot className="h-6 w-6" />}
          title="还没有智能体"
          description="创建一个新的智能体来开始自动化任务"
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((a, i) => (
            <motion.div
              key={a.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <Link to={`/agents/${a.id}`}>
                <Card className="group h-full transition-all hover:border-primary/40">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted text-primary ring-1 ring-border">
                          <Bot className="h-5 w-5" />
                        </div>
                        <div className="min-w-0">
                          <CardTitle className="truncate text-base">{a.name}</CardTitle>
                          <p className="truncate text-xs text-muted-foreground">{a.model}</p>
                        </div>
                      </div>
                      {a.status && <StatusBadge status={a.status} />}
                    </div>
                  </CardHeader>
                  <CardContent>
                    {a.description && (
                      <p className="line-clamp-2 text-xs text-muted-foreground">{a.description}</p>
                    )}
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                      {a.system_prompt || "无系统提示词"}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1">
                      {a.tool_names.slice(0, 3).map((t) => (
                        <Badge key={t} variant="outline" className="font-mono text-[10px]">
                          {t}
                        </Badge>
                      ))}
                      {a.tool_names.length > 3 && (
                        <Badge variant="outline" className="text-[10px]">
                          +{a.tool_names.length - 3}
                        </Badge>
                      )}
                    </div>
                    <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                      <span>
                        最大 {a.max_iterations} 轮迭代 · 温度 {a.temperature.toFixed(2)}
                      </span>
                      <span>{formatRelativeTime(a.updated_at)}</span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-1" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

export function StatusBadge({ status }: { status: AgentStatus }) {
  const meta = STATUS_META[status];
  return (
    <Badge variant="outline" className="gap-1.5">
      <span className={cn("h-1.5 w-1.5 rounded-full", meta.color)} />
      <span className="flex items-center gap-1 text-[10px]">
        {meta.icon}
        {meta.label}
      </span>
    </Badge>
  );
}

function CreateAgentDialog({
	models,
	tools,
	onCreate,
}: {
	models: string[];
	tools: string[];
	onCreate: (a: AgentCreateRequest) => void;
}) {
	const [name, setName] = React.useState("新智能体");
	const [description, setDescription] = React.useState("");
	const [model, setModel] = React.useState(models[0] ?? "gpt-4");
	const [systemPrompt, setSystemPrompt] = React.useState("");
	const [maxIterations, setMaxIterations] = React.useState(10);
	const [temperature, setTemperature] = React.useState(0.7);
	const [enableReflection, setEnableReflection] = React.useState(true);
	const [selectedTools, setSelectedTools] = React.useState<string[]>([]);
	const [templateId, setTemplateId] = React.useState<string>("");

	React.useEffect(() => {
		if (!model && models[0]) setModel(models[0]);
	}, [models, model]);

	// 加载模板
	const applyTemplate = (tid: string) => {
		setTemplateId(tid);
		const t = AGENT_TEMPLATES.find((x) => x.id === tid);
		if (!t) return;
		const built = t.build(model || models[0] || "gpt-4");
		setName(built.name);
		setDescription(built.description || "");
		setSystemPrompt(built.system_prompt);
		setMaxIterations(built.max_iterations);
		setTemperature(built.temperature);
		setEnableReflection(built.enable_reflection);
		setSelectedTools(built.tool_names);
		toast.success("已加载模板", { description: `${t.emoji} ${t.name}` });
	};

	// AI 自动生成系统提示词
	const aiPrompt = React.useMemo(() => {
		return `请为一个 AI 智能体写一段高质量的 system_prompt。

智能体名称：${name}
${description ? `智能体描述：${description}\n` : ""}
要求：
1. 用中文；
2. 明确角色定位（你是一位...）；
3. 列出 3-5 条具体行为规则；
4. 包含输出格式约束（风格 / 长度 / 语言）；
5. 直接输出 prompt 文本，不要加解释或 markdown 代码块。`;
	}, [name, description]);

	const aiSystemHint = React.useMemo(
		() =>
			"你是一位 prompt engineer，专门为 AI 智能体设计 system_prompt。要求：结构化、约束清晰、可直接复制使用。",
		[],
	);

	return (
		<>
			<DialogHeader>
				<DialogTitle>新建智能体</DialogTitle>
				<DialogDescription>选模板或从零开始，下方用 AI 帮填</DialogDescription>
			</DialogHeader>

			<div className="grid gap-3 py-2">
				{/* 模板预设 */}
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">
						<Sparkles className="mr-1 inline h-3 w-3" /> 快速模板
					</Label>
					<div className="grid grid-cols-3 gap-2">
						{AGENT_TEMPLATES.map((t) => (
							<button
								key={t.id}
								type="button"
								onClick={() => applyTemplate(t.id)}
								className={cn(
									"flex flex-col items-start gap-1 rounded-md border border-border bg-card p-2 text-left transition-all hover:border-primary/40 hover:bg-primary/5",
									templateId === t.id && "border-primary bg-primary/10 ring-1 ring-primary/30",
								)}
							>
								<div className="flex items-center gap-1.5">
									<span className="text-base">{t.emoji}</span>
									<span className="text-xs font-medium">{t.name}</span>
								</div>
								<p className="line-clamp-1 text-[10px] text-muted-foreground">{t.description}</p>
							</button>
						))}
					</div>
				</div>

				{/* 名称 + 描述 */}
				<div className="grid grid-cols-2 gap-3">
					<div className="space-y-1.5">
						<Label className="text-xs">名称</Label>
						<Input value={name} onChange={(e) => setName(e.target.value)} />
					</div>
					<div className="space-y-1.5">
						<Label className="text-xs">描述</Label>
						<Input
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="一句话说明这个智能体"
						/>
					</div>
				</div>

				{/* 模型 + 迭代 */}
				<div className="grid grid-cols-3 gap-3">
					<div className="col-span-2 space-y-1.5">
						<Label className="text-xs">模型</Label>
						<Select value={model} onValueChange={setModel}>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								{models.length === 0 ? (
									<SelectItem value={model}>{model}</SelectItem>
								) : (
									models.map((m) => (
										<SelectItem key={m} value={m}>
											{m}
										</SelectItem>
									))
								)}
							</SelectContent>
						</Select>
					</div>
					<div className="space-y-1.5">
						<Label className="text-xs">最大迭代</Label>
						<Input
							type="number"
							min={1}
							max={50}
							value={maxIterations}
							onChange={(e) => setMaxIterations(Number(e.target.value) || 1)}
						/>
					</div>
				</div>

				{/* 系统提示词 + AI 帮填 */}
				<div className="space-y-1.5">
					<div className="flex items-center justify-between">
						<Label className="text-xs">系统提示词</Label>
						<AIGenerateButton
							prompt={aiPrompt}
							systemHint={aiSystemHint}
							onStream={(text) => setSystemPrompt(text)}
							label="AI 帮填"
						/>
					</div>
					<Textarea
						value={systemPrompt}
						onChange={(e) => setSystemPrompt(e.target.value)}
						rows={5}
						placeholder="你是一个...（点击右上「AI 帮填」自动生成）"
					/>
				</div>

				{/* 温度 + 反思 */}
				<div className="grid grid-cols-2 gap-3">
					<div className="space-y-1.5">
						<Label className="text-xs">温度 ({temperature.toFixed(2)})</Label>
						<input
							type="range"
							min={0}
							max={2}
							step={0.05}
							value={temperature}
							onChange={(e) => setTemperature(Number(e.target.value))}
							className="w-full accent-primary"
						/>
					</div>
					<div className="flex items-center justify-between rounded-md border border-border p-2">
						<div>
							<Label className="text-xs">启用反思</Label>
							<p className="text-[10px] text-muted-foreground">自评改进</p>
						</div>
						<Switch checked={enableReflection} onCheckedChange={setEnableReflection} />
					</div>
				</div>

				{/* 工具 */}
				<div className="space-y-1.5">
					<Label className="text-xs">可用工具 ({selectedTools.length}/{tools.length})</Label>
					<div className="max-h-32 overflow-y-auto rounded-md border border-border p-2">
						{tools.length === 0 ? (
							<p className="py-2 text-center text-xs text-muted-foreground">没有可用工具</p>
						) : (
							<div className="grid grid-cols-2 gap-1">
								{tools.map((t) => (
									<label
										key={t}
										className="flex cursor-pointer items-center gap-1.5 rounded px-1 py-0.5 text-xs hover:bg-accent"
									>
										<input
											type="checkbox"
											checked={selectedTools.includes(t)}
											onChange={(e) =>
												setSelectedTools(
													e.target.checked
														? [...selectedTools, t]
														: selectedTools.filter((x) => x !== t),
												)
											}
											className="h-3 w-3 accent-primary"
										/>
										<span className="truncate font-mono">{t}</span>
									</label>
								))}
							</div>
						)}
					</div>
				</div>
			</div>

			<DialogFooter>
				<Button
					variant="outline"
					onClick={() => {
						setName("新智能体");
						setDescription("");
						setSystemPrompt("");
						setMaxIterations(10);
						setTemperature(0.7);
						setEnableReflection(true);
						setSelectedTools([]);
						setTemplateId("");
					}}
				>
					重置
				</Button>
				<Button
					variant="default"
					disabled={!name.trim() || !model}
					onClick={() => {
						const finalModel = model || models[0] || "gpt-4";
						onCreate({
							name: name.trim(),
							description: description || undefined,
							model: finalModel,
							system_prompt: systemPrompt,
							tool_names: selectedTools,
							max_iterations: maxIterations,
							temperature,
							enable_reflection: enableReflection,
						});
					}}
				>
					创建
				</Button>
			</DialogFooter>
		</>
	);
}
