"use client";

import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export type Theme = "light" | "dark" | "system";
export type EffectiveTheme = "light" | "dark";

interface ThemeContextType {
  theme: Theme;
  effectiveTheme: EffectiveTheme;
  setTheme: (theme: Theme) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

const THEME_STORAGE_KEY = "theme_preference";

function getSystemTheme(): EffectiveTheme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyThemeClass(effective: EffectiveTheme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (effective === "dark") {
    root.classList.add("dark");
  } else {
    root.classList.remove("dark");
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [theme, setThemeState] = useState<Theme>("system");
  const [effectiveTheme, setEffectiveTheme] = useState<EffectiveTheme>("light");
  const [mounted, setMounted] = useState(false);
  const syncTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize theme from localStorage or system on mount
  useEffect(() => {
    setMounted(true);
    try {
      const stored = localStorage.getItem(THEME_STORAGE_KEY) as Theme | null;
      const initialTheme: Theme = stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
      setThemeState(initialTheme);

      const effective: EffectiveTheme = initialTheme === "system" ? getSystemTheme() : initialTheme;
      setEffectiveTheme(effective);
      applyThemeClass(effective);
    } catch {
      // LocalStorage access may fail in restricted iframes/private browsing
      const effective = getSystemTheme();
      setEffectiveTheme(effective);
      applyThemeClass(effective);
    }
  }, []);

  // Sync account theme preference once authenticated user loads
  useEffect(() => {
    if (!user) return;
    let isMounted = true;

    // Fetch user preferences to check if cloud setting differs
    api.getPreferences()
      .then((prefs) => {
        if (!isMounted || !prefs.theme_preference) return;
        const cloudTheme = prefs.theme_preference as Theme;
        if (cloudTheme === "light" || cloudTheme === "dark" || cloudTheme === "system") {
          // If stored preference matches or user hasn't modified local, align with cloud
          setThemeState((current) => {
            const stored = typeof window !== "undefined" ? localStorage.getItem(THEME_STORAGE_KEY) : null;
            if (!stored || stored === cloudTheme) {
              const effective: EffectiveTheme = cloudTheme === "system" ? getSystemTheme() : cloudTheme;
              setEffectiveTheme(effective);
              applyThemeClass(effective);
              try {
                localStorage.setItem(THEME_STORAGE_KEY, cloudTheme);
              } catch {}
              return cloudTheme;
            }
            return current;
          });
        }
      })
      .catch(() => {
        // Ignore network failure gracefully
      });

    return () => {
      isMounted = false;
    };
  }, [user]);

  // System theme listener for when theme is 'system'
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");

    const handleChange = () => {
      if (theme === "system") {
        const newEffective = mediaQuery.matches ? "dark" : "light";
        setEffectiveTheme(newEffective);
        applyThemeClass(newEffective);
      }
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handleChange);
    } else {
      mediaQuery.addListener(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener("change", handleChange);
      } else {
        mediaQuery.removeListener(handleChange);
      }
    };
  }, [theme]);

  // Function to switch theme
  const setTheme = useCallback(
    (newTheme: Theme) => {
      setThemeState(newTheme);
      const effective: EffectiveTheme = newTheme === "system" ? getSystemTheme() : newTheme;
      setEffectiveTheme(effective);
      applyThemeClass(effective);

      try {
        localStorage.setItem(THEME_STORAGE_KEY, newTheme);
      } catch {}

      // Persist to backend if user is authenticated
      if (user) {
        if (syncTimeoutRef.current) {
          clearTimeout(syncTimeoutRef.current);
        }
        syncTimeoutRef.current = setTimeout(() => {
          api.updatePreferences({ theme_preference: newTheme }).catch((err) => {
            console.warn("Failed to persist theme preference to backend:", err);
          });
        }, 300);
      }
    },
    [user]
  );

  return (
    <ThemeContext.Provider value={{ theme, effectiveTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}

