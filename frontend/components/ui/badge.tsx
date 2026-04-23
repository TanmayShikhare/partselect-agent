import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "success" | "destructive" | "secondary";

const styles: Record<Variant, string> = {
  success: "bg-emerald-100 text-emerald-800 border-emerald-200",
  destructive: "bg-red-100 text-red-800 border-red-200",
  secondary: "bg-zinc-100 text-zinc-800 border-zinc-200",
};

export function Badge({
  className,
  variant = "secondary",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        styles[variant],
        className
      )}
      {...props}
    />
  );
}

