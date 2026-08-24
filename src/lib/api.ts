
const API_URL =
  /*import.meta.env.VITE_API_URL ?? */
  "http://localhost:8000";

/* =========================================================
   Scrap
   ========================================================= */

export interface ScrapInput {
  entry_date: string;
  product_id: string;
  batch_no: string;
  scrap_type_id: string;
  quantity: number;
  reason: string;
  remarks: string;
}

export interface ScrapData {
  id: string;
  entry_date: string;
  product_id: string;
  batch_no: string;
  scrap_type_id: string;
  quantity: number;
  reason: string;
  remarks: string;
}

/* =========================================================
   Invoices
   ========================================================= */

export type InvoiceStatus =
  | "Unpaid"
  | "Paid"
  | "Partial"
  | "Cancelled";

export interface InvoiceLineInput {
  product_id: string;
  quantity: number;
  rate: number;
  discount_percent: number;

  // null = use product master GST
  // number = custom GST for this invoice line
  gst_rate: number | null;
}

export interface InvoiceInput {
  invoice_date: string;
  customer_id: string;
  po_reference: string;
  notes: string;

  // Backend derives the final status from paid_percent.
  status: InvoiceStatus;

  // 0 to 100
  paid_percent: number;

  lines: InvoiceLineInput[];
}

export interface InvoiceLineData {
  product_id: string;
  product_name: string;
  hsn: string;
  unit: string;

  quantity: number;
  rate: number;
  discount_percent: number;

  // Actual GST rate used on the invoice
  gst_rate: number;

  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
}

export interface InvoiceData {
  id: string;
  invoice_no: string;
  invoice_date: string;

  customer_id: string;
  customer_name: string;

  po_reference: string;
  notes: string;

  inter_state: boolean;

  sub_total: number;
  discount_total: number;
  taxable_total: number;

  cgst: number;
  sgst: number;
  igst: number;

  round_off: number;
  grand_total: number;

  // Payment tracking
  paid_amount: number;
  balance_amount: number;

  status: InvoiceStatus;

  lines: InvoiceLineData[];
}

/* =========================================================
   Dashboard
   ========================================================= */

export interface ScrapReason {
  reason: string;
  quantity: number;
}

export interface ProductionSeries {
  date: string;
  label: string;
  produced: number;
  scrap: number;
}

export interface RecentProduction {
  id: string;
  batch_no: string;
  entry_date: string;
  product_name: string;
  quantity: number;
  machine: string;
  operator: string;
  shift: string;
}

export interface LowStockItem {
  id: string;
  name: string;
  stock: number;
  min_stock: number;
  unit: string;
  kind: string;
}

export interface DashboardData {
  produced_today: number;
  produced_month: number;
  scrap_month: number;
  scrap_rate: number;
  inventory_value: number;
  low_stock_count: number;

  finished_goods_quantity: number;
  finished_goods_sku_count: number;
  finished_goods_value: number;

  scrap_stock_quantity: number;
  scrap_stock_value: number;

  raw_material_value: number;
  raw_material_count: number;

  production_series: ProductionSeries[];
  low_stock_items: LowStockItem[];
  recent_production: RecentProduction[];
  top_scrap_reasons: ScrapReason[];
}

/* =========================================================
   Settings
   ========================================================= */

export interface SettingsData {
  id: number;
  name: string;
  gst_number: string;
  address: string;
  invoice_prefix: string;
  financial_year: string;
}

/* =========================================================
   Masters
   ========================================================= */

export interface ProductData {
  id: string;
  code: string;
  name: string;
  unit: string;
  hsn: string;
  cost_price: number;
  selling_price: number;
  gst_rate: number;
  min_stock: number;
  stock: number;
}

export interface MaterialData {
  id: string;
  name: string;
  unit: string;
  cost: number;
  min_stock: number;
  stock: number;
}

export interface ScrapTypeData {
  id: string;
  name: string;
  unit: string;
  selling_rate: number;
  stock: number;
}

/* =========================================================
   Production
   ========================================================= */

export interface ProductionConsumptionInput {
  material_id: string;
  quantity: number;
}

export interface ProductionInput {
  entry_date: string;
  product_id: string;
  quantity: number;
  machine: string;
  operator: string;
  shift: string;
  remarks: string;
  consumption: ProductionConsumptionInput[];
}

