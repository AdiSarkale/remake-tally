import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  SlidersHorizontal,
} from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

import {
  Tabs,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

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
  createInventoryMovement,
  getInventoryMovements,
  getInventoryValuation,
  getMaterials,
  getProducts,
  getScrapTypes,
  type InventoryMovement,
  type InventoryValuation,
  type ItemKind,
  type MovementType,
  type MaterialData,
  type ProductData,
  type ScrapTypeData,
} from "@/lib/api";

import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/inventory")({
  head: () => ({
    meta: [
      {
        title: "Inventory — MiniTally ERP",
      },
      {
        name: "description",
        content:
          "Live stock, stock in/out, adjustments, valuation and a full inventory movement ledger.",
      },
      {
        property: "og:title",
        content: "Inventory — MiniTally ERP",
      },
      {
        property: "og:description",
        content:
          "Live stock, adjustments, valuation and movement history.",
      },
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

function today() {
  return new Date().toISOString().slice(0, 10);
}

function InventoryPage() {
  const [products, setProducts] = useState<ProductData[]>([]);
  const [materials, setMaterials] = useState<MaterialData[]>([]);
  const [scrapTypes, setScrapTypes] = useState<ScrapTypeData[]>([]);

  const [movements, setMovements] = useState<InventoryMovement[]>([]);

  const [valuation, setValuation] =
    useState<InventoryValuation | null>(null);

  const [loading, setLoading] = useState(true);

  const [tab, setTab] =
    useState<"stock" | "history">("stock");

  const [kindFilter, setKindFilter] =
    useState<"all" | ItemKind>("all");

  const [dialog, setDialog] =
    useState<MovementType | null>(null);

  const [form, setForm] = useState({
    itemKey: "",
    quantity: "",
    reference: "",
    reason: "",
    date: today(),
  });

  async function loadInventory() {
    try {
      setLoading(true);

      const [
        productsData,
        materialsData,
        scrapTypesData,
        movementsData,
        valuationData,
      ] = await Promise.all([
        getProducts(),
        getMaterials(),
        getScrapTypes(),
        getInventoryMovements(),
        getInventoryValuation(),
      ]);

      setProducts(productsData);
      setMaterials(materialsData);
      setScrapTypes(scrapTypesData);
      setMovements(movementsData);
      setValuation(valuationData);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to load inventory",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadInventory();
  }, []);

  const rows = useMemo<StockRow[]>(() => {
    return [
      ...products.map((p) => ({
        id: `product:${p.id}`,
        kind: "product" as ItemKind,
        name: p.name,
        unit: p.unit,
        stock: p.stock,
        min: p.min_stock,
        rate: p.cost_price,
        value: p.stock * p.cost_price,
      })),

      ...materials.map((m) => ({
        id: `material:${m.id}`,
        kind: "material" as ItemKind,
        name: m.name,
        unit: m.unit,
        stock: m.stock,
        min: m.min_stock,
        rate: m.cost,
        value: m.stock * m.cost,
      })),

      ...scrapTypes.map((s) => ({
        id: `scrap:${s.id}`,
        kind: "scrap" as ItemKind,
        name: s.name,
        unit: s.unit,
        stock: s.stock,
        min: 0,
        rate: s.selling_rate,
        value: s.stock * s.selling_rate,
      })),
    ];
  }, [products, materials, scrapTypes]);

  const filtered =
    kindFilter === "all"
      ? rows
      : rows.filter((row) => row.kind === kindFilter);

  const filteredMovements =
    kindFilter === "all"
      ? movements
      : movements.filter(
          (movement) =>
            movement.item_kind === kindFilter,
        );

  async function submit() {
    if (!dialog) return;

    const [kind, id] = form.itemKey.split(":");
    const qty = Number(form.quantity);

    if (!kind || !id) {
      toast.error("Select an item");
      return;
    }

    if (!Number.isFinite(qty) || qty < 0) {
      toast.error("Enter a valid quantity");
      return;
    }

    if (dialog !== "ADJUST" && qty <= 0) {
      toast.error(
        "Quantity must be greater than zero",
      );
      return;
    }

    try {
      /*
       * IMPORTANT:
       *
       * For ADJUST, quantity means the PHYSICAL COUNT.
       *
       * Example:
       * Current stock = 400
       * Counted stock = 399
       *
       * Send quantity = 399.
       *
       * The backend calculates:
       * delta = 399 - 400 = -1
       *
       * Do NOT calculate the difference here.
       */

      const movement =
        await createInventoryMovement({
          item_kind: kind as ItemKind,
          item_id: id,
          movement_type: dialog,
          quantity: qty,
          reference:
            form.reference ||
            (dialog === "ADJUST"
              ? "Physical count"
              : "Manual entry"),
          reason:
            form.reason ||
            (dialog === "IN"
              ? "Stock received"
              : dialog === "OUT"
                ? "Stock issued"
                : "Adjustment"),
          entry_date: form.date,
        });

      toast.success(
        `${movement.item_name} stock updated`,
      );

      setDialog(null);

      setForm({
        itemKey: "",
        quantity: "",
        reference: "",
        reason: "",
        date: today(),
      });

      await loadInventory();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Movement failed",
      );
    }
  }

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle="Every movement is logged with reference, reason and running balance."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => setDialog("IN")}
            >
              <ArrowDownToLine className="mr-1 h-4 w-4" />
              Stock In
            </Button>

            <Button
              variant="outline"
              onClick={() => setDialog("OUT")}
            >
              <ArrowUpFromLine className="mr-1 h-4 w-4" />
              Stock Out
            </Button>

            <Button
              onClick={() => setDialog("ADJUST")}
            >
              <SlidersHorizontal className="mr-1 h-4 w-4" />
              Adjust
            </Button>
          </>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Finished goods value"
          value={inr(
            valuation?.finished_goods ?? 0,
          )}
          tone="primary"
        />

        <StatCard
          label="Raw material value"
          value={inr(
            valuation?.raw_materials ?? 0,
          )}
        />

        <StatCard
          label="Scrap value"
          value={inr(valuation?.scrap ?? 0)}
          tone="warning"
        />

        <StatCard
          label="Total valuation"
          value={inr(valuation?.total ?? 0)}
          tone="success"
        />
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs
          value={tab}
          onValueChange={(value) =>
            setTab(value as "stock" | "history")
          }
        >
          <TabsList>
            <TabsTrigger value="stock">
              Current stock
            </TabsTrigger>

            <TabsTrigger value="history">
              Movement history
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <Select
          value={kindFilter}
          onValueChange={(value) =>
            setKindFilter(
              value as "all" | ItemKind,
            )
          }
        >
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>

          <SelectContent>
            <SelectItem value="all">
              All item types
            </SelectItem>

            <SelectItem value="product">
              Finished goods
            </SelectItem>

            <SelectItem value="material">
              Raw materials
            </SelectItem>

            <SelectItem value="scrap">
              Scrap
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div className="rounded-lg border p-8 text-center text-muted-foreground">
          Loading inventory...
        </div>
      ) : tab === "stock" ? (
        <DataTable
          rows={filtered}
          rowKey={(row) => row.id}
          searchable={(row) =>
            `${row.name} ${row.kind}`
          }
          pageSize={12}
          columns={[
            {
              key: "name",
              header: "Item",
              value: (row) => row.name,
            },

            {
              key: "kind",
              header: "Type",
              value: (row) => row.kind,
              render: (row) => (
                <Badge variant="secondary">
                  {row.kind === "product"
                    ? "Finished"
                    : row.kind === "material"
                      ? "Raw"
                      : "Scrap"}
                </Badge>
              ),
            },

            {
              key: "stock",
              header: "On hand",
              align: "right",
              value: (row) => row.stock,
              render: (row) => (
                <span
                  className={
                    row.min > 0 &&
                    row.stock <= row.min
                      ? "num text-destructive font-medium"
                      : "num"
                  }
                >
                  {num(row.stock, 1)}{" "}
                  {row.unit}
                </span>
              ),
            },

            {
              key: "min",
              header: "Min",
              align: "right",
              value: (row) => row.min,
              render: (row) => (
                <span className="num text-muted-foreground">
                  {row.min
                    ? num(row.min)
                    : "—"}
                </span>
              ),
            },

            {
              key: "rate",
              header: "Rate",
              align: "right",
              value: (row) => row.rate,
              render: (row) => (
                <span className="num">
                  {inr(row.rate)}
                </span>
              ),
            },

            {
              key: "value",
              header: "Value",
              align: "right",
              value: (row) => row.value,
              render: (row) => (
                <span className="num font-medium">
                  {inr(row.value)}
                </span>
              ),
            },
          ]}
        />
      ) : (
        <DataTable
          rows={filteredMovements}
          rowKey={(movement) => movement.id}
          pageSize={12}
          searchable={(movement) =>
            `${movement.item_name} ${movement.reference} ${movement.reason} ${movement.movement_type}`
          }
          columns={[
            {
              key: "date",
              header: "Date",
              value: (movement) =>
                movement.entry_date,
              render: (movement) =>
                dmy(movement.entry_date),
            },

            {
              key: "item",
              header: "Item",
              value: (movement) =>
                movement.item_name,
            },

            {
              key: "type",
              header: "Type",
              value: (movement) =>
                movement.movement_type,
              render: (movement) => (
                <Badge
                  variant={
                    movement.movement_type ===
                    "IN"
                      ? "default"
                      : movement.movement_type ===
                          "OUT"
                        ? "secondary"
                        : "outline"
                  }
                >
                  {movement.movement_type}
                </Badge>
              ),
            },

            {
              key: "qty",
              header: "Qty",
              align: "right",
              value: (movement) =>
                movement.quantity,
              render: (movement) => (
                <span className="num">
                  {num(
                    movement.quantity,
                    1,
                  )}{" "}
                  {movement.unit}
                </span>
              ),
            },

            {
              key: "balance",
              header: "Balance",
              align: "right",
              value: (movement) =>
                movement.balance,
              render: (movement) => (
                <span className="num font-medium">
                  {num(
                    movement.balance,
                    1,
                  )}{" "}
                  {movement.unit}
                </span>
              ),
            },

            {
              key: "ref",
              header: "Reference",
              value: (movement) =>
                movement.reference,
              className: "num text-xs",
            },

            {
              key: "reason",
              header: "Reason",
              value: (movement) =>
                movement.reason,
            },
          ]}
        />
      )}

      <Dialog
        open={!!dialog}
        onOpenChange={(open) => {
          if (!open) {
            setDialog(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {dialog === "IN"
                ? "Stock in"
                : dialog === "OUT"
                  ? "Stock out"
                  : "Adjust stock"}
            </DialogTitle>

            <DialogDescription>
              {dialog === "ADJUST"
                ? "Enter the counted physical quantity. The backend will calculate the adjustment."
                : "Quantity is added to or removed from the running balance."}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div>
              <Label className="mb-1.5 block text-xs">
                Item
              </Label>

              <Select
                value={form.itemKey}
                onValueChange={(value) =>
                  setForm({
                    ...form,
                    itemKey: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select an item" />
                </SelectTrigger>

                <SelectContent>
                  {rows.map((row) => (
                    <SelectItem
                      key={row.id}
                      value={row.id}
                    >
                      {row.name} (
                      {num(row.stock, 1)}{" "}
                      {row.unit})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="mb-1.5 block text-xs">
                  {dialog === "ADJUST"
                    ? "Counted quantity"
                    : "Quantity"}
                </Label>

                <Input
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.quantity}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      quantity:
                        event.target.value,
                    })
                  }
                />
              </div>

              <div>
                <Label className="mb-1.5 block text-xs">
                  Date
                </Label>

                <Input
                  type="date"
                  value={form.date}
                  onChange={(event) =>
                    setForm({
                      ...form,
                      date:
                        event.target.value,
                    })
                  }
                />
              </div>
            </div>

            <div>
              <Label className="mb-1.5 block text-xs">
                Reference
              </Label>

              <Input
                value={form.reference}
                onChange={(event) =>
                  setForm({
                    ...form,
                    reference:
                      event.target.value,
                  })
                }
                placeholder="GRN / Issue slip / Count sheet"
              />
            </div>

            <div>
              <Label className="mb-1.5 block text-xs">
                Reason
              </Label>

              <Input
                value={form.reason}
                onChange={(event) =>
                  setForm({
                    ...form,
                    reason:
                      event.target.value,
                  })
                }
                placeholder="Why is stock changing?"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDialog(null)}
            >
              Cancel
            </Button>

            <Button onClick={() => void submit()}>
              Post movement
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
