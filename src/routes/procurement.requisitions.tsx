import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Check, ClipboardList, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { StatusBadge, DocTrail, Field } from "@/components/erp/DocBits";
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
import { createRequisition, docStats, nextDocNo, setPrStatus } from "@/lib/erp/docs";
import { dmy, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";
import type { PurchaseRequisition } from "@/lib/erp/doc-types";

export const Route = createFileRoute("/procurement/requisitions")({
  head: () => ({
    meta: [
      { title: "Purchase Requisitions — MiniTally ERP" },
      {
        name: "description",
        content: "Raise, approve and track material purchase requisitions before converting them into purchase orders.",
      },
      { property: "og:title", content: "Purchase Requisitions — MiniTally ERP" },
      { property: "og:description", content: "Approve material requests and convert them into purchase orders." },
    ],
  }),
  component: () => (
    <AppShell>
      <RequisitionsPage />
    </AppShell>
  ),
});

const PRIORITIES: PurchaseRequisition["priority"][] = ["Low", "Normal", "High", "Urgent"];

function RequisitionsPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState<string>("all");
  const [form, setForm] = useState({
    date: today(),
    department: "",
    requester: "",
    materialId: "",
    quantity: "",
    priority: "Normal" as PurchaseRequisition["priority"],
    requiredDate: today(),
    reason: "",
  });

  const stats = docStats(state);
  const rows = state.requisitions.filter((r) => filter === "all" || r.status === filter);

  const submit = () => {
    try {
      const prNo = createRequisition(
        {
          date: form.date,
          department: form.department.trim(),
          requester: form.requester.trim(),
          materialId: form.materialId,
          quantity: Number(form.quantity),
          priority: form.priority,
          requiredDate: form.requiredDate,
          reason: form.reason.trim(),
        },
        session?.username ?? "system",
      );
      toast.success(`${prNo} raised`);
      setOpen(false);
      setForm({ ...form, materialId: "", quantity: "", reason: "" });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const act = (id: string, status: PurchaseRequisition["status"]) => {
    try {
      setPrStatus(id, status, session?.username ?? "system");
      toast.success(`Requisition ${status.toLowerCase()}`);
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <>
      <PageHeader
        title="Purchase Requisitions"
        subtitle="Material requests from the shop floor, approved before any purchase order is raised."
        actions={
          <Button onClick={() => setOpen(true)}>
            <Plus className="mr-1 h-4 w-4" /> New requisition
          </Button>
        }
      />

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Pending approval" value={num(stats.openPrs)} tone="warning" icon={<ClipboardList className="h-4 w-4" />} />
        <StatCard label="Approved, not ordered" value={num(stats.approvedPrs)} tone="primary" />
        <StatCard label="Converted to PO" value={num(state.requisitions.filter((r) => r.status === "Converted to PO").length)} tone="success" />
        <StatCard label="Total requisitions" value={num(state.requisitions.length)} />
      </div>

      <DataTable
        rows={rows}
        rowKey={(r) => r.id}
        searchable={(r) => `${r.prNo} ${r.materialName} ${r.department} ${r.requester} ${r.reason} ${r.status}`}
        filters={
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-[190px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="Pending">Pending</SelectItem>
              <SelectItem value="Approved">Approved</SelectItem>
              <SelectItem value="Rejected">Rejected</SelectItem>
              <SelectItem value="Converted to PO">Converted to PO</SelectItem>
            </SelectContent>
          </Select>
        }
        columns={[
          { key: "prNo", header: "PR No", value: (r) => r.prNo, render: (r) => <span className="num font-medium">{r.prNo}</span> },
          { key: "date", header: "Date", value: (r) => r.date, render: (r) => <span className="num">{dmy(r.date)}</span> },
          { key: "material", header: "Material", value: (r) => r.materialName },
          {
            key: "qty",
            header: "Qty",
            align: "right",
            value: (r) => r.quantity,
            render: (r) => (
              <span className="num">
                {num(r.quantity, 2)} {r.unit}
              </span>
            ),
          },
          { key: "dept", header: "Department", value: (r) => r.department },
          { key: "priority", header: "Priority", value: (r) => r.priority, render: (r) => <StatusBadge status={r.priority === "Urgent" ? "Rejected" : r.priority === "High" ? "Sent" : "Open"} /> },
          { key: "required", header: "Required by", value: (r) => r.requiredDate, render: (r) => <span className="num">{dmy(r.requiredDate)}</span> },
          { key: "status", header: "Status", value: (r) => r.status, render: (r) => <StatusBadge status={r.status} /> },
          { key: "link", header: "Trail", render: (r) => <DocTrail steps={[r.prNo, r.poNo]} /> },
          {
            key: "actions",
            header: "",
            align: "right",
            render: (r) =>
              r.status === "Pending" ? (
                <div className="flex justify-end gap-1">
                  <Button size="sm" variant="outline" onClick={() => act(r.id, "Approved")}>
                    <Check className="mr-1 h-3.5 w-3.5" /> Approve
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => act(r.id, "Rejected")}>
                    <X className="text-destructive h-3.5 w-3.5" />
                  </Button>
                </div>
              ) : null,
          },
        ]}
      />

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>New purchase requisition</DialogTitle>
            <DialogDescription>
              Will be numbered {nextDocNo(state, "PR", form.date)} once saved.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Request date">
              <Input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
            </Field>
            <Field label="Required by">
              <Input type="date" value={form.requiredDate} onChange={(e) => setForm({ ...form, requiredDate: e.target.value })} />
            </Field>
            <Field label="Department">
              <Input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} placeholder="Machine Shop" />
            </Field>
            <Field label="Requester">
              <Input value={form.requester} onChange={(e) => setForm({ ...form, requester: e.target.value })} placeholder={session?.fullName ?? ""} />
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
            <Field label="Priority">
              <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v as PurchaseRequisition["priority"] })}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PRIORITIES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Reason" full>
              <Textarea rows={3} value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={submit}>Raise requisition</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
