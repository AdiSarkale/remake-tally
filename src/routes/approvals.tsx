import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { CheckCircle2, ClipboardCheck, XCircle, Hourglass } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { StatusBadge } from "@/components/erp/DocBits";
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
  DialogTrigger,
} from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useErp } from "@/lib/erp/store";
import { useAuth } from "@/lib/erp/auth";
import { decideApproval, raiseApproval } from "@/lib/erp/ops";
import { dmy, inr, num } from "@/lib/erp/format";
import type { ApprovalRequest } from "@/lib/erp/ops-types";

export const Route = createFileRoute("/approvals")({
  head: () => ({
    meta: [
      { title: "Approval Workflow — NKCC ERP" },
      { name: "description", content: "Multi-stage digital approvals for purchase indents, leave, overtime, price changes, expenses and design releases." },
      { property: "og:title", content: "Approval Workflow — NKCC ERP" },
      { property: "og:description", content: "Route every request through the right desks with a full decision trail." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <ApprovalsPage />
    </AppShell>
  ),
});

const TYPES = ["Purchase Indent", "Leave", "Overtime", "Price Approval", "Expense", "Design Release"];
const ROLE_CHAINS: Record<string, string[]> = {
  "Purchase Indent": ["Store In-charge", "Purchase Head", "Management"],
  Leave: ["Supervisor", "HR"],
  Overtime: ["Supervisor", "HR", "Accounts"],
  "Price Approval": ["Sales Head", "Management"],
  Expense: ["Department Head", "Accounts"],
  "Design Release": ["Design Head", "Quality", "Production Head"],
};

function ApprovalsPage() {
  const approvals = useErp((s) => s.approvals);
  const { session } = useAuth();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ type: TYPES[0]!, subject: "", amount: "" });
  const [decide, setDecide] = useState<{ req: ApprovalRequest; action: "Approved" | "Rejected" } | null>(null);
  const [remarks, setRemarks] = useState("");

  const pending = approvals.filter((a) => a.status === "Pending");
  const approved = approvals.filter((a) => a.status === "Approved");
  const rejected = approvals.filter((a) => a.status === "Rejected");
  const pendingValue = pending.reduce((t, a) => t + a.amount, 0);

  function submit() {
    if (!form.subject.trim()) return toast.error("Subject is required");
    raiseApproval(
      {
        type: form.type,
        subject: form.subject.trim(),
        requester: session?.fullName ?? "System",
        amount: Number(form.amount) || 0,
        roles: ROLE_CHAINS[form.type] ?? ["Management"],
      },
      session?.username ?? "system",
    );
    setForm({ type: TYPES[0]!, subject: "", amount: "" });
    setOpen(false);
    toast.success("Approval request raised");
  }

  function confirmDecision() {
    if (!decide) return;
    decideApproval(decide.req.id, decide.action, session?.fullName ?? "System", remarks);
    toast.success(`Stage ${decide.action.toLowerCase()}`);
    setDecide(null);
    setRemarks("");
  }

  return (
    <>
      <PageHeader
        title="Approval Workflow"
        subtitle="Multi-stage digital authorisation with a permanent decision trail."
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">Raise request</Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Raise approval request</DialogTitle>
                <DialogDescription>The approval chain is set automatically by request type.</DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-2">
                <div className="grid gap-2">
                  <Label>Type</Label>
                  <Select value={form.type} onValueChange={(v) => setForm({ ...form, type: v })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {t}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-muted-foreground text-xs">Chain: {(ROLE_CHAINS[form.type] ?? []).join(" → ")}</p>
                </div>
                <div className="grid gap-2">
                  <Label>Subject</Label>
                  <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Indent for 500 kg kraft paper" />
                </div>
                <div className="grid gap-2">
                  <Label>Amount</Label>
                  <Input type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
                </div>
              </div>
              <DialogFooter>
                <Button onClick={submit}>Submit for approval</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        }
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Pending" value={num(pending.length)} tone={pending.length ? "warning" : "success"} icon={<Hourglass className="h-4 w-4" />} />
        <StatCard label="Pending value" value={inr(pendingValue)} tone="primary" icon={<ClipboardCheck className="h-4 w-4" />} />
        <StatCard label="Approved" value={num(approved.length)} tone="success" icon={<CheckCircle2 className="h-4 w-4" />} />
        <StatCard label="Rejected" value={num(rejected.length)} tone={rejected.length ? "destructive" : "success"} icon={<XCircle className="h-4 w-4" />} />
      </div>

      <DataTable
        rows={approvals}
        rowKey={(a) => a.id}
        searchable={(a) => `${a.refNo} ${a.type} ${a.subject} ${a.requester}`}
        columns={[
          { key: "refNo", header: "Ref", value: (a) => a.refNo },
          { key: "date", header: "Date", value: (a) => a.date, render: (a) => dmy(a.date) },
          { key: "type", header: "Type", value: (a) => a.type },
          { key: "subject", header: "Subject", value: (a) => a.subject, render: (a) => <span className="block max-w-64 truncate">{a.subject}</span> },
          { key: "requester", header: "Requester", value: (a) => a.requester },
          { key: "amount", header: "Amount", align: "right", value: (a) => a.amount, render: (a) => <span className="num">{inr(a.amount)}</span> },
          {
            key: "chain",
            header: "Approval chain",
            value: (a) => a.currentStage,
            render: (a) => (
              <div className="flex flex-wrap items-center gap-1">
                {a.stages.map((st, i) => (
                  <span
                    key={st.role + i}
                    title={st.by ? `${st.decision} by ${st.by} on ${st.on}${st.remarks ? ` — ${st.remarks}` : ""}` : `Pending with ${st.role}`}
                    className={
                      "rounded border px-1.5 py-0.5 text-[11px] " +
                      (st.decision === "Approved"
                        ? "border-success/40 text-success"
                        : st.decision === "Rejected"
                          ? "border-destructive/40 text-destructive"
                          : i === a.currentStage && a.status === "Pending"
                            ? "border-primary/50 text-primary"
                            : "border-border text-muted-foreground")
                    }
                  >
                    {st.role}
                  </span>
                ))}
              </div>
            ),
          },
          { key: "status", header: "Status", value: (a) => a.status, render: (a) => <StatusBadge status={a.status} /> },
          {
            key: "act",
            header: "",
            value: () => "",
            render: (a) =>
              a.status === "Pending" ? (
                <div className="flex justify-end gap-1">
                  <Button size="sm" variant="outline" onClick={() => setDecide({ req: a, action: "Approved" })}>
                    Approve
                  </Button>
                  <Button size="sm" variant="ghost" className="text-destructive" onClick={() => setDecide({ req: a, action: "Rejected" })}>
                    Reject
                  </Button>
                </div>
              ) : null,
            align: "right",
          },
        ]}
      />

      <Dialog open={!!decide} onOpenChange={(v) => !v && setDecide(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{decide?.action === "Approved" ? "Approve" : "Reject"} {decide?.req.refNo}</DialogTitle>
            <DialogDescription>
              {decide?.req.subject} — stage {(decide?.req.currentStage ?? 0) + 1} of {decide?.req.stages.length}
              {decide?.req.stages[decide.req.currentStage]?.role ? ` (${decide.req.stages[decide.req.currentStage]!.role})` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 py-2">
            <Label>Remarks</Label>
            <Textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="Optional note recorded in the trail" />
          </div>
          <DialogFooter>
            <Button variant={decide?.action === "Rejected" ? "destructive" : "default"} onClick={confirmDecision}>
              Confirm {decide?.action.toLowerCase()}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
