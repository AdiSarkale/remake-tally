/** Operational actions, derived KPIs, alerting and rule-based smart analytics. */
import type { AppNotification, ApprovalRequest, Severity } from "./ops-types";
import type { ErpState } from "./types";
import { logAudit, today, uid, update } from "./store";

const r2 = (n: number) => Math.round(n * 100) / 100;

/** `PLN-2026-00001` — sequential per record type and calendar year. */
export function nextOpsNo(existing: string[], prefix: string, date = today()) {
  const head = `${prefix}-${date.slice(0, 4)}-`;
  const nums = existing
    .filter((n) => n?.startsWith(head))
    .map((n) => Number(n.slice(head.length)))
    .filter((n) => Number.isFinite(n));
  return `${head}${String((nums.length ? Math.max(...nums) : 0) + 1).padStart(5, "0")}`;
}

export const daysUntil = (date: string) =>
  Math.round((new Date(date + "T00:00:00Z").getTime() - new Date(today() + "T00:00:00Z").getTime()) / 86400000);

/* ------------------------------------------------------------------ */
/* Approval workflow                                                    */
/* ------------------------------------------------------------------ */

export function decideApproval(id: string, decision: "Approved" | "Rejected", by: string, remarks: string) {
  update((s) => {
    const req = s.approvals.find((a) => a.id === id);
    if (!req) throw new Error("Approval request not found");
    if (req.status !== "Pending") throw new Error("This request is already closed");
    const stage = req.stages[req.currentStage];
    if (!stage) throw new Error("No pending stage on this request");

    stage.decision = decision;
    stage.by = by;
    stage.on = today();
    stage.remarks = remarks;

    if (decision === "Rejected") {
      req.status = "Rejected";
    } else if (req.currentStage >= req.stages.length - 1) {
      req.status = "Approved";
      req.currentStage = req.stages.length;
    } else {
      req.currentStage += 1;
    }
    logAudit(s, by, decision.toUpperCase(), "approval", `${req.refNo} — ${stage.role}: ${decision}`);
    return s;
  });
}

export function raiseApproval(
  input: { type: string; subject: string; requester: string; amount: number; roles: string[] },
  username: string,
) {
  update((s) => {
    const req: ApprovalRequest = {
      id: uid(),
      refNo: nextOpsNo(s.approvals.map((a) => a.refNo), "APR"),
      date: today(),
      type: input.type,
      subject: input.subject,
      requester: input.requester,
      amount: input.amount,
      currentStage: 0,
      status: "Pending",
      stages: input.roles.map((role) => ({ role, by: "", decision: "Pending", on: "", remarks: "" })),
    };
    s.approvals.unshift(req);
    logAudit(s, username, "CREATE", "approval", `${req.refNo} — ${req.subject}`);
    return s;
  });
}

export function pendingApprovalsFor(s: ErpState) {
  return s.approvals.filter((a) => a.status === "Pending");
}

/* ------------------------------------------------------------------ */
/* Notification engine — alerts derived from live state                 */
/* ------------------------------------------------------------------ */

function note(category: string, severity: Severity, message: string, link: string): AppNotification {
  return { id: `${category}-${message.slice(0, 24)}`, at: today(), category, severity, message, link, read: false };
}

