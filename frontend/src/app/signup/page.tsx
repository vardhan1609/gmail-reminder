"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Mail, Check, X, AlertCircle } from "lucide-react";
import { api, getApiBase } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [marketingOptIn, setMarketingOptIn] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Password rules validation
  const hasMinLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasNumber = /\d/.test(password);
  const hasSpecial = /[\W_]/.test(password);
  const passwordsMatch = password.length > 0 && password === confirmPassword;
  const isFormValid =
    hasMinLength && hasUppercase && hasLowercase && hasNumber && hasSpecial && passwordsMatch && termsAccepted;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isFormValid) return;

    setError(null);
    setLoading(true);

    try {
      const res = await api.register({
        email,
        password,
        full_name: fullName,
        terms_accepted: termsAccepted,
        marketing_opt_in: marketingOptIn,
      });

      // Redirect to verification view
      router.push(`/verify-email?email=${encodeURIComponent(email)}&token=${res.verification_token || ""}`);
    } catch (err: any) {
      setError(err.detail || "Registration failed. Please check your information.");
    } finally {
      setLoading(false);
    }
  };

  const startGoogleSignup = () => {
    const params = new URLSearchParams({
      intent: "signup",
      terms_accepted: String(termsAccepted),
      marketing_opt_in: String(marketingOptIn),
    });
    window.location.assign(`${getApiBase()}/auth/google-sso/login?${params.toString()}`);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <Card className="w-full max-w-md shadow-md border-border">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto h-12 w-12 rounded-xl bg-blue-600 flex items-center justify-center text-white mb-3 shadow">
            <Mail className="h-6 w-6" />
          </div>
          <CardTitle className="text-2xl font-bold">Create an Account</CardTitle>
          <CardDescription>Get started with automated Gmail alerts</CardDescription>
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
              <label className="text-xs font-semibold text-slate-700">Full Name</label>
              <Input
                type="text"
                placeholder="Jane Doe"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Email Address</label>
              <Input
                type="email"
                placeholder="you@university.edu"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Password</label>
              <Input
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Confirm Password</label>
              <Input
                type="password"
                placeholder="••••••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </div>

            {/* Password requirements indicators */}
            <div className="p-3 bg-muted/40 border border-border rounded-lg space-y-1 text-xs">
              <p className="font-semibold text-foreground mb-1.5">Password requirements:</p>
              <div className="grid grid-cols-2 gap-1">
                <span className={`flex items-center gap-1 ${hasMinLength ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                  {hasMinLength ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />} At least 8 chars
                </span>
                <span className={`flex items-center gap-1 ${hasUppercase ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                  {hasUppercase ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />} Uppercase letter
                </span>
                <span className={`flex items-center gap-1 ${hasLowercase ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                  {hasLowercase ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />} Lowercase letter
                </span>
                <span className={`flex items-center gap-1 ${hasNumber ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                  {hasNumber ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />} Number (0-9)
                </span>
                <span className={`flex items-center gap-1 ${hasSpecial ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                  {hasSpecial ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />} Special character
                </span>
                <span className={`flex items-center gap-1 ${passwordsMatch ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                  {passwordsMatch ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />} Passwords match
                </span>
              </div>
            </div>

            <div className="space-y-3 rounded-lg border border-border p-3 text-sm">
              <label className="flex items-start gap-2 cursor-pointer">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-primary" checked={termsAccepted} onChange={(e) => setTermsAccepted(e.target.checked)} required />
                <span>I agree to the <Link href="/terms" target="_blank" className="font-semibold text-primary underline">Terms of Service</Link> and acknowledge the <Link href="/privacy" target="_blank" className="font-semibold text-primary underline">Privacy Policy</Link>. This is required to create an account.</span>
              </label>
              <label className="flex items-start gap-2 cursor-pointer">
                <input type="checkbox" className="mt-1 h-4 w-4 accent-primary" checked={marketingOptIn} onChange={(e) => setMarketingOptIn(e.target.checked)} />
                <span>Send me occasional product updates, feature announcements and tips by email. Optional; I can unsubscribe at any time.</span>
              </label>
            </div>
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" loading={loading} disabled={!isFormValid}>
              Create Account
            </Button>
            <div className="flex items-center gap-3 w-full text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />OR<span className="h-px flex-1 bg-border" /></div>
            <Button type="button" variant="outline" className="w-full" disabled={!termsAccepted} onClick={startGoogleSignup}>
              <span className="mr-2 font-bold text-base">G</span> Sign up with Google
            </Button>

            <p className="text-center text-xs text-muted-foreground">
              Already have an account?{" "}
              <Link href="/login" className="text-primary font-semibold hover:underline">
                Sign In
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

