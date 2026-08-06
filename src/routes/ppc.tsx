import { createFileRoute } from "@tanstack/react-router";
import { CalendarClock, Factory, Gauge, TriangleAlert } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { DataTable } from "@/components/erp/DataTable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { useErp } from "@/lib/erp/store";
import { daysUntil, machineUtilisation, ppcStats } from "@/lib/erp/ops";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/ppc")({
  head: () => ({
    meta: [
      { title: "Production Planning & Control — NKCC ERP" },
      { name: "description", content: "Schedule production against sales orders, allocate machines, and track delays, capacity and OEE." },
      { property: "og:title", content: "Production Planning & Control — NKCC ERP" },
      { property: "og:description", content: "Machine allocation, daily schedules and delay alerts for the plant." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <PpcPage />
    </AppShell>
  ),
});

function PpcPage() {
  const state = useErp((s) => s);
  const stats = ppcStats(state);
  const util = machineUtilisation(state);
  const machineNames = state.machines.map((m) => m.name);
  const soNos = state.salesOrders.map((o) => o.soNo);
  const productNames = state.products.map((p) => p.name);
  const avgOee = util.length ? Math.round(util.reduce((t, m) => t + m.oee, 0) / util.length) : 0;

  return (
    <>
      <PageHeader
        title="Production Planning & Control"
        subtitle="Sales order → plan → machine allocation → daily schedule → dispatch readiness."
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open plans" value={num(stats.open)} hint="Not yet completed" icon={<CalendarClock className="h-4 w-4" />} />
        <StatCard label="Delayed" value={num(stats.delayed)} tone={stats.delayed ? "destructive" : "success"} hint="Past due date" icon={<TriangleAlert className="h-4 w-4" />} />
        <StatCard label="Order completion" value={`${stats.completion}%`} tone="primary" hint={`${num(stats.produced)} of ${num(stats.planned)} pcs`} icon={<Factory className="h-4 w-4" />} />
        <StatCard label="Average OEE" value={`${avgOee}%`} tone={avgOee >= 70 ? "success" : "warning"} hint="Availability × performance × quality" icon={<Gauge className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="plans">
        <TabsList className="mb-4">
          <TabsTrigger value="plans">Production schedule</TabsTrigger>
          <TabsTrigger value="capacity">Machine capacity & OEE</TabsTrigger>
          <TabsTrigger value="machines">Machine master</TabsTrigger>
        </TabsList>

        <TabsContent value="plans">
          <RecordPage
            entity="productionPlans"
            singular="Plan"
            autoNumber={{ field: "planNo", prefix: "PLN" }}
            defaults={{ producedQty: 0 }}
            fields={[
              { name: "date", label: "Plan date", type: "date", required: true },
              { name: "soNo", label: "Sales order", type: "select", options: soNos.length ? soNos : ["—"] },
              { name: "productName", label: "Product", type: "select", options: productNames, required: true },
              { name: "plannedQty", label: "Planned qty", type: "number", required: true },
              { name: "producedQty", label: "Produced qty", type: "number" },
              { name: "machineName", label: "Machine", type: "select", options: machineNames, required: true },
              { name: "shift", label: "Shift", type: "select", options: ["A", "B", "C"] },
              { name: "startDate", label: "Start date", type: "date" },
              { name: "dueDate", label: "Due date", type: "date", required: true },
              { name: "priority", label: "Priority", type: "select", options: ["Low", "Normal", "High", "Urgent"] },
              { name: "status", label: "Status", type: "select", options: ["Planned", "In Progress", "Completed", "Delayed", "On Hold"] },
            ]}
            searchable={(r) => `${r['planNo']} ${r['productName']} ${r['machineName']} ${r['soNo']}`}
            columns={[
              { key: "planNo", header: "Plan No", value: (r) => String(r['planNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "productName", header: "Product", value: (r) => String(r['productName'] ?? "") },
              { key: "machineName", header: "Machine", value: (r) => String(r['machineName'] ?? "") },
              { key: "shift", header: "Shift", value: (r) => String(r['shift'] ?? "") },
              {
                key: "progress",
                header: "Progress",
                value: (r) => Number(r['producedQty'] ?? 0) / Math.max(1, Number(r['plannedQty'] ?? 1)),
                render: (r) => {
                  const pct = Math.min(100, Math.round((Number(r['producedQty'] ?? 0) / Math.max(1, Number(r['plannedQty'] ?? 1))) * 100));
                  return (
                    <div className="min-w-28">
                      <Progress value={pct} className="h-1.5" />
                      <span className="num text-muted-foreground text-xs">
                        {num(Number(r['producedQty'] ?? 0))} / {num(Number(r['plannedQty'] ?? 0))}
                      </span>
                    </div>
                  );
                },
              },
              {
                key: "dueDate",
                header: "Due",
                value: (r) => String(r['dueDate'] ?? ""),
                render: (r) => {
                  const d = daysUntil(String(r['dueDate'] ?? ""));
                  const late = d < 0 && r['status'] !== "Completed";
                  return (
                    <span className={late ? "text-destructive num" : "num"}>
                      {dmy(String(r['dueDate'] ?? ""))}
                      {late && <span className="ml-1 text-xs">({Math.abs(d)}d late)</span>}
                    </span>
                  );
                },
              },
              { key: "priority", header: "Priority", value: (r) => String(r['priority'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="capacity">
          <DataTable
            rows={util}
            rowKey={(m) => m.id}
            searchable={(m) => `${m.name} ${m.department}`}
            columns={[
              { key: "name", header: "Machine", value: (m) => m.name },
              { key: "department", header: "Department", value: (m) => m.department },
              { key: "capacity", header: "Cap./hr", align: "right", value: (m) => m.capacityPerHour, render: (m) => <span className="num">{num(m.capacityPerHour)}</span> },
              { key: "planned", header: "Planned", align: "right", value: (m) => m.planned, render: (m) => <span className="num">{num(m.planned)}</span> },
              { key: "produced", header: "Produced", align: "right", value: (m) => m.produced, render: (m) => <span className="num">{num(m.produced)}</span> },
              { key: "downtime", header: "Downtime (min)", align: "right", value: (m) => m.downtime, render: (m) => <span className="num">{num(m.downtime)}</span> },
              { key: "availability", header: "Avail.", align: "right", value: (m) => m.availability, render: (m) => <span className="num">{m.availability}%</span> },
              { key: "performance", header: "Perf.", align: "right", value: (m) => m.performance, render: (m) => <span className="num">{m.performance}%</span> },
              {
                key: "oee",
                header: "OEE",
                align: "right",
                value: (m) => m.oee,
                render: (m) => <span className={m.oee >= 70 ? "num text-success" : m.oee >= 50 ? "num text-warning" : "num text-destructive"}>{m.oee}%</span>,
              },
              { key: "status", header: "Status", value: (m) => m.status, render: (m) => <StatusBadge status={m.status} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="machines">
          <RecordPage
            entity="machines"
            singular="Machine"
            fields={[
              { name: "code", label: "Machine code", required: true, placeholder: "PRS-03" },
              { name: "name", label: "Machine name", required: true },
              { name: "department", label: "Department", required: true },
              { name: "capacityPerHour", label: "Capacity / hour", type: "number", required: true },
              { name: "installedOn", label: "Installed on", type: "date" },
              { name: "status", label: "Status", type: "select", options: ["Running", "Idle", "Under Maintenance", "Breakdown"] },
            ]}
            searchable={(r) => `${r['code']} ${r['name']} ${r['department']}`}
            columns={[
              { key: "code", header: "Code", value: (r) => String(r['code'] ?? "") },
              { key: "name", header: "Machine", value: (r) => String(r['name'] ?? "") },
              { key: "department", header: "Department", value: (r) => String(r['department'] ?? "") },
              { key: "capacityPerHour", header: "Cap./hr", align: "right", value: (r) => Number(r['capacityPerHour'] ?? 0), render: (r) => <span className="num">{num(Number(r['capacityPerHour'] ?? 0))}</span> },
              { key: "installedOn", header: "Installed", value: (r) => String(r['installedOn'] ?? ""), render: (r) => dmy(String(r['installedOn'] ?? "")) },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
