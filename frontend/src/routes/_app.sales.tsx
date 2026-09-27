import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowRightLeft, Plus, Truck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { FormDialog, FormField } from "@/components/form-dialog";
import { LineItemsEditor, emptyLine, type LineItem } from "@/components/line-items-editor";
import { PartyManager } from "@/components/party-manager";
import {
  ConfirmAction,
  DetailSheet,
  KeyValues,
  ModuleTabs,
  NumInput,
  QueryTable,
  SectionTitle,
  SelectField,
  runMutation,
} from "@/components/erp";
import * as H from "@/lib/api/hooks";
import type * as T from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { formatCurrency, formatDate, formatNumber, todayIso } from "@/lib/format";

export const Route = createFileRoute("/_app/sales")({
  head: () => ({
    meta: [
      { title: "Sales — Minitally ERP" },
      { name: "description", content: "Customers, quotations, sales orders, deliveries, dispatches and invoices." },
      { property: "og:title", content: "Sales — Minitally ERP" },
      { property: "og:description", content: "Customers, quotations, sales orders, deliveries, dispatches and invoices." },
    ],
  }),
  component: SalesPage,
});

const QUOTE_STATUSES: T.QuotationStatus[] = ["Draft", "Sent", "Accepted", "Rejected", "Expired"];
const SO_STATUSES: T.SalesOrderStatus[] = ["Open", "Partially Delivered", "Delivered", "Invoiced", "Cancelled"];
const DISPATCH_STATUSES: T.DispatchStatus[] = ["Planned", "Loading", "In Transit", "Delivered", "Delayed"];
const INVOICE_STATUSES: T.InvoiceStatus[] = ["Unpaid", "Partial", "Paid", "Cancelled"];

function SalesPage() {
  const { can } = useAuth();
  const canEdit = can("sales");
  return (
    <div className="space-y-5">
      <PageHeader title="Sales" description="Quotation → Sales order → Delivery → Dispatch → Invoice" />
      <ModuleTabs
        defaultValue="orders"
        tabs={[
          { value: "customers", label: "Customers", content: <CustomersTab canEdit={canEdit} /> },
          { value: "quotations", label: "Quotations", content: <QuotationsTab canEdit={canEdit} /> },
          { value: "orders", label: "Sales Orders", content: <SalesOrdersTab canEdit={canEdit} /> },
          { value: "deliveries", label: "Deliveries", content: <DeliveriesTab /> },
          { value: "dispatches", label: "Dispatches", content: <DispatchesTab canEdit={canEdit} /> },
          { value: "invoices", label: "Invoices", content: <InvoicesTab canEdit={canEdit} /> },
        ]}
      />
    </div>
  );
}

function CustomersTab({ canEdit }: { canEdit: boolean }) {
  return (
    <PartyManager
      label="Customer"
      query={H.useCustomers()}
      create={H.useCreateCustomer()}
      update={H.useUpdateCustomer()}
      remove={H.useDeleteCustomer()}
      canEdit={canEdit}
    />
  );
}

