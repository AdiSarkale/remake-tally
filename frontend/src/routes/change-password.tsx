import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useChangePassword } from "@/lib/api/hooks";
import { getStoredProfile } from "@/lib/api/client";

export const Route = createFileRoute("/change-password")({ component: ChangePasswordPage });

function ChangePasswordPage() {
  const navigate = useNavigate();
  const change = useChangePassword();
  const profile = getStoredProfile();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const submit = async () => {
    if (next.length < 6) return toast.error("New password must be at least 6 characters");
    if (next !== confirm) return toast.error("New passwords do not match");
    try {
      await change.mutateAsync({ current_password: current, new_password: next });
      toast.success("Password changed successfully");
      navigate({ to: "/" });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not change password");
    }
  };

  return <div className="flex min-h-screen items-center justify-center bg-background px-4">
    <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-sm">
      <h1 className="text-xl font-semibold">Set your password</h1>
      <p className="mt-2 text-sm text-muted-foreground">{profile?.full_name ?? "User"}, this is your first login. Change the default password before continuing.</p>
      <div className="mt-6 space-y-4">
        <div><Label>Current / default password</Label><Input type="password" value={current} onChange={e=>setCurrent(e.target.value)}/></div>
        <div><Label>New password</Label><Input type="password" value={next} onChange={e=>setNext(e.target.value)}/></div>
        <div><Label>Confirm new password</Label><Input type="password" value={confirm} onChange={e=>setConfirm(e.target.value)}/></div>
        <Button className="w-full" onClick={()=>void submit()} disabled={change.isPending}>Set password</Button>
      </div>
    </div>
  </div>;
}
