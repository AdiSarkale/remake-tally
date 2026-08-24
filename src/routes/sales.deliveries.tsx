import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Receipt, Truck } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { DocTrail, Field } from "@/components/erp/DocBits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createDelivery, getCustomers, getDeliveries, getSalesOrders, type DeliveryData, type PartyData, type SalesOrderData } from "@/lib/erp/api";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/sales/deliveries")({
  head: () => ({ meta: [{ title: "Delivery Notes — MiniTally ERP" }] }),
  component: () => (
    <AppShell>
      <DeliveriesPage />
    </AppShell>
  ),
});

const today = () => new Date().toISOString().slice(0, 10);

function DeliveriesPage() {
  const [deliveries, setDeliveries] = useState<DeliveryData[]>([]);
  const [salesOrders, setSalesOrders] = useState<SalesOrderData[]>([]);
  const [customers, setCustomers] = useState<PartyData[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [mode, setMode] = useState<"so" | "direct">("so");
  const [form, setForm] = useState({
    date: today(),
    soId: "",
    customerId: "",
    vehicleNo: "",
    driverName: "",
    lrNumber: "",
    remarks: "",
  });
  const [qty, setQty] = useState<Record<string, string>>({});

  async function load() {
    try {
      setLoading(true);
      const [d, so, c] = await Promise.all([getDeliveries(), getSalesOrders(), getCustomers()]);
      setDeliveries(d);
      setSalesOrders(so);
      setCustomers(c.filter((x) => x.kind === "customer"));
    } catch (e) {
      toast.error((e as Error).message || "Failed to load deliveries");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const openSos = salesOrders.filter((o) => o.status === "Open" || o.status === "Partially Delivered");
  const selectedSo = salesOrders.find((o) => o.id === form.soId);
  const dispatchables = selectedSo
    ? selectedSo.lines
        .map((l) => ({ productId: l.product_id, name: l.product_name, unit: l.unit, rate: l.rate, ordered: l.quantity, delivered: l.delivered_quantity, pending: Math.max(0, l.quantity - l.delivered_quantity) }))
        .filter((x) => x.pending > 0)
    : [];

  const previewValue = useMemo(() => dispatchables.reduce((t, l) => t + Number(qty[l.productId] ?? 0) * l.rate, 0), [dispatchables, qty]);

  function reset() {
    setMode("so");
    setForm({ date: today(), soId: "", customerId: "", vehicleNo: "", driverName: "", lrNumber: "", remarks: "" });
    setQty({});
  }

  async function submit() {
    const lines = mode === "so"
      ? dispatchables.map((l) => ({ product_id: l.productId, quantity: Number(qty[l.productId] ?? 0) })).filter((x) => x.quantity > 0)
      : [];

    if (mode === "so" && !form.soId) return toast.error("Select a Sales Order");
    if (mode === "direct" && !form.customerId) return toast.error("Select a customer for direct dispatch");
    if (!lines.length) return toast.error("Enter at least one delivery quantity");

    for (const line of lines) {
      const src = dispatchables.find((x) => x.productId === line.product_id);
      if (src && line.quantity > src.pending) return toast.error(`${src.name}: maximum ${num(src.pending)} ${src.unit}`);
    }

    try {
      setSaving(true);
      const delivery = await createDelivery({
        delivery_date: form.date,
        sales_order_id: mode === "so" ? form.soId : null,
        customer_id: mode === "direct" ? form.customerId : null,
        vehicle_no: form.vehicleNo,
        driver_name: form.driverName,
        lr_number: form.lrNumber,
        remarks: form.remarks,
        lines,
      });
      toast.success(`${delivery.delivery_no} posted — stock reduced`);
      setOpen(false);
      reset();
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to post delivery");
    } finally {
      setSaving(false);
    }
  }

  const rows = deliveries;

  return (
    <>
      <PageHeader title="Delivery Notes" subtitle="Dispatch documentation — stock leaves here; invoice is raised against the delivery." actions={<Button onClick={() => { reset(); setOpen(true); }}><Plus className="mr-1 h-4 w-4" /> New delivery</Button>} />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Delivery notes" value={num(rows.length)} tone="primary" icon={<Truck className="h-4 w-4" />} />
        <StatCard label="Pending SOs" value={num(openSos.length)} />
        <StatCard label="Pieces dispatched" value={num(rows.reduce((t, d) => t + d.lines.reduce((x, l) => x + l.quantity, 0), 0))} />
        <StatCard label="SO-linked notes" value={num(rows.filter((d) => Boolean(d.so_no)).length)} />
      </div>

      <DataTable rows={rows} rowKey={(r) => r.id} searchable={(r) => `${r.delivery_no} ${r.so_no} ${r.customer_name} ${r.vehicle_no} ${r.driver_name} ${r.lr_number}`} columns={[
        { key: "no", header: "DN No", value: (r) => r.delivery_no, render: (r) => <span className="num font-medium">{r.delivery_no}</span> },
        { key: "date", header: "Date", value: (r) => r.delivery_date, render: (r) => <span className="num">{dmy(r.delivery_date)}</span> },
        { key: "so", header: "SO", value: (r) => r.so_no || "Direct" },
        { key: "customer", header: "Customer", value: (r) => r.customer_name },
        { key: "items", header: "Dispatched", render: (r) => <span className="text-muted-foreground text-xs">{r.lines.map((l: DeliveryData["lines"][number]) => `${l.product_name} ×${num(l.quantity)}`).join(", ")}</span> },
        { key: "vehicle", header: "Vehicle", value: (r) => r.vehicle_no },
        { key: "driver", header: "Driver", value: (r) => r.driver_name },
        { key: "lr", header: "LR No", value: (r) => r.lr_number },
        { key: "trail", header: "Trail", render: (r) => <DocTrail steps={[r.so_no, r.delivery_no]} /> },
        { key: "invoice", header: "Invoice", render: () => <Badge variant="outline"><Receipt className="mr-1 h-3 w-3" /> Next</Badge> },
      ]} />

      {loading && <div className="py-8 text-center text-sm text-muted-foreground">Loading delivery notes...</div>}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader><DialogTitle>New delivery note</DialogTitle><DialogDescription>Choose an open Sales Order or use direct dispatch.</DialogDescription></DialogHeader>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Delivery mode" full><Select value={mode} onValueChange={(v) => { setMode(v as "so" | "direct"); setForm({ ...form, soId: "", customerId: "" }); setQty({}); }}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="so">Against Sales Order</SelectItem><SelectItem value="direct">Direct dispatch</SelectItem></SelectContent></Select></Field>

            {mode === "so" ? <Field label="Sales Order" full><Select value={form.soId} onValueChange={(v) => { setForm({ ...form, soId: v }); setQty({}); }}><SelectTrigger><SelectValue placeholder="Select Sales Order" /></SelectTrigger><SelectContent>{openSos.map((o) => <SelectItem key={o.id} value={o.id}>{o.so_no} · {o.customer_name} · {o.status}</SelectItem>)}</SelectContent></Select></Field> : <Field label="Customer" full><Select value={form.customerId} onValueChange={(v) => setForm({ ...form, customerId: v })}><SelectTrigger><SelectValue placeholder="Select customer" /></SelectTrigger><SelectContent>{customers.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent></Select></Field>}

            <Field label="Delivery date"><Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
            <Field label="Vehicle number"><Input value={form.vehicleNo} onChange={(e) => setForm({ ...form, vehicleNo: e.target.value })} /></Field>
            <Field label="Driver name"><Input value={form.driverName} onChange={(e) => setForm({ ...form, driverName: e.target.value })} /></Field>
            <Field label="LR number"><Input value={form.lrNumber} onChange={(e) => setForm({ ...form, lrNumber: e.target.value })} /></Field>
          </div>

          {mode === "so" && selectedSo && <div className="mt-4 space-y-2"><p className="text-xs font-semibold">Delivery quantities</p><div className="grid grid-cols-12 gap-2 border-b pb-2 text-xs text-muted-foreground"><div className="col-span-5">Product</div><div className="col-span-2 text-right">Ordered</div><div className="col-span-2 text-right">Delivered</div><div className="col-span-2 text-right">Remaining</div><div className="col-span-1" /></div>{dispatchables.map((l) => <div key={l.productId} className="grid grid-cols-12 items-center gap-2"><div className="col-span-5 text-sm">{l.name}<span className="ml-1 text-xs text-muted-foreground">({l.unit})</span></div><div className="col-span-2 text-right num text-sm">{num(l.ordered)}</div><div className="col-span-2 text-right num text-sm">{num(l.delivered)}</div><div className="col-span-2 text-right num font-medium text-sm">{num(l.pending)}</div><Input className="col-span-1" type="number" min="0" max={l.pending} step="any" value={qty[l.productId] ?? ""} onChange={(e) => { const v = e.target.value; if (v !== "" && Number(v) > l.pending) return toast.error(`Maximum ${num(l.pending)} ${l.unit}`); setQty({ ...qty, [l.productId]: v }); }} /></div>)}</div>}

          <Textarea className="mt-3" rows={2} placeholder="Remarks" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
          {mode === "so" && <p className="num text-right text-sm font-semibold">Delivery value: {inr(previewValue)}</p>}

          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={saving} onClick={() => void submit()}>{saving ? "Posting..." : "Post delivery"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
