import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/erp/AppShell";
import { MasterPage } from "@/components/erp/MasterPage";
import { inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/masters/scrap-types")({
  head: () => ({
    meta: [
      { title: "Scrap Types — MiniTally ERP" },
      { name: "description", content: "Define scrap categories, units and realisable selling rates." },
      { property: "og:title", content: "Scrap Types — MiniTally ERP" },
      { property: "og:description", content: "Define scrap categories, units and realisable selling rates." },
    ],
  }),
  component: () => (
    <AppShell>
      <MasterPage
        title="Scrap Types"
        subtitle="Categories used when recording production scrap."
        entity="scrapTypes"
        defaults={{ stock: 0 }}
        searchable={(r) => `${r.name} ${r.unit}`}
        fields={[
          { name: "name", label: "Scrap Name", required: true, full: true },
          { name: "unit", label: "Unit", placeholder: "KG / PCS" },
          { name: "sellingRate", label: "Selling Rate", type: "number", step: "0.01" },
        ]}
        columns={[
          { key: "name", header: "Scrap", value: (r) => String(r.name) },
          { key: "unit", header: "Unit", value: (r) => String(r.unit) },
          {
            key: "rate",
            header: "Rate",
            align: "right",
            value: (r) => Number(r.sellingRate ?? 0),
            render: (r) => <span className="num">{inr(Number(r.sellingRate ?? 0))}</span>,
          },
          {
            key: "stock",
            header: "In stock",
            align: "right",
            value: (r) => Number(r.stock ?? 0),
            render: (r) => <span className="num">{num(Number(r.stock ?? 0), 1)}</span>,
          },
          {
            key: "value",
            header: "Value",
            align: "right",
            value: (r) => Number(r.stock ?? 0) * Number(r.sellingRate ?? 0),
            render: (r) => <span className="num">{inr(Number(r.stock ?? 0) * Number(r.sellingRate ?? 0))}</span>,
          },
        ]}
      />
    </AppShell>
  ),
});
