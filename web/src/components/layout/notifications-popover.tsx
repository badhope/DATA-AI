import { reportError } from "@/lib/errors";
("use client");

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";
import { toast } from "@/components/ui/toaster";
import { type Notification, api } from "@/lib/api/client";
import { cn, formatRelativeTime } from "@/lib/utils";
import {
  AlertCircle,
  Bell,
  Check,
  CheckCircle2,
  CircleAlert,
  Info,
  MessageCircle,
  Settings2,
  Wrench,
} from "lucide-react";
import * as React from "react";
import { Link } from "react-router-dom";

function levelIcon(level: Notification["level"]) {
  switch (level) {
    case "success":
      return <CheckCircle2 className="h-4 w-4 text-success" />;
    case "warning":
      return <CircleAlert className="h-4 w-4 text-warning" />;
    case "error":
      return <AlertCircle className="h-4 w-4 text-destructive" />;
    default:
      return <Info className="h-4 w-4 text-primary" />;
  }
}

export function NotificationsPopover() {
  const [items, setItems] = React.useState<Notification[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [open, setOpen] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.listNotifications();
      setItems(res.data);
    } catch (e) {
      reportError(e, "加载通知失败");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (open) load();
  }, [open, load]);

  const unread = items.filter((i) => !i.read).length;

  async function markAll() {
    try {
      await api.markNotificationsRead("all");
      setItems((prev) => prev.map((i) => ({ ...i, read: true })));
    } catch (e) {
      reportError(e, "标记失败");
    }
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="通知">
          <Bell className="h-4 w-4" />
          {unread > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <h4 className="text-sm font-semibold">
            通知{" "}
            {unread > 0 && (
              <Badge variant="accent" className="ml-1">
                {unread}
              </Badge>
            )}
          </h4>
          <Button
            variant="ghost"
            size="xs"
            onClick={markAll}
            className="h-7 px-2 text-xs"
            disabled={unread === 0}
          >
            <Check className="h-3 w-3" /> 全部已读
          </Button>
        </div>
        <div className="max-h-80 overflow-y-auto p-1">
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Spinner className="h-4 w-4" />
            </div>
          ) : items.length === 0 ? (
            <div className="px-2 py-10 text-center text-sm text-muted-foreground">
              <Bell className="mx-auto mb-2 h-6 w-6 opacity-40" />
              暂无通知
            </div>
          ) : (
            items.map((n) => {
              const inner = (
                <div
                  className={cn(
                    "flex items-start gap-3 rounded-md px-3 py-2.5 transition-colors hover:bg-accent",
                    !n.read && "bg-primary/5",
                  )}
                >
                  <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted">
                    {levelIcon(n.level)}
                  </div>
                  <div className="flex-1 overflow-hidden">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-medium">{n.title}</p>
                      {!n.read && (
                        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                      )}
                    </div>
                    {n.description && (
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {n.description}
                      </p>
                    )}
                    <p className="mt-1 text-[10px] text-muted-foreground">
                      {formatRelativeTime(n.ts)}
                    </p>
                  </div>
                </div>
              );
              return n.link ? (
                <Link key={n.id} to={n.link} className="block">
                  {inner}
                </Link>
              ) : (
                <div key={n.id}>{inner}</div>
              );
            })
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
