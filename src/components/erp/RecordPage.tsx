import { useState, type ReactNode } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { DataTable, type Column } from "./DataTable";
import { logAudit, today, uid, update, useErp } from "@/lib/erp/store";
import { nextOpsNo } from "@/lib/erp/ops";
import type { ErpState } from "@/lib/erp/types";
import { useAuth } from "@/lib/erp/auth";

export interface RecordField {
  name: string;
  label: string;
  type?: "text" | "number" | "textarea" | "date" | "select";
  options?: string[];
  required?: boolean;
  placeholder?: string;
  full?: boolean;
  step?: string;
}

export type AnyRecord = { id: string } & Record<string, unknown>;

/** Keys of ErpState holding a flat array of operational records. */
export type RecordKey =
  | "machines"
  | "productionPlans"
  | "designRequests"
  | "inspections"
  | "ncrs"
  | "complaints"
  | "calibrations"
  | "maintenancePlans"
  | "breakdowns"
  | "spares"
  | "dispatches"
  | "employees"
  | "attendance"
  | "leaves"
  | "trainings"
  | "appraisals"
  | "payments"
  | "expenses"
  | "gatePasses"
  | "visitors"
  | "assets"
  | "adminServices"
  | "leads";

interface Props {
  entity: RecordKey;
  singular: string;
  fields: RecordField[];
  columns: Column<AnyRecord>[];
  searchable: (row: AnyRecord) => string;
  /** Auto-generated document number, e.g. `{ field: "qcNo", prefix: "QC" }`. */
  autoNumber?: { field: string; prefix: string };
  defaults?: Record<string, unknown>;
  /** Extra per-row buttons rendered before edit/delete. */
  rowActions?: (row: AnyRecord) => ReactNode;
  readOnly?: boolean;
  empty?: string;
}

/**
 * Generic list + create/edit/delete surface for any operational register.
 * Every mutation is written to the audit trail like the rest of the ERP.
 */
export function RecordPage({
  entity,
  singular,
  fields,
  columns,
  searchable,
  autoNumber,
  defaults = {},
  rowActions,
  readOnly = false,
  empty,
}: Props) {
  const rows = useErp((s) => s[entity]) as unknown as AnyRecord[];
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<AnyRecord | null>(null);
  const [deleting, setDeleting] = useState<AnyRecord | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});

  const blank = () =>
    Object.fromEntries(
      fields.map((f) => [f.name, f.type === "date" ? today() : f.type === "select" ? (f.options?.[0] ?? "") : ""]),
    );

  const startCreate = () => {
    setEditing(null);
    setForm(blank());
    setOpen(true);
  };

  const startEdit = (row: AnyRecord) => {
    setEditing(row);
    setForm(Object.fromEntries(fields.map((f) => [f.name, String(row[f.name] ?? "")])));
    setOpen(true);
  };

  const save = () => {
    for (const f of fields) {
      if (f.required && !String(form[f.name] ?? "").trim()) {
        toast.error(`${f.label} is required`);
        return;
      }
    }
    const payload: Record<string, unknown> = { ...defaults };
    fields.forEach((f) => {
      const raw = form[f.name] ?? "";
      payload[f.name] = f.type === "number" ? Number(raw || 0) : raw.trim();
    });

    update((s) => {
      const list = s[entity] as unknown as AnyRecord[];
      if (editing) {
        const idx = list.findIndex((r) => r.id === editing.id);
        if (idx >= 0) list[idx] = { ...(list[idx] as AnyRecord), ...payload };
        logAudit(s as ErpState, session?.username ?? "system", "UPDATE", entity, `${singular} ${describe(editing)}`);
      } else {
        if (autoNumber)
          payload[autoNumber.field] = nextOpsNo(
            list.map((r) => String(r[autoNumber.field] ?? "")),
            autoNumber.prefix,
          );
        const created = { id: uid(), ...payload } as AnyRecord;
        list.unshift(created);
        logAudit(s as ErpState, session?.username ?? "system", "CREATE", entity, `${singular} ${describe(created)}`);
      }
      return s;
    });
    toast.success(editing ? `${singular} updated` : `${singular} created`);
    setOpen(false);
  };

  const confirmDelete = () => {
    if (!deleting) return;
    update((s) => {
      const list = s[entity] as unknown as AnyRecord[];
      const idx = list.findIndex((r) => r.id === deleting.id);
      if (idx >= 0) list.splice(idx, 1);
      logAudit(s as ErpState, session?.username ?? "system", "DELETE", entity, `${singular} ${describe(deleting)}`);
      return s;
    });
    toast.success(`${singular} deleted`);
    setDeleting(null);
  };

  const allColumns: Column<AnyRecord>[] =
    readOnly && !rowActions
      ? columns
      : [
          ...columns,
          {
            key: "actions",
            header: "",
            align: "right",
            render: (row) => (
              <div className="flex justify-end gap-1">
                {rowActions?.(row)}
                {!readOnly && (
                  <>
                    <Button variant="ghost" size="icon" onClick={() => startEdit(row)} aria-label="Edit">
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => setDeleting(row)} aria-label="Delete">
                      <Trash2 className="text-destructive h-4 w-4" />
                    </Button>
                  </>
                )}
              </div>
            ),
          },
        ];

  return (
    <>
      {!readOnly && (
        <div className="mb-3 flex justify-end">
          <Button onClick={startCreate}>
            <Plus className="mr-1 h-4 w-4" /> New {singular}
          </Button>
        </div>
      )}
      <DataTable
        rows={rows}
        columns={allColumns}
        rowKey={(r) => r.id}
        searchable={searchable}
        empty={empty}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit" : "New"} {singular}
            </DialogTitle>
            <DialogDescription>
              {autoNumber && !editing
                ? "The document number is generated automatically on save."
                : "Fields marked required must be filled before saving."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            {fields.map((f) => (
              <div key={f.name} className={f.full || f.type === "textarea" ? "col-span-2" : "col-span-2 sm:col-span-1"}>
                <Label htmlFor={f.name} className="mb-1.5 block text-xs">
                  {f.label}
                  {f.required && <span className="text-destructive"> *</span>}
                </Label>
                {f.type === "textarea" ? (
                  <Textarea
                    id={f.name}
                    rows={3}
                    value={form[f.name] ?? ""}
                    placeholder={f.placeholder}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  />
                ) : f.type === "select" ? (
                  <Select
                    value={form[f.name] ?? ""}
                    onValueChange={(v) => setForm({ ...form, [f.name]: v })}
                  >
                    <SelectTrigger id={f.name}>
                      <SelectValue placeholder={f.placeholder ?? "Select"} />
                    </SelectTrigger>
                    <SelectContent>
                      {(f.options ?? []).map((o) => (
                        <SelectItem key={o} value={o}>
                          {o}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <Input
                    id={f.name}
                    type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"}
                    step={f.step}
                    value={form[f.name] ?? ""}
                    placeholder={f.placeholder}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                  />
                )}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={save}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this record?</AlertDialogTitle>
            <AlertDialogDescription>
              The register entry is removed permanently. Audit history is retained.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function describe(row: AnyRecord) {
  const label =
    row['qcNo'] ?? row['ncrNo'] ?? row['planNo'] ?? row['drNo'] ?? row['ticketNo'] ?? row['dispatchNo'] ??
    row['voucherNo'] ?? row['gpNo'] ?? row['enquiryNo'] ?? row['complaintNo'] ?? row['empCode'] ??
    row['assetCode'] ?? row['code'] ?? row['name'] ?? row['id'];
  return String(label);
}
