import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { FormDialog, FormField } from "@/components/form-dialog";
import { DataTable } from "@/components/data-table";
import { TableSkeleton } from "@/components/query-state";
import { BackendGap, DetailSheet, KeyValues, NumInput, QueryTable, SectionTitle, lookup, runMutation } from "@/components/erp";
import * as H from "@/lib/api/hooks";
import type * as T from "@/lib/api/types";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/_app/hr")({
  head: () => ({
    meta: [
      { title: "Employees — Minitally ERP" },
      { name: "description", content: "Shop-floor employees, skills and work-center assignments." },
      { property: "og:title", content: "Employees — Minitally ERP" },
      { property: "og:description", content: "Shop-floor employees, skills and work-center assignments." },
    ],
  }),
  component: HrPage,
});

function HrPage() {
  const { can } = useAuth();
  const canEdit = can("hr");
  const canManageEmployees = can("hr");
  const query = H.useEmployees();
  const orders = H.useProductionOrders();
  const create = H.useCreateEmployee();
  const update = H.useUpdateEmployee();
  const setStatus = H.useSetEmployeeStatus();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<T.EmployeeIn>({ name: "", employee_type: "shop_floor", department: "Production", designation: "Operator" });
  const [sel, setSel] = useState<T.EmployeeOut | null>(null);

  const load = (id: string) =>
    (orders.data ?? []).flatMap((o) => o.operations.filter((op) => op.assigned_employee_id === id && op.completed_qty < op.planned_qty)).length;

  const submit = async () => {
    if (!f.name.trim()) return;
    const saved = editingId
      ? await runMutation(update.mutateAsync({ ...f, id: editingId }), "Employee updated")
      : await runMutation(create.mutateAsync(f), "Employee created");
    if (saved) {
      setOpen(false);
      setEditingId(null);
      if (sel && editingId) setSel({ ...sel, ...f });
    }
  };

  const startNew = () => {
    setEditingId(null);
    setF({ name: "", employee_type: "shop_floor", department: "Production", designation: "Operator" });
    setOpen(true);
  };

  const startEdit = () => {
    if (!sel) return;
    setF({ name: sel.name, employee_type: sel.employee_type, department: sel.department, designation: sel.designation });
    setEditingId(sel.id);
    setOpen(true);
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Employees" description="Employee codes are assigned by the system and cannot be changed. Skills drive automatic operation assignment on production orders." />
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="employees"
        emptyTitle="No employees"
        onRowClick={setSel}
        toolbar={canEdit ? <Button size="sm" onClick={startNew}><Plus className="mr-1 h-4 w-4" /> New employee</Button> : null}
        columns={[
          { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.emp_code}</span>, searchValue: (r) => r.emp_code, sortValue: (r) => r.emp_code },
          { key: "name", header: "Name", render: (r) => r.name, searchValue: (r) => r.name, sortValue: (r) => r.name },
          { key: "type", header: "Type", render: (r) => r.employee_type === "shop_floor" ? "Shop floor" : "Staff", searchValue: (r) => r.employee_type },
          { key: "dept", header: "Department", render: (r) => r.department, searchValue: (r) => r.department },
          { key: "desig", header: "Designation", render: (r) => r.designation },
          { key: "load", header: "Open operations", className: "text-right", render: (r) => <span className="tabular-nums">{load(r.id)}</span>, sortValue: (r) => load(r.id) },
          { key: "status", header: "Availability", render: (r) => <StatusBadge status={!r.active ? "Inactive" : load(r.id) > 0 ? "Assigned" : "Available"} /> },
        ]}
      />
      <FormDialog open={open} onOpenChange={(value) => { setOpen(value); if (!value) setEditingId(null); }} title={editingId ? "Edit employee" : "New employee"} onSubmit={() => void submit()} pending={create.isPending || update.isPending}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Employee code"><p className="text-sm text-muted-foreground">Assigned automatically after saving (EMP-001, EMP-002, …).</p></FormField>
          <FormField label="Name *"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></FormField>
          <FormField label="Employee type"><select className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={f.employee_type} onChange={(e) => setF({ ...f, employee_type: e.target.value as T.EmployeeType, department: e.target.value === "shop_floor" ? "Production" : "" })}><option value="shop_floor">Shop floor</option><option value="staff">Staff</option></select></FormField>
          <FormField label="Department"><Input value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></FormField>
          <FormField label="Designation"><Input value={f.designation} onChange={(e) => setF({ ...f, designation: e.target.value })} /></FormField>

        </div>
      </FormDialog>
      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSel(null)} title={sel?.name ?? ""} description={sel?.emp_code ?? ""}>
        {sel ? (
          <>
            {canManageEmployees ? (
              <div className="mb-4 flex flex-wrap gap-2">
                <Button variant="outline" size="sm" onClick={startEdit}>Edit employee</Button>
                <Button
                  variant={sel.active ? "destructive" : "default"}
                  size="sm"
                  disabled={setStatus.isPending}
                  onClick={() => void runMutation(setStatus.mutateAsync({ id: sel.id, active: !sel.active }), sel.active ? "Employee deactivated" : "Employee reactivated").then((saved) => { if (saved) setSel(saved); })}
                >
                  {sel.active ? "Deactivate employee" : "Reactivate employee"}
                </Button>
              </div>
            ) : null}
            <EmployeeDetail emp={sel} canEdit={canEdit} />
          </>
        ) : null}
      </DetailSheet>
      <BackendGap>Shift rosters and attendance are not part of HR Foundation v1 and remain unimplemented.</BackendGap>
    </div>
  );
}

