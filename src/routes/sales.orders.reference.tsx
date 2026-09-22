import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ClipboardCheck, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { DocTrail, Field, StatusBadge } from "@/components/erp/DocBits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { today, useErp } from "@/lib/erp/store";
import { createSalesOrder, docStats, nextDocNo, setSoStatus, type SalesLineDraft } from "@/lib/erp/docs";
import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";

export const Route = createFileRoute("/sales/orders/reference")({
  head: () => ({
    meta: [
      { title: "Sales Orders — MiniTally ERP" },
      { name: "description", content: "Track confirmed customer orders, delivery progress and invoicing status." },
      { property: "og:title", content: "Sales Orders — MiniTally ERP" },
      { property: "og:description", content: "Sales order to delivery to invoice tracking." },
    ],
  }),
  component: () => (
    <AppShell>
      <SalesOrdersPage />
    </AppShell>
  ),
});

const blank = (): SalesLineDraft => ({ productId: "", quantity: 0, rate: 0 });

function SalesOrdersPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const user = session?.username ?? "system";
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<SalesLineDraft[]>([blank()]);
  const [form, setForm] = useState({ date: today(), deliveryDate: today(), customerId: "", notes: "" });

  const stats = docStats(state);
  const total = useMemo(
    () =>
      lines.reduce((t, l) => {
        const p = state.products.find((x) => x.id === l.productId);
        const taxable = l.quantity * l.rate;
        return t + taxable + (taxable * (p?.gstPercent ?? 18)) / 100;
      }, 0),
    [lines, state.products],
  );

  const submit = () => {
    try {
      const no = createSalesOrder({ ...form, lines }, user);
      toast.success(`${no} created`);
      setOpen(false);
      setLines([blank()]);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Sales Orders"
        subtitle="Confirmed customer orders — deliveries draw against the ordered quantity."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New sales order
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Open orders" value={num(stats.openSos)} tone="primary" icon={<ClipboardCheck className="h-4 w-4" />} />
        <StatCard label="Order book value" value={inr(stats.soValue)} />
        <StatCard label="Delivered" value={num(state.salesOrders.filter((o) => o.status === "Delivered" || o.status === "Invoiced").length)} tone="success" />
        <StatCard label="Total orders" value={num(state.salesOrders.length)} />
      </div>

      <DataTable
        rows={state.salesOrders}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.soNo} ${r.customerName} ${r.status} ${r.quoteNo ?? ""} ${r.lines.map((l) => l.productName).join(" ")}`}
        columns={[
          { key: "no", header: "SO No", value: (r) => r.soNo, render: (r) => <span className="num font-medium">{r.soNo}</span> },
          { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "customer", header: "Customer", value: (r) => r.customerName },
          { key: "delivery", header: "Delivery by", value: (r) => r.deliveryDate, render: (r) => <span className="num">{dmy(r.deliveryDate)}</span> },
          {
            key: "progress",
            header: "Delivered",
            align: "right",
            value: (r) => r.lines.reduce((t, l) => t + l.deliveredQty, 0),
            render: (r) => (
              <span className="num text-xs">
                {num(r.lines.reduce((t, l) => t + l.deliveredQty, 0))} / {num(r.lines.reduce((t, l) => t + l.quantity, 0))}
              </span>
            ),
          },
          { key: "value", header: "Value", align: "right", value: (r) => r.grandTotal, render: (r) => <span className="num">{inr(r.grandTotal)}</span> },
          { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
          { key: "trail", header: "Trail", render: (r) => <DocTrail steps={[r.quoteNo, r.soNo, r.deliveryNos[0], r.invoiceNo]} /> },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (r) =>
              r.status === "Open" || r.status === "Partially Delivered" ? (
                <Button size="sm" variant="ghost" onClick={() => setSoStatus(r.id, "Cancelled", user)}>
                  Cancel
                </Button>
              ) : null,
          },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>New sales order</DialogTitle>
            <DialogDescription>Numbered {nextDocNo(state, "SO", form.date)} on save.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
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
            <Field label="Order date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Delivery date">
              <Input type="date" value={form.deliveryDate} onChange={(e) => setForm({ ...form, deliveryDate: e.target.value })} />
            </Field>
          </div>

          <div className="mt-3 space-y-2">
            {lines.map((l, i) => (
              <div key={i} className="grid grid-cols-12 items-end gap-2">
                <div className="col-span-12 sm:col-span-6">
                  <Select
                    value={l.productId}
                    onValueChange={(v) =>
                      setLines(lines.map((x, xi) => (xi === i ? { ...x, productId: v, rate: state.products.find((p) => p.id === v)?.sellingPrice ?? 0 } : x)))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Product" />
                    </SelectTrigger>
                    <SelectContent>
                      {state.products.map((p) => (
                        <SelectItem key={p.id} value={p.id}>
                          {p.name} · stock {num(p.stock)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Input className="col-span-5 sm:col-span-2" type="number" placeholder="Qty" value={l.quantity || ""} onChange={(e) => setLines(lines.map((x, xi) => (xi === i ? { ...x, quantity: Number(e.target.value) } : x)))} />
                <Input className="col-span-5 sm:col-span-3" type="number" placeholder="Rate" value={l.rate || ""} onChange={(e) => setLines(lines.map((x, xi) => (xi === i ? { ...x, rate: Number(e.target.value) } : x)))} />
                <Button variant="ghost" size="icon" className="col-span-2 sm:col-span-1" onClick={() => setLines(lines.length > 1 ? lines.filter((_, xi) => xi !== i) : lines)}>
                  <Trash2 className="text-destructive h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button variant="outline" size="sm" onClick={() => setLines([...lines, blank()])}>
              <Plus className="mr-1 h-3.5 w-3.5" /> Add line
            </Button>
          </div>

          <Textarea className="mt-3" rows={2} placeholder="Notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <p className="num mt-2 text-right text-sm font-semibold">Order value: {inr(total)}</p>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Save order</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