export interface ProductionData {
  id: string;
  batch_no: string;
  entry_date: string;
  product_id: string;
  quantity: number;
  machine: string;
  operator: string;
  shift: string;
  remarks: string;
}

/* =========================================================
   Party Data
   ========================================================= */

export interface PartyData {
  id: string;
  name: string;
  gst_number: string;
  phone: string;
  email: string;
  address: string;
  kind: string;
}

/* =========================================================
   Inventory
   ========================================================= */

export type ItemKind =
  | "product"
  | "material"
  | "scrap";

export type MovementType =
  | "IN"
  | "OUT"
  | "ADJUST";

export interface InventoryMovement {
  id: string;
  entry_date: string;
  item_kind: ItemKind;
  item_id: string;
  item_name: string;
  movement_type: MovementType;
  quantity: number;
  unit: string;
  balance: number;
  reference: string;
  reason: string;
}

export interface MovementInput {
  item_kind: ItemKind;
  item_id: string;
  movement_type: MovementType;
  quantity: number;
  reference?: string;
  reason?: string;
  entry_date?: string;
}

export interface InventoryValuation {
  finished_goods: number;
  raw_materials: number;
  scrap: number;
  total: number;
}

/* =========================================================
   Masters API
   ========================================================= */

export async function getProducts(): Promise<ProductData[]> {
  return apiFetch("/api/v1/masters/products");
}

export async function getMaterials(): Promise<MaterialData[]> {
  return apiFetch("/api/v1/masters/materials");
}

export async function getScrapTypes(): Promise<ScrapTypeData[]> {
  return apiFetch("/api/v1/masters/scrap-types");
}

export async function getCustomers(): Promise<PartyData[]> {
  return apiFetch("/api/v1/masters/customers");
}

/* =========================================================
   Production API
   ========================================================= */

export async function getProduction(): Promise<ProductionData[]> {
  return apiFetch("/api/v1/production");
}