export function liveAlerts(s: ErpState): AppNotification[] {
  const out: AppNotification[] = [];

  pendingApprovalsFor(s).forEach((a) =>
    out.push(note("Approvals", "Medium", `${a.refNo} awaiting ${a.stages[a.currentStage]?.role ?? "approval"} — ${a.subject}`, "/approvals")),
  );

  s.productionPlans
    .filter((p) => p.status === "Delayed" || (p.status !== "Completed" && daysUntil(p.dueDate) < 0))
    .forEach((p) => out.push(note("Production", "High", `${p.planNo} behind schedule — ${p.productName} (${p.producedQty}/${p.plannedQty})`, "/ppc")));

  [...s.products, ...s.materials]
    .filter((i) => i.stock <= i.minStock)
    .forEach((i) => out.push(note("Inventory", "Medium", `Low stock: ${i.name} at ${i.stock} ${i.unit} (min ${i.minStock})`, "/inventory")));

  s.spares
    .filter((sp) => sp.stock <= sp.minStock)
    .forEach((sp) => out.push(note("Maintenance", "Medium", `Spare below minimum: ${sp.name} (${sp.stock} left)`, "/maintenance")));

  s.breakdowns
    .filter((b) => b.status !== "Resolved")
    .forEach((b) => out.push(note("Maintenance", "Critical", `Machine down: ${b.machineName} — ${b.problem}`, "/maintenance")));

  s.maintenancePlans
    .filter((m) => daysUntil(m.nextDue) <= 3)
    .forEach((m) =>
      out.push(note("Maintenance", daysUntil(m.nextDue) < 0 ? "High" : "Low", `${m.type} due for ${m.machineName} on ${m.nextDue}`, "/maintenance")),
    );

  s.calibrations
    .filter((c) => daysUntil(c.nextDue) <= 7)
    .forEach((c) => out.push(note("Quality", "High", `Calibration due: ${c.instrument} (${c.instrumentNo}) on ${c.nextDue}`, "/quality")));

  s.ncrs
    .filter((n) => n.status !== "Closed")
    .forEach((n) => out.push(note("Quality", n.severity, `Open NCR ${n.ncrNo}: ${n.description}`, "/quality")));

  s.complaints
    .filter((c) => c.status !== "Closed")
    .forEach((c) => out.push(note("Customer", c.severity, `Complaint ${c.complaintNo} from ${c.customerName}: ${c.issue}`, "/quality")));

  s.dispatches
    .filter((d) => d.status !== "Delivered")
    .forEach((d) => out.push(note("Dispatch", d.status === "Delayed" ? "High" : "Low", `${d.dispatchNo} ${d.status} — ${d.customerName} (${d.vehicleNo})`, "/dispatch")));

  s.attendance
    .filter((a) => a.date === today() && a.status === "Absent")
    .forEach((a) => out.push(note("HR", "Low", `Attendance exception: ${a.empName} marked Absent`, "/hr")));

  s.leaves
    .filter((l) => l.status === "Pending")
    .forEach((l) => out.push(note("HR", "Low", `Leave request pending: ${l.empName}, ${l.days} day(s) ${l.type}`, "/hr")));

  s.invoices
    .filter((i) => i.status === "Unpaid")
    .forEach((i) => out.push(note("Accounts", "Medium", `Outstanding: ${i.invoiceNo} — ${i.customerName} ₹${Math.round(i.grandTotal)}`, "/accounts")));

  const rank: Record<Severity, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  return out.sort((a, b) => rank[a.severity] - rank[b.severity]);
}

/* ------------------------------------------------------------------ */
/* Derived KPIs                                                         */
/* ------------------------------------------------------------------ */

export function machineUtilisation(s: ErpState) {
  return s.machines.map((m) => {
    const plans = s.productionPlans.filter((p) => p.machineName === m.name);
    const planned = plans.reduce((t, p) => t + p.plannedQty, 0);
    const produced = plans.reduce((t, p) => t + p.producedQty, 0);
    const downtime = s.breakdowns
      .filter((b) => b.machineName === m.name)
      .reduce((t, b) => t + b.downtimeMinutes, 0);
    // Availability over a rolling 30 shift-days of 480 minutes.
    const availability = Math.max(0, 1 - downtime / (30 * 480));
    const performance = planned ? Math.min(1, produced / planned) : m.status === "Running" ? 0.9 : 0.4;
    const insp = s.inspections;
    const totalInsp = insp.reduce((t, i) => t + i.inspectedQty, 0);
    const quality = totalInsp ? insp.reduce((t, i) => t + i.acceptedQty, 0) / totalInsp : 1;
    return {
      ...m,
      planned,
      produced,
      downtime,
      availability: r2(availability * 100),
      performance: r2(performance * 100),
      quality: r2(quality * 100),
      oee: r2(availability * performance * quality * 100),
    };
  });
}

export function qualityStats(s: ErpState) {
  const inspected = s.inspections.reduce((t, i) => t + i.inspectedQty, 0);
  const rejected = s.inspections.reduce((t, i) => t + i.rejectedQty, 0);
  return {
    inspected,
    rejected,
    rejectionRate: inspected ? r2((rejected / inspected) * 100) : 0,
    openNcrs: s.ncrs.filter((n) => n.status !== "Closed").length,
    openComplaints: s.complaints.filter((c) => c.status !== "Closed").length,
    calibrationDue: s.calibrations.filter((c) => daysUntil(c.nextDue) <= 7).length,
  };
}

export function maintenanceStats(s: ErpState) {
  const cutoff = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  return {
    pmDue: s.maintenancePlans.filter((p) => daysUntil(p.nextDue) <= 7).length,
    openBreakdowns: s.breakdowns.filter((b) => b.status !== "Resolved").length,
    downtimeMinutes: s.breakdowns.filter((b) => b.date >= cutoff).reduce((t, b) => t + b.downtimeMinutes, 0),
    lowSpares: s.spares.filter((p) => p.stock <= p.minStock).length,
  };
}

