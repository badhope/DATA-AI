import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Cloud, GitBranch, Plus, RefreshCw, ShieldAlert, Zap } from "lucide-react";
import type { ReplicationPolicy, ReplicaStream, FailoverEvent, ReplicationStats } from "@/lib/types/api";

export function ReplicationPage() {
  const apiClient = api;
  const [stats, setStats] = useState<ReplicationStats | null>(null);
  const [policies, setPolicies] = useState<ReplicationPolicy[]>([]);
  const [streams, setStreams] = useState<ReplicaStream[]>([]);
  const [failovers, setFailovers] = useState<FailoverEvent[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "CN→US async",
    source_region: "cn-east",
    target_region: "us-west",
    mode: "async",
    max_lag_sec: 30,
  });
  const [q, setQ] = useState({ region: "cn-east", total: 3, reachable: 3 });
  const [qResult, setQResult] = useState<{ ok: boolean; can_write: boolean; ratio: number; recommendation: string } | null>(null);

  const load = async () => {
    const s = await apiClient.replicationStats();
    setStats(s);
    const p = await apiClient.listReplicationPolicies();
    setPolicies(p.policies);
    const r = await apiClient.listReplicationStreams();
    setStreams(r.streams);
    const f = await apiClient.listFailovers({ limit: 20 });
    setFailovers(f.failovers);
  };

  useEffect(() => {
    load();
  }, []);

  const onCreate = async () => {
    await apiClient.createReplicationPolicy(form);
    setShowCreate(false);
    load();
  };

  const onInitiateFailover = async (from: string, to: string) => {
    await apiClient.initiateFailover({ from_region: from, to_region: to, mode: "planned", reason: "manual" });
    load();
  };

  const onQuorum = async () => {
    const r = await apiClient.replicationQuorumCheck({ region: q.region, total_replicas: q.total, reachable_replicas: q.reachable });
    setQResult(r);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("replication_title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("replication_subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}><RefreshCw className="w-4 h-4 mr-1" />刷新</Button>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)}><Plus className="w-4 h-4 mr-1" />新建策略</Button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card><CardHeader className="pb-2"><CardDescription>策略</CardDescription><CardTitle className="text-2xl">{stats.total_policies}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>流</CardDescription><CardTitle className="text-2xl">{stats.total_streams}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>活跃区</CardDescription><CardTitle className="text-lg">{stats.active_region}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>平均延迟 (s)</CardDescription><CardTitle className="text-2xl">{stats.avg_lag_sec.toFixed(1)}</CardTitle></CardHeader></Card>
        </div>
      )}

      {showCreate && (
        <Card>
          <CardHeader><CardTitle>新建复制策略</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <Input placeholder="名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              <Input placeholder="源区" value={form.source_region} onChange={(e) => setForm({ ...form, source_region: e.target.value })} />
              <Input placeholder="目标区" value={form.target_region} onChange={(e) => setForm({ ...form, target_region: e.target.value })} />
              <Input placeholder="模式 sync/async" value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })} />
              <Input type="number" placeholder="最大延迟" value={form.max_lag_sec} onChange={(e) => setForm({ ...form, max_lag_sec: Number(e.target.value) })} />
            </div>
            <div className="mt-3"><Button onClick={onCreate}>创建</Button></div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>策略</CardTitle></CardHeader>
          <CardContent>
            {policies.length === 0 ? <p className="text-sm text-muted-foreground">暂无策略</p> : (
              <div className="space-y-2">
                {policies.map((p) => (
                  <div key={p.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="font-medium">{p.name}</div>
                      <div className="text-xs text-muted-foreground">{p.source_region} → {p.target_region} · {p.mode} · lag ≤ {p.max_lag_sec}s</div>
                    </div>
                    <div className="flex gap-2">
                      <Badge variant={p.enabled ? "default" : "secondary"}>{p.enabled ? "启用" : "停用"}</Badge>
                      <Button variant="outline" size="sm" onClick={() => onInitiateFailover(p.source_region, p.target_region)}>切换</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>复制流</CardTitle></CardHeader>
          <CardContent>
            {streams.length === 0 ? <p className="text-sm text-muted-foreground">暂无流</p> : (
              <div className="space-y-2">
                {streams.map((s) => (
                  <div key={s.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="text-sm font-medium flex items-center gap-2"><GitBranch className="w-3 h-3" />{s.source_region} → {s.target_region}</div>
                      <div className="text-xs text-muted-foreground">已复制 {s.records_sent} records · {s.bytes_sent} bytes</div>
                    </div>
                    <div className="flex gap-2 items-center">
                      <span className="text-xs">lag {s.lag_sec.toFixed(1)}s</span>
                      <Badge variant={s.state === "healthy" ? "default" : s.state === "failed" ? "error" : "secondary"}>{s.state}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><ShieldAlert className="w-4 h-4" />Quorum 检查 (防脑裂)</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2 items-end">
            <div><label className="text-xs">区</label><Input value={q.region} onChange={(e) => setQ({ ...q, region: e.target.value })} /></div>
            <div><label className="text-xs">总副本</label><Input type="number" value={q.total} onChange={(e) => setQ({ ...q, total: Number(e.target.value) })} /></div>
            <div><label className="text-xs">可达</label><Input type="number" value={q.reachable} onChange={(e) => setQ({ ...q, reachable: Number(e.target.value) })} /></div>
            <Button onClick={onQuorum}><Zap className="w-4 h-4 mr-1" />检查</Button>
            {qResult && (
              <div className="ml-4 text-sm">
                <Badge variant={qResult.ok ? "default" : "error"}>{qResult.can_write ? "可写" : "只读"}</Badge>
                <span className="ml-2 text-xs text-muted-foreground">ratio={qResult.ratio.toFixed(2)} · {qResult.recommendation}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>最近灾备切换</CardTitle></CardHeader>
        <CardContent>
          {failovers.length === 0 ? <p className="text-sm text-muted-foreground">暂无记录</p> : (
            <div className="space-y-2">
              {failovers.map((f) => (
                <div key={f.id} className="flex items-center justify-between border-b pb-2">
                  <div>
                    <div className="text-sm font-medium flex items-center gap-2"><Cloud className="w-3 h-3" />{f.from_region} → {f.to_region}</div>
                    <div className="text-xs text-muted-foreground">{f.reason || "-"}</div>
                  </div>
                  <div className="flex gap-2 items-center">
                    <Badge variant="secondary">{f.mode}</Badge>
                    <Badge variant={f.state === "switched" ? "default" : f.state === "rolled_back" ? "secondary" : "outline"}>{f.state}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
