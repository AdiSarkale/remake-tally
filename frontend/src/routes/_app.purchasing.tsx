import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PackageCheck, Plus, ShoppingCart, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { FormDialog, FormField } from "@/components/form-dialog";
import { DataTable } from "@/components/data-table";
import { PartyManager } from "@/components/party-manager";
import { ErrorState, TableSkeleton } from "@/components/query-state";
import {
  BackendGap,
  DetailSheet,
  KeyValues,
  ModuleTabs,
  NumInput,
  QueryTable,
  SectionTitle,
  SelectField,
  lookup,
  runMutation,
} from "@/components/erp";
import * as H from "@/lib/api/hooks";
import type * as T from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { formatCurrency, formatDate, formatNumber, todayIso } from "@/lib/format";

export const Route = createFileRoute("/_app/purchasing")({
  head: () => ({
    meta: [
      { title: "Procurement — Minitally ERP" },
      { name: "description", content: "Material requirements, purchase orders, goods receipts and suppliers." },
      { property: "og:title", content: "Procurement — Minitally ERP" },
      { property: "og:description", content: "Material requirements, purchase orders, goods receipts and suppliers." },
    ],
  }),
  component: PurchasingPage,
});

const PO_STATUSES: T.PurchaseOrderStatus[] = ["draft", "sent", "partially_received", "received"];

interface DraftLine {
  material_id: string;
  quantity: number;
  rate: number;
  gst_rate: number;
}

function docNo(prefix: string) {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${prefix}-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
}

function PurchasingPage() {
  const { can } = useAuth();
  const canEdit = can("masters") || can("inventory");
  const [poSeed, setPoSeed] = useState<DraftLine[] | null>(null);
  const [tab, setTab] = useState(0);
  return (
    <div className="space-y-5">
      <PageHeader title="Procurement" description="Requisition → Purchase order → Goods receipt → Stock" />
      <ModuleTabs
        key={tab}
        defaultValue={tab === 1 ? "orders" : "requisition"}
        tabs={[
          {
            value: "requisition",
            label: "Requisition",
            content: (
              <RequisitionTab
                onRaise={(lines) => {
                  setPoSeed(lines);
                  setTab(1);
                }}
              />
            ),
          },
          { value: "orders", label: "Purchase Orders", content: <OrdersTab canEdit={canEdit} seed={poSeed} clearSeed={() => setPoSeed(null)} /> },
          { value: "grns", label: "Goods Receipts", content: <GrnsTab /> },
          {
            value: "suppliers",
            label: "Suppliers",
            content: (
              <PartyManager
                label="Supplier"
                query={H.useSuppliers()}
                create={H.useCreateSupplier()}
                update={H.useUpdateSupplier()}
                remove={H.useDeleteSupplier()}
                canEdit={can("masters")}
              />
            ),
          },
        ]}
      />
    </div>
  );
}

