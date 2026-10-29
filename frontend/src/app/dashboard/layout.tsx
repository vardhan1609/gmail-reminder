"use client";

import { Sidebar } from "@/components/layout/sidebar";
import { RealtimeProvider } from "@/components/providers/realtime-provider";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RealtimeProvider>
      <div className="flex min-h-screen bg-background text-foreground">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">{children}</div>
      </div>
    </RealtimeProvider>
  );
}

