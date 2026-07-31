import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FileText, Plus, Printer, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { createInvoice, nextInvoiceNo, salesStats, setInvoiceStatus, today, useErp } from "@/lib/erp/store";
import { buildLine, stateCode, totalsFor, type LineDraft } from "@/lib/erp/gst";
import { dmy, inr, inr2, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";
import type { Invoice } from "@/lib/erp/types";

export const Route = createFileRoute("/invoices")({
  head: () => ({
    meta: [
      { title: "Sales Invoices — MiniTally ERP" },
      {
        name: "description",
        content:
          "Raise GST sales invoices with auto sequential numbering, CGST/SGST/IGST tax, duplicate checks and searchable invoice history.",
      },
      { property: "og:title", content: "Sales Invoices — MiniTally ERP" },
      { property: "og:description", content: "GST invoicing with sequential numbers and searchable history." },
    ],
  }),
  component: () => (
    <AppShell>
      <InvoicesPage />
    </AppShell>
  ),
});

const emptyLine = (): LineDraft => ({ productId: "", quantity: 1, rate: 0, discountPercent: 0 });

function InvoicesPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const stats = salesStats(state);
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<Invoice | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    date: today(),
    customerId: "",
    poReference: "",
    notes: "",
    status: "Unpaid" as Invoice["status"],
  });
  const [lines, setLines] = useState<LineDraft[]>([emptyLine()]);

  const customer = state.customers.find((c) => c.id === form.customerId);
  const interState = customer ? stateCode(customer.gstNumber) !== stateCode(state.settings.gstNumber) : false;

  const preview = useMemo(() => {
    const built = lines
      .filter((l) => l.productId && l.quantity > 0)
      .map((l) => {
        const p = state.products.find((x) => x.id === l.productId)!;
        return buildLine(p, l, interState);
      });
    return { built, totals: totalsFor(built) };
  }, [lines, interState, state.products]);

  const setLine = (i: number, patch: Partial<LineDraft>) =>
    setLines((prev) => prev.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  const reset = () => {
    setForm({ date: today(), customerId: "", poReference: "", notes: "", status: "Unpaid" });
    setLines([emptyLine()]);
  };

  const submit = () => {
    if (saving) return; // guards double-click duplicates
    setSaving(true);
    try {
      const no = createInvoice({ ...form, lines }, session?.username ?? "system");
      toast.success(`Invoice ${no} created`);
      setOpen(false);
      reset();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create invoice");
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Sales Invoices"
        subtitle="Invoice numbers run in sequence; posting an invoice removes finished goods from stock."
        actions={
          <Button
            onClick={() => {
              reset();
              setOpen(true);
            }}
          >
            <Plus className="mr-1 h-4 w-4" /> New invoice
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Invoices raised" value={num(stats.count)} />
        <StatCard label="Sales this month" value={inr(stats.monthValue)} tone="success" />
        <StatCard label="GST collected (month)" value={inr(stats.monthTax)} hint="CGST + SGST + IGST" />
        <StatCard label="Outstanding" value={inr(stats.outstanding)} tone="warning" />
      </div>

      <DataTable
        rows={state.invoices}
        rowKey={(i) => i.id}
        pageSize={12}
        empty="No invoices yet."
        searchable={(i) =>
          `${i.invoiceNo} ${i.customerName} ${i.customerGst} ${i.poReference} ${i.status} ${i.grandTotal} ${i.lines
            .map((l) => l.productName)
            .join(" ")}`
        }
        columns={[
          { key: "no", header: "Invoice no.", value: (i) => i.invoiceNo, className: "num text-xs font-medium" },
          { key: "date", header: "Date", value: (i) => i.date, render: (i) => dmy(i.date) },
          { key: "customer", header: "Customer", value: (i) => i.customerName },
          { key: "po", header: "PO ref", value: (i) => i.poReference, className: "text-muted-foreground text-xs" },
          {
            key: "taxable",
            header: "Taxable",
            align: "right",
            value: (i) => i.taxable,
            render: (i) => <span className="num">{inr2(i.taxable)}</span>,
          },
          {
            key: "tax",
            header: "GST",
            align: "right",
            value: (i) => i.cgst + i.sgst + i.igst,
            render: (i) => (
              <span className="num text-xs text-muted-foreground">
                {i.interState ? "IGST " : "C+S "}
                {inr2(i.cgst + i.sgst + i.igst)}
              </span>
            ),
          },
          {
            key: "total",
            header: "Total",
            align: "right",
            value: (i) => i.grandTotal,
            render: (i) => <span className="num font-semibold">{inr2(i.grandTotal)}</span>,
          },
          {
            key: "status",
            header: "Status",
            value: (i) => i.status,
            render: (i) => (
              <Badge variant={i.status === "Paid" ? "secondary" : "outline"}>{i.status}</Badge>
            ),
          },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (i) => (
              <Button variant="ghost" size="sm" onClick={() => setView(i)}>
                <FileText className="mr-1 h-4 w-4" /> Open
              </Button>
            ),
          },
        ]}
      />

      {/* -------- New invoice -------- */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>New sales invoice</DialogTitle>
            <DialogDescription>
              Will be numbered <span className="num font-medium">{nextInvoiceNo(state)}</span>. GST is{" "}
              {interState ? "IGST (inter-state)" : "CGST + SGST (intra-state)"} based on the customer's GSTIN.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3 sm:grid-cols-4">
            <div className="sm:col-span-2">
              <Label className="mb-1.5 block text-xs">Customer</Label>
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
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Date</Label>
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">PO reference</Label>
              <Input
                value={form.poReference}
                onChange={(e) => setForm({ ...form, poReference: e.target.value })}
                placeholder="PO/1234"
              />
            </div>
          </div>

          <div className="mt-2 space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Line items</Label>
              <Button variant="outline" size="sm" onClick={() => setLines((p) => [...p, emptyLine()])}>
                <Plus className="mr-1 h-3.5 w-3.5" /> Add line
              </Button>
            </div>
            {lines.map((l, i) => {
              const product = state.products.find((p) => p.id === l.productId);
              return (
                <div key={i} className="grid grid-cols-12 items-end gap-2 rounded-md border p-2">
                  <div className="col-span-12 sm:col-span-4">
                    <Label className="mb-1 block text-[10px] text-muted-foreground">Product</Label>
                    <Select
                      value={l.productId}
                      onValueChange={(v) => {
                        const p = state.products.find((x) => x.id === v);
                        setLine(i, { productId: v, rate: p?.sellingPrice ?? 0 });
                      }}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select" />
                      </SelectTrigger>
                      <SelectContent>
                        {state.products.map((p) => (
                          <SelectItem key={p.id} value={p.id}>
                            {p.code} · {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="col-span-4 sm:col-span-2">
                    <Label className="mb-1 block text-[10px] text-muted-foreground">
                      Qty{product ? ` (${num(product.stock)} left)` : ""}
                    </Label>
                    <Input
                      type="number"
                      min="0"
                      value={l.quantity}
                      onChange={(e) => setLine(i, { quantity: Number(e.target.value) })}
                    />
                  </div>
                  <div className="col-span-4 sm:col-span-2">
                    <Label className="mb-1 block text-[10px] text-muted-foreground">Rate</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={l.rate}
                      onChange={(e) => setLine(i, { rate: Number(e.target.value) })}
                    />
                  </div>
                  <div className="col-span-4 sm:col-span-2">
                    <Label className="mb-1 block text-[10px] text-muted-foreground">Disc %</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={l.discountPercent}
                      onChange={(e) => setLine(i, { discountPercent: Number(e.target.value) })}
                    />
                  </div>
                  <div className="col-span-10 sm:col-span-1 text-right">
                    <span className="num text-xs text-muted-foreground">
                      {product ? `${product.gstPercent}%` : "—"}
                    </span>
                  </div>
                  <div className="col-span-2 sm:col-span-1 text-right">
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={lines.length === 1}
                      onClick={() => setLines((p) => p.filter((_, idx) => idx !== i))}
                      aria-label="Remove line"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            <div>
              <Label className="mb-1.5 block text-xs">Notes</Label>
              <Textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              <div className="mt-3">
                <Label className="mb-1.5 block text-xs">Payment status</Label>
                <Select
                  value={form.status}
                  onValueChange={(v) => setForm({ ...form, status: v as Invoice["status"] })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Unpaid">Unpaid</SelectItem>
                    <SelectItem value="Paid">Paid</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="panel space-y-1.5 p-3 text-sm">
              <Row label="Sub total" value={inr2(preview.totals.subTotal)} />
              <Row label="Discount" value={`− ${inr2(preview.totals.discountTotal)}`} />
              <Row label="Taxable value" value={inr2(preview.totals.taxable)} />
              {interState ? (
                <Row label="IGST" value={inr2(preview.totals.igst)} />
              ) : (
                <>
                  <Row label="CGST" value={inr2(preview.totals.cgst)} />
                  <Row label="SGST" value={inr2(preview.totals.sgst)} />
                </>
              )}
              <Row label="Round off" value={inr2(preview.totals.roundOff)} />
              <div className="mt-1 border-t pt-2">
                <Row label="Grand total" value={inr2(preview.totals.grandTotal)} bold />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? "Saving…" : "Save invoice"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* -------- Invoice view / print -------- */}
      <Dialog open={!!view} onOpenChange={(o) => !o && setView(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          {view && (
            <>
              <DialogHeader>
                <DialogTitle>Tax invoice {view.invoiceNo}</DialogTitle>
                <DialogDescription>
                  {dmy(view.date)} · {view.customerName}
                </DialogDescription>
              </DialogHeader>
              <div id="invoice-print" className="space-y-4 text-sm">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <p className="font-semibold">{state.settings.name}</p>
                    <p className="text-xs text-muted-foreground">{state.settings.address}</p>
                    <p className="num text-xs text-muted-foreground">GSTIN {state.settings.gstNumber}</p>
                  </div>
                  <div className="sm:text-right">
                    <p className="font-semibold">{view.customerName}</p>
                    <p className="text-xs text-muted-foreground">{view.customerAddress}</p>
                    <p className="num text-xs text-muted-foreground">GSTIN {view.customerGst}</p>
                    <p className="num text-xs text-muted-foreground">
                      Place of supply {view.placeOfSupply} · {view.interState ? "Inter-state" : "Intra-state"}
                    </p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b bg-muted/50 text-left">
                        <th className="px-2 py-2">Item</th>
                        <th className="px-2 py-2">HSN</th>
                        <th className="px-2 py-2 text-right">Qty</th>
                        <th className="px-2 py-2 text-right">Rate</th>
                        <th className="px-2 py-2 text-right">Disc%</th>
                        <th className="px-2 py-2 text-right">Taxable</th>
                        <th className="px-2 py-2 text-right">GST</th>
                        <th className="px-2 py-2 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {view.lines.map((l, i) => (
                        <tr key={i} className="border-b last:border-0">
                          <td className="px-2 py-2">{l.productName}</td>
                          <td className="num px-2 py-2">{l.hsnCode}</td>
                          <td className="num px-2 py-2 text-right">
                            {num(l.quantity)} {l.unit}
                          </td>
                          <td className="num px-2 py-2 text-right">{inr2(l.rate)}</td>
                          <td className="num px-2 py-2 text-right">{num(l.discountPercent, 2)}</td>
                          <td className="num px-2 py-2 text-right">{inr2(l.taxable)}</td>
                          <td className="num px-2 py-2 text-right">
                            {l.gstPercent}% · {inr2(l.cgst + l.sgst + l.igst)}
                          </td>
                          <td className="num px-2 py-2 text-right font-medium">{inr2(l.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="ml-auto w-full max-w-xs space-y-1.5">
                  <Row label="Taxable value" value={inr2(view.taxable)} />
                  {view.interState ? (
                    <Row label="IGST" value={inr2(view.igst)} />
                  ) : (
                    <>
                      <Row label="CGST" value={inr2(view.cgst)} />
                      <Row label="SGST" value={inr2(view.sgst)} />
                    </>
                  )}
                  <Row label="Round off" value={inr2(view.roundOff)} />
                  <div className="border-t pt-2">
                    <Row label="Grand total" value={inr2(view.grandTotal)} bold />
                  </div>
                </div>
                {view.notes && <p className="text-xs text-muted-foreground">Notes: {view.notes}</p>}
              </div>
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setInvoiceStatus(view.id, view.status === "Paid" ? "Unpaid" : "Paid", session?.username ?? "system");
                    setView(null);
                  }}
                >
                  Mark {view.status === "Paid" ? "Unpaid" : "Paid"}
                </Button>
                <Button onClick={() => window.print()}>
                  <Printer className="mr-1 h-4 w-4" /> Print / PDF
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between">
      <span className={bold ? "font-semibold" : "text-muted-foreground"}>{label}</span>
      <span className={`num ${bold ? "text-base font-bold" : ""}`}>{value}</span>
    </div>
  );
}
