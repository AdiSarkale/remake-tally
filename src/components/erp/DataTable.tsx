import { useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
  value?: (row: T) => string | number;
  align?: "left" | "right";
  className?: string;
}

interface Props<T> {
  rows: T[];
  columns: Column<T>[];
  searchable?: (row: T) => string;
  rowKey: (row: T) => string;
  pageSize?: number;
  toolbar?: ReactNode;
  filters?: ReactNode;
  empty?: string;
}

export function DataTable<T>({
  rows,
  columns,
  searchable,
  rowKey,
  pageSize = 10,
  toolbar,
  filters,
  empty = "No records yet.",
}: Props<T>) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    let out = term && searchable ? rows.filter((r) => searchable(r).toLowerCase().includes(term)) : [...rows];
    if (sort) {
      const col = columns.find((c) => c.key === sort.key);
      if (col?.value) {
        out.sort((a, b) => {
          const av = col.value!(a);
          const bv = col.value!(b);
          const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
          return sort.dir === "asc" ? cmp : -cmp;
        });
      }
    }
    return out;
  }, [rows, q, sort, columns, searchable]);

  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const current = Math.min(page, pages);
  const slice = filtered.slice((current - 1) * pageSize, current * pageSize);

  return (
    <div className="panel overflow-hidden">
      <div className="flex flex-wrap items-center gap-2 border-b p-3">
        {searchable && (
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setPage(1);
              }}
              placeholder="Search…"
              className="pl-9"
            />
          </div>
        )}
        {filters}
        <div className="ml-auto flex items-center gap-2">{toolbar}</div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50 text-left">
              {columns.map((c) => (
                <th
                  key={c.key}
                  className={cn(
                    "px-4 py-2.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase",
                    c.align === "right" && "text-right",
                  )}
                >
                  {c.value ? (
                    <button
                      className="inline-flex items-center gap-1 hover:text-foreground"
                      onClick={() =>
                        setSort((prev) =>
                          prev?.key === c.key
                            ? { key: c.key, dir: prev.dir === "asc" ? "desc" : "asc" }
                            : { key: c.key, dir: "asc" },
                        )
                      }
                    >
                      {c.header}
                      {sort?.key === c.key &&
                        (sort.dir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
                    </button>
                  ) : (
                    c.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {slice.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {empty}
                </td>
              </tr>
            )}
            {slice.map((row) => (
              <tr key={rowKey(row)} className="border-b last:border-0 hover:bg-muted/40">
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={cn("px-4 py-2.5 align-middle", c.align === "right" && "text-right", c.className)}
                  >
                    {c.render ? c.render(row) : String(c.value?.(row) ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t px-4 py-2.5 text-xs text-muted-foreground">
        <span>
          {filtered.length === 0 ? 0 : (current - 1) * pageSize + 1}–{Math.min(current * pageSize, filtered.length)} of{" "}
          {filtered.length}
        </span>
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" disabled={current <= 1} onClick={() => setPage(current - 1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="px-2">
            {current} / {pages}
          </span>
          <Button variant="outline" size="icon" disabled={current >= pages} onClick={() => setPage(current + 1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
