import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RotateCcw, Save } from "lucide-react";
import { toast } from "sonner";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader } from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { logAudit, resetDemoData, update, useErp } from "@/lib/erp/store";
import { useAuth } from "@/lib/erp/auth";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings — MiniTally ERP" },
      {
        name: "description",
        content: "Company profile, invoice numbering, financial year, users and the system audit trail.",
      },
      { property: "og:title", content: "Settings — MiniTally ERP" },
      { property: "og:description", content: "Company profile, users and audit trail for MiniTally ERP." },
    ],
  }),
  component: () => (
    <AppShell>
      <SettingsPage />
    </AppShell>
  ),
});

function SettingsPage() {
  const state = useErp((s) => s);
  const { session } = useAuth();
  const [form, setForm] = useState(state.settings);

  const save = () => {
    if (!form.name.trim()) {
      toast.error("Company name is required");
      return;
    }
    update((s) => {
      s.settings = { ...form };
      logAudit(s, session?.username ?? "system", "UPDATE", "settings", "Company profile updated");
      return s;
    });
    toast.success("Settings saved");
  };

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Company profile, users and the immutable audit trail."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => {
                resetDemoData();
                toast.success("Demo data restored");
              }}
            >
              <RotateCcw className="mr-1 h-4 w-4" /> Reset demo data
            </Button>
            <Button onClick={save}>
              <Save className="mr-1 h-4 w-4" /> Save changes
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="panel p-4">
          <h2 className="mb-4 text-sm font-semibold">Company profile</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label className="mb-1.5 block text-xs">Company name</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">GST number</Label>
              <Input value={form.gstNumber} onChange={(e) => setForm({ ...form, gstNumber: e.target.value })} />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Financial year</Label>
              <Input
                value={form.financialYear}
                onChange={(e) => setForm({ ...form, financialYear: e.target.value })}
              />
            </div>
            <div>
              <Label className="mb-1.5 block text-xs">Invoice prefix</Label>
              <Input
                value={form.invoicePrefix}
                onChange={(e) => setForm({ ...form, invoicePrefix: e.target.value })}
              />
            </div>
            <div className="sm:col-span-2">
              <Label className="mb-1.5 block text-xs">Registered address</Label>
              <Textarea
                rows={3}
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
              />
            </div>
          </div>
        </div>

        <div className="panel p-4">
          <h2 className="mb-4 text-sm font-semibold">Users & roles</h2>
          <div className="divide-border divide-y">
            {state.users.map((u) => (
              <div key={u.id} className="flex items-center justify-between py-2.5">
                <div>
                  <p className="text-sm font-medium">{u.fullName}</p>
                  <p className="text-muted-foreground text-xs">@{u.username}</p>
                </div>
                <Badge variant={u.role === "Admin" ? "default" : "secondary"}>{u.role}</Badge>
              </div>
            ))}
          </div>
          <p className="text-muted-foreground mt-4 text-xs">
            Roles map to module access: Admin (all), Accountant (masters, inventory, reports), Operator (production,
            scrap, inventory).
          </p>
        </div>
      </div>

      <div className="mt-4">
        <h2 className="mb-3 text-sm font-semibold">Audit trail</h2>
        <DataTable
          rows={state.audit}
          rowKey={(a) => a.id}
          pageSize={10}
          searchable={(a) => `${a.user} ${a.action} ${a.entity} ${a.detail}`}
          columns={[
            {
              key: "at",
              header: "When",
              value: (a) => a.at,
              render: (a) => <span className="num text-xs">{new Date(a.at).toLocaleString("en-IN")}</span>,
            },
            { key: "user", header: "User", value: (a) => a.user },
            {
              key: "action",
              header: "Action",
              value: (a) => a.action,
              render: (a) => <Badge variant="outline">{a.action}</Badge>,
            },
            { key: "entity", header: "Module", value: (a) => a.entity },
            { key: "detail", header: "Detail", value: (a) => a.detail, className: "text-muted-foreground text-xs" },
          ]}
        />
      </div>
    </>
  );
}
