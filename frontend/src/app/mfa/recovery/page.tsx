"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { KeySquare, AlertCircle, ArrowLeft } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

export default function MFARecoveryPage() {
  const router = useRouter();
  const { refreshUser } = useAuth();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await api.recoveryMFA(code);
      await refreshUser();
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.detail || "Invalid or already used recovery code.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <Card className="w-full max-w-md shadow-md border-border">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto h-12 w-12 rounded-xl bg-blue-600 flex items-center justify-center text-white mb-3 shadow">
            <KeySquare className="h-6 w-6" />
          </div>
          <CardTitle className="text-2xl font-bold">Use Recovery Code</CardTitle>
          <CardDescription>Enter one of your 10 backup codes to sign in</CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Recovery Code</label>
              <Input
                type="text"
                placeholder="xxxx-xxxx"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                className="font-mono text-center tracking-wider text-lg"
                autoFocus
              />
              <p className="text-xs text-slate-500 mt-1">Each recovery code can only be used once.</p>
            </div>
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" loading={loading} disabled={!code.trim()}>
              Verify Recovery Code
            </Button>

            <Link
              href="/mfa/challenge"
              className="flex items-center justify-center gap-1.5 text-xs text-slate-600 hover:text-slate-900"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Back to Authenticator Code
            </Link>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