// Requisition = computed from real data: open sales orders × active BOMs vs raw-material stock.
function RequisitionTab({ onRaise }: { onRaise: (lines: DraftLine[]) => void }) {
  const materials = H.useMaterials();
  const boms = H.useBoms();
  const orders = H.useSalesOrders();
  const [picked, setPicked] = useState<Record<string, boolean>>({});

  const rows = useMemo(() => {
    const demand: Record<string, number> = {};
    for (const so of orders.data ?? []) {
      if (so.status !== "Open" && so.status !== "Partially Delivered") continue;
      for (const l of so.lines) {
        const bom = (boms.data ?? []).find((b) => b.product_id === l.product_id && b.active);
        if (!bom) continue;
        const open = Math.max(0, l.quantity - l.delivered_quantity);
        for (const bl of bom.lines) demand[bl.material_id] = (demand[bl.material_id] ?? 0) + bl.quantity * open;
      }
    }
    return (materials.data ?? [])
      .map((m) => {
        const req = demand[m.id] ?? 0;
        const shortage = Math.max(0, req + m.min_stock - m.stock);
        return { ...m, required: req, shortage };
      })
      .filter((m) => m.shortage > 0)
      .sort((a, b) => b.shortage - a.shortage);
  }, [materials.data, boms.data, orders.data]);

  if (materials.isLoading || boms.isLoading || orders.isLoading) return <TableSkeleton />;
  if (materials.isError) return <ErrorState error={materials.error} />;

  const selected = rows.filter((r) => picked[r.id]);
  return (
    <div className="space-y-3">
      <BackendGap>
        the backend has no stored purchase-requisition document. This list is calculated live from open sales orders, active BOMs and
        raw-material stock/minimum levels, and converts directly into a real purchase order.
      </BackendGap>
      <DataTable
        data={rows}
        rowKey={(r) => r.id}
        exportName="material-requirements"
        emptyTitle="No shortages — stock covers open orders and minimum levels"
        toolbar={
          <Button
            size="sm"
            disabled={selected.length === 0}
            onClick={() => onRaise(selected.map((r) => ({ material_id: r.id, quantity: Math.ceil(r.shortage), rate: r.cost, gst_rate: 18 })))}
          >
            <ShoppingCart className="mr-1 h-4 w-4" /> Raise PO ({selected.length})
          </Button>
        }
        columns={[
          {
            key: "pick",
            header: "",
            className: "w-8",
            render: (r) => (
              <input
                type="checkbox"
                aria-label={`Select ${r.name}`}
                checked={picked[r.id] ?? false}
                onChange={(e) => setPicked({ ...picked, [r.id]: e.target.checked })}
              />
            ),
          },
          { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code },
          { key: "name", header: "Material", render: (r) => r.name, searchValue: (r) => r.name, sortValue: (r) => r.name },
          { key: "stock", header: "Stock", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.stock, 2)} {r.unit}</span> },
          { key: "min", header: "Min", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.min_stock, 2)}</span> },
          { key: "req", header: "SO demand", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.required, 2)}</span> },
          { key: "short", header: "Shortage", className: "text-right", render: (r) => <span className="font-semibold tabular-nums text-destructive">{formatNumber(r.shortage, 2)}</span>, sortValue: (r) => r.shortage },
        ]}
      />
    </div>
  );
}

