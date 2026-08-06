import { createFileRoute, Link } from "@tanstack/react-router";
import { Bell } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusBadge } from "@/components/erp/DocBits";
import { useErp } from "@/lib/erp/store";
import { liveAlerts } from "@/lib/erp/ops";
import { num } from "@/lib/erp/format";

export const Route = createFileRoute("/notifications")({
  head: () => ({
    meta: [
      { title: "Notification Centre — NKCC ERP" },
      { name: "description", content: "Every operational alert in one place: approvals, delayed production, low stock, breakdowns, quality issues and overdue payments." },
      { property: "og:title", content: "Notification Centre — NKCC ERP" },
      { property: "og:description", content: "Live exception alerts across all departments." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <NotificationsPage />
    </AppShell>
  ),
});

function NotificationsPage() {
  const state = useErp((s) => s);
  const alerts = liveAlerts(state);
  const categories = ["All", ...Array.from(new Set(alerts.map((a) => a.category)))];
  const critical = alerts.filter((a) => a.severity === "Critical").length;
  const high = alerts.filter((a) => a.severity === "High").length;

  return (
    <>
      <PageHeader title="Notification Centre" subtitle="Live exception alerts generated from operational data across every module." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total alerts" value={num(alerts.length)} icon={<Bell className="h-4 w-4" />} />
        <StatCard label="Critical" value={num(critical)} tone={critical ? "destructive" : "success"} />
        <StatCard label="High" value={num(high)} tone={high ? "warning" : "success"} />
        <StatCard label="Categories" value={num(categories.length - 1)} hint="Departments reporting" />
      </div>

      <Tabs defaultValue="All">
        <TabsList className="mb-4 flex-wrap">
          {categories.map((c) => (
            <TabsTrigger key={c} value={c}>
              {c}
            </TabsTrigger>
          ))}
        </TabsList>

        {categories.map((c) => {
          const rows = c === "All" ? alerts : alerts.filter((a) => a.category === c);
          return (
            <TabsContent key={c} value={c}>
              {rows.length === 0 ? (
                <div className="panel text-muted-foreground p-8 text-center text-sm">Nothing needs attention here.</div>
              ) : (
                <ul className="panel divide-y divide-border">
                  {rows.map((a, i) => (
                    <li key={`${a.id}-${i}`} className="flex items-start gap-3 p-3">
                      <span
                        className={
                          "mt-1.5 h-2 w-2 shrink-0 rounded-full " +
                          (a.severity === "Critical"
                            ? "bg-destructive"
                            : a.severity === "High"
                              ? "bg-warning"
                              : a.severity === "Medium"
                                ? "bg-primary"
                                : "bg-muted-foreground")
                        }
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm">{a.message}</p>
                        <p className="text-muted-foreground text-xs">{a.category}</p>
                      </div>
                      <StatusBadge status={a.severity} />
                      <Link to={a.link} className="text-primary shrink-0 text-xs underline-offset-2 hover:underline">
                        Open
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </TabsContent>
          );
        })}
      </Tabs>
    </>
  );
}
