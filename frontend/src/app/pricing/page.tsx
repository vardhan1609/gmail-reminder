"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, PlanInfo } from "@/lib/api";

export default function PricingPage(){
 const [plans,setPlans]=useState<Record<"basic"|"premium",PlanInfo>|null>(null);
 useEffect(()=>{api.getPlans().then(setPlans).catch(()=>setPlans(null))},[]);
 const price=(p:PlanInfo)=>p.price_paise===0?"Free / not configured":new Intl.NumberFormat("en-IN",{style:"currency",currency:p.currency}).format(p.price_paise/100)+" / month";
 return <main className="min-h-screen bg-background px-4 py-12 text-foreground"><div className="mx-auto max-w-5xl space-y-8"><header className="space-y-3 text-center"><Link href="/" className="text-sm text-primary hover:underline">← Gmail Reminder</Link><h1 className="text-3xl font-bold">Simple monthly plans</h1><p className="text-muted-foreground">Choose the mailbox capacity and notification allowance that fit your workflow.</p></header><div className="grid gap-5 md:grid-cols-2">{(["basic","premium"] as const).map(code=>{const p=plans?.[code];return <section key={code} className="rounded-xl border border-border bg-card p-6 shadow-sm"><h2 className="text-xl font-semibold">{p?.name||code}</h2><p className="mt-2 text-2xl font-bold">{p?price(p):"Loading price…"}</p><ul className="my-6 space-y-3 text-sm"><li>• {p?.gmail_accounts??(code==="basic"?1:4)} Gmail mailbox(es)</li><li>• Telegram notifications</li><li>• Google Calendar</li><li>• {code==="premium"?"WhatsApp included":"WhatsApp not included"}</li><li>• {p?.monthly_notifications??(code==="basic"?100:500)} monthly notifications</li></ul><Link href="/signup"><Button className="w-full" variant={code==="premium"?"default":"outline"}>Get started</Button></Link></section>})}</div><p className="text-center text-xs text-muted-foreground">Prices are configured by the service operator. Payment checkout is available after gateway credentials and plan prices are configured.</p><footer className="flex justify-center gap-5 text-sm"><Link href="/terms" className="text-primary hover:underline">Terms</Link><Link href="/privacy" className="text-primary hover:underline">Privacy</Link></footer></div></main>;
}
