// Shared ERP building blocks used by every module screen.
import { useState, type ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { toast } from "sonner";
import { DataTable, type Column } from "@/components/data-table";
import { ErrorState, TableSkeleton } from "@/components/query-state";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { ApiError } from "@/lib/api/client";

export function apiErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}

/** Runs a mutation promise and reports success/failure through toasts. */
export async function runMutation<R>(p: Promise<R>, success: string): Promise<R | null> {
  try {
    const r = await p;
    toast.success(success);
    return r;
  } catch (e) {
    toast.error(apiErrorMessage(e));
    return null;
  }
}

export function QueryTable<T>({
  query,
  columns,
  rowKey,
  exportName,
  emptyTitle,
  onRowClick,
  toolbar,
  searchPlaceholder,
}: {
  query: UseQueryResult<T[]>;
  columns: Column<T>[];
  rowKey: (row: T) => string;
  exportName: string;
  emptyTitle: string;
  onRowClick?: ((row: T) => void) | undefined;
  toolbar?: ReactNode;
  searchPlaceholder?: string | undefined;
}) {
  if (query.isLoading) return <TableSkeleton cols={Math.min(columns.length, 6)} />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  return (
    <DataTable
      data={query.data ?? []}
      columns={columns}
      rowKey={rowKey}
      exportName={exportName}
      emptyTitle={emptyTitle}
      {...(onRowClick ? { onRowClick } : {})}
      {...(toolbar ? { toolbar } : {})}
      {...(searchPlaceholder ? { searchPlaceholder } : {})}
    />
  );
}

export interface Option {
  value: string;
  label: string;
}

export function SelectField({
  value,
  onChange,
  options,
  placeholder = "Select…",
  allowNone = false,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Option[];
  placeholder?: string;
  allowNone?: boolean;
}) {
  return (
    <Select value={value === "" ? "__none" : value} onValueChange={(v) => onChange(v === "__none" ? "" : v)}>
      <SelectTrigger>
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {allowNone || value === "" ? <SelectItem value="__none">{allowNone ? "— None —" : placeholder}</SelectItem> : null}
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export function NumInput({ value, onChange, step = "any" }: { value: number; onChange: (n: number) => void; step?: string }) {
  return (
    <Input
      type="number"
      step={step}
      className="tabular-nums"
      value={Number.isFinite(value) ? value : 0}
      onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))}
    />
  );
}

export function ConfirmAction({
  trigger,
  title,
  description,
  confirmLabel = "Confirm",
  destructive = false,
  onConfirm,
}: {
  trigger: ReactNode;
  title: string;
  description: string;
  confirmLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>{trigger}</AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={destructive ? "bg-destructive text-destructive-foreground hover:bg-destructive/90" : ""}
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

export function DetailSheet({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          {description ? <SheetDescription>{description}</SheetDescription> : null}
        </SheetHeader>
        <div className="mt-4 space-y-5 px-4 pb-6">{children}</div>
      </SheetContent>
    </Sheet>
  );
}

export function KeyValues({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 rounded-md border bg-card p-4 text-sm">
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="text-xs uppercase tracking-wide text-muted-foreground">{k}</dt>
          <dd className="mt-0.5 truncate font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SectionTitle({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{children}</h3>
      {actions}
    </div>
  );
}

export function ModuleTabs({ tabs, defaultValue }: { tabs: { value: string; label: string; content: ReactNode }[]; defaultValue?: string }) {
  const [v, setV] = useState(defaultValue ?? tabs[0]?.value ?? "");
  return (
    <Tabs value={v} onValueChange={setV} className="space-y-4">
      <TabsList className="h-auto flex-wrap justify-start">
        {tabs.map((t) => (
          <TabsTrigger key={t.value} value={t.value}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((t) => (
        <TabsContent key={t.value} value={t.value} className="space-y-4">
          {t.content}
        </TabsContent>
      ))}
    </Tabs>
  );
}

export function BackendGap({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed border-warning/50 bg-warning/5 p-3 text-sm text-muted-foreground">
      <span className="font-medium text-warning">Not in backend yet · </span>
      {children}
    </div>
  );
}

export function lookup<T extends { id: string }>(rows: T[] | undefined, id: string | null | undefined, label: (r: T) => string): string {
  if (!id) return "—";
  const r = rows?.find((x) => x.id === id);
  return r ? label(r) : id.slice(0, 8);
}
