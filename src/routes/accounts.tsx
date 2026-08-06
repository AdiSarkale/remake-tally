import { createFileRoute } from "@tanstack/react-router";
import { Wallet, TrendingUp, Receipt, HandCoins } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { DataTable } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/DocBits";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useErp } from "@/lib/erp/store";
import { accountStats } from "@/lib/erp/ops";
import { dmy, inr } from "@/lib/erp/format";

export const Route = createFileRoute("/accounts")({
  head: () => ({
    meta: [
      { title: "Accounts & Finance — NKCC ERP" },
      { name: "description", content: "Receipts and payments, expense vouchers, outstanding receivables ageing and a live profit & loss summary." },
      { property: "og:title", content: "Accounts & Finance — NKCC ERP" },
      { property: "og:description", content: "Cash position, expenses, outstanding and profitability at a glance." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <AccountsPage />
    </AppShell>
  ),
});

function AccountsPage() {
  const state = useErp((s) => s);
  const a = accountStats(state);
  const parties = [...state.customers.map((c) => c.name), ...state.suppliers.map((s2) => s2.name)];
  const outstanding = state.invoices
    .filter((i) => i.status === "Unpaid")
    .map((i) => ({
      ...i,
      ageDays: Math.max(0, Math.round((Date.now() - new Date(i.date).getTime()) / 86400000)),
    }))
    .sort((x, y) => y.ageDays - x.ageDays);

  return (
    <>
      <PageHeader title="Accounts & Finance" subtitle="Receipts, payments, expenses, receivables ageing and profitability." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Cash position" value={inr(a.cashPosition)} tone={a.cashPosition >= 0 ? "success" : "destructive"} hint="Received − paid − expenses" icon={<Wallet className="h-4 w-4" />} />
        <StatCard label="Outstanding" value={inr(a.outstanding)} tone={a.outstanding ? "warning" : "success"} hint={`${outstanding.length} unpaid invoices`} icon={<HandCoins className="h-4 w-4" />} />
        <StatCard label="Net profit" value={inr(a.netProfit)} tone={a.netProfit >= 0 ? "success" : "destructive"} hint={`Gross margin ${a.margin}%`} icon={<TrendingUp className="h-4 w-4" />} />
        <StatCard label="Expenses" value={inr(a.expenses)} hint={`Revenue ${inr(a.revenue)}`} icon={<Receipt className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="payments">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="payments">Receipts & payments</TabsTrigger>
          <TabsTrigger value="expenses">Expenses</TabsTrigger>
          <TabsTrigger value="outstanding">Outstanding</TabsTrigger>
          <TabsTrigger value="pl">Profit & loss</TabsTrigger>
        </TabsList>

        <TabsContent value="payments">
          <RecordPage
            entity="payments"
            singular="Voucher"
            autoNumber={{ field: "voucherNo", prefix: "PV" }}
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "direction", label: "Direction", type: "select", options: ["Received", "Paid"], required: true },
              { name: "partyType", label: "Party type", type: "select", options: ["Customer", "Vendor", "Employee", "Other"] },
              { name: "party", label: "Party", type: "select", options: parties, required: true },
              { name: "reference", label: "Against reference" },
              { name: "mode", label: "Mode", type: "select", options: ["Cash", "NEFT", "RTGS", "UPI", "Cheque"] },
              { name: "amount", label: "Amount", type: "number", required: true },
              { name: "remarks", label: "Remarks", type: "textarea" },
            ]}
            searchable={(r) => `${r['voucherNo']} ${r['party']} ${r['reference']} ${r['mode']}`}
            columns={[
              { key: "voucherNo", header: "Voucher", value: (r) => String(r['voucherNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "direction", header: "Type", value: (r) => String(r['direction'] ?? ""), render: (r) => <StatusBadge status={String(r['direction'] ?? "")} /> },
              { key: "party", header: "Party", value: (r) => String(r['party'] ?? "") },
              { key: "reference", header: "Reference", value: (r) => String(r['reference'] ?? "") },
              { key: "mode", header: "Mode", value: (r) => String(r['mode'] ?? "") },
              {
                key: "amount",
                header: "Amount",
                align: "right",
                value: (r) => Number(r['amount'] ?? 0),
                render: (r) => (
                  <span className={r['direction'] === "Received" ? "num text-success" : "num text-destructive"}>
                    {r['direction'] === "Received" ? "+" : "−"} {inr(Number(r['amount'] ?? 0))}
                  </span>
                ),
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="expenses">
          <RecordPage
            entity="expenses"
            singular="Expense"
            autoNumber={{ field: "voucherNo", prefix: "EXP" }}
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "category", label: "Category", type: "select", options: ["Power & Fuel", "Consumables", "Transport", "Salary", "Repairs", "Rent", "Statutory", "Miscellaneous"], required: true },
              { name: "costCenter", label: "Cost centre" },
              { name: "amount", label: "Amount", type: "number", required: true },
              { name: "paidBy", label: "Paid by" },
              { name: "mode", label: "Mode", type: "select", options: ["Cash", "NEFT", "RTGS", "UPI", "Cheque"] },
              { name: "description", label: "Description", type: "textarea", full: true },
            ]}
            searchable={(r) => `${r['voucherNo']} ${r['category']} ${r['description']} ${r['costCenter']}`}
            columns={[
              { key: "voucherNo", header: "Voucher", value: (r) => String(r['voucherNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "category", header: "Category", value: (r) => String(r['category'] ?? "") },
              { key: "costCenter", header: "Cost centre", value: (r) => String(r['costCenter'] ?? "") },
              { key: "description", header: "Description", value: (r) => String(r['description'] ?? ""), render: (r) => <span className="block max-w-64 truncate">{String(r['description'] ?? "")}</span> },
              { key: "paidBy", header: "Paid by", value: (r) => String(r['paidBy'] ?? "") },
              { key: "amount", header: "Amount", align: "right", value: (r) => Number(r['amount'] ?? 0), render: (r) => <span className="num">{inr(Number(r['amount'] ?? 0))}</span> },
            ]}
          />
        </TabsContent>

        <TabsContent value="outstanding">
          <DataTable
            rows={outstanding}
            rowKey={(i) => i.id}
            searchable={(i) => `${i.invoiceNo} ${i.customerName}`}
            columns={[
              { key: "invoiceNo", header: "Invoice", value: (i) => i.invoiceNo },
              { key: "date", header: "Date", value: (i) => i.date, render: (i) => dmy(i.date) },
              { key: "customerName", header: "Customer", value: (i) => i.customerName },
              { key: "grandTotal", header: "Amount", align: "right", value: (i) => i.grandTotal, render: (i) => <span className="num">{inr(i.grandTotal)}</span> },
              {
                key: "ageDays",
                header: "Ageing",
                align: "right",
                value: (i) => i.ageDays,
                render: (i) => <span className={i.ageDays > 45 ? "num text-destructive" : i.ageDays > 30 ? "num text-warning" : "num"}>{i.ageDays} days</span>,
              },
              {
                key: "bucket",
                header: "Bucket",
                value: (i) => i.ageDays,
                render: (i) => <StatusBadge status={i.ageDays > 60 ? "60+ days" : i.ageDays > 30 ? "31-60 days" : "0-30 days"} />,
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="pl">
          <div className="panel max-w-xl p-5">
            <h3 className="mb-4 text-sm font-semibold tracking-tight">Profit & loss summary</h3>
            <dl className="space-y-2 text-sm">
              {[
                ["Revenue (taxable sales)", a.revenue],
                ["Cost of goods sold", -a.cogs],
                ["Gross profit", a.grossProfit],
                ["Operating expenses", -a.expenses],
              ].map(([label, val]) => (
                <div key={String(label)} className="flex items-center justify-between border-b border-border/60 pb-2">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className={Number(val) < 0 ? "num text-destructive" : "num"}>{inr(Number(val))}</dd>
                </div>
              ))}
              <div className="flex items-center justify-between pt-1">
                <dt className="font-semibold">Net profit</dt>
                <dd className={a.netProfit >= 0 ? "num text-success font-semibold" : "num text-destructive font-semibold"}>{inr(a.netProfit)}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-muted-foreground">Gross margin</dt>
                <dd className="num">{a.margin}%</dd>
              </div>
            </dl>
          </div>
        </TabsContent>
      </Tabs>
    </>
  );
}
