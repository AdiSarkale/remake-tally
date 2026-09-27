import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { FormDialog, FormField } from "@/components/form-dialog";
import { BackendGap, ModuleTabs, NumInput, QueryTable, SelectField, runMutation } from "@/components/erp";
import * as H from "@/lib/api/hooks";
import { useAuth } from "@/lib/auth";
import { formatCurrency, formatDate, todayIso } from "@/lib/format";

export const Route = createFileRoute("/_app/finance")({
  head: () => ({
    meta: [
      { title: "Finance — Minitally ERP" },
      { name: "description", content: "Receivables, payables, customer receipts and supplier payments." },
      { property: "og:title", content: "Finance — Minitally ERP" },
      { property: "og:description", content: "Receivables, payables, customer receipts and supplier payments." },
    ],
  }),
  component: FinancePage,
});

const MODES = ["Bank Transfer", "UPI", "Cheque", "Cash", "NEFT", "RTGS"];

function FinancePage() {
  const { can } = useAuth();
  const canEdit = can("finance");
  return (
    <div className="space-y-5">
      <PageHeader title="Finance" description="Invoice → Receivable → Receipt · PO → Payable → Payment" />
      <Summary />
      <ModuleTabs
        tabs={[
          { value: "ar", label: "Receivables", content: <Receivables /> },
          { value: "ap", label: "Payables", content: <Payables /> },
          { value: "rcpt", label: "Receipts", content: <Receipts canEdit={canEdit} /> },
          { value: "pay", label: "Payments", content: <Payments canEdit={canEdit} /> },
        ]}
      />
      <BackendGap>chart of accounts and general-ledger transactions are not exposed by the backend; finance here covers AR/AP and payments.</BackendGap>
    </div>
  );
}

function Summary() {
  const ar = H.useReceivables();
  const ap = H.usePayables();
  const rc = H.useCustomerPayments();
  const sp = H.useSupplierPayments();
  const sum = (xs: number[] | undefined) => (xs ?? []).reduce((a, b) => a + b, 0);
  const cards: [string, number][] = [
    ["Receivables outstanding", sum(ar.data?.map((r) => r.balance_amount))],
    ["Payables outstanding", sum(ap.data?.map((r) => r.balance_amount))],
    ["Received to date", sum(rc.data?.map((r) => r.amount))],
    ["Paid to date", sum(sp.data?.map((r) => r.amount))],
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map(([k, v]) => (
        <div key={k} className="rounded-md border bg-card p-4">
          <div className="text-xs uppercase tracking-wide text-muted-foreground">{k}</div>
          <div className="mt-1 text-xl font-semibold tabular-nums">{formatCurrency(v)}</div>
        </div>
      ))}
    </div>
  );
}

function Receivables() {
  return (
    <QueryTable
      query={H.useReceivables()}
      rowKey={(r) => r.invoice_id}
      exportName="receivables"
      emptyTitle="No receivables"
      columns={[
        { key: "no", header: "Invoice", render: (r) => <span className="font-mono text-xs">{r.invoice_no}</span>, searchValue: (r) => r.invoice_no },
        { key: "date", header: "Date", render: (r) => formatDate(r.invoice_date), sortValue: (r) => r.invoice_date },
        { key: "c", header: "Customer", render: (r) => r.customer_name, searchValue: (r) => r.customer_name, sortValue: (r) => r.customer_name },
        { key: "t", header: "Total", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.grand_total)}</span> },
        { key: "p", header: "Paid", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.paid_amount)}</span> },
        { key: "b", header: "Balance", className: "text-right", render: (r) => <span className="font-medium tabular-nums">{formatCurrency(r.balance_amount)}</span>, sortValue: (r) => r.balance_amount },
        { key: "s", header: "Status", render: (r) => <StatusBadge status={r.status} />, searchValue: (r) => r.status },
      ]}
    />
  );
}

function Payables() {
  return (
    <QueryTable
      query={H.usePayables()}
      rowKey={(r) => r.purchase_order_id}
      exportName="payables"
      emptyTitle="No payables"
      columns={[
        { key: "no", header: "PO", render: (r) => <span className="font-mono text-xs">{r.po_no}</span>, searchValue: (r) => r.po_no },
        { key: "date", header: "Date", render: (r) => formatDate(r.po_date), sortValue: (r) => r.po_date },
        { key: "s", header: "Supplier", render: (r) => r.supplier_name, searchValue: (r) => r.supplier_name, sortValue: (r) => r.supplier_name },
        { key: "t", header: "Total", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.grand_total)}</span> },
        { key: "p", header: "Paid", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.paid_amount)}</span> },
        { key: "b", header: "Balance", className: "text-right", render: (r) => <span className="font-medium tabular-nums">{formatCurrency(r.balance_amount)}</span>, sortValue: (r) => r.balance_amount },
        { key: "st", header: "PO status", render: (r) => <StatusBadge status={r.status.replace("_", " ")} /> },
      ]}
    />
  );
}

