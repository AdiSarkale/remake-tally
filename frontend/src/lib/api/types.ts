// TypeScript mirror of the MiniTally FastAPI backend schemas (app/schemas.py).

export type Role = "Admin" | "Accountant" | "Operator";
export type ItemKind = "product" | "material" | "scrap";
export type MovementType = "IN" | "OUT" | "ADJUST";
export type InvoiceStatus = "Unpaid" | "Paid" | "Cancelled" | "Partial";
export type QuotationStatus = "Draft" | "Sent" | "Accepted" | "Rejected" | "Expired" | "Converted";
export type SalesOrderStatus = "Open" | "Partially Delivered" | "Delivered" | "Invoiced" | "Cancelled";
export type DispatchStatus = "Planned" | "Loading" | "In Transit" | "Delivered" | "Delayed";
export type PurchaseOrderStatus = "draft" | "sent" | "partially_received" | "received";
export type QualityStatus = "Pending" | "Accepted" | "Rejected" | "Accepted with Deviation";

// ---------- Auth ----------
export interface LoginRequest {
  company_code: string;
  username: string;
  password: string;
}
export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: Role;
  full_name: string;
  company_id: string;
  company_code: string;
  company_name: string;
  must_change_password: boolean;
}
export interface UserOut {
  id: string;
  username: string;
  full_name: string;
  role: Role;
  email: string;
  active: boolean;
  must_change_password: boolean;
  company_id: string;
  company_code: string;
  company_name: string;
}
export interface UserCreate {
  username: string;
  full_name: string;
  email: string;
  role: Role;
  password?: string;
  active: boolean;
}
export interface UserUpdate {
  full_name: string;
  email: string;
  role: Role;
  active: boolean;
}
export interface PasswordReset {
  new_password: string;
}
export interface PasswordChange {
  current_password: string;
  new_password: string;
}

// ---------- Masters ----------
export interface PartyIn {
  name: string;
  gst_number: string;
  phone: string;
  email: string;
  address: string;
}
export interface PartyOut extends PartyIn {
  id: string;
  kind: string;
}
export interface ProductIn {
  code: string;
  name: string;
  unit: string;
  hsn: string;
  cost_price: number;
  selling_price: number;
  gst_rate: number;
  min_stock: number;
}
export interface ProductOut extends ProductIn {
  id: string;
  stock: number;
}
export interface RawMaterialIn {
  name: string;
  code: string;
  unit: string;
  cost: number;
  min_stock: number;
}
export interface RawMaterialOut extends RawMaterialIn {
  id: string;
  stock: number;
}
export interface ScrapTypeIn {
  code: string;
  name: string;
  unit: string;
  selling_rate: number;
  min_stock: number;
  active: boolean;
}
export interface ScrapTypeOut extends ScrapTypeIn {
  id: string;
  stock: number;
}
export interface BomLineIn {
  material_id: string;
  quantity: number;
}
export interface BomLineOut {
  id: number;
  material_id: string;
  quantity: number;
}
export interface BomIn {
  product_id: string;
  version: number;
  active: boolean;
  expected_scrap_percent: number;
  scrap_type_id: string | null;
  lines: BomLineIn[];
}
export interface BOMOut {
  id: string;
  product_id: string;
  version: number;
  active: boolean;
  expected_scrap_percent: number;
  scrap_type_id: string | null;
  lines: BomLineOut[];
}

