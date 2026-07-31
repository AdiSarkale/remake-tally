import { useState } from "react";
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { createInvoice, today, useErp } from "@/lib/erp/store";
import { createDelivery, defaultWarehouse, linkInvoiceToDelivery, nextDocNo } from "@/lib/erp/docs";
import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";

export const Route = createFileRoute("/sales/deliveries")({
  head: () => ({
    meta: [
      { title: "Delivery Notes — MiniTally ERP" },
      { name: "description", content: "Dispatch goods with vehicle, driver and LR details; stock leaves on dispatch and invoices link back." },
      { property: "og:title", content: "Delivery Notes — MiniTally ERP" },
      { property: "og:description", content: "Dispatch documentation and invoicing for MiniTally ERP." },
    ],
  }),
  component: () => (
    <AppShell>
      <DeliveriesPage />
    </AppShell>
  ),
});

function DeliveriesPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const user = session?.username ?? "system";
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    date: today(),
    soId: "",
    customerId: "",
    warehouseId: defaultWarehouse(state),
    vehicleNo: "",
    driverName: "",
    lrNumber: "",
    remarks: "",
  });
  const [qty, setQty] = useState<Record<string, string>>({});

  const so = state.salesOrders.find((o) => o.id === form.soId);
  const openSos = state.salesOrders.filter((o) => o.status === "Open" || o.status === "Partially Delivered");
  const dispatchables = so
    ? so.lines.map((l) => ({ productId: l.productId, name: l.productName, unit: l.unit, pending: l.quantity - l.deliveredQty }))
    : state.products.map((p) => ({ productId: p.id, name: p.name, unit: p.unit, pending: p.stock }));

  const submit = () => {
    try {
      const dnNo = createDelivery(
        {
          date: form.date,
          soId: form.soId || undefined,
          customerId: so?.customerId ?? form.customerId,
          warehouseId: form.warehouseId,
          vehicleNo: form.vehicleNo,
          driverName: form.driverName,
          lrNumber: form.lrNumber,
          remarks: form.remarks,
          foc: false,
          lines: Object.entries(qty)
            .filter(([, v]) => Number(v) > 0)
            .map(([productId, v]) => ({ productId, quantity: Number(v) })),
        },
        user,
      );
      toast.success(`${dnNo} dispatched — finished goods reduced`);
      setOpen(false);
      setQty({});
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const invoiceFor = (deliveryId: string) => {
    const dn = state.deliveries.find((d) => d.id === deliveryId);
    if (!dn) return;
    try {
      const invoiceNo = createInvoice(
        {
          date: today(),
          customerId: dn.customerId,
          poReference: dn.soNo ?? dn.dnNo,
          notes: `Against delivery note ${dn.dnNo}`,
          status: "Unpaid",
          lines: dn.lines.map((l) => ({ productId: l.productId, quantity: l.quantity, rate: l.rate, discountPercent: 0 })),
        },
        user,
        { skipStock: true },
      );
      linkInvoiceToDelivery(dn.id, invoiceNo);
      toast.success(`${invoiceNo} raised from ${dn.dnNo}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const rows = state.deliveries.filter((d) => !d.foc);

  return (
    <>
      <PageHeader
        title="Delivery Notes"
        subtitle="Dispatch documentation — stock leaves here, the invoice is raised against the delivery."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New dispatch
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Dispatches" value={num(rows.length)} tone="primary" icon={<Truck className="h-4 w-4" />} />
        <StatCard label="Awaiting invoice" value={num(rows.filter((d) => !d.invoiceNo).length)} tone="warning" />
        <StatCard label="Invoiced" value={num(rows.filter((d) => d.invoiceNo).length)} tone="success" />
        <StatCard label="Pieces dispatched" value={num(rows.reduce((t, d) => t + d.lines.reduce((x, l) => x + l.quantity, 0), 0))} />
      </div>

      <DataTable
        rows={rows}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.dnNo} ${r.customerName} ${r.vehicleNo} ${r.driverName} ${r.lrNumber} ${r.soNo ?? ""}`}
        columns={[
          { key: "no", header: "DN No", value: (r) => r.dnNo, render: (r) => <span className="num font-medium">{r.dnNo}</span> },
          { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "customer", header: "Customer", value: (r) => r.customerName },
          { key: "items", header: "Dispatched", render: (r) => <span className="text-muted-foreground text-xs">{r.lines.map((l) => `${l.productName} ×${num(l.quantity)}`).join(", ")}</span> },
          { key: "vehicle", header: "Vehicle", value: (r) => r.vehicleNo, render: (r) => <span className="num text-xs">{r.vehicleNo}</span> },
          { key: "driver", header: "Driver", value: (r) => r.driverName },
          { key: "lr", header: "LR No", value: (r) => r.lrNumber, render: (r) => <span className="num text-xs">{r.lrNumber}</span> },
          { key: "value", header: "Value", align: "right", render: (r) => <span className="num">{inr(r.lines.reduce((t, l) => t + l.quantity * l.rate, 0))}</span> },
          { key: "trail", header: "Trail", render: (r) => <DocTrail steps={[r.soNo, r.dnNo, r.invoiceNo]} /> },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (r) =>
              r.invoiceNo ? (
                <Badge variant="secondary" className="num">{r.invoiceNo}</Badge>
              ) : (
                <Button size="sm" onClick={() => invoiceFor(r.id)}>
                  <Receipt className="mr-1 h-3.5 w-3.5" /> Invoice
                </Button>
              ),
          },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>New delivery note</DialogTitle>
            <DialogDescription>Numbered {nextDocNo(state, "DN", form.date)} on save.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Against sales order" full>
              <Select value={form.soId || "none"} onValueChange={(v) => { setForm({ ...form, soId: v === "none" ? "" : v }); setQty({}); }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Direct dispatch (no SO)</SelectItem>
                  {openSos.map((o) => (
                    <SelectItem key={o.id} value={o.id}>
                      {o.soNo} · {o.customerName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            {!form.soId && (
              <Field label="Customer" full>
                <Select value={form.customerId} onValueChange={(v) => setForm({ ...form, customerId: v })}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select customer" />
                  </SelectTrigger>
                  <SelectContent>
                    {state.customers.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
            )}
            <Field label="Dispatch date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Dispatch from">
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
            <Field label="Vehicle number">
              <Input value={form.vehicleNo} onChange={(e) => setForm({ ...form, vehicleNo: e.target.value })} placeholder="MH 14 AB 1234" />
            </Field>
            <Field label="Driver name">
              <Input value={form.driverName} onChange={(e) => setForm({ ...form, driverName: e.target.value })} />
            </Field>
            <Field label="LR number">
              <Input value={form.lrNumber} onChange={(e) => setForm({ ...form, lrNumber: e.target.value })} />
            </Field>
          </div>

          <div className="mt-3 space-y-2">
            <p className="text-xs font-semibold">Dispatch quantities</p>
            {dispatchables.map((d) => (
              <div key={d.productId} className="grid grid-cols-12 items-center gap-2">
                <div className="col-span-8 text-sm">
                  <p>{d.name}</p>
                  <p className="text-muted-foreground num text-xs">
                    available {num(d.pending, 2)} {d.unit}
                  </p>
                </div>
                <Input
                  className="col-span-4"
                  type="number"
                  placeholder="Qty"
                  value={qty[d.productId] ?? ""}
                  onChange={(e) => setQty({ ...qty, [d.productId]: e.target.value })}
                />
              </div>
            ))}
          </div>

          <Textarea className="mt-3" rows={2} placeholder="Remarks" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Post dispatch</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
