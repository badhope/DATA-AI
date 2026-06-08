"use client";

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
import { toast } from "@/components/ui/toaster";
import {
  type SandboxExecuteResponse,
  type SandboxFileNode,
  type SandboxInfo,
  type SandboxSnapshot,
  api,
} from "@/lib/api/client";
import { SANDBOX_TEMPLATES } from "@/lib/templates";
import { reportError } from "@/lib/errors";
import { formatBytes, formatRelativeTime } from "@/lib/utils";
import Editor from "@monaco-editor/react";
import {
  Box,
  Camera,
  ChevronLeft,
  ChevronRight,
  File as FileIcon,
  Folder,
  FolderTree,
  History,
  Loader2,
  Play,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Terminal,
  Trash2,
} from "lucide-react";
import * as React from "react";
import { useNavigate, useParams } from "react-router-dom";

const LANG_MONACO_MAP: Record<string, string> = {
  python: "python",
  javascript: "javascript",
  bash: "shell",
  go: "go",
  rust: "rust",
};

const DEFAULT_CODE: Record<string, string> = {
  python: `# 欢迎使用代码沙箱
# 在这里编写 Python 代码

import math
print("Hello, DATA-AI Sandbox!")
print(f"π = {math.pi:.6f}")

for i in range(5):
    print(f"i = {i}")
`,
  javascript: `// 欢迎使用代码沙箱
console.log("Hello, DATA-AI Sandbox!");

const items = [1, 2, 3, 4, 5];
const sum = items.reduce((a, b) => a + b, 0);
console.log("sum =", sum);
`,
  bash: `#!/bin/bash
echo "Hello, DATA-AI Sandbox!"
echo "Current dir: $(pwd)"
ls -la
`,
  go: `package main
import "fmt"
func main() {
    fmt.Println("Hello, DATA-AI Sandbox!")
}
`,
  rust: `fn main() {
    println!("Hello, DATA-AI Sandbox!");
}
`,
};

