import { useEffect, useMemo, useState } from "react";
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

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  createScrap,
  getDashboard,
  getProducts,
  getScrap,
  getScrapTypes,
  type DashboardData,
  type ProductData,
  type ScrapData,
  type ScrapTypeData,
} from "@/lib/api";

import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/scrap")({
  head: () => ({
    meta: [
      {
        title: "Scrap Management — MiniTally ERP",
      },
      {
        name: "description",
        content:
          "Log production scrap by type and reason, track scrap rate and realisable scrap value.",
      },
      {
        property: "og:title",
        content: "Scrap Management — MiniTally ERP",
      },
      {
        property: "og:description",
        content:
          "Track scrap by type and reason with realisable value.",
      },
    ],
  }),

  component: () => (
    <AppShell>
      <ScrapPage />
    </AppShell>
  ),
});

const REASONS: string[] = [
  "Machine setup",
  "Material defect",
  "Operator error",
  "Tool wear",
  "Rejected at QC",
  "Other",
];

const CHART_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
];

function today() {
  return new Date().toISOString().slice(0, 10);
}

function ScrapPage() {
  const [products, setProducts] = useState<ProductData[]>([]);
  const [scrapTypes, setScrapTypes] = useState<ScrapTypeData[]>([]);
  const [scrap, setScrap] = useState<ScrapData[]>([]);
  const [dashboard, setDashboard] =
    useState<DashboardData | null>(null);

  const [loading, setLoading] = useState(true);
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

  async function loadScrap() {
    try {
      setLoading(true);

      const [
        productsData,
        scrapTypesData,
        scrapData,
        dashboardData,
      ] = await Promise.all([
        getProducts(),
        getScrapTypes(),
        getScrap(),
        getDashboard(),
      ]);

      setProducts(productsData);
      setScrapTypes(scrapTypesData);
      setScrap(scrapData);
      setDashboard(dashboardData);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to load scrap data",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadScrap();
  }, []);

  const productMap = useMemo(() => {
    return new Map(
      products.map((product) => [
        product.id,
        product,
      ]),
    );
  }, [products]);

  const scrapTypeMap = useMemo(() => {
    return new Map(
      scrapTypes.map((type) => [
        type.id,
        type,
      ]),
    );
  }, [scrapTypes]);

  const monthlyScrap = dashboard?.scrap_month ?? 0;
  const scrapRate = dashboard?.scrap_rate ?? 0;

  const byType = useMemo(() => {
    return scrapTypes
      .map((type) => ({
        name: type.name,

        qty: scrap
          .filter(
            (entry) =>
              entry.scrap_type_id === type.id,
          )
          .reduce(
            (total, entry) =>
              total + entry.quantity,
            0,
          ),

        value:
          type.stock * type.selling_rate,
      }))
      .filter((item) => item.qty > 0);
  }, [scrap, scrapTypes]);

  const byReason = useMemo(() => {
    return REASONS.map((reason) => ({
      reason,

      qty: scrap
        .filter(
          (entry) => entry.reason === reason,
        )
        .reduce(
          (total, entry) =>
            total + entry.quantity,
          0,
        ),
    })).filter((item) => item.qty > 0);
  }, [scrap]);

  const realisableValue = useMemo(() => {
    return scrapTypes.reduce(
      (total, type) =>
        total +
        type.stock * type.selling_rate,
      0,
    );
  }, [scrapTypes]);

  async function submit() {
    const qty = Number(form.quantity);

    if (
      !form.productId ||
      !form.scrapTypeId
    ) {
      toast.error(
        "Select product and scrap type",
      );
      return;
    }

    if (!Number.isFinite(qty) || qty <= 0) {
      toast.error(
        "Enter a valid scrap quantity",
      );
      return;
    }

    try {
      await createScrap({
        entry_date: form.date,
        product_id: form.productId,
        batch_no: form.batchNo,
        scrap_type_id: form.scrapTypeId,
        quantity: qty,
        reason: form.reason,
        remarks: form.remarks,
      });

      toast.success("Scrap recorded");

      setOpen(false);

      setForm({
        ...form,
        quantity: "",
        batchNo: "",
        remarks: "",
      });

      await loadScrap();
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not record scrap",
      );
    }
  }

  return (
    <>
      <PageHeader
        title="Scrap Management"
        subtitle="Scrap is added to scrap stock and measured against production output."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Record scrap
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Scrap this month"
          value={`${num(monthlyScrap, 1)} units`}
          tone="warning"
        />

        <StatCard
          label="Scrap rate"
          value={`${num(scrapRate, 2)}%`}
          hint="Scrap ÷ production"
        />

        <StatCard
          label="Entries logged"
          value={num(scrap.length)}
        />

        <StatCard
          label="Realisable value"
          value={inr(realisableValue)}
          tone="success"
        />
      </div>

      {loading ? (
        <div className="rounded-lg border p-8 text-center text-muted-foreground">
          Loading scrap data...
        </div>
      ) : (
        <>
          <div className="mb-4 grid gap-4 lg:grid-cols-2">
            <div className="panel p-4">
              <h2 className="mb-3 text-sm font-semibold">
                Scrap by type
              </h2>

              <div className="h-64">
                {byType.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No scrap recorded yet.
                  </div>
                ) : (
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                  >
                    <PieChart>
                      <Pie
                        data={byType}
                        dataKey="qty"
                        nameKey="name"
                        innerRadius={55}
                        outerRadius={90}
                        paddingAngle={2}
                      >
                        {byType.map(
                          (_, index) => (
                            <Cell
                              key={index}
                              fill={
                                CHART_COLORS[
                                  index %
                                    CHART_COLORS.length
                                ]
                              }
                            />
                          ),
                        )}
                      </Pie>

                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            <div className="panel p-4">
              <h2 className="mb-3 text-sm font-semibold">
                Scrap by reason
              </h2>

              <div className="h-64">
                {byReason.length === 0 ? (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    No scrap recorded yet.
                  </div>
                ) : (
                  <ResponsiveContainer
                    width="100%"
                    height="100%"
                  >
                    <BarChart data={byReason}>
                      <CartesianGrid
                        strokeDasharray="3 3"
                        stroke="var(--color-border)"
                        vertical={false}
                      />

                      <XAxis
                        dataKey="reason"
                        tick={{ fontSize: 10 }}
                        interval={0}
                        angle={-15}
                        height={50}
                        dy={10}
                      />

                      <YAxis
                        tick={{ fontSize: 11 }}
                      />

                      <Tooltip />

                      <Bar
                        dataKey="qty"
                        fill="var(--color-primary)"
                        radius={[
                          4,
                          4,
                          0,
                          0,
                        ]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </div>

          <DataTable
            rows={scrap}
            rowKey={(entry) => entry.id}
            pageSize={12}
            searchable={(entry) => {
              const product =
                productMap.get(
                  entry.product_id,
                );

              const scrapType =
                scrapTypeMap.get(
                  entry.scrap_type_id,
                );

              return `${product?.name ?? ""} ${
                scrapType?.name ?? ""
              } ${entry.reason} ${
                entry.batch_no
              }`;
            }}
            columns={[
              {
                key: "date",
                header: "Date",
                value: (entry) =>
                  entry.entry_date,
                render: (entry) =>
                  dmy(entry.entry_date),
              },

              {
                key: "batch",
                header: "Batch",
                value: (entry) =>
                  entry.batch_no,
                className:
                  "num text-xs",
              },

              {
                key: "product",
                header: "Product",
                value: (entry) =>
                  productMap.get(
                    entry.product_id,
                  )?.name ??
                  entry.product_id,
              },

              {
                key: "type",
                header: "Scrap type",
                value: (entry) =>
                  scrapTypeMap.get(
                    entry.scrap_type_id,
                  )?.name ??
                  entry.scrap_type_id,
              },

              {
                key: "qty",
                header: "Qty",
                align: "right",
                value: (entry) =>
                  entry.quantity,
                render: (entry) => (
                  <span className="num font-medium">
                    {num(
                      entry.quantity,
                      1,
                    )}
                  </span>
                ),
              },

              {
                key: "reason",
                header: "Reason",
                value: (entry) =>
                  entry.reason,
              },

              {
                key: "remarks",
                header: "Remarks",
                value: (entry) =>
                  entry.remarks,
                className:
                  "text-muted-foreground text-xs",
              },
            ]}
          />
        </>
      )}

      <Dialog
        open={open}
        onOpenChange={setOpen}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              Record scrap
            </DialogTitle>

            <DialogDescription>
              Scrap quantity is added to scrap
              stock for later sale.
            </DialogDescription>
          </DialogHeader>

          <div className="grid grid-cols-2 gap-3">
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

            <div>
              <Label className="mb-1.5 block text-xs">
                Batch no.
              </Label>

              <Input
                value={form.batchNo}
                onChange={(event) =>
                  setForm({
                    ...form,
                    batchNo:
                      event.target.value,
                  })
                }
                placeholder="BATCH-0001"
              />
            </div>

            <div>
              <Label className="mb-1.5 block text-xs">
                Product
              </Label>

              <Select
                value={form.productId}
                onValueChange={(value) =>
                  setForm({
                    ...form,
                    productId: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select product" />
                </SelectTrigger>

                <SelectContent>
                  {products.map((product) => (
                    <SelectItem
                      key={product.id}
                      value={product.id}
                    >
                      {product.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="mb-1.5 block text-xs">
                Scrap type
              </Label>

              <Select
                value={form.scrapTypeId}
                onValueChange={(value) =>
                  setForm({
                    ...form,
                    scrapTypeId: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>

                <SelectContent>
                  {scrapTypes.map((type) => (
                    <SelectItem
                      key={type.id}
                      value={type.id}
                    >
                      {type.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="mb-1.5 block text-xs">
                Quantity
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
                Reason
              </Label>

              <Select
                value={form.reason}
                onValueChange={(value) =>
                  setForm({
                    ...form,
                    reason: value,
                  })
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>

                <SelectContent>
                  {REASONS.map((reason) => (
                    <SelectItem
                      key={reason}
                      value={reason}
                    >
                      {reason}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="col-span-2">
              <Label className="mb-1.5 block text-xs">
                Remarks
              </Label>

              <Textarea
                rows={2}
                value={form.remarks}
                onChange={(event) =>
                  setForm({
                    ...form,
                    remarks:
                      event.target.value,
                  })
                }
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>

            <Button
              onClick={() => void submit()}
            >
              Save scrap
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
