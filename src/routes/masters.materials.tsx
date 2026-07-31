import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/erp/AppShell";
import { MasterPage } from "@/components/erp/MasterPage";
import { Badge } from "@/components/ui/badge";
import { inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/masters/materials")({
  head: () => ({
    meta: [
      { title: "Raw Materials — MiniTally ERP" },
      { name: "description", content: "Raw material master with unit cost, live stock and reorder levels." },
      { property: "og:title", content: "Raw Materials — MiniTally ERP" },
      { property: "og:description", content: "Raw material master with unit cost, live stock and reorder levels." },
    ],
  }),
  component: () => (
    <AppShell>
      <MasterPage
        title="Raw Materials"
        subtitle="Inputs consumed by production batches."
        entity="materials"
        defaults={{ stock: 0 }}
        searchable={(r) => `${r.name} ${r.unit}`}
        fields={[
          { name: "name", label: "Material Name", required: true, full: true },
          { name: "unit", label: "Unit", placeholder: "KG / LTR / PCS" },
          { name: "cost", label: "Cost per unit", type: "number", step: "0.01" },
          { name: "minStock", label: "Minimum Stock", type: "number" },
        ]}
        columns={[
          { key: "name", header: "Material", value: (r) => String(r.name) },
          { key: "unit", header: "Unit", value: (r) => String(r.unit) },
          {
            key: "cost",
            header: "Cost",
            align: "right",
            value: (r) => Number(r.cost ?? 0),
            render: (r) => <span className="num">{inr(Number(r.cost ?? 0))}</span>,
          },
          {
            key: "stock",
            header: "Stock",
            align: "right",
            value: (r) => Number(r.stock ?? 0),
            render: (r) =>
              Number(r.stock ?? 0) <= Number(r.minStock ?? 0) ? (
                <Badge variant="destructive">{num(Number(r.stock ?? 0), 1)}</Badge>
              ) : (
                <span className="num">{num(Number(r.stock ?? 0), 1)}</span>
              ),
          },
          {
            key: "value",
            header: "Value",
            align: "right",
            value: (r) => Number(r.stock ?? 0) * Number(r.cost ?? 0),
            render: (r) => <span className="num">{inr(Number(r.stock ?? 0) * Number(r.cost ?? 0))}</span>,
          },
        ]}
      />
    </AppShell>
  ),
});
