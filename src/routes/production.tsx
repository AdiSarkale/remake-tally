import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, Trash2 } from "lucide-react";
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
import { createProduction, nextBatchNo, today, useErp, getState } from "@/lib/erp/store";
import { dmy, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";

export const Route = createFileRoute("/production")({
  head: () => ({
    meta: [
      { title: "Production — MiniTally ERP" },
      {
        name: "description",
        content: "Record production batches: output increases finished goods, consumption reduces raw material stock.",
      },
      { property: "og:title", content: "Production — MiniTally ERP" },
      { property: "og:description", content: "Record batches with automatic stock postings and material consumption." },
    ],
  }),
  component: () => (
    <AppShell>
      <ProductionPage />
    </AppShell>
  ),
});

interface Line {
  materialId: string;
  quantity: string;
}

const SHIFTS = ["A", "B", "C"] as const;

function ProductionPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    date: today(),
    productId: "",
    quantity: "",
    machine: "",
    operator: session?.fullName ?? "",
    shift: "A" as (typeof SHIFTS)[number],
    remarks: "",
  });
  const [lines, setLines] = useState<Line[]>([{ materialId: "", quantity: "" }]);

  const day = today();
  const month = day.slice(0, 7);
  const todayQty = state.production.filter((p) => p.date === day).reduce((t, p) => t + p.quantity, 0);
  const monthQty = state.production.filter((p) => p.date.startsWith(month)).reduce((t, p) => t + p.quantity, 0);

  const batchNo = useMemo(() => nextBatchNo(state), [state]);

  const reset = () => {
    setForm({
      date: today(),
      productId: "",
      quantity: "",
      machine: "",
      operator: session?.fullName ?? "",
      shift: "A",
      remarks: "",
    });
    setLines([{ materialId: "", quantity: "" }]);
  };

  const submit = () => {
    if (!form.productId) {
      toast.error("Select the product produced");
      return;
    }
    const qty = Number(form.quantity);
    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error("Enter a valid production quantity");
      return;
    }
    const consumption = lines
      .filter((l) => l.materialId && Number(l.quantity) > 0)
      .map((l) => ({
        materialId: l.materialId,
        materialName: "",
        unit: "",
        quantity: Number(l.quantity),
      }));
    if (consumption.length === 0) {
      toast.error("Add at least one raw material consumed");
      return;
    }
    try {
      createProduction(
        {
          date: form.date,
          productId: form.productId,
          quantity: qty,
          machine: form.machine,
          operator: form.operator,
          shift: form.shift,
          remarks: form.remarks,
          consumption,
          batchNo: nextBatchNo(getState()),
        },
        session?.username ?? "system",
      );
      toast.success("Production posted — stock updated");
      setOpen(false);
      reset();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not post production");
    }
  };

  return (
    <>
      <PageHeader
        title="Production"
        subtitle="Each entry increases finished goods and consumes raw materials automatically."
        actions={
          <Button
            onClick={() => {
              reset();
              setOpen(true);
            }}
          >
            <Plus className="mr-1 h-4 w-4" /> New batch
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <StatCard label="Produced today" value={`${num(todayQty)} pcs`} tone="primary" />
        <StatCard label="Produced this month" value={`${num(monthQty)} pcs`} />
        <StatCard label="Batches recorded" value={num(state.production.length)} hint={`Next: ${batchNo}`} />
      </div>

      <DataTable
        rows={state.production}
        rowKey={(p) => p.id}
        pageSize={12}
        searchable={(p) => `${p.batchNo} ${p.productName} ${p.machine} ${p.operator}`}
        columns={[
          { key: "batch", header: "Batch", value: (p) => p.batchNo, className: "num text-xs" },
          { key: "date", header: "Date", value: (p) => p.date, render: (p) => dmy(p.date) },
          { key: "product", header: "Product", value: (p) => p.productName },
          {
            key: "qty",
            header: "Qty",
            align: "right",
            value: (p) => p.quantity,
            render: (p) => <span className="num font-medium">{num(p.quantity)}</span>,
          },
          { key: "machine", header: "Machine", value: (p) => p.machine },
          { key: "operator", header: "Operator", value: (p) => p.operator },
          {
            key: "shift",
            header: "Shift",
            value: (p) => p.shift,
            render: (p) => <Badge variant="secondary">{p.shift}</Badge>,
          },
          {
            key: "consumed",
            header: "Materials consumed",
            render: (p) => (
              <span className="text-muted-foreground text-xs">
                {p.consumption.map((c) => `${c.materialName} ${num(c.quantity, 1)}${c.unit}`).join(", ")}
              </span>
            ),
          },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>New production entry — {batchNo}</DialogTitle>
            <DialogDescription>
              Posting will add finished goods to stock and issue the listed raw materials.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="mb-1.5 block text-xs">Production date</Label>
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Shift</Label>
              <Select
                value={form.shift}
                onValueChange={(v) => setForm({ ...form, shift: v as (typeof SHIFTS)[number] })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SHIFTS.map((s) => (
                    <SelectItem key={s} value={s}>
                      Shift {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Product produced</Label>
              <Select value={form.productId} onValueChange={(v) => setForm({ ...form, productId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select product" />
                </SelectTrigger>
                <SelectContent>
                  {state.products.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.code} — {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Quantity produced</Label>
              <Input
                type="number"
                value={form.quantity}
                onChange={(e) => setForm({ ...form, quantity: e.target.value })}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Machine</Label>
              <Input
                value={form.machine}
                onChange={(e) => setForm({ ...form, machine: e.target.value })}
                placeholder="CNC-01"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Operator</Label>
              <Input value={form.operator} onChange={(e) => setForm({ ...form, operator: e.target.value })} />
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

          <div className="mt-2">
            <div className="mb-2 flex items-center justify-between">
              <Label className="text-xs">Raw material consumption</Label>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setLines([...lines, { materialId: "", quantity: "" }])}
              >
                <Plus className="mr-1 h-3 w-3" /> Add line
              </Button>
            </div>
            <div className="space-y-2">
              {lines.map((line, i) => {
                const mat = state.materials.find((m) => m.id === line.materialId);
                return (
                  <div key={i} className="flex items-center gap-2">
                    <Select
                      value={line.materialId}
                      onValueChange={(v) =>
                        setLines(lines.map((l, li) => (li === i ? { ...l, materialId: v } : l)))
                      }
                    >
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder="Select material" />
                      </SelectTrigger>
                      <SelectContent>
                        {state.materials.map((m) => (
                          <SelectItem key={m.id} value={m.id}>
                            {m.name} ({num(m.stock, 1)} {m.unit})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input
                      type="number"
                      step="0.01"
                      className="w-32"
                      placeholder="Qty"
                      value={line.quantity}
                      onChange={(e) =>
                        setLines(lines.map((l, li) => (li === i ? { ...l, quantity: e.target.value } : l)))
                      }
                    />
                    <span className="text-muted-foreground w-10 text-xs">{mat?.unit ?? ""}</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setLines(lines.filter((_, li) => li !== i))}
                      aria-label="Remove line"
                    >
                      <Trash2 className="text-destructive h-4 w-4" />
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Post production</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
