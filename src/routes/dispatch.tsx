import { createFileRoute } from "@tanstack/react-router";
import { Truck, MapPin, PackageCheck, Clock } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { useErp } from "@/lib/erp/store";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/dispatch")({
  head: () => ({
    meta: [
      { title: "Dispatch & Logistics — NKCC ERP" },
      { name: "description", content: "Vehicle planning, transporter and LR tracking, in-transit status and proof of delivery for every consignment." },
      { property: "og:title", content: "Dispatch & Logistics — NKCC ERP" },
      { property: "og:description", content: "Track consignments from loading bay to customer POD." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <DispatchPage />
    </AppShell>
  ),
});

function DispatchPage() {
  const dispatches = useErp((s) => s.dispatches);
  const customers = useErp((s) => s.customers.map((c) => c.name));
  const dnNos = useErp((s) => s.deliveryNotes.map((d) => d.dnNo));

  const inTransit = dispatches.filter((d) => d.status === "In Transit").length;
  const delivered = dispatches.filter((d) => d.status === "Delivered").length;
  const delayed = dispatches.filter((d) => d.status === "Delayed").length;
  const podPending = dispatches.filter((d) => d.status === "Delivered" && !d.podRef).length;

  return (
    <>
      <PageHeader
        title="Dispatch & Logistics"
        subtitle="Vehicle allocation, transporter and LR details, in-transit visibility and proof of delivery."
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="In transit" value={num(inTransit)} tone="primary" icon={<Truck className="h-4 w-4" />} />
        <StatCard label="Delivered" value={num(delivered)} tone="success" icon={<PackageCheck className="h-4 w-4" />} />
        <StatCard label="Delayed" value={num(delayed)} tone={delayed ? "destructive" : "success"} icon={<Clock className="h-4 w-4" />} />
        <StatCard label="POD pending" value={num(podPending)} tone={podPending ? "warning" : "success"} hint="Delivered without proof" icon={<MapPin className="h-4 w-4" />} />
      </div>

      <RecordPage
        entity="dispatches"
        singular="Dispatch"
        autoNumber={{ field: "dispatchNo", prefix: "DSP" }}
        fields={[
          { name: "date", label: "Dispatch date", type: "date", required: true },
          { name: "dnNo", label: "Delivery note", type: "select", options: dnNos.length ? dnNos : ["—"] },
          { name: "customerName", label: "Customer", type: "select", options: customers, required: true },
          { name: "transporter", label: "Transporter", required: true },
          { name: "vehicleNo", label: "Vehicle no.", required: true },
          { name: "driverName", label: "Driver name" },
          { name: "driverPhone", label: "Driver phone" },
          { name: "lrNumber", label: "LR / consignment no." },
          { name: "status", label: "Status", type: "select", options: ["Planned", "Loading", "In Transit", "Delivered", "Delayed"] },
          { name: "deliveredOn", label: "Delivered on", type: "date" },
          { name: "podRef", label: "POD reference", full: true },
        ]}
        searchable={(r) => `${r['dispatchNo']} ${r['customerName']} ${r['vehicleNo']} ${r['transporter']} ${r['lrNumber']}`}
        columns={[
          { key: "dispatchNo", header: "Dispatch", value: (r) => String(r['dispatchNo'] ?? "") },
          { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
          { key: "dnNo", header: "DN", value: (r) => String(r['dnNo'] ?? "") },
          { key: "customerName", header: "Customer", value: (r) => String(r['customerName'] ?? "") },
          {
            key: "vehicleNo",
            header: "Vehicle / driver",
            value: (r) => String(r['vehicleNo'] ?? ""),
            render: (r) => (
              <div className="leading-tight">
                <div className="num">{String(r['vehicleNo'] ?? "")}</div>
                <div className="text-muted-foreground text-xs">{String(r['driverName'] ?? "—")}</div>
              </div>
            ),
          },
          { key: "transporter", header: "Transporter", value: (r) => String(r['transporter'] ?? "") },
          { key: "lrNumber", header: "LR No", value: (r) => String(r['lrNumber'] ?? "") },
          {
            key: "podRef",
            header: "POD",
            value: (r) => String(r['podRef'] ?? ""),
            render: (r) => (r['podRef'] ? <span className="text-xs">{String(r['podRef'])}</span> : <span className="text-muted-foreground text-xs">—</span>),
          },
          { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
        ]}
      />
    </>
  );
}
