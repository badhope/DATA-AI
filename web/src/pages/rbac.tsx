import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { KeyRound, Plus, Trash2, ShieldCheck, ShieldX } from "lucide-react";
import type { RBACRole, Decision, Policy, Assignment, Permission } from "@/lib/types/api";

export function RbacPage() {
  const apiClient = api;
  const [tab, setTab] = useState<"roles" | "policies" | "check" | "decisions">("roles");
  const [roles, setRoles] = useState<RBACRole[]>([]);
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [checkForm, setCheckForm] = useState({ user_id: "", resource: "agent", action: "read", tenant_id: "" });
  const [checkResult, setCheckResult] = useState<Decision | null>(null);
  const [newRole, setNewRole] = useState({ name: "", description: "" });
  const [newPolicy, setNewPolicy] = useState({ name: "", effect: "allow", priority: 100 });

  const load = async () => {
    const r = await apiClient.listRoles();
    setRoles(r.roles);
    const p = await apiClient.listRbacPolicies();
    setPolicies(p.policies);
    const d = await apiClient.rbacRecentDecisions(50);
    setDecisions(d.decisions);
  };

  useEffect(() => {
    load();
  }, []);

  const onCreateRole = async () => {
    if (!newRole.name) return;
    await apiClient.createRole({ name: newRole.name, description: newRole.description, permissions: [] as Permission[] });
    setNewRole({ name: "", description: "" });
    load();
  };

  const onDeleteRole = async (id: string) => {
    if (!confirm(t("common.confirmDelete"))) return;
    await apiClient.deleteRole(id);
    load();
  };

  const onCreatePolicy = async () => {
    if (!newPolicy.name) return;
    await apiClient.createRbacPolicy({
      name: newPolicy.name,
      effect: newPolicy.effect as "allow" | "deny",
      priority: newPolicy.priority,
      conditions: [{ field: "env.ip", op: "cidr_match", value: "10.0.0.0/8" }],
    });
    setNewPolicy({ name: "", effect: "allow", priority: 100 });
    load();
  };

  const onDeletePolicy = async (id: string) => {
    await apiClient.deleteRbacPolicy(id);
    load();
  };

  const onCheck = async () => {
    const r = await apiClient.rbacCheck(checkForm);
    setCheckResult(r.decision);
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <KeyRound className="h-6 w-6" />
          {t("rbac.title")}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">{t("rbac.subtitle")}</p>
      </div>

      <div className="flex gap-2">
        <Button variant={tab === "roles" ? "default" : "outline"} onClick={() => setTab("roles")}>{t("rbac.roles")}</Button>
        <Button variant={tab === "policies" ? "default" : "outline"} onClick={() => setTab("policies")}>{t("rbac.policies")}</Button>
        <Button variant={tab === "check" ? "default" : "outline"} onClick={() => setTab("check")}>{t("rbac.check")}</Button>
        <Button variant={tab === "decisions" ? "default" : "outline"} onClick={() => setTab("decisions")}>{t("rbac.decisions")}</Button>
      </div>

      {tab === "roles" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("rbac.roles")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder={t("rbac.namePlaceholder")} value={newRole.name} onChange={(e) => setNewRole({ ...newRole, name: e.target.value })} />
              <Input placeholder={t("rbac.descPlaceholder")} value={newRole.description} onChange={(e) => setNewRole({ ...newRole, description: e.target.value })} />
              <Button onClick={onCreateRole}><Plus className="h-4 w-4 mr-1" />{t("common.create")}</Button>
            </div>
            <div className="space-y-1">
              {roles.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-2 border rounded">
                  <div>
                    <span className="text-sm font-medium">{r.name}</span>
                    {r.is_system && <Badge variant="outline" className="ml-2 text-xs">system</Badge>}
                    <span className="text-xs text-muted-foreground ml-2">{r.permissions.length} perms</span>
                  </div>
                  {!r.is_system && (
                    <Button size="sm" variant="outline" onClick={() => onDeleteRole(r.id)}>
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "policies" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("rbac.policies")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2">
              <Input placeholder={t("rbac.namePlaceholder")} value={newPolicy.name} onChange={(e) => setNewPolicy({ ...newPolicy, name: e.target.value })} />
              <select className="border rounded px-2 text-sm" value={newPolicy.effect} onChange={(e) => setNewPolicy({ ...newPolicy, effect: e.target.value })}>
                <option value="allow">allow</option>
                <option value="deny">deny</option>
              </select>
              <Input type="number" placeholder="priority" value={newPolicy.priority} onChange={(e) => setNewPolicy({ ...newPolicy, priority: Number(e.target.value) })} />
              <Button onClick={onCreatePolicy}><Plus className="h-4 w-4 mr-1" />{t("common.create")}</Button>
            </div>
            <div className="space-y-1">
              {policies.map((p) => (
                <div key={p.id} className="flex items-center justify-between p-2 border rounded">
                  <div>
                    <span className="text-sm font-medium">{p.name}</span>
                    <Badge className="ml-2" variant={p.effect === "deny" ? "error" : "default"}>{p.effect}</Badge>
                    <span className="text-xs text-muted-foreground ml-2">prio={p.priority} · {p.conditions.length} cond</span>
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

      {tab === "check" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("rbac.check")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <Input placeholder="user_id" value={checkForm.user_id} onChange={(e) => setCheckForm({ ...checkForm, user_id: e.target.value })} />
              <Input placeholder="tenant_id" value={checkForm.tenant_id} onChange={(e) => setCheckForm({ ...checkForm, tenant_id: e.target.value })} />
              <Input placeholder="resource" value={checkForm.resource} onChange={(e) => setCheckForm({ ...checkForm, resource: e.target.value })} />
              <Input placeholder="action" value={checkForm.action} onChange={(e) => setCheckForm({ ...checkForm, action: e.target.value })} />
            </div>
            <Button onClick={onCheck}>{t("rbac.check")}</Button>
            {checkResult && (
              <div className={`p-3 rounded border flex items-center gap-2 ${checkResult.allowed ? "bg-emerald-50 border-emerald-200" : "bg-rose-50 border-rose-200"}`}>
                {checkResult.allowed ? <ShieldCheck className="h-4 w-4 text-emerald-600" /> : <ShieldX className="h-4 w-4 text-rose-600" />}
                <span className="text-sm font-medium">{checkResult.allowed ? "ALLOW" : "DENY"}</span>
                <span className="text-xs text-muted-foreground">— {checkResult.reason}</span>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "decisions" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("rbac.decisions")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {decisions.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
              ) : (
                decisions.map((d, i) => (
                  <div key={i} className="p-2 border rounded text-sm flex items-center gap-2">
                    <Badge className={d.allowed ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}>
                      {d.allowed ? "ALLOW" : "DENY"}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{new Date(d.evaluated_at * 1000).toLocaleString()}</span>
                    <span className="text-xs">{d.reason}</span>
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

export default RbacPage;
