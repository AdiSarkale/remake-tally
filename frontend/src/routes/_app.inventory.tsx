import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { FormDialog, FormField } from "@/components/form-dialog";
import { DataTable } from "@/components/data-table";
import { ErrorState, TableSkeleton } from "@/components/query-state";
import { ConfirmAction, ModuleTabs, NumInput, QueryTable, SelectField, lookup, runMutation } from "@/components/erp";
import * as H from "@/lib/api/hooks";
import type * as T from "@/lib/api/types";
import { useAuth } from "@/lib/auth";
import { formatCurrency, formatDate, formatNumber, todayIso } from "@/lib/format";
import { Trash2 } from "lucide-react";

export const Route = createFileRoute("/_app/inventory")({
  head: () => ({
    meta: [
      { title: "Inventory — Minitally ERP" },
      { name: "description", content: "Item masters, stock overview, movement ledger and storage locations." },
      { property: "og:title", content: "Inventory — Minitally ERP" },
      { property: "og:description", content: "Item masters, stock overview, movement ledger and storage locations." },
    ],
  }),
  component: InventoryPage,
});

function InventoryPage() {
  const { can } = useAuth();
  return (
    <div className="space-y-5">
      <PageHeader title="Inventory" description="Raw materials, finished goods and scrap — every GRN, production and delivery posts to this ledger." />
      <ModuleTabs
        tabs={[
          { value: "stock", label: "Stock Overview", content: <StockTab /> },
          { value: "materials", label: "Raw Materials", content: <MaterialsTab canEdit={can("masters")} /> },
          { value: "products", label: "Products (FG/SFG)", content: <ProductsTab canEdit={can("masters")} /> },
          { value: "scrap", label: "Scrap Types", content: <ScrapTypesTab canEdit={can("masters")} /> },
          { value: "movements", label: "Movements", content: <MovementsTab canEdit={can("inventory")} /> },
          { value: "locations", label: "Locations", content: <LocationsTab canEdit={can("settings") || can("masters")} /> },
        ]}
      />
    </div>
  );
}

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md border bg-card p-4">
      <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      {sub ? <div className="mt-0.5 text-xs text-muted-foreground">{sub}</div> : null}
    </div>
  );
}

interface StockRow {
  id: string;
  kind: "RM" | "FG" | "Scrap";
  code: string;
  name: string;
  unit: string;
  stock: number;
  min: number;
  value: number;
}

function StockTab() {
  const val = H.useValuation();
  const products = H.useProducts();
  const materials = H.useMaterials();
  const scrap = H.useScrapTypes();
  const rows = useMemo<StockRow[]>(
    () => [
      ...(materials.data ?? []).map((m) => ({ id: m.id, kind: "RM" as const, code: m.code, name: m.name, unit: m.unit, stock: m.stock, min: m.min_stock, value: m.stock * m.cost })),
      ...(products.data ?? []).map((p) => ({ id: p.id, kind: "FG" as const, code: p.code, name: p.name, unit: p.unit, stock: p.stock, min: p.min_stock, value: p.stock * p.cost_price })),
      ...(scrap.data ?? []).map((s) => ({ id: s.id, kind: "Scrap" as const, code: s.code, name: s.name, unit: s.unit, stock: s.stock, min: s.min_stock, value: s.stock * s.selling_rate })),
    ],
    [materials.data, products.data, scrap.data],
  );
  const v = (k: string) => Number(val.data?.[k] ?? 0);
  if (products.isLoading || materials.isLoading) return <TableSkeleton />;
  if (products.isError) return <ErrorState error={products.error} />;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Total inventory value" value={formatCurrency(v("total"))} />
        <Kpi label="Raw materials" value={formatCurrency(v("raw_materials"))} sub={`${materials.data?.length ?? 0} items`} />
        <Kpi label="Finished goods" value={formatCurrency(v("finished_goods"))} sub={`${products.data?.length ?? 0} SKUs`} />
        <Kpi label="Scrap stock" value={formatCurrency(v("scrap"))} />
      </div>
      <DataTable
        data={rows}
        rowKey={(r) => r.kind + r.id}
        exportName="stock-overview"
        emptyTitle="No items"
        columns={[
          { key: "kind", header: "Type", render: (r) => <span className="font-mono text-xs">{r.kind}</span>, sortValue: (r) => r.kind, searchValue: (r) => r.kind },
          { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code, sortValue: (r) => r.code },
          { key: "name", header: "Item", render: (r) => r.name, searchValue: (r) => r.name, sortValue: (r) => r.name },
          { key: "stock", header: "On hand", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.stock, 2)} {r.unit}</span>, sortValue: (r) => r.stock },
          { key: "min", header: "Min", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.min, 2)}</span> },
          { key: "value", header: "Value", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.value)}</span>, sortValue: (r) => r.value },
          { key: "state", header: "Status", render: (r) => <StatusBadge status={r.stock <= 0 ? "Out of stock" : r.stock < r.min ? "Low stock" : "OK"} />, sortValue: (r) => r.stock - r.min },
        ]}
      />
    </div>
  );
}

function MaterialsTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useMaterials();
  const create = H.useCreateMaterial();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<T.RawMaterialIn>({ name: "", code: "", unit: "kg", cost: 0, min_stock: 0 });
  const submit = async () => {
    if (!f.name || !f.code) return;
    if (await runMutation(create.mutateAsync(f), "Material created")) setOpen(false);
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="raw-materials"
        emptyTitle="No raw materials"
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New material</Button> : null}
        columns={[
          { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code, sortValue: (r) => r.code },
          { key: "name", header: "Name", render: (r) => r.name, searchValue: (r) => r.name, sortValue: (r) => r.name },
          { key: "unit", header: "Unit", render: (r) => r.unit },
          { key: "cost", header: "Cost", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.cost)}</span>, sortValue: (r) => r.cost },
          { key: "stock", header: "Stock", className: "text-right", render: (r) => <span className={r.stock < r.min_stock ? "tabular-nums text-destructive" : "tabular-nums"}>{formatNumber(r.stock, 2)}</span>, sortValue: (r) => r.stock },
          { key: "min", header: "Min stock", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.min_stock, 2)}</span> },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="New raw material" onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Code *"><Input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} className="font-mono" /></FormField>
          <FormField label="Unit"><Input value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></FormField>
          <FormField label="Name *" className="space-y-1.5 sm:col-span-2"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></FormField>
          <FormField label="Cost / unit"><NumInput value={f.cost} onChange={(n) => setF({ ...f, cost: n })} /></FormField>
          <FormField label="Min stock"><NumInput value={f.min_stock} onChange={(n) => setF({ ...f, min_stock: n })} /></FormField>
        </div>
      </FormDialog>
    </>
  );
}

function ProductsTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useProducts();
  const create = H.useCreateProduct();
  const update = H.useUpdateProduct();
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const blank: T.ProductIn = { code: "", name: "", unit: "pcs", hsn: "", cost_price: 0, selling_price: 0, gst_rate: 18, min_stock: 0 };
  const [f, setF] = useState<T.ProductIn>(blank);
  const submit = async () => {
    if (!f.name || !f.code) return;
    const r = editId ? await runMutation(update.mutateAsync({ id: editId, ...f }), "Product updated") : await runMutation(create.mutateAsync(f), "Product created");
    if (r) setOpen(false);
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="products"
        emptyTitle="No products"
        onRowClick={canEdit ? (p) => { const { id, stock: _s, ...rest } = p; setEditId(id); setF(rest); setOpen(true); } : undefined}
        toolbar={canEdit ? <Button size="sm" onClick={() => { setEditId(null); setF(blank); setOpen(true); }}><Plus className="mr-1 h-4 w-4" /> New product</Button> : null}
        columns={[
          { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code, sortValue: (r) => r.code },
          { key: "name", header: "Name", render: (r) => r.name, searchValue: (r) => r.name, sortValue: (r) => r.name },
          { key: "hsn", header: "HSN", render: (r) => <span className="font-mono text-xs">{r.hsn || "—"}</span>, hideable: true },
          { key: "cost", header: "Cost", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.cost_price)}</span> },
          { key: "sell", header: "Price", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.selling_price)}</span>, sortValue: (r) => r.selling_price },
          { key: "gst", header: "GST", className: "text-right", render: (r) => `${r.gst_rate}%`, hideable: true },
          { key: "stock", header: "Stock", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.stock, 2)} {r.unit}</span>, sortValue: (r) => r.stock },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title={editId ? "Edit product" : "New product"} onSubmit={() => void submit()} pending={create.isPending || update.isPending}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Code *"><Input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} className="font-mono" /></FormField>
          <FormField label="HSN"><Input value={f.hsn} onChange={(e) => setF({ ...f, hsn: e.target.value })} /></FormField>
          <FormField label="Name *" className="space-y-1.5 sm:col-span-2"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></FormField>
          <FormField label="Unit"><Input value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></FormField>
          <FormField label="GST %"><NumInput value={f.gst_rate} onChange={(n) => setF({ ...f, gst_rate: n })} /></FormField>
          <FormField label="Cost price"><NumInput value={f.cost_price} onChange={(n) => setF({ ...f, cost_price: n })} /></FormField>
          <FormField label="Selling price"><NumInput value={f.selling_price} onChange={(n) => setF({ ...f, selling_price: n })} /></FormField>
          <FormField label="Min stock"><NumInput value={f.min_stock} onChange={(n) => setF({ ...f, min_stock: n })} /></FormField>
        </div>
      </FormDialog>
    </>
  );
}

function ScrapTypesTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useScrapTypes();
  const create = H.useCreateScrapType();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<T.ScrapTypeIn>({ code: "", name: "", unit: "kg", selling_rate: 0, min_stock: 0, active: true });
  const submit = async () => {
    if (!f.code || !f.name) return;
    if (await runMutation(create.mutateAsync(f), "Scrap type created")) setOpen(false);
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="scrap-types"
        emptyTitle="No scrap types"
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><Plus className="mr-1 h-4 w-4" /> New scrap type</Button> : null}
        columns={[
          { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code },
          { key: "name", header: "Name", render: (r) => r.name, searchValue: (r) => r.name, sortValue: (r) => r.name },
          { key: "rate", header: "Selling rate", className: "text-right", render: (r) => <span className="tabular-nums">{formatCurrency(r.selling_rate)}</span> },
          { key: "stock", header: "Stock", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.stock, 2)} {r.unit}</span>, sortValue: (r) => r.stock },
          { key: "active", header: "Status", render: (r) => <StatusBadge status={r.active ? "Active" : "Inactive"} /> },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="New scrap type" onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Code *"><Input value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></FormField>
          <FormField label="Unit"><Input value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></FormField>
          <FormField label="Name *" className="space-y-1.5 sm:col-span-2"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></FormField>
          <FormField label="Selling rate"><NumInput value={f.selling_rate} onChange={(n) => setF({ ...f, selling_rate: n })} /></FormField>
          <FormField label="Min stock"><NumInput value={f.min_stock} onChange={(n) => setF({ ...f, min_stock: n })} /></FormField>
        </div>
      </FormDialog>
    </>
  );
}

