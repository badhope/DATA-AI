import { cn } from "@/lib/utils";
import { type VariantProps, cva } from "class-variance-authority";
import type * as React from "react";

/**
 * Badge — 印刷感的方块标签:
 * - 锐角 1px border, mono 字体
 * - 默认: 黑底白字; outline: 仅边框
 */
const badgeVariants = cva(
  "inline-flex items-center border px-1.5 py-px font-mono text-[10px] font-medium uppercase tracking-wider transition-colors",
  {
    variants: {
      variant: {
        default: "border-foreground bg-foreground text-background",
        secondary: "border-border bg-secondary text-secondary-foreground",
        outline: "border-border bg-transparent text-foreground",
        ghost: "border-transparent bg-transparent text-muted-foreground",
        success: "border-success/60 bg-success/10 text-success",
        warning: "border-warning/60 bg-warning/10 text-warning",
        error: "border-destructive/60 bg-destructive/10 text-destructive",
        info: "border-info/60 bg-info/10 text-info",
        accent: "border-primary bg-primary/10 text-primary",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
