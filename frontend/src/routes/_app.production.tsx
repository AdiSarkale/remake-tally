import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ClipboardCheck, Factory, Plus, Recycle, UserCheck, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { FormDialog, FormField } from "@/components/form-dialog";
import { ErrorState, TableSkeleton } from "@/components/query-state";
import { DetailSheet, KeyValues, ModuleTabs, NumInput, QueryTable, SectionTitle, SelectField, lookup, runMutation } from "@/components/erp";
import { BomTab, RoutingTab, WorkcenterTab } from "@/components/manufacturing-masters";
import * as H from "@/lib/api/hooks";
import type * as T from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { formatDate, formatNumber, todayIso } from "@/lib/format";

export const Route = createFileRoute("/_app/production")({
  head: () => ({
    meta: [
      { title: "Production — Minitally ERP" },
      { name: "description", content: "BOMs, routings, work centers, production orders, execution, batches and scrap." },
      { property: "og:title", content: "Production — Minitally ERP" },
      { property: "og:description", content: "BOMs, routings, work centers, production orders, execution, batches and scrap." },
    ],
  }),
  component: ProductionPage,
});

const FLOW = ["Material", "BOM", "Routing", "Work Center", "Employee", "Production Order", "Allocation", "Production", "FG / SFG", "Scrap"];
const SHIFTS = ["A", "B", "C", "General"];
const QUALITY: T.QualityStatus[] = ["Pending", "Accepted", "Rejected", "Accepted with Deviation"];

function ProductionPage() {
  const { can } = useAuth();
  const canRun = can("production");
  const canMaster = can("masters") || can("production");
  return (
    <div className="space-y-5">
      <PageHeader title="Production" description="Plan, assign and execute manufacturing against BOMs and routings." />
      <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
        {FLOW.map((s, i) => (
          <span key={s} className="flex items-center gap-1">
            <span className="rounded border bg-card px-2 py-0.5 font-medium text-foreground">{s}</span>
            {i < FLOW.length - 1 ? <span aria-hidden>→</span> : null}
          </span>
        ))}
      </div>
      <ModuleTabs
        defaultValue="orders"
        tabs={[
          { value: "orders", label: "Production Orders", content: <OrdersTab canEdit={canRun} /> },
          { value: "entries", label: "Execution & Batches", content: <EntriesTab canEdit={canRun} /> },
          { value: "scrap", label: "Scrap", content: <ScrapTab canEdit={can("scrap") || canRun} /> },
          { value: "bom", label: "BOM", content: <BomTab canEdit={canMaster} /> },
          { value: "routing", label: "Routings", content: <RoutingTab canEdit={canMaster} /> },
          { value: "wc", label: "Work Centers", content: <WorkcenterTab canEdit={canMaster} /> },
          { value: "report", label: "Report", content: <ReportTab /> },
        ]}
      />
    </div>
  );
}

