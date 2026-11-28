import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = "http://127.0.0.1:5173";
const browser = await chromium.launch({ headless: true });

async function persona(role, username, apiOverride = null) {
  const context = await browser.newContext();
  const profile = {
    full_name: username, role, username,
    company_id: "e2e-company", company_code: "E2E", company_name: "E2E Company",
  };
  await context.addInitScript((stored) => {
    localStorage.setItem("minitally.token", "e2e-token");
    localStorage.setItem("minitally.profile", JSON.stringify(stored));
  }, profile);

  const page = await context.newPage();
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace("/api/v1", "");
    if (apiOverride && await apiOverride(route, url, path)) return;
    if (path === "/auth/me") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(profile) });
      return;
    }
    if (path === "/finance/payroll-account-mapping") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        id: 1, salary_expense_account_id: "", salary_payable_account_id: "",
        employee_pf_payable_account_id: "", professional_tax_payable_account_id: "",
        tds_payable_account_id: "", updated_by: "system",
      }) });
      return;
    }
    if (path === "/hr/payroll/settings") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        salary_count_mode: "fixed_days", monthly_salary_days: 26,
        week_off_days: [6], updated_at: null,
      }) });
      return;
    }
    if (path.startsWith("/hr/payroll/preview")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        year: 2026, month: 11, salary_count_mode: "fixed_days",
        salary_count_days: 26, items: [],
      }) });
      return;
    }
    const body = route.request().method() === "GET" ? [] : {};
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  return { context, page };
}