function Receipts({ canEdit }: { canEdit: boolean }) {
  const query = H.useCustomerPayments();
  const customers = H.useCustomers();
  const ar = H.useReceivables();
  const create = H.useCreateCustomerPayment();
  const [open, setOpen] = useState(false);
  const blank = { payment_date: todayIso(), customer_id: "", invoice_id: "", amount: 0, mode: "Bank Transfer", reference: "", remarks: "" };
  const [f, setF] = useState(blank);
  const submit = async () => {
    if (!f.customer_id || f.amount <= 0) return;
    if (await runMutation(create.mutateAsync({ ...f, invoice_id: f.invoice_id || null }), "Receipt recorded")) { setOpen(false); setF(blank); }
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="customer-receipts"
        emptyTitle="No receipts"
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New receipt</Button> : null}
        columns={[
          { key: "no", header: "Receipt #", render: (r) => <span className="font-mono text-xs">{r.payment_no}</span>, searchValue: (r) => r.payment_no },
          { key: "d", header: "Date", render: (r) => formatDate(r.payment_date), sortValue: (r) => r.payment_date },
          { key: "c", header: "Customer", render: (r) => r.customer_name, searchValue: (r) => r.customer_name },
          { key: "i", header: "Invoice", render: (r) => <span className="font-mono text-xs">{r.invoice_no || "On account"}</span> },
          { key: "m", header: "Mode", render: (r) => r.mode, hideable: true },
          { key: "ref", header: "Reference", render: (r) => r.reference || "—", hideable: true },
          { key: "a", header: "Amount", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.amount)}</span>, sortValue: (r) => r.amount },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="Record customer receipt" onSubmit={() => void submit()} pending={create.isPending}>
        <FormField label="Customer *"><SelectField value={f.customer_id} onChange={(v) => setF({ ...f, customer_id: v, invoice_id: "" })} options={(customers.data ?? []).map((c) => ({ value: c.id, label: c.name }))} /></FormField>
        <FormField label="Against invoice">
          <SelectField allowNone value={f.invoice_id} onChange={(v) => { const inv = ar.data?.find((x) => x.invoice_id === v); setF({ ...f, invoice_id: v, amount: inv?.balance_amount ?? f.amount }); }}
            options={(ar.data ?? []).filter((r) => r.customer_id === f.customer_id && r.balance_amount > 0).map((r) => ({ value: r.invoice_id, label: `${r.invoice_no} — due ${formatCurrency(r.balance_amount)}` }))} />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Amount *"><NumInput value={f.amount} onChange={(n) => setF({ ...f, amount: n })} /></FormField>
          <FormField label="Date"><Input type="date" value={f.payment_date} onChange={(e) => setF({ ...f, payment_date: e.target.value })} /></FormField>
          <FormField label="Mode"><SelectField value={f.mode} onChange={(v) => setF({ ...f, mode: v })} options={MODES.map((m) => ({ value: m, label: m }))} /></FormField>
          <FormField label="Reference"><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} /></FormField>
        </div>
      </FormDialog>
    </>
  );
}

function Payments({ canEdit }: { canEdit: boolean }) {
  const query = H.useSupplierPayments();
  const suppliers = H.useSuppliers();
  const ap = H.usePayables();
  const create = H.useCreateSupplierPayment();
  const [open, setOpen] = useState(false);
  const blank = { payment_date: todayIso(), supplier_id: "", purchase_order_id: "", amount: 0, mode: "Bank Transfer", reference: "", remarks: "" };
  const [f, setF] = useState(blank);
  const submit = async () => {
    if (!f.supplier_id || f.amount <= 0) return;
    if (await runMutation(create.mutateAsync({ ...f, purchase_order_id: f.purchase_order_id || null }), "Payment recorded")) { setOpen(false); setF(blank); }
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="supplier-payments"
        emptyTitle="No payments"
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New payment</Button> : null}
        columns={[
          { key: "no", header: "Payment #", render: (r) => <span className="font-mono text-xs">{r.payment_no}</span>, searchValue: (r) => r.payment_no },
          { key: "d", header: "Date", render: (r) => formatDate(r.payment_date), sortValue: (r) => r.payment_date },
          { key: "s", header: "Supplier", render: (r) => r.supplier_name, searchValue: (r) => r.supplier_name },
          { key: "po", header: "PO", render: (r) => <span className="font-mono text-xs">{r.po_no || "On account"}</span> },
          { key: "m", header: "Mode", render: (r) => r.mode, hideable: true },
          { key: "a", header: "Amount", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.amount)}</span>, sortValue: (r) => r.amount },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="Record supplier payment" onSubmit={() => void submit()} pending={create.isPending}>
        <FormField label="Supplier *"><SelectField value={f.supplier_id} onChange={(v) => setF({ ...f, supplier_id: v, purchase_order_id: "" })} options={(suppliers.data ?? []).map((c) => ({ value: c.id, label: c.name }))} /></FormField>
        <FormField label="Against PO">
          <SelectField allowNone value={f.purchase_order_id} onChange={(v) => { const po = ap.data?.find((x) => x.purchase_order_id === v); setF({ ...f, purchase_order_id: v, amount: po?.balance_amount ?? f.amount }); }}
            options={(ap.data ?? []).filter((r) => r.supplier_id === f.supplier_id && r.balance_amount > 0).map((r) => ({ value: r.purchase_order_id, label: `${r.po_no} — due ${formatCurrency(r.balance_amount)}` }))} />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Amount *"><NumInput value={f.amount} onChange={(n) => setF({ ...f, amount: n })} /></FormField>
          <FormField label="Date"><Input type="date" value={f.payment_date} onChange={(e) => setF({ ...f, payment_date: e.target.value })} /></FormField>
          <FormField label="Mode"><SelectField value={f.mode} onChange={(v) => setF({ ...f, mode: v })} options={MODES.map((m) => ({ value: m, label: m }))} /></FormField>
          <FormField label="Reference"><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} /></FormField>
        </div>
      </FormDialog>
    </>
  );
}
