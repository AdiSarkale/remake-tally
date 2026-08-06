import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck, TriangleAlert, MessageSquareWarning, Ruler } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useErp } from "@/lib/erp/store";
import { daysUntil, qualityStats } from "@/lib/erp/ops";
import { dmy, num } from "@/lib/erp/format";

export const Route = createFileRoute("/quality")({
  head: () => ({
    meta: [
      { title: "Quality Management — NKCC ERP" },
      { name: "description", content: "Incoming, in-process and final inspection, NCR and CAPA tracking, 8D customer complaints, and calibration records." },
      { property: "og:title", content: "Quality Management — NKCC ERP" },
      { property: "og:description", content: "ISO 9001-ready inspection, non-conformance and calibration registers." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <QualityPage />
    </AppShell>
  ),
});

const SEVERITY = ["Low", "Medium", "High", "Critical"];

function QualityPage() {
  const state = useErp((s) => s);
  const q = qualityStats(state);
  const customers = state.customers.map((c) => c.name);
  const invoiceNos = state.invoices.map((i) => i.invoiceNo);

  return (
    <>
      <PageHeader
        title="Quality Management"
        subtitle="Inspection checkpoints, non-conformance, root cause, CAPA and calibration control."
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Acceptance rate"
          value={`${Math.round((100 - q.rejectionRate) * 10) / 10}%`}
          tone={q.rejectionRate < 3 ? "success" : "warning"}
          hint={`${num(q.rejected)} rejected of ${num(q.inspected)} inspected`}
          icon={<ShieldCheck className="h-4 w-4" />}
        />
        <StatCard label="Open NCRs" value={num(q.openNcrs)} tone={q.openNcrs ? "warning" : "success"} hint="Awaiting CAPA verification" icon={<TriangleAlert className="h-4 w-4" />} />
        <StatCard label="Open complaints" value={num(q.openComplaints)} tone={q.openComplaints ? "destructive" : "success"} hint="Customer 8D in progress" icon={<MessageSquareWarning className="h-4 w-4" />} />
        <StatCard label="Calibration due" value={num(q.calibrationDue)} tone={q.calibrationDue ? "warning" : "success"} hint="Within 7 days" icon={<Ruler className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="inspections">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="inspections">Inspections</TabsTrigger>
          <TabsTrigger value="ncr">NCR & CAPA</TabsTrigger>
          <TabsTrigger value="complaints">Customer complaints</TabsTrigger>
          <TabsTrigger value="calibration">Calibration</TabsTrigger>
        </TabsList>

        <TabsContent value="inspections">
          <RecordPage
            entity="inspections"
            singular="Inspection"
            autoNumber={{ field: "qcNo", prefix: "QC" }}
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "stage", label: "Stage", type: "select", options: ["Incoming", "In-process", "Final"], required: true },
              { name: "reference", label: "Reference (GRN / batch / DN)", required: true },
              { name: "itemName", label: "Item", required: true },
              { name: "inspectedQty", label: "Inspected qty", type: "number", required: true },
              { name: "acceptedQty", label: "Accepted qty", type: "number", required: true },
              { name: "rejectedQty", label: "Rejected qty", type: "number" },
              { name: "inspector", label: "Inspector", required: true },
              { name: "result", label: "Result", type: "select", options: ["Accepted", "Accepted with Deviation", "Rejected"] },
              { name: "remarks", label: "Observations", type: "textarea" },
            ]}
            searchable={(r) => `${r['qcNo']} ${r['stage']} ${r['itemName']} ${r['reference']} ${r['inspector']}`}
            columns={[
              { key: "qcNo", header: "QC No", value: (r) => String(r['qcNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "stage", header: "Stage", value: (r) => String(r['stage'] ?? "") },
              { key: "itemName", header: "Item", value: (r) => String(r['itemName'] ?? "") },
              { key: "reference", header: "Reference", value: (r) => String(r['reference'] ?? "") },
              { key: "inspectedQty", header: "Insp.", align: "right", value: (r) => Number(r['inspectedQty'] ?? 0), render: (r) => <span className="num">{num(Number(r['inspectedQty'] ?? 0))}</span> },
              { key: "rejectedQty", header: "Rejected", align: "right", value: (r) => Number(r['rejectedQty'] ?? 0), render: (r) => <span className={Number(r['rejectedQty'] ?? 0) ? "num text-destructive" : "num"}>{num(Number(r['rejectedQty'] ?? 0))}</span> },
              { key: "inspector", header: "Inspector", value: (r) => String(r['inspector'] ?? "") },
              { key: "result", header: "Result", value: (r) => String(r['result'] ?? ""), render: (r) => <StatusBadge status={String(r['result'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="ncr">
          <RecordPage
            entity="ncrs"
            singular="NCR"
            autoNumber={{ field: "ncrNo", prefix: "NCR" }}
            fields={[
              { name: "date", label: "Raised on", type: "date", required: true },
              { name: "source", label: "Source", type: "select", options: ["Incoming", "In-process", "Final", "Customer"], required: true },
              { name: "severity", label: "Severity", type: "select", options: SEVERITY },
              { name: "owner", label: "Owner", required: true },
              { name: "dueDate", label: "Target closure", type: "date" },
              { name: "status", label: "Status", type: "select", options: ["Open", "Under Investigation", "CAPA Implemented", "Verified", "Closed"] },
              { name: "description", label: "Non-conformance", type: "textarea", required: true },
              { name: "rootCause", label: "Root cause (why-why)", type: "textarea" },
              { name: "correction", label: "Immediate correction", type: "textarea" },
              { name: "capaAction", label: "Corrective & preventive action", type: "textarea" },
            ]}
            searchable={(r) => `${r['ncrNo']} ${r['description']} ${r['owner']} ${r['source']}`}
            columns={[
              { key: "ncrNo", header: "NCR No", value: (r) => String(r['ncrNo'] ?? "") },
              { key: "date", header: "Raised", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "source", header: "Source", value: (r) => String(r['source'] ?? "") },
              { key: "description", header: "Non-conformance", value: (r) => String(r['description'] ?? ""), render: (r) => <span className="block max-w-72 truncate">{String(r['description'] ?? "")}</span> },
              { key: "severity", header: "Severity", value: (r) => String(r['severity'] ?? ""), render: (r) => <StatusBadge status={String(r['severity'] ?? "")} /> },
              { key: "owner", header: "Owner", value: (r) => String(r['owner'] ?? "") },
              { key: "dueDate", header: "Due", value: (r) => String(r['dueDate'] ?? ""), render: (r) => dmy(String(r['dueDate'] ?? "")) },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="complaints">
          <RecordPage
            entity="complaints"
            singular="Complaint"
            autoNumber={{ field: "complaintNo", prefix: "CMP" }}
            fields={[
              { name: "date", label: "Received on", type: "date", required: true },
              { name: "customerName", label: "Customer", type: "select", options: customers, required: true },
              { name: "invoiceNo", label: "Against invoice", type: "select", options: invoiceNos.length ? invoiceNos : ["—"] },
              { name: "severity", label: "Severity", type: "select", options: SEVERITY },
              { name: "assignedTo", label: "Assigned to", required: true },
              { name: "status", label: "Status", type: "select", options: ["Open", "Investigating", "Resolved", "Closed"] },
              { name: "closedOn", label: "Closed on", type: "date" },
              { name: "issue", label: "Complaint", type: "textarea", required: true },
              { name: "rootCause", label: "Root cause", type: "textarea" },
              { name: "resolution", label: "Resolution / 8D outcome", type: "textarea" },
            ]}
            searchable={(r) => `${r['complaintNo']} ${r['customerName']} ${r['issue']} ${r['assignedTo']}`}
            columns={[
              { key: "complaintNo", header: "Ref", value: (r) => String(r['complaintNo'] ?? "") },
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "customerName", header: "Customer", value: (r) => String(r['customerName'] ?? "") },
              { key: "issue", header: "Issue", value: (r) => String(r['issue'] ?? ""), render: (r) => <span className="block max-w-64 truncate">{String(r['issue'] ?? "")}</span> },
              { key: "invoiceNo", header: "Invoice", value: (r) => String(r['invoiceNo'] ?? "") },
              { key: "severity", header: "Severity", value: (r) => String(r['severity'] ?? ""), render: (r) => <StatusBadge status={String(r['severity'] ?? "")} /> },
              { key: "assignedTo", header: "Owner", value: (r) => String(r['assignedTo'] ?? "") },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="calibration">
          <RecordPage
            entity="calibrations"
            singular="Instrument"
            fields={[
              { name: "instrumentNo", label: "Instrument ID", required: true },
              { name: "instrument", label: "Instrument", required: true },
              { name: "location", label: "Location" },
              { name: "lastCalibrated", label: "Last calibrated", type: "date", required: true },
              { name: "nextDue", label: "Next due", type: "date", required: true },
              { name: "agency", label: "Calibration agency" },
              { name: "certificateNo", label: "Certificate no." },
            ]}
            searchable={(r) => `${r['instrumentNo']} ${r['instrument']} ${r['agency']}`}
            columns={[
              { key: "instrumentNo", header: "ID", value: (r) => String(r['instrumentNo'] ?? "") },
              { key: "instrument", header: "Instrument", value: (r) => String(r['instrument'] ?? "") },
              { key: "location", header: "Location", value: (r) => String(r['location'] ?? "") },
              { key: "lastCalibrated", header: "Last", value: (r) => String(r['lastCalibrated'] ?? ""), render: (r) => dmy(String(r['lastCalibrated'] ?? "")) },
              {
                key: "nextDue",
                header: "Next due",
                value: (r) => String(r['nextDue'] ?? ""),
                render: (r) => {
                  const d = daysUntil(String(r['nextDue'] ?? ""));
                  return (
                    <span className={d < 0 ? "num text-destructive" : d <= 7 ? "num text-warning" : "num"}>
                      {dmy(String(r['nextDue'] ?? ""))}
                      {d < 0 && <span className="ml-1 text-xs">(overdue)</span>}
                    </span>
                  );
                },
              },
              { key: "agency", header: "Agency", value: (r) => String(r['agency'] ?? "") },
              { key: "certificateNo", header: "Certificate", value: (r) => String(r['certificateNo'] ?? "") },
            ]}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
