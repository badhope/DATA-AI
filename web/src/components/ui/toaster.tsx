"use client";

import { CircleAlert, CircleCheck, CircleX, Info, Loader2 } from "lucide-react";
import { Toaster as SonnerToaster, toast as sonnerToast } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="top-right"
      richColors
      closeButton
      icons={{
        success: <CircleCheck className="h-4 w-4" />,
        error: <CircleX className="h-4 w-4" />,
        warning: <CircleAlert className="h-4 w-4" />,
        info: <Info className="h-4 w-4" />,
        loading: <Loader2 className="h-4 w-4 animate-spin" />,
      }}
      toastOptions={{
        style: {
          background: "var(--color-popover)",
          color: "var(--color-popover-foreground)",
          border: "1px solid var(--color-border)",
        },
      }}
    />
  );
}

export const toast = {
  success: (msg: string, opts?: Parameters<typeof sonnerToast.success>[1]) =>
    sonnerToast.success(msg, opts),
  error: (msg: string, opts?: Parameters<typeof sonnerToast.error>[1]) =>
    sonnerToast.error(msg, opts),
  info: (msg: string, opts?: Parameters<typeof sonnerToast.info>[1]) => sonnerToast.info(msg, opts),
  warning: (msg: string, opts?: Parameters<typeof sonnerToast.warning>[1]) =>
    sonnerToast.warning(msg, opts),
  loading: (msg: string, opts?: Parameters<typeof sonnerToast.loading>[1]) =>
    sonnerToast.loading(msg, opts),
  dismiss: (id?: string | number) => sonnerToast.dismiss(id),
};
