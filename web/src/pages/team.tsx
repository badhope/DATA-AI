import { AIGenerateButton } from "@/components/shared/ai-generate-button";
import { reportError } from "@/lib/errors";
("use client");

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
  type ConsensusMethod,
  type TeamConfig,
  type TeamCreateRequest,
  type TeamMode,
  type TeamsListResponse,
  api,
} from "@/lib/api/client";
import { TEAM_TEMPLATES } from "@/lib/templates";
import { cn, formatRelativeTime } from "@/lib/utils";
import { motion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Crown,
  GitBranch,
  Network,
  Plus,
  Sparkles,
  Swords,
  Trash2,
  Users,
  Vote,
  Zap,
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router-dom";

const MODE_META = {
  collaboration: {
    label: "协作",
    icon: Users,
    color: "bg-muted",
    iconColor: "text-info",
  },
  competition: {
    label: "竞争",
    icon: Swords,
    color: "bg-muted",
    iconColor: "text-destructive",
  },
  hierarchy: {
    label: "层级",
    icon: GitBranch,
    color: "bg-muted",
    iconColor: "text-warning",
  },
} as const;

const CONSENSUS_LABELS: Record<ConsensusMethod, string> = {
  majority_vote: "多数投票",
  llm_synthesis: "LLM 综合",
  concatenation: "结果拼接",
  semantic: "语义聚合",
  length_based: "长度加权",
  weighted: "权重投票",
};

export function TeamPage() {
  const [teams, setTeams] = React.useState<TeamConfig[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [openCreate, setOpenCreate] = React.useState(false);

  async function load() {
    setLoading(true);
    try {
      const res: TeamsListResponse = await api.listTeams();
      setTeams(res.data);
    } catch (e) {
      reportError(e, "加载团队失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  async function create(payload: TeamCreateRequest) {
    try {
      const res = await api.createTeam(payload);
      toast.success("团队已创建", { description: res.name });
      setOpenCreate(false);
      await load();
    } catch (e) {
      reportError(e, "创建失败");
    }
  }

  async function remove(id: string, name: string) {
    if (!confirm(`确认删除团队 "${name}" 吗？`)) return;
    try {
      await api.deleteTeam(id);
      toast.success("已删除");
      await load();
    } catch (e) {
      reportError(e, "删除失败");
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="智能体团队"
        description="编排多个 Agent 协作完成复杂任务，支持共识投票与通信画布"
        icon={<Users className="h-5 w-5" />}
        actions={
          <Dialog open={openCreate} onOpenChange={setOpenCreate}>
            <DialogTrigger asChild>
              <Button variant="default">
                <Plus className="h-4 w-4" /> 新建团队
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>新建团队</DialogTitle>
                <DialogDescription>配置协作模式、共识策略和成员</DialogDescription>
              </DialogHeader>
              <CreateTeamForm onCreate={create} />
            </DialogContent>
          </Dialog>
        }
      />

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Spinner className="h-5 w-5" />
        </div>
      ) : teams.length === 0 ? (
        <EmptyState
          icon={<Users className="h-6 w-6" />}
          title="还没有团队"
          description="创建团队来组织多智能体协作"
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {teams.map((t, i) => {
            const meta = MODE_META[t.mode as keyof typeof MODE_META] ?? {
              label: t.mode || "未知",
              icon: Users,
              color: "bg-muted",
              iconColor: "text-muted-foreground",
            };
            const ModeIcon = meta.icon;
            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Card className="group h-full transition-all hover:border-primary/40">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3">
                        <div
                          className={cn(
                            "flex h-10 w-10 items-center justify-center rounded-md ring-1 ring-border",
                            meta.color,
                          )}
                        >
                          <ModeIcon className={cn("h-5 w-5", meta.iconColor)} />
                        </div>
                        <div>
                          <CardTitle className="text-base">{t.name}</CardTitle>
                          <p className="text-xs text-muted-foreground">{t.members.length} 个成员</p>
                        </div>
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => remove(t.id, t.name)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="line-clamp-2 text-xs text-muted-foreground">
                      {t.description || "无描述"}
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1">
                      <Badge variant="outline" className="text-[10px]">
                        {meta.label}
                      </Badge>
                      <Badge variant="accent" className="text-[10px]">
                        {CONSENSUS_LABELS[t.consensus_method] || t.consensus_method}
                      </Badge>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {t.members.slice(0, 4).map((m) => (
                        <Badge key={m.id} variant="outline" className="text-[10px]">
                          {m.name}
                        </Badge>
                      ))}
                      {t.members.length > 4 && (
                        <Badge variant="outline" className="text-[10px]">
                          +{t.members.length - 4}
                        </Badge>
                      )}
                    </div>
                    <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
                      <span>{formatRelativeTime(t.created_at)}</span>
                      <Link to={`/team/${t.id}`}>
                        <Button variant="ghost" size="sm">
                          详情 <ArrowRight className="h-3 w-3" />
                        </Button>
                      </Link>
                    </div>
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

function CreateTeamForm({ onCreate }: { onCreate: (req: TeamCreateRequest) => void }) {
	const [name, setName] = React.useState("");
	const [description, setDescription] = React.useState("");
	const [mode, setMode] = React.useState<TeamMode>("collaboration");
	const [consensusMethod, setConsensusMethod] = React.useState<ConsensusMethod>("llm_synthesis");
	const [memberText, setMemberText] = React.useState(
		"研究员,researcher\n撰稿人,writer\n审校,editor",
	);
	const [templateId, setTemplateId] = React.useState<string>("");

	function applyTemplate(tid: string) {
		setTemplateId(tid);
		const t = TEAM_TEMPLATES.find((x) => x.id === tid);
		if (!t) return;
		const built = t.build("qwen-turbo");
		setName(built.name);
		setDescription(built.description || "");
		setMode(built.mode);
		setConsensusMethod(built.consensus_method);
		const txt = built.members
			.map((m) => `${m.name},${m.role}${m.system_prompt ? `,${m.system_prompt}` : ""}`)
			.join("\n");
		setMemberText(txt);
		toast.success("已加载模板", { description: `${t.emoji} ${t.name}` });
	}

	const aiPrompt = React.useMemo(
		() =>
			`请为多智能体团队生成成员列表。

团队名称：${name || "未命名"}
${description ? `团队描述：${description}\n` : ""}
请输出 3-5 个成员，每行格式：
成员名,角色,系统提示词

角色可选：worker / synthesizer / critic / researcher / writer / editor
要求：成员职责互补，覆盖不同角度。
只输出成员列表，不要加任何解释。`,
		[name, description],
	);

	const aiSystemHint = React.useMemo(
		() =>
			"你是一位多智能体系统设计师，擅长为团队设计差异化成员。要求：每行严格遵循「名字,角色,提示词」格式。",
		[],
	);

	function submit() {
		if (!name.trim()) {
			toast.error("请填写团队名称");
			return;
		}
		const members = memberText
			.split("\n")
			.map((l) => l.trim())
			.filter(Boolean)
			.map((l) => {
				const parts = l.split(",").map((s) => s.trim());
				const [n, r, sp] = parts;
				return { name: n, role: r || "member", weight: 1.0, system_prompt: sp || "" };
			});
		if (members.length < 2) {
			toast.error("至少 2 个成员");
			return;
		}
		onCreate({
			name: name.trim(),
			description: description.trim(),
			mode,
			consensus_method: consensusMethod,
			members,
		});
		setName("");
		setDescription("");
	}

	return (
		<>
			<DialogHeader>
				<DialogTitle>新建团队</DialogTitle>
				<DialogDescription>选模板或自定义成员</DialogDescription>
			</DialogHeader>
			<div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
				{/* 模板预设 */}
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">
						<Sparkles className="mr-1 inline h-3 w-3" /> 团队模板
					</Label>
					<div className="grid grid-cols-3 gap-2">
						{TEAM_TEMPLATES.map((t) => (
							<button
								key={t.id}
								type="button"
								onClick={() => applyTemplate(t.id)}
								className={cn(
									"flex flex-col items-start gap-1 rounded-md border border-border bg-card p-2 text-left transition-all hover:border-primary/40 hover:bg-primary/5",
									templateId === t.id &&
										"border-primary bg-primary/10 ring-1 ring-primary/30",
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

				<div className="grid grid-cols-2 gap-2">
					<div className="space-y-1.5">
						<Label className="text-xs">团队名称</Label>
						<Input
							value={name}
							onChange={(e) => setName(e.target.value)}
							placeholder="内容创作团队"
						/>
					</div>
					<div className="space-y-1.5">
						<Label className="text-xs">描述</Label>
						<Input
							value={description}
							onChange={(e) => setDescription(e.target.value)}
							placeholder="一句话"
						/>
					</div>
				</div>
				<div className="grid grid-cols-2 gap-2">
					<div className="space-y-1.5">
						<Label className="text-xs">协作模式</Label>
						<Select value={mode} onValueChange={(v) => setMode(v as TeamMode)}>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="collaboration">协作</SelectItem>
								<SelectItem value="competition">竞争</SelectItem>
								<SelectItem value="hierarchy">层级</SelectItem>
							</SelectContent>
						</Select>
					</div>
					<div className="space-y-1.5">
						<Label className="text-xs">共识策略</Label>
						<Select
							value={consensusMethod}
							onValueChange={(v) => setConsensusMethod(v as ConsensusMethod)}
						>
							<SelectTrigger>
								<SelectValue />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="majority_vote">多数投票</SelectItem>
								<SelectItem value="llm_synthesis">LLM 综合</SelectItem>
								<SelectItem value="concatenation">结果拼接</SelectItem>
								<SelectItem value="weighted">权重投票</SelectItem>
							</SelectContent>
						</Select>
					</div>
				</div>
				<div className="space-y-1.5">
					<div className="flex items-center justify-between">
						<Label className="text-xs">成员（每行 "名称,角色,提示词"）</Label>
						<AIGenerateButton
							prompt={aiPrompt}
							systemHint={aiSystemHint}
							onStream={(text) => setMemberText(text)}
							label="AI 生成成员"
						/>
					</div>
					<Textarea
						rows={6}
						value={memberText}
						onChange={(e) => setMemberText(e.target.value)}
						className="font-mono text-xs"
						placeholder="乐观者,worker,从积极角度看\n悲观者,worker,从消极角度看"
					/>
				</div>
			</div>
			<DialogFooter>
				<Button
					variant="outline"
					onClick={() => {
						setName("");
						setDescription("");
						setMemberText("");
						setTemplateId("");
					}}
				>
					重置
				</Button>
				<Button onClick={submit} variant="default">
					<Plus className="h-4 w-4" /> 创建
				</Button>
			</DialogFooter>
		</>
	);
}