function DocLines({ lines }: { lines: { product_name: string; quantity: number; rate: number; taxable: number; total: number; unit: string; extra?: string }[] }) {
  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead className="text-right">Qty</TableHead>
            <TableHead className="text-right">Rate</TableHead>
            <TableHead className="text-right">Taxable</TableHead>
            <TableHead className="text-right">Total</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((l, i) => (
            <TableRow key={i}>
              <TableCell>
                {l.product_name}
                {l.extra ? <div className="text-xs text-muted-foreground">{l.extra}</div> : null}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(l.quantity, 2)} {l.unit}
              </TableCell>
              <TableCell className="text-right tabular-nums">{formatCurrency(l.rate)}</TableCell>
              <TableCell className="text-right tabular-nums">{formatCurrency(l.taxable)}</TableCell>
              <TableCell className="text-right tabular-nums">{formatCurrency(l.total)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------- Quotations ----------------
function QuotationsTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useQuotations();
  const customers = H.useCustomers();
  const products = H.useProducts();
  const create = H.useCreateQuotation();
  const setStatus = H.useUpdateQuotationStatus();
  const convert = H.useCreateSalesOrderFromQuotation();
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<T.QuotationOut | null>(null);
  const [form, setForm] = useState({ customer_id: "", quotation_date: todayIso(), valid_until: "", po_reference: "", notes: "" });
  const [lines, setLines] = useState<LineItem[]>([emptyLine()]);

  const submit = async () => {
    const valid = lines.filter((l) => l.product_id && l.quantity > 0);
    if (!form.customer_id || valid.length === 0) return;
    const r = await runMutation(
      create.mutateAsync({ ...form, valid_until: form.valid_until || null, status: "Draft", lines: valid }),
      "Quotation created",
    );
    if (r) {
      setOpen(false);
      setLines([emptyLine()]);
    }
  };

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="quotations"
        emptyTitle="No quotations yet"
        onRowClick={setSel}
        toolbar={
          canEdit ? (
            <Button size="sm" onClick={() => setOpen(true)}>
              <Plus className="mr-1 h-4 w-4" /> New quotation
            </Button>
          ) : null
        }
        columns={[
          { key: "no", header: "Quote #", render: (r) => <span className="font-mono text-xs">{r.quotation_no}</span>, sortValue: (r) => r.quotation_no, searchValue: (r) => r.quotation_no },
          { key: "date", header: "Date", render: (r) => formatDate(r.quotation_date), sortValue: (r) => r.quotation_date },
          { key: "cust", header: "Customer", render: (r) => r.customer_name, sortValue: (r) => r.customer_name, searchValue: (r) => r.customer_name },
          { key: "valid", header: "Valid until", render: (r) => formatDate(r.valid_until), hideable: true },
          { key: "total", header: "Total", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.grand_total)}</span>, sortValue: (r) => r.grand_total },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} />, sortValue: (r) => r.status, searchValue: (r) => r.status },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="New quotation" wide onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Customer *" className="space-y-1.5 sm:col-span-3">
            <SelectField value={form.customer_id} onChange={(v) => setForm({ ...form, customer_id: v })} options={(customers.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          </FormField>
          <FormField label="Date">
            <Input type="date" value={form.quotation_date} onChange={(e) => setForm({ ...form, quotation_date: e.target.value })} />
          </FormField>
          <FormField label="Valid until">
            <Input type="date" value={form.valid_until} onChange={(e) => setForm({ ...form, valid_until: e.target.value })} />
          </FormField>
          <FormField label="Customer PO ref">
            <Input value={form.po_reference} onChange={(e) => setForm({ ...form, po_reference: e.target.value })} />
          </FormField>
        </div>
        <LineItemsEditor lines={lines} onChange={setLines} products={products.data ?? []} />
        <FormField label="Notes">
          <Input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </FormField>
      </FormDialog>
      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSel(null)} title={sel?.quotation_no ?? ""} description={sel?.customer_name ?? ""}>
        {sel ? (
          <>
            <KeyValues
              items={[
                ["Status", <StatusBadge key="s" status={sel.status} />],
                ["Date", formatDate(sel.quotation_date)],
                ["Valid until", formatDate(sel.valid_until)],
                ["PO ref", sel.po_reference || "—"],
                ["Taxable", formatCurrency(sel.taxable_total)],
                ["Grand total", formatCurrency(sel.grand_total)],
              ]}
            />
            <DocLines lines={sel.lines} />
            {canEdit && sel.status !== "Converted" ? (
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-44">
                  <SelectField
                    value={sel.status}
                    onChange={(v) =>
                      void runMutation(setStatus.mutateAsync({ id: sel.id, status: v as T.QuotationStatus }), "Status updated").then((r) => r && setSel(r))
                    }
                    options={QUOTE_STATUSES.map((s) => ({ value: s, label: s }))}
                  />
                </div>
                <ConfirmAction
                  title="Convert to sales order?"
                  description={`${sel.quotation_no} will be marked Converted and a new sales order created.`}
                  confirmLabel="Convert"
                  onConfirm={() =>
                    void runMutation(convert.mutateAsync(sel.id), "Sales order created").then((r) => r && setSel(null))
                  }
                  trigger={
                    <Button size="sm">
                      <ArrowRightLeft className="mr-1 h-4 w-4" /> Convert to sales order
                    </Button>
                  }
                />
              </div>
            ) : null}
          </>
        ) : null}
      </DetailSheet>
    </>
  );
}

