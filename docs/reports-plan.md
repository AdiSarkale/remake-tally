# Reports Module — Implementation Plan

**Status:** Planned; documentation baseline only  
**Repository baseline reviewed:** `main` at `ae14d209e635263087ff3e08558f8508d29c944a`  
**Purpose:** Define the report catalogue, data dependencies, access rules, delivery phases, and acceptance criteria before implementing the Reports module.

> This document is a plan, not a claim that the listed reports or UI exist. At the reviewed baseline, the Reports route is a placeholder. A manufacturing production summary endpoint already exists at `GET /api/v1/manufacturing/reports/production`; dashboard KPIs are separate from a complete reports workspace.

## 1. Goals and non-goals

The Reports module should expose trustworthy, filterable, tenant-scoped views of business activity already recorded by MiniTally, and clearly identify where new source data or accounting logic is required.

### Goals

- Provide one discoverable Reports workspace with reports grouped by business function.
- Reuse domain rules and existing records rather than duplicating business calculations in the frontend.
- Support consistent date, status, party, item, document, and location/work-centre filters where applicable.
- Provide drill-down from summary metrics to the underlying source documents.
- Start with CSV exports; add spreadsheet and print/PDF formats only after report definitions and totals are stable.
- Enforce report access in the backend, not only by hiding frontend navigation.
- Keep every operational report scoped to the tenant selected by authenticated company context.

### Out of scope for the initial releases

- A general-purpose report designer, user-authored SQL, or arbitrary formula engine.
- Treating operational documents as a double-entry accounting ledger.
- Claims of statutory GST, balance-sheet, profit-and-loss, or trial-balance accuracy before the required accounting model and compliance review exist.
- Payroll, attendance, leave, and shift reports; those modules are currently out of scope.
- Cross-company operational reports. Platform-wide tenant operations reports belong to the control plane and the separate audit plan.

## 2. Current baseline and known gaps

- The frontend route `frontend/src/routes/_app.reports.tsx` renders a `ModulePlaceholder`.
- The backend has a manufacturing report endpoint, `GET /api/v1/manufacturing/reports/production`, plus dashboard calculations. These are useful starting points, not a complete report API.
- The tenant database has source records for sales, quotations, sales orders, invoices, customer/supplier payments, purchase requisitions/orders, inventory movements, production entries, scrap entries, BOMs, routings, work centres, and employees/skills.
- Report authorization is currently represented by the `reports` area in the role permissions: administrators and accountants have it; operators do not. Preserve backend enforcement and refine per-report visibility before shipping sensitive financial or audit details.
- The existing audit trail is a separate concern and has coverage limitations. See [Audit Reports Plan](audit-reports-plan.md).
- Data models and workflows must be checked report-by-report. A field existing on a form is not proof that the data is complete, historically correct, or sufficient for a financial KPI.

## 3. Report catalogue

Priority meanings: **P0** foundation / release blocker; **P1** first usable release; **P2** business analysis; **P3** advanced analysis or new data dependency.

### Management

| Key | Report | Main output | Priority / dependency |
|---|---|---|---|
| MGT-01 | Executive operations summary | Selected-period sales, collections, purchase commitments, stock alerts, production output and scrap; links to detail reports | P1; reuse validated domain calculations |
| MGT-02 | KPI trend comparison | Current period vs previous equivalent period, with metric definitions shown | P2; shared date semantics and stable history |
| MGT-03 | Open-work snapshot | Open sales orders, outstanding purchase receipts, active production orders and pending approvals | P1; status meanings must be defined per workflow |

### Sales and customer service

| Key | Report | Main output | Priority / dependency |
|---|---|---|---|
| SAL-01 | Sales document register | Quotations, sales orders, invoices and their statuses with date/customer/document filters | P1; clear which document type is selected |
| SAL-02 | Sales summary by period | Net/gross totals, tax, document counts, customer/product breakdowns | P2; approve cancellation, tax, discount and date rules |
| SAL-03 | Quotation pipeline and conversion | Draft/submitted/accepted/rejected/expired counts and value; conversion rate | P2; stable terminal status definitions and linked order where captured |
| SAL-04 | Sales order backlog | Ordered, fulfilled/delivered, remaining quantity and age by order line | P1; validate fulfilment linkages and partial deliveries |
| SAL-05 | Delivery and dispatch performance | Delivery register, promised vs actual date where stored, delayed/in-transit dispatches | P2; dependable planned dates and status transitions |
| SAL-06 | Customer receivables | Invoice amount, recorded payments, remaining amount, age bucket and customer totals | P2; verify invoice/payment linkage, credit notes/cancellations and due-date semantics |