export function SandboxDetailPage() {
  const { sandboxId: id = "" } = useParams();
  const navigate = useNavigate();
  const [sb, setSb] = React.useState<SandboxInfo | null>(null);
  const [loading, setLoading] = React.useState(true);

  const [language, setLanguage] = React.useState<"python" | "javascript" | "bash" | "go" | "rust">(
    "python",
  );
  const [code, setCode] = React.useState(DEFAULT_CODE.python);
  const [executing, setExecuting] = React.useState(false);
  const [execResult, setExecResult] = React.useState<SandboxExecuteResponse | null>(null);

  const [files, setFiles] = React.useState<SandboxFileNode[]>([]);
  const [currentFile, setCurrentFile] = React.useState<string>("");
  const [fileContent, setFileContent] = React.useState<string>("");
  const [loadingFile, setLoadingFile] = React.useState(false);
  const [savingFile, setSavingFile] = React.useState(false);
  const [filesCollapsed, setFilesCollapsed] = React.useState(false);

  const [snapshots, setSnapshots] = React.useState<SandboxSnapshot[]>([]);
  const [snapshotName, setSnapshotName] = React.useState("");
  const [snapshotDesc, setSnapshotDesc] = React.useState("");
  const [openSnapshotDialog, setOpenSnapshotDialog] = React.useState(false);

  async function loadSandbox() {
    setLoading(true);
    try {
      const res = await api.getSandbox(id);
      setSb(res);
    } catch (e) {
      reportError(e, "加载沙箱");
    } finally {
      setLoading(false);
    }
  }

  async function loadFiles() {
    try {
      const res = await api.listSandboxFiles(id, ".");
      setFiles(res.tree);
    } catch (e) {
      // 没有文件时静默
    }
  }

  async function loadSnapshots() {
    try {
      const res = await api.listSandboxSnapshots(id);
      setSnapshots(res.data);
    } catch (e) {
      // 静默
    }
  }

  React.useEffect(() => {
    loadSandbox();
    loadFiles();
    loadSnapshots();
  }, [id]);

  // 监听来自 chat 的运行代码事件
  React.useEffect(() => {
    function onRun(e: Event) {
      const detail = (e as CustomEvent).detail as {
        code: string;
        language: string;
        sandboxId?: string;
      };
      if (!detail) return;
      if (detail.sandboxId && detail.sandboxId !== id) return;
      setLanguage(detail.language as typeof language);
      setCode(detail.code);
      toast.success("已加载代码到编辑器");
    }
    window.addEventListener("data-ai:run-code", onRun);
    return () => window.removeEventListener("data-ai:run-code", onRun);
  }, [id]);

  // 自动重置默认代码当切换语言
  function changeLanguage(l: typeof language) {
    setLanguage(l);
    setCode(DEFAULT_CODE[l]);
  }

  async function execute() {
    setExecuting(true);
    setExecResult(null);
    try {
      const res = await api.executeInSandbox(id, {
        language,
        code,
        timeout: sb?.timeout || 30,
      });
      setExecResult(res);
      if (res.success) {
        toast.success("执行成功", {
          description: `退出码 ${res.exit_code} · ${res.duration_ms}ms`,
        });
      } else {
        toast.error("执行失败", { description: `退出码 ${res.exit_code}` });
      }
      // 重新加载文件，因为执行可能改变了文件
      loadFiles();
    } catch (e) {
      // exit_code != 0 不算网络错，要明确区分"网络/超时"和"执行失败"
      if (e instanceof Error && /exit code/i.test(e.message)) {
        reportError(e, "执行沙箱代码");
      } else {
        reportError(e, "执行沙箱代码");
      }
    } finally {
      setExecuting(false);
    }
  }

  async function openFile(path: string) {
    setCurrentFile(path);
    setLoadingFile(true);
    try {
      const res = await api.getSandboxFile(id, path);
      setFileContent(res.content);
    } catch (e) {
      reportError(e, "读取文件");
    } finally {
      setLoadingFile(false);
    }
  }

  async function saveFile() {
    if (!currentFile) return;
    setSavingFile(true);
    try {
      await api.saveSandboxFile(id, currentFile, fileContent);
      toast.success("已保存");
    } catch (e) {
      reportError(e, "保存文件");
    } finally {
      setSavingFile(false);
    }
  }

  async function createSnapshot() {
    if (!snapshotName.trim()) {
      toast.error("请输入快照名");
      return;
    }
    try {
      await api.createSandboxSnapshot(id, snapshotName.trim(), snapshotDesc);
      toast.success("快照已创建");
      setOpenSnapshotDialog(false);
      setSnapshotName("");
      setSnapshotDesc("");
      await loadSnapshots();
    } catch (e) {
      reportError(e, "创建快照");
    }
  }

  async function restoreSnapshot(name: string) {
    if (!confirm(`确认恢复到快照 "${name}" 吗？当前工作区内容将被覆盖`)) return;
    try {
      await api.restoreSandboxSnapshot(id, name);
      toast.success("已恢复");
      loadFiles();
    } catch (e) {
      reportError(e, "恢复快照");
    }
  }

  async function deleteSnapshot(name: string) {
    if (!confirm(`确认删除快照 "${name}" 吗？`)) return;
    try {
      await api.deleteSandboxSnapshot(id, name);
      await loadSnapshots();
    } catch (e) {
      reportError(e, "删除快照");
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }
  if (!sb) {
    return <div className="py-24 text-center text-sm text-muted-foreground">沙箱不存在</div>;
  }

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate("/sandbox")}>
        <ChevronLeft className="h-4 w-4" /> 返回
      </Button>
      <PageHeader
        title={sb.name}
        description={`${sb.type} · ${sb.image || "default"} · ${sb.status}`}
        icon={<Box className="h-5 w-5" />}
        accent="amber"
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">状态</p>
            <p className="mt-1 text-sm font-medium">{sb.status}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">运行时长</p>
            <p className="mt-1 text-sm font-medium">{sb.uptime}s</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">CPU / 内存</p>
            <p className="mt-1 text-sm font-medium">
              {sb.cpu || 0}% / {sb.memory || 0}MB
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <p className="text-xs text-muted-foreground">网络</p>
            <p className="mt-1 text-sm font-medium">{sb.network ? "启用" : "禁用"}</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="editor">
        <TabsList>
          <TabsTrigger value="editor">
            <Terminal className="h-3.5 w-3.5" /> 代码
          </TabsTrigger>
          <TabsTrigger value="files">
            <FolderTree className="h-3.5 w-3.5" /> 文件
          </TabsTrigger>
          <TabsTrigger value="snapshots">
            <History className="h-3.5 w-3.5" /> 快照 ({snapshots.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="editor" className="mt-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Select value={language} onValueChange={(v) => changeLanguage(v as typeof language)}>
              <SelectTrigger className="w-40">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="python">Python</SelectItem>
                <SelectItem value="javascript">JavaScript</SelectItem>
                <SelectItem value="bash">Bash</SelectItem>
                <SelectItem value="go">Go</SelectItem>
                <SelectItem value="rust">Rust</SelectItem>
              </SelectContent>
            </Select>
            {/* 模板预设下拉 */}
            <Select
              onValueChange={(tid) => {
                const t = SANDBOX_TEMPLATES.find((x) => x.id === tid);
                if (!t) return;
                changeLanguage(t.language);
                setCode(t.code);
                toast.success("已加载模板", { description: `${t.emoji} ${t.name}` });
              }}
            >
              <SelectTrigger className="w-44">
                <SelectValue placeholder={<><Sparkles className="mr-1 inline h-3.5 w-3.5" /> 选模板</>} />
              </SelectTrigger>
              <SelectContent>
                {SANDBOX_TEMPLATES.map((t) => (
                  <SelectItem key={t.id} value={t.id}>
                    <span className="mr-1">{t.emoji}</span>
                    {t.name}（{t.language}）
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={execute} disabled={executing}>
              {executing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              运行
            </Button>
          </div>

          <Card className="overflow-hidden p-0">
            <Editor
              height="380px"
              language={LANG_MONACO_MAP[language]}
              value={code}
              onChange={(v) => setCode(v || "")}
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 2,
              }}
            />
          </Card>

          {execResult && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">输出</CardTitle>
                  <div className="flex items-center gap-2 text-xs">
                    <Badge variant={execResult.success ? "success" : "error"}>
                      exit {execResult.exit_code}
                    </Badge>
                    <span className="text-muted-foreground">{execResult.duration_ms}ms</span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {execResult.stdout && (
                  <div>
                    <p className="mb-1 text-xs text-muted-foreground">stdout</p>
                    <pre className="max-h-60 overflow-auto rounded-md bg-muted/30 p-3 text-xs">
                      {execResult.stdout}
                    </pre>
                  </div>
                )}
                {execResult.stderr && (
                  <div>
                    <p className="mb-1 text-xs text-destructive">stderr</p>
                    <pre className="max-h-60 overflow-auto rounded-md bg-destructive/10 p-3 text-xs text-destructive">
                      {execResult.stderr}
                    </pre>
                  </div>
                )}
                {!execResult.stdout && !execResult.stderr && (
                  <p className="text-xs text-muted-foreground">（无输出）</p>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="files" className="mt-4">
          <div className="grid grid-cols-12 gap-3">
            <div
              className={filesCollapsed ? "col-span-1" : "col-span-12 sm:col-span-4 lg:col-span-3"}
            >
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    {!filesCollapsed && <CardTitle className="text-sm">文件树</CardTitle>}
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setFilesCollapsed((c) => !c)}
                    >
                      {filesCollapsed ? (
                        <ChevronRight className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronLeft className="h-3.5 w-3.5" />
                      )}
                    </Button>
                  </div>
                </CardHeader>
                {!filesCollapsed && (
                  <CardContent>
                    {files.length === 0 ? (
                      <p className="text-xs text-muted-foreground">空工作区</p>
                    ) : (
                      <div className="space-y-0.5 text-sm">
                        {files.map((f) => (
                          <FileTreeNode
                            key={f.path}
                            node={f}
                            depth={0}
                            onOpen={openFile}
                            currentFile={currentFile}
                          />
                        ))}
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            </div>
            <div
              className={filesCollapsed ? "col-span-11" : "col-span-12 sm:col-span-8 lg:col-span-9"}
            >
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm font-mono">{currentFile || "选择文件"}</CardTitle>
                    {currentFile && (
                      <Button size="sm" onClick={saveFile} disabled={savingFile}>
                        {savingFile ? (
                          <Spinner className="h-3.5 w-3.5" />
                        ) : (
                          <Save className="h-3.5 w-3.5" />
                        )}
                        保存
                      </Button>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {loadingFile ? (
                    <div className="flex items-center justify-center py-12">
                      <Spinner className="h-5 w-5" />
                    </div>
                  ) : !currentFile ? (
                    <div className="py-12 text-center text-sm text-muted-foreground">
                      从左侧选择文件进行编辑
                    </div>
                  ) : (
                    <Editor
                      height="380px"
                      language={
                        LANG_MONACO_MAP[
                          fileContent.startsWith("#!") || fileContent.includes("def ")
                            ? "python"
                            : "plaintext"
                        ]
                      }
                      value={fileContent}
                      onChange={(v) => setFileContent(v || "")}
                      theme="vs-dark"
                      options={{
                        minimap: { enabled: false },
                        fontSize: 13,
                        lineNumbers: "on",
                        scrollBeyondLastLine: false,
                        automaticLayout: true,
                        tabSize: 2,
                      }}
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="snapshots" className="mt-4">
          <div className="mb-3 flex justify-end">
            <Dialog open={openSnapshotDialog} onOpenChange={setOpenSnapshotDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Camera className="h-4 w-4" /> 创建快照
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>创建快照</DialogTitle>
                  <DialogDescription>将当前工作区所有文件打包</DialogDescription>
                </DialogHeader>
                <div className="space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">名称</Label>
                    <Input
                      value={snapshotName}
                      onChange={(e) => setSnapshotName(e.target.value)}
                      placeholder="v1.0-baseline"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">描述（可选）</Label>
                    <Input value={snapshotDesc} onChange={(e) => setSnapshotDesc(e.target.value)} />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="ghost" onClick={() => setOpenSnapshotDialog(false)}>
                    取消
                  </Button>
                  <Button onClick={createSnapshot}>
                    <Plus className="h-4 w-4" /> 创建
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
          {snapshots.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border/60 py-12 text-sm text-muted-foreground">
              <History className="mb-2 h-8 w-8 opacity-30" />
              还没有快照
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {snapshots.map((s) => (
                <Card key={s.name}>
                  <CardContent className="p-3">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{s.name}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {formatBytes(s.size)} · {formatRelativeTime(s.created_at)}
                        </p>
                        {s.description && (
                          <p className="mt-1 text-xs text-muted-foreground">{s.description}</p>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Button variant="ghost" size="icon" onClick={() => restoreSnapshot(s.name)}>
                          <RotateCcw className="h-3.5 w-3.5 text-primary" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => deleteSnapshot(s.name)}>
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FileTreeNode({
  node,
  depth,
  onOpen,
  currentFile,
}: {
  node: SandboxFileNode;
  depth: number;
  onOpen: (path: string) => void;
  currentFile: string;
}) {
  const [open, setOpen] = React.useState(depth < 1);
  const isDir = node.type === "dir";
  return (
    <div>
      <div
        className={`flex cursor-pointer items-center gap-1.5 rounded px-1.5 py-0.5 hover:bg-muted/50 ${
          currentFile === node.path ? "bg-primary/10" : ""
        }`}
        style={{ paddingLeft: `${depth * 12 + 6}px` }}
        onClick={() => {
          if (isDir) setOpen(!open);
          else onOpen(node.path);
        }}
      >
        {isDir ? (
          <Folder className="h-3.5 w-3.5 text-warning" />
        ) : (
          <FileIcon className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <span className="truncate text-xs">{node.name}</span>
        {!isDir && node.size !== undefined && (
          <span className="ml-auto text-[10px] text-muted-foreground">
            {formatBytes(node.size)}
          </span>
        )}
      </div>
      {isDir &&
        open &&
        node.children?.map((c) => (
          <FileTreeNode
            key={c.path}
            node={c}
            depth={depth + 1}
            onOpen={onOpen}
            currentFile={currentFile}
          />
        ))}
    </div>
  );
}