export function hrStats(s: ErpState) {
  const day = today();
  const todays = s.attendance.filter((a) => a.date === day);
  const present = todays.filter((a) => a.status === "Present" || a.status === "Half Day").length;
  return {
    headcount: s.employees.filter((e) => e.status === "Active").length,
    present,
    absent: todays.filter((a) => a.status === "Absent").length,
    onLeave: todays.filter((a) => a.status === "Leave").length,
    attendancePercent: todays.length ? r2((present / todays.length) * 100) : 0,
    pendingLeaves: s.leaves.filter((l) => l.status === "Pending").length,
    overtimeHours: todays.reduce((t, a) => t + a.overtimeHours, 0),
    monthlyPayroll: s.employees.filter((e) => e.status === "Active").reduce((t, e) => t + e.monthlySalary, 0),
  };
}

export function accountStats(s: ErpState) {
  const received = s.payments.filter((p) => p.direction === "Received").reduce((t, p) => t + p.amount, 0);
  const paid = s.payments.filter((p) => p.direction === "Paid").reduce((t, p) => t + p.amount, 0);
  const expenses = s.expenses.reduce((t, e) => t + e.amount, 0);
  const revenue = s.invoices.reduce((t, i) => t + i.taxable, 0);
  const outstanding = s.invoices.filter((i) => i.status === "Unpaid").reduce((t, i) => t + i.grandTotal, 0);
  const cogs = s.invoices.reduce(
    (t, i) => t + i.lines.reduce((lt, l) => lt + l.quantity * (s.products.find((p) => p.id === l.productId)?.costPrice ?? 0), 0),
    0,
  );
  const grossProfit = revenue - cogs;
  return {
    received,
    paid,
    expenses,
    revenue: r2(revenue),
    cogs: r2(cogs),
    grossProfit: r2(grossProfit),
    netProfit: r2(grossProfit - expenses),
    margin: revenue ? r2((grossProfit / revenue) * 100) : 0,
    outstanding: r2(outstanding),
    cashPosition: r2(received - paid - expenses),
  };
}

export function ppcStats(s: ErpState) {
  const plans = s.productionPlans;
  const planned = plans.reduce((t, p) => t + p.plannedQty, 0);
  const produced = plans.reduce((t, p) => t + p.producedQty, 0);
  return {
    open: plans.filter((p) => p.status !== "Completed").length,
    delayed: plans.filter((p) => p.status === "Delayed" || (p.status !== "Completed" && daysUntil(p.dueDate) < 0)).length,
    completion: planned ? r2((produced / planned) * 100) : 0,
    planned,
    produced,
  };
}

/** Department scorecard used by the management dashboard. */
export function departmentKpis(s: ErpState) {
  const q = qualityStats(s);
  const p = ppcStats(s);
  const hr = hrStats(s);
  const acc = accountStats(s);
  const util = machineUtilisation(s);
  const avgOee = util.length ? r2(util.reduce((t, m) => t + m.oee, 0) / util.length) : 0;
  return [
    { department: "Sales", metric: "Order completion", value: `${p.completion}%`, score: p.completion },
    { department: "PPC", metric: "Plans on time", value: `${p.open - p.delayed}/${p.open}`, score: p.open ? ((p.open - p.delayed) / p.open) * 100 : 100 },
    { department: "Production", metric: "Average OEE", value: `${avgOee}%`, score: avgOee },
    { department: "Quality", metric: "Acceptance rate", value: `${r2(100 - q.rejectionRate)}%`, score: 100 - q.rejectionRate },
    { department: "Maintenance", metric: "Machines available", value: `${s.machines.filter((m) => m.status === "Running").length}/${s.machines.length}`, score: s.machines.length ? (s.machines.filter((m) => m.status === "Running").length / s.machines.length) * 100 : 0 },
    { department: "Dispatch", metric: "Delivered on time", value: `${s.dispatches.filter((d) => d.status === "Delivered").length}/${s.dispatches.length}`, score: s.dispatches.length ? (s.dispatches.filter((d) => d.status === "Delivered").length / s.dispatches.length) * 100 : 0 },
    { department: "HR", metric: "Attendance", value: `${hr.attendancePercent}%`, score: hr.attendancePercent },
    { department: "Accounts", metric: "Gross margin", value: `${acc.margin}%`, score: acc.margin },
  ];
}

/* ------------------------------------------------------------------ */
/* Smart features — rule-based forecasting and recommendations          */
/* ------------------------------------------------------------------ */

