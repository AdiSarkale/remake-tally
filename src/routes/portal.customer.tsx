import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Building, FileText, Truck, Wallet } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/DocBits";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useErp } from "@/lib/erp/store";
import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/portal/customer")({
  head: () => ({
    meta: [
      { title: "Customer Portal — NKCC ERP" },
      { name: "description", content: "Customer-facing view of orders, dispatch status, invoices, outstanding balance and complaints raised." },
      { property: "og:title", content: "Customer Portal — NKCC ERP" },
      { property: "og:description", content: "Give customers self-service visibility of orders and invoices." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <CustomerPortal />
    </AppShell>
  ),
});

function CustomerPortal() {
  const state = useErp((s) => s);
  const names = state.customers.map((c) => c.name);
  const [customer, setCustomer] = useState(names[0] ?? "");

  const orders = state.salesOrders.filter((o) => o.customerName === customer);
  const dispatches = state.dispatches.filter((d) => d.customerName === customer);
  const invoices = state.invoices.filter((i) => i.customerName === customer);
  const complaints = state.complaints.filter((c) => c.customerName === customer);
  const outstanding = invoices.filter((i) => i.status === "Unpaid").reduce((t, i) => t + i.grandTotal, 0);

  return (
    <>
      <PageHeader
        title="Customer Portal"
        subtitle="Self-service view a customer sees: order status, dispatch tracking, invoices and complaints."
        actions={
          <Select value={customer} onValueChange={setCustomer}>
            <SelectTrigger className="w-56">
              <SelectValue placeholder="Select customer" />
            </SelectTrigger>
            <SelectContent>
              {names.map((n) => (
                <SelectItem key={n} value={n}>
                  {n}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open orders" value={num(orders.length)} icon={<FileText className="h-4 w-4" />} />
        <StatCard label="Consignments" value={num(dispatches.length)} hint={`${num(dispatches.filter((d) => d.status === "In Transit").length)} in transit`} icon={<Truck className="h-4 w-4" />} />
        <StatCard label="Invoices" value={num(invoices.length)} icon={<Building className="h-4 w-4" />} />
        <StatCard label="Outstanding" value={inr(outstanding)} tone={outstanding ? "warning" : "success"} icon={<Wallet className="h-4 w-4" />} />
      </div>

      <div className="grid gap-4">
        <section>
          <h3 className="mb-2 text-sm font-semibold tracking-tight">Order status</h3>
          <DataTable
            rows={orders}
            rowKey={(o) => o.id}
            columns={[
              { key: "soNo", header: "Order", value: (o) => o.soNo },
              { key: "date", header: "Date", value: (o) => o.date, render: (o) => dmy(o.date) },
              { key: "total", header: "Value", align: "right", value: (o) => o.total, render: (o) => <span className="num">{inr(o.total)}</span> },
              { key: "status", header: "Status", value: (o) => o.status, render: (o) => <StatusBadge status={o.status} /> },
            ]}
          />
        </section>

        <section>
          <h3 className="mb-2 text-sm font-semibold tracking-tight">Dispatch tracking</h3>
          <DataTable
            rows={dispatches}
            rowKey={(d) => d.id}
            columns={[
              { key: "dispatchNo", header: "Dispatch", value: (d) => d.dispatchNo },
              { key: "date", header: "Date", value: (d) => d.date, render: (d) => dmy(d.date) },
              { key: "vehicleNo", header: "Vehicle", value: (d) => d.vehicleNo },
              { key: "lrNumber", header: "LR No", value: (d) => d.lrNumber },
              { key: "status", header: "Status", value: (d) => d.status, render: (d) => <StatusBadge status={d.status} /> },
            ]}
          />
        </section>

        <section>
          <h3 className="mb-2 text-sm font-semibold tracking-tight">Invoices & payments</h3>
          <DataTable
            rows={invoices}
            rowKey={(i) => i.id}
            columns={[
              { key: "invoiceNo", header: "Invoice", value: (i) => i.invoiceNo },
              { key: "date", header: "Date", value: (i) => i.date, render: (i) => dmy(i.date) },
              { key: "grandTotal", header: "Amount", align: "right", value: (i) => i.grandTotal, render: (i) => <span className="num">{inr(i.grandTotal)}</span> },
              { key: "status", header: "Status", value: (i) => i.status, render: (i) => <StatusBadge status={i.status} /> },
            ]}
          />
        </section>

        <section>
          <h3 className="mb-2 text-sm font-semibold tracking-tight">Complaints raised</h3>
          <DataTable
            rows={complaints}
            rowKey={(c) => c.id}
            columns={[
              { key: "complaintNo", header: "Ref", value: (c) => c.complaintNo },
              { key: "date", header: "Date", value: (c) => c.date, render: (c) => dmy(c.date) },
              { key: "issue", header: "Issue", value: (c) => c.issue },
              { key: "status", header: "Status", value: (c) => c.status, render: (c) => <StatusBadge status={c.status} /> },
            ]}
          />
          <p className="text-muted-foreground mt-3 text-xs">
            Log a new complaint from the <Link to="/quality" className="text-primary underline-offset-2 hover:underline">Quality</Link> module.
          </p>
        </section>
      </div>
    </>
  );
}
