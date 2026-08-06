import { createFileRoute } from "@tanstack/react-router";
import { Wrench, AlertOctagon, CalendarCheck, PackageSearch } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useErp } from "@/lib/erp/store";
import { daysUntil, maintenanceStats } from "@/lib/erp/ops";
import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/maintenance")({
  head: () => ({
    meta: [
      { title: "Maintenance Management — NKCC ERP" },
      { name: "description", content: "Preventive maintenance schedules, breakdown logging with downtime analysis, and spare parts stock control." },
      { property: "og:title", content: "Maintenance Management — NKCC ERP" },
      { property: "og:description", content: "Keep machines running with PM schedules, breakdown history and spares." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <MaintenancePage />
    </AppShell>
  ),
});

function MaintenancePage() {
  const state = useErp((s) => s);
  const m = maintenanceStats(state);
  const machineNames = state.machines.map((x) => x.name);

  return (
    <>
      <PageHeader
        title="Maintenance Management"
        subtitle="Preventive schedules, breakdown response, downtime analysis and spare parts control."
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="PM due" value={num(m.pmDue)} tone={m.pmDue ? "warning" : "success"} hint="Due within 7 days" icon={<CalendarCheck className="h-4 w-4" />} />
        <StatCard label="Open breakdowns" value={num(m.openBreakdowns)} tone={m.openBreakdowns ? "destructive" : "success"} icon={<AlertOctagon className="h-4 w-4" />} />
        <StatCard label="Downtime (30d)" value={`${num(m.downtimeMinutes)} min`} hint="Total production loss" icon={<Wrench className="h-4 w-4" />} />
        <StatCard label="Spares below level" value={num(m.lowSpares)} tone={m.lowSpares ? "warning" : "success"} hint="Reorder required" icon={<PackageSearch className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="pm">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="pm">Preventive schedule</TabsTrigger>
          <TabsTrigger value="breakdowns">Breakdowns</TabsTrigger>
          <TabsTrigger value="spares">Spare parts</TabsTrigger>
        </TabsList>

        <TabsContent value="pm">
          <RecordPage
            entity="maintenancePlans"
            singular="PM schedule"
            fields={[
              { name: "machineName", label: "Machine", type: "select", options: machineNames, required: true },
              { name: "type", label: "Type", type: "select", options: ["Preventive", "Lubrication", "AMC", "Inspection"] },
              { name: "frequencyDays", label: "Frequency (days)", type: "number", required: true },
              { name: "lastDone", label: "Last done", type: "date" },
              { name: "nextDue", label: "Next due", type: "date", required: true },
              { name: "technician", label: "Technician", required: true },
              { name: "checklist", label: "Checklist", type: "textarea" },
            ]}
            searchable={(r) => `${r['machineName']} ${r['type']} ${r['technician']}`}
            columns={[
              { key: "machineName", header: "Machine", value: (r) => String(r['machineName'] ?? "") },
              { key: "type", header: "Type", value: (r) => String(r['type'] ?? "") },
              { key: "frequencyDays", header: "Every", align: "right", value: (r) => Number(r['frequencyDays'] ?? 0), render: (r) => <span className="num">{num(Number(r['frequencyDays'] ?? 0))} d</span> },
              { key: "lastDone", header: "Last done", value: (r) => String(r['lastDone'] ?? ""), render: (r) => dmy(String(r['lastDone'] ?? "")) },
              {
                key: "nextDue",
                header: "Next due",
                value: (r) => String(r['nextDue'] ?? ""),
                render: (r) => {
                  const d = daysUntil(String(r['nextDue'] ?? ""));
                  return <span className={d < 0 ? "num text-destructive" : d <= 7 ? "num text-warning" : "num"}>{dmy(String(r['nextDue'] ?? ""))}</span>;
                },
              },
              { key: "technician", header: "Technician", value: (r) => String(r['technician'] ?? "") },
              {
                key: "state",
                header: "Status",
                value: (r) => daysUntil(String(r['nextDue'] ?? "")),
                render: (r) => {
                  const d = daysUntil(String(r['nextDue'] ?? ""));
                  return <StatusBadge status={d < 0 ? "Overdue" : d <= 7 ? "Due Soon" : "Scheduled"} />;
                },
              },
            ]}
          />
        </TabsContent>

        <TabsContent value="breakdowns">
          <RecordPage
            entity="breakdowns"
            singular="Breakdown"
            autoNumber={{ field: "ticketNo", prefix: "BD" }}
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "machineName", label: "Machine", type: "select", options: machineNames, required: true },
              { name: "problem", label: "Problem reported", type: "textarea", required: true },
              { name: "downtimeMinutes", label: "Downtime (minutes)", type: "number", required: true },
              { name: "technician", label: "Technician", required: true },
              { name: "sparesUsed", label: "Spares used", full: true },
              { name: "cost", label: "Repair cost", type: "number" },
              { name: "status", label: "Status", type: "select", options: ["Open", "In Progress", "Resolved"] },
            ]}
            searchable={(r) => `${r['ticketNo']} ${r['machineName']} ${r['problem']} ${r['technician']}`}
            columns={[
              { key: "ticketNo", header: "Ticket", value: (r) => String(r['ticketNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "machineName", header: "Machine", value: (r) => String(r['machineName'] ?? "") },
              { key: "problem", header: "Problem", value: (r) => String(r['problem'] ?? ""), render: (r) => <span className="block max-w-64 truncate">{String(r['problem'] ?? "")}</span> },
              { key: "downtimeMinutes", header: "Downtime", align: "right", value: (r) => Number(r['downtimeMinutes'] ?? 0), render: (r) => <span className="num">{num(Number(r['downtimeMinutes'] ?? 0))} min</span> },
              { key: "cost", header: "Cost", align: "right", value: (r) => Number(r['cost'] ?? 0), render: (r) => <span className="num">{inr(Number(r['cost'] ?? 0))}</span> },
              { key: "technician", header: "Technician", value: (r) => String(r['technician'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="spares">
          <RecordPage
            entity="spares"
            singular="Spare part"
            fields={[
              { name: "code", label: "Part code", required: true },
              { name: "name", label: "Part name", required: true },
              { name: "machineName", label: "Machine", type: "select", options: machineNames },
              { name: "stock", label: "Stock", type: "number", required: true },
              { name: "minStock", label: "Minimum stock", type: "number", required: true },
              { name: "unitCost", label: "Unit cost", type: "number" },
              { name: "location", label: "Store location" },
            ]}
            searchable={(r) => `${r['code']} ${r['name']} ${r['machineName']} ${r['location']}`}
            columns={[
              { key: "code", header: "Code", value: (r) => String(r['code'] ?? "") },
              { key: "name", header: "Part", value: (r) => String(r['name'] ?? "") },
              { key: "machineName", header: "Machine", value: (r) => String(r['machineName'] ?? "") },
              {
                key: "stock",
                header: "Stock",
                align: "right",
                value: (r) => Number(r['stock'] ?? 0),
                render: (r) => (
                  <span className={Number(r['stock'] ?? 0) <= Number(r['minStock'] ?? 0) ? "num text-destructive" : "num"}>{num(Number(r['stock'] ?? 0))}</span>
                ),
              },
              { key: "minStock", header: "Min", align: "right", value: (r) => Number(r['minStock'] ?? 0), render: (r) => <span className="num">{num(Number(r['minStock'] ?? 0))}</span> },
              { key: "unitCost", header: "Rate", align: "right", value: (r) => Number(r['unitCost'] ?? 0), render: (r) => <span className="num">{inr(Number(r['unitCost'] ?? 0))}</span> },
              { key: "value", header: "Value", align: "right", value: (r) => Number(r['unitCost'] ?? 0) * Number(r['stock'] ?? 0), render: (r) => <span className="num">{inr(Number(r['unitCost'] ?? 0) * Number(r['stock'] ?? 0))}</span> },
              { key: "location", header: "Location", value: (r) => String(r['location'] ?? "") },
            ]}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}

