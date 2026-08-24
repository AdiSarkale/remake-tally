import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, ShoppingCart } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Field, StatusBadge } from "@/components/erp/DocBits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { getMaterials, getSuppliers, getWarehouses, createPurchaseOrder, getPurchaseOrders, type MaterialData, type PartyData, type PurchaseOrderData, type WarehouseData } from "@/lib/api";
import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/procurement/orders")({
  head: () => ({ meta: [{ title: "Purchase Orders — MiniTally ERP" }] }),
  component: () => <AppShell><PurchaseOrdersPage /></AppShell>,
});

type DraftLine = { materialId: string; quantity: number; rate: number; gstRate: number };
const blank = (): DraftLine => ({ materialId: "", quantity: 0, rate: 0, gstRate: 18 });
const today = () => new Date().toISOString().slice(0, 10);

function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<PurchaseOrderData[]>([]);
  const [suppliers, setSuppliers] = useState<PartyData[]>([]);
  const [materials, setMaterials] = useState<MaterialData[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseData[]>([]);
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<DraftLine[]>([blank()]);
  const [form, setForm] = useState({ poDate: today(), expectedDate: "", supplierId: "", warehouseId: "", notes: "" });

  async function load() {
    try {
      const [o, s, m, w] = await Promise.all([getPurchaseOrders(), getSuppliers(), getMaterials(), getWarehouses()]);
      setOrders(o); setSuppliers(s.filter((x) => x.kind === "supplier")); setMaterials(m); setWarehouses(w);
    } catch (e) { toast.error((e as Error).message || "Failed to load purchase orders"); }
  }
  useEffect(() => { void load(); }, []);

  async function submit() {
    if (!form.supplierId) return toast.error("Select supplier");
    if (!form.warehouseId) return toast.error("Select receiving warehouse");
    const valid = lines.filter((x) => x.materialId && x.quantity > 0);
    if (!valid.length) return toast.error("Add material lines");
    try {
      const po = await createPurchaseOrder({
        po_date: form.poDate,
        expected_date: form.expectedDate || null,
        supplier_id: form.supplierId,
        warehouse_id: form.warehouseId,
        notes: form.notes,
        lines: valid.map((x) => ({ material_id: x.materialId, quantity: x.quantity, rate: x.rate, gst_rate: x.gstRate })),
      });
      toast.success(`${po.po_no} created`); setOpen(false); setLines([blank()]);
      setForm({ poDate: today(), expectedDate: "", supplierId: "", warehouseId: "", notes: "" }); await load();
    } catch (e) { toast.error((e as Error).message || "Failed to create PO"); }
  }

  return <>
    <PageHeader title="Purchase Orders" subtitle="Buy raw materials from suppliers; stock changes only on GRN." actions={<Button onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New PO</Button>} />
    <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Open POs" value={num(orders.filter((o) => ["Draft", "Sent", "Partially Received"].includes(o.status)).length)} tone="primary" icon={<ShoppingCart className="h-4 w-4" />} />
      <StatCard label="Order value" value={inr(orders.reduce((t, o) => t + o.grand_total, 0))} />
      <StatCard label="Received" value={num(orders.filter((o) => o.status === "Received").length)} tone="success" />
      <StatCard label="Total POs" value={num(orders.length)} />
    </div>
    <DataTable rows={orders} rowKey={(r) => r.id} searchable={(r) => `${r.po_no} ${r.supplier_name} ${r.status}`} columns={[
      { key: "po", header: "PO No", value: (r) => r.po_no, render: (r) => <span className="num font-medium">{r.po_no}</span> },
      { key: "date", header: "Date", value: (r) => r.po_date, render: (r) => <span className="num">{dmy(r.po_date)}</span> },
      { key: "supplier", header: "Supplier", value: (r) => r.supplier_name },
      { key: "items", header: "Items", render: (r) => <span className="text-xs text-muted-foreground">{r.lines.map((l: PurchaseOrderData["lines"][number]) => `${l.material_name} ×${num(l.quantity)}`).join(", ")}</span> },
      { key: "value", header: "Value", align: "right", value: (r) => r.grand_total, render: (r) => <span className="num">{inr(r.grand_total)}</span> },
      { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
    ]} />

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl"><DialogHeader><DialogTitle>New Purchase Order</DialogTitle><DialogDescription>Supplier → PO → GRN → raw material stock.</DialogDescription></DialogHeader>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Supplier"><Select value={form.supplierId} onValueChange={(v) => setForm({ ...form, supplierId: v })}><SelectTrigger><SelectValue placeholder="Supplier" /></SelectTrigger><SelectContent>{suppliers.map((s) => <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>)}</SelectContent></Select></Field>
        <Field label="Receiving warehouse"><Select value={form.warehouseId} onValueChange={(v) => setForm({ ...form, warehouseId: v })}><SelectTrigger><SelectValue placeholder="Warehouse" /></SelectTrigger><SelectContent>{warehouses.map((w) => <SelectItem key={w.id} value={w.id}>{w.code} · {w.name}</SelectItem>)}</SelectContent></Select></Field>
        <Field label="PO date"><Input type="date" value={form.poDate} onChange={(e) => setForm({ ...form, poDate: e.target.value })} /></Field>
        <Field label="Expected date"><Input type="date" value={form.expectedDate} onChange={(e) => setForm({ ...form, expectedDate: e.target.value })} /></Field>
      </div>
      <div className="mt-4 space-y-2">{lines.map((l, i) => <div className="grid grid-cols-12 gap-2" key={i}><div className="col-span-6"><Select value={l.materialId} onValueChange={(v) => { const m = materials.find((x) => x.id === v); setLines(lines.map((x, xi) => xi === i ? { ...x, materialId: v, rate: m?.cost ?? x.rate } : x)); }}><SelectTrigger><SelectValue placeholder="Raw material" /></SelectTrigger><SelectContent>{materials.map((m) => <SelectItem key={m.id} value={m.id}>{m.name} · {m.unit}</SelectItem>)}</SelectContent></Select></div><Input className="col-span-2" type="number" placeholder="Qty" value={l.quantity || ""} onChange={(e) => setLines(lines.map((x, xi) => xi === i ? { ...x, quantity: Number(e.target.value) } : x))} /><Input className="col-span-2" type="number" placeholder="Rate" value={l.rate || ""} onChange={(e) => setLines(lines.map((x, xi) => xi === i ? { ...x, rate: Number(e.target.value) } : x))} /><Input className="col-span-2" type="number" placeholder="GST %" value={l.gstRate} onChange={(e) => setLines(lines.map((x, xi) => xi === i ? { ...x, gstRate: Number(e.target.value) } : x))} /></div>)}<Button variant="outline" size="sm" onClick={() => setLines([...lines, blank()])}><Plus className="mr-1 h-3.5 w-3.5" /> Add line</Button></div>
      <Textarea className="mt-3" rows={2} placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
      <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={() => void submit()}>Create PO</Button></DialogFooter>
    </DialogContent></Dialog>
  </>;
}