// ---------------- Sales orders ----------------
function SalesOrdersTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useSalesOrders();
  const setStatus = H.useUpdateSalesOrderStatus();
  const createDelivery = H.useCreateDelivery();
  const [selId, setSelId] = useState<string | null>(null);
  const sel = query.data?.find((s) => s.id === selId) ?? null;
  const [dOpen, setDOpen] = useState(false);
  const [dForm, setDForm] = useState({ delivery_date: todayIso(), vehicle_no: "", driver_name: "", lr_number: "", remarks: "" });
  const [dQty, setDQty] = useState<Record<string, number>>({});

  const openDelivery = (so: T.SalesOrderOut) => {
    const q: Record<string, number> = {};
    so.lines.forEach((l) => (q[l.product_id] = Math.max(0, l.quantity - l.delivered_quantity)));
    setDQty(q);
    setDOpen(true);
  };
  const submitDelivery = async () => {
    if (!sel) return;
    const lines = Object.entries(dQty)
      .filter(([, q]) => q > 0)
      .map(([product_id, quantity]) => ({ product_id, quantity }));
    if (lines.length === 0) return;
    const r = await runMutation(createDelivery.mutateAsync({ ...dForm, sales_order_id: sel.id, lines }), "Delivery note created — stock issued");
    if (r) setDOpen(false);
  };

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="sales-orders"
        emptyTitle="No sales orders"
        onRowClick={(r) => setSelId(r.id)}
        columns={[
          { key: "no", header: "SO #", render: (r) => <span className="font-mono text-xs">{r.so_no}</span>, sortValue: (r) => r.so_no, searchValue: (r) => r.so_no },
          { key: "date", header: "Order date", render: (r) => formatDate(r.order_date), sortValue: (r) => r.order_date },
          { key: "cust", header: "Customer", render: (r) => r.customer_name, sortValue: (r) => r.customer_name, searchValue: (r) => r.customer_name },
          { key: "quote", header: "Quote", render: (r) => <span className="font-mono text-xs">{r.quote_no || "—"}</span>, hideable: true },
          { key: "due", header: "Delivery", render: (r) => formatDate(r.delivery_date), hideable: true },
          {
            key: "progress",
            header: "Delivered",
            render: (r) => {
              const ordered = r.lines.reduce((a, l) => a + l.quantity, 0);
              const done = r.lines.reduce((a, l) => a + l.delivered_quantity, 0);
              return <span className="tabular-nums">{ordered ? Math.round((done / ordered) * 100) : 0}%</span>;
            },
          },
          { key: "total", header: "Total", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.grand_total)}</span>, sortValue: (r) => r.grand_total },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} />, sortValue: (r) => r.status, searchValue: (r) => r.status },
        ]}
      />
      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSelId(null)} title={sel?.so_no ?? ""} description={sel?.customer_name ?? ""}>
        {sel ? (
          <>
            <KeyValues
              items={[
                ["Status", <StatusBadge key="s" status={sel.status} />],
                ["Order date", formatDate(sel.order_date)],
                ["Delivery date", formatDate(sel.delivery_date)],
                ["From quote", sel.quote_no || "—"],
                ["Taxable", formatCurrency(sel.taxable_total)],
                ["Grand total", formatCurrency(sel.grand_total)],
              ]}
            />
            <SectionTitle>Lines</SectionTitle>
            <DocLines lines={sel.lines.map((l) => ({ ...l, extra: `Delivered ${formatNumber(l.delivered_quantity, 2)} of ${formatNumber(l.quantity, 2)}` }))} />
            {canEdit ? (
              <div className="flex flex-wrap items-center gap-2">
                <div className="w-52">
                  <SelectField
                    value={sel.status}
                    onChange={(v) => void runMutation(setStatus.mutateAsync({ id: sel.id, status: v as T.SalesOrderStatus }), "Status updated")}
                    options={SO_STATUSES.map((s) => ({ value: s, label: s }))}
                  />
                </div>
                {sel.status === "Open" || sel.status === "Partially Delivered" ? (
                  <Button size="sm" onClick={() => openDelivery(sel)}>
                    <Truck className="mr-1 h-4 w-4" /> Create delivery
                  </Button>
                ) : null}
              </div>
            ) : null}
            <p className="text-xs text-muted-foreground">
              Material shortfalls for this order are raised as purchase orders under Procurement; finished goods come from Production.
            </p>
          </>
        ) : null}
      </DetailSheet>
      <FormDialog open={dOpen} onOpenChange={setDOpen} title={`Delivery for ${sel?.so_no ?? ""}`} onSubmit={() => void submitDelivery()} pending={createDelivery.isPending} submitLabel="Create delivery">
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Date">
            <Input type="date" value={dForm.delivery_date} onChange={(e) => setDForm({ ...dForm, delivery_date: e.target.value })} />
          </FormField>
          <FormField label="Vehicle no.">
            <Input value={dForm.vehicle_no} onChange={(e) => setDForm({ ...dForm, vehicle_no: e.target.value })} />
          </FormField>
          <FormField label="Driver">
            <Input value={dForm.driver_name} onChange={(e) => setDForm({ ...dForm, driver_name: e.target.value })} />
          </FormField>
          <FormField label="LR number">
            <Input value={dForm.lr_number} onChange={(e) => setDForm({ ...dForm, lr_number: e.target.value })} />
          </FormField>
        </div>
        <SectionTitle>Quantities to deliver</SectionTitle>
        {sel?.lines.map((l) => (
          <div key={l.id} className="grid grid-cols-[1fr_120px] items-center gap-3 text-sm">
            <span>
              {l.product_name}
              <span className="ml-2 text-xs text-muted-foreground">remaining {formatNumber(l.quantity - l.delivered_quantity, 2)}</span>
            </span>
            <NumInput value={dQty[l.product_id] ?? 0} onChange={(n) => setDQty({ ...dQty, [l.product_id]: n })} />
          </div>
        ))}
      </FormDialog>
    </>
  );
}

