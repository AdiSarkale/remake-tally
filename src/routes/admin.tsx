import { createFileRoute } from "@tanstack/react-router";
import { Building2, Utensils, Boxes, Wrench } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useErp } from "@/lib/erp/store";
import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Administration — NKCC ERP" },
      { name: "description", content: "Fixed asset register with custodians, plus housekeeping, canteen, uniform and utility service logs by department." },
      { property: "og:title", content: "Administration — NKCC ERP" },
      { property: "og:description", content: "Asset register and general administration services tracking." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <AdminPage />
    </AppShell>
  ),
});

function AdminPage() {
  const assets = useErp((s) => s.assets);
  const services = useErp((s) => s.adminServices);
  const assetValue = assets.reduce((t, a) => t + a.value, 0);
  const underRepair = assets.filter((a) => a.status === "Under Repair").length;
  const serviceCost = services.reduce((t, s) => t + s.cost, 0);

  return (
    <>
      <PageHeader title="Administration" subtitle="Fixed assets, custodianship, housekeeping, canteen and general services." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Assets" value={num(assets.length)} icon={<Boxes className="h-4 w-4" />} />
        <StatCard label="Asset value" value={inr(assetValue)} tone="primary" icon={<Building2 className="h-4 w-4" />} />
        <StatCard label="Under repair" value={num(underRepair)} tone={underRepair ? "warning" : "success"} icon={<Wrench className="h-4 w-4" />} />
        <StatCard label="Service spend" value={inr(serviceCost)} hint={`${num(services.length)} service entries`} icon={<Utensils className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="assets">
        <TabsList className="mb-4">
          <TabsTrigger value="assets">Asset register</TabsTrigger>
          <TabsTrigger value="services">General services</TabsTrigger>
        </TabsList>

        <TabsContent value="assets">
          <RecordPage
            entity="assets"
            singular="Asset"
            fields={[
              { name: "assetCode", label: "Asset code", required: true },
              { name: "name", label: "Asset name", required: true },
              { name: "category", label: "Category", type: "select", options: ["Plant & Machinery", "Furniture", "IT Equipment", "Vehicle", "Building", "Tools"] },
              { name: "location", label: "Location" },
              { name: "purchaseDate", label: "Purchase date", type: "date" },
              { name: "value", label: "Value", type: "number", required: true },
              { name: "custodian", label: "Custodian" },
              { name: "status", label: "Status", type: "select", options: ["In Use", "Idle", "Under Repair", "Scrapped"] },
            ]}
            searchable={(r) => `${r['assetCode']} ${r['name']} ${r['category']} ${r['custodian']}`}
            columns={[
              { key: "assetCode", header: "Code", value: (r) => String(r['assetCode'] ?? "") },
              { key: "name", header: "Asset", value: (r) => String(r['name'] ?? "") },
              { key: "category", header: "Category", value: (r) => String(r['category'] ?? "") },
              { key: "location", header: "Location", value: (r) => String(r['location'] ?? "") },
              { key: "purchaseDate", header: "Purchased", value: (r) => String(r['purchaseDate'] ?? ""), render: (r) => dmy(String(r['purchaseDate'] ?? "")) },
              { key: "value", header: "Value", align: "right", value: (r) => Number(r['value'] ?? 0), render: (r) => <span className="num">{inr(Number(r['value'] ?? 0))}</span> },
              { key: "custodian", header: "Custodian", value: (r) => String(r['custodian'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="services">
          <RecordPage
            entity="adminServices"
            singular="Service entry"
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "service", label: "Service", type: "select", options: ["Housekeeping", "Canteen", "Uniform", "Office Supplies", "Utility", "Vehicle"], required: true },
              { name: "department", label: "Department" },
              { name: "quantity", label: "Quantity", type: "number" },
              { name: "cost", label: "Cost", type: "number", required: true },
              { name: "handledBy", label: "Handled by" },
              { name: "status", label: "Status", type: "select", options: ["Requested", "In Progress", "Completed"] },
              { name: "description", label: "Description", type: "textarea", full: true },
            ]}
            searchable={(r) => `${r['service']} ${r['description']} ${r['department']} ${r['handledBy']}`}
            columns={[
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "service", header: "Service", value: (r) => String(r['service'] ?? "") },
              { key: "department", header: "Department", value: (r) => String(r['department'] ?? "") },
              { key: "description", header: "Description", value: (r) => String(r['description'] ?? ""), render: (r) => <span className="block max-w-64 truncate">{String(r['description'] ?? "")}</span> },
              { key: "quantity", header: "Qty", align: "right", value: (r) => Number(r['quantity'] ?? 0), render: (r) => <span className="num">{num(Number(r['quantity'] ?? 0))}</span> },
              { key: "cost", header: "Cost", align: "right", value: (r) => Number(r['cost'] ?? 0), render: (r) => <span className="num">{inr(Number(r['cost'] ?? 0))}</span> },
              { key: "handledBy", header: "Handled by", value: (r) => String(r['handledBy'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
