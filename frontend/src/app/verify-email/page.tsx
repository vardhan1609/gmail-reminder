"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2, AlertCircle, Mail, ArrowRight } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

function VerifyEmailForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const emailParam = searchParams.get("email");
  const tokenParam = searchParams.get("token");

  const [token, setToken] = useState(tokenParam || "");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async (tokenToUse?: string) => {
    const activeToken = tokenToUse || token;
    if (!activeToken) return;

    setLoading(true);
    setError(null);

    try {
      await api.verifyEmail(activeToken);
      setSuccess(true);
    } catch (err: any) {
      setError(err.detail || "Invalid or expired verification token.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (tokenParam) {
      handleVerify(tokenParam);
    }
  }, [tokenParam]);

  return (
    <Card className="w-full max-w-md shadow-md border-slate-200">
      <CardHeader className="text-center pb-4">
        <div
          className={`mx-auto h-12 w-12 rounded-xl flex items-center justify-center text-white mb-3 shadow ${
            success ? "bg-emerald-600" : "bg-blue-600"
          }`}
        >
          {success ? <CheckCircle2 className="h-6 w-6" /> : <Mail className="h-6 w-6" />}
        </div>
        <CardTitle className="text-2xl font-bold">
          {success ? "Email Verified!" : "Verify Your Email"}
        </CardTitle>
        <CardDescription>
          {success
            ? "Your account has been successfully verified."
            : emailParam
            ? `A verification token has been generated for ${emailParam}.`
            : "Enter your verification token to complete registration."}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success ? (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800 text-sm text-center">
            You can now sign in to your dashboard and connect your Gmail account.
          </div>
        ) : (
          <div className="space-y-2">
            <label className="text-xs font-semibold text-slate-700">Verification Token</label>
            <Input
              type="text"
              placeholder="Paste verification token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </div>
        )}
      </CardContent>

      <CardFooter className="flex flex-col gap-3">
        {success ? (
          <Link href="/login" className="w-full">
            <Button className="w-full gap-2">
              Continue to Sign In <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
        ) : (
          <Button
            onClick={() => handleVerify()}
            className="w-full"
            loading={loading}
            disabled={!token.trim()}
          >
            Verify Email Address
          </Button>
        )}

        <p className="text-center text-xs text-slate-500">
          Return to{" "}
          <Link href="/login" className="text-blue-600 font-semibold hover:underline">
            Sign In
          </Link>
        </p>
      </CardFooter>
    </Card>
  );
}

export default function VerifyEmailPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-slate-50">
      <Suspense fallback={<div className="text-slate-500 text-sm">Loading verification...</div>}>
        <VerifyEmailForm />
      </Suspense>
    </div>
  );
}
