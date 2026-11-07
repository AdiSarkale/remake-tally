import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api/client";
import * as H from "@/lib/api/hooks";

interface EmployeeLink { id: string; user_id: string; employee_id: string; created_by: string; }
interface Branch { id: string; code: string; name: string; timezone: string; active: boolean; }
interface OrgAssignment { id: string; employee_id: string; branch_id: string | null; manager_employee_id: string | null; department: string; valid_from: string; valid_to: string | null; created_by: string; }
interface RoleGrant {
  id: string; role: string; module: string; feature: string; action: string;
  data_scope: "tenant" | "self" | "department"; allowed: boolean; updated_by: string;
}
const scopes = ["tenant", "department", "branch", "team", "self"] as const;

export function AuthorizationPanel() {
  const users = H.useUsers();
  const employees = H.useEmployees(true);
  const [links, setLinks] = useState<EmployeeLink[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [assignments, setAssignments] = useState<OrgAssignment[]>([]);
  const [branchForm, setBranchForm] = useState({ code: "", name: "", timezone: "Asia/Kolkata", address: "" });
  const [assignmentForm, setAssignmentForm] = useState({ employee_id: "", branch_id: "", manager_employee_id: "", department: "", valid_from: new Date().toISOString().slice(0, 10) });
  const [grants, setGrants] = useState<RoleGrant[]>([]);
  const [userId, setUserId] = useState("");
  const [employeeId, setEmployeeId] = useState("");
  const [grantForm, setGrantForm] = useState({
    role: "Operator", module: "hr", feature: "leave_requests",
    action: "create", data_scope: "self" as RoleGrant["data_scope"], allowed: true,
  });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    try {
      const [linkRows, grantRows, branchRows, assignmentRows] = await Promise.all([
        api.get<EmployeeLink[]>("/authorization/employee-links"),
        api.get<RoleGrant[]>("/authorization/role-grants"),
        api.get<Branch[]>("/authorization/branches"),
        api.get<OrgAssignment[]>("/authorization/employee-org-assignments"),
      ]);
      setLinks(linkRows);
      setGrants(grantRows);
      setBranches(branchRows);
      setAssignments(assignmentRows);
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not load authorization settings"); }
  };
  useEffect(() => { void load(); }, []);

  const createLink = async () => {
    if (!userId || !employeeId) {
      toast.error("Choose a user account and employee record");
      return;
    }
    setBusy(true);
    try {
      await api.post("/authorization/employee-links", { user_id: userId, employee_id: employeeId });
      toast.success("Employee account linked");
      setUserId(""); setEmployeeId("");
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not create employee link"); }
    finally { setBusy(false); }
  };

  const deleteLink = async (link: EmployeeLink) => {
    if (!window.confirm("Remove this employee-account link? Self-service access will stop.")) return;
    setBusy(true);
    try {
      await api.delete("/authorization/employee-links/" + link.id);
      toast.success("Employee link removed");
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not remove employee link"); }
    finally { setBusy(false); }
  };

  const createBranch = async () => {
    if (!branchForm.code.trim() || !branchForm.name.trim()) { toast.error("Enter branch code and name"); return; }
    setBusy(true);
    try { await api.post("/authorization/branches", branchForm); toast.success("Branch created"); setBranchForm({ code: "", name: "", timezone: "Asia/Kolkata", address: "" }); await load(); }
    catch (err) { toast.error(err instanceof Error ? err.message : "Could not create branch"); }
    finally { setBusy(false); }
  };
  const saveAssignment = async () => {
    if (!assignmentForm.employee_id || !assignmentForm.valid_from) { toast.error("Choose an employee and effective date"); return; }
    setBusy(true);
    try { await api.post("/authorization/employee-org-assignments", { ...assignmentForm, branch_id: assignmentForm.branch_id || null, manager_employee_id: assignmentForm.manager_employee_id || null }); toast.success("Employee organisation assignment saved"); await load(); }
    catch (err) { toast.error(err instanceof Error ? err.message : "Could not save assignment"); }
    finally { setBusy(false); }
  };

  const saveGrant = async () => {
    setBusy(true);
    try {
      await api.put("/authorization/role-grants", grantForm);
      toast.success("Role permission saved");
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not save role permission"); }
    finally { setBusy(false); }
  };

  const userLabel = (id: string) => {
    const row = users.data?.find((user) => user.id === id);
    return row ? row.username + " · " + row.role : id;
  };
  const employeeLabel = (id: string) => {
    const row = employees.data?.find((employee) => employee.id === id);
    return row ? row.emp_code + " · " + row.name : id;
  };

  return (
    <section className="space-y-5">
      <header><h2 className="text-lg font-semibold">Authorization & Account Mapping</h2><p className="text-sm text-muted-foreground">Link login accounts to employee records and manage persisted role permissions. Only Admin can change these settings.</p></header>

      <div className="rounded-lg border p-4 space-y-3">
        <h3 className="font-semibold">Link user account to employee</h3>
        <p className="text-xs text-muted-foreground">Each user account can link to one employee, and each employee can link to one account. This mapping powers self-service leave and payslip access.</p>
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <label className="space-y-1 text-sm"><span>User account</span><select className="h-9 w-full rounded-md border bg-background px-3" value={userId} onChange={(event) => setUserId(event.target.value)}><option value="">Select user</option>{(users.data ?? []).filter((user) => user.active && !links.some((link) => link.user_id === user.id)).map((user) => <option key={user.id} value={user.id}>{user.username} · {user.role}</option>)}</select></label>
          <label className="space-y-1 text-sm"><span>Employee record</span><select className="h-9 w-full rounded-md border bg-background px-3" value={employeeId} onChange={(event) => setEmployeeId(event.target.value)}><option value="">Select employee</option>{(employees.data ?? []).filter((employee) => employee.active && !links.some((link) => link.employee_id === employee.id)).map((employee) => <option key={employee.id} value={employee.id}>{employee.emp_code} · {employee.name}</option>)}</select></label>
          <div className="flex items-end"><Button size="sm" disabled={busy || users.isLoading || employees.isLoading} onClick={() => void createLink()}>Create link</Button></div>
        </div>
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-sm"><thead><tr className="border-b text-left text-muted-foreground"><th className="py-2">User</th><th className="py-2">Employee</th><th className="py-2">Created by</th><th className="py-2">Action</th></tr></thead><tbody>{links.map((link) => <tr key={link.id} className="border-b last:border-0"><td className="py-2">{userLabel(link.user_id)}</td><td className="py-2">{employeeLabel(link.employee_id)}</td><td className="py-2">{link.created_by}</td><td className="py-2"><Button size="icon" variant="outline" aria-label="Remove employee link" disabled={busy} onClick={() => void deleteLink(link)}><Trash2 className="size-4" /></Button></td></tr>)}{links.length === 0 ? <tr><td colSpan={4} className="py-5 text-center text-muted-foreground">No employee account links configured.</td></tr> : null}</tbody></table></div>
      </div>

      <div className="rounded-lg border p-4 space-y-3">
        <h3 className="font-semibold">Branches and reporting structure</h3>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <p className="text-sm font-medium">Create branch</p>
            <div className="grid gap-2 sm:grid-cols-2">
              <Input placeholder="Branch code" value={branchForm.code} onChange={(e) => setBranchForm({ ...branchForm, code: e.target.value.toUpperCase() })} />
              <Input placeholder="Branch name" value={branchForm.name} onChange={(e) => setBranchForm({ ...branchForm, name: e.target.value })} />
              <Input placeholder="IANA timezone" value={branchForm.timezone} onChange={(e) => setBranchForm({ ...branchForm, timezone: e.target.value })} />
              <Input placeholder="Address" value={branchForm.address} onChange={(e) => setBranchForm({ ...branchForm, address: e.target.value })} />
            </div>
            <Button size="sm" disabled={busy} onClick={() => void createBranch()}>Add branch</Button>
            {branches.map((row) => <p key={row.id} className="text-sm">{row.code} · {row.name} <span className="text-muted-foreground">({row.timezone})</span></p>)}
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium">Assign employee organisation</p>
            <p className="text-xs text-muted-foreground">Effective-dated; a new assignment closes the previous assignment the day before it starts.</p>
            <select className="h-9 w-full rounded-md border bg-background px-2" value={assignmentForm.employee_id} onChange={(e) => setAssignmentForm({ ...assignmentForm, employee_id: e.target.value })}><option value="">Select employee</option>{(employees.data ?? []).filter((row) => row.active).map((row) => <option key={row.id} value={row.id}>{row.emp_code} · {row.name}</option>)}</select>
            <select className="h-9 w-full rounded-md border bg-background px-2" value={assignmentForm.branch_id} onChange={(e) => setAssignmentForm({ ...assignmentForm, branch_id: e.target.value })}><option value="">No branch</option>{branches.filter((row) => row.active).map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}</select>
            <select className="h-9 w-full rounded-md border bg-background px-2" value={assignmentForm.manager_employee_id} onChange={(e) => setAssignmentForm({ ...assignmentForm, manager_employee_id: e.target.value })}><option value="">No manager</option>{(employees.data ?? []).filter((row) => row.active && row.id !== assignmentForm.employee_id).map((row) => <option key={row.id} value={row.id}>{row.emp_code} · {row.name}</option>)}</select>
            <Input placeholder="Department" value={assignmentForm.department} onChange={(e) => setAssignmentForm({ ...assignmentForm, department: e.target.value })} />
            <Input type="date" value={assignmentForm.valid_from} onChange={(e) => setAssignmentForm({ ...assignmentForm, valid_from: e.target.value })} />
            <Button size="sm" disabled={busy} onClick={() => void saveAssignment()}>Save assignment</Button>
            <div className="max-h-32 overflow-auto text-xs">{assignments.map((row) => <p key={row.id} className="border-b py-1">{employeeLabel(row.employee_id)} · {row.valid_from} – {row.valid_to || "current"}</p>)}</div>
          </div>
        </div>
        <h3 className="font-semibold">Role permission grants</h3>
        <p className="text-xs text-muted-foreground">A grant is defined by role → module → feature → action → data scope. Setting Allowed to off revokes that exact grant. Branch and team scopes are not available until those relationships exist in the data model.</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <label className="space-y-1 text-sm"><span>Role</span><select className="h-9 w-full rounded-md border bg-background px-3" value={grantForm.role} onChange={(event) => setGrantForm({ ...grantForm, role: event.target.value })}>{["Admin", "HR", "Accountant", "Operator"].map((role) => <option key={role}>{role}</option>)}</select></label>
          <label className="space-y-1 text-sm"><span>Module</span><Input value={grantForm.module} onChange={(event) => setGrantForm({ ...grantForm, module: event.target.value.toLowerCase().replace(/\s+/g, "_") })} /></label>
          <label className="space-y-1 text-sm"><span>Feature</span><Input value={grantForm.feature} onChange={(event) => setGrantForm({ ...grantForm, feature: event.target.value.toLowerCase().replace(/\s+/g, "_") })} /></label>
          <label className="space-y-1 text-sm"><span>Action</span><Input value={grantForm.action} onChange={(event) => setGrantForm({ ...grantForm, action: event.target.value.toLowerCase() })} /></label>
          <label className="space-y-1 text-sm"><span>Data scope</span><select className="h-9 w-full rounded-md border bg-background px-3" value={grantForm.data_scope} onChange={(event) => setGrantForm({ ...grantForm, data_scope: event.target.value as RoleGrant["data_scope"] })}>{scopes.map((scope) => <option key={scope} value={scope}>{scope}</option>)}</select></label>
          <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={grantForm.allowed} onChange={(event) => setGrantForm({ ...grantForm, allowed: event.target.checked })} /> Allowed</label>
        </div>
        <Button size="sm" disabled={busy || !grantForm.module.trim() || !grantForm.feature.trim() || !grantForm.action.trim()} onClick={() => void saveGrant()}>Save permission</Button>
        <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-sm"><thead><tr className="border-b text-left text-muted-foreground">{["Role", "Module", "Feature", "Action", "Scope", "Allowed", "Updated by"].map((label) => <th key={label} className="py-2 pr-3">{label}</th>)}</tr></thead><tbody>{grants.map((grant) => <tr key={grant.id} className="border-b last:border-0"><td className="py-2 pr-3">{grant.role}</td><td className="py-2 pr-3">{grant.module}</td><td className="py-2 pr-3">{grant.feature}</td><td className="py-2 pr-3">{grant.action}</td><td className="py-2 pr-3">{grant.data_scope}</td><td className="py-2 pr-3">{grant.allowed ? "Yes" : "No"}</td><td className="py-2 pr-3">{grant.updated_by}</td></tr>)}{grants.length === 0 ? <tr><td colSpan={7} className="py-5 text-center text-muted-foreground">No role grants configured.</td></tr> : null}</tbody></table></div>
      </div>
    </section>
  );
}
