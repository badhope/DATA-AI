import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CircleDollarSign, Plus, RefreshCw, ShieldAlert } from "lucide-react";
import type { CompensationPolicy, BreachEvent, Credit, Dispute, CompensationStats } from "@/lib/types/api";

export function CompensationPage() {
  const apiClient = api;
  const [stats, setStats] = useState<CompensationStats | null>(null);
  const [policies, setPolicies] = useState<CompensationPolicy[]>([]);
  const [breaches, setBreaches] = useState<BreachEvent[]>([]);
  const [credits, setCredits] = useState<Credit[]>([]);
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [tab, setTab] = useState<"breaches" | "credits" | "disputes" | "policies">("breaches");
  const [form, setForm] = useState({ tenant_id: "tnt-corp", actual: 99.5, fee: 10000 });

  const load = async () => {
    const s = await apiClient.compensationStats();
    setStats(s);
    const p = await apiClient.listCompensationPolicies();
    setPolicies(p.policies);
    const b = await apiClient.listBreaches();
    setBreaches(b.breaches);
    const c = await apiClient.listCredits();
    setCredits(c.credits);
    const d = await apiClient.listDisputes();
    setDisputes(d.disputes);
  };

  useEffect(() => {
    load();
  }, []);

  const onSimulate = async () => {
    if (policies.length === 0) return;
    const policy = policies[0];
    const b = await apiClient.detectBreach({
      policy_id: policy.id,
      tenant_id: form.tenant_id,
      actual_availability_pct: form.actual,
      downtime_sec: 14400,
    });
    if (form.fee > 0) {
      await apiClient.calculateCredit({ breach_id: b.breach.id, monthly_fee_usd: form.fee });
    }
    load();
  };

  const onApply = async (id: string) => {
    await apiClient.applyCredit(id);
    load();
  };

  const onDispute = async (creditId: string, tenantId: string) => {
    await apiClient.raiseDispute({ credit_id: creditId, tenant_id: tenantId, raised_by: "customer", reason: "credit too low" });
    load();
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("compensation_title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t("compensation_subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}><RefreshCw className="w-4 h-4 mr-1" />刷新</Button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card><CardHeader className="pb-2"><CardDescription>违约事件</CardDescription><CardTitle className="text-2xl">{stats.total_breaches}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>赔付</CardDescription><CardTitle className="text-2xl">{stats.total_credits}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>累计赔付 (USD)</CardDescription><CardTitle className="text-2xl">${stats.total_credit_amount_usd.toFixed(2)}</CardTitle></CardHeader></Card>
          <Card><CardHeader className="pb-2"><CardDescription>争议</CardDescription><CardTitle className="text-2xl">{stats.total_disputes}</CardTitle></CardHeader></Card>
        </div>
      )}

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><AlertCircle className="w-4 h-4" />模拟 SLA 违约</CardTitle></CardHeader>
        <CardContent>
          <div className="flex gap-2 items-end">
            <div><label className="text-xs">租户</label><Input value={form.tenant_id} onChange={(e) => setForm({ ...form, tenant_id: e.target.value })} /></div>
            <div><label className="text-xs">实际可用率 %</label><Input type="number" step="0.01" value={form.actual} onChange={(e) => setForm({ ...form, actual: Number(e.target.value) })} /></div>
            <div><label className="text-xs">月费 USD</label><Input type="number" value={form.fee} onChange={(e) => setForm({ ...form, fee: Number(e.target.value) })} /></div>
            <Button onClick={onSimulate}><Plus className="w-4 h-4 mr-1" />检测违约</Button>
          </div>
        </CardContent>
      </Card>

      <div className="flex gap-2 border-b">
        {(["breaches", "credits", "disputes", "policies"] as const).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`px-3 py-1.5 text-sm border-b-2 ${tab === k ? "border-foreground" : "border-transparent text-muted-foreground"}`}
          >
            {k === "breaches" ? "违约" : k === "credits" ? "赔付" : k === "disputes" ? "争议" : "政策"}
          </button>
        ))}
      </div>

      {tab === "breaches" && (
        <Card>
          <CardHeader><CardTitle>SLA 违约事件</CardTitle></CardHeader>
          <CardContent>
            {breaches.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-2">
                {breaches.map((b) => (
                  <div key={b.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="text-sm font-medium flex items-center gap-2"><ShieldAlert className="w-3 h-3" />{b.tenant_id}</div>
                      <div className="text-xs text-muted-foreground">实际 {b.actual_pct}% / 目标 {b.target_pct}% · 偏差 {(b.target_pct - b.actual_pct).toFixed(2)}% · {b.description || "-"}</div>
                    </div>
                    <Badge variant={b.severity === "critical" ? "error" : b.severity === "high" ? "secondary" : "outline"}>{b.severity}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "credits" && (
        <Card>
          <CardHeader><CardTitle>赔付记录</CardTitle></CardHeader>
          <CardContent>
            {credits.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-2">
                {credits.map((c) => (
                  <div key={c.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="text-sm font-medium flex items-center gap-2"><CircleDollarSign className="w-3 h-3" />{c.tenant_id}</div>
                      <div className="text-xs text-muted-foreground">{c.credit_pct}% · ${c.credit_amount_usd.toFixed(2)} · base ${c.base_amount_usd}</div>
                    </div>
                    <div className="flex gap-2">
                      <Badge variant={c.status === "paid" || c.status === "applied" ? "default" : c.status === "disputed" ? "secondary" : "outline"}>{c.status}</Badge>
                      {c.status === "pending" && <Button size="sm" variant="outline" onClick={() => onApply(c.id)}>apply</Button>}
                      {c.status === "approved" && <Button size="sm" variant="outline" onClick={() => onDispute(c.id, c.tenant_id)}>dispute</Button>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "disputes" && (
        <Card>
          <CardHeader><CardTitle>争议工单</CardTitle></CardHeader>
          <CardContent>
            {disputes.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-2">
                {disputes.map((d) => (
                  <div key={d.id} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <div className="text-sm font-medium">credit={d.credit_id} · by {d.raised_by}</div>
                      <div className="text-xs text-muted-foreground">{d.reason} {d.resolution && `→ ${d.resolution}`}</div>
                    </div>
                    <Badge variant={d.status === "resolved" ? "default" : d.status === "rejected" ? "error" : "outline"}>{d.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "policies" && (
        <Card>
          <CardHeader><CardTitle>赔付政策</CardTitle></CardHeader>
          <CardContent>
            {policies.length === 0 ? <p className="text-sm text-muted-foreground">暂无</p> : (
              <div className="space-y-3">
                {policies.map((p) => (
                  <div key={p.id} className="border-b pb-3">
                    <div className="font-medium">{p.name}</div>
                    <div className="text-xs text-muted-foreground">目标 {p.target_availability_pct}% · {p.plan_tier} · {len(p.tiers)} 档</div>
                    <div className="mt-2 grid grid-cols-2 gap-1 text-xs">
                      {p.tiers.map((tier, i) => (
                        <div key={i} className="border rounded p-1">
                          {tier.min_availability_pct.toFixed(1)}%–{tier.max_availability_pct.toFixed(1)}% → {tier.credit_pct}%
                        </div>
                      ))}
                    </div>
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

function len<T>(arr: T[]): number {
  return arr.length;
}
