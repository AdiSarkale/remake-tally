import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, ArrowRight, Boxes, Factory, Gauge, Package, Recycle, TrendingUp } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { ErrorState, TableSkeleton } from "@/components/query-state";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useDashboard } from "@/lib/api/hooks";
import { formatCurrency, formatDate, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/_app/")({
  head: () => ({
    meta: [
      { title: "Dashboard — Minitally ERP" },
      { name: "description", content: "Live overview of production, inventory, scrap and stock health." },
      { property: "og:title", content: "Dashboard — Minitally ERP" },
      { property: "og:description", content: "Live overview of production, inventory, scrap and stock health." },
    ],
  }),
  component: DashboardPage,
});

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

const tooltipStyle = {
  backgroundColor: "var(--popover)",
  border: "1px solid var(--border)",
  borderRadius: "var(--radius-md)",
  fontSize: 12,
  color: "var(--popover-foreground)",
};

function KpiCard({
  title,
  value,
  sub,
  icon: Icon,
  tone = "default",
}: {
  title: string;
  value: string;
  sub?: string;
  icon: typeof TrendingUp;
  tone?: "default" | "success" | "warning" | "critical";
}) {
  const toneClass = {
    default: "text-primary",
    success: "text-success",
    warning: "text-warning",
    critical: "text-destructive",
  }[tone];
  return (
    <Card className="gap-0 py-4">
      <CardContent className="flex items-start justify-between gap-2 px-4">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
          <p className="tabular mt-1.5 truncate text-2xl font-semibold">{value}</p>
          {sub ? <p className="mt-1 text-xs text-muted-foreground">{sub}</p> : null}
        </div>
        <div className={cn("flex size-9 shrink-0 items-center justify-center rounded-md border bg-muted/50", toneClass)}>
          <Icon className="size-4" />
        </div>
      </CardContent>
    </Card>
  );
}

function ChartCard({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={cn("gap-0 py-0", className)}>
      <CardHeader className="border-b px-4 py-3">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent className="h-64 px-2 py-3">{children}</CardContent>
    </Card>
  );
}

