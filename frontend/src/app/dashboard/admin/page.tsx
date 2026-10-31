"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";

type Customer = {id:string;email:string;full_name:string|null;is_active:boolean;is_verified:boolean;is_admin:boolean;created_at:string|null;plan_code:string;subscription_status:string;gmail_accounts:number;channels:string[];notifications_used:number;notifications_limit:number};

export default function AdminPage(){
 const {user,loading:authLoading}=useAuth();
 const [overview,setOverview]=useState<any>(null);
 const [customers,setCustomers]=useState<Customer[]>([]);
 const [query,setQuery]=useState("");
 const [loading,setLoading]=useState(true);
 const [error,setError]=useState("");
 const [busy,setBusy]=useState<string|null>(null);
 const load=useCallback(async()=>{
  setLoading(true);setError("");
  try{const [o,c]=await Promise.all([api.getAdminOverview(),api.getAdminCustomers(query)]);setOverview(o);setCustomers(c.customers||[]);}
  catch(e:any){setError(e.detail||"Could not load admin data.");}
  finally{setLoading(false);}
 },[query]);
 useEffect(()=>{if(user?.is_admin)load();else if(!authLoading)setLoading(false)},[user,authLoading,load]);
 const update=async(id:string,body:{is_active?:boolean;plan_code?:"basic"|"premium"})=>{
  setBusy(id);setError("");
  try{await api.updateAdminCustomer(id,body);await load();}
  catch(e:any){setError(e.detail||"Customer update failed.");}
  finally{setBusy(null);}
 };
 if(!authLoading&&!user?.is_admin)return <div className="p-8 text-sm text-destructive">Administrator access required.</div>;
 return <div className="flex min-h-screen flex-col"><Header title="Admin · Customer Management" description="Manage customer accounts, subscription tiers and usage."/><main className="mx-auto w-full max-w-7xl flex-1 space-y-6 p-4 sm:p-6 lg:p-8">
 {error&&<div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</div>}
 {overview&&<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[["Customers",overview.customers],["Active subscriptions",overview.active_subscriptions],["Basic",overview.basic_customers],["Premium",overview.premium_customers],["Paid orders",overview.paid_orders],["Pending orders",overview.pending_orders]].map(([label,value])=><Card key={String(label)}><CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground">{label}</CardTitle></CardHeader><CardContent><p className="text-2xl font-bold">{value}</p></CardContent></Card>)}</div>}
 <Card><CardHeader><CardTitle>Customers</CardTitle><div className="flex flex-col gap-2 sm:flex-row"><input className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="Search name or email" value={query} onChange={e=>setQuery(e.target.value)}/><Button variant="outline" onClick={load}>Search</Button></div></CardHeader><CardContent>{loading?<p className="text-sm text-muted-foreground">Loading customers…</p>:customers.length===0?<p className="text-sm text-muted-foreground">No customers found.</p>:<div className="overflow-x-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead><tr className="border-b text-muted-foreground"><th className="p-2">Customer</th><th className="p-2">Plan</th><th className="p-2">Gmail</th><th className="p-2">Channels</th><th className="p-2">Monthly usage</th><th className="p-2">Account</th><th className="p-2">Actions</th></tr></thead><tbody>{customers.map(c=><tr key={c.id} className="border-b border-border"><td className="p-2"><div className="font-medium">{c.full_name||"—"}</div><div className="text-xs text-muted-foreground">{c.email}</div><div className="text-xs text-muted-foreground">{c.is_verified?"Verified":"Unverified"}{c.is_admin?" · Admin":""}</div></td><td className="p-2"><select aria-label={"Plan for "+c.email} className="rounded border border-input bg-background p-1" value={c.plan_code} disabled={busy===c.id} onChange={e=>update(c.id,{plan_code:e.target.value as "basic"|"premium"})}><option value="basic">Basic</option><option value="premium">Premium</option></select></td><td className="p-2">{c.gmail_accounts}</td><td className="p-2">{c.channels.join(", ")||"—"}</td><td className="p-2">{c.notifications_used} / {c.notifications_limit}</td><td className="p-2">{c.is_active?"Active":"Disabled"}</td><td className="p-2"><Button size="sm" variant="outline" disabled={busy===c.id||c.is_admin} onClick={()=>update(c.id,{is_active:!c.is_active})}>{c.is_active?"Disable":"Enable"}</Button></td></tr>)}</tbody></table></div>}</CardContent></Card>
 <p className="text-xs text-muted-foreground">Admin changes are privileged actions. Do not share admin access. Payment reconciliation and refunds should be handled in the provider dashboard until a dedicated refund workflow is added.</p>
 </main></div>;
}
