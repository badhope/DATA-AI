import { reportError } from "@/lib/errors";
("use client");

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  type WordEditResponse,
  type WordReadResponse,
  type WordTemplateResponse,
  type WordWriteResponse,
  api,
} from "@/lib/api/client";
import { copyToClipboard, formatBytes } from "@/lib/utils";
import {
  AlertCircle,
  Download,
  FilePlus,
  FileText,
  FileType2,
  Hash,
  Plus,
  Replace,
  Save,
  Search,
  Table,
} from "lucide-react";
import * as React from "react";

export function WordPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Word 文档"
        description="读取、编辑、生成 Word 文档 (.docx)"
        icon={<FileText className="h-5 w-5" />}
        accent="blue"
      />
      <Tabs defaultValue="read">
        <TabsList className="grid w-full max-w-md grid-cols-4">
          <TabsTrigger value="read">读取</TabsTrigger>
          <TabsTrigger value="new">新建</TabsTrigger>
          <TabsTrigger value="edit">编辑</TabsTrigger>
          <TabsTrigger value="template">模板</TabsTrigger>
        </TabsList>
        <TabsContent value="read" className="mt-4">
          <ReadTab />
        </TabsContent>
        <TabsContent value="new" className="mt-4">
          <WriteTab />
        </TabsContent>
        <TabsContent value="edit" className="mt-4">
          <EditTab />
        </TabsContent>
        <TabsContent value="template" className="mt-4">
          <TemplateTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ReadTab() {
  const [filePath, setFilePath] = React.useState("");
  const [data, setData] = React.useState<WordReadResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [query, setQuery] = React.useState("");

  async function read() {
    if (!filePath.trim()) {
      toast.error("请输入文件路径");
      return;
    }
    setLoading(true);
    try {
      const res = await api.wordRead({
        file_path: filePath.trim(),
        extract_tables: true,
        extract_images: false,
      });
      setData(res);
      toast.success("读取成功", { description: `${res.word_count} 词 / ${res.char_count} 字符` });
    } catch (e) {
      reportError(e, "读取失败");
    } finally {
      setLoading(false);
    }
  }

  const filteredParagraphs = React.useMemo(() => {
    if (!data || !query) return data?.paragraphs ?? [];
    const q = query.toLowerCase();
    return data.paragraphs.filter((p: { text: string; style: string }) =>
      p.text.toLowerCase().includes(q),
    );
  }, [data, query]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card className="lg:col-span-1">
        <CardHeader>
          <CardTitle className="text-base">选择文件</CardTitle>
          <CardDescription>输入服务端可访问的 .docx 路径</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">文件路径</Label>
            <Input
              placeholder="/path/to/file.docx"
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
                <span className="text-muted-foreground">段落数</span>
                <span className="font-mono">{data.paragraphs.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">表格数</span>
                <span className="font-mono">{data.tables.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">字数</span>
                <span className="font-mono">{data.word_count}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">内容</CardTitle>
            {data && (
              <div className="relative w-48">
                <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                <Input
                  placeholder="搜索段落..."
                  className="h-8 pl-8 text-xs"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!data ? (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <FileText className="mb-2 h-8 w-8 opacity-30" />
              请先选择文件并点击"读取"
            </div>
          ) : filteredParagraphs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <AlertCircle className="mb-2 h-8 w-8 opacity-30" />
              没有匹配的段落
            </div>
          ) : (
            <div className="max-h-[500px] space-y-2 overflow-y-auto pr-2">
              {filteredParagraphs.map((p, i) => (
                <div key={i} className="rounded-md border border-border/40 bg-muted/20 p-3 text-sm">
                  <Badge variant="outline" className="mb-1 text-[10px]">
                    {p.style}
                  </Badge>
                  <p className="whitespace-pre-wrap">{p.text}</p>
                </div>
              ))}
            </div>
          )}
          {data && data.tables.length > 0 && (
            <div className="mt-4 space-y-3">
              <h4 className="text-sm font-semibold">表格 ({data.tables.length})</h4>
              {data.tables
                .slice(0, 3)
                .map((t: { index: number; rows: number; cols: number; data: string[][] }) => (
                  <div key={t.index} className="overflow-x-auto rounded-md border border-border/40">
                    <table className="w-full text-xs">
                      <tbody>
                        {t.data.slice(0, 5).map((row: string[], ri: number) => (
                          <tr key={ri} className="border-b border-border/30 last:border-0">
                            {row.map((cell: string, ci: number) => (
                              <td key={ci} className="px-2 py-1.5">
                                {cell}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function WriteTab() {
  const [filePath, setFilePath] = React.useState("");
  const [title, setTitle] = React.useState("");
  const [author, setAuthor] = React.useState("");
  const [content, setContent] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<WordWriteResponse | null>(null);

  async function create() {
    if (!filePath.trim() || !content.trim()) {
      toast.error("请填写文件路径和内容");
      return;
    }
    setLoading(true);
    try {
      const res = await api.wordWrite({
        file_path: filePath.trim(),
        content,
        title,
        author,
        format: "text",
      });
      setResult(res);
      toast.success("创建成功", { description: `已写入 ${res.paragraphs_written} 段` });
    } catch (e) {
      reportError(e, "创建失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">新建文档</CardTitle>
          <CardDescription>输入文件名和正文</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">文件路径（含 .docx）</Label>
            <Input
              placeholder="/path/to/output.docx"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <Label className="text-xs">标题</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="可选" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">作者</Label>
              <Input
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder="可选"
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">正文</Label>
            <Textarea
              rows={12}
              placeholder="段落之间用空行分隔"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
          </div>
          <Button onClick={create} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <FilePlus className="h-4 w-4" />}
            创建文档
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">结果</CardTitle>
        </CardHeader>
        <CardContent>
          {result ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-success">
                <Save className="h-4 w-4" /> 文档已保存
              </div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">路径</span>
                  <span className="font-mono">{result.file_path}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">大小</span>
                  <span className="font-mono">{formatBytes(result.file_size)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">段落数</span>
                  <span className="font-mono">{result.paragraphs_written}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <FilePlus className="mb-2 h-8 w-8 opacity-30" />
              填写后点击"创建文档"
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function EditTab() {
  const [filePath, setFilePath] = React.useState("");
  const [operation, setOperation] = React.useState<
    "replace" | "append_paragraph" | "add_heading" | "add_table"
  >("append_paragraph");
  const [find, setFind] = React.useState("");
  const [replace, setReplace] = React.useState("");
  const [text, setText] = React.useState("");
  const [level, setLevel] = React.useState(1);
  const [tableData, setTableData] = React.useState("姓名,年龄,城市\n张三,28,北京\n李四,32,上海");
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<WordEditResponse | null>(null);

  async function run() {
    if (!filePath.trim()) {
      toast.error("请输入文件路径");
      return;
    }
    setLoading(true);
    try {
      let table: string[][] | undefined;
      if (operation === "add_table") {
        table = tableData.split("\n").map((r) => r.split(","));
      }
      const res = await api.wordEdit({
        file_path: filePath.trim(),
        operation,
        find: find || undefined,
        replace: replace || undefined,
        text: text || undefined,
        level: operation === "add_heading" ? level : undefined,
        table,
      });
      setResult(res);
      toast.success("编辑成功", { description: `变更 ${res.changes} 处` });
    } catch (e) {
      reportError(e, "编辑失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">编辑操作</CardTitle>
          <CardDescription>替换、追加段落、添加标题、添加表格</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">文件路径</Label>
            <Input
              placeholder="/path/to/file.docx"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">操作</Label>
            <Select value={operation} onValueChange={(v) => setOperation(v as typeof operation)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="replace">替换文本</SelectItem>
                <SelectItem value="append_paragraph">追加段落</SelectItem>
                <SelectItem value="add_heading">添加标题</SelectItem>
                <SelectItem value="add_table">添加表格</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {operation === "replace" && (
            <div className="space-y-2">
              <div className="space-y-1.5">
                <Label className="text-xs">查找</Label>
                <Input
                  value={find}
                  onChange={(e) => setFind(e.target.value)}
                  placeholder="旧文本"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">替换为</Label>
                <Input
                  value={replace}
                  onChange={(e) => setReplace(e.target.value)}
                  placeholder="新文本"
                />
              </div>
            </div>
          )}
          {operation === "append_paragraph" && (
            <div className="space-y-1.5">
              <Label className="text-xs">追加内容</Label>
              <Textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} />
            </div>
          )}
          {operation === "add_heading" && (
            <div className="space-y-2">
              <div className="space-y-1.5">
                <Label className="text-xs">标题文本</Label>
                <Input value={text} onChange={(e) => setText(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">级别 (1-6)</Label>
                <Input
                  type="number"
                  min={1}
                  max={6}
                  value={level}
                  onChange={(e) => setLevel(Number.parseInt(e.target.value) || 1)}
                />
              </div>
            </div>
          )}
          {operation === "add_table" && (
            <div className="space-y-1.5">
              <Label className="text-xs">表格数据 (CSV)</Label>
              <Textarea
                rows={5}
                value={tableData}
                onChange={(e) => setTableData(e.target.value)}
                className="font-mono text-xs"
              />
            </div>
          )}
          <Button onClick={run} disabled={loading} className="w-full">
            {loading ? (
              <Spinner className="h-4 w-4" />
            ) : operation === "replace" ? (
              <Replace className="h-4 w-4" />
            ) : operation === "add_heading" ? (
              <Hash className="h-4 w-4" />
            ) : operation === "add_table" ? (
              <Table className="h-4 w-4" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            执行
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">结果</CardTitle>
        </CardHeader>
        <CardContent>
          {result ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-success">
                <Save className="h-4 w-4" /> {result.operation} 已完成
              </div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">变更次数</span>
                  <span className="font-mono">{result.changes}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">路径</span>
                  <span className="font-mono">{result.file_path}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <FileType2 className="mb-2 h-8 w-8 opacity-30" />
              选择文件并执行
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function TemplateTab() {
  const [templatePath, setTemplatePath] = React.useState("");
  const [outputPath, setOutputPath] = React.useState("");
  const [data, setData] = React.useState('{"name": "张三", "date": "2026-06-02"}');
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<WordTemplateResponse | null>(null);

  async function generate() {
    if (!templatePath.trim() || !outputPath.trim()) {
      toast.error("请填写模板路径和输出路径");
      return;
    }
    let parsed: Record<string, unknown> = {};
    try {
      parsed = JSON.parse(data);
    } catch {
      toast.error("JSON 数据格式错误");
      return;
    }
    setLoading(true);
    try {
      const res = await api.wordTemplate({
        template_path: templatePath.trim(),
        output_path: outputPath.trim(),
        data: parsed,
      });
      setResult(res);
      toast.success("生成成功", { description: `${res.replacements} 处替换` });
    } catch (e) {
      reportError(e, "生成失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">模板生成</CardTitle>
          <CardDescription>从 .docx 模板 + JSON 数据生成文档</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">模板路径（含 {"{{占位符}}"}）</Label>
            <Input
              placeholder="/path/to/template.docx"
              value={templatePath}
              onChange={(e) => setTemplatePath(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">输出路径</Label>
            <Input
              placeholder="/path/to/output.docx"
              value={outputPath}
              onChange={(e) => setOutputPath(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">数据 (JSON)</Label>
            <Textarea
              rows={8}
              value={data}
              onChange={(e) => setData(e.target.value)}
              className="font-mono text-xs"
            />
          </div>
          <Button onClick={generate} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <FileType2 className="h-4 w-4" />}
            生成文档
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">结果</CardTitle>
        </CardHeader>
        <CardContent>
          {result ? (
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2 text-success">
                <Download className="h-4 w-4" /> 已生成
              </div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">输出路径</span>
                  <span className="font-mono">{result.output_path}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">大小</span>
                  <span className="font-mono">{formatBytes(result.file_size)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">替换次数</span>
                  <span className="font-mono">{result.replacements}</span>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={async () => {
                  await copyToClipboard(result.output_path);
                  toast.success("已复制路径");
                }}
              >
                复制路径
              </Button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <FileType2 className="mb-2 h-8 w-8 opacity-30" />
              填写后点击"生成文档"
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
