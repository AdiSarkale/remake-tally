import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowLeftRight, Plus } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Field } from "@/components/erp/DocBits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { today, useErp } from "@/lib/erp/store";
import { createTransfer, nextDocNo, whQty } from "@/lib/erp/docs";
import { dmy, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";
import type { MaterialTransfer } from "@/lib/erp/doc-types";

export const Route = createFileRoute("/transfers")({
  head: () => ({
    meta: [
      { title: "Interplant Transfers — MiniTally ERP" },
      { name: "description", content: "Move material between plants and warehouses with batch, vehicle and quantity tracking." },
      { property: "og:title", content: "Interplant Transfers — MiniTally ERP" },
      { property: "og:description", content: "Multi-plant stock movement for MiniTally ERP." },
    ],
  }),
  component: () => (
    <AppShell>
      <TransfersPage />
    </AppShell>
  ),
});

function TransfersPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    date: today(),
    sourceId: state.warehouses[0]?.id ?? "",
    destId: state.warehouses[1]?.id ?? "",
    itemKind: "material" as MaterialTransfer["itemKind"],
    itemId: "",
    quantity: "",
    batchNo: "",
    vehicle: "",
    remarks: "",
  });

  const items = form.itemKind === "product" ? state.products : form.itemKind === "material" ? state.materials : state.scrapTypes;

  const submit = () => {
    try {
      const no = createTransfer(
        { ...form, quantity: Number(form.quantity) },
        session?.username ?? "system",
      );
      toast.success(`${no} posted — stock moved between plants`);
      setOpen(false);
      setForm({ ...form, itemId: "", quantity: "", batchNo: "" });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Interplant Transfers"
        subtitle="Stock moves between plants — total company stock stays the same, location changes."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New transfer
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Transfers" value={num(state.transfers.length)} tone="primary" icon={<ArrowLeftRight className="h-4 w-4" />} />
        <StatCard label="Plants / warehouses" value={num(state.warehouses.length)} />
        <StatCard label="Quantity moved" value={num(state.transfers.reduce((t, x) => t + x.quantity, 0), 1)} />
        <StatCard label="This month" value={num(state.transfers.filter((t) => t.date.startsWith(today().slice(0, 7))).length)} tone="success" />
      </div>

      <div className="panel mb-4 overflow-x-auto p-4">
        <h2 className="mb-3 text-sm font-semibold">Stock by plant</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted-foreground border-b text-left text-[11px] tracking-wider uppercase">
              <th className="py-2">Item</th>
              {state.warehouses.map((w) => (
                <th key={w.id} className="py-2 text-right">
                  {w.code}
                </th>
              ))}
              <th className="py-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {[...state.products, ...state.materials].map((i) => (
              <tr key={i.id} className="border-b last:border-0">
                <td className="py-2">{i.name}</td>
                {state.warehouses.map((w) => (
                  <td key={w.id} className="num py-2 text-right">
                    {num(whQty(state, i.id, w.id), 1)}
                  </td>
                ))}
                <td className="num py-2 text-right font-medium">
                  {num(i.stock, 1)} {i.unit}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DataTable
        rows={state.transfers}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.transferNo} ${r.itemName} ${r.sourceName} ${r.destName} ${r.batchNo} ${r.vehicle}`}
        columns={[
          { key: "no", header: "Transfer No", value: (r) => r.transferNo, render: (r) => <span className="num font-medium">{r.transferNo}</span> },
          { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "item", header: "Item", value: (r) => r.itemName },
          { key: "qty", header: "Qty", align: "right", value: (r) => r.quantity, render: (r) => <span className="num">{num(r.quantity, 2)} {r.unit}</span> },
          { key: "from", header: "From", value: (r) => r.sourceName },
          { key: "to", header: "To", value: (r) => r.destName },
          { key: "batch", header: "Batch", value: (r) => r.batchNo, render: (r) => <span className="num text-xs">{r.batchNo || "—"}</span> },
          { key: "vehicle", header: "Vehicle", value: (r) => r.vehicle, render: (r) => <span className="num text-xs">{r.vehicle || "—"}</span> },
          { key: "remarks", header: "Remarks", className: "text-muted-foreground text-xs", value: (r) => r.remarks },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>New interplant transfer</DialogTitle>
            <DialogDescription>Numbered {nextDocNo(state, "TR", form.date)} on save.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Transfer date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Vehicle">
              <Input value={form.vehicle} onChange={(e) => setForm({ ...form, vehicle: e.target.value })} />
            </Field>
            <Field label="Source plant">
              <Select value={form.sourceId} onValueChange={(v) => setForm({ ...form, sourceId: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {state.warehouses.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Destination plant">
              <Select value={form.destId} onValueChange={(v) => setForm({ ...form, destId: v })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {state.warehouses.map((w) => (
                    <SelectItem key={w.id} value={w.id}>
                      {w.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Item type">
              <Select value={form.itemKind} onValueChange={(v) => setForm({ ...form, itemKind: v as MaterialTransfer["itemKind"], itemId: "" })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="material">Raw material</SelectItem>
                  <SelectItem value="product">Finished good</SelectItem>
                  <SelectItem value="scrap">Scrap</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label="Quantity">
              <Input type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
            </Field>
            <Field label="Item" full>
              <Select value={form.itemId} onValueChange={(v) => setForm({ ...form, itemId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select item" />
                </SelectTrigger>
                <SelectContent>
                  {items.map((i) => (
                    <SelectItem key={i.id} value={i.id}>
                      {i.name} · at source {num(whQty(state, i.id, form.sourceId), 1)} {i.unit}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Batch number">
              <Input value={form.batchNo} onChange={(e) => setForm({ ...form, batchNo: e.target.value })} />
            </Field>
            <Field label="Remarks" full>
              <Textarea rows={2} value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Post transfer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