### Procurement

| Key | Report | Main output | Priority / dependency |
|---|---|---|---|
| PUR-01 | Purchase requisition register | Requisition owner/source/status, requested items and approval state | P1; show manual requisitions honestly; do not imply MRP generation exists |
| PUR-02 | Purchase order register | Supplier, order date, status, item/quantity/value and remaining receipt | P1; validate receipt linkage and partial-receipt handling |
| PUR-03 | Open purchase commitments | Ordered quantity/value not yet received, grouped by supplier/item/age | P2; agreed treatment of closed, cancelled and partially received POs |
| PUR-04 | Goods receipt register | Receipt/GRN date, supplier, PO reference, received quantities and exceptions | P1; receipt source data and references must reconcile |
| PUR-05 | Supplier spend trend | Ordered/received value by supplier, material and period | P2; define spend basis; PO value is commitment, not necessarily an accounting expense |
| PUR-06 | Supplier payment register | Payment date, supplier, method/reference and amount | P1; use recorded payments only |
| PUR-07 | Accounts payable ageing | Supplier liability and overdue age buckets | P3; requires a reliable supplier-invoice/liability source and adjustment rules if not already available |

### Inventory and materials

| Key | Report | Main output | Priority / dependency |
|---|---|---|---|
| INV-01 | Stock on hand | Quantity by finished product, raw material and scrap item; location where supported | P1; reconcile stored balance with inventory movements |
| INV-02 | Low-stock exceptions | Current stock vs configured minimum, shortage amount and suggested review list | P1; use item-specific minimum stock; avoid claiming MRP recommendations |
| INV-03 | Inventory movement ledger | In/out/adjustment, quantity, balance, date, reference, reason and actor | P1; inventory movement history and permissions |
| INV-04 | Stock adjustment register | Physical-count adjustments, reason, before/after balance and actor where captured | P1; source audit fields may need strengthening |
| INV-05 | Inventory valuation | Quantity and value by item/category | P3; **blocked until a valuation policy is approved** (for example, standard cost vs weighted average) and purchase/consumption costing is reconciled |
| INV-06 | Stock movement / slow-moving analysis | Inactivity and movement frequency by item | P3; requires a defined inactivity window and complete history; do not label as dead stock without policy |
| INV-07 | Material availability snapshot | BOM demand vs on-hand and open supply | P2/P3; BOM quantities, open PO receipts and production demand must be joined consistently; do not present as full MRP unless planning logic exists |

### Production, work centres and scrap

| Key | Report | Main output | Priority / dependency |
|---|---|---|---|
| PRD-01 | Production output register | Production order/batch, product, quantity, entry date and recorded operator | P1; build on existing production summary and detail records |
| PRD-02 | Production order status and backlog | Planned, in-progress and completed quantities with age/status | P1; validate order lifecycle and planned quantity fields |
| PRD-03 | Output by product / period / work centre | Quantities and trend by product, routing operation and work centre where linked | P2; reliable operation-to-entry mapping |
| PRD-04 | Routing and operation performance | Operation throughput, queue, duration and bottleneck indicators | P3; requires operation-level start/finish and work-time capture; capacity alone is not actual utilisation |
| PRD-05 | Work-centre utilisation | Actual productive time vs available capacity | P3; requires shifts/calendars, downtime and actual operation duration; do not infer true utilisation from output quantity alone |
| PRD-06 | Scrap register and reasons | Scrap quantity, type, reason, date, order/product/operation and recorded actor | P1; existing scrap records and reason values |
| PRD-07 | Scrap rate and yield trend | Scrap relative to production output; trend and reason Pareto | P2; define denominator, units, rework treatment and zero-production periods |
| PRD-08 | BOM consumption variance | Planned component demand vs issued/consumed quantity and variance | P3; requires consistent material-issue and actual-consumption data linked to production orders |

