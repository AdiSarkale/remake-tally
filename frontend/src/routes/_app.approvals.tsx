import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Check, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader } from "@/components/erp/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/client";

export const Route = createFileRoute("/approvals")({ component: () => <AppShell><ApprovalsPage /></AppShell> });

type Approval = {
  id:string; department_id:string; department_code:string; department_name:string;
  request_type:string; reference_id:string|null; reference_no:string; title:string;
  amount:number; requested_by:string; status:string; remarks:string; decided_by:string;
  decided_at:string|null; created_at:string|null;
};
type Department = { id:string; code:string; name:string; hod_username:string; active:boolean };

function ApprovalsPage() {
  const [rows,setRows]=useState<Approval[]>([]);
  const [departments,setDepartments]=useState<Department[]>([]);
  const [isAdmin,setIsAdmin]=useState(false);
  const [form,setForm]=useState({code:"",name:"",hod_username:""});
  const load=async()=>{ 
    const a=await api.get<Approval[]>("/approvals/mine");
    setRows(a);
    try { const d=await api.get<Department[]>("/approvals/departments"); setDepartments(d); setIsAdmin(true); } catch { setIsAdmin(false); }
  };
  useEffect(()=>{void load().catch(e=>toast.error(e instanceof Error?e.message:"Failed to load approvals"));},[]);
  const addDept=async()=>{
    try {
      await api.post<Department>("/approvals/departments",{...form,active:true});
      setForm({code:"",name:"",hod_username:""});
      toast.success("Department created");
      await load();
    } catch(e){toast.error(e instanceof Error?e.message:"Could not create department");}
  };
  const decide=async(id:string,status:"Approved"|"Rejected")=>{
    const remarks=window.prompt(status==="Approved"?"Approval remarks":"Rejection reason","") ?? "";
    try { await api.patch<Approval>("/approvals/"+id,{status,remarks}); toast.success(status); await load(); }
    catch(e){toast.error(e instanceof Error?e.message:"Could not update approval");}
  };
  return <div className="space-y-5">
    <PageHeader title="HOD Approvals" subtitle="Each HOD sees only approval requests assigned to their department." />
    {isAdmin ? <section className="rounded-lg border p-4">
      <div className="mb-3 flex items-center gap-2"><Plus className="h-4 w-4"/><h2 className="font-semibold">Department Master</h2></div>
      <div className="grid gap-3 md:grid-cols-4">
        <Input placeholder="Code e.g. PROD" value={form.code} onChange={e=>setForm({...form,code:e.target.value})}/>
        <Input placeholder="Department name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
        <Input placeholder="HOD username" value={form.hod_username} onChange={e=>setForm({...form,hod_username:e.target.value})}/>
        <Button onClick={()=>void addDept()}>Create Department</Button>
      </div>
      <div className="mt-4 divide-y">{departments.map(d=><div key={d.id} className="flex items-center justify-between py-2 text-sm"><span><b>{d.code}</b> — {d.name}</span><span className="text-muted-foreground">HOD: {d.hod_username}</span></div>)}</div>
    </section> : null}
    <section className="rounded-lg border">
      <div className="border-b p-4"><div className="font-semibold">My Department Approvals</div><div className="text-xs text-muted-foreground">{rows.filter(r=>r.status==="Pending").length} pending</div></div>
      <div className="divide-y">
        {rows.length===0 ? <div className="p-8 text-center text-sm text-muted-foreground">No approvals for your department.</div> :
        rows.map(r=><div key={r.id} className="p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div><div className="text-xs text-muted-foreground">{r.department_code} · {r.request_type} · {r.reference_no}</div><div className="font-semibold">{r.title}</div><div className="text-sm text-muted-foreground">Requested by {r.requested_by}{r.amount ? ` · ₹${r.amount.toLocaleString("en-IN")}` : ""}</div></div>
            <span className={r.status==="Pending"?"rounded-full border px-2 py-1 text-xs":"rounded-full border px-2 py-1 text-xs opacity-70"}>{r.status}</span>
          </div>
          {r.status==="Pending" ? <div className="mt-3 flex gap-2"><Button size="sm" onClick={()=>void decide(r.id,"Approved")}><Check className="mr-1 h-4 w-4"/>Approve</Button><Button size="sm" variant="outline" onClick={()=>void decide(r.id,"Rejected")}><X className="mr-1 h-4 w-4"/>Reject</Button></div> : <div className="mt-2 text-xs text-muted-foreground">Decided by {r.decided_by}</div>}
        </div>)}
      </div>
    </section>
  </div>;
}
