"use client";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { type RagDocument, type RagSearchResult, api } from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { formatBytes, formatRelativeTime } from "@/lib/utils";
import { AlertCircle, Database, FileText, Filter, Search, Trash2, Upload } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router-dom";

const TYPE_COLORS: Record<string, string> = {
  pdf: "destructive",
  docx: "info",
  txt: "muted-foreground",
  md: "success",
  html: "warning",
  pptx: "warning",
  xlsx: "primary",
};

export function RagPage() {
  const navigate = useNavigate();
  const [docs, setDocs] = React.useState<RagDocument[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [uploading, setUploading] = React.useState(false);
  const [query, setQuery] = React.useState("");
  const [typeFilter, setTypeFilter] = React.useState<string>("");
  const [searching, setSearching] = React.useState(false);
  const [results, setResults] = React.useState<RagSearchResult[]>([]);
  const fileRef = React.useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      const res = await api.listRagDocuments();
      setDocs(res.data);
    } catch (e) {
      reportError(e, "加载文档");
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  async function upload(file: File) {
    setUploading(true);
    try {
      await api.uploadRagDocument(file);
      toast.success("上传成功", { description: file.name });
      await load();
    } catch (e) {
      reportError(e, "上传文档");
    } finally {
      setUploading(false);
    }
  }

  async function remove(id: string, name: string) {
    if (!confirm(`确认删除文档 "${name}" 吗？`)) return;
    try {
      await api.deleteRagDocument(id);
      toast.success("已删除", { description: name });
      await load();
    } catch (e) {
      reportError(e, "删除文档");
    }
  }

  async function search() {
    if (!query.trim()) {
      toast.error("请输入查询");
      return;
    }
    setSearching(true);
    try {
      const res = await api.searchRag({ query, top_k: 8 });
      setResults(res.results);
      toast.success(`检索到 ${res.results.length} 个片段`, {
        description: `耗时 ${res.duration_ms}ms`,
      });
    } catch (e) {
      reportError(e, "检索文档");
    } finally {
      setSearching(false);
    }
  }

  const filtered = typeFilter ? docs.filter((d) => d.type === typeFilter) : docs;

  return (
    <div className="space-y-6">
      <PageHeader
        title="RAG 知识库"
        description="上传文档、自动分块、向量化、语义检索"
        icon={<Database className="h-5 w-5" />}
        accent="cyan"
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">语义检索</CardTitle>
          <CardDescription>基于嵌入向量的混合检索</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              placeholder="例如：什么是 ReAct 模式？"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              className="flex-1"
            />
            <Button onClick={search} disabled={searching}>
              {searching ? <Spinner className="h-4 w-4" /> : <Search className="h-4 w-4" />}
              检索
            </Button>
          </div>
          {results.length > 0 && (
            <div className="space-y-2">
              {results.map((r) => (
                <div
                  key={r.id}
                  className="rounded-md border border-border/40 bg-muted/20 p-3 text-sm"
                >
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span className="truncate">
                      {r.document_name} · 块 #{r.chunk_index}
                    </span>
                    <Badge variant="accent">score: {r.score}</Badge>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm">{r.content}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <select
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="">全部类型</option>
            <option value="pdf">PDF</option>
            <option value="docx">Word</option>
            <option value="txt">TXT</option>
            <option value="md">Markdown</option>
            <option value="html">HTML</option>
            <option value="pptx">PPT</option>
            <option value="xlsx">Excel</option>
          </select>
        </div>
        <div>
          <input
            ref={fileRef}
            type="file"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload(f);
              e.target.value = "";
            }}
          />
          <Button onClick={() => fileRef.current?.click()} disabled={uploading}>
            {uploading ? <Spinner className="h-4 w-4" /> : <Upload className="h-4 w-4" />}
            上传文档
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Spinner className="h-5 w-5" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/60 py-12 text-sm text-muted-foreground">
          <FileText className="mb-2 h-8 w-8 opacity-30" />
          {docs.length === 0 ? "知识库为空，上传第一个文档吧" : "没有匹配的文档"}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((d) => (
            <Card
              key={d.id}
              className="cursor-pointer transition-colors hover:border-primary/40"
              onClick={() => navigate(`/rag/${d.id}`)}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant={(TYPE_COLORS[d.type] || "zinc") as never}>
                        {d.type.toUpperCase()}
                      </Badge>
                      <Badge variant="outline" className="text-[10px]">
                        {d.status === "ready"
                          ? "已就绪"
                          : d.status === "processing"
                            ? "处理中"
                            : "错误"}
                      </Badge>
                    </div>
                    <p className="mt-2 truncate text-sm font-medium">{d.name}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatBytes(d.size)} · {d.chunks} 块 · {formatRelativeTime(d.uploaded_at)}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation();
                      remove(d.id, d.name);
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
