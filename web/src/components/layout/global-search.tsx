"use client";

import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import { getNavGroups } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { Search } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router-dom";

export function GlobalSearch() {
  const [open, setOpen] = React.useState(false);
  const [q, setQ] = React.useState("");
  const navigate = useNavigate();
  const { t, locale } = useT();
  const navGroups = React.useMemo(() => getNavGroups(locale), [locale]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const items = React.useMemo(() => {
    const all = navGroups.flatMap((g) => g.items.map((i) => ({ ...i, group: g.title })));
    if (!q) return all;
    const lower = q.toLowerCase();
    return all.filter(
      (i) =>
        i.label.toLowerCase().includes(lower) ||
        (i.description?.toLowerCase().includes(lower) ?? false) ||
        i.group.toLowerCase().includes(lower),
    );
  }, [q, navGroups]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="hidden h-9 w-56 items-center gap-2 rounded-md border border-input bg-muted/30 px-3 text-sm text-muted-foreground transition-colors hover:bg-muted md:flex"
        aria-label={t("search.title")}
      >
        <Search className="h-3.5 w-3.5" />
        <span>{t("search.placeholder")}</span>
        <kbd className="ml-auto rounded bg-background px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl p-0">
          <DialogTitle className="sr-only">{t("search.title")}</DialogTitle>
          <DialogDescription className="sr-only">{t("search.description")}</DialogDescription>
          <div className="flex items-center gap-2 border-b border-border px-4">
            <Search className="h-4 w-4 text-muted-foreground" />
            <Input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder={t("search.placeholder")}
              className="border-0 shadow-none focus-visible:ring-0"
            />
          </div>
          <div className="max-h-80 overflow-y-auto p-2">
            {items.length === 0 ? (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">
                {t("search.noResults")}
              </p>
            ) : (
              <ul>
                {items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <button
                        onClick={() => {
                          navigate(item.href);
                          setOpen(false);
                          setQ("");
                        }}
                        className={cn(
                          "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm hover:bg-accent",
                        )}
                      >
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <div className="flex-1">
                          <div className="font-medium">{item.label}</div>
                          <div className="text-xs text-muted-foreground">{item.group}</div>
                        </div>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
