import { createFileRoute } from "@tanstack/react-router";
import { ShieldAlert, DoorOpen, UserCheck, PackageOpen } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useErp } from "@/lib/erp/store";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/security")({
  head: () => ({
    meta: [
      { title: "Security & Gate — NKCC ERP" },
      { name: "description", content: "Inward and outward gate passes, returnable material tracking, vehicle entries and the visitor register." },
      { property: "og:title", content: "Security & Gate — NKCC ERP" },
      { property: "og:description", content: "Control every movement through the factory gate." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <SecurityPage />
    </AppShell>
  ),
});

function SecurityPage() {
  const gatePasses = useErp((s) => s.gatePasses);
  const visitors = useErp((s) => s.visitors);
  const today = new Date().toISOString().slice(0, 10);
  const openReturnable = gatePasses.filter((g) => g.type === "Returnable" && g.status === "Open").length;
  const inwardToday = gatePasses.filter((g) => g.date === today && g.direction === "Inward").length;
  const outwardToday = gatePasses.filter((g) => g.date === today && g.direction === "Outward").length;
  const insideNow = visitors.filter((v) => v.date === today && !v.outTime).length;

  return (
    <>
      <PageHeader title="Security & Gate" subtitle="Gate passes, returnable material control, vehicle movement and visitor register." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open returnable" value={num(openReturnable)} tone={openReturnable ? "warning" : "success"} hint="Material still outside" icon={<PackageOpen className="h-4 w-4" />} />
        <StatCard label="Inward today" value={num(inwardToday)} icon={<DoorOpen className="h-4 w-4" />} />
        <StatCard label="Outward today" value={num(outwardToday)} icon={<ShieldAlert className="h-4 w-4" />} />
        <StatCard label="Visitors inside" value={num(insideNow)} tone="primary" hint="Not yet signed out" icon={<UserCheck className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="gatepass">
        <TabsList className="mb-4">
          <TabsTrigger value="gatepass">Gate passes</TabsTrigger>
          <TabsTrigger value="visitors">Visitor register</TabsTrigger>
        </TabsList>

        <TabsContent value="gatepass">
          <RecordPage
            entity="gatePasses"
            singular="Gate pass"
            autoNumber={{ field: "gpNo", prefix: "GP" }}
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "direction", label: "Direction", type: "select", options: ["Inward", "Outward"], required: true },
              { name: "type", label: "Type", type: "select", options: ["Returnable", "Non-Returnable"], required: true },
              { name: "party", label: "Party", required: true },
              { name: "itemDescription", label: "Item description", required: true, full: true },
              { name: "quantity", label: "Quantity", type: "number", required: true },
              { name: "vehicleNo", label: "Vehicle no." },
              { name: "issuedBy", label: "Issued by", required: true },
              { name: "status", label: "Status", type: "select", options: ["Open", "Returned", "Closed"] },
            ]}
            searchable={(r) => `${r['gpNo']} ${r['party']} ${r['itemDescription']} ${r['vehicleNo']}`}
            columns={[
              { key: "gpNo", header: "GP No", value: (r) => String(r['gpNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "direction", header: "Direction", value: (r) => String(r['direction'] ?? ""), render: (r) => <StatusBadge status={String(r['direction'] ?? "")} /> },
              { key: "type", header: "Type", value: (r) => String(r['type'] ?? "") },
              { key: "party", header: "Party", value: (r) => String(r['party'] ?? "") },
              { key: "itemDescription", header: "Item", value: (r) => String(r['itemDescription'] ?? ""), render: (r) => <span className="block max-w-64 truncate">{String(r['itemDescription'] ?? "")}</span> },
              { key: "quantity", header: "Qty", align: "right", value: (r) => Number(r['quantity'] ?? 0), render: (r) => <span className="num">{num(Number(r['quantity'] ?? 0))}</span> },
              { key: "vehicleNo", header: "Vehicle", value: (r) => String(r['vehicleNo'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="visitors">
          <RecordPage
            entity="visitors"
            singular="Visitor"
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "name", label: "Visitor name", required: true },
              { name: "company", label: "Company" },
              { name: "whomToMeet", label: "Whom to meet", required: true },
              { name: "purpose", label: "Purpose", full: true },
              { name: "inTime", label: "In time", placeholder: "10:15" },
              { name: "outTime", label: "Out time", placeholder: "11:40" },
              { name: "badgeNo", label: "Badge no." },
              { name: "vehicleNo", label: "Vehicle no." },
            ]}
            searchable={(r) => `${r['name']} ${r['company']} ${r['whomToMeet']} ${r['badgeNo']}`}
            columns={[
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "name", header: "Visitor", value: (r) => String(r['name'] ?? "") },
              { key: "company", header: "Company", value: (r) => String(r['company'] ?? "") },
              { key: "whomToMeet", header: "Meeting", value: (r) => String(r['whomToMeet'] ?? "") },
              { key: "purpose", header: "Purpose", value: (r) => String(r['purpose'] ?? ""), render: (r) => <span className="block max-w-56 truncate">{String(r['purpose'] ?? "")}</span> },
              { key: "inTime", header: "In", value: (r) => String(r['inTime'] ?? "") },
              {
                key: "outTime",
                header: "Out",
                value: (r) => String(r['outTime'] ?? ""),
                render: (r) => (r['outTime'] ? String(r['outTime']) : <StatusBadge status="Inside" />),
              },
              { key: "badgeNo", header: "Badge", value: (r) => String(r['badgeNo'] ?? "") },
            ]}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
