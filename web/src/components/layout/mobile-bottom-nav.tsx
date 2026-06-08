"use client";

import { useT } from "@/lib/i18n";
import { getMobileNav } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { Link, useLocation } from "react-router-dom";

export function MobileBottomNav() {
  const location = useLocation();
  const { t, locale } = useT();
  const items = getMobileNav(locale);
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-border bg-background safe-bottom md:hidden">
      {items.map((item) => {
        const Icon = item.icon;
        const active =
          location.pathname === item.href || location.pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            to={item.href}
            className={cn(
              "flex min-h-[56px] flex-col items-center justify-center gap-0.5 py-1.5 text-[10px] font-medium transition-colors",
              active ? "text-primary" : "text-muted-foreground",
            )}
          >
            <Icon className="h-5 w-5" />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
