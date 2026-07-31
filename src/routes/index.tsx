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
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
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
  const value = inventoryValue(state);
  const low = lowStockItems(state);
  const scrap = scrapStats(state);
  const series = seriesLastDays(state, 14);
  const day = today();

  const todaysProduction = state.production.filter((p) => p.date === day).reduce((t, p) => t + p.quantity, 0);
  const totalFg = state.products.reduce((t, p) => t + p.stock, 0);
  const totalScrapStock = state.scrapTypes.reduce((t, s) => t + s.stock, 0);
  const scrapValue = state.scrapTypes.reduce((t, s) => t + s.stock * s.sellingRate, 0);
  const recentBatches = state.production.slice(0, 6);

  return (
    <>
      <PageHeader
        title="Dashboard"
        subtitle={`${state.settings.name} · FY ${state.settings.financialYear}`}
        actions={
          <Button asChild>
            <Link to="/production">New production entry</Link>
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          label="Today's production"
          value={`${num(todaysProduction)} pcs`}
          hint={`${state.production.filter((p) => p.date === day).length} batches today`}
          icon={<Factory className="h-4 w-4" />}
          tone="primary"
        />
        <StatCard
          label="Finished goods"
          value={`${num(totalFg)} pcs`}
          hint={`${state.products.length} SKUs · ${inr(value.fg)} at cost`}
          icon={<Package className="h-4 w-4" />}
        />
        <StatCard
          label="Scrap in stock"
          value={`${num(totalScrapStock, 1)} units`}
          hint={`${inr(scrapValue)} realisable`}
          icon={<Recycle className="h-4 w-4" />}
          tone="warning"
        />
        <StatCard
          label="Raw material value"
          value={inr(value.rm)}
          hint={`${state.materials.length} materials tracked`}
          icon={<Boxes className="h-4 w-4" />}
        />
        <StatCard
          label="Scrap percentage (MTD)"
          value={`${scrap.percent.toFixed(2)}%`}
          hint={`${num(scrap.monthly, 1)} units scrapped this month`}
          icon={<TrendingUp className="h-4 w-4" />}
          tone={scrap.percent > 4 ? "destructive" : "success"}
        />
        <StatCard
          label="Total inventory value"
          value={inr(value.total)}
          hint="Finished goods + raw material + scrap"
          icon={<IndianRupee className="h-4 w-4" />}
          tone="primary"
        />
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
                  <td className="num px-4 py-2">{b.batchNo}</td>
                  <td className="px-4 py-2">{dmy(b.date)}</td>
                  <td className="px-4 py-2">{b.productName}</td>
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
              {low.slice(0, 6).map((i) => (
                <div key={`${i.kind}-${i.id}`} className="flex items-center justify-between gap-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{i.name}</p>
                    <p className="text-muted-foreground text-xs">{i.kind}</p>
                  </div>
                  <span className="num text-destructive shrink-0 text-xs">
                    {num(i.stock, 1)} / {num(i.min)} {i.unit}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="panel p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Wallet className="h-4 w-4" /> Top scrap reasons
            </h2>
            <div className="space-y-2">
              {scrap.topReasons.map((r) => (
                <div key={r.reason} className="flex items-center justify-between text-sm">
                  <span className="truncate">{r.reason}</span>
                  <span className="num text-muted-foreground text-xs">{num(r.qty, 1)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
