import { createFileRoute, Link } from "@tanstack/react-router";
import { BarChart3, Brain, PackageSearch, Gauge } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/DocBits";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { useErp } from "@/lib/erp/store";
import { accountStats, demandForecast, departmentKpis, machineUtilisation, smartInsights } from "@/lib/erp/ops";
import { inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/reports")({
  head: () => ({
    meta: [
      { title: "Reports & Analytics — NKCC ERP" },
      { name: "description", content: "Department scorecards, machine efficiency, demand forecasting and AI-style smart insights across the whole plant." },
      { property: "og:title", content: "Reports & Analytics — NKCC ERP" },
      { property: "og:description", content: "One hub for MIS: KPIs, efficiency, forecasts and recommended actions." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <ReportsPage />
    </AppShell>
  ),
});

function ReportsPage() {
  const state = useErp((s) => s);
  const kpis = departmentKpis(state);
  const util = machineUtilisation(state);
  const forecast = demandForecast(state);
  const insights = smartInsights(state);
  const acc = accountStats(state);

  return (
    <>
      <PageHeader title="Reports & Analytics" subtitle="Department scorecards, efficiency analysis, demand forecast and smart recommendations." />

      <Tabs defaultValue="scorecard">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="scorecard">Department scorecard</TabsTrigger>
          <TabsTrigger value="efficiency">Machine efficiency</TabsTrigger>
          <TabsTrigger value="forecast">Demand forecast</TabsTrigger>
          <TabsTrigger value="insights">Smart insights</TabsTrigger>
        </TabsList>

        <TabsContent value="scorecard">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {kpis.map((k) => (
              <div key={k.department} className="panel p-4">
                <div className="text-muted-foreground flex items-center justify-between text-xs">
                  <span>{k.department}</span>
                  <BarChart3 className="h-3.5 w-3.5" />
                </div>
                <div className="num mt-1 text-2xl font-semibold tracking-tight">{k.value}</div>
                <div className="text-muted-foreground mb-2 text-xs">{k.metric}</div>
                <Progress value={Math.max(0, Math.min(100, k.score))} className="h-1.5" />
              </div>
            ))}
          </div>

          <div className="panel mt-4 p-5">
            <h3 className="mb-3 text-sm font-semibold tracking-tight">Financial summary</h3>
            <div className="grid gap-4 text-sm sm:grid-cols-4">
              {[
                ["Revenue", inr(acc.revenue)],
                ["Gross profit", inr(acc.grossProfit)],
                ["Expenses", inr(acc.expenses)],
                ["Net profit", inr(acc.netProfit)],
              ].map(([label, value]) => (
                <div key={label}>
                  <div className="text-muted-foreground text-xs">{label}</div>
                  <div className="num text-lg font-semibold">{value}</div>
                </div>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="efficiency">
          <div className="panel mb-4 p-4">
            <div className="text-muted-foreground mb-3 flex items-center gap-2 text-xs">
              <Gauge className="h-3.5 w-3.5" /> OEE by machine
            </div>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={util.map((m) => ({ name: m.name, OEE: m.oee, Availability: m.availability }))}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit="%" />
                  <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="Availability" fill="var(--muted-foreground)" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="OEE" fill="var(--primary)" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <DataTable
            rows={util}
            rowKey={(m) => m.id}
            searchable={(m) => `${m.name} ${m.department}`}
            columns={[
              { key: "name", header: "Machine", value: (m) => m.name },
              { key: "department", header: "Department", value: (m) => m.department },
              { key: "planned", header: "Planned", align: "right", value: (m) => m.planned, render: (m) => <span className="num">{num(m.planned)}</span> },
              { key: "produced", header: "Produced", align: "right", value: (m) => m.produced, render: (m) => <span className="num">{num(m.produced)}</span> },
              { key: "downtime", header: "Downtime", align: "right", value: (m) => m.downtime, render: (m) => <span className="num">{num(m.downtime)} min</span> },
              { key: "oee", header: "OEE", align: "right", value: (m) => m.oee, render: (m) => <span className={m.oee >= 70 ? "num text-success" : "num text-warning"}>{m.oee}%</span> },
              { key: "status", header: "Status", value: (m) => m.status, render: (m) => <StatusBadge status={m.status} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="forecast">
          <div className="text-muted-foreground mb-3 flex items-center gap-2 text-xs">
            <PackageSearch className="h-3.5 w-3.5" /> Moving-average forecast from the last 30 days of invoiced demand
          </div>
          <DataTable
            rows={forecast}
            rowKey={(f) => f.id}
            searchable={(f) => f.name}
            columns={[
              { key: "name", header: "Product", value: (f) => f.name },
              { key: "stock", header: "Stock", align: "right", value: (f) => f.stock, render: (f) => <span className="num">{num(f.stock)} {f.unit}</span> },
              { key: "soldLast30", header: "Sold (30d)", align: "right", value: (f) => f.soldLast30, render: (f) => <span className="num">{num(f.soldLast30)}</span> },
              { key: "forecastNextMonth", header: "Forecast", align: "right", value: (f) => f.forecastNextMonth, render: (f) => <span className="num">{num(f.forecastNextMonth)}</span> },
              {
                key: "coverDays",
                header: "Cover",
                align: "right",
                value: (f) => f.coverDays,
                render: (f) => <span className={f.coverDays < 10 ? "num text-destructive" : f.coverDays < 30 ? "num text-warning" : "num"}>{f.coverDays > 365 ? "—" : `${f.coverDays} d`}</span>,
              },
              { key: "reorderQty", header: "Suggested make/buy", align: "right", value: (f) => f.reorderQty, render: (f) => <span className="num">{f.reorderQty ? num(f.reorderQty) : "—"}</span> },
            ]}
          />
        </TabsContent>

        <TabsContent value="insights">
          <div className="text-muted-foreground mb-3 flex items-center gap-2 text-xs">
            <Brain className="h-3.5 w-3.5" /> Recommendations generated from live operational data
          </div>
          {insights.length === 0 ? (
            <div className="panel text-muted-foreground p-8 text-center text-sm">No exceptions detected — every tracked metric is within range.</div>
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {insights.map((i, idx) => (
                <div key={`${i.title}-${idx}`} className="panel p-4">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-muted-foreground text-xs uppercase tracking-wide">{i.category}</span>
                    <StatusBadge status={i.severity} />
                  </div>
                  <h4 className="text-sm font-semibold tracking-tight">{i.title}</h4>
                  <p className="text-muted-foreground mt-1 text-sm">{i.detail}</p>
                  <p className="mt-2 text-sm">
                    <span className="text-primary font-medium">Recommended: </span>
                    {i.action}
                  </p>
                </div>
              ))}
            </div>
          )}
          <p className="text-muted-foreground mt-4 text-xs">
            Need the raw registers? Open <Link to="/inventory" className="text-primary underline-offset-2 hover:underline">Inventory</Link> or{" "}
            <Link to="/accounts" className="text-primary underline-offset-2 hover:underline">Accounts</Link>.
          </p>
        </TabsContent>
      </Tabs>
    </>
  );
}
