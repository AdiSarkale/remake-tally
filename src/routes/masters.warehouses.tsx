import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/erp/AppShell";
import { MasterPage } from "@/components/erp/MasterPage";
import { useErp } from "@/lib/erp/store";
import { num } from "@/lib/erp/format";

export const Route = createFileRoute("/masters/warehouses")({
  head: () => ({
    meta: [
      { title: "Plants & Warehouses — MiniTally ERP" },
      { name: "description", content: "Maintain plants and warehouses used for interplant material transfers." },
      { property: "og:title", content: "Plants & Warehouses — MiniTally ERP" },
      { property: "og:description", content: "Multi-plant stock locations for MiniTally ERP." },
    ],
  }),
  component: () => (
    <AppShell>
      <WarehousesPage />
    </AppShell>
  ),
});

function WarehousesPage() {
  const stock = useErp((s) => s.warehouseStock);

  return (
    <MasterPage
      title="Plants & Warehouses"
      subtitle="Stock locations used by transfers, receipts and dispatches."
      entity="warehouses"
      fields={[
        { name: "code", label: "Code", required: true, placeholder: "PLT-3" },
        { name: "name", label: "Name", required: true },
        { name: "location", label: "Location", full: true },
      ]}
      searchable={(r) => `${r['code']} ${r.name} ${r['location']}`}
      columns={[
        { key: "code", header: "Code", value: (r) => String(r['code'] ?? "") },
        { key: "name", header: "Name", value: (r) => String(r.name ?? "") },
        { key: "location", header: "Location", value: (r) => String(r['location'] ?? "") },
        {
          key: "items",
          header: "Item lines",
          align: "right",
          value: (r) => Object.values(stock).filter((m) => (m[r.id] ?? 0) > 0).length,
          render: (r) => (
            <span className="num">{num(Object.values(stock).filter((m) => (m[r.id] ?? 0) > 0).length)}</span>
          ),
        },
      ]}
    />
  );
}
