"use client";

import { useState } from "react";
import Link from "next/link";
import { KeyRound, AlertCircle, ArrowLeft, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setMessage(null);

    try {
      const res = await api.forgotPassword(email);
      setMessage(res.message);
      if (res.reset_token) {
        setResetToken(res.reset_token);
      }
    } catch (err: any) {
      setError(err.detail || "Request failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <Card className="w-full max-w-md shadow-md border-border">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto h-12 w-12 rounded-xl bg-blue-600 flex items-center justify-center text-white mb-3 shadow">
            <KeyRound className="h-6 w-6" />
          </div>
          <CardTitle className="text-2xl font-bold">Password Recovery</CardTitle>
          <CardDescription>Enter your account email to receive reset instructions</CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {message && (
              <div className="p-3 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-lg space-y-2">
                <div className="flex items-center gap-2 font-medium">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{message}</span>
                </div>
                {resetToken && (
                  <div className="pt-2 border-t border-emerald-200 dark:border-emerald-900/60">
                    <p className="text-xs text-muted-foreground mb-1">Your Reset Token:</p>
                    <code className="block p-1.5 bg-background text-foreground text-xs font-mono rounded border border-border select-all">
                      {resetToken}
                    </code>
                    <Link
                      href={`/reset-password?token=${encodeURIComponent(resetToken)}`}
                      className="mt-2 inline-block text-xs font-semibold text-primary hover:underline"
                    >
                      Click here to reset password now →
                    </Link>
                  </div>
                )}
              </div>
            )}

            <div className="space-y-1">
              <label className="text-xs font-semibold text-foreground">Account Email</label>
              <Input
                type="email"
                placeholder="you@university.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" loading={loading}>
              Send Reset Instructions
            </Button>

            <Link
              href="/login"
              className="flex items-center justify-center gap-1.5 text-xs text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back to Sign In
            </Link>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

