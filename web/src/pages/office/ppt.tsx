import { reportError } from "@/lib/errors";
("use client");

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { type PptReadResponse, type PptWriteResponse, api } from "@/lib/api/client";
import { formatBytes } from "@/lib/utils";
import {
  ChevronLeft,
  ChevronRight,
  FilePlus,
  FileText,
  Plus,
  Presentation,
  Save,
  Trash2,
} from "lucide-react";
import * as React from "react";

export function PptPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="PPT 演示文稿"
        description="读取、创建 PowerPoint 幻灯片 (.pptx)"
        icon={<Presentation className="h-5 w-5" />}
        accent="orange"
      />
      <Tabs defaultValue="read">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="read">读取</TabsTrigger>
          <TabsTrigger value="create">创建</TabsTrigger>
        </TabsList>
        <TabsContent value="read" className="mt-4">
          <ReadTab />
        </TabsContent>
        <TabsContent value="create" className="mt-4">
          <CreateTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ReadTab() {
  const [filePath, setFilePath] = React.useState("");
  const [data, setData] = React.useState<PptReadResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [currentSlide, setCurrentSlide] = React.useState(0);

  async function read() {
    if (!filePath.trim()) {
      toast.error("请输入文件路径");
      return;
    }
    setLoading(true);
    try {
      const res = await api.pptRead({ file_path: filePath.trim() });
      setData(res);
      setCurrentSlide(0);
      toast.success("读取成功", { description: `${res.total_slides} 张幻灯片` });
    } catch (e) {
      reportError(e, "读取失败");
    } finally {
      setLoading(false);
    }
  }

  const slide = data?.slides[currentSlide];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">选择文件</CardTitle>
          <CardDescription>输入 .pptx 文件路径</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">文件路径</Label>
            <Input
              placeholder="/path/to/file.pptx"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
            />
          </div>
          <Button onClick={read} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
            读取
          </Button>
          {data && (
            <div className="space-y-2 pt-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">文件名</span>
                <span className="font-mono">{data.file_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">大小</span>
                <span className="font-mono">{formatBytes(data.file_size)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">幻灯片数</span>
                <span className="font-mono">{data.total_slides}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">预览</CardTitle>
            {data && (
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setCurrentSlide((i) => Math.max(0, i - 1))}
                  disabled={currentSlide === 0}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <span className="text-sm text-muted-foreground">
                  {currentSlide + 1} / {data.slides.length}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setCurrentSlide((i) => Math.min(data.slides.length - 1, i + 1))}
                  disabled={currentSlide >= data.slides.length - 1}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!data ? (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <Presentation className="mb-2 h-8 w-8 opacity-30" />
              请先选择文件并点击"读取"
            </div>
          ) : slide ? (
            <div className="space-y-3">
              <div className="border border-border bg-muted p-6">
                <h3 className="text-lg font-semibold">第 {slide.slide_number} 张</h3>
                {slide.text.length > 0 ? (
                  <ul className="mt-3 space-y-2 text-sm">
                    {slide.text.map((t: string, i: number) => (
                      <li key={i} className="rounded border border-border/30 bg-background/40 p-2">
                        {t}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-sm text-muted-foreground">（无文本内容）</p>
                )}
                {slide.notes && (
                  <div className="mt-4 border-t border-border/30 pt-3">
                    <p className="text-xs text-muted-foreground">备注：</p>
                    <p className="mt-1 text-sm">{slide.notes}</p>
                  </div>
                )}
              </div>
              {slide.shapes.length > 0 && (
                <div className="text-xs text-muted-foreground">{slide.shapes.length} 个形状</div>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

interface SlideDraft {
  id: string;
  title: string;
  content: string;
  layout: "title" | "title_and_content" | "section" | "blank";
  notes: string;
}

function CreateTab() {
  const [filePath, setFilePath] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [slides, setSlides] = React.useState<SlideDraft[]>([
    { id: "1", title: "标题", content: "副标题或简介", layout: "title", notes: "" },
    {
      id: "2",
      title: "要点",
      content: "• 要点 1\n• 要点 2\n• 要点 3",
      layout: "title_and_content",
      notes: "",
    },
  ]);
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<PptWriteResponse | null>(null);

  function addSlide() {
    setSlides((prev) => [
      ...prev,
      { id: String(Date.now()), title: "", content: "", layout: "title_and_content", notes: "" },
    ]);
  }

  function removeSlide(id: string) {
    setSlides((prev) => prev.filter((s) => s.id !== id));
  }

  function updateSlide(id: string, patch: Partial<SlideDraft>) {
    setSlides((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)));
  }

  async function create() {
    if (!filePath.trim()) {
      toast.error("请填写输出文件路径");
      return;
    }
    if (slides.length === 0) {
      toast.error("至少需要一张幻灯片");
      return;
    }
    setLoading(true);
    try {
      const res = await api.pptWrite({
        file_path: filePath.trim(),
        title: title || "未命名演示文稿",
        slides: slides.map((s) => ({
          title: s.title,
          content: s.content,
          layout: s.layout,
          notes: s.notes,
        })),
      });
      setResult(res);
      toast.success("创建成功", { description: `${res.total_slides} 张幻灯片` });
    } catch (e) {
      reportError(e, "创建失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">新建演示文稿</CardTitle>
          <CardDescription>配置输出文件、标题和每张幻灯片</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">输出文件路径</Label>
              <Input
                placeholder="/path/to/output.pptx"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">演示文稿标题</Label>
              <Input
                placeholder="我的演示"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-3">
        {slides.map((s, idx) => (
          <Card key={s.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Badge variant="outline">第 {idx + 1} 张</Badge>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeSlide(s.id)}
                  disabled={slides.length <= 1}
                >
                  <Trash2 className="h-4 w-4 text-destructive" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <Input
                  placeholder="标题"
                  value={s.title}
                  onChange={(e) => updateSlide(s.id, { title: e.target.value })}
                  className="sm:col-span-2"
                />
                <select
                  className="h-9 rounded-md border border-input bg-background px-3 text-sm"
                  value={s.layout}
                  onChange={(e) =>
                    updateSlide(s.id, { layout: e.target.value as SlideDraft["layout"] })
                  }
                >
                  <option value="title">标题页</option>
                  <option value="title_and_content">标题+内容</option>
                  <option value="section">节标题</option>
                  <option value="blank">空白</option>
                </select>
              </div>
              <Textarea
                rows={3}
                placeholder="内容（每行一个要点）"
                value={s.content}
                onChange={(e) => updateSlide(s.id, { content: e.target.value })}
              />
              <Input
                placeholder="演讲者备注（可选）"
                value={s.notes}
                onChange={(e) => updateSlide(s.id, { notes: e.target.value })}
              />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex items-center justify-between gap-2">
        <Button variant="outline" onClick={addSlide}>
          <Plus className="h-4 w-4" /> 添加幻灯片
        </Button>
        <Button onClick={create} disabled={loading}>
          {loading ? <Spinner className="h-4 w-4" /> : <FilePlus className="h-4 w-4" />}
          创建演示文稿
        </Button>
      </div>

      {result && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-success">
              <Save className="h-4 w-4" /> 已保存到 {result.file_path}
            </div>
            <div className="mt-2 grid grid-cols-3 gap-3 text-xs">
              <div>
                <span className="text-muted-foreground">大小：</span>
                {formatBytes(result.file_size)}
              </div>
              <div>
                <span className="text-muted-foreground">幻灯片：</span>
                {result.total_slides}
              </div>
              <div className="truncate">
                <span className="text-muted-foreground">路径：</span>
                <span className="font-mono">{result.file_path}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