function OrdersTab({ canEdit, seed, clearSeed }: { canEdit: boolean; seed: DraftLine[] | null; clearSeed: () => void }) {
  const query = H.usePurchaseOrders();
  const suppliers = H.useSuppliers();
  const materials = H.useMaterials();
  const warehouses = H.useWarehouses();
  const create = H.useCreatePurchaseOrder();
  const update = H.useUpdatePurchaseOrder();
  const createGrn = H.useCreateGrn();
  const [open, setOpen] = useState(seed !== null);
  const [head, setHead] = useState({ po_no: docNo("PO"), po_date: todayIso(), expected_date: "", supplier_id: "", warehouse_id: "", notes: "" });
  const [lines, setLines] = useState<DraftLine[]>(seed ?? [{ material_id: "", quantity: 1, rate: 0, gst_rate: 18 }]);
  const [selId, setSelId] = useState<string | null>(null);
  const sel = query.data?.find((p) => p.id === selId) ?? null;
  const [grnOpen, setGrnOpen] = useState(false);
  const [grn, setGrn] = useState({ grn_no: "", grn_date: todayIso(), warehouse_id: "" });
  const [grnQty, setGrnQty] = useState<Record<string, { qty: number; batch: string }>>({});

  const calc = lines.map((l) => {
    const sub = l.quantity * l.rate;
    const tax = (sub * l.gst_rate) / 100;
    return { sub, tax, total: sub + tax };
  });
  const sub_total = calc.reduce((a, c) => a + c.sub, 0);
  const gst_total = calc.reduce((a, c) => a + c.tax, 0);

  const submit = async () => {
    const valid = lines.filter((l) => l.material_id && l.quantity > 0);
    const supplier = suppliers.data?.find((s) => s.id === head.supplier_id);
    if (!supplier || valid.length === 0) return;
    const body: T.PurchaseOrderIn = {
      po_no: head.po_no,
      po_date: head.po_date,
      expected_date: head.expected_date || null,
      supplier_id: supplier.id,
      supplier_name: supplier.name,
      warehouse_id: head.warehouse_id || null,
      notes: head.notes,
      status: "draft",
      sub_total,
      gst_total,
      grand_total: sub_total + gst_total,
      lines: valid.map((l) => {
        const s = l.quantity * l.rate;
        const tax = (s * l.gst_rate) / 100;
        return {
          material_id: l.material_id,
          material_name: materials.data?.find((m) => m.id === l.material_id)?.name ?? "",
          quantity: l.quantity,
          rate: l.rate,
          gst_rate: l.gst_rate,
          received_quantity: 0,
          tax,
          total: s + tax,
        };
      }),
    };
    const r = await runMutation(create.mutateAsync(body), `Purchase order ${head.po_no} created`);
    if (r) {
      setOpen(false);
      clearSeed();
      setHead({ ...head, po_no: docNo("PO") });
      setLines([{ material_id: "", quantity: 1, rate: 0, gst_rate: 18 }]);
    }
  };

  const changeStatus = (po: T.PurchaseOrderOut, status: T.PurchaseOrderStatus) => {
    const { id, created_by: _c, ...rest } = po;
    void runMutation(update.mutateAsync({ ...rest, id, status, lines: po.lines.map(({ id: _i, ...l }) => l) }), "PO status updated");
  };

  const openGrn = (po: T.PurchaseOrderOut) => {
    const q: Record<string, { qty: number; batch: string }> = {};
    po.lines.forEach((l) => {
      if (l.material_id) q[l.material_id] = { qty: Math.max(0, l.quantity - l.received_quantity), batch: "" };
    });
    setGrnQty(q);
    setGrn({ grn_no: docNo("GRN"), grn_date: todayIso(), warehouse_id: po.warehouse_id ?? warehouses.data?.[0]?.id ?? "" });
    setGrnOpen(true);
  };
  const submitGrn = async () => {
    if (!sel || !grn.warehouse_id) return;
    const glines = sel.lines
      .filter((l) => l.material_id && (grnQty[l.material_id]?.qty ?? 0) > 0)
      .map((l) => ({
        material_id: l.material_id ?? "",
        material_name: l.material_name,
        quantity: grnQty[l.material_id ?? ""]?.qty ?? 0,
        batch_no: grnQty[l.material_id ?? ""]?.batch ?? "",
      }));
    if (glines.length === 0) return;
    const r = await runMutation(
      createGrn.mutateAsync({ ...grn, purchase_order_id: sel.id, po_no: sel.po_no, lines: glines }),
      "Goods received — raw-material stock increased",
    );
    if (r) setGrnOpen(false);
  };

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="purchase-orders"
        emptyTitle="No purchase orders"
        onRowClick={(r) => setSelId(r.id)}
        toolbar={
          canEdit ? (
            <Button size="sm" onClick={() => setOpen(true)}>
              <Plus className="mr-1 h-4 w-4" /> New PO
            </Button>
          ) : null
        }
        columns={[
          { key: "no", header: "PO #", render: (r) => <span className="font-mono text-xs">{r.po_no}</span>, sortValue: (r) => r.po_no, searchValue: (r) => r.po_no },
          { key: "date", header: "Date", render: (r) => formatDate(r.po_date), sortValue: (r) => r.po_date },
          { key: "sup", header: "Supplier", render: (r) => r.supplier_name, searchValue: (r) => r.supplier_name, sortValue: (r) => r.supplier_name },
          { key: "exp", header: "Expected", render: (r) => formatDate(r.expected_date), hideable: true },
          {
            key: "recv",
            header: "Received",
            render: (r) => {
              const o = r.lines.reduce((a, l) => a + l.quantity, 0);
              const d = r.lines.reduce((a, l) => a + l.received_quantity, 0);
              return <span className="tabular-nums">{o ? Math.round((d / o) * 100) : 0}%</span>;
            },
          },
          { key: "total", header: "Total", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.grand_total)}</span>, sortValue: (r) => r.grand_total },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status.replace("_", " ")} />, sortValue: (r) => r.status, searchValue: (r) => r.status },
        ]}
      />

      <FormDialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) clearSeed(); }} title="New purchase order" wide onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="PO number">
            <Input value={head.po_no} onChange={(e) => setHead({ ...head, po_no: e.target.value })} className="font-mono" />
          </FormField>
          <FormField label="Date">
            <Input type="date" value={head.po_date} onChange={(e) => setHead({ ...head, po_date: e.target.value })} />
          </FormField>
          <FormField label="Expected">
            <Input type="date" value={head.expected_date} onChange={(e) => setHead({ ...head, expected_date: e.target.value })} />
          </FormField>
          <FormField label="Supplier *" className="space-y-1.5 sm:col-span-2">
            <SelectField value={head.supplier_id} onChange={(v) => setHead({ ...head, supplier_id: v })} options={(suppliers.data ?? []).map((s) => ({ value: s.id, label: s.name }))} />
          </FormField>
          <FormField label="Receiving warehouse">
            <SelectField allowNone value={head.warehouse_id} onChange={(v) => setHead({ ...head, warehouse_id: v })} options={(warehouses.data ?? []).map((w) => ({ value: w.id, label: `${w.code} — ${w.name}` }))} />
          </FormField>
        </div>
        <SectionTitle
          actions={
            <Button type="button" size="sm" variant="outline" onClick={() => setLines([...lines, { material_id: "", quantity: 1, rate: 0, gst_rate: 18 }])}>
              <Plus className="mr-1 h-3.5 w-3.5" /> Line
            </Button>
          }
        >
          Materials
        </SectionTitle>
        <div className="space-y-2">
          {lines.map((l, i) => (
            <div key={i} className="grid grid-cols-[1fr_90px_100px_70px_32px] items-center gap-2">
              <SelectField
                value={l.material_id}
                onChange={(v) => {
                  const m = materials.data?.find((x) => x.id === v);
                  setLines(lines.map((x, j) => (j === i ? { ...x, material_id: v, rate: m?.cost ?? x.rate } : x)));
                }}
                options={(materials.data ?? []).map((m) => ({ value: m.id, label: `${m.code} — ${m.name}` }))}
                placeholder="Material"
              />
              <NumInput value={l.quantity} onChange={(n) => setLines(lines.map((x, j) => (j === i ? { ...x, quantity: n } : x)))} />
              <NumInput value={l.rate} onChange={(n) => setLines(lines.map((x, j) => (j === i ? { ...x, rate: n } : x)))} />
              <NumInput value={l.gst_rate} onChange={(n) => setLines(lines.map((x, j) => (j === i ? { ...x, gst_rate: n } : x)))} />
              <Button type="button" size="icon" variant="ghost" className="h-8 w-8" onClick={() => setLines(lines.filter((_, j) => j !== i))} aria-label="Remove line">
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">Qty · Rate · GST %</p>
        </div>
        <div className="flex justify-end gap-6 text-sm tabular-nums">
          <span>Sub-total {formatCurrency(sub_total)}</span>
          <span>GST {formatCurrency(gst_total)}</span>
          <span className="font-semibold">Total {formatCurrency(sub_total + gst_total)}</span>
        </div>
      </FormDialog>

      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSelId(null)} title={sel?.po_no ?? ""} description={sel?.supplier_name ?? ""}>
        {sel ? (
          <>
            <KeyValues
              items={[
                ["Status", <StatusBadge key="s" status={sel.status.replace("_", " ")} />],
                ["PO date", formatDate(sel.po_date)],
                ["Expected", formatDate(sel.expected_date)],
                ["Warehouse", lookup(warehouses.data, sel.warehouse_id, (w) => w.name)],
                ["Sub-total", formatCurrency(sel.sub_total)],
                ["Grand total", formatCurrency(sel.grand_total)],
              ]}
            />
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Material</TableHead>
                    <TableHead className="text-right">Ordered</TableHead>
                    <TableHead className="text-right">Received</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sel.lines.map((l) => (
                    <TableRow key={l.id}>
                      <TableCell>{l.material_name}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatNumber(l.quantity, 2)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatNumber(l.received_quantity, 2)}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatCurrency(l.total)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            {canEdit ? (
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-48">
                  <SelectField value={sel.status} onChange={(v) => changeStatus(sel, v as T.PurchaseOrderStatus)} options={PO_STATUSES.map((s) => ({ value: s, label: s.replace("_", " ") }))} />
                </div>
                {sel.status !== "received" ? (
                  <Button size="sm" onClick={() => openGrn(sel)}>
                    <PackageCheck className="mr-1 h-4 w-4" /> Receive goods (GRN)
                  </Button>
                ) : null}
              </div>
            ) : null}
          </>
        ) : null}
      </DetailSheet>

      <FormDialog open={grnOpen} onOpenChange={setGrnOpen} title={`Goods receipt for ${sel?.po_no ?? ""}`} onSubmit={() => void submitGrn()} pending={createGrn.isPending} submitLabel="Post GRN">
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="GRN number">
            <Input value={grn.grn_no} onChange={(e) => setGrn({ ...grn, grn_no: e.target.value })} className="font-mono" />
          </FormField>
          <FormField label="Date">
            <Input type="date" value={grn.grn_date} onChange={(e) => setGrn({ ...grn, grn_date: e.target.value })} />
          </FormField>
          <FormField label="Warehouse *">
            <SelectField value={grn.warehouse_id} onChange={(v) => setGrn({ ...grn, warehouse_id: v })} options={(warehouses.data ?? []).map((w) => ({ value: w.id, label: w.code }))} />
          </FormField>
        </div>
        {sel?.lines
          .filter((l) => l.material_id)
          .map((l) => {
            const k = l.material_id ?? "";
            const v = grnQty[k] ?? { qty: 0, batch: "" };
            return (
              <div key={l.id} className="grid grid-cols-[1fr_100px_140px] items-center gap-2 text-sm">
                <span>
                  {l.material_name}
                  <span className="ml-2 text-xs text-muted-foreground">open {formatNumber(l.quantity - l.received_quantity, 2)}</span>
                </span>
                <NumInput value={v.qty} onChange={(n) => setGrnQty({ ...grnQty, [k]: { ...v, qty: n } })} />
                <Input placeholder="Batch no." value={v.batch} onChange={(e) => setGrnQty({ ...grnQty, [k]: { ...v, batch: e.target.value } })} />
              </div>
            );
          })}
      </FormDialog>
    </>
  );
}

function GrnsTab() {
  const query = H.useGrns();
  const warehouses = H.useWarehouses();
  return (
    <QueryTable
      query={query}
      rowKey={(r) => r.id}
      exportName="grns"
      emptyTitle="No goods receipts"
      columns={[
        { key: "no", header: "GRN #", render: (r) => <span className="font-mono text-xs">{r.grn_no}</span>, sortValue: (r) => r.grn_no, searchValue: (r) => r.grn_no },
        { key: "date", header: "Date", render: (r) => formatDate(r.grn_date), sortValue: (r) => r.grn_date },
        { key: "po", header: "PO", render: (r) => <span className="font-mono text-xs">{r.po_no}</span>, searchValue: (r) => r.po_no },
        { key: "wh", header: "Warehouse", render: (r) => lookup(warehouses.data, r.warehouse_id, (w) => w.code) },
        { key: "items", header: "Items received", render: (r) => r.lines.map((l) => `${l.material_name} × ${formatNumber(l.quantity, 2)}${l.batch_no ? ` [${l.batch_no}]` : ""}`).join(", "), searchValue: (r) => r.lines.map((l) => l.material_name + l.batch_no).join(" ") },
      ]}
    />
  );
}
