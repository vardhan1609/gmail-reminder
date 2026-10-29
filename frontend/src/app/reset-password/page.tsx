"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Lock, AlertCircle, ArrowRight, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tokenParam = searchParams.get("token") || "";

  const [token, setToken] = useState(tokenParam);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await api.resetPassword({ token, new_password: newPassword });
      setSuccess(true);
    } catch (err: any) {
      setError(err.detail || "Password reset failed. Token may be expired.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="w-full max-w-md shadow-md border-slate-200">
      <CardHeader className="text-center pb-4">
        <div className="mx-auto h-12 w-12 rounded-xl bg-blue-600 flex items-center justify-center text-white mb-3 shadow">
          <Lock className="h-6 w-6" />
        </div>
        <CardTitle className="text-2xl font-bold">Set New Password</CardTitle>
        <CardDescription>Enter your new password below</CardDescription>
      </CardHeader>

      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success ? (
            <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm text-center">
              <CheckCircle2 className="h-6 w-6 mx-auto mb-2 text-emerald-600" />
              Password reset successful. All previous sessions have been invalidated.
            </div>
          ) : (
            <>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Reset Token</label>
                <Input
                  type="text"
                  placeholder="Reset token"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  required
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">New Password</label>
                <Input
                  type="password"
                  placeholder="••••••••••••"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Confirm New Password</label>
                <Input
                  type="password"
                  placeholder="••••••••••••"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={8}
                />
              </div>
            </>
          )}
        </CardContent>

        <CardFooter className="flex flex-col gap-3">
          {success ? (
            <Link href="/login" className="w-full">
              <Button className="w-full gap-2">
                Sign In with New Password <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
          ) : (
            <Button type="submit" className="w-full" loading={loading}>
              Update Password
            </Button>
          )}

          <p className="text-center text-xs text-slate-500">
            Return to{" "}
            <Link href="/login" className="text-blue-600 font-semibold hover:underline">
              Sign In
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <Suspense fallback={<div className="text-muted-foreground text-sm">Loading password reset...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
