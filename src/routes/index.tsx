/* eslint-disable prettier/prettier */
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  Boxes,
  Factory,
  IndianRupee,
  Package,
  Recycle,
  TrendingUp,
  Wallet,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useEffect, useState } from "react";


import {
  getDashboard,
  getSettings,
  type DashboardData,
  type SettingsData,
} from "@/lib/api";


import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { docStats } from "@/lib/erp/docs";
import { inventoryValue, lowStockItems, scrapStats, seriesLastDays, today, useErp } from "@/lib/erp/store";
import { dmy, inr, num } from "@/lib/erp/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Dashboard — MiniTally ERP" },
      {
        name: "description",
        content: "Live production, scrap, stock valuation and low-stock alerts for your manufacturing unit.",
      },
      { property: "og:title", content: "Dashboard — MiniTally ERP" },
      {
        property: "og:description",
        content: "Live production, scrap, stock valuation and low-stock alerts for your manufacturing unit.",
      },
    ],
  }),
  component: DashboardPage,
});

function DashboardPage() {
  return (
    <AppShell>
      <Dashboard />
    </AppShell>
  );
}

function Dashboard() {
  const state = useErp((s) => s);


  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);

  const series = dashboard?.production_series ?? [];
  const low = dashboard?.low_stock_items ?? [];
  const day = today();
  const topScrapReasons = dashboard?.top_scrap_reasons ?? [];
  const recentBatches = dashboard?.recent_production ?? [];
  const docs = docStats(state);

  useEffect(() => {
    Promise.all([getDashboard(), getSettings()])
      .then(([dashboardData, settingsData]) => {
        setDashboard(dashboardData);
        setSettings(settingsData);
      })
      .catch((error) => {
        setDashboardError(
          error instanceof Error ? error.message : "Failed to load dashboard",
        );
      });
  }, []);


  return (
    <>

    {dashboardError && (
    <div className="rounded-md border border-destructive p-3 text-sm text-destructive">
      {dashboardError}
    </div>
  )}
      <PageHeader
        title="Dashboard"
        subtitle={
            settings
              ? `${settings.name} · FY ${settings.financial_year}`
              : "MiniTally ERP"
          }
        actions={
          <Button asChild>
            <Link to="/production">New production entry</Link>
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
  <StatCard
    label="Today's production"
    value={dashboard?.produced_today ?? 0}
    hint="Production recorded today"
    icon={<Factory className="h-4 w-4" />}
    tone="primary"
  />

  <StatCard
    label="Finished goods"
    value={`${num(dashboard?.finished_goods_quantity ?? 0)} pcs`}
    hint={`${dashboard?.finished_goods_sku_count ?? 0} SKUs · ${inr(dashboard?.finished_goods_value ?? 0)} at cost`}
    icon={<Package className="h-4 w-4" />}
  />

  <StatCard
    label="Scrap in stock"
    value={`${num(dashboard?.scrap_stock_quantity ?? 0, 1)} units`}
    hint={`${inr(dashboard?.scrap_stock_value ?? 0)} realisable`}
    icon={<Recycle className="h-4 w-4" />}
    tone="warning"
  />

  <StatCard
    label="Raw material value"
    value={inr(dashboard?.raw_material_value ?? 0)}
    hint={`${dashboard?.raw_material_count ?? 0} materials tracked`}
    icon={<Boxes className="h-4 w-4" />}
  />

  <StatCard
    label="Scrap percentage (MTD)"
    value={`${(dashboard?.scrap_rate ?? 0).toFixed(2)}%`}
    hint={`${num(dashboard?.scrap_month ?? 0, 1)} units scrapped this month`}
    icon={<TrendingUp className="h-4 w-4" />}
    tone={(dashboard?.scrap_rate ?? 0) > 4 ? "destructive" : "success"}
  />

  <StatCard
    label="Total inventory value"
    value={inr(dashboard?.inventory_value ?? 0)}
    hint="Finished goods + raw material + scrap"
    icon={<IndianRupee className="h-4 w-4" />}
    tone="primary"
  />
</div>

      <div className="mt-3 grid gap-3 grid-cols-2 lg:grid-cols-6">
        {[
          { label: "Open PRs", value: num(docs.openPrs), to: "/procurement/requisitions" },
          { label: "Open POs", value: num(docs.openPos), to: "/procurement/orders" },
          { label: "Live quotes", value: num(docs.liveQuotes), to: "/sales/quotations" },
          { label: "Open sales orders", value: num(docs.openSos), to: "/sales/orders" },
          { label: "At vendor (job work)", value: num(docs.atVendor), to: "/jobwork" },
          { label: "FOC issues", value: num(docs.focIssues), to: "/foc" },
        ].map((k) => (
          <Link key={k.label} to={k.to} className="panel hover:border-primary/50 p-3 transition-colors">
            <p className="text-muted-foreground text-xs">{k.label}</p>
            <p className="num mt-1 text-xl font-semibold">{k.value}</p>
          </Link>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="panel p-4 lg:col-span-2">
          <h2 className="mb-4 text-sm font-semibold">Production — last 14 days</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="prodFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-chart-1)" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="var(--color-chart-1)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" width={40} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "var(--color-popover-foreground)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="produced"
                  name="Produced"
                  stroke="var(--color-chart-1)"
                  fill="url(#prodFill)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel p-4">
          <h2 className="mb-4 text-sm font-semibold">Scrap by day</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" />
                <YAxis tick={{ fontSize: 11 }} stroke="var(--color-muted-foreground)" width={34} />
                <Tooltip
                  contentStyle={{
                    background: "var(--color-popover)",
                    border: "1px solid var(--color-border)",
                    borderRadius: 8,
                    fontSize: 12,
                    color: "var(--color-popover-foreground)",
                  }}
                />
                <Bar dataKey="scrap" name="Scrap" fill="var(--color-chart-4)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <div className="panel lg:col-span-2">
          <div className="flex items-center justify-between border-b p-4">
            <h2 className="text-sm font-semibold">Recent production batches</h2>
            <Link to="/production" className="text-primary text-xs hover:underline">
              View all
            </Link>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-muted-foreground border-b text-left text-[11px] tracking-wider uppercase">
                <th className="px-4 py-2">Batch</th>
                <th className="px-4 py-2">Date</th>
                <th className="px-4 py-2">Product</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2">Shift</th>
              </tr>
            </thead>
            <tbody>
              {recentBatches.map((b) => (
                <tr key={b.id} className="border-b last:border-0">
                  <td className="num px-4 py-2">{b.batch_no}</td>
                  <td className="px-4 py-2">{dmy(b.entry_date)}</td>
                  <td className="px-4 py-2">{b.product_name}</td>
                  <td className="num px-4 py-2 text-right">{num(b.quantity)}</td>
                  <td className="px-4 py-2">
                    <Badge variant="secondary">{b.shift}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="space-y-4">
          <div className="panel p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <AlertTriangle className="text-warning h-4 w-4" /> Low stock alerts
            </h2>
            {low.length === 0 && <p className="text-muted-foreground text-sm">All items above minimum level.</p>}
            <div className="space-y-2">
              {low.map((item) => (
                <div key={item.id}>
                  <span>{item.name}</span>
                  <span>{item.stock}</span>
                  <span>{item.min_stock}</span>
                  <span>{item.unit}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="panel p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Wallet className="h-4 w-4" /> Top scrap reasons
            </h2>
            <div className="space-y-2">
              {topScrapReasons.length === 0 ? (
                  <p className="text-muted-foreground text-sm">
                    No scrap recorded yet.
                  </p>
                ) : (
                  topScrapReasons.map((item) => (
                    <div
                      key={item.reason}
                      className="flex items-center justify-between"
                    >
                      <span>{item.reason}</span>
                      <span>{num(item.quantity, 1)}</span>
                    </div>
                  ))
                )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