### Finance and tax visibility

| Key | Report | Main output | Priority / dependency |
|---|---|---|---|
| FIN-01 | Invoice register | Invoice date/number, customer, status, taxable amount, tax and gross total | P1; validate line totals, cancellations and credit adjustments |
| FIN-02 | Customer collection trend | Payments by period/customer/method and linked invoice where recorded | P1; use customer payment records and explicit payment-date rules |
| FIN-03 | Customer outstanding summary | Invoice balance and age by customer/document | P2; reconcile invoice and payment allocations; expose unapplied payments if supported |
| FIN-04 | Tax summary (internal review) | Sales tax rates and amounts by period | P2; label as an internal summary until statutory mapping and accounting review are complete |
| FIN-05 | Profitability by product/customer | Revenue less cost and margin percentage | P3; blocked until cost basis, returns, discounts and tax exclusion rules are approved |
| FIN-06 | Cash / payment register | Customer and supplier payments with filters and totals | P1; distinguishes cash movements recorded in MiniTally from bank reconciliation |
| FIN-07 | General ledger, trial balance, P&L and balance sheet | Double-entry account balances and financial statements | P3 / separate accounting capability; requires chart of accounts, journal entries, period close, opening balances and reconciliation. Do not derive these reports from invoices/payments alone |

### People and administration (limited current scope)

| Key | Report | Main output | Priority / dependency |
|---|---|---|---|
| HR-01 | Employee and skills directory | Active employee list, skills and levels; filters by skill/type/active state | P2; existing employee/skill data; access restricted |
| HR-02 | Attendance, payroll, leave and shift reports | Attendance exceptions, wage/payroll totals, leave balances and shift coverage | Out of scope until the corresponding source modules and approvals are implemented |

Audit-specific reports are defined in [Audit Reports Plan](audit-reports-plan.md) and should not be duplicated as ordinary operational analytics.

## 4. Shared report behaviour

Every report should define the following before implementation:

1. **Definition:** purpose, calculation formula, source entities, unit/currency, inclusions/exclusions, status treatment and known limitations.
2. **Filters:** relevant date range, customer/supplier, document/status, product/material, work centre, employee and location where data supports them. Reject invalid ranges and unknown filter values.
3. **Tenant boundary:** derive the active tenant from the authenticated token/context. Never take a request-supplied database URL or untrusted company ID as a selector.
4. **Authorization:** check the report permission in the backend. Hide or redact sensitive fields according to role; frontend route visibility is not the security boundary.
5. **Result metadata:** report key/version, generated-at timestamp, selected filters, row count, currency/unit and any warning that affects interpretation.
6. **Performance:** aggregate and filter in the database; paginate detail rows; add indexes only from measured query plans; establish row/export limits and timeout behaviour.
7. **Accuracy:** use decimal-safe arithmetic for money, explicit rounding, documented date/time zones and consistent cancellation/return handling.
8. **Drill-down:** include stable document identifiers and link to an authorized detail page when one exists.
9. **Export safety:** CSV first, escaping cells that could execute spreadsheet formulas; exports must apply the same filters and authorization as the displayed report.
10. **Auditability:** record report exports and sensitive report access where required; see the audit plan.

## 5. Suggested implementation layout

Keep report definitions in domain-focused backend services and expose explicit schemas. Avoid a user-controlled SQL or untyped query language.

Suggested direction (names are proposals, not existing files):

```text
backend/app/
├── api/routes/reports.py
├── schemas_reports.py
└── services/reports/
    ├── common.py          # filter validation, metadata and shared helpers
    ├── sales.py
    ├── procurement.py
    ├── inventory.py
    ├── production.py
    └── finance.py
frontend/src/
├── routes/_app.reports.tsx
└── components/reports/    # filters, summary cards, tables and export controls
```

Suggested API shape:

- `GET /api/v1/reports/catalog` — only reports visible to the current role.
- `GET /api/v1/reports/{report_key}` — typed report results with validated filters.
- `GET /api/v1/reports/{report_key}/export?format=csv` — export the same query with the same access checks.

