"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, PlanInfo, SubscriptionInfo } from "@/lib/api";

const money = (paise: number, currency: string) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency }).format(paise / 100);

export default function BillingPage() {
  const [plans, setPlans] = useState<Record<"basic" | "premium", PlanInfo> | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [provider, setProvider] = useState<"razorpay" | "cashfree">("razorpay");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const load = async () => {
    try {
      const [p, s] = await Promise.all([api.getPlans(), api.getSubscription()]);
      setPlans(p);
      setSubscription(s);
    } catch (e: any) { setMessage(e.detail || "Could not load subscription details."); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const checkout = async (plan: "basic" | "premium") => {
    setBusy(true); setMessage("");
    try {
      const result = await api.createCheckout(plan, provider);
      window.location.assign(result.checkout_url);
    } catch (e: any) { setMessage(e.detail || "Unable to start checkout."); setBusy(false); }
  };
  const cancel = async () => {
    setBusy(true);
    try { const r = await api.cancelSubscription(); setMessage(r.message); await load(); }
    catch (e: any) { setMessage(e.detail || "Unable to cancel subscription."); }
    finally { setBusy(false); }
  };

  return <div className="flex min-h-screen flex-col"><Header title="Subscription & Billing" description="Review your plan, monthly usage and available features."/><main className="mx-auto w-full max-w-6xl flex-1 space-y-6 p-4 sm:p-6 lg:p-8">
    {message && <div role="status" className="rounded-lg border border-border bg-muted p-3 text-sm">{message}</div>}
    {loading ? <p className="text-sm text-muted-foreground">Loading subscription…</p> : <>
      {subscription && <Card><CardHeader><CardTitle>Current plan: {subscription.plan_name}</CardTitle><CardDescription>Status: {subscription.status} · {subscription.cancel_at_period_end ? "Cancellation scheduled" : "Active access"}</CardDescription></CardHeader><CardContent className="space-y-3">
        <div className="flex items-center justify-between text-sm"><span>Monthly notifications used</span><strong>{subscription.usage.notifications_used} / {subscription.usage.notifications_limit}</strong></div>
        <div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full rounded-full bg-primary" style={{width: Math.min(100, subscription.usage.notifications_used / Math.max(1, subscription.usage.notifications_limit) * 100) + "%"}}/></div>
        <div className="grid gap-2 text-sm sm:grid-cols-2"><p>Gmail accounts: {subscription.limits.gmail_accounts}</p><p>Telegram: Included</p><p>Google Calendar: Included</p><p>WhatsApp: {subscription.limits.whatsapp ? "Included" : "Premium only"}</p></div>
        {subscription.plan_code === "premium" && !subscription.cancel_at_period_end && <Button variant="outline" disabled={busy} onClick={cancel}>Cancel at period end</Button>}
      </CardContent></Card>}
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-xl font-semibold">Choose a plan</h2><p className="text-sm text-muted-foreground">Monthly access. Plan limits are enforced by the backend.</p></div><label className="text-sm">Payment provider <select className="ml-2 rounded-md border border-input bg-background p-2" value={provider} onChange={e=>setProvider(e.target.value as "razorpay"|"cashfree")}><option value="razorpay">Razorpay</option><option value="cashfree">Cashfree</option></select></label></div>
      <div className="grid gap-5 md:grid-cols-2">{(["basic","premium"] as const).map(code=>{const p=plans?.[code];if(!p)return null;const current=subscription?.plan_code===code;return <Card key={code} className={code==="premium"?"border-primary/50 shadow-md":""}><CardHeader><CardTitle className="flex items-center justify-between">{p.name}{current&&<span className="rounded-full bg-primary/10 px-2 py-1 text-xs text-primary">Current plan</span>}</CardTitle><CardDescription>{p.price_paise===0?(code==="basic"?"Free":"Price not configured"):money(p.price_paise,p.currency)} / month</CardDescription></CardHeader><CardContent className="space-y-4"><ul className="space-y-2 text-sm"><li>✓ {p.gmail_accounts} connected Gmail {p.gmail_accounts===1?"account":"accounts"}</li><li>✓ Telegram notifications</li><li>✓ Google Calendar integration</li><li>{p.whatsapp?"✓ WhatsApp notifications":"— WhatsApp (Premium only)"}</li><li>✓ {p.monthly_notifications} notifications per calendar month</li></ul>{code==="premium"&&!current&&<Button className="w-full" disabled={busy||p.price_paise<=0} onClick={()=>checkout(code)}>{p.price_paise<=0?"Set Premium price to enable checkout":"Upgrade to Premium"}</Button>}{current&&<Button className="w-full" variant="outline" disabled>Active plan</Button>}</CardContent></Card>})}</div>
      <p className="text-xs text-muted-foreground">Payments are processed by the selected payment provider. Premium access is activated only after a verified payment webhook. Monthly renewals currently require a new checkout; automatic recurring billing is not enabled.</p>
    </>}
  </main></div>;
}
