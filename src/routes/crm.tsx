import { createFileRoute } from "@tanstack/react-router";
import { Target, PhoneCall, Trophy, IndianRupee } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { useErp } from "@/lib/erp/store";
import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/crm")({
  head: () => ({
    meta: [
      { title: "Enquiries & CRM — NKCC ERP" },
      { name: "description", content: "Capture customer enquiries, track follow-ups, monitor the quotation pipeline and measure win rate by source." },
      { property: "og:title", content: "Enquiries & CRM — NKCC ERP" },
      { property: "og:description", content: "Lead pipeline from enquiry to won order." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <CrmPage />
    </AppShell>
  ),
});

function CrmPage() {
  const leads = useErp((s) => s.leads);
  const customers = useErp((s) => s.customers.map((c) => c.name));
  const open = leads.filter((l) => !["Won", "Lost"].includes(l.status));
  const won = leads.filter((l) => l.status === "Won");
  const decided = leads.filter((l) => ["Won", "Lost"].includes(l.status)).length;
  const winRate = decided ? Math.round((won.length / decided) * 100) : 0;
  const pipeline = open.reduce((t, l) => t + l.estimatedValue, 0);
  const today = new Date().toISOString().slice(0, 10);
  const dueFollowUps = open.filter((l) => l.nextFollowUp && l.nextFollowUp <= today).length;

  return (
    <>
      <PageHeader title="Enquiries & CRM" subtitle="Enquiry capture, follow-up discipline, quotation pipeline and conversion tracking." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Open enquiries" value={num(open.length)} icon={<Target className="h-4 w-4" />} />
        <StatCard label="Pipeline value" value={inr(pipeline)} tone="primary" icon={<IndianRupee className="h-4 w-4" />} />
        <StatCard label="Win rate" value={`${winRate}%`} tone={winRate >= 40 ? "success" : "warning"} hint={`${num(won.length)} won of ${num(decided)} closed`} icon={<Trophy className="h-4 w-4" />} />
        <StatCard label="Follow-ups due" value={num(dueFollowUps)} tone={dueFollowUps ? "warning" : "success"} hint="On or before today" icon={<PhoneCall className="h-4 w-4" />} />
      </div>

      <RecordPage
        entity="leads"
        singular="Enquiry"
        autoNumber={{ field: "enquiryNo", prefix: "ENQ" }}
        fields={[
          { name: "date", label: "Enquiry date", type: "date", required: true },
          { name: "customerName", label: "Customer", type: "select", options: customers, required: true },
          { name: "contact", label: "Contact person / phone" },
          { name: "productInterest", label: "Product interest", required: true, full: true },
          { name: "expectedQty", label: "Expected qty", type: "number" },
          { name: "estimatedValue", label: "Estimated value", type: "number", required: true },
          { name: "source", label: "Source", type: "select", options: ["Referral", "Website", "Exhibition", "Cold Call", "Existing Customer"] },
          { name: "owner", label: "Owner", required: true },
          { name: "status", label: "Stage", type: "select", options: ["New", "Contacted", "Quoted", "Negotiation", "Won", "Lost"] },
          { name: "nextFollowUp", label: "Next follow-up", type: "date" },
        ]}
        searchable={(r) => `${r['enquiryNo']} ${r['customerName']} ${r['productInterest']} ${r['owner']} ${r['source']}`}
        columns={[
          { key: "enquiryNo", header: "Enquiry", value: (r) => String(r['enquiryNo'] ?? "") },
          { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
          { key: "customerName", header: "Customer", value: (r) => String(r['customerName'] ?? "") },
          { key: "productInterest", header: "Interest", value: (r) => String(r['productInterest'] ?? ""), render: (r) => <span className="block max-w-56 truncate">{String(r['productInterest'] ?? "")}</span> },
          { key: "expectedQty", header: "Qty", align: "right", value: (r) => Number(r['expectedQty'] ?? 0), render: (r) => <span className="num">{num(Number(r['expectedQty'] ?? 0))}</span> },
          { key: "estimatedValue", header: "Value", align: "right", value: (r) => Number(r['estimatedValue'] ?? 0), render: (r) => <span className="num">{inr(Number(r['estimatedValue'] ?? 0))}</span> },
          { key: "source", header: "Source", value: (r) => String(r['source'] ?? "") },
          { key: "owner", header: "Owner", value: (r) => String(r['owner'] ?? "") },
          {
            key: "nextFollowUp",
            header: "Follow-up",
            value: (r) => String(r['nextFollowUp'] ?? ""),
            render: (r) => {
              const d = String(r['nextFollowUp'] ?? "");
              const overdue = d && d <= new Date().toISOString().slice(0, 10) && !["Won", "Lost"].includes(String(r['status'] ?? ""));
              return <span className={overdue ? "num text-warning" : "num"}>{d ? dmy(d) : "—"}</span>;
            },
          },
          { key: "status", header: "Stage", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
        ]}
      />
    </>
  );
}
