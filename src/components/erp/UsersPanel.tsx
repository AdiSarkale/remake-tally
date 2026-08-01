import { useState } from "react";
import { KeyRound, Pencil, ShieldCheck, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useErp } from "@/lib/erp/store";
import { useAuth } from "@/lib/erp/auth";
import {
  createUser,
  generatePassword,
  resetUserPassword,
  setUserActive,
  updateUser,
  type UserDraft,
} from "@/lib/erp/users";
import type { Role, User } from "@/lib/erp/types";

const ROLES: Role[] = ["Admin", "Accountant", "Operator"];

const emptyDraft: UserDraft = {
  username: "",
  fullName: "",
  email: "",
  role: "Operator",
  password: "",
  active: true,
};

export function UsersPanel() {
  const users = useErp((s) => s.users);
  const { session } = useAuth();
  const isAdmin = session?.role === "Admin";
  const actor = session?.username ?? "system";

  const [addOpen, setAddOpen] = useState(false);
  const [draft, setDraft] = useState<UserDraft>(emptyDraft);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editDraft, setEditDraft] = useState(emptyDraft);
  const [pwdUser, setPwdUser] = useState<User | null>(null);
  const [pwd, setPwd] = useState("");
  const [pwd2, setPwd2] = useState("");

  const submitAdd = () => {
    const res = createUser(draft, actor);
    if (!res.ok) return toast.error(res.error);
    toast.success(`User @${draft.username.trim().toLowerCase()} created`);
    setAddOpen(false);
    setDraft(emptyDraft);
  };

  const submitEdit = () => {
    if (!editUser) return;
    const res = updateUser(editUser.id, editDraft, actor);
    if (!res.ok) return toast.error(res.error);
    toast.success("User updated");
    setEditUser(null);
  };

  const submitReset = () => {
    if (!pwdUser) return;
    if (pwd !== pwd2) return toast.error("Passwords do not match");
    const res = resetUserPassword(pwdUser.id, pwd, actor);
    if (!res.ok) return toast.error(res.error);
    toast.success(`Password reset for @${pwdUser.username}`);
    setPwdUser(null);
    setPwd("");
    setPwd2("");
  };

  return (
    <div className="panel p-4">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Users &amp; roles</h2>
        {isAdmin && (
          <Button size="sm" onClick={() => setAddOpen(true)}>
            <UserPlus className="mr-1 h-4 w-4" /> Add user
          </Button>
        )}
      </div>

      <div className="divide-border divide-y">
        {users.map((u) => (
          <div key={u.id} className="flex items-center justify-between gap-2 py-2.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">
                {u.fullName}
                {!u.active && <span className="text-muted-foreground ml-2 text-xs">(disabled)</span>}
              </p>
              <p className="text-muted-foreground truncate text-xs">
                @{u.username}
                {u.email ? ` · ${u.email}` : ""}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <Badge variant={u.role === "Admin" ? "default" : "secondary"}>{u.role}</Badge>
              {isAdmin && (
                <>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Edit ${u.username}`}
                    onClick={() => {
                      setEditUser(u);
                      setEditDraft({ ...emptyDraft, ...u });
                    }}
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Reset password for ${u.username}`}
                    onClick={() => {
                      setPwdUser(u);
                      setPwd("");
                      setPwd2("");
                    }}
                  >
                    <KeyRound className="h-4 w-4" />
                  </Button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      <p className="text-muted-foreground mt-4 flex items-start gap-1.5 text-xs">
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        {isAdmin
          ? "Admins can create users and reset any password without the old one. Every change is written to the audit trail."
          : "Only Admins can add users or reset passwords. Roles map to module access: Admin (all), Accountant (masters, inventory, sales, reports), Operator (production, scrap, inventory)."}
      </p>

      {/* Add user */}
      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add user</DialogTitle>
            <DialogDescription>Create a login and assign a role.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label className="mb-1.5 block text-xs">Username</Label>
              <Input value={draft.username} onChange={(e) => setDraft({ ...draft, username: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Full name</Label>
              <Input value={draft.fullName} onChange={(e) => setDraft({ ...draft, fullName: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Email</Label>
              <Input value={draft.email} onChange={(e) => setDraft({ ...draft, email: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Role</Label>
              <Select value={draft.role} onValueChange={(v) => setDraft({ ...draft, role: v as Role })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="sm:col-span-2">
              <Label className="mb-1.5 block text-xs">Temporary password</Label>
              <div className="flex gap-2">
                <Input value={draft.password} onChange={(e) => setDraft({ ...draft, password: e.target.value })} />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setDraft({ ...draft, password: generatePassword() })}
                >
                  Generate
                </Button>
              </div>
            </div>
            <div className="flex items-center gap-2 sm:col-span-2">
              <Switch
                id="add-active"
                checked={draft.active}
                onCheckedChange={(v) => setDraft({ ...draft, active: v })}
              />
              <Label htmlFor="add-active" className="text-xs">
                Allow sign-in
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submitAdd}>Create user</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit user */}
      <Dialog open={!!editUser} onOpenChange={(o) => !o && setEditUser(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit @{editUser?.username}</DialogTitle>
            <DialogDescription>Change the profile, role or sign-in access.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label className="mb-1.5 block text-xs">Full name</Label>
              <Input
                value={editDraft.fullName}
                onChange={(e) => setEditDraft({ ...editDraft, fullName: e.target.value })}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Email</Label>
              <Input
                value={editDraft.email}
                onChange={(e) => setEditDraft({ ...editDraft, email: e.target.value })}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Role</Label>
              <Select value={editDraft.role} onValueChange={(v) => setEditDraft({ ...editDraft, role: v as Role })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="edit-active"
                checked={editDraft.active}
                onCheckedChange={(v) => setEditDraft({ ...editDraft, active: v })}
              />
              <Label htmlFor="edit-active" className="text-xs">
                Allow sign-in
              </Label>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                if (!editUser) return;
                const res = setUserActive(editUser.id, !editUser.active, actor);
                if (!res.ok) return toast.error(res.error);
                toast.success(editUser.active ? "User disabled" : "User enabled");
                setEditUser(null);
              }}
            >
              {editUser?.active ? "Disable" : "Enable"}
            </Button>
            <Button onClick={submitEdit}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset password */}
      <Dialog open={!!pwdUser} onOpenChange={(o) => !o && setPwdUser(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Reset password</DialogTitle>
            <DialogDescription>
              Set a new password for @{pwdUser?.username}. The old password is not required.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div>
              <Label className="mb-1.5 block text-xs">New password</Label>
              <div className="flex gap-2">
                <Input value={pwd} onChange={(e) => setPwd(e.target.value)} />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    const g = generatePassword();
                    setPwd(g);
                    setPwd2(g);
                  }}
                >
                  Generate
                </Button>
              </div>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Confirm password</Label>
              <Input value={pwd2} onChange={(e) => setPwd2(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPwdUser(null)}>
              Cancel
            </Button>
            <Button onClick={submitReset}>Reset password</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
