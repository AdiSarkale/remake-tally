import { createFileRoute } from "@tanstack/react-router";
import { PencilRuler, CheckCircle2, Clock, Layers } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { useErp } from "@/lib/erp/store";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/design")({
  head: () => ({
    meta: [
      { title: "Design & Development — NKCC ERP" },
      { name: "description", content: "Artwork design requests, version control, customer approval records, die and printing layout management." },
      { property: "og:title", content: "Design & Development — NKCC ERP" },
      { property: "og:description", content: "From customer requirement to approved artwork released to production." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <DesignPage />
    </AppShell>
  ),
});

const STAGES = ["Drafting", "Internal Review", "Sent to Customer", "Revision", "Approved", "Released"];

function DesignPage() {
  const requests = useErp((s) => s.designRequests);
  const customers = useErp((s) => s.customers.map((c) => c.name));
  const awaiting = requests.filter((r) => r.status === "Sent to Customer" || r.status === "Revision").length;
  const released = requests.filter((r) => r.status === "Released").length;
  const dies = new Set(requests.map((r) => r.dieNo).filter(Boolean)).size;

  return (
    <>
      <PageHeader
        title="Design & Development"
        subtitle="Requirement → artwork → internal review → customer approval → revision → release to production."
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Active requests" value={num(requests.length)} icon={<PencilRuler className="h-4 w-4" />} />
        <StatCard label="Awaiting customer" value={num(awaiting)} tone="warning" hint="Approval or revision pending" icon={<Clock className="h-4 w-4" />} />
        <StatCard label="Released to production" value={num(released)} tone="success" icon={<CheckCircle2 className="h-4 w-4" />} />
        <StatCard label="Dies under control" value={num(dies)} hint="Unique die numbers" icon={<Layers className="h-4 w-4" />} />
      </div>

      <RecordPage
        entity="designRequests"
        singular="Design request"
        autoNumber={{ field: "drNo", prefix: "DR" }}
        fields={[
          { name: "date", label: "Request date", type: "date", required: true },
          { name: "customerName", label: "Customer", type: "select", options: customers, required: true },
          { name: "productName", label: "Product / artwork", required: true, full: true },
          { name: "dieNo", label: "Die number", placeholder: "DIE-131" },
          { name: "version", label: "Version", placeholder: "v1" },
          { name: "designer", label: "Designer", required: true },
          { name: "status", label: "Stage", type: "select", options: STAGES },
          { name: "approvedBy", label: "Approved by" },
          { name: "approvedOn", label: "Approved on", type: "date" },
          { name: "requirement", label: "Customer requirement", type: "textarea" },
        ]}
        searchable={(r) => `${r['drNo']} ${r['customerName']} ${r['productName']} ${r['dieNo']} ${r['designer']}`}
        columns={[
          { key: "drNo", header: "DR No", value: (r) => String(r['drNo'] ?? "") },
          { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
          { key: "customerName", header: "Customer", value: (r) => String(r['customerName'] ?? "") },
          { key: "productName", header: "Artwork", value: (r) => String(r['productName'] ?? "") },
          { key: "dieNo", header: "Die", value: (r) => String(r['dieNo'] ?? "") },
          { key: "version", header: "Ver.", value: (r) => String(r['version'] ?? "") },
          { key: "designer", header: "Designer", value: (r) => String(r['designer'] ?? "") },
          { key: "status", header: "Stage", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
          {
            key: "approvedBy",
            header: "Customer approval",
            value: (r) => String(r['approvedBy'] ?? ""),
            render: (r) =>
              r['approvedBy'] ? (
                <span className="text-xs">
                  {String(r['approvedBy'])} · {dmy(String(r['approvedOn'] ?? ""))}
                </span>
              ) : (
                <span className="text-muted-foreground text-xs">Pending</span>
              ),
          },
        ]}
      />
    </>
  );
}
