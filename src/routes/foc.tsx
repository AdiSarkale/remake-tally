import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Gift, Plus } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Field } from "@/components/erp/DocBits";
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
import { today, useErp } from "@/lib/erp/store";
import { createDelivery, defaultWarehouse, nextDocNo } from "@/lib/erp/docs";
import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";

export const Route = createFileRoute("/foc")({
  head: () => ({
    meta: [
      { title: "Free of Cost Issues — MiniTally ERP" },
      { name: "description", content: "Issue samples, warranty and replacement material at zero value while inventory still reduces." },
      { property: "og:title", content: "Free of Cost Issues — MiniTally ERP" },
      { property: "og:description", content: "FOC dispatch register with separate reporting." },
    ],
  }),
  component: () => (
    <AppShell>
      <FocPage />
    </AppShell>
  ),
});

const PURPOSES = ["Sample", "Warranty replacement", "Rework replacement", "Marketing", "Trial lot"];

function FocPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  const [qty, setQty] = useState<Record<string, string>>({});
  const [form, setForm] = useState({
    date: today(),
    customerId: "",
    warehouseId: defaultWarehouse(state),
    focPurpose: "Sample",
    vehicleNo: "",
    driverName: "",
    remarks: "",
  });

  const rows = state.deliveries.filter((d) => d.foc);
  const notionalValue = rows.reduce(
    (t, d) => t + d.lines.reduce((x, l) => x + l.quantity * (state.products.find((p) => p.id === l.productId)?.sellingPrice ?? 0), 0),
    0,
  );

  const submit = () => {
    try {
      const no = createDelivery(
        {
          date: form.date,
          customerId: form.customerId,
          warehouseId: form.warehouseId,
          vehicleNo: form.vehicleNo,
          driverName: form.driverName,
          lrNumber: "-",
          remarks: form.remarks,
          foc: true,
          focPurpose: form.focPurpose,
          lines: Object.entries(qty)
            .filter(([, v]) => Number(v) > 0)
            .map(([productId, v]) => ({ productId, quantity: Number(v) })),
        },
        session?.username ?? "system",
      );
      toast.success(`${no} issued free of cost — stock reduced, no invoice value`);
      setOpen(false);
      setQty({});
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Free of Cost Issues"
        subtitle="Samples, warranty and replacement despatches — inventory reduces, nothing is billed."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New FOC issue
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="FOC issues" value={num(rows.length)} tone="primary" icon={<Gift className="h-4 w-4" />} />
        <StatCard label="Pieces issued" value={num(rows.reduce((t, d) => t + d.lines.reduce((x, l) => x + l.quantity, 0), 0))} />
        <StatCard label="Notional value given away" value={inr(notionalValue)} tone="warning" hint="At list selling price" />
        <StatCard label="This month" value={num(rows.filter((d) => d.date.startsWith(today().slice(0, 7))).length)} tone="success" />
      </div>

      <DataTable
        rows={rows}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.dnNo} ${r.customerName} ${r.focPurpose ?? ""} ${r.lines.map((l) => l.productName).join(" ")}`}
        columns={[
          { key: "no", header: "FOC No", value: (r) => r.dnNo, render: (r) => <span className="num font-medium">{r.dnNo}</span> },
          { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "customer", header: "Issued to", value: (r) => r.customerName },
          { key: "purpose", header: "Purpose", value: (r) => r.focPurpose ?? "", render: (r) => <Badge variant="secondary">{r.focPurpose}</Badge> },
          { key: "items", header: "Items", render: (r) => <span className="text-muted-foreground text-xs">{r.lines.map((l) => `${l.productName} ×${num(l.quantity)}`).join(", ")}</span> },
          {
            key: "value",
            header: "Notional value",
            align: "right",
            render: (r) => (
              <span className="num">
                {inr(r.lines.reduce((t, l) => t + l.quantity * (state.products.find((p) => p.id === l.productId)?.sellingPrice ?? 0), 0))}
              </span>
            ),
          },
          { key: "billed", header: "Billed", render: () => <Badge variant="outline">₹0 · FOC</Badge> },
          { key: "remarks", header: "Remarks", className: "text-muted-foreground text-xs", value: (r) => r.remarks },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>New free of cost issue</DialogTitle>
            <DialogDescription>Numbered {nextDocNo(state, "FOC", form.date)} — no commercial value is recorded.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Customer / receiver" full>
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
            <Field label="Issue date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Purpose">
              <Select value={form.focPurpose} onValueChange={(v) => setForm({ ...form, focPurpose: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PURPOSES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Issue from">
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
            <Field label="Vehicle">
              <Input value={form.vehicleNo} onChange={(e) => setForm({ ...form, vehicleNo: e.target.value })} />
            </Field>
            <Field label="Driver">
              <Input value={form.driverName} onChange={(e) => setForm({ ...form, driverName: e.target.value })} />
            </Field>
          </div>

          <div className="mt-3 space-y-2">
            <p className="text-xs font-semibold">Quantities</p>
            {state.products.map((p) => (
              <div key={p.id} className="grid grid-cols-12 items-center gap-2">
                <div className="col-span-8 text-sm">
                  <p>{p.name}</p>
                  <p className="text-muted-foreground num text-xs">
                    stock {num(p.stock)} {p.unit}
                  </p>
                </div>
                <Input className="col-span-4" type="number" placeholder="Qty" value={qty[p.id] ?? ""} onChange={(e) => setQty({ ...qty, [p.id]: e.target.value })} />
              </div>
            ))}
          </div>

          <Textarea className="mt-3" rows={2} placeholder="Remarks" value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Issue FOC</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
