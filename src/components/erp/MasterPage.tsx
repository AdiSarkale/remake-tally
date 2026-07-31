import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { PageHeader } from "./PageHeader";
import { logAudit, uid, update, useErp } from "@/lib/erp/store";
import type { ErpState } from "@/lib/erp/types";
import { useAuth } from "@/lib/erp/auth";

export interface Field {
  name: string;
  label: string;
  type?: "text" | "number" | "textarea";
  required?: boolean;
  placeholder?: string;
  full?: boolean;
  step?: string;
}

type MasterKey = "customers" | "suppliers" | "products" | "materials" | "scrapTypes";
export type Row = {
  id: string;
  name?: string;
  code?: string;
  category?: string;
  unit?: string;
  sellingPrice?: number;
  costPrice?: number;
  hsnCode?: string;
  gstPercent?: number;
  minStock?: number;
  stock?: number;
  cost?: number;
  sellingRate?: number;
  gstNumber?: string;
  mobile?: string;
  email?: string;
  contact?: string;
  address?: string;
} & Record<string, unknown>;

interface Props {
  title: string;
  subtitle: string;
  entity: MasterKey;
  fields: Field[];
  columns: Column<Row>[];
  searchable: (row: Row) => string;
  defaults?: Record<string, unknown>;
  readOnly?: boolean;
}

export function MasterPage({
  title,
  subtitle,
  entity,
  fields,
  columns,
  searchable,
  defaults = {},
  readOnly = false,
}: Props) {
  const rows = useErp((s) => s[entity]) as unknown as Row[];
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Row | null>(null);
  const [deleting, setDeleting] = useState<Row | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});

  const startCreate = () => {
    setEditing(null);
    setForm(Object.fromEntries(fields.map((f) => [f.name, ""])));
    setOpen(true);
  };

  const startEdit = (row: Row) => {
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
      const list = s[entity] as unknown as Row[];
      if (editing) {
        const idx = list.findIndex((r) => r.id === editing.id);
        if (idx >= 0) list[idx] = { ...(list[idx] as Row), ...payload } as Row;
        logAudit(s as ErpState, session?.username ?? "system", "UPDATE", entity, String(payload['name'] ?? editing.id));
      } else {
        list.unshift({ id: uid(), ...payload } as Row);
        logAudit(s as ErpState, session?.username ?? "system", "CREATE", entity, String(payload['name'] ?? ""));
      }
      return s;
    });
    toast.success(editing ? `${title.replace(/s$/, "")} updated` : `${title.replace(/s$/, "")} created`);
    setOpen(false);
  };

  const confirmDelete = () => {
    if (!deleting) return;
    update((s) => {
      const list = s[entity] as unknown as Row[];
      const idx = list.findIndex((r) => r.id === deleting.id);
      if (idx >= 0) list.splice(idx, 1);
      logAudit(s as ErpState, session?.username ?? "system", "DELETE", entity, String(deleting.name ?? deleting.id));
      return s;
    });
    toast.success("Record deleted");
    setDeleting(null);
  };

  const allColumns: Column<Row>[] = readOnly
    ? columns
    : [
        ...columns,
        {
          key: "actions",
          header: "",
          align: "right",
          render: (row) => (
            <div className="flex justify-end gap-1">
              <Button variant="ghost" size="icon" onClick={() => startEdit(row)} aria-label="Edit">
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setDeleting(row)} aria-label="Delete">
                <Trash2 className="text-destructive h-4 w-4" />
              </Button>
            </div>
          ),
        },
      ];

  return (
    <>
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={
          !readOnly && (
            <Button onClick={startCreate}>
              <Plus className="mr-1 h-4 w-4" /> New
            </Button>
          )
        }
      />
      <DataTable rows={rows} columns={allColumns} rowKey={(r) => r.id} searchable={searchable} />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit" : "New"} {title.replace(/s$/, "")}
            </DialogTitle>
            <DialogDescription>Fields marked required must be filled before saving.</DialogDescription>
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
                    value={form[f.name] ?? ""}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                    placeholder={f.placeholder}
                    rows={3}
                  />
                ) : (
                  <Input
                    id={f.name}
                    type={f.type === "number" ? "number" : "text"}
                    step={f.step}
                    value={form[f.name] ?? ""}
                    onChange={(e) => setForm({ ...form, [f.name]: e.target.value })}
                    placeholder={f.placeholder}
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
              This removes the master record permanently. Historical movements stay in the ledger.
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
