/* eslint-disable prettier/prettier */
import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";
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

import {
  createProduction as createProductionApi,
  getProducts,
  getProduction,
  type ProductData,
  type ProductionData,
} from "@/lib/api";

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

const SHIFTS = ["A", "B", "C"] as const;

function ProductionPage() {
const [products, setProducts] = useState<ProductData[]>([]);
function today() {
  return new Date().toISOString().slice(0, 10);
}

const productNames = new Map(
  products.map((p) => [p.id, p.name]),
);
const [production, setProduction] = useState<ProductionData[]>([]);
const [loading, setLoading] = useState(true);
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

  const day = today();
  const month = day.slice(0, 7);
  const todayQty = production
  .filter((p) => p.entry_date === day)
  .reduce((total, p) => total + p.quantity, 0);

const monthQty = production
  .filter((p) => p.entry_date.startsWith(month))
  .reduce((total, p) => total + p.quantity, 0);

  useEffect(() => {
  Promise.all([
    getProducts(),
    getProduction(),
  ])
.then(([productsData, productionData]) => {
      setProducts(productsData);
      setProduction(productionData);
    })
    .catch((error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to load production data",
      );
    })
    .finally(() => {
      setLoading(false);
    });
}, []);
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
  };


  const submit = async () => {
  if (!form.productId) {
    toast.error("Select a product");
    return;
  }

  const qty = Number(form.quantity);

  if (!qty || qty <= 0) {
    toast.error("Enter a valid production quantity");
    return;
  }

  try {
    await createProductionApi({
      entry_date: form.date,
      product_id: form.productId,
      quantity: qty,
      machine: form.machine,
      operator: form.operator,
      shift: form.shift,
      remarks: form.remarks,
    });

    toast.success("Production posted — stock updated");

    const [productsData, materialsData, productionData] =
      await Promise.all([
        getProducts(),
        getMaterials(),
        getProduction(),
      ]);

    setProducts(productsData);
    setMaterials(materialsData);
    setProduction(productionData);

    setOpen(false);
    reset();
  } catch (err) {
    toast.error(
      err instanceof Error
        ? err.message
        : "Could not post production",
    );
  }
};

  return (
    <>
      <PageHeader
        title="Production"
        subtitle="Each entry increases finished goods and consumes raw materials from the active BOM."
        actions={
          <Button
            disabled={loading}
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
        <StatCard label="Batches recorded" value={num(production.length)}/>
      </div>

      <DataTable
        rows={production}
        rowKey={(p) => p.id}
        pageSize={12}
        searchable={(p) =>
  `${p.batch_no} ${productNames.get(p.product_id) ?? ""} ${p.machine} ${p.operator}`
}
        columns={[
          { key: "batch", header: "Batch", value: (p) => p.batch_no, className: "num text-xs" },
          { key: "date", header: "Date", value: (p) => p.entry_date, render: (p) => dmy(p.entry_date) },
          { key: "product", header: "Product", value: (p) => p.product_id },
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
          // {
          //   key: "consumed",
          //   header: "Materials consumed",
          //   render: (p) => (
          //     <span className="text-muted-foreground text-xs">
          //       {p.consumption.map((c) => `${c.materialName} ${num(c.quantity, 1)}${c.unit}`).join(", ")}
          //     </span>
          //   ),
          // },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>New production entry</DialogTitle>
            <DialogDescription>
              Posting will add finished goods to stock and issue raw materials from the active BOM.
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
                  {products.map((p) => (
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

          <div className="mt-2 rounded-md border p-3 text-sm text-muted-foreground">
            Raw material consumption is calculated automatically from the active BOM.
            Manual actual-consumption variance will be enabled in Phase 1.
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={loading} onClick={submit}>Post production</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
