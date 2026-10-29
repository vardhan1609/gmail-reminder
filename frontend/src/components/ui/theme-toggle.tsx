"use client";

import React from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme, Theme } from "@/components/providers/theme-provider";
import { cn } from "@/lib/utils";

interface ThemeToggleProps {
  className?: string;
  variant?: "segmented" | "compact";
  showLabel?: boolean;
}

export function ThemeToggle({
  className,
  variant = "segmented",
  showLabel = false,
}: ThemeToggleProps) {
  const { theme, effectiveTheme, setTheme } = useTheme();

  const options: { value: Theme; label: string; icon: React.ReactNode }[] = [
    {
      value: "light",
      label: "Light",
      icon: <Sun className="h-4 w-4" aria-hidden="true" />,
    },
    {
      value: "dark",
      label: "Dark",
      icon: <Moon className="h-4 w-4" aria-hidden="true" />,
    },
    {
      value: "system",
      label: "System",
      icon: <Monitor className="h-4 w-4" aria-hidden="true" />,
    },
  ];

  if (variant === "compact") {
    // Compact button cycling through light -> dark -> system
    const nextTheme: Theme =
      theme === "light" ? "dark" : theme === "dark" ? "system" : "light";

    const currentIcon =
      theme === "system" ? (
        <Monitor className="h-4 w-4" />
      ) : effectiveTheme === "dark" ? (
        <Moon className="h-4 w-4" />
      ) : (
        <Sun className="h-4 w-4" />
      );

    return (
      <button
        type="button"
        onClick={() => setTheme(nextTheme)}
        className={cn(
          "inline-flex items-center justify-center rounded-lg p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-100 dark:hover:bg-slate-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 select-none border border-transparent dark:border-slate-800/60",
          className
        )}
        aria-label={`Current theme: ${theme} (${effectiveTheme} active). Click to switch to ${nextTheme}.`}
        title={`Theme: ${theme.charAt(0).toUpperCase() + theme.slice(1)} (Click to switch)`}
      >
        {currentIcon}
        <span className="sr-only">Toggle theme</span>
      </button>
    );
  }

  return (
    <div
      role="radiogroup"
      aria-label="Theme selection"
      className={cn(
        "inline-flex items-center p-1 rounded-xl bg-slate-100 dark:bg-slate-900/90 border border-slate-200 dark:border-slate-800 shadow-inner select-none",
        className
      )}
    >
      {options.map((opt) => {
        const isSelected = theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => setTheme(opt.value)}
            className={cn(
              "flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1",
              isSelected
                ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-50 shadow-sm border border-slate-200/50 dark:border-slate-700/60 font-semibold"
                : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800/40"
            )}
            title={`${opt.label} theme`}
          >
            {opt.icon}
            {(showLabel || isSelected) && <span>{opt.label}</span>}
          </button>
        );
      })}
    </div>
  );
}

