import { createFileRoute } from "@tanstack/react-router";
import { Users, CalendarCheck2, Plane, IndianRupee } from "lucide-react";
import { AppShell } from "@/components/erp/AppShell";
import { PageHeader, StatCard } from "@/components/erp/PageHeader";
import { RecordPage } from "@/components/erp/RecordPage";
import { StatusBadge } from "@/components/erp/DocBits";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useErp } from "@/lib/erp/store";
import { hrStats } from "@/lib/erp/ops";
import { dmy, inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/hr")({
  head: () => ({
    meta: [
      { title: "HR & Workforce — NKCC ERP" },
      { name: "description", content: "Employee master, daily attendance and overtime, leave approvals, skill training records, appraisals and payroll summary." },
      { property: "og:title", content: "HR & Workforce — NKCC ERP" },
      { property: "og:description", content: "Attendance, leave, training and appraisal management for the plant." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: () => (
    <AppShell>
      <HrPage />
    </AppShell>
  ),
});

function HrPage() {
  const state = useErp((s) => s);
  const h = hrStats(state);
  const empNames = state.employees.map((e) => e.name);

  return (
    <>
      <PageHeader title="HR & Workforce" subtitle="Employee master, attendance, leave, training, appraisal and payroll cost." />

      <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Headcount" value={num(h.headcount)} hint="Active employees" icon={<Users className="h-4 w-4" />} />
        <StatCard label="Attendance today" value={`${h.attendancePercent}%`} tone={h.attendancePercent >= 90 ? "success" : "warning"} hint={`${num(h.present)} present · ${num(h.absent)} absent`} icon={<CalendarCheck2 className="h-4 w-4" />} />
        <StatCard label="Leaves pending" value={num(h.pendingLeaves)} tone={h.pendingLeaves ? "warning" : "success"} hint={`${num(h.onLeave)} on leave today`} icon={<Plane className="h-4 w-4" />} />
        <StatCard label="Monthly payroll" value={inr(h.monthlyPayroll)} tone="primary" hint={`${num(h.overtimeHours)} OT hrs today`} icon={<IndianRupee className="h-4 w-4" />} />
      </div>

      <Tabs defaultValue="employees">
        <TabsList className="mb-4 flex-wrap">
          <TabsTrigger value="employees">Employees</TabsTrigger>
          <TabsTrigger value="attendance">Attendance</TabsTrigger>
          <TabsTrigger value="leaves">Leave</TabsTrigger>
          <TabsTrigger value="trainings">Training</TabsTrigger>
          <TabsTrigger value="appraisals">Appraisal</TabsTrigger>
        </TabsList>

        <TabsContent value="employees">
          <RecordPage
            entity="employees"
            singular="Employee"
            fields={[
              { name: "empCode", label: "Employee code", required: true },
              { name: "name", label: "Name", required: true },
              { name: "department", label: "Department", required: true },
              { name: "designation", label: "Designation", required: true },
              { name: "doj", label: "Date of joining", type: "date" },
              { name: "mobile", label: "Mobile" },
              { name: "monthlySalary", label: "Monthly salary", type: "number", required: true },
              { name: "skillLevel", label: "Skill level", type: "select", options: ["Trainee", "Semi-skilled", "Skilled", "Highly Skilled"] },
              { name: "status", label: "Status", type: "select", options: ["Active", "On Notice", "Exited"] },
            ]}
            searchable={(r) => `${r['empCode']} ${r['name']} ${r['department']} ${r['designation']}`}
            columns={[
              { key: "empCode", header: "Code", value: (r) => String(r['empCode'] ?? "") },
              { key: "name", header: "Name", value: (r) => String(r['name'] ?? "") },
              { key: "department", header: "Department", value: (r) => String(r['department'] ?? "") },
              { key: "designation", header: "Designation", value: (r) => String(r['designation'] ?? "") },
              { key: "doj", header: "Joined", value: (r) => String(r['doj'] ?? ""), render: (r) => dmy(String(r['doj'] ?? "")) },
              { key: "skillLevel", header: "Skill", value: (r) => String(r['skillLevel'] ?? "") },
              { key: "monthlySalary", header: "Salary", align: "right", value: (r) => Number(r['monthlySalary'] ?? 0), render: (r) => <span className="num">{inr(Number(r['monthlySalary'] ?? 0))}</span> },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="attendance">
          <RecordPage
            entity="attendance"
            singular="Attendance entry"
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "empName", label: "Employee", type: "select", options: empNames, required: true },
              { name: "empCode", label: "Employee code" },
              { name: "status", label: "Status", type: "select", options: ["Present", "Absent", "Leave", "Half Day", "Week Off"] },
              { name: "inTime", label: "In time", placeholder: "08:30" },
              { name: "outTime", label: "Out time", placeholder: "17:30" },
              { name: "overtimeHours", label: "Overtime hours", type: "number" },
            ]}
            searchable={(r) => `${r['empName']} ${r['empCode']} ${r['status']} ${r['date']}`}
            columns={[
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "empCode", header: "Code", value: (r) => String(r['empCode'] ?? "") },
              { key: "empName", header: "Employee", value: (r) => String(r['empName'] ?? "") },
              { key: "inTime", header: "In", value: (r) => String(r['inTime'] ?? "") },
              { key: "outTime", header: "Out", value: (r) => String(r['outTime'] ?? "") },
              { key: "overtimeHours", header: "OT", align: "right", value: (r) => Number(r['overtimeHours'] ?? 0), render: (r) => <span className="num">{num(Number(r['overtimeHours'] ?? 0))}</span> },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="leaves">
          <RecordPage
            entity="leaves"
            singular="Leave request"
            fields={[
              { name: "empName", label: "Employee", type: "select", options: empNames, required: true },
              { name: "empCode", label: "Employee code" },
              { name: "type", label: "Leave type", type: "select", options: ["Casual", "Sick", "Earned", "Unpaid"] },
              { name: "fromDate", label: "From", type: "date", required: true },
              { name: "toDate", label: "To", type: "date", required: true },
              { name: "days", label: "Days", type: "number", required: true },
              { name: "status", label: "Status", type: "select", options: ["Pending", "Approved", "Rejected"] },
              { name: "reason", label: "Reason", type: "textarea" },
            ]}
            searchable={(r) => `${r['empName']} ${r['type']} ${r['status']}`}
            columns={[
              { key: "empCode", header: "Code", value: (r) => String(r['empCode'] ?? "") },
              { key: "empName", header: "Employee", value: (r) => String(r['empName'] ?? "") },
              { key: "type", header: "Type", value: (r) => String(r['type'] ?? "") },
              { key: "fromDate", header: "From", value: (r) => String(r['fromDate'] ?? ""), render: (r) => dmy(String(r['fromDate'] ?? "")) },
              { key: "toDate", header: "To", value: (r) => String(r['toDate'] ?? ""), render: (r) => dmy(String(r['toDate'] ?? "")) },
              { key: "days", header: "Days", align: "right", value: (r) => Number(r['days'] ?? 0), render: (r) => <span className="num">{num(Number(r['days'] ?? 0))}</span> },
              { key: "reason", header: "Reason", value: (r) => String(r['reason'] ?? ""), render: (r) => <span className="block max-w-56 truncate">{String(r['reason'] ?? "")}</span> },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="trainings">
          <RecordPage
            entity="trainings"
            singular="Training record"
            fields={[
              { name: "date", label: "Date", type: "date", required: true },
              { name: "empName", label: "Employee", type: "select", options: empNames, required: true },
              { name: "empCode", label: "Employee code" },
              { name: "topic", label: "Topic", required: true, full: true },
              { name: "trainer", label: "Trainer" },
              { name: "hours", label: "Hours", type: "number" },
              { name: "effectiveness", label: "Effectiveness", type: "select", options: ["Pending Evaluation", "Satisfactory", "Good", "Excellent", "Re-training Needed"] },
            ]}
            searchable={(r) => `${r['empName']} ${r['topic']} ${r['trainer']}`}
            columns={[
              { key: "date", header: "Date", value: (r) => String(r['date'] ?? ""), render: (r) => dmy(String(r['date'] ?? "")) },
              { key: "empName", header: "Employee", value: (r) => String(r['empName'] ?? "") },
              { key: "topic", header: "Topic", value: (r) => String(r['topic'] ?? "") },
              { key: "trainer", header: "Trainer", value: (r) => String(r['trainer'] ?? "") },
              { key: "hours", header: "Hours", align: "right", value: (r) => Number(r['hours'] ?? 0), render: (r) => <span className="num">{num(Number(r['hours'] ?? 0))}</span> },
              { key: "effectiveness", header: "Effectiveness", value: (r) => String(r['effectiveness'] ?? ""), render: (r) => <StatusBadge status={String(r['effectiveness'] ?? "")} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="appraisals">
          <RecordPage
            entity="appraisals"
            singular="Appraisal"
            fields={[
              { name: "period", label: "Period", required: true, placeholder: "2026-27 H1" },
              { name: "empName", label: "Employee", type: "select", options: empNames, required: true },
              { name: "empCode", label: "Employee code" },
              { name: "rating", label: "Rating (1-5)", type: "number", required: true },
              { name: "incrementPercent", label: "Increment %", type: "number" },
              { name: "status", label: "Status", type: "select", options: ["Draft", "Reviewed", "Approved"] },
              { name: "strengths", label: "Strengths", type: "textarea" },
              { name: "improvement", label: "Improvement areas", type: "textarea" },
            ]}
            searchable={(r) => `${r['empName']} ${r['period']} ${r['status']}`}
            columns={[
              { key: "period", header: "Period", value: (r) => String(r['period'] ?? "") },
              { key: "empCode", header: "Code", value: (r) => String(r['empCode'] ?? "") },
              { key: "empName", header: "Employee", value: (r) => String(r['empName'] ?? "") },
              { key: "rating", header: "Rating", align: "right", value: (r) => Number(r['rating'] ?? 0), render: (r) => <span className="num">{Number(r['rating'] ?? 0)} / 5</span> },
              { key: "incrementPercent", header: "Increment", align: "right", value: (r) => Number(r['incrementPercent'] ?? 0), render: (r) => <span className="num">{Number(r['incrementPercent'] ?? 0)}%</span> },
              { key: "strengths", header: "Strengths", value: (r) => String(r['strengths'] ?? ""), render: (r) => <span className="block max-w-56 truncate">{String(r['strengths'] ?? "")}</span> },
              { key: "status", header: "Status", value: (r) => String(r['status'] ?? ""), render: (r) => <StatusBadge status={String(r['status'] ?? "")} /> },
            ]}
          />
        </TabsContent>
      </Tabs>
    </>
  );
}
