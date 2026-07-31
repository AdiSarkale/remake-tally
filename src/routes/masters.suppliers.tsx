import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/erp/AppShell";
import { MasterPage } from "@/components/erp/MasterPage";

export const Route = createFileRoute("/masters/suppliers")({
  head: () => ({
    meta: [
      { title: "Suppliers — MiniTally ERP" },
      { name: "description", content: "Maintain supplier master records with GST and contact details." },
      { property: "og:title", content: "Suppliers — MiniTally ERP" },
      { property: "og:description", content: "Maintain supplier master records with GST and contact details." },
    ],
  }),
  component: () => (
    <AppShell>
      <MasterPage
        title="Suppliers"
        subtitle="Vendors supplying raw materials and consumables."
        entity="suppliers"
        searchable={(r) => `${r.name} ${r.gstNumber} ${r.contact}`}
        fields={[
          { name: "name", label: "Supplier Name", required: true, full: true },
          { name: "gstNumber", label: "GST Number" },
          { name: "contact", label: "Contact" },
          { name: "address", label: "Address", type: "textarea" },
        ]}
        columns={[
          { key: "name", header: "Name", value: (r) => String(r.name) },
          { key: "gst", header: "GST", value: (r) => String(r.gstNumber), className: "num text-xs" },
          { key: "contact", header: "Contact", value: (r) => String(r.contact) },
          { key: "address", header: "Address", value: (r) => String(r.address), className: "max-w-xs truncate" },
        ]}
      />
    </AppShell>
  ),
});
