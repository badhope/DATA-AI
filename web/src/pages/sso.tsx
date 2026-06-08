import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ShieldCheck, Plus, Trash2, ExternalLink } from "lucide-react";
import type { IdentityProvider, SCIMUser, SSOSession } from "@/lib/types/api";

export function SsoPage() {
  const apiClient = api;
  const [tab, setTab] = useState<"idps" | "scim" | "sessions">("idps");
  const [idps, setIdps] = useState<IdentityProvider[]>([]);
  const [scimUsers, setScimUsers] = useState<SCIMUser[]>([]);
  const [sessions, setSessions] = useState<SSOSession[]>([]);
  const [show, setShow] = useState(false);
  const [form, setForm] = useState({ name: "", type: "oidc", issuer: "", client_id: "", client_secret: "" });

  const load = async () => {
    const r = await apiClient.listIDPs();
    setIdps(r.idps);
    const s = await apiClient.listSCIMUsers();
    setScimUsers(s.users);
    const sess = await apiClient.listSSOSessions();
    setSessions(sess.sessions);
  };

  useEffect(() => {
    load();
  }, []);

  const onCreate = async () => {
    if (!form.name) return;
    await apiClient.registerIDP(form as unknown as Parameters<typeof apiClient.registerIDP>[0]);
    setShow(false);
    setForm({ name: "", type: "oidc", issuer: "", client_id: "", client_secret: "" });
    load();
  };

  const onDelete = async (id: string) => {
    if (!confirm(t("common.confirmDelete"))) return;
    await apiClient.deleteIDP(id);
    load();
  };

  const onUpsertSCIM = async () => {
    const user_name = prompt(t("sso.scimUserName"));
    if (!user_name) return;
    await apiClient.upsertSCIMUser({ user_name });
    load();
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <ShieldCheck className="h-6 w-6" />
            {t("sso.title")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{t("sso.subtitle")}</p>
        </div>
        {tab === "idps" && <Button onClick={() => setShow(true)}><Plus className="h-4 w-4 mr-1" />{t("sso.registerIdp")}</Button>}
        {tab === "scim" && <Button onClick={onUpsertSCIM}><Plus className="h-4 w-4 mr-1" />{t("sso.upsertUser")}</Button>}
      </div>

      <div className="flex gap-2">
        <Button variant={tab === "idps" ? "default" : "outline"} onClick={() => setTab("idps")}>{t("sso.idps")}</Button>
        <Button variant={tab === "scim" ? "default" : "outline"} onClick={() => setTab("scim")}>{t("sso.scim")}</Button>
        <Button variant={tab === "sessions" ? "default" : "outline"} onClick={() => setTab("sessions")}>{t("sso.sessions")}</Button>
      </div>

      {show && (
        <Card>
          <CardHeader>
            <CardTitle>{t("sso.registerIdp")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input placeholder={t("sso.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            <div className="grid grid-cols-2 gap-2">
              <select className="border rounded px-2 text-sm" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                <option value="oidc">OIDC</option>
                <option value="saml">SAML</option>
                <option value="ldap">LDAP</option>
              </select>
              <Input placeholder="issuer URL" value={form.issuer} onChange={(e) => setForm({ ...form, issuer: e.target.value })} />
              <Input placeholder="client_id" value={form.client_id} onChange={(e) => setForm({ ...form, client_id: e.target.value })} />
              <Input placeholder="client_secret" type="password" value={form.client_secret} onChange={(e) => setForm({ ...form, client_secret: e.target.value })} />
            </div>
            <div className="flex gap-2">
              <Button onClick={onCreate}>{t("common.create")}</Button>
              <Button variant="outline" onClick={() => setShow(false)}>{t("common.cancel")}</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "idps" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {idps.length === 0 ? (
            <p className="text-sm text-muted-foreground col-span-full">{t("sso.noIdps")}</p>
          ) : (
            idps.map((i) => (
              <Card key={i.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{i.name}</CardTitle>
                    <Badge>{i.type.toUpperCase()}</Badge>
                  </div>
                  <CardDescription className="font-mono text-xs">{i.issuer}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-xs text-muted-foreground space-y-1">
                    <p>Client ID: <span className="font-mono">{i.client_id}</span></p>
                    {i.allowed_email_domains.length > 0 && (
                      <p>Allowed: {i.allowed_email_domains.join(", ")}</p>
                    )}
                    <p>Auto provision: {i.auto_provision ? "✓" : "✗"}</p>
                  </div>
                  <div className="flex gap-2 mt-3">
                    <Button size="sm" variant="outline" onClick={() => onDelete(i.id)}>
                      <Trash2 className="h-3 w-3 mr-1" />{t("common.delete")}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {tab === "scim" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("sso.scim")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {scimUsers.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
              ) : (
                scimUsers.map((u) => (
                  <div key={u.id} className="flex items-center justify-between p-2 border rounded">
                    <div>
                      <span className="text-sm font-medium">{u.user_name}</span>
                      <span className="text-xs text-muted-foreground ml-2">{u.display_name}</span>
                    </div>
                    <Badge className={u.active ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-500"}>
                      {u.active ? "active" : "inactive"}
                    </Badge>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "sessions" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("sso.sessions")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1 max-h-96 overflow-y-auto">
              {sessions.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("sso.noSessions")}</p>
              ) : (
                sessions.map((s) => (
                  <div key={s.id} className="p-2 border rounded text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-mono">{s.user_id}</span>
                      <span className="text-xs text-muted-foreground">{s.email}</span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      expires {new Date(s.expires_at * 1000).toLocaleString()} · ip={s.ip || "—"}
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

export default SsoPage;
