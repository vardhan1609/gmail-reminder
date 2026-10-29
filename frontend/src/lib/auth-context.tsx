"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { api, User } from "./api";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  refreshUser: async () => {},
  logout: async () => {},
});

const PUBLIC_PATHS = [
  "/",
  "/login",
  "/signup",
  "/verify-email",
  "/forgot-password",
  "/reset-password",
  "/mfa/challenge",
  "/mfa/recovery",
];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refreshUser = async () => {
    try {
      const u = await api.getMe();
      setUser(u);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  // Route protection
  useEffect(() => {
    if (loading) return;

    const isPublic = PUBLIC_PATHS.some(
      (p) => pathname === p || pathname?.startsWith("/verify-email") || pathname?.startsWith("/reset-password")
    );

    if (!user && !isPublic) {
      router.push(`/login?redirect=${encodeURIComponent(pathname || "/dashboard")}`);
    }
  }, [user, loading, pathname, router]);

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Continue even if logout API returns error
    }
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

