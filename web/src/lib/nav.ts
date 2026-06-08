import { type Locale, t as i18n } from "@/lib/i18n";
import {
  Bell,
  Boxes,
  Brain,
  Building2,
  ChartPie,
  CircleDollarSign,
  Cloud,
  Cpu,
  Database,
  FileText,
  Folder,
  Gauge,
  Globe,
  KeyRound,
  LayoutDashboard,
  MessageSquare,
  Plug2,
  Radio,
  Settings,
  ShieldCheck,
  Sparkles,
  Terminal,
  Timer,
  Users,
  Webhook,
  Wrench,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
  description?: string;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

/**
 * Build localized navigation groups. `locale` defaults to the currently
 * active UI locale (auto-detected by `i18n`).
 */
export function getNavGroups(locale?: Locale): NavGroup[] {
  return [
    {
      title: i18n("nav.overview", locale),
      items: [
        {
          label: i18n("nav.overviewDashboard", locale),
          href: "/",
          icon: LayoutDashboard,
          description: i18n("nav.overviewDashboardDesc", locale),
        },
      ],
    },
    {
      title: i18n("nav.convoAndAgents", locale),
      items: [
        {
          label: i18n("nav.chat", locale),
          href: "/chat",
          icon: MessageSquare,
          description: i18n("nav.chatDesc", locale),
        },
        {
          label: i18n("nav.agents", locale),
          href: "/agents",
          icon: Brain,
          description: i18n("nav.agentsDesc", locale),
        },
        {
          label: i18n("nav.team", locale),
          href: "/team",
          icon: Users,
          description: i18n("nav.teamDesc", locale),
        },
      ],
    },
    {
      title: i18n("nav.capabilities", locale),
      items: [
        {
          label: i18n("nav.tools", locale),
          href: "/tools",
          icon: Wrench,
          description: i18n("nav.toolsDesc", locale),
        },
        {
          label: i18n("nav.sandbox", locale),
          href: "/sandbox",
          icon: Terminal,
          description: i18n("nav.sandboxDesc", locale),
        },
        {
          label: i18n("nav.rag", locale),
          href: "/rag",
          icon: Database,
          description: i18n("nav.ragDesc", locale),
        },
        {
          label: i18n("nav.memory", locale),
          href: "/memory",
          icon: Boxes,
          description: i18n("nav.memoryDesc", locale),
        },
        {
          label: i18n("nav.skills", locale),
          href: "/skills",
          icon: Sparkles,
          description: i18n("nav.skillsDesc", locale),
        },
        {
          label: i18n("nav.mcp", locale),
          href: "/mcp",
          icon: Plug2,
          description: i18n("nav.mcpDesc", locale),
        },
      ],
    },
    {
      title: i18n("nav.office", locale),
      items: [
        {
          label: i18n("nav.officeWord", locale),
          href: "/office/word",
          icon: FileText,
          description: i18n("nav.officeWordDesc", locale),
        },
        {
          label: i18n("nav.officePpt", locale),
          href: "/office/ppt",
          icon: ChartPie,
          description: i18n("nav.officePptDesc", locale),
        },
        {
          label: i18n("nav.officeExcel", locale),
          href: "/office/excel",
          icon: Database,
          description: i18n("nav.officeExcelDesc", locale),
        },
        {
          label: i18n("nav.officePdf", locale),
          href: "/office/pdf",
          icon: FileText,
          description: i18n("nav.officePdfDesc", locale),
        },
      ],
    },
    {
      title: i18n("nav.system", locale),
      items: [
        {
          label: i18n("nav.notifications", locale),
          href: "/notifications",
          icon: Bell,
          description: i18n("nav.notificationsDesc", locale),
        },
        {
          label: i18n("nav.models", locale),
          href: "/models",
          icon: Cpu,
          description: i18n("nav.modelsDesc", locale),
        },
      ],
    },
    {
      title: i18n("nav.governance", locale),
      items: [
        {
          label: i18n("nav.audit", locale),
          href: "/audit",
          icon: ShieldCheck,
          description: i18n("nav.auditDesc", locale),
        },
        {
          label: i18n("nav.quota", locale),
          href: "/quota",
          icon: Gauge,
          description: i18n("nav.quotaDesc", locale),
        },
        {
          label: i18n("nav.webhooks", locale),
          href: "/webhooks",
          icon: Webhook,
          description: i18n("nav.webhooksDesc", locale),
        },
        {
          label: i18n("nav.scheduler", locale),
          href: "/scheduler",
          icon: Timer,
          description: i18n("nav.schedulerDesc", locale),
        },
        {
          label: i18n("nav.settings", locale),
          href: "/settings",
          icon: Settings,
          description: i18n("nav.settingsDesc", locale),
        },
      ],
    },
    {
      title: i18n("nav.enterprise", locale),
      items: [
        {
          label: i18n("nav.tenants", locale),
          href: "/tenants",
          icon: Building2,
          description: i18n("nav.tenantsDesc", locale),
        },
        {
          label: i18n("nav.rbac", locale),
          href: "/rbac",
          icon: KeyRound,
          description: i18n("nav.rbacDesc", locale),
        },
        {
          label: i18n("nav.billing", locale),
          href: "/billing",
          icon: CircleDollarSign,
          description: i18n("nav.billingDesc", locale),
        },
        {
          label: i18n("nav.sla", locale),
          href: "/sla",
          icon: Radio,
          description: i18n("nav.slaDesc", locale),
        },
        {
          label: i18n("nav.sso", locale),
          href: "/sso",
          icon: ShieldCheck,
          description: i18n("nav.ssoDesc", locale),
        },
        {
          label: i18n("nav.residency", locale),
          href: "/residency",
          icon: Globe,
          description: i18n("nav.residencyDesc", locale),
        },
        {
          label: i18n("nav.auditChain", locale),
          href: "/audit-chain",
          icon: Cloud,
          description: i18n("nav.auditChainDesc", locale),
        },
        {
          label: i18n("nav.replication", locale),
          href: "/replication",
          icon: Cloud,
          description: i18n("nav.replicationDesc", locale),
        },
        {
          label: i18n("nav.recovery", locale),
          href: "/recovery",
          icon: Cloud,
          description: i18n("nav.recoveryDesc", locale),
        },
        {
          label: i18n("nav.compensation", locale),
          href: "/compensation",
          icon: CircleDollarSign,
          description: i18n("nav.compensationDesc", locale),
        },
      ],
    },
  ];
}

export function getMobileNav(locale?: Locale): NavItem[] {
  return [
    { label: i18n("mobile.chat", locale), href: "/chat", icon: MessageSquare },
    { label: i18n("mobile.agents", locale), href: "/agents", icon: Brain },
    { label: i18n("mobile.tools", locale), href: "/tools", icon: Wrench },
    { label: i18n("mobile.sandbox", locale), href: "/sandbox", icon: Terminal },
    { label: i18n("mobile.rag", locale), href: "/rag", icon: Folder },
    { label: i18n("mobile.settings", locale), href: "/settings", icon: Settings },
  ];
}

export function getOfficeNav(locale?: Locale): NavItem[] {
  return [
    { label: i18n("nav.officeWord", locale), href: "/office/word", icon: FileText },
    { label: i18n("nav.officePpt", locale), href: "/office/ppt", icon: ChartPie },
    { label: i18n("nav.officeExcel", locale), href: "/office/excel", icon: Database },
    { label: i18n("nav.officePdf", locale), href: "/office/pdf", icon: FileText },
  ];
}

// Backwards-compatible defaults (English, computed once at module load).
// Prefer using the `getXxx(locale)` functions inside components.
export const NAV_GROUPS: NavGroup[] = getNavGroups("en");
export const MOBILE_NAV: NavItem[] = getMobileNav("en");
export const OFFICE_NAV: NavItem[] = getOfficeNav("en");