// ---------------- Orders ----------------
function OrdersTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useProductionOrders();
  const products = H.useProducts();
  const routings = H.useRoutings();
  const wcs = H.useWorkcenters();
  const employees = H.useEmployees();
  const boms = H.useBoms();
  const materials = H.useMaterials();
  const create = H.useCreateProductionOrder();
  const assign = H.useAssignOperation();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<T.ProductionOrderIn>({ order_date: todayIso(), product_id: "", quantity: 1, due_date: null, routing_id: null, remarks: "" });
  const [selId, setSelId] = useState<string | null>(null);
  const sel = query.data?.find((o) => o.id === selId) ?? null;
  const [entryFor, setEntryFor] = useState<{ order: T.ProductionOrderOut; op: T.ProductionOrderOperationOut } | null>(null);

  const routingOps = useMemo(() => {
    const m = new Map<string, T.RoutingOperationOut>();
    (routings.data ?? []).forEach((r) => r.operations.forEach((o) => m.set(o.id, o)));
    return m;
  }, [routings.data]);

  const submit = async () => {
    if (!f.product_id || f.quantity <= 0) return;
    const r = await runMutation(create.mutateAsync(f), "Production order created — operations auto-assigned");
    if (r) {
      setOpen(false);
      setSelId(r.id);
    }
  };

  const allocation = sel ? (boms.data ?? []).find((b) => b.product_id === sel.product_id && b.active) : undefined;

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="production-orders"
        emptyTitle="No production orders"
        onRowClick={(r) => setSelId(r.id)}
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New production order</Button> : null}
        columns={[
          { key: "no", header: "Order #", render: (r) => <span className="font-mono text-xs">{r.order_no}</span>, sortValue: (r) => r.order_no, searchValue: (r) => r.order_no },
          { key: "date", header: "Date", render: (r) => formatDate(r.order_date), sortValue: (r) => r.order_date },
          { key: "prod", header: "Product", render: (r) => lookup(products.data, r.product_id, (p) => p.name), searchValue: (r) => lookup(products.data, r.product_id, (p) => p.code + p.name) },
          { key: "qty", header: "Qty", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.quantity, 2)}</span> },
          {
            key: "prog",
            header: "Progress",
            render: (r) => {
              const last = [...r.operations].sort((a, b) => b.sequence - a.sequence)[0];
              const pct = last && last.planned_qty ? Math.round((last.completed_qty / last.planned_qty) * 100) : 0;
              return (
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-20 overflow-hidden rounded bg-muted"><div className="h-full bg-primary" style={{ width: `${Math.min(100, pct)}%` }} /></div>
                  <span className="text-xs tabular-nums">{pct}%</span>
                </div>
              );
            },
          },
          { key: "due", header: "Due", render: (r) => formatDate(r.due_date), hideable: true },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} />, sortValue: (r) => r.status, searchValue: (r) => r.status },
        ]}
      />

      <FormDialog open={open} onOpenChange={setOpen} title="New production order" description="Operations are generated from the routing and auto-assigned to skilled employees." onSubmit={() => void submit()} pending={create.isPending}>
        <FormField label="Product *">
          <SelectField value={f.product_id} onChange={(v) => setF({ ...f, product_id: v, routing_id: null })} options={(products.data ?? []).map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` }))} />
        </FormField>
        <FormField label="Routing">
          <SelectField allowNone placeholder="Active routing (auto)" value={f.routing_id ?? ""} onChange={(v) => setF({ ...f, routing_id: v || null })}
            options={(routings.data ?? []).filter((r) => r.product_id === f.product_id).map((r) => ({ value: r.id, label: `${r.name || "Routing"} v${r.version}` }))} />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Quantity *"><NumInput value={f.quantity} onChange={(n) => setF({ ...f, quantity: n })} /></FormField>
          <FormField label="Order date"><Input type="date" value={f.order_date} onChange={(e) => setF({ ...f, order_date: e.target.value })} /></FormField>
          <FormField label="Due date"><Input type="date" value={f.due_date ?? ""} onChange={(e) => setF({ ...f, due_date: e.target.value || null })} /></FormField>
        </div>
        <FormField label="Remarks"><Input value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></FormField>
      </FormDialog>

      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSelId(null)} title={sel?.order_no ?? ""} description={sel ? lookup(products.data, sel.product_id, (p) => `${p.code} — ${p.name}`) : ""}>
        {sel ? (
          <>
            <KeyValues items={[
              ["Status", <StatusBadge key="s" status={sel.status} />],
              ["Quantity", formatNumber(sel.quantity, 2)],
              ["Order date", formatDate(sel.order_date)],
              ["Due", formatDate(sel.due_date)],
              ["Routing", lookup(routings.data, sel.routing_id, (r) => `${r.name || "Routing"} v${r.version}`)],
              ["Remarks", sel.remarks || "—"],
            ]} />

            <SectionTitle>Material allocation (from active BOM)</SectionTitle>
            {allocation ? (
              <div className="rounded-md border">
                <Table>
                  <TableHeader><TableRow><TableHead>Material</TableHead><TableHead className="text-right">Required</TableHead><TableHead className="text-right">Available</TableHead><TableHead>Status</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {allocation.lines.map((l) => {
                      const m = materials.data?.find((x) => x.id === l.material_id);
                      const req = l.quantity * sel.quantity;
                      return (
                        <TableRow key={l.id}>
                          <TableCell>{m?.name ?? l.material_id}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatNumber(req, 3)} {m?.unit}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatNumber(m?.stock, 3)}</TableCell>
                          <TableCell><StatusBadge status={(m?.stock ?? 0) >= req ? "Available" : "Shortage"} /></TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-destructive">No active BOM for this product — production entry will be rejected by the backend.</p>
            )}

            <SectionTitle>Operations & employee assignment</SectionTitle>
            <div className="rounded-md border">
              <Table>
                <TableHeader><TableRow><TableHead>Seq</TableHead><TableHead>Operation</TableHead><TableHead>Work center</TableHead><TableHead>Employee</TableHead><TableHead className="text-right">Done / Plan</TableHead><TableHead /></TableRow></TableHeader>
                <TableBody>
                  {[...sel.operations].sort((a, b) => a.sequence - b.sequence).map((op) => {
                    const rop = routingOps.get(op.operation_id);
                    return (
                      <TableRow key={op.id}>
                        <TableCell className="tabular-nums">{op.sequence}</TableCell>
                        <TableCell>
                          {rop?.name ?? "—"}
                          <div className="text-xs text-muted-foreground">Skill: {rop?.required_skill || "Any"}</div>
                        </TableCell>
                        <TableCell className="font-mono text-xs">{lookup(wcs.data, op.workcenter_id, (w) => w.code)}</TableCell>
                        <TableCell className="min-w-44">
                          {canEdit ? (
                            <SelectField
                              value={op.assigned_employee_id ?? ""}
                              placeholder="Unassigned"
                              onChange={(v) => v && void runMutation(assign.mutateAsync({ orderId: sel.id, operationRowId: op.id, employee_id: v }), "Employee assigned (manual override)")}
                              options={(employees.data ?? []).filter((e) => e.active).map((e) => ({ value: e.id, label: `${e.emp_code} — ${e.name}` }))}
                            />
                          ) : (
                            lookup(employees.data, op.assigned_employee_id, (e) => e.emp_code)
                          )}
                          <div className="mt-1"><StatusBadge status={op.status} /></div>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{formatNumber(op.completed_qty, 2)} / {formatNumber(op.planned_qty, 2)}</TableCell>
                        <TableCell className="text-right">
                          {canEdit ? (
                            <div className="flex flex-col items-end gap-1">
                              <Button size="sm" variant="ghost" className="h-7" title="Auto-assign by skill" onClick={() => void runMutation(assign.mutateAsync({ orderId: sel.id, operationRowId: op.id, employee_id: null }), "Auto-assigned by routing skill")}>
                                <Wand2 className="mr-1 h-3.5 w-3.5" /> Auto
                              </Button>
                              {op.assigned_employee_id && op.completed_qty < op.planned_qty ? (
                                <Button size="sm" className="h-7" onClick={() => setEntryFor({ order: sel, op })}>
                                  <Factory className="mr-1 h-3.5 w-3.5" /> Record
                                </Button>
                              ) : null}
                            </div>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </>
        ) : null}
      </DetailSheet>

      {entryFor ? <ProductionEntryDialog preset={entryFor} onClose={() => setEntryFor(null)} /> : null}
    </>
  );
}

// ---------------- Production entry dialog ----------------
function ProductionEntryDialog({ preset, onClose }: { preset: { order: T.ProductionOrderOut; op: T.ProductionOrderOperationOut } | null; onClose: () => void }) {
  const products = H.useProducts();
  const employees = H.useEmployees();
  const wcs = H.useWorkcenters();
  const boms = H.useBoms();
  const materials = H.useMaterials();
  const scrapTypes = H.useScrapTypes();
  const create = H.useCreateProduction();
  const [f, setF] = useState<T.ProductionIn>({
    entry_date: todayIso(),
    product_id: preset?.order.product_id ?? "",
    quantity: preset ? Math.max(0, preset.op.planned_qty - preset.op.completed_qty) : 1,
    machine: "",
    workcenter_id: preset?.op.workcenter_id ?? null,
    routing_id: preset?.order.routing_id ?? null,
    operation_id: preset?.op.id ?? null,
    production_order_id: preset?.order.id ?? null,
    employee_id: preset?.op.assigned_employee_id ?? null,
    operator: "",
    shift: "A",
    remarks: "",
    consumption: [],
    scrap_type_id: null,
  });
  const bom = (boms.data ?? []).find((b) => b.product_id === f.product_id && b.active);
  const [actual, setActual] = useState<Record<string, number>>({});

  const submit = async () => {
    if (!f.product_id || f.quantity <= 0) return;
    const emp = employees.data?.find((e) => e.id === f.employee_id);
    const wc = wcs.data?.find((w) => w.id === f.workcenter_id);
    const consumption = bom && Object.keys(actual).length > 0 ? bom.lines.map((l) => ({ material_id: l.material_id, quantity: actual[l.material_id] ?? l.quantity * f.quantity })) : [];
    const r = await runMutation(
      create.mutateAsync({ ...f, operator: f.operator || emp?.name || "", machine: f.machine || wc?.code || "", consumption }),
      "Production recorded — FG stock increased, materials consumed",
    );
    if (r) onClose();
  };

  return (
    <FormDialog open onOpenChange={(o) => !o && onClose()} title={preset ? `Record production · ${preset.order.order_no}` : "Record production"} description="Backend creates the batch number, consumes BOM materials and posts finished goods." wide onSubmit={() => void submit()} pending={create.isPending} submitLabel="Post production">
      <div className="grid gap-3 sm:grid-cols-3">
        <FormField label="Product *" className="space-y-1.5 sm:col-span-2">
          <SelectField value={f.product_id} onChange={(v) => { setF({ ...f, product_id: v }); setActual({}); }} options={(products.data ?? []).map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` }))} />
        </FormField>
        <FormField label="Good qty *"><NumInput value={f.quantity} onChange={(n) => setF({ ...f, quantity: n })} /></FormField>
        <FormField label="Date"><Input type="date" value={f.entry_date} onChange={(e) => setF({ ...f, entry_date: e.target.value })} /></FormField>
        <FormField label="Shift"><SelectField value={f.shift} onChange={(v) => setF({ ...f, shift: v })} options={SHIFTS.map((s) => ({ value: s, label: s }))} /></FormField>
        <FormField label="Work center">
          <SelectField allowNone value={f.workcenter_id ?? ""} onChange={(v) => setF({ ...f, workcenter_id: v || null })} options={(wcs.data ?? []).map((w) => ({ value: w.id, label: `${w.code} (${w.status})` }))} />
        </FormField>
        <FormField label="Employee">
          <SelectField allowNone value={f.employee_id ?? ""} onChange={(v) => setF({ ...f, employee_id: v || null })} options={(employees.data ?? []).map((e) => ({ value: e.id, label: `${e.emp_code} — ${e.name}` }))} />
        </FormField>
        <FormField label="Machine"><Input value={f.machine} onChange={(e) => setF({ ...f, machine: e.target.value })} placeholder="Defaults to work center" /></FormField>
        <FormField label="Scrap type">
          <SelectField allowNone value={f.scrap_type_id ?? ""} onChange={(v) => setF({ ...f, scrap_type_id: v || null })} options={(scrapTypes.data ?? []).map((s) => ({ value: s.id, label: s.name }))} />
        </FormField>
      </div>
      <SectionTitle>Material consumption</SectionTitle>
      {bom ? (
        <div className="space-y-2">
          {bom.lines.map((l) => {
            const m = materials.data?.find((x) => x.id === l.material_id);
            const planned = l.quantity * f.quantity;
            return (
              <div key={l.id} className="grid grid-cols-[1fr_110px_120px] items-center gap-2 text-sm">
                <span>{m?.name ?? l.material_id} <span className="text-xs text-muted-foreground">stock {formatNumber(m?.stock, 2)}</span></span>
                <span className="text-right tabular-nums text-muted-foreground">plan {formatNumber(planned, 3)}</span>
                <NumInput value={actual[l.material_id] ?? planned} onChange={(n) => setActual({ ...actual, [l.material_id]: n })} />
              </div>
            );
          })}
          <p className="text-xs text-muted-foreground">Actual consumption above plan is posted as process scrap.</p>
        </div>
      ) : (
        <p className="text-sm text-destructive">No active BOM for this product.</p>
      )}
      <FormField label="Remarks"><Input value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></FormField>
    </FormDialog>
  );
}

