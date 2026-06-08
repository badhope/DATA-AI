import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Radio, Plus, AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import type { SLAStatusPage, SLAComponent, Incident, SLO, SLOResult } from "@/lib/types/api";

const statusColor: Record<string, string> = {
  operational: "bg-emerald-100 text-emerald-700",
  degraded: "bg-amber-100 text-amber-700",
  partial_outage: "bg-orange-100 text-orange-700",
  major_outage: "bg-rose-100 text-rose-700",
  maintenance: "bg-blue-100 text-blue-700",
};

const overallIcon = (s: string) =>
  s === "operational" ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> : s === "major_outage" ? <XCircle className="h-5 w-5 text-rose-600" /> : <AlertCircle className="h-5 w-5 text-amber-600" />;

export function SlaPage() {
  const apiClient = api;
  const [tab, setTab] = useState<"status" | "slos" | "incidents">("status");
  const [status, setStatus] = useState<SLAStatusPage | null>(null);
  const [slos, setSlos] = useState<SLO[]>([]);
  const [sloResults, setSloResults] = useState<SLOResult[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [newIncident, setNewIncident] = useState({ title: "", severity: "minor" });

  const load = async () => {
    const s = await apiClient.slaStatus();
    setStatus(s);
    const sl = await apiClient.listSLOs();
    setSlos(sl.slos);
    const sr = await apiClient.evaluateAllSLOs();
    setSloResults(sr.reports);
    const inc = await apiClient.listIncidents({ limit: 50 });
    setIncidents(inc.incidents);
  };

  useEffect(() => {
    load();
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, []);

  const onOpenIncident = async () => {
    if (!newIncident.title) return;
    await apiClient.openIncident({ title: newIncident.title, severity: newIncident.severity as "minor" | "major" | "critical", affected_components: [] });
    setNewIncident({ title: "", severity: "minor" });
    load();
  };

  const onResolveIncident = async (id: string) => {
    await apiClient.updateIncident(id, { status: "resolved", message: "Manually resolved" });
    load();
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Radio className="h-6 w-6" />
          {t("sla.title")}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">{t("sla.subtitle")}</p>
      </div>

      <div className="flex gap-2">
        <Button variant={tab === "status" ? "default" : "outline"} onClick={() => setTab("status")}>{t("sla.status")}</Button>
        <Button variant={tab === "slos" ? "default" : "outline"} onClick={() => setTab("slos")}>{t("sla.slos")}</Button>
        <Button variant={tab === "incidents" ? "default" : "outline"} onClick={() => setTab("incidents")}>{t("sla.incidents")}</Button>
      </div>

      {tab === "status" && status && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {overallIcon(status.overall)}
                {t("sla.overall")}: {status.overall}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {status.components.map((c) => (
                  <div key={c.id} className="p-3 border rounded flex items-center justify-between">
                    <span className="text-sm font-medium">{c.name}</span>
                    <Badge className={statusColor[c.status]}>{c.status}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {status.active_incidents.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-rose-600">{t("sla.activeIncidents")}</CardTitle>
              </CardHeader>
              <CardContent>
                {status.active_incidents.map((i) => (
                  <div key={i.id} className="p-3 border rounded mb-2">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{i.title}</span>
                      <Badge className="bg-rose-100 text-rose-700">{i.severity}</Badge>
                    </div>
                    <span className="text-xs text-muted-foreground">{new Date(i.started_at * 1000).toLocaleString()}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {tab === "slos" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("sla.slos")}</CardTitle>
            <CardDescription>{t("sla.slosDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {sloResults.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("sla.noSlos")}</p>
              ) : (
                sloResults.map((r) => (
                  <div key={r.slo_id} className="p-3 border rounded flex items-center justify-between">
                    <div>
                      <span className="text-sm font-medium">{r.name}</span>
                      <span className="text-xs text-muted-foreground ml-2">({r.type})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-mono">{r.current_value?.toFixed(2) ?? "—"} / {r.target}</span>
                      <Badge className={r.status === "ok" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}>{r.status}</Badge>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "incidents" && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{t("sla.openIncident")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex gap-2">
                <Input placeholder={t("sla.incidentTitle")} value={newIncident.title} onChange={(e) => setNewIncident({ ...newIncident, title: e.target.value })} />
                <select className="border rounded px-2 text-sm" value={newIncident.severity} onChange={(e) => setNewIncident({ ...newIncident, severity: e.target.value })}>
                  <option value="minor">minor</option>
                  <option value="major">major</option>
                  <option value="critical">critical</option>
                </select>
                <Button onClick={onOpenIncident}><Plus className="h-4 w-4 mr-1" />{t("sla.open")}</Button>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{t("sla.incidents")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-1">
                {incidents.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
                ) : (
                  incidents.map((i) => (
                    <div key={i.id} className="p-3 border rounded flex items-center justify-between">
                      <div>
                        <span className="text-sm font-medium">{i.title}</span>
                        <Badge className="ml-2">{i.status}</Badge>
                        <Badge className="ml-1" variant="outline">{i.severity}</Badge>
                        <span className="text-xs text-muted-foreground ml-2">{new Date(i.started_at * 1000).toLocaleString()}</span>
                      </div>
                      {i.status !== "resolved" && (
                        <Button size="sm" variant="outline" onClick={() => onResolveIncident(i.id)}>{t("sla.resolve")}</Button>
                      )}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

export default SlaPage;
