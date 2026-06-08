import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CircleDollarSign, Plus, Trash2, Download, AlertTriangle } from "lucide-react";
import type { Budget, CostCenter, PricingModel, BillingSummary, BudgetAlert } from "@/lib/types/api";

export function BillingPage() {
  const apiClient = api;
  const [tab, setTab] = useState<"summary" | "pricing" | "budgets" | "centers">("summary");
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [pricing, setPricing] = useState<PricingModel[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [costCenters, setCostCenters] = useState<CostCenter[]>([]);
  const [alerts, setAlerts] = useState<BudgetAlert[]>([]);
  const [tenantId, setTenantId] = useState("");

  const load = async () => {
    const s = await apiClient.billingSummary(tenantId ? { tenant_id: tenantId } : undefined);
    setSummary(s.summary);
    const p = await apiClient.listPricing();
    setPricing(p.pricing);
    const b = await apiClient.listBudgets();
    setBudgets(b.budgets);
    const c = await apiClient.listCostCenters(tenantId ? { tenant_id: tenantId } : undefined);
    setCostCenters(c.cost_centers);
    const chk = await apiClient.budgetCheck(tenantId ? { tenant_id: tenantId } : undefined);
    setAlerts(chk.alerts);
  };

  useEffect(() => {
    load();
  }, [tenantId]);

  const onCreateBudget = async () => {
    const name = prompt(t("billing.budgetName"));
    if (!name) return;
    await apiClient.setBudget({
      name,
      scope: "tenant",
      scope_id: tenantId,
      period: "monthly",
      amount_usd: 1000,
      hard_limit: false,
      warn_threshold: 0.8,
      enabled: true,
    });
    load();
  };

  const onDeleteBudget = async (id: string) => {
    if (!confirm(t("common.confirmDelete"))) return;
    await apiClient.deleteBudget(id);
    load();
  };

  const onAddCC = async () => {
    const name = prompt(t("billing.ccName"));
    if (!name) return;
    await apiClient.addCostCenter({ tenant_id: tenantId, name });
    load();
  };

  const onExportInvoice = async () => {
    if (!tenantId) {
      alert(t("billing.tenantRequired"));
      return;
    }
    const now = Math.floor(Date.now() / 1000);
    const since = now - 30 * 86400;
    const r = await apiClient.exportInvoice({ tenant_id: tenantId, since, until: now, format: "json" });
    const blob = new Blob([r.invoice], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `invoice-${tenantId}-${since}-${now}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <CircleDollarSign className="h-6 w-6" />
            {t("billing.title")}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{t("billing.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          <Input placeholder="tenant_id" value={tenantId} onChange={(e) => setTenantId(e.target.value)} className="w-48" />
          <Button variant="outline" onClick={onExportInvoice}><Download className="h-4 w-4 mr-1" />{t("billing.invoice")}</Button>
        </div>
      </div>

      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <div key={i} className={`p-3 rounded border flex items-center gap-2 ${a.level === "exceeded" ? "bg-rose-50 border-rose-200" : "bg-amber-50 border-amber-200"}`}>
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-medium">{a.budget_name}</span>
              <span className="text-xs">${a.used_usd} / ${a.limit_usd} ({a.usage_pct}%)</span>
            </div>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <Button variant={tab === "summary" ? "default" : "outline"} onClick={() => setTab("summary")}>{t("billing.summary")}</Button>
        <Button variant={tab === "pricing" ? "default" : "outline"} onClick={() => setTab("pricing")}>{t("billing.pricing")}</Button>
        <Button variant={tab === "budgets" ? "default" : "outline"} onClick={() => setTab("budgets")}>{t("billing.budgets")}</Button>
        <Button variant={tab === "centers" ? "default" : "outline"} onClick={() => setTab("centers")}>{t("billing.costCenters")}</Button>
      </div>

      {tab === "summary" && summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("billing.totalCost")}</CardDescription>
              <CardTitle className="text-2xl">${summary.total_cost_usd.toFixed(2)}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("billing.totalTokens")}</CardDescription>
              <CardTitle className="text-2xl">{summary.total_tokens.toLocaleString()}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>{t("billing.totalRequests")}</CardDescription>
              <CardTitle className="text-2xl">{summary.total_requests.toLocaleString()}</CardTitle>
            </CardHeader>
          </Card>
          <Card className="md:col-span-3">
            <CardHeader>
              <CardTitle>{t("billing.byModel")}</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left">
                    <th>Model</th>
                    <th>Cost</th>
                    <th>Tokens</th>
                    <th>Requests</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(summary.by_model).map(([m, s]) => (
                    <tr key={m} className="border-t">
                      <td className="py-1 font-mono">{m}</td>
                      <td>${s.cost_usd.toFixed(4)}</td>
                      <td>{s.tokens.toLocaleString()}</td>
                      <td>{s.requests.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "pricing" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("billing.pricing")}</CardTitle>
            <CardDescription>{t("billing.pricingDesc")}</CardDescription>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left">
                  <th>Model</th>
                  <th>Input/1k</th>
                  <th>Output/1k</th>
                  <th>Cached/1k</th>
                  <th>Currency</th>
                </tr>
              </thead>
              <tbody>
                {pricing.map((p) => (
                  <tr key={p.model_id} className="border-t">
                    <td className="py-1 font-mono">{p.model_id}</td>
                    <td>${p.input_per_1k}</td>
                    <td>${p.output_per_1k}</td>
                    <td>${p.cached_input_per_1k}</td>
                    <td>{p.currency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {tab === "budgets" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{t("billing.budgets")}</CardTitle>
            <Button size="sm" onClick={onCreateBudget}><Plus className="h-4 w-4 mr-1" />{t("common.create")}</Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {budgets.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
              ) : (
                budgets.map((b) => (
                  <div key={b.id} className="flex items-center justify-between p-2 border rounded">
                    <div>
                      <span className="text-sm font-medium">{b.name}</span>
                      <Badge className="ml-2">{b.scope}</Badge>
                      <span className="text-xs text-muted-foreground ml-2">${b.amount_usd} / {b.period} {b.hard_limit && "· hard"}</span>
                    </div>
                    <Button size="sm" variant="outline" onClick={() => onDeleteBudget(b.id)}>
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "centers" && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{t("billing.costCenters")}</CardTitle>
            <Button size="sm" onClick={onAddCC}><Plus className="h-4 w-4 mr-1" />{t("common.create")}</Button>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {costCenters.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t("common.empty")}</p>
              ) : (
                costCenters.map((c) => (
                  <div key={c.id} className="flex items-center justify-between p-2 border rounded">
                    <span className="text-sm">{c.name}</span>
                    <span className="text-xs text-muted-foreground">{c.code}</span>
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

export default BillingPage;