function DashboardPage() {
  const { data, isLoading, error, refetch } = useDashboard();

  if (isLoading) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dashboard" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="h-24 animate-pulse" />
          ))}
        </div>
        <TableSkeleton rows={8} cols={4} />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="space-y-4">
        <PageHeader title="Dashboard" />
        <Card>
          <ErrorState error={error} onRetry={() => refetch()} />
        </Card>
      </div>
    );
  }

  const inventorySplit = [
    { label: "Finished goods", value: data.finished_goods_value },
    { label: "Raw materials", value: data.raw_material_value },
    { label: "Scrap stock", value: data.scrap_stock_value },
  ].filter((s) => s.value > 0);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Operations Dashboard"
        description="Live view of production, inventory and scrap across the plant."
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Produced Today"
          value={formatNumber(data.produced_today, 2)}
          sub={`${formatNumber(data.produced_month, 2)} this month`}
          icon={Factory}
        />
        <KpiCard
          title="Scrap Rate"
          value={`${formatNumber(data.scrap_rate, 1)}%`}
          sub={`${formatNumber(data.scrap_month, 2)} scrapped this month`}
          icon={Recycle}
          tone={data.scrap_rate > 5 ? "critical" : data.scrap_rate > 2 ? "warning" : "success"}
        />
        <KpiCard
          title="Inventory Value"
          value={formatCurrency(data.inventory_value)}
          sub={`${formatNumber(data.low_stock_count)} items at or below minimum`}
          icon={Boxes}
          tone={data.low_stock_count > 0 ? "warning" : "success"}
        />
        <KpiCard
          title="Finished Goods"
          value={formatNumber(data.finished_goods_quantity, 0)}
          sub={`${formatNumber(data.finished_goods_sku_count)} SKUs · ${formatCurrency(data.finished_goods_value)}`}
          icon={Package}
        />
      </div>

      {data.low_stock_items.length > 0 ? (
        <Card className="gap-0 border-warning/40 py-0">
          <CardHeader className="flex flex-row items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-2">
              <AlertTriangle className="size-4 text-warning" />
              <CardTitle className="text-sm font-medium">Low stock — {data.low_stock_items.length} items need attention</CardTitle>
            </div>
            <Button variant="ghost" size="sm" className="h-7" asChild>
              <Link to="/inventory">
                Open inventory <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="px-0 py-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead className="text-right">Stock</TableHead>
                  <TableHead className="text-right">Minimum</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.low_stock_items.slice(0, 6).map((item) => (
                  <TableRow key={`${item.kind}-${item.id}`}>
                    <TableCell className="py-2 text-sm font-medium">{item.name}</TableCell>
                    <TableCell className="py-2 text-sm text-muted-foreground">{item.kind}</TableCell>
                    <TableCell className="tabular py-2 text-right text-sm">
                      {formatNumber(item.stock, 2)} {item.unit}
                    </TableCell>
                    <TableCell className="tabular py-2 text-right text-sm text-muted-foreground">
                      {formatNumber(item.min_stock, 2)} {item.unit}
                    </TableCell>
                    <TableCell className="py-2">
                      <StatusBadge status={item.stock <= 0 ? "Critical" : "Low"} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="Production vs scrap — last 14 days">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.production_series} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="produced" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--chart-2)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--chart-2)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} width={50} />
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area type="monotone" dataKey="produced" name="Produced" stroke="var(--chart-2)" fill="url(#produced)" strokeWidth={2} />
              <Area type="monotone" dataKey="scrap" name="Scrap" stroke="var(--destructive)" fill="transparent" strokeWidth={1.5} strokeDasharray="4 3" />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Inventory value split">
          {inventorySplit.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={inventorySplit} dataKey="value" nameKey="label" innerRadius="55%" outerRadius="80%" paddingAngle={2}>
                  {inventorySplit.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} formatter={(v) => formatCurrency(Number(v))} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No inventory value recorded yet.
            </div>
          )}
        </ChartCard>

        <ChartCard title="Top scrap reasons">
          {data.top_scrap_reasons.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.top_scrap_reasons} layout="vertical" margin={{ top: 0, right: 12, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="reason" width={130} tick={{ fontSize: 11, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="quantity" name="Qty scrapped" fill="var(--destructive)" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No scrap recorded yet.
            </div>
          )}
        </ChartCard>

        <Card className="gap-0 py-0">
          <CardHeader className="flex flex-row items-center justify-between border-b px-4 py-3">
            <CardTitle className="text-sm font-medium">Recent production</CardTitle>
            <Button variant="ghost" size="sm" className="h-7" asChild>
              <Link to="/production">
                View all <ArrowRight className="size-3.5" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent className="px-0 py-0">
            {data.recent_production.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Batch</TableHead>
                    <TableHead>Product</TableHead>
                    <TableHead className="text-right">Qty</TableHead>
                    <TableHead>Shift</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.recent_production.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="py-2 font-mono text-xs">{entry.batch_no}</TableCell>
                      <TableCell className="max-w-40 truncate py-2 text-sm">{entry.product_name}</TableCell>
                      <TableCell className="tabular py-2 text-right text-sm">{formatNumber(entry.quantity, 2)}</TableCell>
                      <TableCell className="py-2 text-sm text-muted-foreground">{entry.shift}</TableCell>
                      <TableCell className="py-2 text-sm text-muted-foreground">{formatDate(entry.entry_date)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
                No production entries yet.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          title="Raw Material Value"
          value={formatCurrency(data.raw_material_value)}
          sub={`${formatNumber(data.raw_material_count)} materials tracked`}
          icon={Gauge}
        />
        <KpiCard
          title="Scrap Stock"
          value={formatNumber(data.scrap_stock_quantity, 2)}
          sub={`Recoverable value ${formatCurrency(data.scrap_stock_value)}`}
          icon={Recycle}
        />
      </div>
    </div>
  );
}
