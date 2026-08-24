import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PackageCheck, Plus } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Field } from "@/components/erp/DocBits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createGRN, getGRNs, getPurchaseOrders, getWarehouses, type GRNData, type PurchaseOrderData, type WarehouseData } from "@/lib/erp/api";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/procurement/receipts")({
  head: () => ({ meta: [{ title: "Goods Receipts — MiniTally ERP" }] }),
  component: () => <AppShell><GoodsReceiptsPage /></AppShell>,
});

const today = () => new Date().toISOString().slice(0, 10);

function GoodsReceiptsPage() {
  const [grns, setGrns] = useState<GRNData[]>([]);
  const [orders, setOrders] = useState<PurchaseOrderData[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseData[]>([]);
  const [open, setOpen] = useState(false);
  const [poId, setPoId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [date, setDate] = useState(today());
  const [remarks, setRemarks] = useState("");
  const [qty, setQty] = useState<Record<string, string>>({});
  const [batch, setBatch] = useState<Record<string, string>>({});

  async function load() {
    try {
      const [g, o, w] = await Promise.all([getGRNs(), getPurchaseOrders(), getWarehouses()]);
      setGrns(g); setOrders(o.filter((x) => x.status !== "Cancelled" && x.status !== "Received")); setWarehouses(w);
    } catch (e) { toast.error((e as Error).message || "Failed to load GRNs"); }
  }
  useEffect(() => { void load(); }, []);

  const po = orders.find((x) => x.id === poId);

  async function submit() {
    if (!po) return toast.error("Select a purchase order");
    if (!warehouseId) return toast.error("Select warehouse");
    const lines = po.lines.map((l) => ({ material_id: l.material_id, quantity: Number(qty[l.material_id] ?? 0), batch_no: batch[l.material_id] ?? "" })).filter((l) => l.quantity > 0);
    if (!lines.length) return toast.error("Enter received quantities");
    for (const l of lines) {
      const src = po.lines.find((x) => x.material_id === l.material_id);
      if (src && l.quantity > src.quantity - src.received_quantity) return toast.error(`Only ${src.quantity - src.received_quantity} ${src.unit} pending for ${src.material_name}`);
    }
    try {
      const g = await createGRN({ grn_date: date, purchase_order_id: po.id, warehouse_id: warehouseId, remarks, lines });
      toast.success(`${g.grn_no} posted — raw material stock increased`); setOpen(false); setPoId(""); setWarehouseId(""); setQty({}); setBatch({}); setRemarks(""); await load();
    } catch (e) { toast.error((e as Error).message || "Failed to create GRN"); }
  }

  return <>
    <PageHeader title="Goods Receipts" subtitle="Receive supplier material into the selected warehouse; this is the inventory IN point." actions={<Button onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New GRN</Button>} />
    <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"><StatCard label="GRNs" value={num(grns.length)} tone="primary" icon={<PackageCheck className="h-4 w-4" />} /><StatCard label="Pending POs" value={num(orders.length)} /><StatCard label="Received lines" value={num(grns.reduce((t, g) => t + g.lines.length, 0))} /></div>
    <DataTable rows={grns} rowKey={(r) => r.id} searchable={(r) => `${r.grn_no} ${r.po_no} ${r.supplier_name}`} columns={[{ key: "no", header: "GRN No", value: (r) => r.grn_no }, { key: "date", header: "Date", value: (r) => r.grn_date, render: (r) => <span className="num">{dmy(r.grn_date)}</span> }, { key: "po", header: "PO", value: (r) => r.po_no }, { key: "supplier", header: "Supplier", value: (r) => r.supplier_name }, { key: "items", header: "Items", render: (r) => <span className="text-xs text-muted-foreground">{r.lines.map((l: GRNData["lines"][number]) => `${l.material_name} ×${num(l.quantity)}`).join(", ")}</span> }]} />
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl"><DialogHeader><DialogTitle>New Goods Receipt</DialogTitle><DialogDescription>Post received quantities against a purchase order.</DialogDescription></DialogHeader><div className="grid grid-cols-2 gap-3"><Field label="Purchase Order"><Select value={poId} onValueChange={(v) => { setPoId(v); setQty({}); }}><SelectTrigger><SelectValue placeholder="Select PO" /></SelectTrigger><SelectContent>{orders.map((o) => <SelectItem key={o.id} value={o.id}>{o.po_no} · {o.supplier_name}</SelectItem>)}</SelectContent></Select></Field><Field label="Warehouse"><Select value={warehouseId} onValueChange={setWarehouseId}><SelectTrigger><SelectValue placeholder="Select warehouse" /></SelectTrigger><SelectContent>{warehouses.map((w) => <SelectItem key={w.id} value={w.id}>{w.code} · {w.name}</SelectItem>)}</SelectContent></Select></Field><Field label="GRN date"><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field></div>{po && <div className="mt-4 space-y-2">{po.lines.filter((l) => l.quantity > l.received_quantity).map((l) => <div key={l.id} className="grid grid-cols-12 gap-2 items-center"><div className="col-span-5 text-sm">{l.material_name}<span className="ml-1 text-xs text-muted-foreground">({l.unit})</span></div><div className="col-span-2 text-right num text-xs">pending {num(l.quantity - l.received_quantity)}</div><Input className="col-span-3" type="number" min="0" max={l.quantity - l.received_quantity} value={qty[l.material_id] ?? ""} onChange={(e) => setQty({ ...qty, [l.material_id]: e.target.value })} placeholder="Received" /><Input className="col-span-2" value={batch[l.material_id] ?? ""} onChange={(e) => setBatch({ ...batch, [l.material_id]: e.target.value })} placeholder="Batch" /></div>)}</div>}<Textarea className="mt-3" rows={2} placeholder="Remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} /><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={() => void submit()}>Post GRN</Button></DialogFooter></DialogContent></Dialog>
  </>;
}
