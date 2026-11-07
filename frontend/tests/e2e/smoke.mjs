import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = "http://127.0.0.1:5173";
const browser = await chromium.launch({ headless: true });

async function persona(role, username) {
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
    await page.getByText("Create leave policy", { exact: true }).waitFor();
    assert.equal(await page.getByRole("tab", { name: "Access Control", exact: true }).count(), 0);
    await page.getByRole("tab", { name: "Payroll", exact: true }).click();
    await page.getByText(/Payroll preview/).waitFor();
    await context.close();
  }

  // Admin persona: branch/reporting assignment controls and Finance ledger are available.
  {
    const { context, page } = await persona("Admin", "admin");
    await page.goto(base + "/hr");
    await page.getByRole("tab", { name: "Access Control", exact: true }).click();
    await page.getByText("Branches and reporting structure", { exact: true }).waitFor();
    await page.getByText("Employee reporting assignments", { exact: true }).waitFor();
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
