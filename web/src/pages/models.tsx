"use client";

import { EmptyState } from "@/components/shared/empty-state";
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
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { getClient } from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import type { ModelsResponse } from "@/lib/types/api";
import { formatDuration } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Cpu, Loader2, Play, Send, Sparkles, TestTube2, Zap } from "lucide-react";
import * as React from "react";

const PROVIDER_COLOR: Record<string, string> = {
  openai: "bg-muted",
  anthropic: "bg-muted",
  google: "bg-muted",
  deepseek: "bg-muted",
  ollama: "bg-muted",
  azure: "bg-muted",
  ppio: "bg-muted",
  jiekouai: "bg-muted",
  unknown: "bg-muted",
};

export function ModelsPage() {
  const query = useQuery<ModelsResponse>({
    queryKey: ["models"],
    queryFn: () => getClient().listModels(),
  });
  const [testModel, setTestModel] = React.useState("");
  const [prompt, setPrompt] = React.useState("用一句话介绍 DATA-AI 框架");
  const [testResult, setTestResult] = React.useState<{
    text: string;
    duration: number;
    tokens: number;
  } | null>(null);
  const [testing, setTesting] = React.useState(false);

  const models: Array<{ id: string; object: string; created: number; owned_by: string }> =
    (query.data?.data as any) ?? [];

  const test = async () => {
    if (!testModel || !prompt.trim()) return;
    setTesting(true);
    setTestResult(null);
    const start = performance.now();
    try {
      const res = await getClient().chatCompletion({
        model: testModel,
        messages: [{ role: "user", content: prompt }],
      });
      const dur = performance.now() - start;
      setTestResult({
        text: res.choices[0]?.message.content ?? "(空响应)",
        duration: dur,
        tokens: res.usage?.total_tokens ?? 0,
      });
      toast.success("测试成功", {
        description: `${res.usage?.total_tokens ?? 0} tokens · ${formatDuration(dur)}`,
      });
    } catch (e) {
      setTestResult(null);
      reportError(e, "测试模型");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="模型管理"
        description={`${models.length} 个模型 · 来自 ${new Set(models.map((m) => m.owned_by)).size} 个 provider`}
        icon={<Cpu className="h-5 w-5" />}
      />

      {models.length === 0 ? (
        <EmptyState
          icon={<Cpu className="h-6 w-6" />}
          title="还没有模型"
          description="请在后端配置 LLM provider 和模型"
        />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {models.map((m, i) => {
            const colorClass = PROVIDER_COLOR[m.owned_by] ?? PROVIDER_COLOR.unknown;
            return (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <Card
                  className={`group cursor-pointer transition-colors hover:border-primary/40 ${
                    testModel === m.id ? "border-primary" : ""
                  }`}
                  onClick={() => setTestModel(m.id)}
                >
                  <CardContent className="p-4">
                    <div
                      className={`mb-2 flex h-8 w-8 items-center justify-center rounded-md ring-1 ring-border ${colorClass}`}
                    >
                      <Sparkles className="h-4 w-4 text-primary" />
                    </div>
                    <p className="truncate font-mono text-sm font-semibold">{m.id}</p>
                    <div className="mt-1 flex items-center gap-1.5">
                      <Badge variant="outline" className="text-[10px]">
                        {m.owned_by}
                      </Badge>
                      <Badge variant="success" className="ml-auto text-[10px]">
                        <span className="mr-1 h-1 w-1 rounded-full bg-success" />
                        可用
                      </Badge>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <TestTube2 className="h-4 w-4" /> 模型测试
          </CardTitle>
          <CardDescription>点击上方模型卡片选择，然后发送测试 prompt</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">模型</Label>
              <Select value={testModel} onValueChange={setTestModel}>
                <SelectTrigger>
                  <SelectValue placeholder="选择模型" />
                </SelectTrigger>
                <SelectContent>
                  {models.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.id} ({m.owned_by})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Prompt</Label>
            <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} />
          </div>
          <Button
            variant="default"
            onClick={test}
            disabled={testing || !testModel || !prompt.trim()}
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            发送测试
          </Button>
          {testResult && (
            <div className="rounded-md border border-border bg-muted/20 p-3">
              <div className="mb-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                <Badge variant="info">{testModel}</Badge>
                <span>{testResult.tokens} tokens</span>
                <span>· {formatDuration(testResult.duration)}</span>
              </div>
              <p className="text-sm leading-relaxed text-pretty">{testResult.text}</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
