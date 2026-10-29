import * as React from "react";
import { cn } from "@/lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "success" | "warning";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants = {
    default: "border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/90",
    secondary: "border-transparent bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700",
    destructive: "border-transparent bg-red-100 text-red-800 dark:bg-red-950/70 dark:text-red-300 dark:border dark:border-red-800/50 hover:bg-red-200",
    outline: "text-foreground border border-border",
    success: "border-transparent bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 dark:border dark:border-emerald-800/50",
    warning: "border-transparent bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300 dark:border dark:border-amber-800/50",
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        variants[variant],
        className
      )}
      {...props}
    />
  );
}

export { Badge };
