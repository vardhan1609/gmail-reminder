"use client";
import { Sidebar } from "@/components/layout/sidebar";
import { RealtimeProvider } from "@/components/providers/realtime-provider";
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <RealtimeProvider><div className="flex min-h-screen flex-col bg-background text-foreground md:flex-row"><Sidebar /><div className="flex min-w-0 flex-1 flex-col overflow-x-hidden">{children}</div></div></RealtimeProvider>;
}
