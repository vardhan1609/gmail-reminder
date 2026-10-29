"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Inbox,
  Clock,
  Bell,
  Plug,
  Sliders,
  ShieldCheck,
  Smartphone,
  LayoutDashboard,
  LogOut,
  Mail,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";

const NAV_ITEMS = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Emails", href: "/dashboard/emails", icon: Inbox },
  { label: "Reminders", href: "/dashboard/reminders", icon: Clock },
  { label: "Notifications", href: "/dashboard/notifications", icon: Bell },
  { label: "Integrations", href: "/dashboard/integrations", icon: Plug },
  { label: "Notification Rules", href: "/dashboard/settings", icon: Sliders },
  { label: "Security & MFA", href: "/dashboard/security", icon: ShieldCheck },
  { label: "Active Sessions", href: "/dashboard/sessions", icon: Smartphone },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-[#111827] flex flex-col h-screen sticky top-0 transition-colors">
      {/* Brand */}
      <div className="h-16 flex items-center px-6 border-b border-slate-200 dark:border-slate-800 gap-3">
        <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold shadow">
          <Mail className="h-5 w-5" />
        </div>
        <div>
          <h1 className="font-bold text-slate-900 dark:text-slate-100 leading-tight">MailNotifier</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400">Multi-Channel Alerts</p>
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          return (
            <a
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-blue-50 text-blue-600 dark:bg-blue-950/60 dark:text-blue-400 font-semibold"
                  : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-slate-100"
              )}
            >
              <Icon className={cn("h-4 w-4", isActive ? "text-blue-600 dark:text-blue-400" : "text-slate-500 dark:text-slate-400")} />
              {item.label}
            </a>
          );
        })}
      </nav>

      {/* User profile & Logout */}
      <div className="p-4 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-[#0E1524]">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900/60 text-blue-600 dark:text-blue-300 flex items-center justify-center font-bold text-sm">
            {user?.full_name ? user.full_name[0].toUpperCase() : user?.email[0].toUpperCase() || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 truncate">
              {user?.full_name || "User"}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{user?.email}</p>
          </div>
        </div>

        <button
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-800/80 transition-colors"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
