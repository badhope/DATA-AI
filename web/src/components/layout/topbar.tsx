"use client";

import { GlobalSearch } from "@/components/layout/global-search";
import { NotificationsPopover } from "@/components/layout/notifications-popover";
import { UserMenu } from "@/components/layout/user-menu";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { SUPPORTED_LOCALES, useT } from "@/lib/i18n";
import { getNavGroups } from "@/lib/nav";
import { useChat } from "@/lib/stores/chat";
import { useSettings } from "@/lib/stores/settings";
import { Globe, Languages, Menu, MonitorSmartphone, Moon, Sun } from "lucide-react";
import * as React from "react";
import { useLocation } from "react-router-dom";

interface TopbarProps {
  onMobileMenuOpen: () => void;
}

function findCurrentTitle(
  pathname: string,
  groups: ReturnType<typeof getNavGroups>,
  fallbacks: { office: string; default: string },
) {
  for (const group of groups) {
    for (const item of group.items) {
      if (item.href === pathname) return { title: item.label, parent: group.title };
      if (pathname.startsWith(`${item.href}/`)) return { title: item.label, parent: group.title };
    }
  }
  if (pathname.startsWith("/office")) return { title: fallbacks.office, parent: "" };
  return { title: fallbacks.default, parent: "" };
}

const THEME_LABEL: Record<string, { en: string; zh: string }> = {
  dark: { en: "Dark", zh: "深色" },
  light: { en: "Light", zh: "浅色" },
  system: { en: "System", zh: "跟随系统" },
};

export function Topbar({ onMobileMenuOpen }: TopbarProps) {
  const location = useLocation();
  const theme = useSettings((s) => s.theme);
  const setSettings = useSettings((s) => s.set);
  const sessionCount = useChat((s) => Object.keys(s.sessions).length);
  const { t, locale, setLocale } = useT();
  const navGroups = React.useMemo(() => getNavGroups(locale), [locale]);
  const { title, parent } = findCurrentTitle(location.pathname, navGroups, {
    office: t("nav.office"),
    default: "DATA-AI",
  });

  const cycleTheme = () => {
    const order = ["dark", "light", "system"] as const;
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setSettings({ theme: next });
  };

  const ThemeIcon = theme === "dark" ? Moon : theme === "light" ? Sun : MonitorSmartphone;
  const themeLabel = THEME_LABEL[theme]?.[locale] ?? theme;

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-2 border-b border-border bg-background px-3 sm:gap-3 sm:px-6">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        onClick={onMobileMenuOpen}
        aria-label={t("nav.openMenu")}
      >
        <Menu className="h-5 w-5" />
      </Button>

      <div className="hidden items-baseline gap-2 sm:flex">
        {parent && (
          <>
            <span className="eyebrow text-muted-foreground/60">{parent}</span>
            <span className="text-muted-foreground/40">/</span>
          </>
        )}
        <h1 className="font-display text-[15px] font-semibold tracking-tight">
          {title}
        </h1>
      </div>

      <div className="flex-1" />

      <GlobalSearch />

      <div className="hidden items-center gap-1.5 md:flex">
        <span className="eyebrow">SESSIONS</span>
        <span className="num text-[13px] font-medium">{sessionCount}</span>
      </div>

      <NotificationsPopover />

      {/* Language switcher */}
      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={t("common.language")}>
                <Languages className="h-4 w-4" strokeWidth={1.75} />
              </Button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent>{t("common.language")}</TooltipContent>
        </Tooltip>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>{t("common.language")}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          {SUPPORTED_LOCALES.map((l) => (
            <DropdownMenuItem
              key={l}
              onSelect={() => setLocale(l)}
              className={l === locale ? "bg-accent" : ""}
            >
              <Globe className="h-4 w-4" strokeWidth={1.75} />
              {l === "en" ? "English" : "简体中文"}
              {l === locale && <span className="ml-auto text-xs text-primary">✓</span>}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <Tooltip>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={t("common.theme")}>
                <ThemeIcon className="h-4 w-4" strokeWidth={1.75} />
              </Button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <TooltipContent>
            {t("common.theme")}: {themeLabel}
          </TooltipContent>
        </Tooltip>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setSettings({ theme: "dark" })}>
            <Moon className="h-4 w-4" strokeWidth={1.75} /> {THEME_LABEL.dark[locale]}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setSettings({ theme: "light" })}>
            <Sun className="h-4 w-4" strokeWidth={1.75} /> {THEME_LABEL.light[locale]}
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setSettings({ theme: "system" })}>
            <MonitorSmartphone className="h-4 w-4" strokeWidth={1.75} /> {THEME_LABEL.system[locale]}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <UserMenu />
    </header>
  );
}
