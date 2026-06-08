import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Building2, Plus, Pause, Play, Trash2, Users } from "lucide-react";
import type { Tenant, TenantCreateRequest, PlanTier, TenantStatus, MemberRole } from "@/lib/types/api";

const planColor: Record<PlanTier, string> = {
  free: "bg-slate-100 text-slate-700",
  starter: "bg-blue-100 text-blue-700",
  pro: "bg-violet-100 text-violet-700",
  enterprise: "bg-amber-100 text-amber-700",
};

const statusColor: Record<TenantStatus, string> = {
  active: "bg-emerald-100 text-emerald-700",
  suspended: "bg-rose-100 text-rose-700",
  archived: "bg-slate-100 text-slate-500",
};

export function TenantsPage() {
  const apiClient = api;
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [stats, setStats] = useState<{ total_tenants: number; total_members: number; by_plan: Record<string, number>; by_status: Record<string, number> } | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [form, setForm] = useState<TenantCreateRequest>({ name: "", slug: "", plan: "free", region: "default" });
  const [selected, setSelected] = useState<Tenant | null>(null);
  const [members, setMembers] = useState<{ tenant_id: string; user_id: string; role: MemberRole; joined_at: number }[]>([]);
  const [memberInput, setMemberInput] = useState({ user_id: "", role: "member" });

  const load = async () => {
    setLoading(true);
    try {
      const r = await apiClient.listTenants();
      setTenants(r.tenants);
      setStats(r.stats);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onCreate = async () => {
    if (!form.name) return;
    await apiClient.createTenant(form);
    setForm({ name: "", slug: "", plan: "free", region: "default" });
    setShowDialog(false);
    load();
  };

  const onSuspend = async (tid: string) => {
    await apiClient.suspendTenant(tid);
    load();
  };
  const onActivate = async (tid: string) => {
    await apiClient.activateTenant(tid);
    load();
  };
  const onDelete = async (tid: string) => {
    if (!confirm(t("common.confirmDelete"))) return;
    await apiClient.deleteTenant(tid);
    load();
  };

  const openDetail = async (tenant: Tenant) => {
    setSelected(tenant);
    const r = await apiClient.listTenantMembers(tenant.id);
    setMembers(r.members);
  };

  const onAddMember = async () => {
    if (!selected || !memberInput.user_id) return;
    await apiClient.addTenantMember(selected.id, memberInput);
    setMemberInput({ user_id: "", role: "member" });
    const r = await apiClient.listTenantMembers(selected.id);
    setMembers(r.members);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Building2 className="h-6 w-6" />
            {t("tenants.title")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{t("tenants.subtitle")}</p>
        </div>
        <Button onClick={() => setShowDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          {t("tenants.create")}
        </Button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("tenants.totalTenants")}</CardDescription>
              <CardTitle className="text-2xl">{stats.total_tenants}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("tenants.totalMembers")}</CardDescription>
              <CardTitle className="text-2xl">{stats.total_members}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("tenants.byPlan")}</CardDescription>
              <CardTitle className="text-base">{Object.entries(stats.by_plan).map(([k, v]) => `${k}:${v}`).join(" / ") || "—"}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("tenants.byStatus")}</CardDescription>
              <CardTitle className="text-base">{Object.entries(stats.by_status).map(([k, v]) => `${k}:${v}`).join(" / ") || "—"}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {showDialog && (
        <Card>
          <CardHeader>
            <CardTitle>{t("tenants.create")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input placeholder={t("tenants.namePlaceholder")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <div className="grid grid-cols-3 gap-3">
              <Input placeholder={t("tenants.slugPlaceholder")} value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} />
              <select className="border rounded px-2 py-1 text-sm" value={form.plan} onChange={(e) => setForm({ ...form, plan: e.target.value as PlanTier })}>
                <option value="free">free</option>
                <option value="starter">starter</option>
                <option value="pro">pro</option>
                <option value="enterprise">enterprise</option>
              </select>
              <Input placeholder={t("tenants.regionPlaceholder")} value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />
            </div>
            <div className="flex gap-2">
              <Button onClick={onCreate}>{t("common.create")}</Button>
              <Button variant="outline" onClick={() => setShowDialog(false)}>{t("common.cancel")}</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {loading ? (
          <div className="col-span-full text-center text-sm text-muted-foreground">{t("common.loading")}</div>
        ) : tenants.length === 0 ? (
          <div className="col-span-full text-center text-sm text-muted-foreground">{t("tenants.empty")}</div>
        ) : (
          tenants.map((tn) => (
            <Card key={tn.id} className="cursor-pointer hover:shadow-md transition" onClick={() => openDetail(tn)}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{tn.name}</CardTitle>
                  <Badge className={planColor[tn.plan]}>{tn.plan}</Badge>
                </div>
                <CardDescription className="font-mono text-xs">{tn.slug} · {tn.region}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <Badge className={statusColor[tn.status]}>{tn.status}</Badge>
                  <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                    {tn.status === "active" ? (
                      <Button size="sm" variant="outline" onClick={() => onSuspend(tn.id)}>
                        <Pause className="h-3 w-3" />
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => onActivate(tn.id)}>
                        <Play className="h-3 w-3" />
                      </Button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => onDelete(tn.id)}>
                      <Trash2 className="h-3 w-3 text-rose-500" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {selected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" />
              {t("tenants.members")} — {selected.name}
            </CardTitle>
            <CardDescription className="font-mono">{selected.id}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder={t("tenants.userId")} value={memberInput.user_id} onChange={(e) => setMemberInput({ ...memberInput, user_id: e.target.value })} />
              <select className="border rounded px-2 text-sm" value={memberInput.role} onChange={(e) => setMemberInput({ ...memberInput, role: e.target.value as MemberRole })}>
                <option value="owner">owner</option>
                <option value="admin">admin</option>
                <option value="member">member</option>
                <option value="viewer">viewer</option>
              </select>
              <Button onClick={onAddMember}>{t("common.add")}</Button>
            </div>
            <div className="space-y-1">
              {members.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("tenants.noMembers")}</p>
              ) : (
                members.map((m) => (
                  <div key={m.user_id} className="flex items-center justify-between p-2 border rounded">
                    <span className="text-sm font-mono">{m.user_id}</span>
                    <Badge>{m.role}</Badge>
                  </div>
                ))
              )}
            </div>
            <Button variant="outline" onClick={() => setSelected(null)}>{t("common.close")}</Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default TenantsPage;
