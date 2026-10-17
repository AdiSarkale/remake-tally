import { createFileRoute } from "@tanstack/react-router";
import { useManufacturingReport, useWorkcenters } from "@/lib/api/hooks";

export const Route = createFileRoute("/_app/reports")({
  head: () => ({
    meta: [
      { title: "Reports — Nexora ERP" },
      { name: "description", content: "Manufacturing production, scrap and material variance report." },
      { property: "og:title", content: "Reports — Nexora ERP" },
      { property: "og:description", content: "Manufacturing production, scrap and material variance report." },
    ],
  }),
  component: ReportsPage,
});

function number(value: unknown) {
  return typeof value === "number"
    ? new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 }).format(value)
    : String(value ?? "—");
}

function ReportsPage() {
  const report = useManufacturingReport();
  const workcenters = useWorkcenters();
  const data = report.data;

  const exportCsv = () => {
    if (!data) return;
    const rows: unknown[][] = [
      ["Manufacturing Report"],
      ["Produced quantity", data.production_qty],
      ["Scrap quantity", data.scrap_qty],
      ["Planned material quantity", data.planned_material_qty],
      ["Actual material quantity", data.actual_material_qty],
      ["Material variance", data.material_variance],
      [],
    ];
    const columns = [...new Set(data.by_workcenter.flatMap((row) => Object.keys(row)))];
    if (columns.length) {
      rows.push(columns);
      for (const row of data.by_workcenter) rows.push(columns.map((column) => row[column]));
    }
    const csv = rows.map((row) => row.map((cell) => {
      const value = String(cell ?? "");
      return `"${value.replace(/"/g, '""')}"`;
    }).join(",")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8;" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "manufacturing-report.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const metrics = data ? [
    { label: "Produced quantity", value: data.production_qty, note: "Recorded production entries" },
    { label: "Scrap quantity", value: data.scrap_qty, note: "Actual scrap recorded" },
    { label: "Planned material", value: data.planned_material_qty, note: "Expected consumption" },
    { label: "Actual material", value: data.actual_material_qty, note: "Posted consumption" },
    { label: "Material variance", value: data.material_variance, note: "Actual minus planned" },
  ] : [];

  return (
    <main className="space-y-6 p-4 md:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Analytics</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Reports</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Reports currently available from the backend. Manufacturing metrics are calculated from recorded production and material consumption.
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => void report.refetch()} disabled={report.isFetching}
            className="rounded-md border px-3 py-2 text-sm hover:bg-muted disabled:opacity-50">
            {report.isFetching ? "Refreshing…" : "Refresh"}
          </button>
          <button type="button" onClick={exportCsv} disabled={!data}
            className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground hover:opacity-90 disabled:opacity-50">
            Export CSV
          </button>
        </div>
      </div>

      {report.isLoading ? (
        <div className="rounded-lg border p-6 text-sm text-muted-foreground">Loading manufacturing report…</div>
      ) : report.isError ? (
        <div role="alert" className="rounded-lg border border-destructive/40 p-5">
          <h2 className="font-medium">Unable to load manufacturing report</h2>
          <p className="mt-1 text-sm text-muted-foreground">The report request failed. Check your access and backend availability, then retry.</p>
          <button type="button" onClick={() => void report.refetch()} className="mt-3 rounded-md border px-3 py-2 text-sm">Try again</button>
        </div>
      ) : data ? (
        <>
          <section aria-label="Manufacturing summary" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {metrics.map((metric) => (
              <article key={metric.label} className="rounded-lg border bg-card p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{metric.label}</p>
                <p className="mt-3 text-2xl font-semibold tabular-nums">{number(metric.value)}</p>
                <p className="mt-1 text-xs text-muted-foreground">{metric.note}</p>
              </article>
            ))}
          </section>

          <section className="overflow-hidden rounded-lg border">
            <div className="border-b p-4">
              <h2 className="font-semibold">Work-center breakdown</h2>
              <p className="mt-1 text-sm text-muted-foreground">Production and material metrics grouped by work center.</p>
            </div>
            {data.by_workcenter.length === 0 ? (
              <div className="p-8 text-center text-sm text-muted-foreground">No work-center report rows are available yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-left">
                    <tr>
                      {Object.keys(data.by_workcenter[0] ?? {}).map((key) => (
                        <th key={key} className={`whitespace-nowrap px-4 py-3 font-medium capitalize ${key === "workcenter_id" ? "" : "text-right"}`}>
                          {key === "workcenter_id" ? "Work center" : key.replace(/_/g, " ")}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.by_workcenter.map((row, index) => (
                      <tr key={String(row["workcenter_id"] ?? index)} className="border-t">
                        {Object.entries(row).map(([key, value]) => {
                          const center = workcenters.data?.find((item) => item.id === String(value));
                          const display = key === "workcenter_id"
                            ? (String(value) === "Unassigned" ? "Unassigned" : center ? `${center.code} — ${center.name}` : String(value ?? "Unassigned"))
                            : number(value);
                          return <td key={key} className={`whitespace-nowrap px-4 py-3 tabular-nums ${key === "workcenter_id" ? "font-medium" : "text-right"}`}>{display}</td>;
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <p className="text-xs text-muted-foreground">
            Scope note: the backend currently exposes a manufacturing report endpoint. Inventory, sales, finance, HR and audit reports are not presented here as finished reports because dedicated report endpoints are not confirmed.
          </p>
        </>
      ) : null}
    </main>
  );
}
