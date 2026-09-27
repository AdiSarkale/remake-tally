import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import type { UseMutationResult, UseQueryResult } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormDialog, FormField } from "@/components/form-dialog";
import { ConfirmAction, QueryTable, runMutation } from "@/components/erp";
import type { PartyIn, PartyOut } from "@/lib/api/types";

const EMPTY: PartyIn = { name: "", gst_number: "", phone: "", email: "", address: "" };

/** Customer / supplier master — list, create, edit, delete against /masters/{kind}. */
export function PartyManager({
  label,
  query,
  create,
  update,
  remove,
  canEdit,
}: {
  label: "Customer" | "Supplier";
  query: UseQueryResult<PartyOut[]>;
  create: UseMutationResult<PartyOut, Error, PartyIn>;
  update: UseMutationResult<PartyOut, Error, PartyIn & { id: string }>;
  remove: UseMutationResult<unknown, Error, string>;
  canEdit: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [form, setForm] = useState<PartyIn>(EMPTY);

  const startNew = () => {
    setEditId(null);
    setForm(EMPTY);
    setOpen(true);
  };
  const startEdit = (p: PartyOut) => {
    setEditId(p.id);
    setForm({ name: p.name, gst_number: p.gst_number, phone: p.phone, email: p.email, address: p.address });
    setOpen(true);
  };
  const submit = async () => {
    if (!form.name.trim()) return;
    const r = editId
      ? await runMutation(update.mutateAsync({ id: editId, ...form }), `${label} updated`)
      : await runMutation(create.mutateAsync(form), `${label} created`);
    if (r) setOpen(false);
  };

  const set = (k: keyof PartyIn) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName={`${label.toLowerCase()}s`}
        emptyTitle={`No ${label.toLowerCase()}s yet`}
        toolbar={
          canEdit ? (
            <Button size="sm" onClick={startNew}>
              <Plus className="mr-1 h-4 w-4" /> New {label.toLowerCase()}
            </Button>
          ) : null
        }
        columns={[
          { key: "name", header: "Name", render: (r) => <span className="font-medium">{r.name}</span>, sortValue: (r) => r.name, searchValue: (r) => r.name },
          { key: "gst", header: "GSTIN", render: (r) => <span className="font-mono text-xs">{r.gst_number || "—"}</span>, searchValue: (r) => r.gst_number },
          { key: "phone", header: "Phone", render: (r) => r.phone || "—", hideable: true },
          { key: "email", header: "Email", render: (r) => r.email || "—", hideable: true, searchValue: (r) => r.email },
          { key: "address", header: "Address", render: (r) => <span className="line-clamp-1">{r.address || "—"}</span>, hideable: true },
          {
            key: "actions",
            header: "",
            className: "w-24 text-right",
            render: (r) =>
              canEdit ? (
                <div className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => startEdit(r)} aria-label="Edit">
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <ConfirmAction
                    destructive
                    title={`Delete ${r.name}?`}
                    description="This cannot be undone. The backend will refuse if documents reference this record."
                    confirmLabel="Delete"
                    onConfirm={() => void runMutation(remove.mutateAsync(r.id), `${label} deleted`)}
                    trigger={
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" aria-label="Delete">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    }
                  />
                </div>
              ) : null,
          },
        ]}
      />
      <FormDialog
        open={open}
        onOpenChange={setOpen}
        title={editId ? `Edit ${label.toLowerCase()}` : `New ${label.toLowerCase()}`}
        onSubmit={() => void submit()}
        pending={create.isPending || update.isPending}
      >
        <FormField label="Name *">
          <Input value={form.name} onChange={set("name")} required />
        </FormField>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="GSTIN">
            <Input value={form.gst_number} onChange={set("gst_number")} className="font-mono" />
          </FormField>
          <FormField label="Phone">
            <Input value={form.phone} onChange={set("phone")} />
          </FormField>
        </div>
        <FormField label="Email">
          <Input type="email" value={form.email} onChange={set("email")} />
        </FormField>
        <FormField label="Address">
          <Input value={form.address} onChange={set("address")} />
        </FormField>
      </FormDialog>
    </>
  );
}
