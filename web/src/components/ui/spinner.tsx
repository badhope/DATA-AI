"use client";

import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

interface SpinnerProps {
  className?: string;
  size?: number;
  label?: string;
}

export function Spinner({ className, size = 16, label }: SpinnerProps) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <Loader2 className="animate-spin" style={{ width: size, height: size }} />
      {label && <span className="text-sm text-muted-foreground">{label}</span>}
    </span>
  );
}

export function PageSpinner({ label = "加载中..." }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[300px] w-full items-center justify-center">
      <Spinner size={24} label={label} />
    </div>
  );
}
