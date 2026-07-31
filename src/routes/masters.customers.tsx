import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/erp/AppShell";
import { MasterPage } from "@/components/erp/MasterPage";

export const Route = createFileRoute("/masters/customers")({
  head: () => ({
    meta: [
      { title: "Customers — MiniTally ERP" },
      { name: "description", content: "Maintain customer master records with GST, contact and billing address." },
      { property: "og:title", content: "Customers — MiniTally ERP" },
      { property: "og:description", content: "Maintain customer master records with GST and billing details." },
    ],
  }),
  component: () => (
    <AppShell>
      <MasterPage
        title="Customers"
        subtitle="Billing parties used on sales invoices."
        entity="customers"
        searchable={(r) => `${r.name} ${r.gstNumber} ${r.mobile} ${r.email}`}
        fields={[
          { name: "name", label: "Customer Name", required: true, full: true },
          { name: "gstNumber", label: "GST Number", placeholder: "27AABCD1234E1Z5" },
          { name: "mobile", label: "Mobile" },
          { name: "email", label: "Email" },
          { name: "address", label: "Address", type: "textarea" },
        ]}
        columns={[
          { key: "name", header: "Name", value: (r) => String(r.name) },
          { key: "gst", header: "GST", value: (r) => String(r.gstNumber), className: "num text-xs" },
          { key: "mobile", header: "Mobile", value: (r) => String(r.mobile) },
          { key: "email", header: "Email", value: (r) => String(r.email) },
        ]}
      />
    </AppShell>
  ),
});
