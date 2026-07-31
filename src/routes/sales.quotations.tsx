import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FileSignature, Plus, Trash2 } from "lucide-react";
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
import { createQuotation, docStats, nextDocNo, quoteToSalesOrder, setQuoteStatus, type SalesLineDraft } from "@/lib/erp/docs";
import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";

export const Route = createFileRoute("/sales/quotations")({
  head: () => ({
    meta: [
      { title: "Quotations — MiniTally ERP" },
      { name: "description", content: "Prepare customer quotations with GST pricing and convert accepted quotes into sales orders." },
      { property: "og:title", content: "Quotations — MiniTally ERP" },
      { property: "og:description", content: "Quote to sales order conversion for MiniTally ERP." },
    ],
  }),
  component: () => (
    <AppShell>
      <QuotationsPage />
    </AppShell>
  ),
});

const blank = (): SalesLineDraft => ({ productId: "", quantity: 0, rate: 0 });

function QuotationsPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const user = session?.username ?? "system";
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<SalesLineDraft[]>([blank()]);
  const [form, setForm] = useState({ date: today(), validUntil: today(), customerId: "", notes: "" });

  const stats = docStats(state);
  const totals = useMemo(() => {
    let taxable = 0;
    let tax = 0;
    lines.forEach((l) => {
      const p = state.products.find((x) => x.id === l.productId);
      const t = l.quantity * l.rate;
      taxable += t;
      tax += (t * (p?.gstPercent ?? 18)) / 100;
    });
    return { taxable, tax, grand: taxable + tax };
  }, [lines, state.products]);

  const submit = () => {
    try {
      const no = createQuotation({ ...form, lines }, user);
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
        title="Quotations"
        subtitle="Offer prices to customers, then convert an accepted quote straight into a sales order."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New quotation
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Live quotations" value={num(stats.liveQuotes)} tone="primary" icon={<FileSignature className="h-4 w-4" />} />
        <StatCard label="Converted to SO" value={num(state.quotations.filter((q) => q.status === "Converted to SO").length)} tone="success" />
        <StatCard label="Quoted value" value={inr(state.quotations.reduce((t, q) => t + q.grandTotal, 0))} />
        <StatCard label="Total quotations" value={num(state.quotations.length)} />
      </div>

      <DataTable
        rows={state.quotations}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.quoteNo} ${r.customerName} ${r.status} ${r.lines.map((l) => l.productName).join(" ")}`}
        columns={[
          { key: "no", header: "Quote No", value: (r) => r.quoteNo, render: (r) => <span className="num font-medium">{r.quoteNo}</span> },
          { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "customer", header: "Customer", value: (r) => r.customerName },
          { key: "valid", header: "Valid until", value: (r) => r.validUntil, render: (r) => <span className="num">{dmy(r.validUntil)}</span> },
          { key: "items", header: "Items", render: (r) => <span className="text-muted-foreground text-xs">{r.lines.map((l) => `${l.productName} ×${num(l.quantity)}`).join(", ")}</span> },
          { key: "value", header: "Value", align: "right", value: (r) => r.grandTotal, render: (r) => <span className="num">{inr(r.grandTotal)}</span> },
          { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
          { key: "trail", header: "Trail", render: (r) => <DocTrail steps={[r.quoteNo, r.soNo]} /> },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (r) => (
              <div className="flex justify-end gap-1">
                {r.status === "Draft" && (
                  <Button size="sm" variant="outline" onClick={() => setQuoteStatus(r.id, "Sent", user)}>
                    Mark sent
                  </Button>
                )}
                {(r.status === "Sent" || r.status === "Accepted") && (
                  <Button
                    size="sm"
                    onClick={() => {
                      try {
                        const soNo = quoteToSalesOrder(r.id, today(), user);
                        toast.success(`${soNo} created from ${r.quoteNo}`);
                      } catch (e) {
                        toast.error((e as Error).message);
                      }
                    }}
                  >
                    Convert to SO
                  </Button>
                )}
              </div>
            ),
          },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>New quotation</DialogTitle>
            <DialogDescription>Numbered {nextDocNo(state, "QT", form.date)} on save.</DialogDescription>
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
            <Field label="Quote date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Valid until">
              <Input type="date" value={form.validUntil} onChange={(e) => setForm({ ...form, validUntil: e.target.value })} />
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
                          {p.name}
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

          <Textarea className="mt-3" rows={2} placeholder="Terms / notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />

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
              <p className="text-muted-foreground text-xs">Total</p>
              <p className="num text-primary font-semibold">{inr(totals.grand)}</p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Save quotation</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
