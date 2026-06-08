"use client";

import { Markdown } from "@/components/chat/markdown";
import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { getClient } from "@/lib/api/client";
import type { JsonSchema, ToolExecuteResponse, ToolInfo, ToolsResponse } from "@/lib/types/api";
import { formatDuration, safeJSON } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronRight, Loader2, Play, Wrench } from "lucide-react";
import * as React from "react";
import { Link, useParams } from "react-router-dom";

const SEED: Record<string, ToolInfo> = {
  bash: {
    name: "bash",
    description: "在沙箱中执行 shell 命令（ls / cat / grep / curl 等）",
    category: "system",
    parameters: {
      type: "object",
      properties: {
        command: { type: "string", description: "shell 命令字符串" },
        timeout: { type: "number", description: "超时（秒）", default: 30 },
      },
      required: ["command"],
    },
  },
  python_execute: {
    name: "python_execute",
    description: "在沙箱中执行 Python 代码并返回 stdout",
    category: "system",
    parameters: {
      type: "object",
      properties: {
        code: { type: "string", description: "Python 代码" },
      },
      required: ["code"],
    },
  },
  word_read: {
    name: "word_read",
    description: "读取 Word 文档内容、段落、表格、图片元数据",
    category: "office",
    parameters: {
      type: "object",
      properties: {
        file_path: { type: "string", description: ".docx 文件路径" },
        extract_tables: { type: "boolean", default: true },
        extract_images: { type: "boolean", default: false },
      },
      required: ["file_path"],
    },
  },
};

export function ToolDetailPage() {
  const { toolName } = useParams<{ toolName: string }>();
  const decoded = toolName ? decodeURIComponent(toolName) : "";

  const toolsQuery = useQuery<ToolsResponse>({
    queryKey: ["tools"],
    queryFn: () => getClient().listTools(),
  });

  const tool: ToolInfo = toolsQuery.data?.data.find((t) => t.name === decoded) ?? {
    name: decoded,
    description: toolsQuery.isLoading ? "加载中..." : "未在注册中心找到此工具",
    category: "uncategorized",
    parameters: { type: "object", properties: {}, required: [] },
  };

  const [params, setParams] = React.useState<Record<string, unknown>>({});
  const [running, setRunning] = React.useState(false);
  const [result, setResult] = React.useState<ToolExecuteResponse | null>(null);

  React.useEffect(() => {
    const initial: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(tool.parameters.properties ?? {})) {
      if (v && typeof v === "object" && "default" in v) initial[k] = v.default;
    }
    setParams(initial);
  }, [tool]);

  const run = async () => {
    setRunning(true);
    setResult(null);
    try {
      const res = await getClient().executeTool({ tool: tool.name, parameters: params });
      setResult(res);
      if (res.success) {
        toast.success("执行成功", { description: `${formatDuration(res.execution_time_ms)}` });
      } else {
        toast.error("执行失败", { description: res.error });
      }
    } catch (e) {
      setResult({
        success: false,
        error: (e as Error).message,
        result: null,
        execution_time_ms: 0,
      });
      toast.error("请求失败", { description: (e as Error).message });
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <Button asChild variant="ghost" size="sm">
        <Link to="/tools">
          <ArrowLeft className="h-3 w-3" /> 返回工具广场
        </Link>
      </Button>

      <PageHeader
        title={tool.name}
        description={tool.description}
        icon={<Wrench className="h-5 w-5" />}
        actions={<Badge variant="outline">{tool.category ?? "uncategorized"}</Badge>}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">参数 Schema</CardTitle>
            <CardDescription>必填字段以 * 标记</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(tool.parameters.properties ?? {}).length === 0 ? (
              <p className="text-sm text-muted-foreground">无参数</p>
            ) : (
              Object.entries(tool.parameters.properties ?? {}).map(([k, schema]) => {
                const isRequired = tool.parameters.required?.includes(k);
                const s = schema as JsonSchema;
                return (
                  <div key={k} className="space-y-1.5">
                    <Label className="text-xs">
                      {k}
                      {isRequired && <span className="ml-1 text-destructive">*</span>}
                      <span className="ml-2 text-muted-foreground">({s.type})</span>
                    </Label>
                    {s.description && (
                      <p className="text-[11px] text-muted-foreground">{s.description}</p>
                    )}
                    {s.type === "string" && (s.enum?.length ?? 0) > 0 ? (
                      <select
                        value={(params[k] as string) ?? ""}
                        onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                        className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
                      >
                        <option value="">--</option>
                        {s.enum?.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    ) : s.type === "string" ? (
                      s.description && s.description.length > 50 ? (
                        <Textarea
                          rows={4}
                          value={(params[k] as string) ?? ""}
                          onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                        />
                      ) : (
                        <Input
                          value={(params[k] as string) ?? ""}
                          onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.value }))}
                        />
                      )
                    ) : s.type === "number" || s.type === "integer" ? (
                      <Input
                        type="number"
                        value={(params[k] as number) ?? ""}
                        onChange={(e) => setParams((p) => ({ ...p, [k]: Number(e.target.value) }))}
                      />
                    ) : s.type === "boolean" ? (
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={Boolean(params[k])}
                          onChange={(e) => setParams((p) => ({ ...p, [k]: e.target.checked }))}
                          className="h-4 w-4 accent-primary"
                        />
                        {String(params[k] ?? false)}
                      </label>
                    ) : (
                      <Textarea
                        rows={4}
                        value={JSON.stringify(params[k] ?? {}, null, 2)}
                        onChange={(e) => {
                          const parsed = safeJSON<unknown>(e.target.value, {});
                          setParams((p) => ({ ...p, [k]: parsed }));
                        }}
                      />
                    )}
                  </div>
                );
              })
            )}

            <Button className="w-full" variant="default" onClick={run} disabled={running}>
              {running ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> 执行中
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" /> 试运行
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">结果</CardTitle>
            {result && (
              <CardDescription>
                {result.success ? "成功" : "失败"} · 耗时 {formatDuration(result.execution_time_ms)}
              </CardDescription>
            )}
          </CardHeader>
          <CardContent>
            {!result ? (
              <p className="text-sm text-muted-foreground">运行后将在此显示结果</p>
            ) : result.error ? (
              <div className="border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {result.error}
              </div>
            ) : (
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs">
                {JSON.stringify(result.result, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
