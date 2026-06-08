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
import {
  type PdfMergeResponse,
  type PdfReadResponse,
  type PdfSplitResponse,
  api,
} from "@/lib/api/client";
import { formatBytes } from "@/lib/utils";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Combine,
  FileText,
  Save,
  Scissors,
  Search,
} from "lucide-react";
import * as React from "react";

export function PdfPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="PDF 文档"
        description="读取、合并、拆分 PDF 文档"
        icon={<FileText className="h-5 w-5" />}
        accent="red"
      />
      <Tabs defaultValue="read">
        <TabsList className="grid w-full max-w-md grid-cols-3">
          <TabsTrigger value="read">读取</TabsTrigger>
          <TabsTrigger value="merge">合并</TabsTrigger>
          <TabsTrigger value="split">拆分</TabsTrigger>
        </TabsList>
        <TabsContent value="read" className="mt-4">
          <ReadTab />
        </TabsContent>
        <TabsContent value="merge" className="mt-4">
          <MergeTab />
        </TabsContent>
        <TabsContent value="split" className="mt-4">
          <SplitTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ReadTab() {
  const [filePath, setFilePath] = React.useState("");
  const [data, setData] = React.useState<PdfReadResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [currentPage, setCurrentPage] = React.useState(0);

  async function read() {
    if (!filePath.trim()) {
      toast.error("请输入文件路径");
      return;
    }
    setLoading(true);
    try {
      const res = await api.pdfRead({ file_path: filePath.trim() });
      setData(res);
      setCurrentPage(0);
      toast.success("读取成功", { description: `${res.total_pages} 页` });
    } catch (e) {
      reportError(e, "读取失败");
    } finally {
      setLoading(false);
    }
  }

  const page = data?.pages[currentPage];
  const pageText = page?.text || "";
  const matches = React.useMemo(() => {
    if (!page || !query) return [] as Array<{ start: number; end: number }>;
    const out: Array<{ start: number; end: number }> = [];
    const q = query.toLowerCase();
    const t = pageText.toLowerCase();
    let i = 0;
    while (true) {
      const idx = t.indexOf(q, i);
      if (idx === -1) break;
      out.push({ start: idx, end: idx + q.length });
      i = idx + q.length;
    }
    return out;
  }, [page, query, pageText]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">选择文件</CardTitle>
          <CardDescription>输入 .pdf 文件路径</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">文件路径</Label>
            <Input
              placeholder="/path/to/file.pdf"
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
                <span className="text-muted-foreground">页数</span>
                <span className="font-mono">{data.total_pages}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">
              {data ? `第 ${currentPage + 1} / ${data.total_pages} 页` : "内容"}
            </CardTitle>
            {data && (
              <>
                <div className="relative flex-1 max-w-xs">
                  <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
                  <Input
                    placeholder="搜索文本..."
                    className="h-8 pl-8 text-xs"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setCurrentPage((i) => Math.max(0, i - 1))}
                  disabled={currentPage === 0}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setCurrentPage((i) => Math.min(data.total_pages - 1, i + 1))}
                  disabled={currentPage >= data.total_pages - 1}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!data ? (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <FileText className="mb-2 h-8 w-8 opacity-30" />
              请先选择文件并点击"读取"
            </div>
          ) : !page ? null : matches.length === 0 && query ? (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <AlertCircle className="mb-2 h-8 w-8 opacity-30" />
              本页未找到 "{query}"
            </div>
          ) : (
            <div className="max-h-[500px] overflow-y-auto rounded-md border border-border/40 bg-muted/20 p-4 text-sm leading-relaxed">
              {matches.length > 0 ? (
                <>
                  {matches.map((m, i) => (
                    <React.Fragment key={i}>
                      <span>{pageText.slice(i === 0 ? 0 : matches[i - 1].end, m.start)}</span>
                      <mark className="rounded bg-warning/30 px-0.5 text-warning">
                        {pageText.slice(m.start, m.end)}
                      </mark>
                      {i === matches.length - 1 && <span>{pageText.slice(m.end)}</span>}
                    </React.Fragment>
                  ))}
                </>
              ) : (
                <p className="whitespace-pre-wrap">{pageText || "（本页无文本）"}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MergeTab() {
  const [paths, setPaths] = React.useState("/a.pdf\n/b.pdf\n/c.pdf");
  const [output, setOutput] = React.useState("/merged.pdf");
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<PdfMergeResponse | null>(null);

  async function merge() {
    const list = paths
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (list.length < 2) {
      toast.error("至少输入 2 个 PDF 路径");
      return;
    }
    if (!output.trim()) {
      toast.error("请填写输出路径");
      return;
    }
    setLoading(true);
    try {
      const res = await api.pdfMerge({ file_paths: list, output_path: output.trim() });
      setResult(res);
      toast.success("合并成功", { description: `${res.merged_count} 个文件` });
    } catch (e) {
      reportError(e, "合并失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">合并 PDF</CardTitle>
          <CardDescription>每行一个 PDF 路径</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">输入文件（每行一个）</Label>
            <Textarea
              rows={6}
              value={paths}
              onChange={(e) => setPaths(e.target.value)}
              className="font-mono text-xs"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">输出文件</Label>
            <Input
              placeholder="/merged.pdf"
              value={output}
              onChange={(e) => setOutput(e.target.value)}
            />
          </div>
          <Button onClick={merge} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <Combine className="h-4 w-4" />}
            合并
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
                <Save className="h-4 w-4" /> 合并完成
              </div>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">输出</span>
                  <span className="font-mono">{result.output_path}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">大小</span>
                  <span className="font-mono">{formatBytes(result.file_size)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">合并数</span>
                  <span className="font-mono">{result.merged_count}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <Combine className="mb-2 h-8 w-8 opacity-30" />
              填写后点击"合并"
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function SplitTab() {
  const [filePath, setFilePath] = React.useState("");
  const [ranges, setRanges] = React.useState("1-3, 5, 7-10");
  const [outputDir, setOutputDir] = React.useState("/tmp/split");
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<PdfSplitResponse | null>(null);

  async function split() {
    if (!filePath.trim() || !outputDir.trim()) {
      toast.error("请填写文件路径和输出目录");
      return;
    }
    setLoading(true);
    try {
      const res = await api.pdfSplit({
        file_path: filePath.trim(),
        ranges,
        output_dir: outputDir.trim(),
      });
      setResult(res);
      toast.success("拆分成功", { description: `${res.split_count} 个文件` });
    } catch (e) {
      reportError(e, "拆分失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">拆分 PDF</CardTitle>
          <CardDescription>按页码范围拆分，支持 "1-3, 5, 7-10" 格式</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label className="text-xs">输入文件</Label>
            <Input
              placeholder="/path/to/file.pdf"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">页码范围</Label>
            <Input
              placeholder="1-3, 5, 7-10"
              value={ranges}
              onChange={(e) => setRanges(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">输出目录</Label>
            <Input
              placeholder="/tmp/split"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
            />
          </div>
          <Button onClick={split} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <Scissors className="h-4 w-4" />}
            拆分
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
                <Save className="h-4 w-4" /> 拆分完成
              </div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">输出目录</span>
                  <span className="font-mono">{result.output_dir}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">文件数</span>
                  <span className="font-mono">{result.split_count}</span>
                </div>
              </div>
              {result.output_files.length > 0 && (
                <div className="mt-2 space-y-1 rounded-md bg-muted/20 p-2 text-xs font-mono">
                  {result.output_files.slice(0, 10).map((f, i) => (
                    <div key={i} className="truncate">
                      {f}
                    </div>
                  ))}
                  {result.output_files.length > 10 && (
                    <div className="text-muted-foreground">
                      ... +{result.output_files.length - 10} 个文件
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-sm text-muted-foreground">
              <Scissors className="mb-2 h-8 w-8 opacity-30" />
              填写后点击"拆分"
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
