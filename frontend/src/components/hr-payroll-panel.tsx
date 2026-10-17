import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Pencil, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, BASE_URL, getToken } from "@/lib/api/client";

type Tab = "salary" | "attendance" | "calendar" | "payroll" | "settings";
type SalaryMode = "working_days" | "calendar_days" | "fixed_days";
type CalendarType = "working_day" | "holiday" | "week_off";
type AttendanceStatus = "present" | "absent" | "half_day" | "paid_leave" | "unpaid_leave" | "unmarked";
interface SalaryRow {
  employee_id: string; employee_code: string; employee_name: string; department: string; active: boolean; configured: boolean;
  annual_salary: number; basic_pct: number; hra_pct: number; da_pct: number; conveyance_monthly: number; medical_allowance_monthly: number;
  pf_pct: number; professional_tax_monthly: number; tds_monthly: number; monthly_gross: number; basic: number; hra: number; da: number;
  conveyance: number; medical_allowance: number; special_allowance: number; employee_pf: number; professional_tax: number; tds: number;
}
interface SalaryInput {
  annual_salary: number; basic_pct: number; hra_pct: number; da_pct: number; conveyance_monthly: number;
  medical_allowance_monthly: number; pf_pct: number; professional_tax_monthly: number; tds_monthly: number;
}
interface PayrollSettings { id: number; salary_count_mode: SalaryMode; monthly_salary_days: number; week_off_days: number[]; updated_at?: string | null; }
interface CalendarDay { work_date: string; day_type: CalendarType; description: string; is_override: boolean; }
interface AttendanceRow {
  id: string | null; employee_id: string; employee_code: string; employee_name: string; work_date: string; status: string;
  calendar_type: CalendarType; calendar_description: string; punch_in: string | null; punch_out: string | null; overtime_minutes: number; note: string;
}
interface PayrollItem {
  employee_id: string; employee_code: string; employee_name: string; department: string; configured: boolean; annual_salary: number;
  monthly_gross: number; basic: number; hra: number; da: number; conveyance: number; medical_allowance: number; special_allowance: number;
  employee_pf: number; professional_tax: number; tds: number; absence_deduction: number; overtime_pay: number; net_pay: number;
  present_days: number; half_days: number; absent_days: number; paid_leave_days: number; unpaid_leave_days: number; overtime_minutes: number;
}
interface PayrollPreview { year: number; month: number; salary_count_mode: SalaryMode; salary_count_days: number; items: PayrollItem[]; }
interface PayrollRun { id: string; year: number; month: number; status: string; created_by: string; created_at: string; finalized_at: string; employee_count: number; net_total: number; }
const emptySalary: SalaryInput = {
  annual_salary: 0, basic_pct: 50, hra_pct: 40, da_pct: 0, conveyance_monthly: 0,
  medical_allowance_monthly: 0, pf_pct: 12, professional_tax_monthly: 200, tds_monthly: 0,
};
const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const money = (value: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(value || 0);
const monthName = (year: number, month: number) => new Date(year, month - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
const dayLabel = (value: string) => new Date(value + "T12:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" });

export function PayrollPanel({ canEdit }: { canEdit: boolean }) {
  const today = new Date();
  const [tab, setTab] = useState<Tab>("salary");
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [employees, setEmployees] = useState<SalaryRow[]>([]);
  const [settings, setSettings] = useState<PayrollSettings | null>(null);
  const [calendar, setCalendar] = useState<CalendarDay[]>([]);
  const [attendance, setAttendance] = useState<AttendanceRow[]>([]);
  const [selectedEmployee, setSelectedEmployee] = useState("");
  const [editingEmployee, setEditingEmployee] = useState<string | null>(null);
  const [salaryForm, setSalaryForm] = useState<SalaryInput>(emptySalary);
  const [preview, setPreview] = useState<PayrollPreview | null>(null);
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const fail = (err: unknown) => {
    const message = err instanceof Error ? err.message : "Payroll operation failed";
    setError(message); toast.error(message);
  };
  const loadEmployees = useCallback(async () => {
    try {
      const rows = await api.get<SalaryRow[]>("/hr/salaries");
      setEmployees(rows);
      setSelectedEmployee((selected) => selected && rows.some((row) => row.employee_id === selected) ? selected : rows[0]?.employee_id ?? "");
    } catch (err) { fail(err); }
  }, []);
  const loadSettings = useCallback(async () => {
    try { setSettings(await api.get<PayrollSettings>("/hr/payroll/settings")); } catch (err) { fail(err); }
  }, []);
  const loadCalendar = useCallback(async () => {
    try { setCalendar(await api.get<CalendarDay[]>("/hr/calendar?year=" + year + "&month=" + month)); } catch (err) { fail(err); }
  }, [year, month]);
  const loadAttendance = useCallback(async () => {
    if (!selectedEmployee) { setAttendance([]); return; }
    try {
      setAttendance(await api.get<AttendanceRow[]>("/hr/attendance/monthly?employee_id=" + encodeURIComponent(selectedEmployee) + "&year=" + year + "&month=" + month));
    } catch (err) { fail(err); }
  }, [selectedEmployee, year, month]);
  const loadPreview = useCallback(async () => {
    try { setPreview(await api.get<PayrollPreview>("/hr/payroll/preview?year=" + year + "&month=" + month)); } catch (err) { fail(err); }
  }, [year, month]);
  const loadRuns = useCallback(async () => {
    try { setRuns(await api.get<PayrollRun[]>("/hr/payroll/runs")); } catch (err) { fail(err); }
  }, []);
  useEffect(() => { void loadEmployees(); void loadSettings(); }, [loadEmployees, loadSettings]);
  useEffect(() => {
    if (tab === "calendar") void loadCalendar();
    if (tab === "attendance") void loadAttendance();
    if (tab === "payroll") { void loadPreview(); void loadRuns(); }
  }, [tab, loadCalendar, loadAttendance, loadPreview, loadRuns]);

  const editSalary = (row: SalaryRow) => {
    setEditingEmployee(row.employee_id);
    setSalaryForm({
      annual_salary: row.annual_salary, basic_pct: row.basic_pct, hra_pct: row.hra_pct, da_pct: row.da_pct,
      conveyance_monthly: row.conveyance_monthly, medical_allowance_monthly: row.medical_allowance_monthly,
      pf_pct: row.pf_pct, professional_tax_monthly: row.professional_tax_monthly, tds_monthly: row.tds_monthly,
    });
  };
  const saveSalary = async () => {
    if (!editingEmployee) return;
    setBusy(true);
    try {
      await api.put("/hr/employees/" + editingEmployee + "/salary", salaryForm);
      toast.success("Salary structure saved"); setEditingEmployee(null); await loadEmployees();
    } catch (err) { fail(err); } finally { setBusy(false); }
  };
  const saveSettings = async () => {
    if (!settings) return;
    setBusy(true);
    try { setSettings(await api.put<PayrollSettings>("/hr/payroll/settings", settings)); toast.success("Payroll settings saved"); await loadCalendar(); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const saveCalendarDay = async (day: CalendarDay) => {
    setBusy(true);
    try {
      await api.put("/hr/calendar/" + day.work_date, { day_type: day.day_type, description: day.description });
      toast.success("Calendar updated for " + day.work_date); await loadCalendar();
    } catch (err) { fail(err); } finally { setBusy(false); }
  };
  const resetCalendarDay = async (day: CalendarDay) => {
    setBusy(true);
    try { await api.delete("/hr/calendar/" + day.work_date); toast.success("Calendar override removed"); await loadCalendar(); }
    catch (err) { fail(err); } finally { setBusy(false); }
  };
  const saveAttendance = async (row: AttendanceRow) => {
    setBusy(true);
    try {
      await api.put("/hr/attendance", {
        employee_id: row.employee_id, work_date: row.work_date, status: row.status as AttendanceStatus,
        punch_in: row.punch_in || null, punch_out: row.punch_out || null,
        overtime_minutes: Number(row.overtime_minutes) || 0, note: row.note || "",
      });
      toast.success("Attendance saved for " + row.work_date); await loadAttendance();
    } catch (err) { fail(err); } finally { setBusy(false); }
  };
  const finalizePayroll = async () => {
    setBusy(true);
    try {
      await api.post("/hr/payroll/runs/" + year + "/" + month + "/finalize");
      toast.success("Payroll finalized for " + monthName(year, month)); await Promise.all([loadPreview(), loadRuns()]);
    } catch (err) { fail(err); } finally { setBusy(false); }
  };
  const downloadSlip = async (employeeId: string, code: string) => {
    setBusy(true);
    try {
      const token = getToken();
      const response = await fetch(BASE_URL + "/api/v1/hr/payroll/slips/" + encodeURIComponent(employeeId) + "/" + year + "/" + month, {
        headers: token ? { Authorization: "Bearer " + token } : {},
      });
      if (!response.ok) {
        let detail = "Salary slip download failed";
        try { const body = await response.json() as { detail?: string }; detail = body.detail ?? detail; } catch { /* API may return a non-JSON error */ }
        throw new Error(detail);
      }
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl; anchor.download = "salary-slip-" + code + "-" + year + "-" + String(month).padStart(2, "0") + ".pdf";
      document.body.appendChild(anchor); anchor.click(); anchor.remove(); URL.revokeObjectURL(objectUrl);
    } catch (err) { fail(err); } finally { setBusy(false); }
  };
  const patchAttendance = (dateValue: string, patch: Partial<AttendanceRow>) => setAttendance((rows) => rows.map((row) => row.work_date === dateValue ? { ...row, ...patch } : row));
  const patchCalendar = (dateValue: string, patch: Partial<CalendarDay>) => setCalendar((rows) => rows.map((row) => row.work_date === dateValue ? { ...row, ...patch } : row));
  const periods = <div className="flex flex-wrap items-center gap-2">
    <label className="text-xs text-muted-foreground" htmlFor="payroll-month">Month</label>
    <select id="payroll-month" className="h-9 rounded-md border bg-background px-3 text-sm" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
      {Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{new Date(2026, i, 1).toLocaleDateString("en-IN", { month: "long" })}</option>)}
    </select>
    <label className="text-xs text-muted-foreground" htmlFor="payroll-year">Year</label>
    <Input id="payroll-year" className="w-24" type="number" value={year} onChange={(e) => setYear(Math.max(2000, Math.min(2100, Number(e.target.value) || today.getFullYear())))} />
    <span className="text-xs text-muted-foreground">{monthName(year, month)}</span>
  </div>;

  return <section className="space-y-4">
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-semibold">Payroll & Attendance</h2><p className="text-sm text-muted-foreground">Salary profiles, working calendar, daily attendance, and finalized salary slips.</p></div>
      {periods}
    </header>
    <div className="flex flex-wrap gap-2 border-b pb-3" role="tablist" aria-label="Payroll tools">
      <Button size="sm" variant={tab === "salary" ? "default" : "outline"} onClick={() => setTab("salary")}>Salary Structure</Button>
      <Button size="sm" variant={tab === "attendance" ? "default" : "outline"} onClick={() => setTab("attendance")}>Daily Attendance</Button>
      <Button size="sm" variant={tab === "calendar" ? "default" : "outline"} onClick={() => setTab("calendar")}>Calendar & Holidays</Button>
      <Button size="sm" variant={tab === "payroll" ? "default" : "outline"} onClick={() => setTab("payroll")}>Monthly Payroll</Button>
      <Button size="sm" variant={tab === "settings" ? "default" : "outline"} onClick={() => setTab("settings")}>Payroll Settings</Button>
    </div>
    {error ? <div className="rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive" role="alert">{error}<button className="ml-2 underline" onClick={() => setError("")}>Dismiss</button></div> : null}

    {tab === "salary" ? <div className="space-y-4">
      <p className="text-sm text-muted-foreground">Monthly gross equals annual salary ÷ 12. Special allowance balances gross after the configured components.</p>
      {editingEmployee ? <div className="space-y-3 rounded-lg border p-4">
        <div className="flex items-center justify-between"><h3 className="font-semibold">Edit salary — {employees.find((row) => row.employee_id === editingEmployee)?.employee_name}</h3><Button size="sm" variant="outline" onClick={() => setEditingEmployee(null)}>Cancel</Button></div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {([
            ["annual_salary", "Annual salary (₹)"], ["basic_pct", "Basic (% of gross)"], ["hra_pct", "HRA (% of basic)"], ["da_pct", "DA (% of gross)"],
            ["conveyance_monthly", "Conveyance / month (₹)"], ["medical_allowance_monthly", "Medical allowance / month (₹)"],
            ["pf_pct", "Employee PF (% of basic)"], ["professional_tax_monthly", "Professional tax / month (₹)"], ["tds_monthly", "TDS / month (₹)"],
          ] as const).map(([field, label]) => <label key={field} className="space-y-1 text-sm"><span>{label}</span><Input disabled={!canEdit || busy} type="number" min="0" step="0.01" value={salaryForm[field]} onChange={(e) => setSalaryForm((old) => ({ ...old, [field]: Number(e.target.value) }))} /></label>)}
        </div>
        <p className="text-xs text-muted-foreground">Basic + HRA + DA + fixed allowances must not exceed monthly gross. Confirm statutory PF and tax values with your payroll policy.</p>
        {canEdit ? <Button disabled={busy || salaryForm.annual_salary <= 0} onClick={() => void saveSalary()}><Save className="mr-1 size-4" />Save salary structure</Button> : null}
        <div className="grid gap-2 rounded-md bg-muted/40 p-3 text-sm sm:grid-cols-3">
          <div>Monthly gross <strong>{money(salaryForm.annual_salary / 12)}</strong></div>
          <div>Basic <strong>{money(salaryForm.annual_salary / 12 * salaryForm.basic_pct / 100)}</strong></div>
          <div>HRA <strong>{money(salaryForm.annual_salary / 12 * salaryForm.basic_pct / 100 * salaryForm.hra_pct / 100)}</strong></div>
          <div>DA <strong>{money(salaryForm.annual_salary / 12 * salaryForm.da_pct / 100)}</strong></div>
          <div>PF <strong>{money(salaryForm.annual_salary / 12 * salaryForm.basic_pct / 100 * salaryForm.pf_pct / 100)}</strong></div>
        </div>
      </div> : null}
      <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[980px] text-sm">
        <thead className="bg-muted/50 text-left"><tr>{["Employee", "Department", "Annual salary", "Monthly gross", "Basic", "HRA", "Special allowance", "PF / PT / TDS", ""].map((title) => <th key={title} className="px-3 py-2 font-medium">{title}</th>)}</tr></thead>
        <tbody>{employees.map((row) => <tr key={row.employee_id} className="border-t">
          <td className="px-3 py-2"><div className="font-medium">{row.employee_name}</div><div className="text-xs text-muted-foreground">{row.employee_code}{row.active ? "" : " · Inactive"}</div></td>
          <td className="px-3 py-2">{row.department || "—"}</td><td className="px-3 py-2 tabular-nums">{row.configured ? money(row.annual_salary) : "Not configured"}</td>
          <td className="px-3 py-2 tabular-nums">{money(row.monthly_gross)}</td><td className="px-3 py-2 tabular-nums">{money(row.basic)}</td><td className="px-3 py-2 tabular-nums">{money(row.hra)}</td>
          <td className="px-3 py-2 tabular-nums">{money(row.special_allowance)}</td><td className="px-3 py-2 tabular-nums">{money(row.employee_pf + row.professional_tax + row.tds)}</td>
          <td className="px-3 py-2">{canEdit ? <Button size="sm" variant="outline" onClick={() => editSalary(row)}><Pencil className="mr-1 size-3.5" />{row.configured ? "Edit" : "Set salary"}</Button> : null}</td>
        </tr>)}{employees.length === 0 ? <tr><td colSpan={9} className="px-3 py-8 text-center text-muted-foreground">No employees found.</td></tr> : null}</tbody>
      </table></div>
    </div> : null}

    {tab === "calendar" ? <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Edit individual holidays and week-offs here. Remove an override to restore the default rule from Payroll Settings.</p>
      <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[700px] text-sm"><thead className="bg-muted/50 text-left"><tr>{["Date", "Default / current", "Calendar classification", "Description", "Actions"].map((title) => <th key={title} className="px-3 py-2 font-medium">{title}</th>)}</tr></thead>
        <tbody>{calendar.map((day) => <tr key={day.work_date} className="border-t"><td className="px-3 py-2">{dayLabel(day.work_date)}</td><td className="px-3 py-2">{day.is_override ? "Override" : "Default"}</td>
          <td className="px-3 py-2"><select aria-label={"Classification " + day.work_date} disabled={!canEdit || busy} className="h-8 rounded-md border bg-background px-2" value={day.day_type} onChange={(e) => patchCalendar(day.work_date, { day_type: e.target.value as CalendarType })}><option value="working_day">Working day</option><option value="holiday">Holiday</option><option value="week_off">Week-off</option></select></td>
          <td className="px-3 py-2"><Input aria-label={"Description " + day.work_date} disabled={!canEdit || busy} value={day.description} placeholder="Optional note" onChange={(e) => patchCalendar(day.work_date, { description: e.target.value })} /></td>
          <td className="px-3 py-2"><div className="flex gap-1">{canEdit ? <Button size="sm" disabled={busy} onClick={() => void saveCalendarDay(day)}><Save className="mr-1 size-3.5" />Save</Button> : null}{canEdit && day.is_override ? <Button size="icon" variant="outline" aria-label="Remove calendar override" disabled={busy} onClick={() => void resetCalendarDay(day)}><Trash2 className="size-4" /></Button> : null}</div></td>
        </tr>)}</tbody></table></div>
    </div> : null}

    {tab === "attendance" ? <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3"><label className="text-sm font-medium" htmlFor="attendance-employee">Employee</label><select id="attendance-employee" className="h-9 min-w-[240px] rounded-md border bg-background px-3 text-sm" value={selectedEmployee} onChange={(e) => setSelectedEmployee(e.target.value)}>{employees.map((row) => <option key={row.employee_id} value={row.employee_id}>{row.employee_code} — {row.employee_name}</option>)}</select><Button size="sm" variant="outline" onClick={() => void loadAttendance()}>Refresh month</Button></div>
      <p className="text-sm text-muted-foreground">Attendance is tracked for each calendar day of the selected month. A holiday/week-off may still be marked present when worked.</p>
      <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[900px] text-sm"><thead className="bg-muted/50 text-left"><tr>{["Date", "Calendar", "Attendance", "OT minutes", "Note", "Action"].map((title) => <th key={title} className="px-3 py-2 font-medium">{title}</th>)}</tr></thead>
        <tbody>{attendance.map((row) => <tr key={row.work_date} className="border-t"><td className="px-3 py-2">{dayLabel(row.work_date)}</td>
          <td className="px-3 py-2">{row.calendar_type.replace("_", " ")}{row.calendar_description ? <div className="text-xs text-muted-foreground">{row.calendar_description}</div> : null}</td>
          <td className="px-3 py-2"><select disabled={!canEdit || busy} aria-label={"Attendance " + row.work_date} className="h-8 rounded-md border bg-background px-2" value={(["present", "absent", "half_day", "paid_leave", "unpaid_leave", "unmarked"] as string[]).includes(row.status) ? row.status : "unmarked"} onChange={(e) => patchAttendance(row.work_date, { status: e.target.value })}>{[["present", "Present"], ["absent", "Absent"], ["half_day", "Half day"], ["paid_leave", "Paid leave"], ["unpaid_leave", "Unpaid leave"], ["unmarked", "Unmarked"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></td>
          <td className="px-3 py-2"><Input className="w-24" type="number" min="0" max="1440" disabled={!canEdit || busy} value={row.overtime_minutes} onChange={(e) => patchAttendance(row.work_date, { overtime_minutes: Number(e.target.value) })} /></td>
          <td className="px-3 py-2"><Input className="min-w-[140px]" disabled={!canEdit || busy} value={row.note} onChange={(e) => patchAttendance(row.work_date, { note: e.target.value })} /></td>
          <td className="px-3 py-2">{canEdit ? <Button size="sm" disabled={busy} onClick={() => void saveAttendance(row)}><Save className="mr-1 size-3.5" />Save</Button> : null}</td>
        </tr>)}</tbody></table></div>
    </div> : null}

    {tab === "settings" ? settings ? <div className="max-w-3xl space-y-4 rounded-lg border p-4">
      <div><h3 className="font-semibold">Monthly salary count</h3><p className="text-sm text-muted-foreground">The divisor affects daily absence deductions and overtime calculations.</p></div>
      <label className="block space-y-1 text-sm"><span>Salary count mode</span><select className="h-9 w-full rounded-md border bg-background px-3" disabled={!canEdit || busy} value={settings.salary_count_mode} onChange={(e) => setSettings({ ...settings, salary_count_mode: e.target.value as SalaryMode })}><option value="working_days">Actual working days in month</option><option value="calendar_days">All calendar days in month</option><option value="fixed_days">Fixed monthly days</option></select></label>
      <label className="block max-w-xs space-y-1 text-sm"><span>Fixed monthly salary days (1–31)</span><Input type="number" min="1" max="31" disabled={!canEdit || busy} value={settings.monthly_salary_days} onChange={(e) => setSettings({ ...settings, monthly_salary_days: Math.max(1, Math.min(31, Number(e.target.value) || 1)) })} /></label>
      <fieldset className="space-y-2"><legend className="text-sm font-medium">Default week-offs</legend><div className="grid grid-cols-2 gap-2 sm:grid-cols-4">{weekdays.map((label, index) => <label key={label} className="flex items-center gap-2 rounded-md border p-2 text-sm"><input type="checkbox" disabled={!canEdit || busy} checked={settings.week_off_days.includes(index)} onChange={(e) => setSettings({ ...settings, week_off_days: e.target.checked ? [...settings.week_off_days, index].sort() : settings.week_off_days.filter((day) => day !== index) })} />{label}</label>)}</div></fieldset>
      <p className="text-xs text-muted-foreground">A calendar override takes precedence over the default week-offs.</p>
      {canEdit ? <Button disabled={busy} onClick={() => void saveSettings()}><Save className="mr-1 size-4" />Save payroll settings</Button> : null}
    </div> : <p className="text-sm text-muted-foreground">Loading payroll settings…</p> : null}

    {tab === "payroll" ? <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-3"><div><h3 className="font-semibold">Payroll preview — {monthName(year, month)}</h3><p className="text-sm text-muted-foreground">Divisor: {preview?.salary_count_days ?? "—"} days ({preview?.salary_count_mode.replace("_", " ") ?? "loading"}). Finalization snapshots the month’s payroll.</p></div>
        <div className="flex gap-2"><Button variant="outline" disabled={busy} onClick={() => void Promise.all([loadPreview(), loadRuns()])}>Refresh</Button>{canEdit ? <Button disabled={busy || !preview?.items.some((item) => item.configured) || runs.some((run) => run.year === year && run.month === month && run.status === "finalized")} onClick={() => void finalizePayroll()}>Finalize month</Button> : null}</div></div>
      <div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[1050px] text-sm"><thead className="bg-muted/50 text-left"><tr>{["Employee", "Annual salary", "Gross/month", "Absent", "Half days", "Unpaid leave", "Total deductions", "Overtime pay", "Net payable", "Slip"].map((title) => <th key={title} className="px-3 py-2 font-medium">{title}</th>)}</tr></thead>
        <tbody>{(preview?.items ?? []).map((item) => <tr key={item.employee_id} className="border-t"><td className="px-3 py-2"><div>{item.employee_name}</div><div className="text-xs text-muted-foreground">{item.employee_code}{item.configured ? "" : " · Salary missing"}</div></td>
          <td className="px-3 py-2 tabular-nums">{money(item.annual_salary)}</td><td className="px-3 py-2 tabular-nums">{money(item.monthly_gross)}</td><td className="px-3 py-2">{item.absent_days}</td><td className="px-3 py-2">{item.half_days}</td><td className="px-3 py-2">{item.unpaid_leave_days}</td>
          <td className="px-3 py-2 tabular-nums">{money(item.absence_deduction + item.employee_pf + item.professional_tax + item.tds)}</td><td className="px-3 py-2 tabular-nums">{money(item.overtime_pay)}</td><td className="px-3 py-2 font-semibold tabular-nums">{money(item.net_pay)}</td>
          <td className="px-3 py-2">{runs.some((run) => run.year === year && run.month === month && run.status === "finalized") ? <Button size="sm" variant="outline" disabled={busy} onClick={() => void downloadSlip(item.employee_id, item.employee_code)}><Download className="mr-1 size-3.5" />PDF</Button> : "—"}</td>
        </tr>)}{(preview?.items.length ?? 0) === 0 ? <tr><td colSpan={10} className="px-3 py-8 text-center text-muted-foreground">No active employees for this period.</td></tr> : null}</tbody>
      </table></div>
      <div className="space-y-2"><h3 className="font-semibold">Finalized payroll history</h3><div className="overflow-x-auto rounded-lg border"><table className="w-full min-w-[600px] text-sm"><thead className="bg-muted/50 text-left"><tr>{["Period", "Employees", "Net total", "Status", "Created by"].map((title) => <th key={title} className="px-3 py-2 font-medium">{title}</th>)}</tr></thead>
        <tbody>{runs.map((run) => <tr key={run.id} className="border-t"><td className="px-3 py-2">{monthName(run.year, run.month)}</td><td className="px-3 py-2">{run.employee_count}</td><td className="px-3 py-2 tabular-nums">{money(run.net_total)}</td><td className="px-3 py-2 capitalize">{run.status}</td><td className="px-3 py-2">{run.created_by}</td></tr>)}{runs.length === 0 ? <tr><td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">No finalized payroll months yet.</td></tr> : null}</tbody></table></div></div>
    </div> : null}
  </section>;
}
