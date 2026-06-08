"use client";

import { BackgroundFX } from "@/components/layout/background-fx";
import { MobileBottomNav } from "@/components/layout/mobile-bottom-nav";
import { MobileSidebar } from "@/components/layout/mobile-sidebar";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useSettings } from "@/lib/stores/settings";
import { AgentDetailPage } from "@/pages/agent-detail";
import { AgentsPage } from "@/pages/agents";
import { AuditPage } from "@/pages/audit";
import { ChatPage } from "@/pages/chat";
import { DashboardPage } from "@/pages/dashboard";
import { MemoryPage } from "@/pages/memory";
import { ModelsPage } from "@/pages/models";
import { NotFoundPage } from "@/pages/not-found";
import { NotificationsPage } from "@/pages/notifications";
import { ExcelPage } from "@/pages/office/excel";
import { PdfPage } from "@/pages/office/pdf";
import { PptPage } from "@/pages/office/ppt";
import { WordPage } from "@/pages/office/word";
import { MCPPage } from "@/pages/mcp";
import { QuotaPage } from "@/pages/quota";
import { RagPage } from "@/pages/rag";
import { RagDocumentPage } from "@/pages/rag-document";
import { SandboxPage } from "@/pages/sandbox";
import { SandboxDetailPage } from "@/pages/sandbox-detail";
import { SchedulerPage } from "@/pages/scheduler";
import { SettingsPage } from "@/pages/settings";
import { SkillsPage } from "@/pages/skills";
import { TeamPage } from "@/pages/team";
import { TeamDetailPage } from "@/pages/team-detail";
import { ToolDetailPage } from "@/pages/tool-detail";
import { ToolsPage } from "@/pages/tools";
import { WebhooksPage } from "@/pages/webhooks";
import { AnimatePresence, motion } from "framer-motion";
import * as React from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { AuditChainPage } from "@/pages/audit-chain";
import { BillingPage } from "@/pages/billing";
import { RbacPage } from "@/pages/rbac";
import { ResidencyPage } from "@/pages/residency";
import { SlaPage } from "@/pages/sla";
import { SsoPage } from "@/pages/sso";
import { TenantsPage } from "@/pages/tenants";
import { ReplicationPage } from "@/pages/replication";
import { RecoveryPage } from "@/pages/recovery";
import { CompensationPage } from "@/pages/compensation";

export function App() {
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const location = useLocation();
  const theme = useSettings((s) => s.theme);

  // Apply theme class to <html>
  React.useEffect(() => {
    const root = document.documentElement;
    const apply = (t: "dark" | "light" | "system") => {
      if (t === "system") {
        const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        root.classList.toggle("light", !isDark);
      } else {
        root.classList.toggle("light", t === "light");
      }
    };
    apply(theme);
    if (theme === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => apply("system");
      mq.addEventListener("change", onChange);
      return () => mq.removeEventListener("change", onChange);
    }
  }, [theme]);

  // Keyboard shortcuts
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        setCollapsed((c) => !c);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <TooltipProvider>
      <BackgroundFX>
        <div className="flex min-h-screen w-full">
          <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
          <MobileSidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar onMobileMenuOpen={() => setMobileOpen(true)} />
            <main className="flex-1 overflow-x-hidden pb-20 md:pb-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={location.pathname}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                  className="mx-auto w-full max-w-[1600px] p-4 sm:p-6 lg:p-8"
                >
                  <Routes location={location}>
                    <Route path="/" element={<DashboardPage />} />
                    <Route path="/chat" element={<ChatPage />} />
                    <Route path="/chat/:sessionId" element={<ChatPage />} />
                    <Route path="/agents" element={<AgentsPage />} />
                    <Route path="/agents/:agentId" element={<AgentDetailPage />} />
                    <Route path="/team" element={<TeamPage />} />
                    <Route path="/team/:teamId" element={<TeamDetailPage />} />
                    <Route path="/tools" element={<ToolsPage />} />
                    <Route path="/tools/:toolName" element={<ToolDetailPage />} />
                    <Route path="/memory" element={<MemoryPage />} />
                    <Route path="/rag" element={<RagPage />} />
                    <Route path="/rag/:docId" element={<RagDocumentPage />} />
                    <Route path="/sandbox" element={<SandboxPage />} />
                    <Route path="/sandbox/:sandboxId" element={<SandboxDetailPage />} />
                    <Route path="/office/word" element={<WordPage />} />
                    <Route path="/office/ppt" element={<PptPage />} />
                    <Route path="/office/excel" element={<ExcelPage />} />
                    <Route path="/office/pdf" element={<PdfPage />} />
                    <Route path="/models" element={<ModelsPage />} />
                    <Route path="/skills" element={<SkillsPage />} />
                    <Route path="/notifications" element={<NotificationsPage />} />
                    <Route path="/audit" element={<AuditPage />} />
                    <Route path="/quota" element={<QuotaPage />} />
                    <Route path="/webhooks" element={<WebhooksPage />} />
                    <Route path="/scheduler" element={<SchedulerPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/tenants" element={<TenantsPage />} />
                    <Route path="/rbac" element={<RbacPage />} />
                    <Route path="/billing" element={<BillingPage />} />
                    <Route path="/sla" element={<SlaPage />} />
                    <Route path="/sso" element={<SsoPage />} />
                    <Route path="/residency" element={<ResidencyPage />} />
                    <Route path="/audit-chain" element={<AuditChainPage />} />
                    <Route path="/replication" element={<ReplicationPage />} />
                    <Route path="/recovery" element={<RecoveryPage />} />
                    <Route path="/compensation" element={<CompensationPage />} />
                    <Route path="*" element={<NotFoundPage />} />
                  </Routes>
                </motion.div>
              </AnimatePresence>
            </main>
          </div>
          <MobileBottomNav />
        </div>
        <Toaster />
      </BackgroundFX>
    </TooltipProvider>
  );
}
