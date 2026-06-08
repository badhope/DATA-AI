"use client";

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
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toaster";
import { api } from "@/lib/api/client";
import { useT } from "@/lib/i18n";
import {
  type AuthScheme,
  type ConnectionProfile,
  type Language,
  type LogLevel,
  PROVIDER_PRESETS,
  type ProviderPreset,
  type ThemeMode,
  getSettings,
  useSettings,
} from "@/lib/stores/settings";
import {
  Activity,
  AlertCircle,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  Copy,
  Download,
  Edit3,
  Eye,
  EyeOff,
  Github,
  Globe,
  Info,
  KeyRound,
  Loader2,
  MonitorSmartphone,
  Moon,
  Palette,
  Plug,
  Plus,
  Server,
  Sun,
  Trash2,
  Upload,
  Volume2,
  Wifi,
  WifiOff,
  X,
  XCircle,
} from "lucide-react";
import * as React from "react";
import { useSearchParams } from "react-router-dom";

const TABS = [
  { id: "connection", label: "连接", icon: Server },
  { id: "appearance", label: "外观", icon: Palette },
  { id: "behavior", label: "行为", icon: Volume2 },
  { id: "about", label: "关于", icon: Info },
];

export function SettingsPage() {
  const params = useSearchParams();
  const [activeTab, setActiveTab] = React.useState(params[0].get("tab") ?? "connection");

  return (
    <div className="space-y-6">
      <PageHeader
        title="设置"
        description="全局偏好与连接配置"
        icon={<Palette className="h-5 w-5" />}
      />

      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        orientation="vertical"
        className="flex flex-col gap-4 md:flex-row md:gap-6"
      >
        <aside className="md:w-56 shrink-0">
          <TabsList className="flex h-auto w-full flex-col items-stretch bg-card p-1 md:inline-flex">
            {TABS.map((t) => {
              const Icon = t.icon;
              return (
                <TabsTrigger
                  key={t.id}
                  value={t.id}
                  className="w-full justify-start gap-2 data-[state=active]:bg-primary/10 data-[state=active]:text-primary"
                >
                  <Icon className="h-4 w-4" /> {t.label}
                </TabsTrigger>
              );
            })}
          </TabsList>
        </aside>

        <div className="flex-1 space-y-4">
          <TabsContent value="connection" className="mt-0">
            <ConnectionSettings />
          </TabsContent>
          <TabsContent value="appearance" className="mt-0">
            <AppearanceSettings />
          </TabsContent>
          <TabsContent value="behavior" className="mt-0">
            <BehaviorSettings />
          </TabsContent>
          <TabsContent value="about" className="mt-0">
            <AboutSettings />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

function ConnectionSettings() {
  const { t } = useT();
  const settings = useSettings();
  const {
    profiles,
    activeProfileId,
    diagnostic,
    diagnosticLoading,
    addProfile,
    updateProfile,
    deleteProfile,
    setActiveProfile,
    duplicateProfile,
    setDiagnostic,
    setDiagnosticLoading,
    importProfiles,
    reset,
  } = settings;

  const active = profiles.find((p) => p.id === activeProfileId) || profiles[0];
  const [showKey, setShowKey] = React.useState(false);
  const [testing, setTesting] = React.useState(false);

  /* 当前 Profile 字段即时同步（onBlur 写入 store） */
  const [draft, setDraft] = React.useState<ConnectionProfile | null>(active ?? null);
  React.useEffect(() => {
    setDraft(active ?? null);
  }, [active?.id]);

  const onProviderChange = (provider: ProviderPreset) => {
    if (!draft) return;
    const preset = PROVIDER_PRESETS[provider];
    setDraft({
      ...draft,
      provider,
      baseUrl: preset.baseUrl,
      authScheme: preset.authScheme,
      defaultModel: draft.defaultModel || preset.defaultModel,
    });
  };

  const onTest = async () => {
    if (!draft) return;
    setTesting(true);
    setDiagnosticLoading(true);
    try {
      const r = await api.testConnection({
        baseUrl: draft.baseUrl,
        apiKey: draft.apiKey,
        authScheme: draft.authScheme,
      });
      setDiagnostic({
        ok: r.ok,
        status: r.status,
        latencyMs: r.latencyMs,
        version: r.version,
        apiVersion: r.apiVersion,
        modelsCount: r.modelsCount,
        toolsCount: r.toolsCount,
        capabilities: r.capabilities,
        uptimeMs: r.uptimeMs,
        python: r.python,
        error: r.error,
        detail: r.detail,
        testedAt: Date.now(),
      });
      if (r.ok) {
        toast.success(t("settings.testOk"), {
          description: `${r.latencyMs}ms · v${r.version} · ${r.modelsCount} models · ${r.toolsCount} tools`,
        });
      }
      // 失败时不弹 toast，让 UI 上的 diagnostic 卡片自己显示错误（避免双报）
    } finally {
      setTesting(false);
      setDiagnosticLoading(false);
    }
  };

  const onSave = () => {
    if (!draft) return;
    updateProfile(draft.id, draft);
    setActiveProfile(draft.id);
    toast.success(t("settings.testSavedOk"));
  };

  const onAddProfile = () => {
    const id = addProfile({});
    setActiveProfile(id);
  };

  const onDeleteProfile = (id: string) => {
    if (profiles.length === 1) {
      toast.error(t("settings.profileDelete"), {
        description: "至少保留一个 Profile。",
      });
      return;
    }
    if (!confirm(t("settings.profileDeleteConfirm"))) return;
    deleteProfile(id);
  };

  const onDuplicate = (id: string) => {
    const newId = duplicateProfile(id);
    if (newId) setActiveProfile(newId);
  };

  /* Export / Import */
  const onExport = () => {
    const blob = new Blob([JSON.stringify({ profiles, activeProfileId }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `data-ai-connection-profiles-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const onImport = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const json = JSON.parse(String(reader.result));
        const ps: ConnectionProfile[] = Array.isArray(json?.profiles) ? json.profiles : [];
        if (!ps.length) throw new Error("empty");
        // 校验：保证有 id / provider / baseUrl
        const valid = ps.filter(
          (p) => p && typeof p.id === "string" && typeof p.baseUrl === "string",
        );
        if (!valid.length) throw new Error("invalid");
        const activeId = ps.find((p) => p.id === json.activeProfileId)
          ? json.activeProfileId
          : valid[0].id;
        importProfiles(valid, activeId);
        toast.success(t("settings.profileImportOk").replace("{n}", String(valid.length)));
      } catch {
        toast.error(t("settings.profileImportErr"));
      }
    };
    reader.readAsText(file);
  };

  const onResetAll = () => {
    if (!confirm(t("settings.profileResetConfirm"))) return;
    reset();
  };

  if (!draft) return null;

  return (
    <div className="space-y-4">
      {/* Profile 列表（多 Profile 切换） */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Plug className="h-4 w-4 text-primary" />
                {t("settings.profilesTitle")}
              </CardTitle>
              <CardDescription>{t("settings.profilesDesc")}</CardDescription>
            </div>
            <div className="flex gap-1.5">
              <Button size="sm" variant="outline" onClick={onAddProfile}>
                <Plus className="h-3.5 w-3.5" /> {t("settings.profileAdd")}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {profiles.map((p) => {
              const isActive = p.id === activeProfileId;
              const preset = PROVIDER_PRESETS[p.provider];
              return (
                <button
                  key={p.id}
                  onClick={() => setActiveProfile(p.id)}
                  className={`text-left rounded-lg border-2 p-3 transition-all ${
                    isActive
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-primary/30"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate flex items-center gap-1.5">
                        {isActive && <ChevronRight className="h-3.5 w-3.5 text-primary" />}
                        {p.name || preset.label}
                      </p>
                      <p className="text-[11px] text-muted-foreground truncate mt-0.5 font-mono">
                        {p.baseUrl}
                      </p>
                    </div>
                    {isActive && (
                      <Badge variant="accent" className="shrink-0 text-[10px] py-0">
                        {t("settings.profileActive")}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-2 flex items-center justify-between gap-1">
                    <span className="text-[10px] text-muted-foreground">{preset.label}</span>
                    <div className="flex gap-1">
                      <span
                        role="button"
                        tabIndex={0}
                        title={t("settings.profileDuplicate")}
                        onClick={(e) => {
                          e.stopPropagation();
                          onDuplicate(p.id);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.stopPropagation();
                            onDuplicate(p.id);
                          }
                        }}
                        className="rounded p-1 text-muted-foreground hover:bg-accent"
                      >
                        <Copy className="h-3 w-3" />
                      </span>
                      <span
                        role="button"
                        tabIndex={0}
                        title={t("settings.profileDelete")}
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteProfile(p.id);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.stopPropagation();
                            onDeleteProfile(p.id);
                          }
                        }}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* 当前 Profile 编辑 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-4 w-4 text-primary" />
            {t("settings.sectionConnection")}
          </CardTitle>
          <CardDescription>
            {draft.provider === "data-ai"
              ? "DATA-AI 本项目后端（默认）"
              : PROVIDER_PRESETS[draft.provider].label}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Profile 名称 + Provider */}
          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">{t("settings.profileName")}</Label>
              <Input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                placeholder="My Workspace"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">{t("settings.fieldProvider")}</Label>
              <Select
                value={draft.provider}
                onValueChange={(v) => onProviderChange(v as ProviderPreset)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(PROVIDER_PRESETS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>
                      {v.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Base URL + Auth scheme */}
          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-1.5 md:col-span-2">
              <Label className="text-xs">{t("settings.fieldBaseUrl")}</Label>
              <Input
                value={draft.baseUrl}
                onChange={(e) => setDraft({ ...draft, baseUrl: e.target.value })}
                placeholder="http://localhost:8000"
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">{t("settings.fieldAuthScheme")}</Label>
              <Select
                value={draft.authScheme}
                onValueChange={(v) => setDraft({ ...draft, authScheme: v as AuthScheme })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="bearer">{t("settings.authBearer")}</SelectItem>
                  <SelectItem value="x-api-key">{t("settings.authXApiKey")}</SelectItem>
                  <SelectItem value="none">{t("settings.authNone")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* API Key + Default model + Timeout */}
          <div className="grid gap-3 md:grid-cols-3">
            <div className="space-y-1.5 md:col-span-2">
              <Label className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1">
                  <KeyRound className="h-3 w-3" /> {t("settings.fieldApiKey")}
                </span>
                <button
                  type="button"
                  onClick={() => setShowKey(!showKey)}
                  className="text-[10px] text-muted-foreground hover:text-foreground flex items-center gap-1"
                >
                  {showKey ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}
                  {showKey ? t("settings.fieldHideKey") : t("settings.fieldShowKey")}
                </button>
              </Label>
              <Input
                type={showKey ? "text" : "password"}
                value={draft.apiKey === "dev-mode" ? "" : draft.apiKey}
                onChange={(e) => setDraft({ ...draft, apiKey: e.target.value })}
                placeholder={t("settings.fieldApiKeyPlaceholder")}
                className="font-mono text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">{t("settings.fieldDefaultModel")}</Label>
              <Input
                value={draft.defaultModel}
                onChange={(e) => setDraft({ ...draft, defaultModel: e.target.value })}
                placeholder="offline-chat"
                className="font-mono text-xs"
              />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">{t("settings.fieldTimeout")}</Label>
              <Input
                type="number"
                min={1000}
                max={60000}
                step={500}
                value={draft.timeoutMs}
                onChange={(e) => setDraft({ ...draft, timeoutMs: Number(e.target.value) || 8000 })}
              />
            </div>
          </div>

          {/* Custom Headers */}
          <div className="space-y-1.5">
            <Label className="text-xs">{t("settings.fieldCustomHeaders")}</Label>
            <p className="text-[11px] text-muted-foreground">
              {t("settings.fieldCustomHeadersDesc")}
            </p>
            <div className="space-y-2 mt-2">
              {draft.customHeaders.length === 0 && (
                <p className="text-[11px] text-muted-foreground italic">（无）</p>
              )}
              {draft.customHeaders.map((h, idx) => (
                <div key={h.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={h.enabled}
                    onChange={(e) => {
                      const next = [...draft.customHeaders];
                      next[idx] = { ...h, enabled: e.target.checked };
                      setDraft({ ...draft, customHeaders: next });
                    }}
                    className="h-3.5 w-3.5"
                  />
                  <Input
                    value={h.key}
                    onChange={(e) => {
                      const next = [...draft.customHeaders];
                      next[idx] = { ...h, key: e.target.value };
                      setDraft({ ...draft, customHeaders: next });
                    }}
                    placeholder={t("settings.fieldHeaderKey")}
                    className="font-mono text-xs flex-1"
                  />
                  <Input
                    value={h.value}
                    onChange={(e) => {
                      const next = [...draft.customHeaders];
                      next[idx] = { ...h, value: e.target.value };
                      setDraft({ ...draft, customHeaders: next });
                    }}
                    placeholder={t("settings.fieldHeaderValue")}
                    className="font-mono text-xs flex-1"
                  />
                  <Button
                    size="icon"
                    variant="ghost"
                    onClick={() => {
                      const next = draft.customHeaders.filter((_, i) => i !== idx);
                      setDraft({ ...draft, customHeaders: next });
                    }}
                    className="h-7 w-7"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  const id =
                    typeof crypto !== "undefined" && crypto.randomUUID
                      ? crypto.randomUUID().slice(0, 8)
                      : String(Date.now());
                  setDraft({
                    ...draft,
                    customHeaders: [
                      ...draft.customHeaders,
                      { id, key: "", value: "", enabled: true },
                    ],
                  });
                }}
              >
                <Plus className="h-3.5 w-3.5" /> {t("settings.fieldHeaderAdd")}
              </Button>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-wrap items-center gap-2 pt-2 border-t">
            <Button onClick={onSave} variant="default">
              <Check className="h-4 w-4" /> {t("common.save")}
            </Button>
            <Button onClick={onTest} disabled={testing} variant="outline">
              {testing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Activity className="h-4 w-4" />
              )}
              {testing ? t("settings.testRunning") : t("settings.testButton")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 诊断面板 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-primary" />
            {t("settings.sectionTest")}
          </CardTitle>
          <CardDescription>{t("settings.testHint")}</CardDescription>
        </CardHeader>
        <CardContent>
          {diagnosticLoading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {t("settings.testRunning")}
            </div>
          ) : !diagnostic ? (
            <p className="text-sm text-muted-foreground italic">{t("settings.testNoDiagnostic")}</p>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                {diagnostic.ok ? (
                  <CheckCircle2 className="h-5 w-5 text-success" />
                ) : (
                  <XCircle className="h-5 w-5 text-destructive" />
                )}
                <span
                  className={`text-sm font-medium ${diagnostic.ok ? "text-success" : "text-destructive"}`}
                >
                  {diagnostic.ok ? t("settings.testOk") : t("settings.testFail")}
                </span>
                <span className="text-xs text-muted-foreground ml-2">
                  {diagnostic.status > 0 ? `HTTP ${diagnostic.status}` : "Network"}
                </span>
              </div>

              {diagnostic.error && (
                <div className="border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive flex items-start gap-1.5">
                  <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
                  <span className="break-all">{diagnostic.error}</span>
                </div>
              )}

              {diagnostic.ok && (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  <Stat label={t("settings.testLatency")} value={`${diagnostic.latencyMs} ms`} />
                  <Stat label={t("settings.testVersion")} value={diagnostic.version || "-"} />
                  <Stat
                    label={t("settings.testApiVersion")}
                    value={diagnostic.apiVersion || "v1"}
                  />
                  <Stat label={t("settings.testPython")} value={diagnostic.python || "-"} />
                  <Stat
                    label={t("settings.testUptime")}
                    value={diagnostic.uptimeMs != null ? formatUptime(diagnostic.uptimeMs) : "-"}
                  />
                  <Stat
                    label={t("settings.testModelsCount")}
                    value={String(diagnostic.modelsCount ?? 0)}
                  />
                  <Stat
                    label={t("settings.testToolsCount")}
                    value={String(diagnostic.toolsCount ?? 0)}
                  />
                </div>
              )}

              {diagnostic.capabilities && diagnostic.capabilities.length > 0 && (
                <div className="space-y-1.5">
                  <Label className="text-xs">{t("settings.testCapabilities")}</Label>
                  <div className="flex flex-wrap gap-1.5">
                    {diagnostic.capabilities.map((c) => (
                      <Badge key={c} variant="secondary" className="text-[10px]">
                        {c}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 备份与恢复 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-4 w-4 text-primary" />
            {t("settings.sectionExport")}
          </CardTitle>
          <CardDescription>把所有 Profile 导出为 JSON 文件，或从 JSON 导入。</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={onExport}>
              <Download className="h-4 w-4" /> {t("settings.profileExport")}
            </Button>
            <label className="inline-flex">
              <input
                type="file"
                accept="application/json,.json"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) onImport(f);
                  e.target.value = "";
                }}
                className="hidden"
              />
              <span className="inline-flex items-center justify-center gap-1.5 rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium hover:bg-accent cursor-pointer">
                <Upload className="h-4 w-4" /> {t("settings.profileImport")}
              </span>
            </label>
            <Button
              variant="ghost"
              onClick={onResetAll}
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" /> {t("settings.profileReset")}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card/50 px-3 py-2">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-sm font-medium font-mono mt-0.5 truncate">{value}</p>
    </div>
  );
}

function formatUptime(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ${m % 60}m`;
  const d = Math.floor(h / 24);
  return `${d}d ${h % 24}h`;
}

function AppearanceSettings() {
  const { theme, language, set } = useSettings();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Palette className="h-4 w-4 text-primary" /> 外观
        </CardTitle>
        <CardDescription>主题与语言</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <Label className="text-xs">主题</Label>
          <div className="grid grid-cols-3 gap-2">
            {(
              [
                { v: "dark", label: "暗色", icon: Moon },
                { v: "light", label: "浅色", icon: Sun },
                { v: "system", label: "跟随系统", icon: MonitorSmartphone },
              ] as {
                v: ThemeMode;
                label: string;
                icon: React.ComponentType<{ className?: string }>;
              }[]
            ).map((opt) => {
              const Icon = opt.icon;
              const active = theme === opt.v;
              return (
                <button
                  key={opt.v}
                  onClick={() => set({ theme: opt.v })}
                  className={`flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-all ${
                    active
                      ? "border-primary bg-primary/10"
                      : "border-border hover:border-primary/30"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  <span className="text-xs font-medium">{opt.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="space-y-2">
          <Label className="flex items-center gap-2 text-xs">
            <Globe className="h-3 w-3" /> 语言
          </Label>
          <Select value={language} onValueChange={(v) => set({ language: v as Language })}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="zh">中文</SelectItem>
              <SelectItem value="en">English</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  );
}

function BehaviorSettings() {
  const { logLevel, autoScroll, showTokenUsage, saveHistory, enableAutoTitle, set } = useSettings();
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Volume2 className="h-4 w-4 text-primary" /> 行为
        </CardTitle>
        <CardDescription>日志级别与运行时行为</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label className="text-xs">日志级别</Label>
          <Select value={logLevel} onValueChange={(v) => set({ logLevel: v as LogLevel })}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="debug">Debug</SelectItem>
              <SelectItem value="info">Info</SelectItem>
              <SelectItem value="warn">Warning</SelectItem>
              <SelectItem value="error">Error</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">自动滚动到最新消息</p>
              <p className="text-xs text-muted-foreground">Chat 收到新消息时自动滚动到底部</p>
            </div>
            <Switch checked={autoScroll} onCheckedChange={(v) => set({ autoScroll: v })} />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">显示 Token 用量</p>
              <p className="text-xs text-muted-foreground">
                在每条消息下方显示 prompt/completion/total tokens
              </p>
            </div>
            <Switch checked={showTokenUsage} onCheckedChange={(v) => set({ showTokenUsage: v })} />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">保存聊天历史到 localStorage</p>
              <p className="text-xs text-muted-foreground">刷新页面后保留会话</p>
            </div>
            <Switch checked={saveHistory} onCheckedChange={(v) => set({ saveHistory: v })} />
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">自动为会话命名</p>
              <p className="text-xs text-muted-foreground">首条消息后自动用 LLM 生成会话标题</p>
            </div>
            <Switch
              checked={enableAutoTitle}
              onCheckedChange={(v) => set({ enableAutoTitle: v })}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function AboutSettings() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Info className="h-4 w-4 text-primary" /> 关于
        </CardTitle>
        <CardDescription>DATA-AI Web 控制台</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <InfoItem label="版本" value="1.0.0" />
          <InfoItem label="构建时间" value={new Date().toLocaleString("zh-CN")} />
          <InfoItem label="前端框架" value="Vite 6 + React 19" />
          <InfoItem label="后端" value="data_ai FastAPI" />
        </div>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button asChild variant="outline">
            <a href="https://github.com/data-ai/data-ai" target="_blank" rel="noreferrer">
              <Github className="h-4 w-4" /> GitHub
            </a>
          </Button>
          <Button asChild variant="outline">
            <a href="/docs" target="_blank" rel="noreferrer">
              <BookOpen className="h-4 w-4" /> 文档
            </a>
          </Button>
        </div>
        <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
          © 2026 DATA-AI · Apache 2.0 License
        </div>
      </CardContent>
    </Card>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-3">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-1 font-mono text-sm">{value}</p>
    </div>
  );
}
