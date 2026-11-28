import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = process.env.P0_11_LIVE_FRONTEND_URL || "http://127.0.0.1:5173";
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ acceptDownloads: true });
const page = await context.newPage();

try {
  // No API interception is installed in this test: all login and HR requests hit
  // the ephemeral FastAPI + SQLite backend started by CI.
  await page.goto(base + "/login");
  await page.getByLabel("Company code", { exact: true }).fill("P011");
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Password", { exact: true }).fill("P0.1-11-E2E!");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(url => !url.pathname.startsWith("/login"), { timeout: 15000 });

  await page.goto(base + "/hr");
  await page.getByRole("tab", { name: "Attendance & Shifts", exact: true }).click();
  await page.getByRole("tab", { name: "Roster", exact: true }).click();
  await page.getByRole("cell", { name: "P011-001", exact: false }).waitFor({ timeout: 15000 });

  await page.getByRole("tab", { name: "Attendance", exact: true }).click();
  await page.getByRole("cell", { name: "complete", exact: true }).waitFor();
  await page.getByRole("heading", { name: "Raw attendance events", exact: true }).waitFor();

  await page.getByRole("tab", { name: "Corrections", exact: true }).click();
  await page.getByText("p0-11-live-employee", { exact: false }).waitFor();

  await page.getByRole("tab", { name: "Reports", exact: true }).click();
  await page.getByRole("heading", { name: "Daily attendance report", exact: true }).waitFor();
  assert.match(await page.locator("body").innerText(), /Scheduled roster days\s*1/);
  assert.match(await page.locator("body").innerText(), /Complete days\s*1/);
  await page.getByRole("button", { name: "Monthly report", exact: true }).click();
  const monthlyExport = page.getByRole("button", { name: "Export monthly CSV", exact: true });
  await monthlyExport.waitFor({ state: "visible", timeout: 15000 });
  const enableDeadline = Date.now() + 15000;
  while (!(await monthlyExport.isEnabled()) && Date.now() < enableDeadline) {
    await page.waitForTimeout(250);
  }
  assert.equal(await monthlyExport.isEnabled(), true, "Monthly CSV export should become enabled");
  const monthlyDownload = page.waitForEvent("download");
  await monthlyExport.click();
  assert.match((await monthlyDownload).suggestedFilename(), /attendance-monthly/);

  await page.getByRole("tab", { name: "Team Overview", exact: true }).click();
  await page.getByRole("heading", { name: "Supervisor / team attendance overview", exact: true }).waitFor();
  assert.match(await page.locator("body").innerText(), /Pending corrections\s*1/);
  assert.match(await page.locator("body").innerText(), /Open anomalies\s*0/);

  await page.getByRole("tab", { name: "Shifts & Assignments", exact: true }).click();
  await page.getByRole("button", { name: "Edit", exact: true }).first().click();
  await page.getByLabel("name", { exact: true }).first().fill("Day Shift Live Updated");
  await page.getByRole("button", { name: "Update shift", exact: true }).click();
  assert.match(await page.locator("body").innerText(), /DAY · Day Shift Live Updated/);

  await page.getByLabel("Shift", { exact: true }).nth(1).selectOption("p0-11-live-shift");
  await page.getByRole("button", { name: "Edit", exact: true }).nth(1).click();
  await page.getByLabel("name", { exact: true }).nth(1).fill("Lunch break Live Updated");
  await page.getByRole("button", { name: "Update break rule", exact: true }).click();
  await page.getByText("Lunch break Live Updated", { exact: false }).waitFor();

  await page.getByLabel("Assignment scope", { exact: true }).selectOption("department");
  await page.getByLabel("Department", { exact: true }).fill("Production");
  await page.getByLabel("Shift", { exact: true }).first().selectOption("p0-11-live-shift");
  await page.getByRole("button", { name: "Assign shift", exact: true }).click();
  await page.getByText("department · Production", { exact: false }).waitFor();

  process.stdout.write("P0.1-11 LIVE API acceptance passed: login, roster, summary/events, corrections, daily/monthly reports, supervisor view, shift/break edits, and department assignment.\n");
} catch (error) {
  process.stderr.write("P0.1-11 LIVE API acceptance failed: " + (error instanceof Error ? error.stack : String(error)) + "\n");
  await page.screenshot({ path: "/tmp/p0-11-live-api-failure.png", fullPage: true }).catch(() => {});
  throw error;
} finally {
  await context.close();
  await browser.close();
}
