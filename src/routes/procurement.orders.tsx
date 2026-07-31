import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PackageCheck, Plus, Trash2, Truck } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { DocTrail, Field, StatusBadge } from "@/components/erp/DocBits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { today, useErp } from "@/lib/erp/store";
import {
  createPurchaseOrder,
  defaultWarehouse,
  docStats,
  nextDocNo,
  receiveGoods,
  setPoStatus,
  type PoLineDraft,
} from "@/lib/erp/docs";
import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";
import type { PurchaseOrder } from "@/lib/erp/doc-types";

export const Route = createFileRoute("/procurement/orders")({
  head: () => ({
    meta: [
      { title: "Purchase Orders — MiniTally ERP" },
      {
        name: "description",
        content: "Raise purchase orders from approved requisitions, track deliveries and receive goods into stock.",
      },
      { property: "og:title", content: "Purchase Orders — MiniTally ERP" },
      { property: "og:description", content: "PO to GRN with automatic raw-material stock updates." },
    ],
  }),
  component: () => (
    <AppShell>
      <PurchaseOrdersPage />
    </AppShell>
  ),
});

const blankLine = (): PoLineDraft => ({ materialId: "", quantity: 0, rate: 0, gstPercent: 18 });

function PurchaseOrdersPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const user = session?.username ?? "system";

  const [open, setOpen] = useState(false);
  const [receiving, setReceiving] = useState<PurchaseOrder | null>(null);
  const [lines, setLines] = useState<PoLineDraft[]>([blankLine()]);
  const [prIds, setPrIds] = useState<string[]>([]);
  const [form, setForm] = useState({
    date: today(),
    supplierId: "",
    expectedDate: today(),
    paymentTerms: "30 days credit",
    warehouseId: defaultWarehouse(state),
    status: "Draft" as PurchaseOrder["status"],
  });
  const [grn, setGrn] = useState<{ date: string; warehouseId: string; remarks: string; qty: Record<string, string>; batch: Record<string, string> }>({
    date: today(),
    warehouseId: defaultWarehouse(state),
    remarks: "",
    qty: {},
    batch: {},
  });

  const stats = docStats(state);
  const approvedPrs = state.requisitions.filter((p) => p.status === "Approved");

  const totals = useMemo(() => {
    let taxable = 0;
    let tax = 0;
    lines.forEach((l) => {
      const t = l.quantity * l.rate;
      taxable += t;
      tax += (t * l.gstPercent) / 100;
    });
    return { taxable, tax, grand: taxable + tax };
  }, [lines]);

  const applyPrSelection = (ids: string[]) => {
    setPrIds(ids);
    const picked = state.requisitions.filter((p) => ids.includes(p.id));
    if (picked.length)
      setLines(
        picked.map((p) => {
          const mat = state.materials.find((m) => m.id === p.materialId);
          return { materialId: p.materialId, quantity: p.quantity, rate: mat?.cost ?? 0, gstPercent: 18 };
        }),
      );
  };

  const submit = () => {
    try {
      const poNo = createPurchaseOrder({ ...form, prIds, lines }, user);
      toast.success(`${poNo} created`);
      setOpen(false);
      setLines([blankLine()]);
      setPrIds([]);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const submitGrn = () => {
    if (!receiving) return;
    try {
      const grnNo = receiveGoods(
        receiving.id,
        {
          date: grn.date,
          warehouseId: grn.warehouseId,
          remarks: grn.remarks,
          lines: receiving.lines.map((l) => ({
            materialId: l.materialId,
            quantity: Number(grn.qty[l.materialId] ?? 0),
            batchNo: grn.batch[l.materialId] ?? "",
          })),
        },
        user,
      );
      toast.success(`${grnNo} posted — raw material stock updated`);
      setReceiving(null);
      setGrn({ ...grn, qty: {}, batch: {}, remarks: "" });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Purchase Orders"
        subtitle="From approved requisitions to goods receipt — receiving posts raw materials into stock."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New purchase order
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Open POs" value={num(stats.openPos)} tone="primary" icon={<Truck className="h-4 w-4" />} />
        <StatCard label="PO value on book" value={inr(stats.poValue)} />
        <StatCard label="Goods receipts" value={num(state.receipts.length)} tone="success" />
        <StatCard label="Approved PRs waiting" value={num(stats.approvedPrs)} tone="warning" />
      </div>

      <DataTable
        rows={state.purchaseOrders}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.poNo} ${r.supplierName} ${r.status} ${r.prNos.join(" ")} ${r.lines.map((l) => l.materialName).join(" ")}`}
        columns={[
          { key: "poNo", header: "PO No", value: (r) => r.poNo, render: (r) => <span className="num font-medium">{r.poNo}</span> },
          { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "supplier", header: "Supplier", value: (r) => r.supplierName },
          {
            key: "items",
            header: "Items",
            render: (r) => (
              <span className="text-muted-foreground text-xs">
                {r.lines.map((l) => `${l.materialName} ×${num(l.quantity, 1)}`).join(", ")}
              </span>
            ),
          },
          {
            key: "received",
            header: "Received",
            align: "right",
            value: (r) => r.lines.reduce((t, l) => t + l.receivedQty, 0),
            render: (r) => (
              <span className="num text-xs">
                {num(r.lines.reduce((t, l) => t + l.receivedQty, 0), 1)} / {num(r.lines.reduce((t, l) => t + l.quantity, 0), 1)}
              </span>
            ),
          },
          { key: "expected", header: "Expected", value: (r) => r.expectedDate, render: (r) => <span className="num">{dmy(r.expectedDate)}</span> },
          { key: "total", header: "Value", align: "right", value: (r) => r.grandTotal, render: (r) => <span className="num">{inr(r.grandTotal)}</span> },
          { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
          { key: "trail", header: "Trail", render: (r) => <DocTrail steps={[r.prNos[0], r.poNo, state.receipts.find((g) => g.poId === r.id)?.grnNo]} /> },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (r) => (
              <div className="flex justify-end gap-1">
                {r.status === "Draft" && (
                  <Button size="sm" variant="outline" onClick={() => setPoStatus(r.id, "Approved", user)}>
                    Approve
                  </Button>
                )}
                {(r.status === "Approved" || r.status === "Partially Received") && (
                  <Button
                    size="sm"
                    onClick={() => {
                      setReceiving(r);
                      setGrn((g) => ({ ...g, warehouseId: r.warehouseId, date: today(), qty: {}, batch: {} }));
                    }}
                  >
                    <PackageCheck className="mr-1 h-3.5 w-3.5" /> Receive
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />

      <div className="mt-6">
        <h2 className="mb-3 text-sm font-semibold">Goods receipts (GRN)</h2>
        <DataTable
          rows={state.receipts}
          rowKey={(r) => r.id}
          pageSize={5}
          searchable={(r) => `${r.grnNo} ${r.poNo} ${r.lines.map((l) => l.materialName).join(" ")}`}
          columns={[
            { key: "grnNo", header: "GRN No", value: (r) => r.grnNo, render: (r) => <span className="num font-medium">{r.grnNo}</span> },
            { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
            { key: "po", header: "Against PO", value: (r) => r.poNo, render: (r) => <span className="num">{r.poNo}</span> },
            {
              key: "lines",
              header: "Received",
              render: (r) => (
                <span className="text-xs">
                  {r.lines.map((l) => `${l.materialName} ${num(l.quantity, 1)}${l.batchNo ? ` (${l.batchNo})` : ""}`).join(", ")}
                </span>
              ),
            },
            {
              key: "wh",
              header: "Warehouse",
              value: (r) => r.warehouseId,
              render: (r) => state.warehouses.find((w) => w.id === r.warehouseId)?.name ?? r.warehouseId,
            },
            { key: "remarks", header: "Remarks", className: "text-muted-foreground text-xs", value: (r) => r.remarks },
          ]}
        />
      </div>

      {/* ---- New PO ---- */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>New purchase order</DialogTitle>
            <DialogDescription>Numbered {nextDocNo(state, "PO", form.date)} on save.</DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Supplier" full>
              <Select value={form.supplierId} onValueChange={(v) => setForm({ ...form, supplierId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select supplier" />
                </SelectTrigger>
                <SelectContent>
                  {state.suppliers.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="PO date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Expected delivery">
              <Input type="date" value={form.expectedDate} onChange={(e) => setForm({ ...form, expectedDate: e.target.value })} />
            </Field>
            <Field label="Payment terms">
              <Input value={form.paymentTerms} onChange={(e) => setForm({ ...form, paymentTerms: e.target.value })} />
            </Field>
            <Field label="Receiving warehouse">
              <Select value={form.warehouseId} onValueChange={(v) => setForm({ ...form, warehouseId: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {state.warehouses.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>

          {approvedPrs.length > 0 && (
            <div className="panel mt-3 p-3">
              <p className="mb-2 text-xs font-semibold">Pull from approved requisitions</p>
              <div className="space-y-2">
                {approvedPrs.map((p) => (
                  <label key={p.id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={prIds.includes(p.id)}
                      onCheckedChange={(c) =>
                        applyPrSelection(c ? [...prIds, p.id] : prIds.filter((x) => x !== p.id))
                      }
                    />
                    <span className="num text-xs">{p.prNo}</span>
                    <span>
                      {p.materialName} · {num(p.quantity, 1)} {p.unit}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div className="mt-3 space-y-2">
            {lines.map((l, i) => (
              <div key={i} className="grid grid-cols-12 items-end gap-2">
                <div className="col-span-12 sm:col-span-5">
                  <Select value={l.materialId} onValueChange={(v) => setLines(lines.map((x, xi) => (xi === i ? { ...x, materialId: v, rate: state.materials.find((m) => m.id === v)?.cost ?? x.rate } : x)))}>
                    <SelectTrigger>
                      <SelectValue placeholder="Material" />
                    </SelectTrigger>
                    <SelectContent>
                      {state.materials.map((m) => (
                        <SelectItem key={m.id} value={m.id}>
                          {m.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input
                  className="col-span-4 sm:col-span-2"
                  type="number"
                  placeholder="Qty"
                  value={l.quantity || ""}
                  onChange={(e) => setLines(lines.map((x, xi) => (xi === i ? { ...x, quantity: Number(e.target.value) } : x)))}
                />
                <Input
                  className="col-span-4 sm:col-span-2"
                  type="number"
                  placeholder="Rate"
                  value={l.rate || ""}
                  onChange={(e) => setLines(lines.map((x, xi) => (xi === i ? { ...x, rate: Number(e.target.value) } : x)))}
                />
                <Input
                  className="col-span-3 sm:col-span-2"
                  type="number"
                  placeholder="GST %"
                  value={l.gstPercent}
                  onChange={(e) => setLines(lines.map((x, xi) => (xi === i ? { ...x, gstPercent: Number(e.target.value) } : x)))}
                />
                <Button variant="ghost" size="icon" className="col-span-1" onClick={() => setLines(lines.length > 1 ? lines.filter((_, xi) => xi !== i) : lines)}>
                  <Trash2 className="text-destructive h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setLines([...lines, blankLine()])}>
              <Plus className="mr-1 h-3.5 w-3.5" /> Add line
            </Button>
          </div>

          <div className="panel mt-3 grid grid-cols-3 gap-2 p-3 text-sm">
            <div>
              <p className="text-muted-foreground text-xs">Taxable</p>
              <p className="num font-medium">{inr(totals.taxable)}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">GST</p>
              <p className="num font-medium">{inr(totals.tax)}</p>
            </div>
            <div>
              <p className="text-muted-foreground text-xs">Grand total</p>
              <p className="num text-primary font-semibold">{inr(totals.grand)}</p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={() => { setForm({ ...form, status: "Draft" }); submit(); }}>
              Save draft
            </Button>
            <Button onClick={() => { setForm({ ...form, status: "Approved" }); createAndApprove(); }}>
              Approve & save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---- GRN ---- */}
      <Dialog open={!!receiving} onOpenChange={(o) => !o && setReceiving(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Receive goods — {receiving?.poNo}</DialogTitle>
            <DialogDescription>Received quantities post an IN movement and credit the warehouse.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Receipt date">
              <Input type="date" value={grn.date} onChange={(e) => setGrn({ ...grn, date: e.target.value })} />
            </Field>
            <Field label="Warehouse">
              <Select value={grn.warehouseId} onValueChange={(v) => setGrn({ ...grn, warehouseId: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {state.warehouses.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
          <div className="mt-2 space-y-2">
            {receiving?.lines.map((l) => (
              <div key={l.materialId} className="grid grid-cols-12 items-center gap-2">
                <div className="col-span-12 text-sm sm:col-span-5">
                  <p className="font-medium">{l.materialName}</p>
                  <p className="text-muted-foreground num text-xs">
                    pending {num(l.quantity - l.receivedQty, 2)} {l.unit}
                  </p>
                </div>
                <Input
                  className="col-span-6 sm:col-span-3"
                  type="number"
                  placeholder="Qty received"
                  value={grn.qty[l.materialId] ?? ""}
                  onChange={(e) => setGrn({ ...grn, qty: { ...grn.qty, [l.materialId]: e.target.value } })}
                />
                <Input
                  className="col-span-6 sm:col-span-4"
                  placeholder="Batch / heat no"
                  value={grn.batch[l.materialId] ?? ""}
                  onChange={(e) => setGrn({ ...grn, batch: { ...grn.batch, [l.materialId]: e.target.value } })}
                />
              </div>
            ))}
          </div>
          <Textarea
            className="mt-2"
            rows={2}
            placeholder="Remarks"
            value={grn.remarks}
            onChange={(e) => setGrn({ ...grn, remarks: e.target.value })}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setReceiving(null)}>
              Cancel
            </Button>
            <Button onClick={submitGrn}>Post GRN</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );

  function createAndApprove() {
    try {
      const poNo = createPurchaseOrder({ ...form, status: "Approved", prIds, lines }, user);
      toast.success(`${poNo} approved`);
      setOpen(false);
      setLines([blankLine()]);
      setPrIds([]);
    } catch (e) {
      toast.error((e as Error).message);
    }
  }
}
