import Link from "next/link";
import { Mail, Shield, Bell, Clock, CheckCircle2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col justify-between transition-colors">
      {/* Header */}
      <header className="border-b border-border bg-background/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow">
              <Mail className="h-5 w-5" />
            </div>
            <span className="font-bold text-lg text-foreground tracking-tight">MailNotifier</span>
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle variant="compact" />
            <Link href="/login">
              <Button variant="ghost" size="sm">Sign In</Button>
            </Link>
            <Link href="/signup">
              <Button size="sm">Get Started</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1 max-w-5xl mx-auto px-6 py-20 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-semibold mb-6 border border-primary/20">
          <span>Enterprise Multi-Tenant Gmail Monitoring</span>
        </div>

        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-foreground tracking-tight mb-6">
          Never miss critical emails. <br />
          Instant alerts on{" "}
          <span className="text-primary underline decoration-primary/40 decoration-wavy underline-offset-8">
            WhatsApp & Telegram
          </span>
        </h1>

        <p className="text-lg text-muted-foreground max-w-2xl mx-auto mb-10 leading-relaxed">
          Connect your Google Workspace or personal Gmail. Real-time categorization across academics, bills, security, and assignments with intelligent deadline reminders.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
          <Link href="/signup">
            <Button size="lg" className="gap-2 w-full sm:w-auto shadow-md">
              Create Free Account <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="outline" size="lg" className="w-full sm:w-auto">
              Sign In to Mailbox
            </Button>
          </Link>
        </div>

        {/* Feature Grid */}
        <div className="grid sm:grid-cols-3 gap-6 text-left">
          <div className="bg-card p-6 rounded-xl border border-border shadow-sm">
            <div className="h-10 w-10 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center mb-4">
              <Bell className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-foreground mb-2">Dual Channel Delivery</h3>
            <p className="text-sm text-muted-foreground">
              Deliver notifications independently to WhatsApp and Telegram with failover and retry handling.
            </p>
          </div>

          <div className="bg-card p-6 rounded-xl border border-border shadow-sm">
            <div className="h-10 w-10 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-4">
              <Clock className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-foreground mb-2">Deadline Extraction</h3>
            <p className="text-sm text-muted-foreground">
              Extract explicit deadlines and schedule automated reminders at 24h, 6h, and 1h intervals.
            </p>
          </div>

          <div className="bg-card p-6 rounded-xl border border-border shadow-sm">
            <div className="h-10 w-10 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mb-4">
              <Shield className="h-5 w-5" />
            </div>
            <h3 className="font-bold text-foreground mb-2">Enterprise Security</h3>
            <p className="text-sm text-muted-foreground">
              Argon2id password hashing, RFC 6238 TOTP two-factor authentication, and user data isolation.
            </p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border bg-card py-6">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between text-xs text-muted-foreground gap-2">
          <p>© {new Date().getFullYear()} MailNotifier. Secure Multi-User Email Automation.</p>
          <div className="flex gap-4">
            <span>Privacy Mode Supported</span>
            <span>•</span>
            <span>Gmail History API</span>
            <span>•</span>
            <span>TOTP 2FA</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
