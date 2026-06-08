"use client";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toaster";
import { type RagDocDetailResponse, type RagSearchResult, api } from "@/lib/api/client";
import { reportError } from "@/lib/errors";
import { formatBytes, formatRelativeTime } from "@/lib/utils";
import { ChevronLeft, Database, FileText, Layers, Search, Settings2 } from "lucide-react";
import * as React from "react";
import { useNavigate, useParams } from "react-router-dom";

export function RagDocumentPage() {
  const { docId: id = "" } = useParams();
  const navigate = useNavigate();
  const [data, setData] = React.useState<RagDocDetailResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [query, setQuery] = React.useState("");
  const [searching, setSearching] = React.useState(false);
  const [results, setResults] = React.useState<RagSearchResult[]>([]);

  React.useEffect(() => {
    let mounted = true;
    setLoading(true);
    api
      .getRagDocument(id)
      .then((d) => mounted && setData(d))
      .catch((e) => reportError(e, "加载 RAG 文档"))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [id]);

  async function searchInDoc() {
    if (!query.trim()) {
      toast.error("请输入查询");
      return;
    }
    setSearching(true);
    try {
      const res = await api.searchRag({ query, top_k: 5, document_ids: [id] });
      setResults(res.results);
    } catch (e) {
      reportError(e, "检索 RAG 文档");
    } finally {
      setSearching(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (!data || !data.document) {
    return <div className="py-24 text-center text-sm text-muted-foreground">文档不存在</div>;
  }

  const { document, chunks } = data;

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={() => navigate("/rag")}>
        <ChevronLeft className="h-4 w-4" /> 返回
      </Button>
      <PageHeader
        title={document.name}
        description={`${formatBytes(document.size)} · ${chunks.length} 块 · ${formatRelativeTime(document.uploaded_at)}`}
        icon={<Database className="h-5 w-5" />}
        accent="cyan"
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground">类型</p>
            <p className="mt-1 text-sm font-medium">{document.type.toUpperCase()}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground">状态</p>
            <p className="mt-1 text-sm font-medium">{document.status}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground">嵌入模型</p>
            <p className="mt-1 text-sm font-medium">{document.embedder}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <p className="text-xs text-muted-foreground">向量维度</p>
            <p className="mt-1 text-sm font-medium">{document.vector_dim}</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="chunks">
        <TabsList>
          <TabsTrigger value="chunks">
            <Layers className="h-3.5 w-3.5" /> 块 ({chunks.length})
          </TabsTrigger>
          <TabsTrigger value="metadata">
            <Settings2 className="h-3.5 w-3.5" /> 元数据
          </TabsTrigger>
          <TabsTrigger value="search">
            <Search className="h-3.5 w-3.5" /> 检索测试
          </TabsTrigger>
        </TabsList>
        <TabsContent value="chunks" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              {chunks.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  该文档没有分块
                </div>
              ) : (
                <div className="space-y-2">
                  {chunks.slice(0, 50).map((c) => (
                    <div
                      key={c.id}
                      className="rounded-md border border-border/40 bg-muted/20 p-3 text-sm"
                    >
                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <Badge variant="outline">块 #{c.index}</Badge>
                        <span>{c.tokens} tokens</span>
                      </div>
                      <p className="mt-2 whitespace-pre-wrap text-sm">{c.content}</p>
                    </div>
                  ))}
                  {chunks.length > 50 && (
                    <p className="pt-2 text-center text-xs text-muted-foreground">
                      仅显示前 50 块（共 {chunks.length}）
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="metadata" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              <pre className="max-h-96 overflow-auto rounded-md bg-muted/20 p-3 text-xs">
                {JSON.stringify(document.metadata || {}, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="search" className="mt-4">
          <Card>
            <CardContent className="pt-6 space-y-3">
              <div className="flex gap-2">
                <input
                  className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                  placeholder="查询"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && searchInDoc()}
                />
                <Button onClick={searchInDoc} disabled={searching}>
                  {searching ? <Spinner className="h-4 w-4" /> : <Search className="h-4 w-4" />}
                  检索
                </Button>
              </div>
              <div className="space-y-2">
                {results.map((r) => (
                  <div
                    key={r.id}
                    className="rounded-md border border-border/40 bg-muted/20 p-3 text-sm"
                  >
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>块 #{r.chunk_index}</span>
                      <Badge variant="accent">score: {r.score}</Badge>
                    </div>
                    <p className="mt-2 whitespace-pre-wrap text-sm">{r.content}</p>
                  </div>
                ))}
                {results.length === 0 && !searching && (
                  <p className="py-8 text-center text-sm text-muted-foreground">
                    点击检索以测试查询
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
