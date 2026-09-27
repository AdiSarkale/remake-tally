// BOM, routing and work-center masters for the Production module.
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatusBadge } from "@/components/status-badge";
import { FormDialog, FormField } from "@/components/form-dialog";
import { ConfirmAction, DetailSheet, KeyValues, NumInput, QueryTable, SectionTitle, SelectField, lookup, runMutation } from "@/components/erp";
import * as H from "@/lib/api/hooks";
import type * as T from "@/lib/api/types";
import { formatNumber } from "@/lib/format";

export const WC_STATUSES = ["Available", "Running", "Idle", "Under Maintenance", "Breakdown"];

// ---------------- BOM ----------------
export function BomTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useBoms();
  const products = H.useProducts();
  const materials = H.useMaterials();
  const scrapTypes = H.useScrapTypes();
  const create = H.useCreateBom();
  const update = H.useUpdateBom();
  const remove = H.useDeleteBom();
  const blank: T.BomIn = { product_id: "", version: 1, active: true, expected_scrap_percent: 0, scrap_type_id: null, lines: [{ material_id: "", quantity: 1 }] };
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [f, setF] = useState<T.BomIn>(blank);
  const [sel, setSel] = useState<T.BOMOut | null>(null);

  const submit = async () => {
    const lines = f.lines.filter((l) => l.material_id && l.quantity > 0);
    if (!f.product_id || lines.length === 0) return;
    const body = { ...f, lines };
    const r = editId ? await runMutation(update.mutateAsync({ id: editId, ...body }), "BOM updated") : await runMutation(create.mutateAsync(body), "BOM created");
    if (r) setOpen(false);
  };
  const edit = (b: T.BOMOut) => {
    setEditId(b.id);
    setF({ product_id: b.product_id, version: b.version, active: b.active, expected_scrap_percent: b.expected_scrap_percent, scrap_type_id: b.scrap_type_id, lines: b.lines.map((l) => ({ material_id: l.material_id, quantity: l.quantity })) });
    setSel(null);
    setOpen(true);
  };

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="boms"
        emptyTitle="No bills of materials"
        onRowClick={setSel}
        toolbar={canEdit ? <Button size="sm" onClick={() => { setEditId(null); setF(blank); setOpen(true); }}><Plus className="mr-1 h-4 w-4" /> New BOM</Button> : null}
        columns={[
          { key: "prod", header: "Product", render: (r) => lookup(products.data, r.product_id, (p) => `${p.code} — ${p.name}`), searchValue: (r) => lookup(products.data, r.product_id, (p) => p.code + p.name) },
          { key: "ver", header: "Version", render: (r) => `v${r.version}`, sortValue: (r) => r.version },
          { key: "lines", header: "Components", render: (r) => r.lines.length },
          { key: "scrap", header: "Exp. scrap", className: "text-right", render: (r) => `${formatNumber(r.expected_scrap_percent, 1)}%` },
          { key: "active", header: "Status", render: (r) => <StatusBadge status={r.active ? "Active" : "Inactive"} /> },
        ]}
      />
      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSel(null)} title={sel ? `BOM v${sel.version}` : ""} description={sel ? lookup(products.data, sel.product_id, (p) => p.name) : ""}>
        {sel ? (
          <>
            <KeyValues items={[["Status", <StatusBadge key="s" status={sel.active ? "Active" : "Inactive"} />], ["Expected scrap", `${sel.expected_scrap_percent}%`], ["Scrap type", lookup(scrapTypes.data, sel.scrap_type_id, (s) => s.name)], ["Components", String(sel.lines.length)]]} />
            <div className="rounded-md border">
              <Table>
                <TableHeader><TableRow><TableHead>Material (RM)</TableHead><TableHead className="text-right">Qty / unit</TableHead><TableHead className="text-right">In stock</TableHead></TableRow></TableHeader>
                <TableBody>
                  {sel.lines.map((l) => {
                    const m = materials.data?.find((x) => x.id === l.material_id);
                    return (
                      <TableRow key={l.id}>
                        <TableCell>{m ? `${m.code} — ${m.name}` : l.material_id}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatNumber(l.quantity, 3)} {m?.unit}</TableCell>
                        <TableCell className="text-right tabular-nums">{formatNumber(m?.stock, 2)}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
            {canEdit ? (
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => edit(sel)}>Edit BOM</Button>
                <ConfirmAction destructive title="Delete this BOM?" description="Production entries for this product will fail without an active BOM." confirmLabel="Delete"
                  onConfirm={() => void runMutation(remove.mutateAsync(sel.id), "BOM deleted").then((r) => r !== null && setSel(null))}
                  trigger={<Button size="sm" variant="outline" className="text-destructive">Delete</Button>} />
              </div>
            ) : null}
          </>
        ) : null}
      </DetailSheet>
      <FormDialog open={open} onOpenChange={setOpen} title={editId ? "Edit BOM" : "New bill of materials"} wide onSubmit={() => void submit()} pending={create.isPending || update.isPending}>
        <div className="grid gap-3 sm:grid-cols-4">
          <FormField label="Product (FG/SFG) *" className="space-y-1.5 sm:col-span-2">
            <SelectField value={f.product_id} onChange={(v) => setF({ ...f, product_id: v })} options={(products.data ?? []).map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` }))} />
          </FormField>
          <FormField label="Version"><NumInput step="1" value={f.version} onChange={(n) => setF({ ...f, version: n })} /></FormField>
          <FormField label="Exp. scrap %"><NumInput value={f.expected_scrap_percent} onChange={(n) => setF({ ...f, expected_scrap_percent: n })} /></FormField>
          <FormField label="Scrap type" className="space-y-1.5 sm:col-span-2">
            <SelectField allowNone value={f.scrap_type_id ?? ""} onChange={(v) => setF({ ...f, scrap_type_id: v || null })} options={(scrapTypes.data ?? []).map((s) => ({ value: s.id, label: s.name }))} />
          </FormField>
          <label className="flex items-center gap-2 pt-6 text-sm"><Switch checked={f.active} onCheckedChange={(c) => setF({ ...f, active: c })} /> Active</label>
        </div>
        <SectionTitle actions={<Button type="button" size="sm" variant="outline" onClick={() => setF({ ...f, lines: [...f.lines, { material_id: "", quantity: 1 }] })}><Plus className="mr-1 h-3.5 w-3.5" /> Component</Button>}>Components per unit</SectionTitle>
        {f.lines.map((l, i) => (
          <div key={i} className="grid grid-cols-[1fr_110px_32px] gap-2">
            <SelectField value={l.material_id} placeholder="Material" onChange={(v) => setF({ ...f, lines: f.lines.map((x, j) => (j === i ? { ...x, material_id: v } : x)) })} options={(materials.data ?? []).map((m) => ({ value: m.id, label: `${m.code} — ${m.name}` }))} />
            <NumInput value={l.quantity} onChange={(n) => setF({ ...f, lines: f.lines.map((x, j) => (j === i ? { ...x, quantity: n } : x)) })} />
            <Button type="button" size="icon" variant="ghost" className="h-8 w-8" aria-label="Remove" onClick={() => setF({ ...f, lines: f.lines.filter((_, j) => j !== i) })}><Trash2 className="h-3.5 w-3.5" /></Button>
          </div>
        ))}
      </FormDialog>
    </>
  );
}

// ---------------- Routings ----------------
const blankOp = (seq: number): T.RoutingOperationIn => ({ sequence: seq, code: `OP${seq}`, name: "", workcenter_id: "", required_skill: "", setup_minutes: 0, run_minutes_per_unit: 0, active: true });

export function RoutingTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useRoutings();
  const products = H.useProducts();
  const wcs = H.useWorkcenters();
  const create = H.useCreateRouting();
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<T.RoutingOut | null>(null);
  const [f, setF] = useState<T.RoutingIn>({ product_id: "", version: 1, name: "", active: true, operations: [blankOp(10)] });
  const submit = async () => {
    const ops = f.operations.filter((o) => o.workcenter_id && o.name);
    if (!f.product_id || ops.length === 0) return;
    if (await runMutation(create.mutateAsync({ ...f, operations: ops }), "Routing created")) setOpen(false);
  };
  const setOp = (i: number, patch: Partial<T.RoutingOperationIn>) => setF({ ...f, operations: f.operations.map((o, j) => (j === i ? { ...o, ...patch } : o)) });
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="routings"
        emptyTitle="No routings"
        onRowClick={setSel}
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New routing</Button> : null}
        columns={[
          { key: "name", header: "Routing", render: (r) => r.name || "—", searchValue: (r) => r.name },
          { key: "prod", header: "Product", render: (r) => lookup(products.data, r.product_id, (p) => `${p.code} — ${p.name}`), searchValue: (r) => lookup(products.data, r.product_id, (p) => p.name) },
          { key: "ver", header: "Version", render: (r) => `v${r.version}` },
          { key: "ops", header: "Operations", render: (r) => r.operations.map((o) => `${o.sequence} ${lookup(wcs.data, o.workcenter_id, (w) => w.code)}`).join(" → ") },
          { key: "a", header: "Status", render: (r) => <StatusBadge status={r.active ? "Active" : "Inactive"} /> },
        ]}
      />
      <DetailSheet open={sel !== null} onOpenChange={(o) => !o && setSel(null)} title={sel?.name || "Routing"} description={sel ? lookup(products.data, sel.product_id, (p) => p.name) : ""}>
        {sel ? (
          <div className="rounded-md border">
            <Table>
              <TableHeader><TableRow><TableHead>Seq</TableHead><TableHead>Operation</TableHead><TableHead>Work center</TableHead><TableHead>Skill</TableHead><TableHead className="text-right">Setup / Run</TableHead></TableRow></TableHeader>
              <TableBody>
                {sel.operations.map((o) => (
                  <TableRow key={o.id}>
                    <TableCell className="tabular-nums">{o.sequence}</TableCell>
                    <TableCell>{o.code} — {o.name}</TableCell>
                    <TableCell className="font-mono text-xs">{lookup(wcs.data, o.workcenter_id, (w) => w.code)}</TableCell>
                    <TableCell>{o.required_skill || "Any"}</TableCell>
                    <TableCell className="text-right tabular-nums">{o.setup_minutes}m / {o.run_minutes_per_unit}m</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
        <p className="text-xs text-muted-foreground">When a production order is created, each operation is auto-assigned to the highest-level active employee holding the required skill.</p>
      </DetailSheet>
      <FormDialog open={open} onOpenChange={setOpen} title="New routing" wide onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-4">
          <FormField label="Product *" className="space-y-1.5 sm:col-span-2"><SelectField value={f.product_id} onChange={(v) => setF({ ...f, product_id: v })} options={(products.data ?? []).map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` }))} /></FormField>
          <FormField label="Name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></FormField>
          <FormField label="Version"><NumInput step="1" value={f.version} onChange={(n) => setF({ ...f, version: n })} /></FormField>
        </div>
        <SectionTitle actions={<Button type="button" size="sm" variant="outline" onClick={() => setF({ ...f, operations: [...f.operations, blankOp((f.operations.length + 1) * 10)] })}><Plus className="mr-1 h-3.5 w-3.5" /> Operation</Button>}>Operations</SectionTitle>
        <div className="space-y-2">
          {f.operations.map((o, i) => (
            <div key={i} className="grid grid-cols-[60px_80px_1fr_1fr_1fr_70px_70px_32px] items-center gap-2">
              <NumInput step="1" value={o.sequence} onChange={(n) => setOp(i, { sequence: n })} />
              <Input value={o.code} onChange={(e) => setOp(i, { code: e.target.value })} placeholder="Code" />
              <Input value={o.name} onChange={(e) => setOp(i, { name: e.target.value })} placeholder="Operation name" />
              <SelectField value={o.workcenter_id} placeholder="Work center" onChange={(v) => setOp(i, { workcenter_id: v })} options={(wcs.data ?? []).map((w) => ({ value: w.id, label: w.code }))} />
              <Input value={o.required_skill} onChange={(e) => setOp(i, { required_skill: e.target.value })} placeholder="Required skill" />
              <NumInput value={o.setup_minutes} onChange={(n) => setOp(i, { setup_minutes: n })} />
              <NumInput value={o.run_minutes_per_unit} onChange={(n) => setOp(i, { run_minutes_per_unit: n })} />
              <Button type="button" size="icon" variant="ghost" className="h-8 w-8" aria-label="Remove" onClick={() => setF({ ...f, operations: f.operations.filter((_, j) => j !== i) })}><Trash2 className="h-3.5 w-3.5" /></Button>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">Seq · Code · Name · Work center · Skill · Setup min · Run min/unit</p>
        </div>
      </FormDialog>
    </>
  );
}

// ---------------- Work centers ----------------
export function WorkcenterTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useWorkcenters();
  const routings = H.useRoutings();
  const products = H.useProducts();
  const materials = H.useMaterials();
  const create = H.useCreateWorkcenter();
  const update = H.useUpdateWorkcenter();
  const blank: T.WorkcenterIn = { code: "", name: "", department: "", capacity_per_hour: 0, status: "Available", active: true, location: "", materials: [] };
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [f, setF] = useState<T.WorkcenterIn>(blank);

  const ops = (routings.data ?? []).flatMap((r) => r.operations.filter((o) => !editId || o.workcenter_id === editId).map((o) => ({ value: o.id, label: `${r.name || "Routing"} · ${o.sequence} ${o.name}` })));
  const itemOptions = (kind: "RM" | "SF" | "FG") =>
    kind === "RM" ? (materials.data ?? []).map((m) => ({ value: m.id, label: `${m.code} — ${m.name}` })) : (products.data ?? []).map((p) => ({ value: p.id, label: `${p.code} — ${p.name}` }));
  const itemLabel = (m: T.WorkcenterMaterialOut) =>
    m.item_kind === "RM" ? lookup(materials.data, m.item_id, (x) => x.code) : lookup(products.data, m.item_id, (x) => x.code);

  const submit = async () => {
    if (!f.code || !f.name) return;
    const body = { ...f, materials: f.materials.filter((m) => m.item_id) };
    const r = editId ? await runMutation(update.mutateAsync({ id: editId, ...body }), "Work center updated") : await runMutation(create.mutateAsync(body), "Work center created");
    if (r) setOpen(false);
  };
  const edit = (w: T.WorkcenterOut) => {
    const { id, materials: mats, ...rest } = w;
    setEditId(id);
    setF({ ...rest, materials: mats.map((m) => ({ item_kind: m.item_kind === "RM" || m.item_kind === "SF" ? m.item_kind : "FG", item_id: m.item_id, operation_id: m.operation_id })) });
    setOpen(true);
  };

  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="work-centers"
        emptyTitle="No work centers"
        {...(canEdit ? { onRowClick: edit } : {})}
        toolbar={canEdit ? <Button size="sm" onClick={() => { setEditId(null); setF(blank); setOpen(true); }}><Plus className="mr-1 h-4 w-4" /> New work center</Button> : null}
        columns={[
          { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code, sortValue: (r) => r.code },
          { key: "name", header: "Name", render: (r) => r.name, searchValue: (r) => r.name },
          { key: "dept", header: "Department", render: (r) => r.department || "—", hideable: true },
          { key: "cap", header: "Capacity/h", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.capacity_per_hour, 1)}</span> },
          { key: "ops", header: "Operations", render: (r) => (routings.data ?? []).flatMap((x) => x.operations).filter((o) => o.workcenter_id === r.id).map((o) => o.name).join(", ") || "—" },
          { key: "mats", header: "Assigned items", render: (r) => r.materials.map((m) => `${m.item_kind}:${itemLabel(m)}`).join(", ") || "—", hideable: true },
          { key: "status", header: "Status", render: (r) => <StatusBadge status={r.active ? r.status : "Inactive"} />, sortValue: (r) => r.status },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title={editId ? `Edit ${f.code}` : "New work center"} wide onSubmit={() => void submit()} pending={create.isPending || update.isPending}>
        <div className="grid gap-3 sm:grid-cols-3">
          <FormField label="Code *"><Input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} className="font-mono" /></FormField>
          <FormField label="Name *" className="space-y-1.5 sm:col-span-2"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></FormField>
          <FormField label="Department"><Input value={f.department} onChange={(e) => setF({ ...f, department: e.target.value })} /></FormField>
          <FormField label="Location"><Input value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></FormField>
          <FormField label="Capacity / hour"><NumInput value={f.capacity_per_hour} onChange={(n) => setF({ ...f, capacity_per_hour: n })} /></FormField>
          <FormField label="Status"><SelectField value={f.status} onChange={(v) => setF({ ...f, status: v })} options={WC_STATUSES.map((s) => ({ value: s, label: s }))} /></FormField>
          <label className="flex items-center gap-2 pt-6 text-sm"><Switch checked={f.active} onCheckedChange={(c) => setF({ ...f, active: c })} /> Active</label>
        </div>
        <SectionTitle actions={<Button type="button" size="sm" variant="outline" onClick={() => setF({ ...f, materials: [...f.materials, { item_kind: "RM", item_id: "", operation_id: null }] })}><Plus className="mr-1 h-3.5 w-3.5" /> Item</Button>}>
          Materials handled (RM / SFG / FG)
        </SectionTitle>
        {f.materials.length === 0 ? <p className="text-xs text-muted-foreground">No items assigned to this work center.</p> : null}
        {f.materials.map((m, i) => (
          <div key={i} className="grid grid-cols-[90px_1fr_1fr_32px] gap-2">
            <SelectField value={m.item_kind} onChange={(v) => setF({ ...f, materials: f.materials.map((x, j) => (j === i ? { ...x, item_kind: v as "RM" | "SF" | "FG", item_id: "" } : x)) })} options={[{ value: "RM", label: "RM" }, { value: "SF", label: "SFG" }, { value: "FG", label: "FG" }]} />
            <SelectField value={m.item_id} placeholder="Item" onChange={(v) => setF({ ...f, materials: f.materials.map((x, j) => (j === i ? { ...x, item_id: v } : x)) })} options={itemOptions(m.item_kind)} />
            <SelectField allowNone value={m.operation_id ?? ""} placeholder="Operation" onChange={(v) => setF({ ...f, materials: f.materials.map((x, j) => (j === i ? { ...x, operation_id: v || null } : x)) })} options={ops} />
            <Button type="button" size="icon" variant="ghost" className="h-8 w-8" aria-label="Remove" onClick={() => setF({ ...f, materials: f.materials.filter((_, j) => j !== i) })}><Trash2 className="h-3.5 w-3.5" /></Button>
          </div>
        ))}
      </FormDialog>
    </>
  );
}
