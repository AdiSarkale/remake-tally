/* eslint-disable prettier/prettier */

const API_URL =
  import.meta.env.VITE_API_URL ?? "http://localhost:8000";


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
  | "unpaid"
  | "paid"
  | "partial"
  | "cancelled";

export interface InvoiceLineInput {
  product_id: string;
  quantity: number;
  rate: number;
  discount_percent: number;
}

export interface InvoiceInput {
  invoice_date: string;
  customer_id: string;
  po_reference: string;
  notes: string;
  status: InvoiceStatus;
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
   Inventory
   ========================================================= */

export type ItemKind = "product" | "material" | "scrap";

export type MovementType = "IN" | "OUT" | "ADJUST";

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
  return apiFetch(`/api/v1/inventory/movements?limit=${limit}`);
}

export async function createInventoryMovement(
  payload: MovementInput,
): Promise<InventoryMovement> {
  return apiFetch("/api/v1/inventory/movements", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getInventoryValuation(): Promise<InventoryValuation> {
  return apiFetch("/api/v1/inventory/valuation");
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

  return apiFetch(`/api/v1/sales/invoices${query}`);
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
  return apiFetch("/api/v1/sales/invoices", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateInvoiceStatus(
  invoiceId: string,
  status: InvoiceStatus,
): Promise<InvoiceData> {
  return apiFetch(
    `/api/v1/sales/invoices/${invoiceId}/status`,
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
  return apiFetch("/api/v1/scrap", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}


/* =========================================================
   Parties / Masters
   ========================================================= */

export interface PartyData {
  id: string;
  kind: "customer" | "supplier" | string;
  name: string;
  gst_number: string;
  phone: string;
  email: string;
  address: string;
}

export interface PlantData {
  id: string;
  code: string;
  name: string;
  location: string;
  active: boolean;
}

export interface WarehouseData {
  id: string;
  plant_id: string;
  code: string;
  name: string;
  location: string;
  active: boolean;
}

export interface SupplierProductData {
  id: number;
  supplier_id: string;
  product_id: string;
  supplier_code: string;
  purchase_rate: number;
  minimum_order_qty: number;
  lead_time_days: number;
  active: boolean;
}

export async function getCustomers(): Promise<PartyData[]> {
  return apiFetch("/api/v1/masters/customers");
}

export async function getSuppliers(): Promise<PartyData[]> {
  return apiFetch("/api/v1/masters/suppliers");
}

export async function getPlants(): Promise<PlantData[]> {
  return apiFetch("/api/v1/locations/plants");
}

export async function getWarehouses(
  plantId?: string,
): Promise<WarehouseData[]> {
  const query = plantId
    ? `?plant_id=${encodeURIComponent(plantId)}`
    : "";
  return apiFetch(`/api/v1/locations/warehouses${query}`);
}

export async function getSupplierProducts(
  supplierId?: string,
): Promise<SupplierProductData[]> {
  const query = supplierId
    ? `?supplier_id=${encodeURIComponent(supplierId)}`
    : "";
  return apiFetch(`/api/v1/purchasing/supplier-products${query}`);
}

/* =========================================================
   Customer PO lookup
   ========================================================= */

export interface CustomerPOLineData {
  id: number;
  product_id: string;
  product_name: string;
  quantity: number;
  rate: number | null;
  notes: string;
}

export interface CustomerPOData {
  id: string;
  po_no: string;
  po_date: string;
  customer_id: string;
  customer_name: string;
  delivery_date: string | null;
  notes: string;
  lines: CustomerPOLineData[];
}

export async function lookupCustomerPO(
  poReference: string,
): Promise<CustomerPOData> {
  return apiFetch(
    `/api/v1/sales/customer-pos/lookup/${encodeURIComponent(poReference)}`,
  );
}

/* =========================================================
   Purchase Orders / GRN
   ========================================================= */

export type PurchaseOrderStatus =
  | "Draft"
  | "Sent"
  | "Partially Received"
  | "Received"
  | "Cancelled";

export interface PurchaseOrderLineData {
  id: number;
  material_id: string;
  material_name: string;
  unit: string;
  quantity: number;
  received_quantity: number;
  rate: number;
  gst_rate: number;
  taxable: number;
  tax: number;
  total: number;
}

export interface PurchaseOrderData {
  id: string;
  po_no: string;
  po_date: string;
  expected_date: string | null;
  supplier_id: string;
  supplier_name: string;
  warehouse_id: string | null;
  notes: string;
  status: PurchaseOrderStatus;
  sub_total: number;
  gst_total: number;
  grand_total: number;
  created_by: string;
  lines: PurchaseOrderLineData[];
}

export interface GRNLineData {
  id: number;
  material_id: string;
  material_name: string;
  unit: string;
  quantity: number;
  batch_no: string;
}

export interface GRNData {
  id: string;
  grn_no: string;
  grn_date: string;
  purchase_order_id: string;
  po_no: string;
  supplier_id: string;
  supplier_name: string;
  warehouse_id: string;
  remarks: string;
  created_by: string;
  lines: GRNLineData[];
}

export interface PurchaseOrderLineInput {
  material_id: string;
  quantity: number;
  rate: number;
  gst_rate: number;
}

export interface PurchaseOrderInput {
  po_date: string;
  expected_date: string | null;
  supplier_id: string;
  warehouse_id: string | null;
  notes: string;
  lines: PurchaseOrderLineInput[];
}

export async function getPurchaseOrders(): Promise<PurchaseOrderData[]> {
  return apiFetch("/api/v1/purchasing/orders");
}

export async function createPurchaseOrder(
  payload: PurchaseOrderInput,
): Promise<PurchaseOrderData> {
  return apiFetch("/api/v1/purchasing/orders", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updatePurchaseOrderStatus(
  purchaseOrderId: string,
  status: PurchaseOrderStatus,
): Promise<PurchaseOrderData> {
  return apiFetch(
    `/api/v1/purchasing/orders/${purchaseOrderId}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    },
  );
}

export async function getGRNs(): Promise<GRNData[]> {
  return apiFetch("/api/v1/purchasing/grns");
}

export interface GRNInput {
  grn_date: string;
  purchase_order_id: string;
  warehouse_id: string;
  remarks: string;
  lines: {
    material_id: string;
    quantity: number;
    batch_no: string;
  }[];
}

export async function createGRN(
  payload: GRNInput,
): Promise<GRNData> {
  return apiFetch("/api/v1/purchasing/grns", {
    method: "POST",
    body: JSON.stringify(payload),
  });
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

export async function getSalesOrders(): Promise<SalesOrderData[]> {
  return apiFetch("/api/v1/sales-orders");
}

export async function getSalesOrder(
  salesOrderId: string,
): Promise<SalesOrderData> {
  return apiFetch(`/api/v1/sales-orders/${salesOrderId}`);
}

export async function convertQuotationToSalesOrder(
  quotationId: string,
): Promise<SalesOrderData> {
  return apiFetch(
    `/api/v1/sales-orders/from-quotation/${quotationId}`,
    { method: "POST" },
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

export interface DeliveryInput {
  delivery_date: string;
  sales_order_id: string;
  vehicle_no: string;
  driver_name: string;
  lr_number: string;
  remarks: string;
  lines: { product_id: string; quantity: number }[];
}

export async function getDeliveries(): Promise<DeliveryData[]> {
  return apiFetch("/api/v1/deliveries");
}

export async function createDelivery(
  payload: DeliveryInput,
): Promise<DeliveryData> {
  return apiFetch("/api/v1/deliveries", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/* =========================================================
   Dispatch
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
  delivery_id: string;
  transporter: string;
  vehicle_no: string;
  driver_name: string;
  driver_phone: string;
  lr_number: string;
  status: DispatchStatus;
  delivered_on?: string | null;
  pod_ref: string;
}

export interface DispatchUpdateInput {
  transporter: string;
  vehicle_no: string;
  driver_name: string;
  driver_phone: string;
  lr_number: string;
  status: DispatchStatus;
  delivered_on?: string | null;
  pod_ref: string;
}

export async function getDispatches(): Promise<DispatchData[]> {
  return apiFetch("/api/v1/dispatches");
}

export async function getNextDispatchNumber(): Promise<{ dispatch_no: string }> {
  return apiFetch("/api/v1/dispatches/next-number");
}

export async function createDispatch(
  payload: DispatchInput,
): Promise<DispatchData> {
  return apiFetch("/api/v1/dispatches", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateDispatch(
  dispatchId: string,
  payload: DispatchUpdateInput,
): Promise<DispatchData> {
  return apiFetch(`/api/v1/dispatches/${dispatchId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

/* =========================================================
   Generic API Fetch
   ========================================================= */

export async function apiFetch(
  path: string,
  options: RequestInit = {},
) {
  const token = localStorage.getItem("minitally-token");

  const headers = new Headers(options.headers);

  headers.set("Content-Type", "application/json");

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let message = `API error: ${response.status}`;

    try {
      const data = await response.json();

      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail
          .map((item: { msg?: string }) => item.msg ?? "Validation error")
          .join(", ");
      }
    } catch {
      // Ignore invalid/non-JSON response
    }

    throw new Error(message);
  }

  return response.json();
}
