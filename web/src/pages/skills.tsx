import { AIGenerateButton } from "@/components/shared/ai-generate-button";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { type Skill, type SkillExtractionResponse, api } from "@/lib/api/client";
import { SKILL_TEMPLATES } from "@/lib/templates";
import { cn, formatRelativeTime } from "@/lib/utils";
import {
	AlertCircle,
	Code2,
	Pencil,
	Play,
	Plus,
	Save,
	Search,
	Settings2,
	Sparkles,
	Trash2,
	Wand2,
} from "lucide-react";
import * as React from "react";

export function SkillsPage() {
  const [skills, setSkills] = React.useState<Skill[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [search, setSearch] = React.useState("");
  const [category, setCategory] = React.useState("");

  async function load() {
    setLoading(true);
    try {
      const res = await api.listSkills({
        q: search || undefined,
        category: category || undefined,
      });
      setSkills(res.data);
    } catch (e) {
      reportError(e, "加载技能失败");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, [search, category]);

  const categories = Array.from(new Set(skills.map((s) => s.category))).filter(Boolean);

  return (
    <div className="space-y-6">
      <PageHeader
        title="技能市场"
        description="可复用的工具 / 提示词 / 工作流模板"
        icon={<Sparkles className="h-5 w-5" />}
        accent="pink"
      />

      <Tabs defaultValue="list">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="list">浏览</TabsTrigger>
          <TabsTrigger value="create">创建</TabsTrigger>
          <TabsTrigger value="extract">提取</TabsTrigger>
        </TabsList>

        <TabsContent value="list" className="mt-4 space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索技能"
                className="pl-8"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <Select
              value={category || "_all"}
              onValueChange={(v) => setCategory(v === "_all" ? "" : v)}
            >
              <SelectTrigger className="sm:w-40">
                <SelectValue placeholder="全部类别" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_all">全部类别</SelectItem>
                {categories.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Spinner className="h-5 w-5" />
            </div>
          ) : skills.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/60 py-12 text-sm text-muted-foreground">
              <Sparkles className="mb-2 h-8 w-8 opacity-30" />
              还没有技能
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {skills.map((s) => (
                <SkillCard key={s.name} skill={s} onDeleted={load} />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="create" className="mt-4">
          <CreateSkillForm onCreated={load} />
        </TabsContent>

        <TabsContent value="extract" className="mt-4">
          <ExtractForm />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SkillCard({ skill, onDeleted }: { skill: Skill; onDeleted: () => void }) {
  const [open, setOpen] = React.useState(false);
  const [params, setParams] = React.useState<Record<string, string>>({});
  const [executing, setExecuting] = React.useState(false);
  const [output, setOutput] = React.useState<unknown>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [editing, setEditing] = React.useState(false);
  const [yaml, setYaml] = React.useState(skill.yaml || "");

  async function run() {
    setExecuting(true);
    setOutput(null);
    setError(null);
    try {
      // 解析参数
      const parsed: Record<string, unknown> = {};
      for (const p of skill.parameters) {
        const v = params[p.name];
        if (v === undefined || v === "") continue;
        if (p.type === "number") parsed[p.name] = Number.parseFloat(v);
        else if (p.type === "integer") parsed[p.name] = Number.parseInt(v, 10);
        else if (p.type === "boolean") parsed[p.name] = v === "true";
        else parsed[p.name] = v;
      }
      const res = await api.executeSkill(skill.name, { parameters: parsed });
      setOutput(res.output);
      if (res.error) setError(res.error);
      toast[res.success ? "success" : "error"](res.success ? "执行成功" : "执行失败", {
        description: `${res.duration_ms}ms`,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      reportError(e, "请求失败");
    } finally {
      setExecuting(false);
    }
  }

  async function saveYaml() {
    try {
      await api.saveSkill(skill.name, { ...skill, yaml });
      toast.success("已保存");
      setEditing(false);
    } catch (e) {
      reportError(e, "保存失败");
    }
  }

  async function remove() {
    if (!confirm(`确认删除技能 "${skill.name}" 吗？`)) return;
    try {
      await api.deleteSkill(skill.name);
      toast.success("已删除");
      onDeleted();
    } catch (e) {
      reportError(e, "删除失败");
    }
  }

  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{skill.name}</p>
            <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{skill.description}</p>
            <div className="mt-2 flex flex-wrap gap-1">
              <Badge variant="outline" className="text-[10px]">
                {skill.category}
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                v{skill.version}
              </Badge>
              {skill.tags.slice(0, 2).map((t) => (
                <Badge key={t} variant="accent" className="text-[10px]">
                  {t}
                </Badge>
              ))}
            </div>
            <p className="mt-2 text-[10px] text-muted-foreground">
              {skill.parameters.length} 个参数
              {"source" in skill && (skill as { source?: string }).source === "user" && " · 自定义"}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <Button size="icon" variant="ghost" onClick={() => setOpen(true)}>
              <Play className="h-4 w-4 text-primary" />
            </Button>
            {(skill as { source?: string }).source === "user" && (
              <Button size="icon" variant="ghost" onClick={() => setEditing(true)}>
                <Pencil className="h-4 w-4 text-info" />
              </Button>
            )}
            <Button size="icon" variant="ghost" onClick={remove}>
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
          </div>
        </div>
      </CardContent>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>执行 {skill.name}</DialogTitle>
            <DialogDescription>{skill.description}</DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {skill.parameters.length === 0 ? (
              <p className="text-sm text-muted-foreground">该技能无参数</p>
            ) : (
              skill.parameters.map((p) => (
                <div key={p.name} className="space-y-1">
                  <Label className="text-xs">
                    {p.name}
                    {p.required && <span className="ml-1 text-destructive">*</span>}
                    <span className="ml-1 text-muted-foreground">({p.type})</span>
                  </Label>
                  <Input
                    value={params[p.name] || ""}
                    onChange={(e) => setParams({ ...params, [p.name]: e.target.value })}
                    placeholder={p.description}
                  />
                </div>
              ))
            )}
            <Button onClick={run} disabled={executing} className="w-full mt-2">
              {executing ? <Spinner className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              执行
            </Button>
            {output !== null && (
              <div>
                <Label className="text-xs">输出</Label>
                <pre className="mt-1 max-h-60 overflow-auto rounded-md bg-muted/30 p-3 text-xs">
                  {typeof output === "string" ? output : JSON.stringify(output, null, 2)}
                </pre>
              </div>
            )}
            {error && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
                <AlertCircle className="mr-1 inline h-3 w-3" />
                {error}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={editing} onOpenChange={setEditing}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑 YAML</DialogTitle>
            <DialogDescription>修改技能定义</DialogDescription>
          </DialogHeader>
          <Textarea
            rows={12}
            value={yaml}
            onChange={(e) => setYaml(e.target.value)}
            className="font-mono text-xs"
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditing(false)}>
              取消
            </Button>
            <Button onClick={saveYaml}>
              <Save className="h-4 w-4" /> 保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function CreateSkillForm({ onCreated }: { onCreated: () => void }) {
	const [name, setName] = React.useState("");
	const [description, setDescription] = React.useState("");
	const [category, setCategory] = React.useState("custom");
	const [tags, setTags] = React.useState("");
	const [implementation, setImplementation] = React.useState("");
	const [yaml, setYaml] = React.useState("");
	const [loading, setLoading] = React.useState(false);
	const [templateId, setTemplateId] = React.useState<string>("");
	const [mode, setMode] = React.useState<"python" | "yaml">("python");

	function applyTemplate(tid: string) {
		setTemplateId(tid);
		const t = SKILL_TEMPLATES.find((x) => x.id === tid);
		if (!t) return;
		setName(t.name);
		setDescription(t.description);
		setCategory(t.category);
		setYaml(t.yaml);
		setMode("yaml");
		toast.success("已加载模板", { description: `${t.emoji} ${t.name}` });
	}

	const aiDescPrompt = React.useMemo(
		() =>
			`请为一个名为「${name || "未命名"}」的 skill 写一段精炼的中文描述（一句话，30 字内）。`,
		[name],
	);

	async function create() {
		if (!name.trim() || !description.trim()) {
			toast.error("请填写名称和描述");
			return;
		}
		setLoading(true);
		try {
			await api.createSkill({
				name: name.trim(),
				description: description.trim(),
				category,
				tags: tags
					.split(",")
					.map((t) => t.trim())
					.filter(Boolean),
				parameters: [],
				implementation: mode === "python" ? implementation || undefined : undefined,
				yaml: mode === "yaml" ? yaml || undefined : undefined,
			});
			toast.success("已创建", { description: name });
			setName("");
			setDescription("");
			setImplementation("");
			setYaml("");
			setTemplateId("");
			onCreated();
		} catch (e) {
			reportError(e, "创建失败");
		} finally {
			setLoading(false);
		}
	}

	return (
		<Card>
			<CardHeader>
				<CardTitle className="text-base">新建技能</CardTitle>
				<CardDescription>选模板、AI 帮填、Python / YAML 双模式</CardDescription>
			</CardHeader>
			<CardContent className="space-y-3">
				{/* 模板 */}
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">
						<Sparkles className="mr-1 inline h-3 w-3" /> 快速模板
					</Label>
					<div className="grid grid-cols-3 gap-2">
						{SKILL_TEMPLATES.map((t) => (
							<button
								key={t.id}
								type="button"
								onClick={() => applyTemplate(t.id)}
								className={cn(
									"flex flex-col items-start gap-1 rounded-md border border-border bg-card p-2 text-left transition-all hover:border-primary/40",
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

				<div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<div className="space-y-1.5">
						<Label className="text-xs">名称</Label>
						<Input value={name} onChange={(e) => setName(e.target.value)} placeholder="my-skill" />
					</div>
					<div className="space-y-1.5">
						<Label className="text-xs">分类</Label>
						<Input value={category} onChange={(e) => setCategory(e.target.value)} />
					</div>
				</div>
				<div className="space-y-1.5">
					<div className="flex items-center justify-between">
						<Label className="text-xs">描述</Label>
						<AIGenerateButton
							prompt={aiDescPrompt}
							onStream={(text) => setDescription(text)}
							label="AI 帮填"
						/>
					</div>
					<Textarea rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs">标签（逗号分隔）</Label>
					<Input
						value={tags}
						onChange={(e) => setTags(e.target.value)}
						placeholder="parser, text"
					/>
				</div>
				{/* 模式选择 */}
				<div className="flex gap-2">
					<Button
						type="button"
						variant={mode === "python" ? "default" : "outline"}
						size="sm"
						onClick={() => setMode("python")}
					>
						Python 实现
					</Button>
					<Button
						type="button"
						variant={mode === "yaml" ? "default" : "outline"}
						size="sm"
						onClick={() => setMode("yaml")}
					>
						YAML 定义
					</Button>
				</div>
				{mode === "python" ? (
					<div className="space-y-1.5">
						<Label className="text-xs">Python 实现（stdout 作为输出）</Label>
						<Textarea
							rows={6}
							value={implementation}
							onChange={(e) => setImplementation(e.target.value)}
							className="font-mono text-xs"
							placeholder={`print("hello")\nfor i in range(3):\n    print(i)`}
						/>
					</div>
				) : (
					<div className="space-y-1.5">
						<Label className="text-xs">YAML 技能定义</Label>
						<Textarea
							rows={10}
							value={yaml}
							onChange={(e) => setYaml(e.target.value)}
							className="font-mono text-xs"
							placeholder={`name: my-skill\nversion: 1.0.0\ndescription: ...\nparameters:\n  ...`}
						/>
					</div>
				)}
				<Button onClick={create} disabled={loading} className="w-full">
					{loading ? <Spinner className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
					创建技能
				</Button>
			</CardContent>
		</Card>
	);
}

function ExtractForm() {
  const [text, setText] = React.useState("");
  const [sourceType, setSourceType] = React.useState<"text" | "file" | "url">("text");
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<SkillExtractionResponse | null>(null);

  async function extract() {
    if (!text.trim()) {
      toast.error("请输入要分析的文本");
      return;
    }
    setLoading(true);
    try {
      const res = await api.extractSkill({ source: text, source_type: sourceType });
      setResult(res);
      toast.success(`提取到 ${res.candidates.length} 个候选技能`);
    } catch (e) {
      reportError(e, "提取失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">从文档提取技能</CardTitle>
          <CardDescription>分析代码或文档中的函数定义</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">源类型</Label>
            <Select value={sourceType} onValueChange={(v) => setSourceType(v as typeof sourceType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="text">纯文本</SelectItem>
                <SelectItem value="file">文件路径</SelectItem>
                <SelectItem value="url">URL（暂未实现）</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">{sourceType === "file" ? "文件路径" : "源文本"}</Label>
            <Textarea
              rows={10}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="font-mono text-xs"
              placeholder={
                sourceType === "file"
                  ? "/path/to/doc.md"
                  : "def my_function(x):\n    return x * 2\n..."
              }
            />
          </div>
          <Button onClick={extract} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <Wand2 className="h-4 w-4" />}
            提取 Skill
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">候选技能</CardTitle>
          <CardDescription>从文本中识别出的可重用函数</CardDescription>
        </CardHeader>
        <CardContent>
          {result ? (
            result.candidates.length === 0 ? (
              <p className="text-sm text-muted-foreground">未识别到候选技能</p>
            ) : (
              <div className="space-y-2">
                {result.candidates.map((c, i) => (
                  <div
                    key={i}
                    className="rounded-md border border-border/40 bg-muted/20 p-3 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <p className="font-mono text-sm font-medium">{c.name}()</p>
                      <Badge variant="accent">置信度 {c.confidence.toFixed(2)}</Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{c.description}</p>
                    {c.parameters.length > 0 && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        参数：{c.parameters.map((p) => p.name).join(", ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )
          ) : (
            <div className="py-12 text-center text-sm text-muted-foreground">
              <Wand2 className="mx-auto mb-2 h-8 w-8 opacity-30" />
              填写后点击"提取 Skill"
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
