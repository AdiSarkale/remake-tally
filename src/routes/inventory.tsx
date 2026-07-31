import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowDownToLine, ArrowUpFromLine, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { inventoryValue, stockMovement, today, useErp } from "@/lib/erp/store";
import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";
import type { ItemKind, MovementType } from "@/lib/erp/types";

export const Route = createFileRoute("/inventory")({
  head: () => ({
    meta: [
      { title: "Inventory — MiniTally ERP" },
      {
        name: "description",
        content: "Live stock, stock in/out, adjustments, valuation and a full inventory movement ledger.",
      },
      { property: "og:title", content: "Inventory — MiniTally ERP" },
      { property: "og:description", content: "Live stock, adjustments, valuation and movement history." },
    ],
  }),
  component: () => (
    <AppShell>
      <InventoryPage />
    </AppShell>
  ),
});

interface StockRow {
  id: string;
  kind: ItemKind;
  name: string;
  unit: string;
  stock: number;
  min: number;
  rate: number;
  value: number;
}

function InventoryPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const value = inventoryValue(state);
  const [tab, setTab] = useState<"stock" | "history">("stock");
  const [kindFilter, setKindFilter] = useState<"all" | ItemKind>("all");
  const [dialog, setDialog] = useState<MovementType | null>(null);
  const [form, setForm] = useState({ itemKey: "", quantity: "", reference: "", reason: "", date: today() });

  const rows = useMemo<StockRow[]>(
    () => [
      ...state.products.map((p) => ({
        id: `product:${p.id}`,
        kind: "product" as ItemKind,
        name: p.name,
        unit: p.unit,
        stock: p.stock,
        min: p.minStock,
        rate: p.costPrice,
        value: p.stock * p.costPrice,
      })),
      ...state.materials.map((m) => ({
        id: `material:${m.id}`,
        kind: "material" as ItemKind,
        name: m.name,
        unit: m.unit,
        stock: m.stock,
        min: m.minStock,
        rate: m.cost,
        value: m.stock * m.cost,
      })),
      ...state.scrapTypes.map((s) => ({
        id: `scrap:${s.id}`,
        kind: "scrap" as ItemKind,
        name: s.name,
        unit: s.unit,
        stock: s.stock,
        min: 0,
        rate: s.sellingRate,
        value: s.stock * s.sellingRate,
      })),
    ],
    [state],
  );

  const filtered = kindFilter === "all" ? rows : rows.filter((r) => r.kind === kindFilter);
  const movements =
    kindFilter === "all" ? state.movements : state.movements.filter((m) => m.itemKind === kindFilter);

  const submit = () => {
    if (!dialog) return;
    const [kind, id] = form.itemKey.split(":");
    const qty = Number(form.quantity);
    if (!kind || !id) return toast.error("Select an item");
    if (!Number.isFinite(qty) || qty < 0) return toast.error("Enter a valid quantity");
    try {
      stockMovement(
        {
          itemKind: kind as ItemKind,
          itemId: id,
          type: dialog,
          quantity: qty,
          reference: form.reference || (dialog === "ADJUST" ? "Physical count" : "Manual entry"),
          reason: form.reason || (dialog === "IN" ? "Stock received" : dialog === "OUT" ? "Stock issued" : "Adjustment"),
          date: form.date,
        },
        session?.username ?? "system",
      );
      toast.success("Stock updated");
      setDialog(null);
      setForm({ itemKey: "", quantity: "", reference: "", reason: "", date: today() });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Movement failed");
    }
  };

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle="Every movement is logged with reference, reason and running balance."
        actions={
          <>
            <Button variant="outline" onClick={() => setDialog("IN")}>
              <ArrowDownToLine className="mr-1 h-4 w-4" /> Stock In
            </Button>
            <Button variant="outline" onClick={() => setDialog("OUT")}>
              <ArrowUpFromLine className="mr-1 h-4 w-4" /> Stock Out
            </Button>
            <Button onClick={() => setDialog("ADJUST")}>
              <SlidersHorizontal className="mr-1 h-4 w-4" /> Adjust
            </Button>
          </>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Finished goods value" value={inr(value.fg)} tone="primary" />
        <StatCard label="Raw material value" value={inr(value.rm)} />
        <StatCard label="Scrap value" value={inr(value.sc)} tone="warning" />
        <StatCard label="Total valuation" value={inr(value.total)} tone="success" />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={tab} onValueChange={(v) => setTab(v as "stock" | "history")}>
          <TabsList>
            <TabsTrigger value="stock">Current stock</TabsTrigger>
            <TabsTrigger value="history">Movement history</TabsTrigger>
          </TabsList>
        </Tabs>
        <Select value={kindFilter} onValueChange={(v) => setKindFilter(v as typeof kindFilter)}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All item types</SelectItem>
            <SelectItem value="product">Finished goods</SelectItem>
            <SelectItem value="material">Raw materials</SelectItem>
            <SelectItem value="scrap">Scrap</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {tab === "stock" ? (
        <DataTable
          rows={filtered}
          rowKey={(r) => r.id}
          searchable={(r) => `${r.name} ${r.kind}`}
          pageSize={12}
          columns={[
            { key: "name", header: "Item", value: (r) => r.name },
            {
              key: "kind",
              header: "Type",
              value: (r) => r.kind,
              render: (r) => (
                <Badge variant="secondary">
                  {r.kind === "product" ? "Finished" : r.kind === "material" ? "Raw" : "Scrap"}
                </Badge>
              ),
            },
            {
              key: "stock",
              header: "On hand",
              align: "right",
              value: (r) => r.stock,
              render: (r) => (
                <span className={r.min > 0 && r.stock <= r.min ? "num text-destructive font-medium" : "num"}>
                  {num(r.stock, 1)} {r.unit}
                </span>
              ),
            },
            {
              key: "min",
              header: "Min",
              align: "right",
              value: (r) => r.min,
              render: (r) => <span className="num text-muted-foreground">{r.min ? num(r.min) : "—"}</span>,
            },
            {
              key: "rate",
              header: "Rate",
              align: "right",
              value: (r) => r.rate,
              render: (r) => <span className="num">{inr(r.rate)}</span>,
            },
            {
              key: "value",
              header: "Value",
              align: "right",
              value: (r) => r.value,
              render: (r) => <span className="num font-medium">{inr(r.value)}</span>,
            },
          ]}
        />
      ) : (
        <DataTable
          rows={movements}
          rowKey={(m) => m.id}
          pageSize={12}
          searchable={(m) => `${m.itemName} ${m.reference} ${m.reason} ${m.type}`}
          columns={[
            { key: "date", header: "Date", value: (m) => m.date, render: (m) => dmy(m.date) },
            { key: "item", header: "Item", value: (m) => m.itemName },
            {
              key: "type",
              header: "Type",
              value: (m) => m.type,
              render: (m) => (
                <Badge variant={m.type === "IN" ? "default" : m.type === "OUT" ? "secondary" : "outline"}>
                  {m.type}
                </Badge>
              ),
            },
            {
              key: "qty",
              header: "Qty",
              align: "right",
              value: (m) => m.quantity,
              render: (m) => (
                <span className="num">
                  {num(m.quantity, 1)} {m.unit}
                </span>
              ),
            },
            { key: "ref", header: "Reference", value: (m) => m.reference, className: "num text-xs" },
            { key: "reason", header: "Reason", value: (m) => m.reason },
          ]}
        />
      )}

      <Dialog open={!!dialog} onOpenChange={(o) => !o && setDialog(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {dialog === "IN" ? "Stock in" : dialog === "OUT" ? "Stock out" : "Adjust stock"}
            </DialogTitle>
            <DialogDescription>
              {dialog === "ADJUST"
                ? "Enter the counted physical quantity — the difference is logged as an adjustment."
                : "Quantity is added to or removed from the running balance."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="mb-1.5 block text-xs">Item</Label>
              <Select value={form.itemKey} onValueChange={(v) => setForm({ ...form, itemKey: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select an item" />
                </SelectTrigger>
                <SelectContent>
                  {rows.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name} ({num(r.stock, 1)} {r.unit})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="mb-1.5 block text-xs">
                  {dialog === "ADJUST" ? "Counted quantity" : "Quantity"}
                </Label>
                <Input
                  type="number"
                  step="0.01"
                  value={form.quantity}
                  onChange={(e) => setForm({ ...form, quantity: e.target.value })}
                />
              </div>
              <div>
                <Label className="mb-1.5 block text-xs">Date</Label>
                <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
              </div>
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Reference</Label>
              <Input
                value={form.reference}
                onChange={(e) => setForm({ ...form, reference: e.target.value })}
                placeholder="GRN / Issue slip / Count sheet"
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Reason</Label>
              <Input
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                placeholder="Why is stock changing?"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>
              Cancel
            </Button>
            <Button onClick={submit}>Post movement</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
