import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Globe, Plus, Trash2, MapPin, CheckCircle2, XCircle } from "lucide-react";
import type { Region, ResidencyPolicy, ResidencyAssignment, ResidencyStats, DataClass } from "@/lib/types/api";

export function ResidencyPage() {
  const apiClient = api;
  const [tab, setTab] = useState<"regions" | "policies" | "route" | "assignments">("regions");
  const [regions, setRegions] = useState<Region[]>([]);
  const [policies, setPolicies] = useState<ResidencyPolicy[]>([]);
  const [assignments, setAssignments] = useState<ResidencyAssignment[]>([]);
  const [stats, setStats] = useState<ResidencyStats | null>(null);
  const [routeForm, setRouteForm] = useState({ resource_id: "test-001", data_class: "pii", tenant_id: "", prefer_region: "" });
  const [routeResult, setRouteResult] = useState<ResidencyAssignment | null>(null);
  const [newRegion, setNewRegion] = useState({ id: "", name: "", country: "" });
  const [newPolicy, setNewPolicy] = useState({ name: "", data_class: "user_data" });

  const load = async () => {
    const r = await apiClient.listRegions();
    setRegions(r.regions);
    const p = await apiClient.listResidencyPolicies();
    setPolicies(p.policies);
    const a = await apiClient.listResidencyAssignments();
    setAssignments(a.assignments);
    const s = await apiClient.residencyStats();
    setStats(s);
  };

  useEffect(() => {
    load();
  }, []);

  const onAddRegion = async () => {
    if (!newRegion.id) return;
    await apiClient.addRegion(newRegion as unknown as Parameters<typeof apiClient.addRegion>[0]);
    setNewRegion({ id: "", name: "", country: "" });
    load();
  };

  const onSetStatus = async (id: string, status: string) => {
    await apiClient.setRegionStatus(id, status);
    load();
  };

  const onAddPolicy = async () => {
    if (!newPolicy.name) return;
    await apiClient.addResidencyPolicy({
      name: newPolicy.name,
      data_class: newPolicy.data_class as DataClass,
      allowed_regions: [],
      forbidden_regions: [],
      allow_cross_region_transfer: false,
      encryption_required: true,
      retention_days: 365,
      enabled: true,
    });
    setNewPolicy({ name: "", data_class: "user_data" });
    load();
  };

  const onDeletePolicy = async (id: string) => {
    if (!confirm(t("common.confirmDelete"))) return;
    await apiClient.deleteResidencyPolicy(id);
    load();
  };

  const onRoute = async () => {
    const r = await apiClient.residencyRoute({
      ...routeForm,
      data_class: routeForm.data_class as DataClass,
    });
    setRouteResult(r.assignment);
    load();
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Globe className="h-6 w-6" />
          {t("residency.title")}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">{t("residency.subtitle")}</p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("residency.regions")}</CardDescription>
              <CardTitle className="text-2xl">{stats.regions}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("residency.policies")}</CardDescription>
              <CardTitle className="text-2xl">{stats.policies}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("residency.assignments")}</CardDescription>
              <CardTitle className="text-2xl">{stats.total_assignments}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("residency.byClass")}</CardDescription>
              <CardTitle className="text-sm">{Object.entries(stats.by_data_class).map(([k, v]) => `${k}:${v}`).join(" / ") || "—"}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      <div className="flex gap-2">
        <Button variant={tab === "regions" ? "default" : "outline"} onClick={() => setTab("regions")}>{t("residency.regions")}</Button>
        <Button variant={tab === "policies" ? "default" : "outline"} onClick={() => setTab("policies")}>{t("residency.policies")}</Button>
        <Button variant={tab === "route" ? "default" : "outline"} onClick={() => setTab("route")}>{t("residency.route")}</Button>
        <Button variant={tab === "assignments" ? "default" : "outline"} onClick={() => setTab("assignments")}>{t("residency.assignments")}</Button>
      </div>

      {tab === "regions" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("residency.regions")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder="region id (e.g. cn-east)" value={newRegion.id} onChange={(e) => setNewRegion({ ...newRegion, id: e.target.value })} />
              <Input placeholder="name" value={newRegion.name} onChange={(e) => setNewRegion({ ...newRegion, name: e.target.value })} />
              <Input placeholder="country" value={newRegion.country} onChange={(e) => setNewRegion({ ...newRegion, country: e.target.value })} />
              <Button onClick={onAddRegion}><Plus className="h-4 w-4 mr-1" />{t("common.create")}</Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {regions.map((r) => (
                <div key={r.id} className="p-3 border rounded">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4" />
                      <span className="font-medium text-sm">{r.id}</span>
                    </div>
                    <Badge className={r.status === "active" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}>{r.status}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{r.name} · {r.country} · {r.tier}</p>
                  <div className="flex gap-1 mt-2">
                    {r.status === "active" ? (
                      <Button size="sm" variant="outline" onClick={() => onSetStatus(r.id, "offline")}>{t("residency.deactivate")}</Button>
                    ) : (
                      <Button size="sm" variant="outline" onClick={() => onSetStatus(r.id, "active")}>{t("residency.activate")}</Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "policies" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("residency.policies")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder={t("rbac.namePlaceholder")} value={newPolicy.name} onChange={(e) => setNewPolicy({ ...newPolicy, name: e.target.value })} />
              <select className="border rounded px-2 text-sm" value={newPolicy.data_class} onChange={(e) => setNewPolicy({ ...newPolicy, data_class: e.target.value })}>
                <option value="user_data">user_data</option>
                <option value="pii">pii</option>
                <option value="phi">phi</option>
                <option value="financial">financial</option>
                <option value="audit_log">audit_log</option>
                <option value="embedding">embedding</option>
              </select>
              <Button onClick={onAddPolicy}><Plus className="h-4 w-4 mr-1" />{t("common.create")}</Button>
            </div>
            <div className="space-y-1">
              {policies.map((p) => (
                <div key={p.id} className="flex items-center justify-between p-2 border rounded">
                  <div>
                    <span className="text-sm font-medium">{p.name}</span>
                    <Badge className="ml-2">{p.data_class}</Badge>
                    <span className="text-xs text-muted-foreground ml-2">{p.allowed_regions.length} allowed · {p.forbidden_regions.length} forbidden</span>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => onDeletePolicy(p.id)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "route" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("residency.route")}</CardTitle>
            <CardDescription>{t("residency.routeDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="resource_id" value={routeForm.resource_id} onChange={(e) => setRouteForm({ ...routeForm, resource_id: e.target.value })} />
              <select className="border rounded px-2 text-sm" value={routeForm.data_class} onChange={(e) => setRouteForm({ ...routeForm, data_class: e.target.value })}>
                <option value="user_data">user_data</option>
                <option value="pii">pii</option>
                <option value="phi">phi</option>
                <option value="financial">financial</option>
              </select>
              <Input placeholder="tenant_id" value={routeForm.tenant_id} onChange={(e) => setRouteForm({ ...routeForm, tenant_id: e.target.value })} />
              <Input placeholder="prefer_region" value={routeForm.prefer_region} onChange={(e) => setRouteForm({ ...routeForm, prefer_region: e.target.value })} />
            </div>
            <Button onClick={onRoute}>{t("residency.route")}</Button>
            {routeResult && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span className="text-sm">{routeResult.resource_id} → <span className="font-mono">{routeResult.region_id}</span></span>
                <Badge>{routeResult.data_class}</Badge>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "assignments" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("residency.assignments")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {assignments.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
              ) : (
                assignments.map((a) => (
                  <div key={a.id} className="p-2 border rounded text-sm flex items-center justify-between">
                    <span className="font-mono">{a.resource_id}</span>
                    <div>
                      <Badge className="mr-2">{a.data_class}</Badge>
                      <span className="text-xs">{a.region_id}</span>
                      {a.encrypted && <span className="ml-2 text-xs text-emerald-600">🔒</span>}
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default ResidencyPage;
