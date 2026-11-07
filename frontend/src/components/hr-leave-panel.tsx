import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface LeaveType {
  id: string; code: string; name: string; is_paid: boolean; annual_entitlement: number;
  carry_forward_limit: number; accrual_method: "annual_upfront" | "monthly" | "monthly_prorated"; accrual_effective_from: string; count_week_offs: boolean; count_holidays: boolean;
  allow_half_day: boolean; active: boolean;
}
interface LeaveBalance {
  id: string; employee_id: string; leave_type_id: string; year: number;
  opening_balance: number; accrued: number; adjusted: number; used: number; available: number;
}
interface LeaveRequest {
  id: string; employee_id: string; leave_type_id: string; start_date: string; end_date: string;
  total_days: number; half_day: boolean; reason: string; status: string; requested_by: string;
  approver_username: string; decided_by: string; decision_note: string;
}
interface Employee { id: string; emp_code: string; name: string; department: string; active: boolean; }

export function LeavePanel({ canManage, username }: { canManage: boolean; username: string }) {
  const [year, setYear] = useState(new Date().getFullYear());
  const [accrualMonth, setAccrualMonth] = useState(new Date().getMonth() + 1);
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [balances, setBalances] = useState<LeaveBalance[]>([]);
  const [requests, setRequests] = useState<LeaveRequest[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [halfDay, setHalfDay] = useState(false);
  const [reason, setReason] = useState("");
  const [typeForm, setTypeForm] = useState({
    code: "", name: "", is_paid: true, annual_entitlement: 12, accrual_method: "annual_upfront" as const, accrual_effective_from: new Date().getFullYear() + "-01-01", carry_forward_limit: 0,
    count_week_offs: false, count_holidays: false, allow_half_day: true, active: true,
  });
  const [balanceForm, setBalanceForm] = useState({
    employee_id: "", leave_type_id: "", opening_balance: 0, accrued: 0, adjusted: 0,
  });

  const load = async () => {
    setLoading(true);
    try {
      const [typeRows, balanceRows, requestRows] = await Promise.all([
        api.get<LeaveType[]>("/hr/leave/types"),
        api.get<LeaveBalance[]>("/hr/leave/balances?year=" + year),
        api.get<LeaveRequest[]>("/hr/leave/requests"),
      ]);
      setTypes(typeRows);
      setBalances(balanceRows);
      setRequests(requestRows);
      setLeaveTypeId((current) => current && typeRows.some((row) => row.id === current) ? current : typeRows[0]?.id ?? "");
      setBalanceForm((current) => ({ ...current, leave_type_id: current.leave_type_id || typeRows[0]?.id || "" }));
      if (canManage) {
        const employeeRows = await api.get<Employee[]>("/manufacturing/employees?include_inactive=true");
        setEmployees(employeeRows);
        setBalanceForm((current) => ({ ...current, employee_id: current.employee_id || employeeRows.find((row) => row.active)?.id || "" }));
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not load leave data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [year, canManage]);

  const typeName = (id: string) => types.find((row) => row.id === id)?.name ?? "Unknown leave type";
  const employeeName = (id: string) => {
    const row = employees.find((employee) => employee.id === id);
    return row ? row.emp_code + " · " + row.name : id;
  };

  const submitRequest = async () => {
    if (!leaveTypeId || !startDate || !endDate || !reason.trim()) {
      toast.error("Choose a leave type, dates and reason");
      return;
    }
    setBusy(true);
    try {
      await api.post("/hr/leave/requests", {
        leave_type_id: leaveTypeId, start_date: startDate, end_date: endDate,
        half_day: halfDay, reason: reason.trim(),
      });
      toast.success("Leave request submitted to the configured approver");
      setReason(""); setHalfDay(false);
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Leave request failed"); }
    finally { setBusy(false); }
  };

  const createType = async () => {
    if (!typeForm.code.trim() || !typeForm.name.trim()) {
      toast.error("Enter a leave type code and name");
      return;
    }
    setBusy(true);
    try {
      await api.post("/hr/leave/types", typeForm);
      toast.success("Leave policy created");
      setTypeForm({
        code: "", name: "", is_paid: true, annual_entitlement: 12, accrual_method: "annual_upfront" as const, accrual_effective_from: new Date().getFullYear() + "-01-01", carry_forward_limit: 0,
        count_week_offs: false, count_holidays: false, allow_half_day: true, active: true,
      });
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not create leave policy"); }
    finally { setBusy(false); }
  };

  const saveBalance = async () => {
    if (!balanceForm.employee_id || !balanceForm.leave_type_id) {
      toast.error("Choose an employee and leave type");
      return;
    }
    setBusy(true);
    try {
      await api.put("/hr/leave/balances", { ...balanceForm, year });
      toast.success("Leave balance saved");
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Could not save leave balance"); }
    finally { setBusy(false); }
  };

  const runAccrual = async () => {
    setBusy(true);
    try {
      const result = await api.post<{ created_count: number; total_accrued: number; skipped_existing: number }>(
        "/hr/leave/accruals/run/" + year + "/" + accrualMonth,
      );
      toast.success(result.created_count + " accrual entries created · " + result.total_accrued.toFixed(2) + " days; " + result.skipped_existing + " already processed");
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Leave accrual failed"); }
    finally { setBusy(false); }
  };

  const carryForward = async () => {
    setBusy(true);
    try {
      const rows = await api.post<LeaveBalance[]>("/hr/leave/balances/carry-forward/" + (year - 1));
      toast.success(rows.length + " leave balance(s) carried into " + year);
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Carry-forward failed"); }
    finally { setBusy(false); }
  };

  const decide = async (request: LeaveRequest, status: "approved" | "rejected") => {
    const note = window.prompt(status === "approved" ? "Approval note (optional):" : "Reason for rejection:");
    if (note === null) return;
    setBusy(true);
    try {
      await api.patch("/hr/leave/requests/" + request.id, { status, decision_note: note });
      toast.success("Leave request " + status);
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Decision failed"); }
    finally { setBusy(false); }
  };

  const cancel = async (request: LeaveRequest) => {
    if (!window.confirm("Cancel this pending leave request?")) return;
    setBusy(true);
    try {
      await api.delete("/hr/leave/requests/" + request.id);
      toast.success("Leave request cancelled");
      await load();
    } catch (err) { toast.error(err instanceof Error ? err.message : "Cancellation failed"); }
    finally { setBusy(false); }
  };

  const canDecide = (request: LeaveRequest) =>
    request.status === "pending" && (canManage || request.approver_username === username);

  return (
    <section className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div><h2 className="text-lg font-semibold">Leave Management</h2><p className="text-sm text-muted-foreground">Leave policies, balances, employee requests and department approvals.</p></div>
        <div className="flex items-center gap-2"><label className="text-xs text-muted-foreground" htmlFor="leave-year">Leave year</label><Input id="leave-year" className="w-24" type="number" min="2000" max="2100" value={year} onChange={(event) => setYear(Number(event.target.value) || new Date().getFullYear())} /><Button size="sm" variant="outline" disabled={busy || loading} onClick={() => void load()}>Refresh</Button></div>
      </header>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border p-4 space-y-3">
          <h3 className="font-semibold">Apply for leave</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm"><span>Leave type</span><select className="h-9 w-full rounded-md border bg-background px-3" value={leaveTypeId} onChange={(event) => setLeaveTypeId(event.target.value)}>{types.filter((row) => row.active).map((row) => <option key={row.id} value={row.id}>{row.name} · {row.is_paid ? "Paid" : "Unpaid"}</option>)}</select></label>
            <label className="space-y-1 text-sm"><span>Start date</span><Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
            <label className="space-y-1 text-sm"><span>End date</span><Input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
            <label className="flex items-center gap-2 pt-6 text-sm"><input type="checkbox" checked={halfDay} onChange={(event) => setHalfDay(event.target.checked)} /> Half-day request</label>
          </div>
          <label className="block space-y-1 text-sm"><span>Reason</span><textarea className="min-h-20 w-full rounded-md border bg-background p-2" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={2000} /></label>
          <Button size="sm" disabled={busy || loading || types.filter((row) => row.active).length === 0} onClick={() => void submitRequest()}>Submit leave request</Button>
          <p className="text-xs text-muted-foreground">Your approver is assigned from your department configuration. You cannot choose or approve your own request.</p>
        </div>

        <div className="rounded-lg border p-4 space-y-3">
          <h3 className="font-semibold">{canManage ? "Leave balances" : "My leave balances"}</h3>
          {loading ? <p className="text-sm text-muted-foreground">Loading balances…</p> : balances.length ? <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-muted-foreground"><th className="py-2">Leave type</th><th className="py-2 text-right">Available</th><th className="py-2 text-right">Used</th></tr></thead><tbody>{balances.map((row) => <tr key={row.id} className="border-b last:border-0"><td className="py-2">{typeName(row.leave_type_id)}</td><td className="py-2 text-right font-medium tabular-nums">{row.available}</td><td className="py-2 text-right tabular-nums">{row.used}</td></tr>)}</tbody></table></div> : <p className="text-sm text-muted-foreground">No balances allocated for {year} yet.</p>}
        </div>
      </div>

      {canManage ? <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border p-4 space-y-3">
          <h3 className="font-semibold">Create leave policy</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-sm"><span>Code</span><Input value={typeForm.code} onChange={(event) => setTypeForm({ ...typeForm, code: event.target.value.toUpperCase() })} placeholder="CL" /></label>
            <label className="space-y-1 text-sm"><span>Name</span><Input value={typeForm.name} onChange={(event) => setTypeForm({ ...typeForm, name: event.target.value })} placeholder="Casual Leave" /></label>
            <label className="space-y-1 text-sm"><span>Annual entitlement</span><Input type="number" min="0" max="366" value={typeForm.annual_entitlement} onChange={(event) => setTypeForm({ ...typeForm, annual_entitlement: Number(event.target.value) })} /></label>
            <label className="space-y-1 text-sm"><span>Accrual method</span><select className="h-9 w-full rounded-md border bg-background px-3" value={typeForm.accrual_method} onChange={(event) => setTypeForm({ ...typeForm, accrual_method: event.target.value as typeof typeForm.accrual_method })}><option value="annual_upfront">Annual upfront (HR allocated)</option><option value="monthly">Monthly</option><option value="monthly_prorated">Monthly, prorated for join/exit/effective date</option></select></label>
            <label className="space-y-1 text-sm"><span>Policy effective from</span><Input type="date" value={typeForm.accrual_effective_from} onChange={(event) => setTypeForm({ ...typeForm, accrual_effective_from: event.target.value })} /></label>
            <label className="space-y-1 text-sm"><span>Carry-forward limit</span><Input type="number" min="0" max="366" value={typeForm.carry_forward_limit} onChange={(event) => setTypeForm({ ...typeForm, carry_forward_limit: Number(event.target.value) })} /></label>
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={typeForm.is_paid} onChange={(event) => setTypeForm({ ...typeForm, is_paid: event.target.checked })} /> Paid leave</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={typeForm.allow_half_day} onChange={(event) => setTypeForm({ ...typeForm, allow_half_day: event.target.checked })} /> Allow half day</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={typeForm.count_week_offs} onChange={(event) => setTypeForm({ ...typeForm, count_week_offs: event.target.checked })} /> Count week-offs</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={typeForm.count_holidays} onChange={(event) => setTypeForm({ ...typeForm, count_holidays: event.target.checked })} /> Count holidays</label>
          </div>
          <Button size="sm" disabled={busy} onClick={() => void createType()}>Create leave policy</Button>
          <p className="text-xs text-muted-foreground">A policy becomes immutable once used by a balance or request. Create a new code for a changed policy.</p>
        </div>

        <div className="rounded-lg border p-4 space-y-3">
          <h3 className="font-semibold">Allocate or adjust balance</h3>
          <label className="block space-y-1 text-sm"><span>Employee</span><select className="h-9 w-full rounded-md border bg-background px-3" value={balanceForm.employee_id} onChange={(event) => setBalanceForm({ ...balanceForm, employee_id: event.target.value })}>{employees.filter((row) => row.active).map((row) => <option key={row.id} value={row.id}>{row.emp_code} · {row.name}</option>)}</select></label>
          <label className="block space-y-1 text-sm"><span>Leave type</span><select className="h-9 w-full rounded-md border bg-background px-3" value={balanceForm.leave_type_id} onChange={(event) => setBalanceForm({ ...balanceForm, leave_type_id: event.target.value })}>{types.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="space-y-1 text-sm"><span>Opening</span><Input type="number" min="0" step="0.5" value={balanceForm.opening_balance} onChange={(event) => setBalanceForm({ ...balanceForm, opening_balance: Number(event.target.value) })} /></label>
            <label className="space-y-1 text-sm"><span>Accrued</span><Input type="number" min="0" step="0.5" value={balanceForm.accrued} onChange={(event) => setBalanceForm({ ...balanceForm, accrued: Number(event.target.value) })} /></label>
            <label className="space-y-1 text-sm"><span>Adjustment</span><Input type="number" step="0.5" value={balanceForm.adjusted} onChange={(event) => setBalanceForm({ ...balanceForm, adjusted: Number(event.target.value) })} /></label>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <label className="space-y-1 text-sm"><span>Accrual month</span><select className="h-9 rounded-md border bg-background px-2" value={accrualMonth} onChange={(event) => setAccrualMonth(Number(event.target.value))}>{Array.from({ length: 12 }, (_, i) => i + 1).map((month) => <option key={month} value={month}>{new Date(2000, month - 1, 1).toLocaleString("en-IN", { month: "long" })}</option>)}</select></label>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void runAccrual()}>Run monthly accrual</Button>
            <Button size="sm" variant="outline" disabled={busy || !balanceForm.employee_id || !balanceForm.leave_type_id} onClick={() => void saveBalance()}>Save balance</Button>
            <Button size="sm" variant="outline" disabled={busy} onClick={() => void carryForward()}>Carry forward from {year - 1}</Button>
          </div>
          <p className="text-xs text-muted-foreground">Annual-upfront policies remain HR-allocated. Monthly policies accrue 1/12 per eligible month; monthly-prorated policies prorate by eligible calendar days. Each employee/type/month is recorded once in the accrual ledger.</p>
        </div>
      </div> : null}

      <div className="rounded-lg border p-4 space-y-3">
        <h3 className="font-semibold">Leave requests and approvals</h3>
        {loading ? <p className="text-sm text-muted-foreground">Loading requests…</p> : requests.length ? <div className="overflow-x-auto"><table className="w-full min-w-[850px] text-sm"><thead><tr className="border-b text-left text-muted-foreground">{["Employee", "Leave type", "Dates", "Days", "Reason", "Status", "Approver / action"].map((label) => <th key={label} className="py-2 pr-3">{label}</th>)}</tr></thead><tbody>{requests.map((request) => <tr key={request.id} className="border-b last:border-0"><td className="py-2 pr-3">{canManage ? employeeName(request.employee_id) : "My request"}</td><td className="py-2 pr-3">{typeName(request.leave_type_id)}</td><td className="py-2 pr-3 whitespace-nowrap">{request.start_date}{request.end_date !== request.start_date ? " – " + request.end_date : ""}{request.half_day ? " · half day" : ""}</td><td className="py-2 pr-3 tabular-nums">{request.total_days}</td><td className="py-2 pr-3 max-w-48 truncate" title={request.reason}>{request.reason}</td><td className="py-2 pr-3 capitalize">{request.status}</td><td className="py-2 pr-3"><div className="flex flex-wrap gap-1">{canDecide(request) ? <><Button size="sm" disabled={busy} onClick={() => void decide(request, "approved")}>Approve</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => void decide(request, "rejected")}>Reject</Button></> : request.status === "pending" && request.requested_by === username ? <Button size="sm" variant="outline" disabled={busy} onClick={() => void cancel(request)}>Cancel</Button> : <span className="text-xs text-muted-foreground">{request.approver_username}</span>}</div></td></tr>)}</tbody></table></div> : <p className="text-sm text-muted-foreground">No leave requests found.</p>}
      </div>
    </section>
  );
}
