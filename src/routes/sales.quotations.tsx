import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FileSignature, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/DocBits";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createQuotation,
  convertQuotationToSalesOrder,
  getCustomers,
  getNextQuotationNumber,
  getProducts,
  getQuotations,
  lookupCustomerPO,
  updateQuotationStatus,
  type ProductData,
  type PartyData,
  type QuotationData,
  type QuotationStatus,
  type CustomerPOData,
} from "@/lib/erp/api";
import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/sales/quotations")({
  head: () => ({ meta: [{ title: "Quotations — MiniTally ERP" }] }),
  component: () => (
    <AppShell>
      <QuotationsPage />
    </AppShell>
  ),
});

type DraftLine = {
  productId: string;
  quantity: number;
  rate: number;
  discountPercent: number;
  gstRate: number | null;
};

const blankLine = (): DraftLine => ({
  productId: "",
  quantity: 0,
  rate: 0,
  discountPercent: 0,
  gstRate: null,
});

const today = () => new Date().toISOString().slice(0, 10);

function QuotationsPage() {
  const [quotations, setQuotations] = useState<QuotationData[]>([]);
  const [products, setProducts] = useState<ProductData[]>([]);
  const [customers, setCustomers] = useState<PartyData[]>([]);
  const [nextNo, setNextNo] = useState("QT0001");
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lines, setLines] = useState<DraftLine[]>([blankLine()]);
  const [poLookupLoading, setPoLookupLoading] = useState(false);
  const [poInfo, setPoInfo] = useState<CustomerPOData | null>(null);
  const [form, setForm] = useState({
    date: today(),
    validUntil: today(),
    customerId: "",
    poReference: "",
    notes: "",
    status: "Draft" as QuotationStatus,
  });

  async function load() {
    try {
      setLoading(true);
      const [q, p, c, n] = await Promise.all([
        getQuotations(),
        getProducts(),
        getCustomers(),
        getNextQuotationNumber(),
      ]);
      setQuotations(q);
      setProducts(p);
      setCustomers(c.filter((x) => x.kind === "customer"));
      setNextNo(n.quotation_no);
    } catch (e) {
      toast.error((e as Error).message || "Failed to load quotations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const totals = useMemo(() => {
    let subtotal = 0;
    let discount = 0;
    let taxable = 0;
    let tax = 0;
    for (const line of lines) {
      const gross = line.quantity * line.rate;
      const disc = gross * line.discountPercent / 100;
      const tx = gross - disc;
      const product = products.find((p) => p.id === line.productId);
      const gst = line.gstRate ?? product?.gst_rate ?? 18;
      subtotal += gross;
      discount += disc;
      taxable += tx;
      tax += tx * gst / 100;
    }
    return {
      subtotal: Math.round(subtotal * 100) / 100,
      discount: Math.round(discount * 100) / 100,
      taxable: Math.round(taxable * 100) / 100,
      tax: Math.round(tax * 100) / 100,
      grand: Math.round((taxable + tax) * 100) / 100,
    };
  }, [lines, products]);

  async function lookupPO() {
    const ref = form.poReference.trim();
    if (!ref) return;
    try {
      setPoLookupLoading(true);
      const po = await lookupCustomerPO(ref);
      setPoInfo(po);
      setForm((f) => ({
        ...f,
        customerId: po.customer_id,
        validUntil: po.delivery_date ?? f.validUntil,
      }));
      setLines(
        po.lines.map((line) => {
          const p = products.find((x) => x.id === line.product_id);
          return {
            productId: line.product_id,
            quantity: line.quantity,
            rate: line.rate ?? p?.selling_price ?? 0,
            discountPercent: 0,
            gstRate: null,
          };
        }),
      );
      toast.success(`PO ${po.po_no} loaded`);
    } catch (e) {
      setPoInfo(null);
      toast.error((e as Error).message || "Customer PO not found");
    } finally {
      setPoLookupLoading(false);
    }
  }

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((current) => current.map((line, i) => i === index ? { ...line, ...patch } : line));
  }

  function selectProduct(index: number, productId: string) {
    const product = products.find((p) => p.id === productId);
    updateLine(index, { productId, rate: product?.selling_price ?? 0, gstRate: null });
  }

  async function submit() {
    if (!form.customerId) return toast.error("Select a customer");
    const validLines = lines.filter((l) => l.productId && l.quantity > 0);
    if (!validLines.length) return toast.error("Add at least one product line");
    if (form.validUntil < form.date) return toast.error("Valid until cannot be before quotation date");

    try {
      setSaving(true);
      const created = await createQuotation({
        quotation_date: form.date,
        valid_until: form.validUntil || null,
        customer_id: form.customerId,
        po_reference: form.poReference,
        notes: form.notes,
        status: form.status,
        lines: validLines.map((line) => ({
          product_id: line.productId,
          quantity: line.quantity,
          rate: line.rate,
          discount_percent: line.discountPercent,
          gst_rate: line.gstRate,
        })),
      });
      toast.success(`${created.quotation_no} created`);
      setOpen(false);
      setForm({ date: today(), validUntil: today(), customerId: "", poReference: "", notes: "", status: "Draft" });
      setLines([blankLine()]);
      setPoInfo(null);
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to create quotation");
    } finally {
      setSaving(false);
    }
  }

  async function changeStatus(row: QuotationData, status: QuotationStatus) {
    try {
      await updateQuotationStatus(row.id, status);
      toast.success(`${row.quotation_no} marked ${status}`);
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to update quotation");
    }
  }

  async function convert(row: QuotationData) {
    if (row.status !== "Accepted") return toast.error("Only Accepted quotations can be converted");
    try {
      const so = await convertQuotationToSalesOrder(row.id);
      toast.success(`${row.quotation_no} converted to ${so.so_no}`);
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to convert quotation");
    }
  }

  return (
    <>
      <PageHeader
        title="Quotations"
        subtitle="Customer quotations with live masters, customer-PO lookup, discounts and custom GST."
        actions={<Button onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New quotation</Button>}
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Live quotations" value={num(quotations.filter((q) => !["Rejected", "Converted"].includes(q.status)).length)} tone="primary" icon={<FileSignature className="h-4 w-4" />} />
        <StatCard label="Accepted" value={num(quotations.filter((q) => q.status === "Accepted").length)} tone="success" />
        <StatCard label="Quoted value" value={inr(quotations.reduce((t, q) => t + q.grand_total, 0))} />
        <StatCard label="Total quotations" value={num(quotations.length)} />
      </div>

      <DataTable
        rows={quotations}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.quotation_no} ${r.customer_name} ${r.status} ${r.po_reference} ${r.lines.map((l: QuotationData["lines"][number]) => l.product_name).join(" ")}`}
        columns={[
          { key: "no", header: "Quote No", value: (r) => r.quotation_no, render: (r) => <span className="num font-medium">{r.quotation_no}</span> },
          { key: "date", header: "Date", value: (r) => r.quotation_date, render: (r) => <span className="num">{dmy(r.quotation_date)}</span> },
          { key: "customer", header: "Customer", value: (r) => r.customer_name },
          { key: "po", header: "PO Ref", value: (r) => r.po_reference || "" },
          { key: "items", header: "Items", render: (r) => <span className="text-muted-foreground text-xs">{r.lines.map((l: QuotationData["lines"][number]) => `${l.product_name} ×${num(l.quantity)}`).join(", ")}</span> },
          { key: "value", header: "Value", align: "right", value: (r) => r.grand_total, render: (r) => <span className="num">{inr(r.grand_total)}</span> },
          { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
          {
            key: "actions", header: "", align: "right", render: (r) => <div className="flex justify-end gap-1">
              {r.status === "Draft" && <Button size="sm" variant="outline" onClick={() => void changeStatus(r, "Sent")}>Mark sent</Button>}
              {r.status === "Sent" && <Button size="sm" variant="outline" onClick={() => void changeStatus(r, "Accepted")}>Accept</Button>}
              {r.status === "Accepted" && <Button size="sm" onClick={() => void convert(r)}>Convert to SO</Button>}
              {!["Rejected", "Converted"].includes(r.status) && <Button size="sm" variant="ghost" onClick={() => void changeStatus(r, "Rejected")}>Reject</Button>}
            </div>,
          },
        ]}
      />

      {loading && <div className="py-8 text-center text-sm text-muted-foreground">Loading quotations...</div>}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
          <DialogHeader><DialogTitle>New quotation</DialogTitle><DialogDescription>Numbered {nextNo}. Enter a customer PO reference to load its customer and line information.</DialogDescription></DialogHeader>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Customer" full><Select value={form.customerId} onValueChange={(v) => setForm({ ...form, customerId: v })}><SelectTrigger><SelectValue placeholder="Select customer" /></SelectTrigger><SelectContent>{customers.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent></Select></Field>
            <Field label="Quotation date"><Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} /></Field>
            <Field label="Valid until"><Input type="date" value={form.validUntil} onChange={(e) => setForm({ ...form, validUntil: e.target.value })} /></Field>
            <Field label="Customer PO reference"><div className="flex gap-2"><Input value={form.poReference} onChange={(e) => setForm({ ...form, poReference: e.target.value })} onBlur={() => void lookupPO()} placeholder="Enter PO number" /><Button type="button" variant="outline" disabled={poLookupLoading} onClick={() => void lookupPO()}>{poLookupLoading ? "Loading..." : "Load PO"}</Button></div></Field>
          </div>

          {poInfo && <div className="mt-3 rounded-lg border bg-muted/30 p-3 text-sm"><b>PO loaded:</b> {poInfo.po_no} · {poInfo.customer_name}{poInfo.delivery_date ? ` · Delivery ${dmy(poInfo.delivery_date)}` : ""}</div>}

          <div className="mt-4 space-y-3">
            <div className="text-sm font-medium">Products</div>
            {lines.map((line, index) => {
              const product = products.find((p) => p.id === line.productId);
              const gstRate = line.gstRate ?? product?.gst_rate ?? 18;
              return <div key={index} className="rounded-lg border p-3"><div className="grid grid-cols-12 items-end gap-2">
                <div className="col-span-12 sm:col-span-5"><Field label="Product"><Select value={line.productId} onValueChange={(v) => selectProduct(index, v)}><SelectTrigger><SelectValue placeholder="Product" /></SelectTrigger><SelectContent>{products.map((p) => <SelectItem key={p.id} value={p.id}>{p.code} · {p.name}</SelectItem>)}</SelectContent></Select></Field></div>
                <div className="col-span-4 sm:col-span-2"><Field label="Qty"><Input type="number" min="0" value={line.quantity || ""} onChange={(e) => updateLine(index, { quantity: Number(e.target.value) })} /></Field></div>
                <div className="col-span-4 sm:col-span-2"><Field label="Rate"><Input type="number" min="0" value={line.rate || ""} onChange={(e) => updateLine(index, { rate: Number(e.target.value) })} /></Field></div>
                <div className="col-span-4 sm:col-span-2"><Field label="Discount %"><Input type="number" min="0" max="100" step="0.01" value={line.discountPercent} onChange={(e) => updateLine(index, { discountPercent: Number(e.target.value) })} /></Field></div>
                <Button variant="ghost" size="icon" className="col-span-12 sm:col-span-1" onClick={() => setLines(lines.length > 1 ? lines.filter((_, i) => i !== index) : lines)}><Trash2 className="text-destructive h-4 w-4" /></Button>
              </div><div className="mt-2 flex items-center gap-2"><Field label="GST %"><Input className="w-28" type="number" min="0" max="100" step="0.01" value={line.gstRate ?? ""} placeholder={`${gstRate}`} onChange={(e) => updateLine(index, { gstRate: e.target.value === "" ? null : Number(e.target.value) })} /></Field><span className="text-xs text-muted-foreground">Leave blank to use master GST ({product?.gst_rate ?? 18}%).</span></div></div>;
            })}
            <Button variant="outline" size="sm" onClick={() => setLines([...lines, blankLine()])}><Plus className="mr-1 h-3.5 w-3.5" /> Add line</Button>
          </div>

          <Textarea className="mt-3" rows={2} placeholder="Terms / notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          <div className="panel mt-3 grid grid-cols-4 gap-2 p-3 text-sm"><div><p className="text-xs text-muted-foreground">Subtotal</p><p className="num">{inr(totals.subtotal)}</p></div><div><p className="text-xs text-muted-foreground">Discount</p><p className="num">{inr(totals.discount)}</p></div><div><p className="text-xs text-muted-foreground">GST</p><p className="num">{inr(totals.tax)}</p></div><div><p className="text-xs text-muted-foreground">Grand total</p><p className="num font-semibold text-primary">{inr(totals.grand)}</p></div></div>

          <DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={saving} onClick={() => void submit()}>{saving ? "Saving..." : "Save quotation"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