function MovementsTab({ canEdit }: { canEdit: boolean }) {
  const query = H.useMovements();
  const products = H.useProducts();
  const materials = H.useMaterials();
  const scrap = H.useScrapTypes();
  const create = H.useCreateMovement();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<T.MovementIn>({ item_kind: "material", item_id: "", movement_type: "ADJUST", quantity: 0, reference: "", reason: "", entry_date: todayIso() });
  const itemOptions =
    f.item_kind === "material"
      ? (materials.data ?? []).map((m) => ({ value: m.id, label: `${m.code} — ${m.name} (${formatNumber(m.stock, 2)})` }))
      : f.item_kind === "product"
        ? (products.data ?? []).map((m) => ({ value: m.id, label: `${m.code} — ${m.name} (${formatNumber(m.stock, 2)})` }))
        : (scrap.data ?? []).map((m) => ({ value: m.id, label: `${m.code} — ${m.name} (${formatNumber(m.stock, 2)})` }));
  const submit = async () => {
    if (!f.item_id || !f.reason) return;
    if (await runMutation(create.mutateAsync(f), "Stock movement posted")) setOpen(false);
  };
  return (
    <>
      <QueryTable
        query={query}
        rowKey={(r) => r.id}
        exportName="stock-movements"
        emptyTitle="No stock movements"
        toolbar={canEdit ? <Button size="sm" onClick={() => setOpen(true)}><SlidersHorizontal className="mr-1 h-4 w-4" /> Post movement</Button> : null}
        columns={[
          { key: "date", header: "Date", render: (r) => formatDate(r.entry_date), sortValue: (r) => r.entry_date },
          { key: "kind", header: "Kind", render: (r) => <span className="font-mono text-xs uppercase">{r.item_kind}</span>, searchValue: (r) => r.item_kind },
          { key: "item", header: "Item", render: (r) => r.item_name, searchValue: (r) => r.item_name, sortValue: (r) => r.item_name },
          { key: "type", header: "Type", render: (r) => <StatusBadge status={r.movement_type} />, searchValue: (r) => r.movement_type },
          { key: "qty", header: "Qty", className: "text-right", render: (r) => <span className={r.movement_type === "OUT" ? "tabular-nums text-destructive" : "tabular-nums"}>{r.movement_type === "OUT" ? "−" : ""}{formatNumber(r.quantity, 2)} {r.unit}</span> },
          { key: "bal", header: "Balance", className: "text-right", render: (r) => <span className="tabular-nums">{formatNumber(r.balance, 2)}</span> },
          { key: "ref", header: "Reference", render: (r) => <span className="font-mono text-xs">{r.reference || "—"}</span>, searchValue: (r) => r.reference },
          { key: "reason", header: "Reason", render: (r) => r.reason, hideable: true, searchValue: (r) => r.reason },
        ]}
      />
      <FormDialog open={open} onOpenChange={setOpen} title="Post stock movement" description="Manual receipts, issues and cycle-count adjustments." onSubmit={() => void submit()} pending={create.isPending}>
        <div className="grid gap-3 sm:grid-cols-2">
          <FormField label="Item kind">
            <SelectField value={f.item_kind} onChange={(v) => setF({ ...f, item_kind: v as T.ItemKind, item_id: "" })} options={[{ value: "material", label: "Raw material" }, { value: "product", label: "Product" }, { value: "scrap", label: "Scrap" }]} />
          </FormField>
          <FormField label="Movement type">
            <SelectField value={f.movement_type} onChange={(v) => setF({ ...f, movement_type: v as T.MovementType })} options={[{ value: "IN", label: "IN — receipt" }, { value: "OUT", label: "OUT — issue" }, { value: "ADJUST", label: "ADJUST — set balance" }]} />
          </FormField>
          <FormField label="Item *" className="space-y-1.5 sm:col-span-2"><SelectField value={f.item_id} onChange={(v) => setF({ ...f, item_id: v })} options={itemOptions} /></FormField>
          <FormField label="Quantity"><NumInput value={f.quantity} onChange={(n) => setF({ ...f, quantity: n })} /></FormField>
          <FormField label="Date"><Input type="date" value={f.entry_date ?? ""} onChange={(e) => setF({ ...f, entry_date: e.target.value || null })} /></FormField>
          <FormField label="Reference"><Input value={f.reference} onChange={(e) => setF({ ...f, reference: e.target.value })} /></FormField>
          <FormField label="Reason *"><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></FormField>
        </div>
      </FormDialog>
    </>
  );
}

