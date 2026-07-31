import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Hammer, Plus } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Field, StatusBadge } from "@/components/erp/DocBits";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
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
import { createJobWorkOut, defaultWarehouse, docStats, nextDocNo, receiveJobWork } from "@/lib/erp/docs";
import { dmy, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";
import type { JobWork } from "@/lib/erp/doc-types";

export const Route = createFileRoute("/jobwork")({
  head: () => ({
    meta: [
      { title: "Job Work — MiniTally ERP" },
      { name: "description", content: "Send material to processing vendors and receive finished goods and scrap back into stock." },
      { property: "og:title", content: "Job Work — MiniTally ERP" },
      { property: "og:description", content: "Job work out and in with material-at-vendor tracking." },
    ],
  }),
  component: () => (
    <AppShell>
      <JobWorkPage />
    </AppShell>
  ),
});

function JobWorkPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const user = session?.username ?? "system";
  const [open, setOpen] = useState(false);
  const [receiving, setReceiving] = useState<JobWork | null>(null);
  const [form, setForm] = useState({
    date: today(),
    vendorId: "",
    process: "",
    materialId: "",
    quantity: "",
    expectedDate: today(),
    warehouseId: defaultWarehouse(state),
    remarks: "",
  });
  const [rec, setRec] = useState({ date: today(), productId: "", productQty: "", scrapTypeId: "", scrapQty: "", remarks: "", close: false });

  const stats = docStats(state);

  const submit = () => {
    try {
      const no = createJobWorkOut({ ...form, quantity: Number(form.quantity) }, user);
      toast.success(`${no} issued — material marked at vendor`);
      setOpen(false);
      setForm({ ...form, materialId: "", quantity: "", process: "" });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const submitReceipt = () => {
    if (!receiving) return;
    try {
      receiveJobWork(
        receiving.id,
        {
          date: rec.date,
          productId: rec.productId,
          productQty: Number(rec.productQty),
          scrapTypeId: rec.scrapTypeId,
          scrapQty: Number(rec.scrapQty || 0),
          remarks: rec.remarks,
          close: rec.close,
        },
        user,
      );
      toast.success("Job work receipt posted — finished stock and scrap updated");
      setReceiving(null);
      setRec({ ...rec, productId: "", productQty: "", scrapQty: "", close: false });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Job Work"
        subtitle="Material sent out for processing stays visible as 'at vendor' until it returns."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New job work out
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Open at vendor" value={num(stats.atVendor)} tone="warning" icon={<Hammer className="h-4 w-4" />} />
        <StatCard label="Quantity at vendor" value={num(state.jobWorks.filter((j) => j.status !== "Closed").reduce((t, j) => t + j.quantity, 0), 1)} />
        <StatCard label="Receipts booked" value={num(state.jobWorks.reduce((t, j) => t + j.receipts.length, 0))} tone="success" />
        <StatCard label="Closed orders" value={num(state.jobWorks.filter((j) => j.status === "Closed").length)} />
      </div>

      <DataTable
        rows={state.jobWorks}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.jwNo} ${r.vendorName} ${r.process} ${r.materialName} ${r.status}`}
        columns={[
          { key: "no", header: "JW No", value: (r) => r.jwNo, render: (r) => <span className="num font-medium">{r.jwNo}</span> },
          { key: "date", header: "Sent on", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "vendor", header: "Vendor", value: (r) => r.vendorName },
          { key: "process", header: "Process", value: (r) => r.process },
          { key: "material", header: "Material out", value: (r) => r.materialName, render: (r) => <span>{r.materialName} · <span className="num">{num(r.quantity, 1)} {r.unit}</span></span> },
          {
            key: "received",
            header: "Received back",
            align: "right",
            render: (r) => (
              <span className="num text-xs">
                {num(r.receipts.reduce((t, x) => t + x.productQty, 0))} pcs · {num(r.receipts.reduce((t, x) => t + x.scrapQty, 0), 1)} scrap
              </span>
            ),
          },
          { key: "expected", header: "Due", value: (r) => r.expectedDate, render: (r) => <span className="num">{dmy(r.expectedDate)}</span> },
          { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (r) =>
              r.status === "Closed" ? null : (
                <Button size="sm" onClick={() => { setReceiving(r); setRec((x) => ({ ...x, date: today() })); }}>
                  Receive
                </Button>
              ),
          },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Job work out</DialogTitle>
            <DialogDescription>Numbered {nextDocNo(state, "JW", form.date)} — material leaves stock on save.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Vendor" full>
              <Select value={form.vendorId} onValueChange={(v) => setForm({ ...form, vendorId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select vendor" />
                </SelectTrigger>
                <SelectContent>
                  {state.suppliers.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Process">
              <Input value={form.process} onChange={(e) => setForm({ ...form, process: e.target.value })} placeholder="Zinc plating" />
            </Field>
            <Field label="Send date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Material" full>
              <Select value={form.materialId} onValueChange={(v) => setForm({ ...form, materialId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select material" />
                </SelectTrigger>
                <SelectContent>
                  {state.materials.map((m) => (
                    <SelectItem key={m.id} value={m.id}>
                      {m.name} · stock {num(m.stock, 1)} {m.unit}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Quantity">
              <Input type="number" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
            </Field>
            <Field label="Expected back">
              <Input type="date" value={form.expectedDate} onChange={(e) => setForm({ ...form, expectedDate: e.target.value })} />
            </Field>
            <Field label="Issue from">
              <Select value={form.warehouseId} onValueChange={(v) => setForm({ ...form, warehouseId: v })}>
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
            <Field label="Remarks" full>
              <Textarea rows={2} value={form.remarks} onChange={(e) => setForm({ ...form, remarks: e.target.value })} />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Send to vendor</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!receiving} onOpenChange={(o) => !o && setReceiving(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Job work in — {receiving?.jwNo}</DialogTitle>
            <DialogDescription>Finished goods increase and any scrap returned is booked to scrap stock.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Receipt date">
              <Input type="date" value={rec.date} onChange={(e) => setRec({ ...rec, date: e.target.value })} />
            </Field>
            <Field label="Finished quantity">
              <Input type="number" value={rec.productQty} onChange={(e) => setRec({ ...rec, productQty: e.target.value })} />
            </Field>
            <Field label="Finished product" full>
              <Select value={rec.productId} onValueChange={(v) => setRec({ ...rec, productId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Select product" />
                </SelectTrigger>
                <SelectContent>
                  {state.products.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Scrap type">
              <Select value={rec.scrapTypeId} onValueChange={(v) => setRec({ ...rec, scrapTypeId: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="Optional" />
                </SelectTrigger>
                <SelectContent>
                  {state.scrapTypes.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Scrap quantity">
              <Input type="number" value={rec.scrapQty} onChange={(e) => setRec({ ...rec, scrapQty: e.target.value })} />
            </Field>
            <Field label="Remarks" full>
              <Textarea rows={2} value={rec.remarks} onChange={(e) => setRec({ ...rec, remarks: e.target.value })} />
            </Field>
          </div>
          <label className="mt-2 flex items-center gap-2 text-sm">
            <Checkbox checked={rec.close} onCheckedChange={(c) => setRec({ ...rec, close: !!c })} />
            Close this job work order
          </label>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReceiving(null)}>
              Cancel
            </Button>
            <Button onClick={submitReceipt}>Post receipt</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
