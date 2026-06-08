"use client";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { getClient } from "@/lib/api/client";
import { useT } from "@/lib/i18n";
import { getNavGroups } from "@/lib/nav";
import { useSettings } from "@/lib/stores/settings";
import type { HealthResponse } from "@/lib/types/api";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronsLeft } from "lucide-react";
import * as React from "react";
import { Link, useLocation } from "react-router-dom";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  className?: string;
}

export function Sidebar({ collapsed, onToggle, className }: SidebarProps) {
  const location = useLocation();
  const { t, locale } = useT();
  const navGroups = React.useMemo(() => getNavGroups(locale), [locale]);
  const baseUrl = useSettings((s) => s.baseUrl);
  const health = useQuery<HealthResponse>({
    queryKey: ["health", baseUrl],
    queryFn: async () => {
      try {
        return await getClient().health();
      } catch (e) {
        return {
          status: "down" as const,
          version: "unknown",
          timestamp: Date.now() / 1000,
          components: {},
        };
      }
    },
    refetchInterval: 15_000,
    retry: false,
    staleTime: 5_000,
  });

  const status = health.data?.status;
  const isHealthy = status === "healthy";
  const isDegraded = status === "degraded";
  const isOffline = status === "down" || (!health.isLoading && health.isError);
  const statusText = isHealthy
    ? t("status.healthy")
    : isDegraded
      ? t("status.degraded")
      : isOffline
        ? t("status.down")
        : t("status.checking");
  const statusColor = isHealthy
    ? "text-success"
    : isDegraded
      ? "text-warning"
      : "text-destructive";

  return (
    <TooltipProvider delayDuration={200}>
      <aside
        className={cn(
          "sticky top-0 z-30 hidden h-screen shrink-0 flex-col border-r border-border bg-background",
          collapsed ? "w-[56px]" : "w-[248px]",
          "transition-[width] duration-200",
          className,
        )}
      >
        {/* Logo / 报头 */}
        <div className="flex h-14 items-center gap-2 border-b border-border px-3">
          <Link to="/" className="flex items-center gap-2 overflow-hidden">
            {/* logo 改为字母方块, 1px border */}
            <div className="flex h-7 w-7 shrink-0 items-center justify-center border border-foreground bg-foreground text-background font-mono text-[13px] font-bold">
              D
            </div>
            {!collapsed && (
              <div className="flex flex-col leading-none">
                <span className="font-display text-[15px] font-bold tracking-tight">
                  DATA<span className="text-primary">/</span>AI
                </span>
                <span className="mt-0.5 text-[9px] font-mono uppercase tracking-[0.18em] text-muted-foreground">
                  Agent Console
                </span>
              </div>
            )}
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className={cn("ml-auto h-6 w-6", collapsed && "ml-0")}
            aria-label={t("nav.collapse")}
          >
            <ChevronsLeft
              className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")}
            />
          </Button>
        </div>

        {/* Nav — 编辑式目录 */}
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {navGroups.map((group, gi) => (
            <div key={group.title} className={cn(gi > 0 && "mt-4")}>
              {!collapsed && (
                <div className="mb-1 flex items-baseline gap-2 px-2.5">
                  <span className="font-mono text-[9px] font-medium uppercase tracking-[0.16em] text-muted-foreground/60">
                    {String(gi + 1).padStart(2, "0")}
                  </span>
                  <h3 className="font-mono text-[9px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                    {group.title}
                  </h3>
                </div>
              )}
              <ul className="space-y-px">
                {group.items.map((item, ii) => {
                  const Icon = item.icon;
                  const active =
                    item.href === "/"
                      ? location.pathname === "/"
                      : location.pathname === item.href ||
                        location.pathname.startsWith(`${item.href}/`);

                  const linkContent = (
                    <Link
                      to={item.href}
                      className={cn(
                        "group relative flex items-center gap-2.5 px-2.5 py-1.5 text-[13px] transition-colors",
                        active
                          ? "bg-foreground text-background"
                          : "text-foreground/80 hover:bg-accent",
                        collapsed && "justify-center px-0",
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-[14px] w-[14px] shrink-0",
                          active ? "text-primary" : "text-foreground/60 group-hover:text-foreground",
                        )}
                        strokeWidth={1.75}
                      />
                      {!collapsed && (
                        <>
                          <span className="truncate font-medium tracking-tight">
                            {item.label}
                          </span>
                          {item.badge && (
                            <span className="ml-auto font-mono text-[9px] uppercase tracking-wider opacity-70">
                              {item.badge}
                            </span>
                          )}
                          {active && (
                            <span className="ml-auto text-primary">●</span>
                          )}
                        </>
                      )}
                    </Link>
                  );

                  if (collapsed) {
                    return (
                      <li key={item.href}>
                        <Tooltip>
                          <TooltipTrigger asChild>{linkContent}</TooltipTrigger>
                          <TooltipContent side="right">
                            <div className="font-medium">{item.label}</div>
                            {item.description && (
                              <div className="font-mono text-[10px] text-muted-foreground">
                                {item.description}
                              </div>
                            )}
                          </TooltipContent>
                        </Tooltip>
                      </li>
                    );
                  }

                  return <li key={item.href}>{linkContent}</li>;
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Backend status footer — 印刷风: hostname / status */}
        {!collapsed && (
          <div className="border-t border-border p-3">
            <div className="flex items-center gap-2 text-[10px] font-mono text-muted-foreground">
              <span className={cn("status-dot status-dot-live", statusColor)} />
              <span className="truncate">
                {baseUrl.replace(/^https?:\/\//, "")}
              </span>
              <span className="ml-auto shrink-0 border border-border px-1.5 py-px text-[9px] uppercase tracking-wider">
                {statusText}
              </span>
            </div>
          </div>
        )}
      </aside>
    </TooltipProvider>
  );
}

export function MobileSidebarToggle({ onOpen }: { onOpen: () => void }) {
  const { t } = useT();
  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={onOpen}
      className="md:hidden"
      aria-label={t("nav.openMenu")}
    >
      <ChevronLeft className="h-5 w-5" />
    </Button>
  );
}
