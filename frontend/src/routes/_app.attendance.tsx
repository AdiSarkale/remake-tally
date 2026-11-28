import { createFileRoute } from "@tanstack/react-router";
import { HrSelfAttendancePanel } from "@/components/hr-self-attendance-panel";
export const Route = createFileRoute("/_app/attendance")({
  head: () => ({ meta: [{ title: "My Attendance — Nexora ERP" }, { name: "description", content: "Employee self-service attendance and shift information." }] }),
  component: AttendancePage,
});
function AttendancePage(){return <HrSelfAttendancePanel/>}
