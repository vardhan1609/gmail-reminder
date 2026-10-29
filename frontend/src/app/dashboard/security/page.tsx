"use client";

import { useState } from "react";
import {
  ShieldCheck,
  ShieldAlert,
  KeyRound,
  CheckCircle2,
  AlertCircle,
  Copy,
  Download,
} from "lucide-react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, ConfirmDialog } from "@/components/ui/dialog";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";

export default function SecurityPage() {
  const { user, refreshUser } = useAuth();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // MFA Enrollment Flow
  const [enrollModalOpen, setEnrollModalOpen] = useState(false);
  const [enrollData, setEnrollData] = useState<{
    secret: string;
    provisioning_uri: string;
    qr_code: string;
  } | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [confirmLoading, setConfirmLoading] = useState(false);

  // Recovery Codes Display Modal
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [recoveryModalOpen, setRecoveryModalOpen] = useState(false);

  // Disable MFA Flow
  const [disableModalOpen, setDisableModalOpen] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableLoading, setDisableLoading] = useState(false);

  const handleStartEnrollment = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.enrollMFA();
      setEnrollData(data);
      setEnrollModalOpen(true);
    } catch (err: any) {
      setError(err.detail || "Failed to initiate MFA enrollment.");
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmEnrollment = async (e: React.FormEvent) => {
    e.preventDefault();
    setConfirmLoading(true);
    setError(null);
    try {
      const res = await api.confirmMFA(totpCode);
      setEnrollModalOpen(false);
      setTotpCode("");
      setRecoveryCodes(res.recovery_codes || []);
      setRecoveryModalOpen(true);
      await refreshUser();
      setSuccessMsg("Two-Factor Authentication has been successfully activated.");
    } catch (err: any) {
      setError(err.detail || "Invalid verification code.");
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleDisableMFA = async (e: React.FormEvent) => {
    e.preventDefault();
    setDisableLoading(true);
    setError(null);
    try {
      await api.disableMFA(disablePassword);
      setDisableModalOpen(false);
      setDisablePassword("");
      await refreshUser();
      setSuccessMsg("Two-Factor Authentication has been disabled.");
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setError(err.detail || "Failed to disable MFA. Please verify your password.");
    } finally {
      setDisableLoading(false);
    }
  };

  const handleCopyRecoveryCodes = () => {
    navigator.clipboard.writeText(recoveryCodes.join("\n"));
    setSuccessMsg("Recovery codes copied to clipboard.");
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  return (
    <div className="flex-1 flex flex-col">
      <Header
        title="Security & Two-Factor Authentication"
        description="Protect your account with RFC 6238 TOTP authentication and managed recovery keys."
      />

      <main className="flex-1 p-8 space-y-6 max-w-4xl mx-auto w-full">
        {error && (
          <div className="flex items-center gap-2 p-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="flex items-center gap-2 p-4 text-sm text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-xl">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* 2FA Card */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Multi-Factor Authentication (MFA)</CardTitle>
                <CardDescription>
                  Require a 6-digit one-time code from an authenticator app (e.g. Google Authenticator, 1Password, Authy) on login.
                </CardDescription>
              </div>
              <Badge variant={user?.mfa_enabled ? "success" : "secondary"} className="text-xs">
                {user?.mfa_enabled ? "Active" : "Disabled"}
              </Badge>
            </div>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="p-4 bg-muted/40 border border-border rounded-xl flex items-start gap-4">
              <div
                className={`h-10 w-10 rounded-lg flex items-center justify-center shrink-0 ${
                  user?.mfa_enabled
                    ? "bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {user?.mfa_enabled ? (
                  <ShieldCheck className="h-5 w-5" />
                ) : (
                  <ShieldAlert className="h-5 w-5" />
                )}
              </div>
              <div>
                <p className="font-semibold text-sm text-slate-900">
                  {user?.mfa_enabled
                    ? "Your account is secured with 2FA"
                    : "Two-factor authentication is currently inactive"}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {user?.mfa_enabled
                    ? "You will be prompted for your authenticator code whenever you sign in from a new session."
                    : "Adding two-factor authentication provides an extra layer of defense against unauthorized access."}
                </p>
              </div>
            </div>

            <div className="pt-2 flex justify-end gap-3">
              {user?.mfa_enabled ? (
                <Button
                  variant="outline"
                  onClick={() => setDisableModalOpen(true)}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200 text-xs"
                >
                  Disable 2FA
                </Button>
              ) : (
                <Button onClick={handleStartEnrollment} loading={loading} className="gap-2 text-xs">
                  <ShieldCheck className="h-4 w-4" /> Enable Two-Factor Authentication
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </main>

      {/* MFA Enrollment Modal */}
      <Dialog
        open={enrollModalOpen}
        onOpenChange={setEnrollModalOpen}
        title="Set Up Two-Factor Authentication"
        description="Scan the QR code with your authenticator app."
      >
        {enrollData && (
          <form onSubmit={handleConfirmEnrollment} className="space-y-4">
            <div className="flex flex-col items-center justify-center p-4 bg-muted/40 border border-border rounded-lg">
              {/* QR Code image */}
              <img
                src={enrollData.qr_code}
                alt="MFA QR Code"
                className="h-44 w-44 rounded border border-border bg-white p-2 shadow-sm"
              />
              <div className="mt-3 text-center">
                <p className="text-xs text-muted-foreground">Cannot scan? Enter code manually:</p>
                <code className="text-xs font-mono font-bold bg-background text-foreground px-2 py-1 rounded border border-border mt-1 inline-block select-all">
                  {enrollData.secret}
                </code>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-slate-700">Verification Code</label>
              <Input
                placeholder="123456"
                maxLength={6}
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ""))}
                className="text-center text-lg font-mono tracking-widest"
                required
                autoFocus
              />
              <p className="text-[11px] text-slate-500">
                Enter the 6-digit code shown in your authenticator app to confirm setup.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEnrollModalOpen(false)}
                disabled={confirmLoading}
              >
                Cancel
              </Button>
              <Button type="submit" loading={confirmLoading} disabled={totpCode.length < 6}>
                Verify & Enable
              </Button>
            </div>
          </form>
        )}
      </Dialog>

      {/* Recovery Codes Modal */}
      <Dialog
        open={recoveryModalOpen}
        onOpenChange={setRecoveryModalOpen}
        title="Backup Recovery Codes"
        description="Save these codes in a secure password manager. This is the only time they are displayed."
      >
        <div className="space-y-4">
          <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/50 rounded-lg text-amber-800 dark:text-amber-200 text-xs">
            ⚠️ If you lose your authenticator device, each of these 10 codes can be used once to access your account.
          </div>

          <div className="grid grid-cols-2 gap-2 p-3 bg-muted/40 border border-border rounded-lg font-mono text-xs font-bold text-foreground">
            {recoveryCodes.map((code, idx) => (
              <div key={idx} className="p-1.5 bg-card border border-border text-foreground rounded text-center">
                {code}
              </div>
            ))}
          </div>

          <div className="flex justify-between items-center pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCopyRecoveryCodes}
              className="gap-1.5 text-xs"
            >
              <Copy className="h-3.5 w-3.5" /> Copy Codes
            </Button>
            <Button type="button" size="sm" onClick={() => setRecoveryModalOpen(false)}>
              I Have Saved My Codes
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Disable MFA Modal */}
      <Dialog
        open={disableModalOpen}
        onOpenChange={setDisableModalOpen}
        title="Disable Two-Factor Authentication"
        description="Enter your account password to confirm disabling 2FA."
      >
        <form onSubmit={handleDisableMFA} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">Account Password</label>
            <Input
              type="password"
              placeholder="••••••••••••"
              value={disablePassword}
              onChange={(e) => setDisablePassword(e.target.value)}
              required
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => setDisableModalOpen(false)}
              disabled={disableLoading}
            >
              Cancel
            </Button>
            <Button type="submit" variant="destructive" loading={disableLoading}>
              Disable 2FA
            </Button>
          </div>
        </form>
      </Dialog>
    </div>
  );
}

