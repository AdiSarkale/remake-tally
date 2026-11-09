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