// ---------------- Entries ----------------
function EntriesTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useProductionEntries();
  const products = H.useProducts();
  const employees = H.useEmployees();
  const wcs = H.useWorkcenters();
  const orders = H.useProductionOrders();
  const materials = H.useMaterials();
  const quality = H.useUpdateProductionQuality();
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<T.ProductionOut | null>(null);
  const [q, setQ] = useState<T.ProductionQualityIn>({ status: "Accepted", accepted_qty: 0, rejected_qty: 0, remarks: "" });

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="production-entries"
        emptyTitle="No production recorded yet"
        searchPlaceholder="Search batch, product, operator…"
        onRowClick={(r) => { setSel(r); setQ({ status: r.quality_status === "Pending" ? "Accepted" : (r.quality_status as T.QualityStatus), accepted_qty: r.accepted_qty || r.quantity, rejected_qty: r.rejected_qty, remarks: r.quality_remarks }); }}
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> Record production</Button> : null}
        columns={[
          { key: "batch", header: "Batch", render: (r) => <span className="font-mono text-xs">{r.batch_no}</span>, sortValue: (r) => r.batch_no, searchValue: (r) => r.batch_no },
          { key: "date", header: "Date", render: (r) => formatDate(r.entry_date), sortValue: (r) => r.entry_date },
          { key: "prod", header: "Product", render: (r) => lookup(products.data, r.product_id, (p) => p.name), searchValue: (r) => lookup(products.data, r.product_id, (p) => p.name) },
          { key: "order", header: "Order", render: (r) => <span className="font-mono text-xs">{lookup(orders.data, r.production_order_id, (o) => o.order_no)}</span>, hideable: true },
          { key: "wc", header: "Work center", render: (r) => <span className="font-mono text-xs">{lookup(wcs.data, r.workcenter_id, (w) => w.code)}</span> },
          { key: "emp", header: "Employee", render: (r) => r.employee_id ? lookup(employees.data, r.employee_id, (e) => e.name) : r.operator || "—", searchValue: (r) => r.operator },
          { key: "shift", header: "Shift", render: (r) => r.shift, hideable: true },
          { key: "qty", header: "Qty", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.quantity, 2)}</span>, sortValue: (r) => r.quantity },
          { key: "scrap", header: "Scrap", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.actual_scrap, 3)}</span> },
          { key: "qc", header: "Quality", render: (r) => <StatusBadge status={r.quality_status} />, searchValue: (r) => r.quality_status },
        ]}
      />
      {open ? <ProductionEntryDialog preset={null} onClose={() => setOpen(false)} /> : null}
      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSel(null)} title={`Batch ${sel?.batch_no ?? ""}`} description={sel ? lookup(products.data, sel.product_id, (p) => p.name) : ""}>
        {sel ? (
          <>
            <KeyValues items={[
              ["Quantity", formatNumber(sel.quantity, 2)],
              ["Date / shift", `${formatDate(sel.entry_date)} · ${sel.shift}`],
              ["Work center", lookup(wcs.data, sel.workcenter_id, (w) => w.code)],
              ["Employee", sel.employee_id ? lookup(employees.data, sel.employee_id, (e) => e.name) : sel.operator || "—"],
              ["Actual scrap", formatNumber(sel.actual_scrap, 3)],
              ["Quality", <StatusBadge key="q" status={sel.quality_status} />],
            ]} />
            <SectionTitle>Material consumption</SectionTitle>
            <div className="rounded-md border">
              <Table>
                <TableHeader><TableRow><TableHead>Material</TableHead><TableHead className="text-right">Planned</TableHead><TableHead className="text-right">Actual</TableHead><TableHead className="text-right">Variance</TableHead></TableRow></TableHeader>
                <TableBody>
                  {sel.consumption.map((c) => (
                    <TableRow key={c.material_id}>
                      <TableCell>{lookup(materials.data, c.material_id, (m) => m.name)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatNumber(c.planned_quantity, 3)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatNumber(c.quantity, 3)}</TableCell>
                      <TableCell className={c.variance > 0 ? "text-right tabular-nums text-destructive" : "text-right tabular-nums"}>{formatNumber(c.variance, 3)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {canEdit ? (
              <>
                <SectionTitle>Quality inspection</SectionTitle>
                <div className="grid gap-3 sm:grid-cols-3">
                  <FormField label="Result" className="space-y-1.5 sm:col-span-3"><SelectField value={q.status} onChange={(v) => setQ({ ...q, status: v as T.QualityStatus })} options={QUALITY.map((s) => ({ value: s, label: s }))} /></FormField>
                  <FormField label="Accepted"><NumInput value={q.accepted_qty} onChange={(n) => setQ({ ...q, accepted_qty: n })} /></FormField>
                  <FormField label="Rejected"><NumInput value={q.rejected_qty} onChange={(n) => setQ({ ...q, rejected_qty: n })} /></FormField>
                  <FormField label="Remarks"><Input value={q.remarks} onChange={(e) => setQ({ ...q, remarks: e.target.value })} /></FormField>
                </div>
                <Button size="sm" disabled={quality.isPending} onClick={() => void runMutation(quality.mutateAsync({ id: sel.id, ...q }), "Quality recorded").then((r) => r && setSel(r))}>
                  <ClipboardCheck className="mr-1 h-4 w-4" /> Save inspection
                </Button>
              </>
            ) : null}
          </>
        ) : null}
      </DetailSheet>
    </>
  );
}

// ---------------- Scrap ----------------
function ScrapTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useScrap();
  const products = H.useProducts();
  const scrapTypes = H.useScrapTypes();
  const entries = H.useProductionEntries();
  const create = H.useCreateScrap();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<T.ScrapIn>({ entry_date: todayIso(), product_id: "", batch_no: "", scrap_type_id: "", quantity: 0, reason: "", remarks: "" });
  const submit = async () => {
    if (!f.product_id || !f.scrap_type_id || f.quantity <= 0 || !f.reason) return;
    if (await runMutation(create.mutateAsync(f), "Scrap recorded — scrap stock updated")) setOpen(false);
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="scrap"
        emptyTitle="No scrap recorded"
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Recycle className="mr-1 h-4 w-4" /> Record scrap</Button> : null}
        columns={[
          { key: "date", header: "Date", render: (r) => formatDate(r.entry_date), sortValue: (r) => r.entry_date },
          { key: "batch", header: "Batch", render: (r) => <span className="font-mono text-xs">{r.batch_no || "—"}</span>, searchValue: (r) => r.batch_no },
          { key: "prod", header: "Product", render: (r) => lookup(products.data, r.product_id, (p) => p.name), searchValue: (r) => lookup(products.data, r.product_id, (p) => p.name) },
          { key: "type", header: "Scrap type", render: (r) => lookup(scrapTypes.data, r.scrap_type_id, (s) => s.name) },
          { key: "qty", header: "Qty", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.quantity, 3)}</span>, sortValue: (r) => r.quantity },
          { key: "reason", header: "Reason", render: (r) => r.reason, searchValue: (r) => r.reason },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="Record scrap" onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Batch">
            <SelectField allowNone value={f.batch_no} onChange={(v) => { const e = entries.data?.find((x) => x.batch_no === v); setF({ ...f, batch_no: v, product_id: e?.product_id ?? f.product_id }); }}
              options={(entries.data ?? []).map((e) => ({ value: e.batch_no, label: e.batch_no }))} />
          </FormField>
          <FormField label="Date"><Input type="date" value={f.entry_date} onChange={(e) => setF({ ...f, entry_date: e.target.value })} /></FormField>
          <FormField label="Product *" className="space-y-1.5 sm:col-span-2"><SelectField value={f.product_id} onChange={(v) => setF({ ...f, product_id: v })} options={(products.data ?? []).map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` }))} /></FormField>
          <FormField label="Scrap type *"><SelectField value={f.scrap_type_id} onChange={(v) => setF({ ...f, scrap_type_id: v })} options={(scrapTypes.data ?? []).map((s) => ({ value: s.id, label: s.name }))} /></FormField>
          <FormField label="Quantity *"><NumInput value={f.quantity} onChange={(n) => setF({ ...f, quantity: n })} /></FormField>
          <FormField label="Reason *"><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></FormField>
          <FormField label="Remarks"><Input value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} /></FormField>
        </div>
      </FormDialog>
    </>
  );
}

// ---------------- Report ----------------
function ReportTab() {
  const q = H.useManufacturingReport();
  const wcs = H.useWorkcenters();
  if (q.isLoading) return <TableSkeleton rows={3} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  const d = q.data;
  if (!d) return null;
  const cards: [string, number][] = [
    ["Produced", d.production_qty],
    ["Scrap", d.scrap_qty],
    ["Planned material", d.planned_material_qty],
    ["Actual material", d.actual_material_qty],
    ["Material variance", d.material_variance],
  ];
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {cards.map(([k, v]) => (
          <div key={k} className="rounded-md border bg-card p-4">
            <div className="text-xs uppercase tracking-wide text-muted-foreground">{k}</div>
            <div className="mt-1 text-xl font-semibold tabular-nums">{formatNumber(v, 2)}</div>
          </div>
        ))}
      </div>
      <div className="rounded-md border">
        <Table>
          <TableHeader><TableRow><TableHead>Work center</TableHead>{Object.keys(d.by_workcenter[0] ?? {}).filter((k) => k !== "workcenter_id").map((k) => <TableHead key={k} className="text-right capitalize">{k.replace(/_/g, " ")}</TableHead>)}</TableRow></TableHeader>
          <TableBody>
            {d.by_workcenter.map((row, i) => {
              const id = String(row["workcenter_id"] ?? "");
              return (
                <TableRow key={i}>
                  <TableCell className="font-mono text-xs"><UserCheck className="mr-1 inline h-3 w-3 opacity-0" />{lookup(wcs.data, id === "Unassigned" ? null : id, (w) => w.code)}</TableCell>
                  {Object.entries(row).filter(([k]) => k !== "workcenter_id").map(([k, v]) => <TableCell key={k} className="text-right tabular-nums">{typeof v === "number" ? formatNumber(v, 2) : String(v)}</TableCell>)}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