The existing manufacturing report can either remain as a compatibility endpoint or be moved behind the shared report service after parity tests. Do not break its response contract without a deliberate migration.

## 6. Delivery phases

### Phase 0 — Definitions and data readiness (required before coding)

- Confirm report names, metric owners and calculation definitions with the business owner.
- Map each metric to source tables/fields and prove key joins using seeded and edge-case data.
- Document missing fields (notably GL data, inventory valuation basis, true work-centre time, and AP liabilities).
- Choose date, time-zone, currency, GST/tax, cancellation and rounding rules.
- Define report permissions and export limits.
- Add a report registry with explicit readiness: **Ready**, **Partial / caveated**, or **Blocked by source data**.

**Exit criteria:** each P1 report has an approved formula, source mapping, role matrix and example expected result.

### Phase 1 — Report foundation and MVP (P1)

- Replace the Reports placeholder with a role-aware workspace grouped by domain.
- Add report catalog and shared filters/metadata, typed results and database-side pagination.
- Implement stock on hand, low-stock exceptions, inventory movement ledger, production output register, production/scrap summaries, purchase requisition/PO/receipt registers, invoice/payment registers and open-work snapshot.
- Add CSV export for approved reports.
- Add backend tests for tenant isolation, permission denial, filter validation, totals and export parity.

**Exit criteria:** no cross-tenant leakage; report totals match source records; all displayed reports identify their date range and limitations.

### Phase 2 — Commercial and working-capital views (P2)

- Sales by period/customer/product, quotation pipeline, sales backlog and delivery performance.
- Customer receivables and collection trends with explicit invoice/payment allocation rules.
- Supplier spend, open commitments, and material availability snapshot.
- Employee/skills directory only, within current HR scope.
- Add drill-downs and period comparisons.

**Exit criteria:** every calculated balance has reconciliation tests; partial fulfilments, cancellations, unapplied payments and missing dates are covered.

### Phase 3 — Manufacturing analytics and costing foundations (P3)

- Scrap-rate/yield trends, operation performance, work-centre utilisation and BOM consumption variance only after required source capture is available.
- Define inventory costing and build the valuation pipeline before reporting stock value or gross margin.
- Define AP liability capture before payable-ageing reports.
- Treat new data capture or migrations as separate scoped changes and test them before enabling dependent reports.

**Exit criteria:** source data measures what the report claims to measure; no capacity, value, quality, or efficiency metrics are inferred from unrelated proxies.

### Phase 4 — Accounting-grade reports and hardening (separately scoped)

- Implement or integrate chart of accounts, journals, posting controls, accounting periods, opening balances and reconciliation if the product requires a ledger.
- Only then consider trial balance, P&L, balance sheet, cash-flow statement and statutory tax returns.
- Add XLSX/PDF generation if user needs and operational load justify it.
- Add report usage telemetry, scheduled delivery only with authorization controls, and query performance budgets.

**Exit criteria:** accounting owner signs off on reconciliation and statutory mapping; report definitions are versioned and validated against controlled fixtures.

## 7. Testing and acceptance checklist

- [ ] Report is available only to authorized roles at API and UI layers.
- [ ] Token/company context limits every tenant report query.
- [ ] Empty, malformed, reversed and boundary date ranges behave predictably.
- [ ] Totals match source records for a controlled fixture, including partial receipts/deliveries and cancellations.
- [ ] Currency and quantities use explicit rounding and units.
- [ ] Pagination does not alter summary totals or omit export rows.
- [ ] Export output matches the same filtered dataset and cannot trigger spreadsheet formulas.
- [ ] Cross-tenant integration tests prove that tenant A cannot access tenant B's rows.
- [ ] Large report queries use database-side aggregation and have bounded export sizes.
- [ ] Reports disclose blocked/partial data dependencies instead of presenting fabricated values.
- [ ] Existing manufacturing report and dashboard behaviours remain covered by regression tests.
- [ ] Audit log records required sensitive exports without capturing passwords, tokens or secrets.

## 8. Release rule

A report is **implemented** only when its formula, source mapping, permissions, tests and export/drill-down behaviour are complete. A mock card or frontend table backed by demo constants is not a completed report. Financial-statement and operational-capacity reports stay blocked until their source models are capable of supporting their names.