function LocationsTab({ canEdit }: { canEdit: boolean }) {
  const plants = H.usePlants();
  const warehouses = H.useWarehouses();
  const createPlant = H.useCreatePlant();
  const createWh = H.useCreateWarehouse();
  const deletePlant = H.useDeletePlant();
  const deleteWh = H.useDeleteWarehouse();
  const [pOpen, setPOpen] = useState(false);
  const [wOpen, setWOpen] = useState(false);
  const [p, setP] = useState<T.PlantIn>({ code: "", name: "", location: "", active: true });
  const [w, setW] = useState<T.WarehouseIn>({ code: "", name: "", plant_id: "", active: true });
  const del = (onConfirm: () => void, name: string) => (
    <ConfirmAction destructive title={`Delete ${name}?`} description="This cannot be undone." confirmLabel="Delete" onConfirm={onConfirm}
      trigger={<Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></Button>} />
  );
  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Plants</h3>
        <QueryTable
          query={plants}
          rowKey={(r) => r.id}
          exportName="plants"
          emptyTitle="No plants"
          toolbar={canEdit ? <Button size="sm" onClick={() => setPOpen(true)}><Plus className="mr-1 h-4 w-4" /> Plant</Button> : null}
          columns={[
            { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code },
            { key: "name", header: "Name", render: (r) => r.name, searchValue: (r) => r.name },
            { key: "loc", header: "Location", render: (r) => r.location || "—" },
            { key: "a", header: "", className: "w-10", render: (r) => (canEdit ? del(() => void runMutation(deletePlant.mutateAsync(r.id), "Plant deleted"), r.name) : null) },
          ]}
        />
      </div>
      <div className="space-y-2">
        <h3 className="text-sm font-semibold">Warehouses</h3>
        <QueryTable
          query={warehouses}
          rowKey={(r) => r.id}
          exportName="warehouses"
          emptyTitle="No warehouses"
          toolbar={canEdit ? <Button size="sm" onClick={() => setWOpen(true)}><Plus className="mr-1 h-4 w-4" /> Warehouse</Button> : null}
          columns={[
            { key: "code", header: "Code", render: (r) => <span className="font-mono text-xs">{r.code}</span>, searchValue: (r) => r.code },
            { key: "name", header: "Name", render: (r) => r.name, searchValue: (r) => r.name },
            { key: "plant", header: "Plant", render: (r) => lookup(plants.data, r.plant_id, (x) => x.code) },
            { key: "a", header: "", className: "w-10", render: (r) => (canEdit ? del(() => void runMutation(deleteWh.mutateAsync(r.id), "Warehouse deleted"), r.name) : null) },
          ]}
        />
      </div>
      <FormDialog open={pOpen} onOpenChange={setPOpen} title="New plant" onSubmit={() => void runMutation(createPlant.mutateAsync(p), "Plant created").then((r) => r && setPOpen(false))} pending={createPlant.isPending}>
        <FormField label="Code *"><Input value={p.code} onChange={(e) => setP({ ...p, code: e.target.value })} /></FormField>
        <FormField label="Name *"><Input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} /></FormField>
        <FormField label="Location"><Input value={p.location} onChange={(e) => setP({ ...p, location: e.target.value })} /></FormField>
      </FormDialog>
      <FormDialog open={wOpen} onOpenChange={setWOpen} title="New warehouse" onSubmit={() => void runMutation(createWh.mutateAsync(w), "Warehouse created").then((r) => r && setWOpen(false))} pending={createWh.isPending}>
        <FormField label="Plant *"><SelectField value={w.plant_id} onChange={(v) => setW({ ...w, plant_id: v })} options={(plants.data ?? []).map((x) => ({ value: x.id, label: `${x.code} — ${x.name}` }))} /></FormField>
        <FormField label="Code *"><Input value={w.code} onChange={(e) => setW({ ...w, code: e.target.value })} /></FormField>
        <FormField label="Name *"><Input value={w.name} onChange={(e) => setW({ ...w, name: e.target.value })} /></FormField>
      </FormDialog>
    </div>
  );
}
