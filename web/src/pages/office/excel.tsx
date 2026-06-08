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
import { type ExcelAnalyzeResponse, type ExcelReadResponse, api } from "@/lib/api/client";
import { formatBytes } from "@/lib/utils";
import {
  AlertCircle,
  BarChart,
  BarChart3,
  BarChartHorizontal,
  FileSpreadsheet,
  Save,
  Sheet,
  TrendingUp,
} from "lucide-react";
import * as React from "react";

export function ExcelPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Excel 表格"
        description="读取、分析、可视化 Excel 工作簿 (.xlsx)"
        icon={<Sheet className="h-5 w-5" />}
        accent="emerald"
      />
      <Tabs defaultValue="read">
        <TabsList className="grid w-full max-w-2xl grid-cols-4">
          <TabsTrigger value="read">读取</TabsTrigger>
          <TabsTrigger value="analyze">分析</TabsTrigger>
          <TabsTrigger value="chart">图表</TabsTrigger>
          <TabsTrigger value="write">创建</TabsTrigger>
        </TabsList>
        <TabsContent value="read" className="mt-4">
          <ReadTab />
        </TabsContent>
        <TabsContent value="analyze" className="mt-4">
          <AnalyzeTab />
        </TabsContent>
        <TabsContent value="chart" className="mt-4">
          <ChartTab />
        </TabsContent>
        <TabsContent value="write" className="mt-4">
          <WriteTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ReadTab() {
  const [filePath, setFilePath] = React.useState("");
  const [data, setData] = React.useState<ExcelReadResponse | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [activeSheet, setActiveSheet] = React.useState(0);

  async function read() {
    if (!filePath.trim()) {
      toast.error("请输入文件路径");
      return;
    }
    setLoading(true);
    try {
      const res = await api.excelRead({ file_path: filePath.trim() });
      setData(res);
      setActiveSheet(0);
      toast.success("读取成功", { description: `${res.sheets.length} 个工作表` });
    } catch (e) {
      reportError(e, "读取失败");
    } finally {
      setLoading(false);
    }
  }

  const sheet = data?.sheets[activeSheet];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">读取 Excel</CardTitle>
          <CardDescription>输入服务端可访问的 .xlsx 路径</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              placeholder="/path/to/file.xlsx"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              className="flex-1"
            />
            <Button onClick={read} disabled={loading}>
              {loading ? <Spinner className="h-4 w-4" /> : <Sheet className="h-4 w-4" />}
              读取
            </Button>
          </div>
        </CardContent>
      </Card>

      {data && (
        <>
          <div className="flex flex-wrap gap-2">
            {data.sheets.map((s, i) => (
              <Button
                key={s.name}
                size="sm"
                variant={i === activeSheet ? "default" : "outline"}
                onClick={() => setActiveSheet(i)}
              >
                {s.name}
                <Badge variant="outline" className="ml-1.5 text-[10px]">
                  {s.max_row}×{s.max_column}
                </Badge>
              </Button>
            ))}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">文件名</p>
                <p className="mt-1 font-mono text-sm">{data.file_name}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">大小</p>
                <p className="mt-1 font-mono text-sm">{formatBytes(data.file_size)}</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">工作表数</p>
                <p className="mt-1 font-mono text-sm">{data.sheets.length}</p>
              </CardContent>
            </Card>
          </div>
          {sheet && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">{sheet.name}</CardTitle>
                <CardDescription>{sheet.dimensions}</CardDescription>
              </CardHeader>
              <CardContent>
                {sheet.data.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 text-sm text-muted-foreground">
                    <AlertCircle className="mb-2 h-6 w-6 opacity-30" />
                    工作表为空
                  </div>
                ) : (
                  <div className="overflow-x-auto rounded-md border border-border/40">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-border/40 bg-muted/30">
                          {sheet.headers.map((h: unknown, i: number) => (
                            <th key={i} className="px-2 py-2 text-left font-medium">
                              {String(h ?? "")}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {sheet.data.slice(0, 50).map(
                          (
                            row: Array<{
                              column: string;
                              row: number;
                              value: unknown;
                              formula?: string;
                            }>,
                            ri: number,
                          ) => (
                            <tr key={ri} className="border-b border-border/20 last:border-0">
                              {row.map(
                                (
                                  cell: {
                                    column: string;
                                    row: number;
                                    value: unknown;
                                    formula?: string;
                                  },
                                  ci: number,
                                ) => (
                                  <td key={ci} className="px-2 py-1.5">
                                    {String(cell.value ?? "")}
                                  </td>
                                ),
                              )}
                            </tr>
                          ),
                        )}
                      </tbody>
                    </table>
                    {sheet.data.length > 50 && (
                      <p className="border-t border-border/30 bg-muted/20 px-2 py-1.5 text-center text-xs text-muted-foreground">
                        仅显示前 50 行（共 {sheet.max_row} 行）
                      </p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

function AnalyzeTab() {
  const [filePath, setFilePath] = React.useState("");
  const [type, setType] = React.useState<"summary" | "stats" | "correlation">("summary");
  const [data, setData] = React.useState<ExcelAnalyzeResponse | null>(null);
  const [loading, setLoading] = React.useState(false);

  async function run() {
    if (!filePath.trim()) {
      toast.error("请输入文件路径");
      return;
    }
    setLoading(true);
    try {
      const res = await api.excelAnalyze({ file_path: filePath.trim(), analysis_type: type });
      setData(res);
      toast.success("分析完成");
    } catch (e) {
      reportError(e, "分析失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">数据分析</CardTitle>
          <CardDescription>summary / stats / correlation</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              placeholder="/path/to/file.xlsx"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              className="flex-1"
            />
            <Select value={type} onValueChange={(v) => setType(v as typeof type)}>
              <SelectTrigger className="sm:w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="summary">概览</SelectItem>
                <SelectItem value="stats">统计</SelectItem>
                <SelectItem value="correlation">相关性</SelectItem>
              </SelectContent>
            </Select>
            <Button onClick={run} disabled={loading}>
              {loading ? <Spinner className="h-4 w-4" /> : <BarChart3 className="h-4 w-4" />}
              分析
            </Button>
          </div>
        </CardContent>
      </Card>
      {data && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">分析结果 · {data.analysis_type}</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-96 overflow-auto rounded-md bg-muted/30 p-3 text-xs">
              {JSON.stringify(data.results, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ChartTab() {
  const [filePath, setFilePath] = React.useState("");
  const [chartType, setChartType] = React.useState<"bar" | "line" | "pie" | "scatter">("bar");
  const [dataRange, setDataRange] = React.useState("A1:B10");
  const [outputPath, setOutputPath] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<{
    output_path: string;
    file_size: number;
    chart_type: string;
    data_points: number;
  } | null>(null);

  async function generate() {
    if (!filePath.trim() || !outputPath.trim()) {
      toast.error("请填写文件路径和输出路径");
      return;
    }
    setLoading(true);
    try {
      const res = await api.excelChart({
        file_path: filePath.trim(),
        chart_type: chartType,
        data_range: dataRange,
        output_path: outputPath.trim(),
      });
      setResult(res);
      toast.success("图表已生成");
    } catch (e) {
      reportError(e, "生成失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">生成图表</CardTitle>
          <CardDescription>从 Excel 数据生成可视化图表（输出 .png）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">数据文件 (.xlsx)</Label>
              <Input
                placeholder="/path/to/data.xlsx"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">数据范围</Label>
              <Input
                placeholder="A1:B10"
                value={dataRange}
                onChange={(e) => setDataRange(e.target.value)}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">图表类型</Label>
              <Select value={chartType} onValueChange={(v) => setChartType(v as typeof chartType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bar">柱状图</SelectItem>
                  <SelectItem value="line">折线图</SelectItem>
                  <SelectItem value="pie">饼图</SelectItem>
                  <SelectItem value="scatter">散点图</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">输出图片路径</Label>
              <Input
                placeholder="/path/to/chart.png"
                value={outputPath}
                onChange={(e) => setOutputPath(e.target.value)}
              />
            </div>
          </div>
          <Button onClick={generate} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <BarChart3 className="h-4 w-4" />}
            生成图表
          </Button>
        </CardContent>
      </Card>
      {result && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-success">
              <Save className="h-4 w-4" /> 已生成
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-muted-foreground">类型：</span>
                {result.chart_type}
              </div>
              <div>
                <span className="text-muted-foreground">数据点：</span>
                {result.data_points}
              </div>
              <div className="col-span-2 truncate">
                <span className="text-muted-foreground">路径：</span>
                <span className="font-mono">{result.output_path}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function WriteTab() {
  const [filePath, setFilePath] = React.useState("/tmp/data-ai-demo.xlsx");
  const [sheetName, setSheetName] = React.useState("Sheet1");
  const [csvText, setCsvText] = React.useState(
    "name,age,city\nAlice,30,Beijing\nBob,25,Shanghai\nCarol,28,Shenzhen",
  );
  const [loading, setLoading] = React.useState(false);
  const [result, setResult] = React.useState<{
    file_path: string;
    file_size: number;
    rows: number;
    columns: number;
    success: boolean;
  } | null>(null);

  async function create() {
    if (!filePath.trim()) {
      toast.error("请输入文件路径");
      return;
    }
    setLoading(true);
    try {
      // 将 CSV 文本解析为 headers + rows
      const lines = csvText
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter((l) => l.length > 0);
      if (lines.length === 0) {
        throw new Error("数据为空");
      }
      const headers = lines[0].split(",").map((s) => s.trim());
      const rows = lines.slice(1).map((line) =>
        line.split(",").map((cell) => {
          const v = cell.trim();
          const n = Number(v);
          return Number.isNaN(n) ? v : n;
        }),
      );

      const res = await api.excelWrite({
        file_path: filePath.trim(),
        data: { headers, rows },
        sheet_name: sheetName.trim() || "Sheet1",
      });
      setResult(res);
      toast.success("创建成功", {
        description: `${res.rows} 行 × ${res.columns} 列`,
      });
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
          <CardTitle className="flex items-center gap-2 text-base">
            <FileSpreadsheet className="h-4 w-4" /> 创建新工作簿
          </CardTitle>
          <CardDescription>
            输入 CSV 格式数据，第一行作为表头，其余为数据行。生成 .xlsx 文件。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">输出文件路径</Label>
              <Input
                placeholder="/path/to/output.xlsx"
                value={filePath}
                onChange={(e) => setFilePath(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">工作表名</Label>
              <Input
                placeholder="Sheet1"
                value={sheetName}
                onChange={(e) => setSheetName(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">CSV 数据</Label>
            <Textarea
              rows={8}
              placeholder="name,age,city&#10;Alice,30,Beijing&#10;Bob,25,Shanghai"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
              className="font-mono text-xs"
            />
          </div>
          <Button onClick={create} disabled={loading} className="w-full">
            {loading ? <Spinner className="h-4 w-4" /> : <Save className="h-4 w-4" />}
            创建 Excel 文件
          </Button>
        </CardContent>
      </Card>
      {result && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-success">
              <Save className="h-4 w-4" /> 已创建
            </div>
            <div className="mt-2 grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-muted-foreground">行数：</span>
                {result.rows}
              </div>
              <div>
                <span className="text-muted-foreground">列数：</span>
                {result.columns}
              </div>
              <div>
                <span className="text-muted-foreground">大小：</span>
                {formatBytes(result.file_size)}
              </div>
              <div className="col-span-2 truncate">
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
