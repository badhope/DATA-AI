"use client";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSettings } from "@/lib/stores/settings";
import { Bell, ChevronRight, Cog, KeyRound, LogOut, User } from "lucide-react";
import * as React from "react";
import { useNavigate } from "react-router-dom";

export function UserMenu() {
  const navigate = useNavigate();
  const apiKey = useSettings((s) => s.apiKey);
  const baseUrl = useSettings((s) => s.baseUrl);
  const setSettings = useSettings((s) => s.set);

  const isDevMode = !apiKey || apiKey === "dev-mode";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="rounded-full" aria-label="用户菜单">
          <Avatar className="h-8 w-8">
            <AvatarFallback>{isDevMode ? "DEV" : "U"}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-semibold">{isDevMode ? "开发者模式" : "API 用户"}</p>
            <p className="truncate text-xs text-muted-foreground">
              {isDevMode ? baseUrl : `${apiKey.slice(0, 8)}...`}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => navigate("/settings")}>
          <User className="h-4 w-4" /> 个人资料
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate("/settings?tab=connection")}>
          <KeyRound className="h-4 w-4" /> API Key
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => navigate("/settings?tab=appearance")}>
          <Cog className="h-4 w-4" /> 设置
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={() => {
            setSettings({ apiKey: "dev-mode" });
          }}
        >
          <LogOut className="h-4 w-4" /> 切换到 dev-mode
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
