import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Clock, MapPin, PackageCheck, Plus, Truck } from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Field, StatusBadge } from "@/components/erp/DocBits";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  createDispatch,
  getDeliveries,
  getDispatches,
  getNextDispatchNumber,
  updateDispatch,
  type DeliveryData,
  type DispatchData,
  type DispatchStatus,
} from "@/lib/api";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/dispatch")({
  head: () => ({
    meta: [
      { title: "Dispatch & Logistics — MiniTally ERP" },
      { name: "description", content: "Vehicle allocation, transporter and LR details, in-transit visibility and proof of delivery." },
    ],
  }),
  component: () => (
    <AppShell>
      <DispatchPage />
    </AppShell>
  ),
});

function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function DispatchPage() {
  const [dispatches, setDispatches] = useState<DispatchData[]>([]);
  const [deliveries, setDeliveries] = useState<DeliveryData[]>([]);
  const [nextNo, setNextNo] = useState("DSP0001");
  const [loading, setLoading] = useState(true);
  const [openCreate, setOpenCreate] = useState(false);
  const [edit, setEdit] = useState<DispatchData | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    dispatch_date: isoToday(),
    delivery_id: "",
    transporter: "",
    vehicle_no: "",
    driver_name: "",
    driver_phone: "",
    lr_number: "",
    status: "Planned" as DispatchStatus,
    delivered_on: "",
    pod_ref: "",
  });

  async function load() {
    try {
      setLoading(true);
      const [d, dns, n] = await Promise.all([
        getDispatches(),
        getDeliveries(),
        getNextDispatchNumber(),
      ]);
      setDispatches(d);
      setDeliveries(dns);
      setNextNo(n.dispatch_no);
    } catch (e) {
      toast.error((e as Error).message || "Failed to load dispatch data");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const inTransit = useMemo(() => dispatches.filter((d) => d.status === "In Transit").length, [dispatches]);
  const delivered = useMemo(() => dispatches.filter((d) => d.status === "Delivered").length, [dispatches]);
  const delayed = useMemo(() => dispatches.filter((d) => d.status === "Delayed").length, [dispatches]);
  const podPending = useMemo(() => dispatches.filter((d) => d.status === "Delivered" && !d.pod_ref).length, [dispatches]);

  function resetForm() {
    setForm({
      dispatch_date: isoToday(),
      delivery_id: "",
      transporter: "",
      vehicle_no: "",
      driver_name: "",
      driver_phone: "",
      lr_number: "",
      status: "Planned",
      delivered_on: "",
      pod_ref: "",
    });
  }

  function openEdit(row: DispatchData) {
    setEdit(row);
    setForm({
      dispatch_date: row.dispatch_date,
      delivery_id: row.delivery_id ?? "",
      transporter: row.transporter,
      vehicle_no: row.vehicle_no,
      driver_name: row.driver_name,
      driver_phone: row.driver_phone,
      lr_number: row.lr_number,
      status: row.status,
      delivered_on: row.delivered_on ?? "",
      pod_ref: row.pod_ref,
    });
  }

  async function saveCreate() {
    if (!form.delivery_id) return toast.error("Select a delivery note");
    if (!form.transporter.trim()) return toast.error("Transporter is required");
    if (!form.vehicle_no.trim()) return toast.error("Vehicle number is required");
    if (form.status === "Delivered" && !form.delivered_on) return toast.error("Delivered on is required");

    try {
      setSaving(true);
      await createDispatch({
        dispatch_date: form.dispatch_date,
        delivery_id: form.delivery_id,
        transporter: form.transporter,
        vehicle_no: form.vehicle_no,
        driver_name: form.driver_name,
        driver_phone: form.driver_phone,
        lr_number: form.lr_number,
        status: form.status,
        delivered_on: form.delivered_on || null,
        pod_ref: form.pod_ref,
      });
      toast.success(`${nextNo} created`);
      setOpenCreate(false);
      resetForm();
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to create dispatch");
    } finally {
      setSaving(false);
    }
  }

  async function saveEdit() {
    if (!edit) return;
    if (form.status === "Delivered" && !form.delivered_on) return toast.error("Delivered on is required");
    try {
      setSaving(true);
      await updateDispatch(edit.id, {
        transporter: form.transporter,
        vehicle_no: form.vehicle_no,
        driver_name: form.driver_name,
        driver_phone: form.driver_phone,
        lr_number: form.lr_number,
        status: form.status,
        delivered_on: form.delivered_on || null,
        pod_ref: form.pod_ref,
      });
      toast.success(`${edit.dispatch_no} updated`);
      setEdit(null);
      await load();
    } catch (e) {
      toast.error((e as Error).message || "Failed to update dispatch");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Dispatch & Logistics"
        subtitle="Vehicle allocation, transporter and LR details, in-transit visibility and proof of delivery."
        actions={
          <Button onClick={() => { resetForm(); setOpenCreate(true); }}>
            <Plus className="mr-1 h-4 w-4" /> New dispatch
          </Button>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="In transit" value={num(inTransit)} tone="primary" icon={<Truck className="h-4 w-4" />} />
        <StatCard label="Delivered" value={num(delivered)} tone="success" icon={<PackageCheck className="h-4 w-4" />} />
        <StatCard label="Delayed" value={num(delayed)} tone={delayed ? "destructive" : "success"} icon={<Clock className="h-4 w-4" />} />
        <StatCard label="POD pending" value={num(podPending)} tone={podPending ? "warning" : "success"} hint="Delivered without proof" icon={<MapPin className="h-4 w-4" />} />
      </div>

      <DataTable
        rows={dispatches}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.dispatch_no} ${r.delivery_no} ${r.customer_name} ${r.vehicle_no} ${r.transporter} ${r.lr_number}`}
        columns={[
          { key: "no", header: "Dispatch", value: (r) => r.dispatch_no, render: (r) => <span className="num font-medium">{r.dispatch_no}</span> },
          { key: "date", header: "Date", value: (r) => r.dispatch_date, render: (r) => <span className="num">{dmy(r.dispatch_date)}</span> },
          { key: "dn", header: "DN", value: (r) => r.delivery_no },
          { key: "customer", header: "Customer", value: (r) => r.customer_name },
          { key: "vehicle", header: "Vehicle / driver", value: (r) => r.vehicle_no, render: (r) => <div className="leading-tight"><div className="num">{r.vehicle_no || "—"}</div><div className="text-muted-foreground text-xs">{r.driver_name || "—"}</div></div> },
          { key: "transporter", header: "Transporter", value: (r) => r.transporter },
          { key: "lr", header: "LR No", value: (r) => r.lr_number },
          { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
          { key: "pod", header: "POD", value: (r) => r.pod_ref, render: (r) => r.pod_ref ? <span className="text-xs">{r.pod_ref}</span> : <span className="text-muted-foreground text-xs">—</span> },
          { key: "edit", header: "", align: "right", render: (r) => <Button size="sm" variant="outline" onClick={() => openEdit(r)}>Edit</Button> },
        ]}
      />

      {loading && <div className="py-8 text-center text-sm text-muted-foreground">Loading dispatches...</div>}

      <Dialog open={openCreate} onOpenChange={setOpenCreate}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>New dispatch</DialogTitle>
            <DialogDescription>Dispatch number {nextNo}</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Dispatch date"><Input type="date" value={form.dispatch_date} onChange={(e) => setForm({ ...form, dispatch_date: e.target.value })} /></Field>
            <Field label="Delivery note"><Select value={form.delivery_id} onValueChange={(v) => setForm({ ...form, delivery_id: v })}><SelectTrigger><SelectValue placeholder="Select delivery note" /></SelectTrigger><SelectContent>{deliveries.filter((d) => !dispatches.some((x) => x.delivery_id === d.id)).map((d) => <SelectItem key={d.id} value={d.id}>{d.delivery_no} · {d.customer_name}</SelectItem>)}</SelectContent></Select></Field>
            <Field label="Transporter"><Input value={form.transporter} onChange={(e) => setForm({ ...form, transporter: e.target.value })} /></Field>
            <Field label="Vehicle no."><Input value={form.vehicle_no} onChange={(e) => setForm({ ...form, vehicle_no: e.target.value })} /></Field>
            <Field label="Driver name"><Input value={form.driver_name} onChange={(e) => setForm({ ...form, driver_name: e.target.value })} /></Field>
            <Field label="Driver phone"><Input value={form.driver_phone} onChange={(e) => setForm({ ...form, driver_phone: e.target.value })} /></Field>
            <Field label="LR number"><Input value={form.lr_number} onChange={(e) => setForm({ ...form, lr_number: e.target.value })} /></Field>
            <Field label="Status"><Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v as DispatchStatus })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["Planned", "Loading", "In Transit", "Delivered", "Delayed"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></Field>
            <Field label="Delivered on"><Input type="date" value={form.delivered_on} onChange={(e) => setForm({ ...form, delivered_on: e.target.value })} /></Field>
            <Field label="POD reference" full><Input value={form.pod_ref} onChange={(e) => setForm({ ...form, pod_ref: e.target.value })} /></Field>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setOpenCreate(false)}>Cancel</Button><Button disabled={saving} onClick={() => void saveCreate()}>{saving ? "Saving..." : "Create dispatch"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(edit)} onOpenChange={(v) => !v && setEdit(null)}>
        <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader><DialogTitle>Edit {edit?.dispatch_no}</DialogTitle><DialogDescription>Update logistics and POD information.</DialogDescription></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Transporter"><Input value={form.transporter} onChange={(e) => setForm({ ...form, transporter: e.target.value })} /></Field>
            <Field label="Vehicle no."><Input value={form.vehicle_no} onChange={(e) => setForm({ ...form, vehicle_no: e.target.value })} /></Field>
            <Field label="Driver name"><Input value={form.driver_name} onChange={(e) => setForm({ ...form, driver_name: e.target.value })} /></Field>
            <Field label="Driver phone"><Input value={form.driver_phone} onChange={(e) => setForm({ ...form, driver_phone: e.target.value })} /></Field>
            <Field label="LR number"><Input value={form.lr_number} onChange={(e) => setForm({ ...form, lr_number: e.target.value })} /></Field>
            <Field label="Status"><Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v as DispatchStatus })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent>{["Planned", "Loading", "In Transit", "Delivered", "Delayed"].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent></Select></Field>
            <Field label="Delivered on"><Input type="date" value={form.delivered_on} onChange={(e) => setForm({ ...form, delivered_on: e.target.value })} /></Field>
            <Field label="POD reference" full><Input value={form.pod_ref} onChange={(e) => setForm({ ...form, pod_ref: e.target.value })} /></Field>
          </div>
          <DialogFooter><Button variant="outline" onClick={() => setEdit(null)}>Cancel</Button><Button disabled={saving} onClick={() => void saveEdit()}>{saving ? "Saving..." : "Save changes"}</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
