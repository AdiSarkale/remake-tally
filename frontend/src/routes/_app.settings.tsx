import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/page-header";
import { useCreateUser, useResetUserPassword, useUsers } from "@/lib/api/hooks";
import type { Role } from "@/lib/api/types";
import { useAuth } from "@/lib/auth";

const DEFAULT_INITIAL_PASSWORD = "Minitally@123";

export const Route = createFileRoute("/_app/settings")({
  head: () => ({ meta: [{ title: "Settings — Minitally ERP" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const { role } = useAuth();
  const users = useUsers();
  const createUser = useCreateUser();
  const resetPassword = useResetUserPassword();
  const [form, setForm] = useState({ username: "", full_name: "", email: "", role: "Operator" as Role });

  if (role !== "Admin") return <div className="p-6 text-sm text-destructive">Admin access required.</div>;

  const create = async () => {
    if (!form.username.trim() || !form.full_name.trim()) return toast.error("Username and full name are required");
    try {
      await createUser.mutateAsync({ ...form, active: true });
      toast.success("User created. Initial password: " + DEFAULT_INITIAL_PASSWORD);
      setForm({ username: "", full_name: "", email: "", role: "Operator" });
    } catch (e) { toast.error(e instanceof Error ? e.message : "Could not create user"); }
  };

  const reset = async (id: string, username: string) => {
    try {
      await resetPassword.mutateAsync({ id, new_password: DEFAULT_INITIAL_PASSWORD });
      toast.success("Password reset for " + username + ". Initial password: " + DEFAULT_INITIAL_PASSWORD);
    } catch (e) { toast.error(e instanceof Error ? e.message : "Could not reset password"); }
  };

  return <div className="space-y-6">
    <PageHeader title="Settings" description="User administration and access control" />
    <section className="rounded-lg border bg-card p-5">
      <h2 className="font-semibold">Add User</h2>
      <p className="mt-1 text-xs text-muted-foreground">New users start with the default password and must set their own password after first login.</p>
      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <div><Label>Username</Label><Input value={form.username} onChange={e=>setForm({...form,username:e.target.value})}/></div>
        <div><Label>Full name</Label><Input value={form.full_name} onChange={e=>setForm({...form,full_name:e.target.value})}/></div>
        <div><Label>Email</Label><Input value={form.email} onChange={e=>setForm({...form,email:e.target.value})}/></div>
        <div><Label>Role</Label><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={form.role} onChange={e=>setForm({...form,role:e.target.value as Role})}><option>Operator</option><option>Accountant</option><option>Admin</option></select></div>
      </div>
      <div className="mt-4 flex items-center gap-3"><Button onClick={()=>void create()} disabled={createUser.isPending}>Create User</Button><span className="font-mono text-xs text-muted-foreground">Default: {DEFAULT_INITIAL_PASSWORD}</span></div>
    </section>
    <section className="rounded-lg border bg-card">
      <div className="border-b p-5"><h2 className="font-semibold">Users</h2></div>
      <div className="divide-y">{(users.data ?? []).map(user=><div key={user.id} className="flex flex-wrap items-center justify-between gap-3 p-4"><div><div className="font-medium">{user.full_name} <span className="font-mono text-xs text-muted-foreground">@{user.username}</span></div><div className="text-xs text-muted-foreground">{user.role} · {user.active ? "Active" : "Inactive"}{user.must_change_password ? " · Password change required" : ""}</div></div><Button size="sm" variant="outline" onClick={()=>void reset(user.id,user.username)} disabled={resetPassword.isPending}>Reset password</Button></div>)}</div>
    </section>
  </div>;
}
