import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Database, HardDrive, Play, Plus, RefreshCw, ShieldCheck, TestTube } from "lucide-react";
import type { BackupSchedule, BackupRecord, RestoreJob, DRDrill, RecoveryStats, RetentionHold } from "@/lib/types/api";

export function RecoveryPage() {
  const apiClient = api;
  const [stats, setStats] = useState<RecoveryStats | null>(null);
  const [schedules, setSchedules] = useState<BackupSchedule[]>([]);
  const [backups, setBackups] = useState<BackupRecord[]>([]);
  const [drills, setDrills] = useState<DRDrill[]>([]);
  const [holds, setHolds] = useState<RetentionHold[]>([]);
  const [tab, setTab] = useState<"schedules" | "backups" | "drills" | "holds">("schedules");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "daily-full",
    backup_type: "full",
    cron_expr: "0 2 * * *",
    retention_days: 30,
  });

  const load = async () => {
    const s = await apiClient.recoveryStats();
    setStats(s);
    const sc = await apiClient.listBackupSchedules();
    setSchedules(sc.schedules);
    const b = await apiClient.listBackups();
    setBackups(b.backups);
    const d = await apiClient.listDRDrills();
    setDrills(d.drills);
    const h = await apiClient.listRetentionHolds({ active_only: true });
    setHolds(h.holds);
  };

  useEffect(() => {
    load();
  }, []);

  const onCreate = async () => {
    await apiClient.createBackupSchedule({ ...form, retention_days: Number(form.retention_days) });
    setShowCreate(false);
    load();
  };

  const onTrigger = async (id: string) => {
    await apiClient.triggerBackup(id, { record_count: 100 });
    load();
  };

  const onRunDrill = async (scheduleId: string) => {
    await apiClient.runDRDrill({ name: `drill-${Date.now()}`, schedule_id: scheduleId, conducted_by: "sre" });
    load();
  };

  const onCreateHold = async () => {
    await apiClient.createRetentionHold({ resource_id: `res-${Date.now()}`, regulation: "gdpr", action: "preserve", reason: "legal" });
    load();
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("recovery_title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("recovery_subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}><RefreshCw className="w-4 h-4 mr-1" />刷新</Button>
          {tab === "schedules" && <Button size="sm" onClick={() => setShowCreate(!showCreate)}><Plus className="w-4 h-4 mr-1" />新建计划</Button>}
          {tab === "holds" && <Button size="sm" onClick={onCreateHold}><ShieldCheck className="w-4 h-4 mr-1" />加 hold</Button>}
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <Card><CardHeader className="pb-2"><CardDescription>计划</CardDescription><CardTitle className="text-2xl">{stats.total_schedules}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>备份</CardDescription><CardTitle className="text-2xl">{stats.total_backups}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>恢复</CardDescription><CardTitle className="text-2xl">{stats.total_restores}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>演练</CardDescription><CardTitle className="text-2xl">{stats.total_drills}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>活跃 hold</CardDescription><CardTitle className="text-2xl">{stats.active_holds}</CardTitle></CardHeader></Card>
        </div>
      )}

      <div className="flex gap-2 border-b">
        {(["schedules", "backups", "drills", "holds"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-3 py-1.5 text-sm border-b-2 ${tab === k ? "border-foreground" : "border-transparent text-muted-foreground"}`}
          >
            {k === "schedules" ? "计划" : k === "backups" ? "备份" : k === "drills" ? "DR 演练" : "合规保留"}
          </button>
        ))}
      </div>

      {showCreate && tab === "schedules" && (
        <Card>
          <CardHeader><CardTitle>新建备份计划</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Input placeholder="名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input placeholder="类型 full/incremental" value={form.backup_type} onChange={(e) => setForm({ ...form, backup_type: e.target.value })} />
              <Input placeholder="cron" value={form.cron_expr} onChange={(e) => setForm({ ...form, cron_expr: e.target.value })} />
              <Input type="number" placeholder="保留天数" value={form.retention_days} onChange={(e) => setForm({ ...form, retention_days: Number(e.target.value) })} />
            </div>
            <div className="mt-3"><Button onClick={onCreate}>创建</Button></div>
          </CardContent>
        </Card>
      )}

      {tab === "schedules" && (
        <Card>
          <CardHeader><CardTitle>备份计划</CardTitle></CardHeader>
          <CardContent>
            {schedules.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-2">
                {schedules.map((s) => (
                  <div key={s.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="font-medium flex items-center gap-2"><Database className="w-3 h-3" />{s.name}</div>
                      <div className="text-xs text-muted-foreground">{s.backup_type} · {s.cron_expr} · 保留 {s.retention_days}d · {s.target_regions.join(",")}</div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => onTrigger(s.id)}><Play className="w-3 h-3 mr-1" />触发</Button>
                      <Button size="sm" variant="outline" onClick={() => onRunDrill(s.id)}><TestTube className="w-3 h-3 mr-1" />演练</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "backups" && (
        <Card>
          <CardHeader><CardTitle>备份记录</CardTitle></CardHeader>
          <CardContent>
            {backups.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-2">
                {backups.map((b) => (
                  <div key={b.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="text-sm font-medium flex items-center gap-2"><HardDrive className="w-3 h-3" />{b.id}</div>
                      <div className="text-xs text-muted-foreground">{b.target_region} · {b.size_bytes} bytes · checksum {b.checksum.slice(0, 12)}</div>
                    </div>
                    <Badge variant={b.status === "success" ? "default" : b.status === "expired" ? "secondary" : "outline"}>{b.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "drills" && (
        <Card>
          <CardHeader><CardTitle>灾备演练</CardTitle></CardHeader>
          <CardContent>
            {drills.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-2">
                {drills.map((d) => (
                  <div key={d.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="text-sm font-medium">{d.name}</div>
                      <div className="text-xs text-muted-foreground">RTO={d.rto_actual_sec.toFixed(1)}s (target {d.rto_target_sec}s) · RPO={d.rpo_actual_sec.toFixed(1)}s · verified {d.records_verified}</div>
                      {d.issues.length > 0 && <div className="text-xs text-orange-500 mt-1">{d.issues.join("; ")}</div>}
                    </div>
                    <Badge variant={d.result === "pass" ? "default" : d.result === "pass_with_issues" ? "secondary" : "error"}>{d.result}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "holds" && (
        <Card>
          <CardHeader><CardTitle>合规保留锁定</CardTitle></CardHeader>
          <CardContent>
            {holds.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-2">
                {holds.map((h) => (
                  <div key={h.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="text-sm font-medium">{h.resource_id}</div>
                      <div className="text-xs text-muted-foreground">{h.regulation} · {h.reason}</div>
                    </div>
                    <Badge variant={h.action === "preserve" ? "default" : "secondary"}>{h.action}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
