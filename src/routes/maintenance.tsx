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
            autoNumber={{ field: "pmNo", prefix: "PM" }}
            fields={[
              { name: "machineName", label: "Machine", type: "select", options: machineNames, required: true },
              { name: "task", label: "Maintenance task", required: true, full: true },
              { name: "frequency", label: "Frequency", type: "select", options: ["Daily", "Weekly", "Monthly", "Quarterly", "Half-yearly", "Yearly"] },
              { name: "lastDone", label: "Last done", type: "date" },
              { name: "nextDue", label: "Next due", type: "date", required: true },
              { name: "assignedTo", label: "Assigned to", required: true },
              { name: "status", label: "Status", type: "select", options: ["Scheduled", "In Progress", "Completed", "Overdue"] },
            ]}
            searchable={(r) => `${r['pmNo']} ${r['machineName']} ${r['task']} ${r['assignedTo']}`}
            columns={[
              { key: "pmNo", header: "PM No", value: (r) => String(r['pmNo'] ?? "") },
              { key: "machineName", header: "Machine", value: (r) => String(r['machineName'] ?? "") },
              { key: "task", header: "Task", value: (r) => String(r['task'] ?? "") },
              { key: "frequency", header: "Frequency", value: (r) => String(r['frequency'] ?? "") },
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
              { key: "assignedTo", header: "Owner", value: (r) => String(r['assignedTo'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="breakdowns">
          <RecordPage
            entity="breakdowns"
            singular="Breakdown"
            autoNumber={{ field: "bdNo", prefix: "BD" }}
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "machineName", label: "Machine", type: "select", options: machineNames, required: true },
              { name: "reportedBy", label: "Reported by", required: true },
              { name: "attendedBy", label: "Attended by" },
              { name: "downtimeMinutes", label: "Downtime (minutes)", type: "number", required: true },
              { name: "status", label: "Status", type: "select", options: ["Open", "Attending", "Resolved"] },
              { name: "problem", label: "Problem reported", type: "textarea", required: true },
              { name: "rootCause", label: "Root cause", type: "textarea" },
              { name: "action", label: "Action taken", type: "textarea" },
              { name: "sparesUsed", label: "Spares used", full: true },
            ]}
            searchable={(r) => `${r['bdNo']} ${r['machineName']} ${r['problem']} ${r['reportedBy']}`}
            columns={[
              { key: "bdNo", header: "BD No", value: (r) => String(r['bdNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "machineName", header: "Machine", value: (r) => String(r['machineName'] ?? "") },
              { key: "problem", header: "Problem", value: (r) => String(r['problem'] ?? ""), render: (r) => <span className="block max-w-64 truncate">{String(r['problem'] ?? "")}</span> },
              { key: "downtimeMinutes", header: "Downtime", align: "right", value: (r) => Number(r['downtimeMinutes'] ?? 0), render: (r) => <span className="num">{num(Number(r['downtimeMinutes'] ?? 0))} min</span> },
              { key: "attendedBy", header: "Attended by", value: (r) => String(r['attendedBy'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="spares">
          <RecordPage
            entity="spareParts"
            singular="Spare part"
            fields={[
              { name: "code", label: "Part code", required: true },
              { name: "name", label: "Part name", required: true },
              { name: "uom", label: "UOM", type: "select", options: ["Nos", "Set", "Mtr", "Ltr", "Kg"] },
              { name: "stock", label: "Stock", type: "number", required: true },
              { name: "reorderLevel", label: "Reorder level", type: "number", required: true },
              { name: "rate", label: "Rate", type: "number" },
              { name: "location", label: "Store location" },
            ]}
            searchable={(r) => `${r['code']} ${r['name']} ${r['location']}`}
            columns={[
              { key: "code", header: "Code", value: (r) => String(r['code'] ?? "") },
              { key: "name", header: "Part", value: (r) => String(r['name'] ?? "") },
              {
                key: "stock",
                header: "Stock",
                align: "right",
                value: (r) => Number(r['stock'] ?? 0),
                render: (r) => (
                  <span className={Number(r['stock'] ?? 0) <= Number(r['reorderLevel'] ?? 0) ? "num text-destructive" : "num"}>
                    {num(Number(r['stock'] ?? 0))} {String(r['uom'] ?? "")}
                  </span>
                ),
              },
              { key: "reorderLevel", header: "Reorder", align: "right", value: (r) => Number(r['reorderLevel'] ?? 0), render: (r) => <span className="num">{num(Number(r['reorderLevel'] ?? 0))}</span> },
              { key: "rate", header: "Rate", align: "right", value: (r) => Number(r['rate'] ?? 0), render: (r) => <span className="num">{inr(Number(r['rate'] ?? 0))}</span> },
              { key: "value", header: "Value", align: "right", value: (r) => Number(r['rate'] ?? 0) * Number(r['stock'] ?? 0), render: (r) => <span className="num">{inr(Number(r['rate'] ?? 0) * Number(r['stock'] ?? 0))}</span> },
              { key: "location", header: "Location", value: (r) => String(r['location'] ?? "") },
            ]}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