export async function createProduction(
  payload: ProductionInput,
): Promise<ProductionData> {
  return apiFetch("/api/v1/production", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/* =========================================================
   Dashboard API
   ========================================================= */

export async function getDashboard(): Promise<DashboardData> {
  return apiFetch("/api/v1/dashboard");
}

/* =========================================================
   Settings API
   ========================================================= */

export async function getSettings(): Promise<SettingsData> {
  return apiFetch("/api/v1/settings");
}

/* =========================================================
   Inventory API
   ========================================================= */

export async function getInventoryMovements(
  limit = 200,
): Promise<InventoryMovement[]> {
  return apiFetch(
    `/api/v1/inventory/movements?limit=${limit}`,
  );
}

export async function createInventoryMovement(
  payload: MovementInput,
): Promise<InventoryMovement> {
  return apiFetch(
    "/api/v1/inventory/movements",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function getInventoryValuation(): Promise<InventoryValuation> {
  return apiFetch(
    "/api/v1/inventory/valuation",
  );
}

/* =========================================================
   Invoice API
   ========================================================= */

export async function getInvoices(
  q?: string,
): Promise<InvoiceData[]> {
  const query = q
    ? `?q=${encodeURIComponent(q)}`
    : "";

  return apiFetch(
    `/api/v1/sales/invoices${query}`,
  );
}

export async function getNextInvoiceNumber(): Promise<{
  invoice_no: string;
}> {
  return apiFetch(
    "/api/v1/sales/invoices/next-number",
  );
}

export async function getInvoice(
  invoiceId: string,
): Promise<InvoiceData> {
  return apiFetch(
    `/api/v1/sales/invoices/${invoiceId}`,
  );
}

export async function createInvoice(
  payload: InvoiceInput,
): Promise<InvoiceData> {
  return apiFetch(
    "/api/v1/sales/invoices",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/**
 * Update invoice payment status.
 *
 * Unpaid:
 *   paid_percent is ignored.
 *
 * Paid:
 *   backend sets paid_amount = grand_total.
 *
 * Partial:
 *   paid_percent is required and must be
 *   greater than 0 and less than 100.
 *
 * Cancelled:
 *   payment values remain unchanged.
 */
export async function updateInvoiceStatus(
  invoiceId: string,
  status: InvoiceStatus,
  paidPercent?: number,
): Promise<InvoiceData> {
  return apiFetch(
    `/api/v1/sales/invoices/${invoiceId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({
        status,
        paid_percent:
          paidPercent ?? 0,
      }),
    },
  );
}

/* =========================================================
   Quotations
   ========================================================= */

export type QuotationStatus =
  | "Draft"
  | "Sent"
  | "Accepted"
  | "Rejected"
  | "Expired"
  | "Converted";

export interface QuotationLineInput {
  product_id: string;
  quantity: number;
  rate: number;
  discount_percent: number;
  gst_rate: number | null;
}

export interface QuotationInput {
  quotation_date: string;
  valid_until: string | null;
  customer_id: string;
  po_reference: string;
  notes: string;
  status: QuotationStatus;
  lines: QuotationLineInput[];
}

export interface QuotationLineData {
  id: number;
  product_id: string;
  product_name: string;
  hsn: string;
  unit: string;
  quantity: number;
  rate: number;
  discount_percent: number;
  gst_rate: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
}

export interface QuotationData {
  id: string;
  quotation_no: string;
  quotation_date: string;
  valid_until: string | null;
  customer_id: string;
  customer_name: string;
  po_reference: string;
  notes: string;
  inter_state: boolean;
  sub_total: number;
  discount_total: number;
  taxable_total: number;
  cgst: number;
  sgst: number;
  igst: number;
  round_off: number;
  grand_total: number;
  status: QuotationStatus;
  created_by: string;
  lines: QuotationLineData[];
}
export interface CustomerData {
  id: string;
  name: string;
  gst_number: string;
  phone: string;
  email: string;
  address: string;
}

export async function getQuotations(): Promise<QuotationData[]> {
  return apiFetch("/api/v1/quotations");
}

export async function getNextQuotationNumber(): Promise<{
  quotation_no: string;
}> {
  return apiFetch("/api/v1/quotations/next-number");
}

export async function getQuotation(
  quotationId: string,
): Promise<QuotationData> {
  return apiFetch(
    `/api/v1/quotations/${quotationId}`,
  );
}

export async function createQuotation(
  payload: QuotationInput,
): Promise<QuotationData> {
  return apiFetch("/api/v1/quotations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateQuotationStatus(
  quotationId: string,
  status: QuotationStatus,
): Promise<QuotationData> {
  return apiFetch(
    `/api/v1/quotations/${quotationId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    },
  );
}

/* =========================================================
   Scrap API
   ========================================================= */

export async function getScrap(): Promise<ScrapData[]> {
  return apiFetch("/api/v1/scrap");
}

export async function createScrap(
  payload: ScrapInput,
): Promise<ScrapData> {
  return apiFetch(
    "/api/v1/scrap",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

/* =========================================================
   Generic API Fetch
   ========================================================= */

export async function apiFetch(
  path: string,
  options: RequestInit = {},
) {
  const token =
    localStorage.getItem(
      "minitally-token",
    );

  const headers =
    new Headers(options.headers);

  headers.set(
    "Content-Type",
    "application/json",
  );

  if (token) {
    headers.set(
      "Authorization",
      `Bearer ${token}`,
    );
  }

  const response = await fetch(
    `${API_URL}${path}`,
    {
      ...options,
      headers,
    },
  );

  if (!response.ok) {
    let message =
      `API error: ${response.status}`;

    try {
      const data =
        await response.json();

      if (
        typeof data.detail ===
        "string"
      ) {
        message =
          data.detail;
      } else if (
        Array.isArray(
          data.detail,
        )
      ) {
        message =
          data.detail
            .map(
              (
                item: {
                  msg?: string;
                },
              ) =>
                item.msg ??
                "Validation error",
            )
            .join(", ");
      }
    } catch {
      // Ignore invalid/non-JSON response
    }

    throw new Error(message);
  }

  return response.json();
}


/* =========================================================
   Sales Orders
   ========================================================= */

export interface SalesOrderLineData {
  id: number;
  product_id: string;
  product_name: string;
  hsn: string;
  unit: string;
  quantity: number;
  rate: number;
  discount_percent: number;
  gst_rate: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
  delivered_quantity: number;
}

export type SalesOrderStatus =
  | "Open"
  | "Partially Delivered"
  | "Delivered"
  | "Invoiced"
  | "Cancelled";

export interface SalesOrderData {
  id: string;
  so_no: string;
  order_date: string;
  delivery_date: string | null;
  customer_id: string;
  customer_name: string;
  notes: string;
  status: SalesOrderStatus;
  quote_id: string | null;
  quote_no: string;
  taxable_total: number;
  cgst: number;
  sgst: number;
  igst: number;
  grand_total: number;
  created_by: string;
  lines: SalesOrderLineData[];
}

export async function getSalesOrders(): Promise<
  SalesOrderData[]
> {
  return apiFetch("/api/v1/sales-orders");
}

export async function getNextSalesOrderNumber(): Promise<{
  so_no: string;
}> {
  return apiFetch(
    "/api/v1/sales-orders/next-number",
  );
}

export async function getSalesOrder(
  salesOrderId: string,
): Promise<SalesOrderData> {
  return apiFetch(
    `/api/v1/sales-orders/${salesOrderId}`,
  );
}

export async function convertQuotationToSalesOrder(
  quotationId: string,
): Promise<SalesOrderData> {
  return apiFetch(
    `/api/v1/sales-orders/from-quotation/${quotationId}`,
    {
      method: "POST",
    },
  );
}

export async function updateSalesOrderStatus(
  salesOrderId: string,
  status: SalesOrderStatus,
): Promise<SalesOrderData> {
  return apiFetch(
    `/api/v1/sales-orders/${salesOrderId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({
        status,
      }),
    },
  );
}


/* =========================================================
   Deliveries
   ========================================================= */

export interface DeliveryLineData {
  id: number;
  product_id: string;
  product_name: string;
  unit: string;
  quantity: number;
}

export interface DeliveryData {
  id: string;
  delivery_no: string;
  delivery_date: string;
  sales_order_id: string | null;
  so_no: string;
  customer_id: string;
  customer_name: string;
  vehicle_no: string;
  driver_name: string;
  lr_number: string;
  remarks: string;
  created_by: string;
  lines: DeliveryLineData[];
}

export async function getDeliveries(): Promise<
  DeliveryData[]
> {
  return apiFetch("/api/v1/deliveries");
}


/* =========================================================
   Dispatches
   ========================================================= */

export type DispatchStatus =
  | "Planned"
  | "Loading"
  | "In Transit"
  | "Delivered"
  | "Delayed";

export interface DispatchData {
  id: string;
  dispatch_no: string;
  dispatch_date: string;
  delivery_id: string | null;
  delivery_no: string;
  customer_id: string;
  customer_name: string;
  transporter: string;
  vehicle_no: string;
  driver_name: string;
  driver_phone: string;
  lr_number: string;
  status: DispatchStatus;
  delivered_on: string | null;
  pod_ref: string;
  created_by: string;
}

export interface DispatchInput {
  dispatch_date: string;
  delivery_id?: string | null;
  transporter: string;
  vehicle_no: string;
  driver_name: string;
  driver_phone: string;
  lr_number: string;
  status: DispatchStatus;
  delivered_on?: string | null;
  pod_ref: string;
}

export async function getDispatches(): Promise<
  DispatchData[]
> {
  return apiFetch("/api/v1/dispatches");
}

export async function getNextDispatchNumber(): Promise<{
  dispatch_no: string;
}> {
  return apiFetch(
    "/api/v1/dispatches/next-number",
  );
}

export async function createDispatch(
  payload: DispatchInput,
): Promise<DispatchData> {
  return apiFetch("/api/v1/dispatches", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateDispatchStatus(
  dispatchId: string,
  status: DispatchStatus,
): Promise<DispatchData> {
  return apiFetch(
    `/api/v1/dispatches/${dispatchId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({
        status,
      }),
    },
  );
}

export interface SalesOrderLineData {
  id: number;
  product_id: string;
  product_name: string;
  unit: string;
  quantity: number;
  rate: number;
  discount_percent: number;
  gst_rate: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
  delivered_quantity: number;
}

export interface DeliveryLineInput {
  product_id: string;
  quantity: number;
}

export interface DeliveryInput {
  delivery_date: string;
  sales_order_id: string;
  vehicle_no: string;
  driver_name: string;
  lr_number: string;
  remarks: string;
  lines: DeliveryLineInput[];
}

export async function createDelivery(
  payload: DeliveryInput,
) {
  return apiFetch(
    "/api/v1/deliveries",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