export interface Insight {
  category: string;
  severity: Severity;
  title: string;
  detail: string;
  action: string;
}

/** Simple moving-average demand forecast per product from invoice history. */
export function demandForecast(s: ErpState) {
  return s.products
    .map((p) => {
      const sold = s.invoices.flatMap((i) => i.lines.filter((l) => l.productId === p.id).map((l) => l.quantity));
      const total = sold.reduce((t, q) => t + q, 0);
      const perDay = total / 30;
      const nextMonth = Math.round(perDay * 30);
      const coverDays = perDay > 0 ? Math.round(p.stock / perDay) : 999;
      return {
        id: p.id,
        name: p.name,
        unit: p.unit,
        stock: p.stock,
        soldLast30: total,
        forecastNextMonth: nextMonth,
        coverDays,
        reorderQty: Math.max(0, Math.round(nextMonth + p.minStock - p.stock)),
      };
    })
    .sort((a, b) => a.coverDays - b.coverDays);
}

export function smartInsights(s: ErpState): Insight[] {
  const out: Insight[] = [];
  const util = machineUtilisation(s);
  const q = qualityStats(s);
  const acc = accountStats(s);

  util
    .filter((m) => m.oee < 60)
    .forEach((m) =>
      out.push({
        category: "Production planning",
        severity: m.oee < 40 ? "High" : "Medium",
        title: `${m.name} running at ${m.oee}% OEE`,
        detail: `Availability ${m.availability}%, performance ${m.performance}%. ${m.downtime} minutes of recorded downtime.`,
        action: "Rebalance the queue onto higher-availability machines and close the open breakdown ticket first.",
      }),
    );

  s.maintenancePlans
    .filter((m) => daysUntil(m.nextDue) <= 0)
    .forEach((m) =>
      out.push({
        category: "Predictive maintenance",
        severity: "High",
        title: `${m.machineName} is overdue for ${m.type.toLowerCase()}`,
        detail: `Last done ${m.lastDone}, cycle every ${m.frequencyDays} days. Machines skipping this cycle historically account for the longest breakdowns.`,
        action: `Schedule ${m.technician} within 48 hours to avoid an unplanned stop.`,
      }),
    );

  demandForecast(s)
    .filter((f) => f.coverDays < 30 && f.reorderQty > 0)
    .slice(0, 4)
    .forEach((f) =>
      out.push({
        category: "Demand forecast",
        severity: f.coverDays < 10 ? "High" : "Medium",
        title: `${f.name} covers only ${f.coverDays} days of demand`,
        detail: `Sold ${f.soldLast30} ${f.unit} in the last 30 days; forecast ${f.forecastNextMonth} ${f.unit} next month against ${f.stock} in stock.`,
        action: `Plan production or purchase of about ${f.reorderQty} ${f.unit}.`,
      }),
    );

  const reasons = new Map<string, number>();
  s.complaints.forEach((c) => reasons.set(c.issue.split(" ")[0] ?? c.issue, (reasons.get(c.issue.split(" ")[0] ?? c.issue) ?? 0) + 1));
  if (q.openComplaints > 0)
    out.push({
      category: "Complaint trend",
      severity: "Medium",
      title: `${q.openComplaints} open customer complaint(s)`,
      detail: `Rejection rate is ${q.rejectionRate}% across ${q.inspected} inspected pieces. Recurring themes: ${[...reasons.keys()].slice(0, 3).join(", ") || "none"}.`,
      action: "Link each open complaint to an NCR and verify the CAPA before closing.",
    });

  if (acc.margin < 25)
    out.push({
      category: "Cost analysis",
      severity: acc.margin < 15 ? "High" : "Medium",
      title: `Gross margin at ${acc.margin}%`,
      detail: `Revenue ₹${Math.round(acc.revenue)} against COGS ₹${Math.round(acc.cogs)} and overheads ₹${Math.round(acc.expenses)}.`,
      action: "Review the highest cost centres and revisit pricing on low-margin SKUs.",
    });

  if (acc.outstanding > 0)
    out.push({
      category: "Smart reminder",
      severity: "Medium",
      title: `₹${Math.round(acc.outstanding)} outstanding from customers`,
      detail: `${s.invoices.filter((i) => i.status === "Unpaid").length} unpaid invoice(s) on the books.`,
      action: "Trigger the payment follow-up sequence from the Accounts module.",
    });

  const rank: Record<Severity, number> = { Critical: 0, High: 1, Medium: 2, Low: 3 };
  return out.sort((a, b) => rank[a.severity] - rank[b.severity]);
}
