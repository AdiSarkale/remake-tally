import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { createScrap, scrapStats, today, useErp } from "@/lib/erp/store";
import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";

export const Route = createFileRoute("/scrap")({
  head: () => ({
    meta: [
      { title: "Scrap Management — MiniTally ERP" },
      {
        name: "description",
        content: "Log production scrap by type and reason, track scrap rate and realisable scrap value.",
      },
      { property: "og:title", content: "Scrap Management — MiniTally ERP" },
      { property: "og:description", content: "Track scrap by type and reason with realisable value." },
    ],
  }),
  component: () => (
    <AppShell>
      <ScrapPage />
    </AppShell>
  ),
});

const REASONS: string[] = ["Machine setup", "Material defect", "Operator error", "Tool wear", "Rejected at QC", "Other"];
const CHART_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
];

function ScrapPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const stats = scrapStats(state);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    date: today(),
    productId: "",
    batchNo: "",
    scrapTypeId: "",
    quantity: "",
    reason: "Machine setup",
    remarks: "",
  });

  const byType = state.scrapTypes.map((t) => ({
    name: t.name,
    qty: state.scrap.filter((s) => s.scrapTypeId === t.id).reduce((a, s) => a + s.quantity, 0),
    value: t.stock * t.sellingRate,
  }));
  const byReason = REASONS.map((r) => ({
    reason: r,
    qty: state.scrap.filter((s) => s.reason === r).reduce((a, s) => a + s.quantity, 0),
  })).filter((r) => r.qty > 0);

  const submit = () => {
    const qty = Number(form.quantity);
    if (!form.productId || !form.scrapTypeId) {
      toast.error("Select product and scrap type");
      return;
    }
    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error("Enter a valid scrap quantity");
      return;
    }
    try {
      createScrap(
        {
          date: form.date,
          productId: form.productId,
          batchNo: form.batchNo,
          scrapTypeId: form.scrapTypeId,
          quantity: qty,
          reason: form.reason,
          remarks: form.remarks,
        },
        session?.username ?? "system",
      );
      toast.success("Scrap recorded");
      setOpen(false);
      setForm({ ...form, quantity: "", batchNo: "", remarks: "" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not record scrap");
    }
  };

  return (
    <>
      <PageHeader
        title="Scrap Management"
        subtitle="Scrap is added to scrap stock and measured against production output."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> Record scrap
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Scrap this month" value={`${num(stats.monthly, 1)} units`} tone="warning" />
        <StatCard label="Scrap rate" value={`${num(stats.percent, 2)}%`} hint="Scrap ÷ production" />
        <StatCard label="Entries logged" value={num(state.scrap.length)} />
        <StatCard label="Realisable value" value={inr(byType.reduce((t, b) => t + b.value, 0))} tone="success" />
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Scrap by type</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={byType} dataKey="qty" nameKey="name" innerRadius={55} outerRadius={90} paddingAngle={2}>
                  {byType.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Scrap by reason</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={byReason}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="reason" tick={{ fontSize: 10 }} interval={0} angle={-15} height={50} dy={10} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="qty" fill="var(--color-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <DataTable
        rows={state.scrap}
        rowKey={(s) => s.id}
        pageSize={12}
        searchable={(s) => `${s.productName} ${s.scrapTypeName} ${s.reason} ${s.batchNo}`}
        columns={[
          { key: "date", header: "Date", value: (s) => s.date, render: (s) => dmy(s.date) },
          { key: "batch", header: "Batch", value: (s) => s.batchNo, className: "num text-xs" },
          { key: "product", header: "Product", value: (s) => s.productName },
          { key: "type", header: "Scrap type", value: (s) => s.scrapTypeName },
          {
            key: "qty",
            header: "Qty",
            align: "right",
            value: (s) => s.quantity,
            render: (s) => <span className="num font-medium">{num(s.quantity, 1)}</span>,
          },
          { key: "reason", header: "Reason", value: (s) => s.reason },
          { key: "remarks", header: "Remarks", value: (s) => s.remarks, className: "text-muted-foreground text-xs" },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Record scrap</DialogTitle>
            <DialogDescription>Scrap quantity is added to scrap stock for later sale.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="mb-1.5 block text-xs">Date</Label>
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Batch no.</Label>
              <Input
                value={form.batchNo}
                onChange={(e) => setForm({ ...form, batchNo: e.target.value })}
                placeholder="BATCH-0001"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Product</Label>
              <Select value={form.productId} onValueChange={(v) => setForm({ ...form, productId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select product" />
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
            <div>
              <Label className="mb-1.5 block text-xs">Scrap type</Label>
              <Select value={form.scrapTypeId} onValueChange={(v) => setForm({ ...form, scrapTypeId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  {state.scrapTypes.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Quantity</Label>
              <Input
                type="number"
                step="0.01"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Reason</Label>
              <Select value={form.reason} onValueChange={(v) => setForm({ ...form, reason: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REASONS.map((r) => (
                    <SelectItem key={r} value={r}>
                      {r}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="col-span-2">
              <Label className="mb-1.5 block text-xs">Remarks</Label>
              <Textarea
                rows={2}
                value={form.remarks}
                onChange={(e) => setForm({ ...form, remarks: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Save scrap</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