function DeliveriesTab() {
  const query = H.useDeliveries();
  return (
    <QueryTable
      query={query}
      rowKey={(r) => r.id}
      exportName="deliveries"
      emptyTitle="No delivery notes"
      columns={[
        { key: "no", header: "Delivery #", render: (r) => <span className="font-mono text-xs">{r.delivery_no}</span>, sortValue: (r) => r.delivery_no, searchValue: (r) => r.delivery_no },
        { key: "date", header: "Date", render: (r) => formatDate(r.delivery_date), sortValue: (r) => r.delivery_date },
        { key: "so", header: "SO", render: (r) => <span className="font-mono text-xs">{r.so_no || "Direct"}</span>, searchValue: (r) => r.so_no },
        { key: "cust", header: "Customer", render: (r) => r.customer_name, searchValue: (r) => r.customer_name },
        { key: "items", header: "Items", render: (r) => r.lines.map((l) => `${l.product_name} × ${formatNumber(l.quantity, 2)}`).join(", ") },
        { key: "veh", header: "Vehicle", render: (r) => r.vehicle_no || "—", hideable: true },
      ]}
    />
  );
}

function DispatchesTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useDispatches();
  const deliveries = H.useDeliveries();
  const create = H.useCreateDispatch();
  const setStatus = H.useUpdateDispatchStatus();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ delivery_id: "", transporter: "", vehicle_no: "", driver_name: "", driver_phone: "", lr_number: "" });
  const submit = async () => {
    if (!f.delivery_id) return;
    const r = await runMutation(
      create.mutateAsync({ ...f, dispatch_date: todayIso(), status: "Planned", delivered_on: null, pod_ref: "" }),
      "Dispatch planned",
    );
    if (r) setOpen(false);
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="dispatches"
        emptyTitle="No dispatches"
        toolbar={
          canEdit ? (
            <Button size="sm" onClick={() => setOpen(true)}>
              <Plus className="mr-1 h-4 w-4" /> Plan dispatch
            </Button>
          ) : null
        }
        columns={[
          { key: "no", header: "Dispatch #", render: (r) => <span className="font-mono text-xs">{r.dispatch_no}</span>, sortValue: (r) => r.dispatch_no, searchValue: (r) => r.dispatch_no },
          { key: "date", header: "Date", render: (r) => formatDate(r.dispatch_date), sortValue: (r) => r.dispatch_date },
          { key: "dn", header: "Delivery", render: (r) => <span className="font-mono text-xs">{r.delivery_no || "—"}</span> },
          { key: "cust", header: "Customer", render: (r) => r.customer_name, searchValue: (r) => r.customer_name },
          { key: "tr", header: "Transporter", render: (r) => r.transporter || "—", hideable: true },
          { key: "veh", header: "Vehicle", render: (r) => r.vehicle_no || "—", hideable: true },
          {
            key: "status",
            header: "Status",
            render: (r) =>
              canEdit ? (
                <div className="w-36" onClick={(e) => e.stopPropagation()}>
                  <SelectField
                    value={r.status}
                    onChange={(v) => void runMutation(setStatus.mutateAsync({ id: r.id, status: v as T.DispatchStatus }), "Dispatch updated")}
                    options={DISPATCH_STATUSES.map((s) => ({ value: s, label: s }))}
                  />
                </div>
              ) : (
                <StatusBadge status={r.status} />
              ),
            sortValue: (r) => r.status,
          },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="Plan dispatch" onSubmit={() => void submit()} pending={create.isPending}>
        <FormField label="Delivery note *">
          <SelectField
            value={f.delivery_id}
            onChange={(v) => setF({ ...f, delivery_id: v })}
            options={(deliveries.data ?? []).map((d) => ({ value: d.id, label: `${d.delivery_no} — ${d.customer_name}` }))}
          />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          {(["transporter", "vehicle_no", "driver_name", "driver_phone", "lr_number"] as const).map((k) => (
            <FormField key={k} label={k.replace("_", " ").replace(/^\w/, (c) => c.toUpperCase())}>
              <Input value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
            </FormField>
          ))}
        </div>
      </FormDialog>
    </>
  );
}

function InvoicesTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useInvoices();
  const customers = H.useCustomers();
  const products = H.useProducts();
  const create = H.useCreateInvoice();
  const setStatus = H.useUpdateInvoiceStatus();
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<T.InvoiceOut | null>(null);
  const [f, setF] = useState({ customer_id: "", invoice_date: todayIso(), po_reference: "", notes: "" });
  const [lines, setLines] = useState<LineItem[]>([emptyLine()]);
  const submit = async () => {
    const valid = lines.filter((l) => l.product_id && l.quantity > 0);
    if (!f.customer_id || valid.length === 0) return;
    const r = await runMutation(create.mutateAsync({ ...f, status: "Unpaid", paid_percent: 0, lines: valid }), "Invoice created");
    if (r) {
      setOpen(false);
      setLines([emptyLine()]);
    }
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="invoices"
        emptyTitle="No invoices"
        onRowClick={setSel}
        toolbar={
          canEdit ? (
            <Button size="sm" onClick={() => setOpen(true)}>
              <Plus className="mr-1 h-4 w-4" /> New invoice
            </Button>
          ) : null
        }
        columns={[
          { key: "no", header: "Invoice #", render: (r) => <span className="font-mono text-xs">{r.invoice_no}</span>, sortValue: (r) => r.invoice_no, searchValue: (r) => r.invoice_no },
          { key: "date", header: "Date", render: (r) => formatDate(r.invoice_date), sortValue: (r) => r.invoice_date },
          { key: "cust", header: "Customer", render: (r) => r.customer_name, searchValue: (r) => r.customer_name, sortValue: (r) => r.customer_name },
          { key: "total", header: "Total", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.grand_total)}</span>, sortValue: (r) => r.grand_total },
          { key: "bal", header: "Balance", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.balance_amount)}</span>, sortValue: (r) => r.balance_amount },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.status} />, sortValue: (r) => r.status, searchValue: (r) => r.status },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="New tax invoice" wide onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Customer *" className="space-y-1.5 sm:col-span-3">
            <SelectField value={f.customer_id} onChange={(v) => setF({ ...f, customer_id: v })} options={(customers.data ?? []).map((c) => ({ value: c.id, label: c.name }))} />
          </FormField>
          <FormField label="Date">
            <Input type="date" value={f.invoice_date} onChange={(e) => setF({ ...f, invoice_date: e.target.value })} />
          </FormField>
          <FormField label="PO reference" className="space-y-1.5 sm:col-span-2">
            <Input value={f.po_reference} onChange={(e) => setF({ ...f, po_reference: e.target.value })} />
          </FormField>
        </div>
        <LineItemsEditor lines={lines} onChange={setLines} products={products.data ?? []} />
      </FormDialog>
      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSel(null)} title={sel?.invoice_no ?? ""} description={sel?.customer_name ?? ""}>
        {sel ? (
          <>
            <KeyValues
              items={[
                ["Status", <StatusBadge key="s" status={sel.status} />],
                ["Date", formatDate(sel.invoice_date)],
                ["Taxable", formatCurrency(sel.taxable_total)],
                ["GST", formatCurrency(sel.cgst + sel.sgst + sel.igst)],
                ["Grand total", formatCurrency(sel.grand_total)],
                ["Balance", formatCurrency(sel.balance_amount)],
              ]}
            />
            <DocLines lines={sel.lines} />
            {canEdit ? (
              <div className="w-44">
                <SelectField
                  value={sel.status}
                  onChange={(v) =>
                    void runMutation(
                      setStatus.mutateAsync({ id: sel.id, status: v as T.InvoiceStatus, paid_percent: v === "Paid" ? 100 : 0 }),
                      "Invoice updated",
                    ).then((r) => r && setSel(null))
                  }
                  options={INVOICE_STATUSES.map((s) => ({ value: s, label: s }))}
                />
              </div>
            ) : null}
            <p className="text-xs text-muted-foreground">Record part payments against this invoice under Finance → Receipts.</p>
          </>
        ) : null}
      </DetailSheet>
    </>
  );
}