function EmployeeDetail({ emp, canEdit }: { emp: T.EmployeeOut; canEdit: boolean }) {
  const skills = H.useEmployeeSkills(emp.id);
  const add = H.useAddEmployeeSkill();
  const routings = H.useRoutings();
  const wcs = H.useWorkcenters();
  const orders = H.useProductionOrders();
  const products = H.useProducts();
  const [s, setS] = useState<T.EmployeeSkillIn>({ skill: "", level: 3, certified: false, active: true });

  const skillSet = new Set((skills.data ?? []).filter((x) => x.active).map((x) => x.skill));
  const eligible = (routings.data ?? []).flatMap((r) =>
    r.operations.filter((o) => !o.required_skill || skillSet.has(o.required_skill)).map((o) => ({ id: o.id, routing: r.name || "Routing", product: lookup(products.data, r.product_id, (p) => p.code), op: `${o.sequence} ${o.name}`, wc: lookup(wcs.data, o.workcenter_id, (w) => w.code), skill: o.required_skill || "Any" })),
  );
  const assigned = (orders.data ?? []).flatMap((o) => o.operations.filter((op) => op.assigned_employee_id === emp.id).map((op) => ({ id: op.id, order: o.order_no, wc: lookup(wcs.data, op.workcenter_id, (w) => w.code), status: op.status, prog: `${op.completed_qty}/${op.planned_qty}` })));

  return (
    <>
      <KeyValues items={[["Type", emp.employee_type === "shop_floor" ? "Shop floor" : "Staff"], ["Department", emp.department], ["Designation", emp.designation], ["Status", <StatusBadge key="s" status={emp.active ? "Active" : "Inactive"} />], ["Skills", String(skillSet.size)]]} />
      <SectionTitle>Skills</SectionTitle>
      {skills.isLoading ? <TableSkeleton rows={2} cols={3} /> : (
        <DataTable data={skills.data ?? []} rowKey={(r) => r.id} exportName={`${emp.emp_code}-skills`} emptyTitle="No skills recorded" pageSize={10}
          columns={[
            { key: "s", header: "Skill", render: (r) => r.skill },
            { key: "l", header: "Level", render: (r) => `L${r.level}`, sortValue: (r) => r.level },
            { key: "c", header: "Certified", render: (r) => (r.certified ? "Yes" : "No") },
            { key: "a", header: "Status", render: (r) => <StatusBadge status={r.active ? "Active" : "Inactive"} /> },
          ]} />
      )}
      {canEdit ? (
        <form className="grid grid-cols-[1fr_80px_auto_auto] items-end gap-2" onSubmit={(e) => { e.preventDefault(); if (s.skill) void runMutation(add.mutateAsync({ employeeId: emp.id, ...s }), "Skill added").then((r) => r && setS({ ...s, skill: "" })); }}>
          <FormField label="Add skill"><Input value={s.skill} onChange={(e) => setS({ ...s, skill: e.target.value })} placeholder="e.g. CNC" /></FormField>
          <FormField label="Level"><NumInput step="1" value={s.level} onChange={(n) => setS({ ...s, level: n })} /></FormField>
          <label className="flex h-9 items-center gap-2 text-sm"><Switch checked={s.certified} onCheckedChange={(c) => setS({ ...s, certified: c })} /> Cert.</label>
          <Button type="submit" size="sm" disabled={add.isPending}>Add</Button>
        </form>
      ) : null}
      <SectionTitle>Eligible routing operations</SectionTitle>
      <DataTable data={eligible} rowKey={(r) => r.id} exportName={`${emp.emp_code}-eligible`} emptyTitle="No routing operations match this employee's skills" pageSize={8}
        columns={[
          { key: "p", header: "Product", render: (r) => r.product },
          { key: "o", header: "Operation", render: (r) => r.op },
          { key: "w", header: "Work center", render: (r) => <span className="font-mono text-xs">{r.wc}</span> },
          { key: "s", header: "Skill", render: (r) => r.skill },
        ]} />
      <SectionTitle>Assigned production operations</SectionTitle>
      <DataTable data={assigned} rowKey={(r) => r.id} exportName={`${emp.emp_code}-assignments`} emptyTitle="Not assigned to any production order" pageSize={8}
        columns={[
          { key: "o", header: "Order", render: (r) => <span className="font-mono text-xs">{r.order}</span> },
          { key: "w", header: "Work center", render: (r) => <span className="font-mono text-xs">{r.wc}</span> },
          { key: "p", header: "Done/Plan", render: (r) => <span className="tabular-nums">{r.prog}</span> },
          { key: "s", header: "Status", render: (r) => <StatusBadge status={r.status} /> },
        ]} />
    </>
  );
}