try {
  // Employee self-service: visible to production/operator persona, without HR policy controls.
  {
    const { context, page } = await persona("Operator", "employee");
    await page.goto(base + "/hr");
    await page.waitForTimeout(1500);
    process.stdout.write("Operator HR page URL: " + page.url() + "\\n" + (await page.locator("body").innerText()).slice(0, 1800) + "\\n");
    await page.getByRole("tab", { name: "Leave", exact: true }).click();
    await page.getByText("Apply for leave", { exact: true }).waitFor();
    await page.getByText("My leave balances", { exact: true }).waitFor();
    assert.equal(await page.getByText("Create leave policy", { exact: true }).count(), 0);
    assert.equal(await page.getByRole("tab", { name: "Access Control", exact: true }).count(), 0);
    await context.close();
  }

  // Employee persona: self-service attendance and correction request screen.
  {
    const { context, page } = await persona("Operator", "attendance-self-service");
    await page.goto(base + "/attendance");
    await page.getByRole("heading", { name: "My Attendance & Shifts", exact: true }).waitFor();
    await page.getByRole("heading", { name: "My roster", exact: true }).waitFor();
    await page.getByRole("heading", { name: "My daily attendance summaries", exact: true }).waitFor();
    await page.getByRole("heading", { name: "Request an attendance correction", exact: true }).waitFor();
    await context.close();
  }

  // HR persona: can manage leave and payroll, but cannot administer system access.
  {
    const { context, page } = await persona("HR", "hr-manager");
    await page.goto(base + "/hr");
    await page.getByRole("tab", { name: "Leave", exact: true }).click();
    await page.getByRole("heading", { name: "Create leave policy", exact: true }).waitFor();
    assert.equal(await page.getByRole("tab", { name: "Access Control", exact: true }).count(), 0);
    await page.getByRole("tab", { name: "Payroll", exact: true }).click();
    await page.getByRole("button", { name: "Monthly Payroll", exact: true }).click();
    await page.getByText(/Payroll preview/).waitFor();
    await context.close();
  }


  // HR persona: P0.1-11 attendance workspace renders its scoped work areas.
  {
    const { context, page } = await persona("HR", "attendance-manager");
    await page.goto(base + "/hr");
    await page.getByRole("tab", { name: "Attendance & Shifts", exact: true }).click();
    await page.getByRole("tab", { name: "Roster", exact: true }).waitFor();
    await page.getByRole("tab", { name: "Attendance", exact: true }).click();
    await page.getByRole("tab", { name: "Anomalies", exact: true }).click();
    await page.getByRole("tab", { name: "Corrections", exact: true }).click();
    await page.getByRole("tab", { name: "Reports", exact: true }).click();
    await page.getByRole("heading", { name: "Attendance report", exact: true }).waitFor();
    await page.getByRole("button", { name: "Export attendance CSV", exact: true }).waitFor();
    await page.getByRole("button", { name: "Export shift CSV", exact: true }).waitFor();
    await page.getByRole("button", { name: "Export overtime CSV", exact: true }).waitFor();
    await page.getByRole("tab", { name: "Shifts & Assignments", exact: true }).click();
    await page.getByRole("heading", { name: "Create shift", exact: true }).waitFor();
    await page.getByRole("heading", { name: "Create shift assignment", exact: true }).waitFor();
    await context.close();
  }

  // P0.1-11: report reconciliation, full-dataset pagination, exports and scoped supervisor overview.
  {
    const today = new Date().toISOString().slice(0, 10);
    const employees = Array.from({ length: 30 }, (_, i) => ({
      id: "report-employee-" + (i + 1),
      emp_code: "REP-" + String(i + 1).padStart(3, "0"),
      name: "Report Employee " + (i + 1),
      active: true,
      department: "Production",
    }));
    const rosters = employees.map((e, i) => ({
      id: "roster-" + (i + 1), employee_id: e.id, employee_code: e.emp_code,
      employee_name: e.name, work_date: today, status: "scheduled",
      shift_type_id: "shift-day", shift_code: "DAY", shift_name: "Day shift",
      scheduled_start_at_utc: today + "T03:30:00Z", scheduled_end_at_utc: today + "T12:30:00Z",
      timezone_name: "Asia/Kolkata", department: "Production", branch_id: null,
      is_override: false, override_reason: "", version: 1, break_rules: [],
    }));
    const summaries = employees.map((e, i) => ({
      id: "summary-" + (i + 1), employee_id: e.id, work_date: today,
      classification: i < 28 ? "complete" : "incomplete", current_revision: 1,
      elapsed_minutes: i < 28 ? 480 : 0, paired_break_minutes: 30,
      exception_codes: i < 28 ? [] : ["missing_punch_out"], source_event_ids: [],
      first_punch_in_utc: today + "T03:30:00Z", last_punch_out_utc: i < 28 ? today + "T12:30:00Z" : undefined,
      timezone_name: "Asia/Kolkata", input_fingerprint: "fingerprint-" + (i + 1), revision: {},
    }));
    const anomalies = [{
      id: "anomaly-e2e", employee_id: employees[0].id, work_date: today,
      anomaly_type: "late_arrival", status: "open", observed_delta_minutes: 15,
      threshold_minutes: 10, source_events: [], source_event_ids: [], resolution_reason: "",
    }];
    const corrections = [{
      id: "correction-e2e", employee_id: employees[1].id, work_date: today,
      correction_kind: "add", proposed_event_type: "punch_in",
      proposed_at_utc: today + "T03:30:00Z", reason: "Missing punch-in test",
      status: "submitted", requested_by: "employee", reviewer: "",
      decision_reason: "", target_event_id: "",
    }];
    const events = [{
      id: "event-e2e", employee_id: employees[0].id, work_date: today,
      event_type: "punch_in", occurred_at_utc: today + "T03:30:00Z",
      timezone_name: "Asia/Kolkata", source_type: "manual_hr", source_reference: "E2E-REF",
      note: "", voided_at: null, supersedes_event_id: null,
    }];
    const overtime = [{
      id: "overtime-e2e", employee_id: employees[0].id, work_date: today,
      status: "candidate", raw_candidate_minutes: 30, rounded_candidate_minutes: 30, revision: 1,
    }];
    const paginate = (arr, url) => {
      const offset = Number(url.searchParams.get("offset") || 0);
      const limit = Number(url.searchParams.get("limit") || 500);
      return arr.slice(offset, offset + limit);
    };
    const { context, page } = await persona("HR", "attendance-report-e2e", async (route, url, path) => {
      if (path === "/manufacturing/employees" && route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(employees) });
        return true;
      }
      const routes = {
        "/hr/shift-rosters": rosters,
        "/hr/attendance/summaries": summaries,
        "/hr/attendance/events": events,
        "/hr/attendance/anomalies": anomalies,
        "/hr/attendance/corrections": corrections,
        "/hr/overtime": overtime,
      };
      if (routes[path] && route.request().method() === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(paginate(routes[path], url)) });
        return true;
      }
      return false;
    });
    await page.goto(base + "/hr");
    await page.getByRole("tab", { name: "Attendance & Shifts", exact: true }).click();
    await page.getByRole("tab", { name: "Reports", exact: true }).click();
    await page.getByText("Scheduled roster days", { exact: true }).waitFor();
    assert.match(await page.locator("body").innerText(), /Scheduled roster days\s*30/);
    assert.match(await page.locator("body").innerText(), /Complete days\s*28/);
    assert.match(await page.locator("body").innerText(), /Exception days\s*2/);
    const dailySection = page.getByRole("heading", { name: "Daily attendance report", exact: true }).locator("xpath=ancestor::section[1]");
    await dailySection.getByText("Showing 1–25 of 30", { exact: true }).waitFor();
    await dailySection.getByRole("button", { name: "Next", exact: true }).click();
    await dailySection.getByText("Showing 26–30 of 30", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Monthly report", exact: true }).click();
    const monthlySection = page.getByRole("heading", { name: "Monthly attendance report", exact: true }).locator("xpath=ancestor::section[1]");
    await monthlySection.getByText("Showing 1–25 of 30", { exact: true }).waitFor();
    await monthlySection.getByRole("button", { name: "Export monthly CSV", exact: true }).waitFor();
    const monthlyDownload = page.waitForEvent("download");
    await monthlySection.getByRole("button", { name: "Export monthly CSV", exact: true }).click();
    assert.match((await monthlyDownload).suggestedFilename(), /attendance-monthly/);
    await page.getByRole("button", { name: "Daily report", exact: true }).click();
    const attendanceDownload = page.waitForEvent("download");
    await dailySection.getByRole("button", { name: "Export attendance CSV", exact: true }).click();
    assert.match((await attendanceDownload).suggestedFilename(), /attendance-daily/);
    const periodSection = page.getByRole("heading", { name: "Period employee summary", exact: true }).locator("xpath=ancestor::section[1]");
    const periodDownload = page.waitForEvent("download");
    await periodSection.getByRole("button", { name: "Export period summary CSV", exact: true }).click();
    assert.match((await periodDownload).suggestedFilename(), /attendance-period-summary/);
    const eventDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export source events CSV", exact: true }).click();
    assert.match((await eventDownload).suggestedFilename(), /source-events/);
    const shiftDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export shift CSV", exact: true }).click();
    assert.match((await shiftDownload).suggestedFilename(), /attendance-by-shift/);
    const overtimeDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export overtime CSV", exact: true }).click();
    assert.match((await overtimeDownload).suggestedFilename(), /overtime-candidates/);
    const anomalyDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export anomalies CSV", exact: true }).click();
    assert.match((await anomalyDownload).suggestedFilename(), /attendance-anomalies/);
    const correctionDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Export corrections CSV", exact: true }).click();
    assert.match((await correctionDownload).suggestedFilename(), /attendance-corrections/);
    await page.getByRole("tab", { name: "Team Overview", exact: true }).click();
    await page.getByRole("heading", { name: "Supervisor / team attendance overview", exact: true }).waitFor();
    assert.match(await page.locator("body").innerText(), /Open anomalies\s*1/);
    assert.match(await page.locator("body").innerText(), /Pending corrections\s*1/);
    await page.getByText("late_arrival", { exact: false }).waitFor();
    await page.getByText("Missing punch-in test", { exact: false }).waitFor();
    await context.close();
  }

  // P0.1-11: live UI interactions for shift/break-rule updates and department-default assignment controls.
  {
    const employee = { id: "shift-ui-employee", emp_code: "SH-001", name: "Shift UI Employee", active: true, department: "Production" };
    let shift = { id: "shift-ui-day", code: "DAY", name: "Day Shift", start_time: "09:00", end_time: "17:00", end_day_offset: 0, active: true };
    let rule = { id: "break-ui-lunch", shift_type_id: shift.id, code: "LUNCH", name: "Lunch break", sequence: 1, is_paid: false, planned_duration_minutes: 30, scheduled_start_time: "13:00", scheduled_end_time: "13:30", active: true };
    let assignments = [];
    let assignmentPayload = null;
    const { context, page } = await persona("HR", "shift-edit-e2e", async (route, url, path) => {
      const method = route.request().method();
      if (path === "/manufacturing/employees" && method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([employee]) }); return true;
      }
      if (path === "/hr/shifts" && method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([shift]) }); return true;
      }
      if (path === "/hr/shifts/shift-ui-day/break-rules" && method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([rule]) }); return true;
      }
      if (path === "/hr/shifts/shift-ui-day" && method === "PUT") {
        shift = { ...shift, ...route.request().postDataJSON() };
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(shift) }); return true;
      }
      if (path === "/hr/shifts/shift-ui-day/active" && method === "PATCH") {
        shift = { ...shift, ...route.request().postDataJSON() };
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(shift) }); return true;
      }
      if (path === "/hr/shifts/shift-ui-day/break-rules/break-ui-lunch" && method === "PUT") {
        rule = { ...rule, ...route.request().postDataJSON() };
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(rule) }); return true;
      }
      if (path === "/hr/shifts/shift-ui-day/break-rules/break-ui-lunch/active" && method === "PATCH") {
        rule = { ...rule, ...route.request().postDataJSON() };
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(rule) }); return true;
      }
      if (path === "/hr/shift-assignments" && method === "GET") {
        const offset = Number(url.searchParams.get("offset") || 0);
        const limit = Number(url.searchParams.get("limit") || 500);
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(assignments.slice(offset, offset + limit)) }); return true;
      }
      if (path === "/hr/shift-assignments" && method === "POST") {
        assignmentPayload = route.request().postDataJSON();
        assignments = [{ id: "department-assignment-e2e", ...assignmentPayload, created_by: "shift-edit-e2e" }];
        await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify(assignments[0]) }); return true;
      }
      return false;
    });
    await page.goto(base + "/hr");
    await page.getByRole("tab", { name: "Attendance & Shifts", exact: true }).click();
    await page.getByRole("tab", { name: "Shifts & Assignments", exact: true }).click();
    await page.getByRole("button", { name: "Edit", exact: true }).first().click();
    await page.getByLabel("name", { exact: true }).first().fill("Day Shift Updated");
    await page.getByRole("button", { name: "Update shift", exact: true }).click();
    await page.getByText("DAY · Day Shift Updated · 09:", { exact: false }).waitFor();
    const shiftCatalog = page.getByRole("heading", { name: "Shift catalog", exact: true }).locator("xpath=ancestor::section[1]");
    await shiftCatalog.getByRole("combobox").selectOption(shift.id);
    await page.getByText("Lunch break", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Edit", exact: true }).nth(1).click();
    await page.getByLabel("name", { exact: true }).nth(1).fill("Lunch break updated");
    await page.getByRole("button", { name: "Update break rule", exact: true }).click();
    await page.getByText("Lunch break updated", { exact: false }).waitFor();
    const assignmentSection = page.getByRole("heading", { name: "Create shift assignment", exact: true }).locator("xpath=ancestor::section[1]");
    await assignmentSection.getByRole("combobox").first().selectOption("department");
    await page.getByLabel("Department", { exact: true }).fill("Production");
    await assignmentSection.getByRole("combobox").nth(1).selectOption(shift.id);
    await page.getByRole("button", { name: "Assign shift", exact: true }).click();
    assert.equal(assignmentPayload?.scope_type, "department");
    assert.equal(assignmentPayload?.department, "Production");
    await context.close();
  }

  // HOD persona: a department approver can decide only requests assigned to their login.
  {
    let decision = "pending";
    let patchCount = 0;
    const { context, page } = await persona("Operator", "hod", async (route, url, path) => {
      const method = route.request().method();
      if (path === "/hr/leave/types" && method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([
          { id: "leave-cl", code: "CL", name: "Casual Leave", is_paid: true, active: true },
        ]) });
        return true;
      }
      if (path.startsWith("/hr/leave/balances") && method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
        return true;
      }
      if (path === "/hr/leave/requests" && method === "GET") {
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([
          {
            id: "hod-request", employee_id: "employee-1", leave_type_id: "leave-cl",
            start_date: "2026-11-16", end_date: "2026-11-17", total_days: 2,
            half_day: false, reason: "Personal work", status: decision,
            requested_by: "employee", approver_username: "hod",
            decided_by: decision === "pending" ? "" : "hod", decision_note: "Approved by HOD",
          },
        ]) });
        return true;
      }
      if (path === "/hr/leave/requests/hod-request" && method === "PATCH") {
        const payload = route.request().postDataJSON();
        decision = payload.status;
        patchCount += 1;
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ id: "hod-request", status: decision }) });
        return true;
      }
      return false;
    });
    page.on("dialog", (dialog) => dialog.accept("Approved by HOD"));
    await page.goto(base + "/hr");
    await page.getByRole("tab", { name: "Leave", exact: true }).click();
    await page.getByRole("button", { name: "Approve", exact: true }).waitFor();
    assert.equal(await page.getByRole("heading", { name: "Create leave policy", exact: true }).count(), 0);
    await page.getByRole("button", { name: "Approve", exact: true }).click();
    await page.getByText("approved", { exact: true }).waitFor();
    assert.equal(decision, "approved");
    assert.equal(patchCount, 1);
    await context.close();
  }

  // Admin persona: branch/reporting assignment controls and Finance ledger are available.
  {
    const { context, page } = await persona("Admin", "admin");
    await page.goto(base + "/hr");
    await page.getByRole("tab", { name: "Access Control", exact: true }).click();
    await page.getByText("Branches and reporting structure", { exact: true }).waitFor();
    await page.getByText("Assign employee organisation", { exact: true }).waitFor();
    await page.goto(base + "/finance");
    await page.getByRole("tab", { name: "Ledger & Payroll" }).click();
    await page.getByText("General Ledger & Payroll Posting", { exact: true }).waitFor();
    await page.getByText("Journal history", { exact: true }).waitFor();
    await context.close();
  }

  process.stdout.write("UI smoke checks passed: Operator self-service, HR workflows, Admin access control and Finance ledger.\n");
} finally {
  await browser.close();
}
