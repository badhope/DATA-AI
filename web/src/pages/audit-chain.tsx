import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { api } from "@/lib/api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Cloud, ShieldCheck, ShieldX, Plus } from "lucide-react";
import type { AuditChainBlock, AuditChainIntegrity } from "@/lib/types/api";

export function AuditChainPage() {
  const apiClient = api;
  const [integrity, setIntegrity] = useState<AuditChainIntegrity | null>(null);
  const [blocks, setBlocks] = useState<AuditChainBlock[]>([]);
  const [pending, setPending] = useState(0);
  const [entryId, setEntryId] = useState("");
  const [proofResult, setProofResult] = useState<{ block_id: string; entry_id: string; entry_index: number; root: string } | null>(null);

  const load = async () => {
    const i = await apiClient.auditChainIntegrity();
    setIntegrity(i);
    const b = await apiClient.listAuditBlocks();
    setBlocks(b.blocks);
  };

  useEffect(() => {
    load();
  }, []);

  const onAdd = async () => {
    const r = await apiClient.auditChainAdd({
      id: `entry-${Date.now()}`,
      actor: "admin",
      action: "manual.add",
      timestamp: Date.now() / 1000,
    });
    setPending(r.pending);
    load();
  };

  const onSeal = async () => {
    await apiClient.auditChainSeal();
    load();
  };

  const onGetProof = async () => {
    if (!entryId) return;
    const r = await apiClient.auditChainProof(entryId);
    setProofResult(r.proof);
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Cloud className="h-6 w-6" />
          {t("auditChain.title")}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">{t("auditChain.subtitle")}</p>
      </div>

      {integrity && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {integrity.ok ? <ShieldCheck className="h-5 w-5 text-emerald-600" /> : <ShieldX className="h-5 w-5 text-rose-600" />}
              {t("auditChain.integrity")}: {integrity.ok ? t("auditChain.valid") : t("auditChain.tampered")}
            </CardTitle>
            <CardDescription>
              {t("auditChain.blocks")}: {integrity.block_count} · {t("auditChain.pending")}: {pending}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-xs font-mono break-all">latest_root: {integrity.latest_root || "(empty)"}</p>
            {integrity.issues.length > 0 && (
              <div className="mt-2 p-2 bg-rose-50 border border-rose-200 rounded">
                {integrity.issues.map((iss, i) => (
                  <p key={i} className="text-xs text-rose-700">⚠ {iss}</p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>{t("auditChain.addEntry")}</CardTitle>
            <CardDescription>{t("auditChain.addEntryDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm">{t("auditChain.pending")}: <Badge>{pending}</Badge></p>
            <Button onClick={onAdd}><Plus className="h-4 w-4 mr-1" />{t("auditChain.addEntry")}</Button>
            <Button variant="outline" onClick={onSeal}>{t("auditChain.seal")}</Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("auditChain.getProof")}</CardTitle>
            <CardDescription>{t("auditChain.getProofDesc")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Input placeholder="entry_id" value={entryId} onChange={(e) => setEntryId(e.target.value)} />
            <Button onClick={onGetProof}>{t("auditChain.getProof")}</Button>
            {proofResult && (
              <div className="p-2 bg-slate-50 border rounded text-xs font-mono break-all">
                <p>block_id: {proofResult.block_id}</p>
                <p>entry_index: {proofResult.entry_index}</p>
                <p>root: {proofResult.root}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("auditChain.blocks")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-1 max-h-96 overflow-y-auto">
            {blocks.length === 0 ? (
              <p className="text-sm text-muted-foreground">{t("auditChain.noBlocks")}</p>
            ) : (
              blocks.map((b) => (
                <div key={b.id} className="p-2 border rounded text-sm">
                  <div className="flex items-center justify-between">
                    <span className="font-mono">#{b.index} {b.id}</span>
                    <Badge>{b.entry_count} entries</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground font-mono break-all">root: {b.root}</p>
                  <p className="text-xs text-muted-foreground">{new Date(b.timestamp * 1000).toLocaleString()}</p>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default AuditChainPage;