// ---------- Inventory ----------
export interface MovementIn {
  item_kind: ItemKind;
  item_id: string;
  movement_type: MovementType;
  quantity: number;
  reference: string;
  reason: string;
  entry_date: string | null;
}
export interface MovementOut {
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

// ---------- Production ----------
export interface ConsumptionIn {
  material_id: string;
  quantity: number;
}
export interface ConsumptionOut {
  material_id: string;
  planned_quantity: number;
  quantity: number;
  variance: number;
}
export interface ProductionIn {
  entry_date: string;
  product_id: string;
  quantity: number;
  machine: string;
  workcenter_id: string | null;
  routing_id: string | null;
  operation_id: string | null;
  production_order_id: string | null;
  employee_id: string | null;
  operator: string;
  shift: string;
  remarks: string;
  consumption: ConsumptionIn[];
  scrap_type_id: string | null;
}
export interface ProductionOut {
  id: string;
  batch_no: string;
  entry_date: string;
  product_id: string;
  quantity: number;
  machine: string;
  workcenter_id: string | null;
  routing_id: string | null;
  operation_id: string | null;
  production_order_id: string | null;
  employee_id: string | null;
  operator: string;
  shift: string;
  remarks: string;
  actual_scrap: number | null;
  quality_status: string;
  accepted_qty: number;
  rejected_qty: number;
  quality_remarks: string;
  consumption: ConsumptionOut[];
}

// ---------- Scrap ----------
export interface ScrapIn {
  entry_date: string;
  product_id: string;
  batch_no: string;
  scrap_type_id: string;
  quantity: number;
  reason: string;
  remarks: string;
}
export interface ScrapOut extends ScrapIn {
  id: string;
}

// ---------- Finance ----------
export interface CustomerPaymentIn {
  payment_date: string;
  customer_id: string;
  invoice_id: string | null;
  amount: number;
  mode: string;
  reference: string;
  remarks: string;
}
export interface CustomerPaymentOut extends CustomerPaymentIn {
  id: string;
  payment_no: string;
  customer_name: string;
  invoice_no: string;
  created_by: string;
  created_at: string;
}
export interface SupplierPaymentIn {
  payment_date: string;
  supplier_id: string;
  purchase_order_id: string | null;
  amount: number;
  mode: string;
  reference: string;
  remarks: string;
}
export interface SupplierPaymentOut extends SupplierPaymentIn {
  id: string;
  payment_no: string;
  supplier_name: string;
  po_no: string;
  created_by: string;
  created_at: string;
}
export interface ReceivableOut {
  invoice_id: string;
  invoice_no: string;
  invoice_date: string;
  customer_id: string;
  customer_name: string;
  grand_total: number;
  paid_amount: number;
  balance_amount: number;
  status: InvoiceStatus;
}
export interface PayableOut {
  purchase_order_id: string;
  po_no: string;
  po_date: string;
  supplier_id: string;
  supplier_name: string;
  grand_total: number;
  paid_amount: number;
  balance_amount: number;
  status: PurchaseOrderStatus;
}

// ---------- Dashboard / settings / audit ----------
export interface ProductionSeriesOut {
  date: string;
  label: string;
  produced: number;
  scrap: number;
}
export interface RecentProductionOut {
  id: string;
  batch_no: string;
  entry_date: string;
  product_name: string;
  quantity: number;
  machine: string;
  operator: string;
  shift: string;
}
export interface LowStockOut {
  id: string;
  name: string;
  stock: number;
  min_stock: number;
  unit: string;
  kind: string;
}
export interface ScrapReasonOut {
  reason: string;
  quantity: number;
}
export interface DashboardOut {
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
  production_series: ProductionSeriesOut[];
  recent_production: RecentProductionOut[];
  low_stock_items: LowStockOut[];
  top_scrap_reasons: ScrapReasonOut[];
}
export interface AuditOut {
  id: string;
  at: string;
  username: string;
  action: string;
  entity: string;
  detail: string;
}
export interface SettingsIn {
  name: string;
  gst_number: string | null;
  address: string | null;
  invoice_prefix: string;
  financial_year: string;
}
export interface SettingsOut extends SettingsIn {
  id: number;
}

// ---------- Sales ----------
export interface InvoiceLineIn {
  product_id: string;
  quantity: number;
  rate: number;
  discount_percent: number;
  gst_rate: number | null;
}
export interface InvoiceLineOut {
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
export interface InvoiceIn {
  invoice_date: string;
  customer_id: string;
  po_reference: string;
  notes: string;
  status: InvoiceStatus;
  paid_percent: number;
  lines: InvoiceLineIn[];
}
export interface InvoiceOut {
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
  paid_amount: number;
  balance_amount: number;
  status: InvoiceStatus;
  lines: InvoiceLineOut[];
}
export interface InvoiceStatusIn {
  status: InvoiceStatus;
  paid_percent: number;
}
export interface QuotationLineIn {
  product_id: string;
  quantity: number;
  rate: number;
  discount_percent: number;
  gst_rate: number | null;
}
export interface QuotationLineOut extends QuotationLineIn {
  id: number;
  product_name: string;
  hsn: string;
  unit: string;
  gst_rate: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
}
export interface QuotationIn {
  quotation_date: string;
  valid_until: string | null;
  customer_id: string;
  po_reference: string;
  notes: string;
  status: QuotationStatus;
  lines: QuotationLineIn[];
}
export interface QuotationOut {
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
  lines: QuotationLineOut[];
}
export interface QuotationStatusIn {
  status: QuotationStatus;
}
export interface SalesOrderLineOut {
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
export interface SalesOrderOut {
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
  lines: SalesOrderLineOut[];
}
export interface SalesOrderStatusIn {
  status: SalesOrderStatus;
}
export interface DeliveryLineIn {
  product_id: string;
  quantity: number;
}
export interface DeliveryCreate {
  delivery_date: string;
  sales_order_id: string;
  vehicle_no: string;
  driver_name: string;
  lr_number: string;
  remarks: string;
  lines: DeliveryLineIn[];
}
export interface DeliveryLineOut {
  id: number;
  product_id: string;
  product_name: string;
  unit: string;
  quantity: number;
}
export interface DeliveryOut {
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
  lines: DeliveryLineOut[];
}
export interface DispatchIn {
  dispatch_date: string;
  delivery_id: string | null;
  transporter: string;
  vehicle_no: string;
  driver_name: string;
  driver_phone: string;
  lr_number: string;
  status: DispatchStatus;
  delivered_on: string | null;
  pod_ref: string;
}
export interface DispatchUpdateIn {
  transporter: string;
  vehicle_no: string;
  driver_name: string;
  driver_phone: string;
  lr_number: string;
  status: DispatchStatus;
  delivered_on: string | null;
  pod_ref: string;
}
export interface DispatchStatusIn {
  status: DispatchStatus;
}
export interface DispatchOut {
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

export type PurchaseRequisitionStatus = "draft" | "submitted" | "approved" | "rejected" | "converted";
export type PurchaseRequisitionSource = "manual" | "mrp";

export interface PurchaseRequisitionLineIn {
  material_id: string;
  material_name: string;
  quantity: number;
  required_date: string | null;
  notes: string;
}

export interface PurchaseRequisitionLineOut extends PurchaseRequisitionLineIn {
  id: number;
}

export interface PurchaseRequisitionIn {
  pr_no: string;
  pr_date: string;
  required_date: string | null;
  requested_by: string;
  department: string;
  priority: string;
  warehouse_id: string | null;
  notes: string;
  source: PurchaseRequisitionSource;
  source_reference: string;
  status: PurchaseRequisitionStatus;
  lines: PurchaseRequisitionLineIn[];
}

export interface PurchaseRequisitionOut extends PurchaseRequisitionIn {
  id: string;
  created_by: string;
  lines: PurchaseRequisitionLineOut[];
}

// ---------- Purchasing / locations / customer POs ----------
export interface SupplierProductIn {
  supplier_id: string;
  product_id: string;
  supplier_code: string;
  purchase_rate: number;
  minimum_order_qty: number;
  lead_time_days: number;
}
export interface SupplierProductOut extends SupplierProductIn {
  id: string;
}
export interface PlantIn {
  code: string;
  name: string;
  location: string;
  active: boolean;
}
export interface PlantOut extends PlantIn {
  id: string;
}
export interface WarehouseIn {
  code: string;
  name: string;
  plant_id: string;
  active: boolean;
}
export interface WarehouseOut extends WarehouseIn {
  id: string;
}
export interface PurchaseOrderLineIn {
  material_id: string | null;
  material_name: string;
  quantity: number;
  rate: number;
  gst_rate: number;
  received_quantity: number;
  tax: number;
  total: number;
}
export interface PurchaseOrderLineOut extends PurchaseOrderLineIn {
  id: number;
}
export interface PurchaseOrderIn {
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
  lines: PurchaseOrderLineIn[];
}
export interface PurchaseOrderOut extends PurchaseOrderIn {
  id: string;
  created_by: string;
  lines: PurchaseOrderLineOut[];
}
export interface GRNLineIn {
  material_id: string;
  material_name: string;
  quantity: number;
  batch_no: string;
}
export interface GRNLineOut extends GRNLineIn {
  id: number;
}
export interface GRNIn {
  grn_no: string;
  grn_date: string;
  purchase_order_id: string;
  po_no: string;
  warehouse_id: string;
  lines: GRNLineIn[];
}
export interface GRNOut extends GRNIn {
  id: string;
  lines: GRNLineOut[];
}
export interface CustomerPOLineIn {
  product_id: string | null;
  product_name: string;
  quantity: number;
  rate: number | null;
}
export interface CustomerPOLineOut extends CustomerPOLineIn {
  id: number;
}
export interface CustomerPOIn {
  po_no: string;
  po_date: string;
  customer_id: string;
  customer_name: string;
  delivery_date: string | null;
  lines: CustomerPOLineIn[];
}
export interface CustomerPOOut extends CustomerPOIn {
  id: string;
  lines: CustomerPOLineOut[];
}

// ---------- Manufacturing execution ----------
export interface WorkcenterMaterialIn {
  item_kind: "RM" | "SF" | "FG";
  item_id: string;
  operation_id: string | null;
}
export interface WorkcenterMaterialOut {
  id: string;
  workcenter_id: string;
  item_kind: string;
  item_id: string;
  operation_id: string | null;
}
export interface WorkcenterIn {
  code: string;
  name: string;
  department: string;
  capacity_per_hour: number;
  status: string;
  active: boolean;
  location: string;
  materials: WorkcenterMaterialIn[];
}
export interface WorkcenterOut {
  id: string;
  code: string;
  name: string;
  department: string;
  capacity_per_hour: number;
  status: string;
  active: boolean;
  location: string;
  materials: WorkcenterMaterialOut[];
}
export interface RoutingOperationIn {
  sequence: number;
  code: string;
  name: string;
  workcenter_id: string;
  required_skill: string;
  setup_minutes: number;
  run_minutes_per_unit: number;
  active: boolean;
}
export interface RoutingIn {
  product_id: string;
  version: number;
  name: string;
  active: boolean;
  operations: RoutingOperationIn[];
}
export interface RoutingOperationOut {
  id: string;
  sequence: number;
  code: string;
  name: string;
  workcenter_id: string;
  required_skill: string;
  setup_minutes: number;
  run_minutes_per_unit: number;
  active: boolean;
}
export interface RoutingOut {
  id: string;
  product_id: string;
  version: number;
  name: string;
  active: boolean;
  operations: RoutingOperationOut[];
}
export type EmployeeType = "shop_floor" | "staff";
export interface EmployeeIn {
  emp_code: string;
  name: string;
  employee_type: EmployeeType;
  department: string;
  designation: string;
  active: boolean;
}
export interface EmployeeSkillIn {
  skill: string;
  level: number;
  certified: boolean;
  active: boolean;
}
export interface EmployeeOut {
  id: string;
  emp_code: string;
  name: string;
  employee_type: EmployeeType;
  department: string;
  designation: string;
  active: boolean;
}
export interface EmployeeSkillOut {
  id: string;
  employee_id: string;
  skill: string;
  level: number;
  certified: boolean;
  active: boolean;
}
export interface ProductionOrderIn {
  order_date: string;
  product_id: string;
  quantity: number;
  due_date: string | null;
  routing_id: string | null;
  remarks: string;
}
export interface ProductionOrderOperationOut {
  id: string;
  operation_id: string;
  sequence: number;
  workcenter_id: string;
  assigned_employee_id: string | null;
  status: string;
  planned_qty: number;
  completed_qty: number;
}
export interface ProductionOrderOut {
  id: string;
  order_no: string;
  order_date: string;
  product_id: string;
  quantity: number;
  due_date: string | null;
  routing_id: string | null;
  status: string;
  remarks: string;
  operations: ProductionOrderOperationOut[];
}
export interface AssignEmployeeIn {
  employee_id: string | null;
}
export interface ManufacturingAssignmentOut {
  operation_id: string;
  workcenter_id: string;
  employee_id: string | null;
  assignment_mode: string;
}
export interface ProductionQualityIn {
  status: QualityStatus;
  accepted_qty: number;
  rejected_qty: number;
  remarks: string;
}
export interface ManufacturingReportOut {
  production_qty: number;
  scrap_qty: number;
  planned_material_qty: number;
  actual_material_qty: number;
  material_variance: number;
  by_workcenter: Record<string, unknown>[];
}
