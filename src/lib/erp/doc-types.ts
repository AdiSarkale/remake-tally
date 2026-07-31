/** Document-flow domain types: procurement, sales cycle, transfers, FOC, job work. */

export interface Warehouse {
  id: string;
  code: string;
  name: string;
  location: string;
}

export type Priority = "Low" | "Normal" | "High" | "Urgent";
export type PrStatus = "Pending" | "Approved" | "Rejected" | "Converted to PO";

export interface PurchaseRequisition {
  id: string;
  prNo: string;
  date: string;
  department: string;
  requester: string;
  materialId: string;
  materialName: string;
  quantity: number;
  unit: string;
  priority: Priority;
  requiredDate: string;
  reason: string;
  status: PrStatus;
  approvedBy?: string | undefined;
  poId?: string | undefined;
  poNo?: string | undefined;
}

export type PoStatus = "Draft" | "Approved" | "Partially Received" | "Completed" | "Cancelled";

export interface PoLine {
  materialId: string;
  materialName: string;
  unit: string;
  quantity: number;
  receivedQty: number;
  rate: number;
  gstPercent: number;
  taxable: number;
  tax: number;
  total: number;
}

export interface GoodsReceipt {
  id: string;
  grnNo: string;
  date: string;
  poId: string;
  poNo: string;
  warehouseId: string;
  lines: { materialId: string; materialName: string; quantity: number; batchNo: string }[];
  remarks: string;
}

export interface PurchaseOrder {
  id: string;
  poNo: string;
  supplierId: string;
  supplierName: string;
  date: string;
  expectedDate: string;
  paymentTerms: string;
  warehouseId: string;
  status: PoStatus;
  prIds: string[];
  prNos: string[];
  lines: PoLine[];
  subTotal: number;
  tax: number;
  grandTotal: number;
}

export interface SalesDocLine {
  productId: string;
  productName: string;
  unit: string;
  quantity: number;
  rate: number;
  gstPercent: number;
  taxable: number;
  tax: number;
  total: number;
}

export type QuoteStatus = "Draft" | "Sent" | "Accepted" | "Rejected" | "Converted to SO";

export interface Quotation {
  id: string;
  quoteNo: string;
  date: string;
  validUntil: string;
  customerId: string;
  customerName: string;
  notes: string;
  status: QuoteStatus;
  lines: SalesDocLine[];
  taxable: number;
  tax: number;
  grandTotal: number;
  soId?: string | undefined;
  soNo?: string | undefined;
}

export type SoStatus = "Open" | "Partially Delivered" | "Delivered" | "Invoiced" | "Cancelled";

export interface SalesOrderLine extends SalesDocLine {
  deliveredQty: number;
}

export interface SalesOrder {
  id: string;
  soNo: string;
  date: string;
  deliveryDate: string;
  customerId: string;
  customerName: string;
  notes: string;
  status: SoStatus;
  lines: SalesOrderLine[];
  taxable: number;
  tax: number;
  grandTotal: number;
  quoteId?: string | undefined;
  quoteNo?: string | undefined;
  deliveryNos: string[];
  invoiceNo?: string | undefined;
}

export interface DeliveryNote {
  id: string;
  dnNo: string;
  date: string;
  soId?: string | undefined;
  soNo?: string | undefined;
  customerId: string;
  customerName: string;
  warehouseId: string;
  vehicleNo: string;
  driverName: string;
  lrNumber: string;
  remarks: string;
  foc: boolean;
  focPurpose?: string | undefined;
  lines: { productId: string; productName: string; unit: string; quantity: number; rate: number }[];
  invoiceNo?: string | undefined;
}

export interface MaterialTransfer {
  id: string;
  transferNo: string;
  date: string;
  sourceId: string;
  sourceName: string;
  destId: string;
  destName: string;
  itemKind: "product" | "material" | "scrap";
  itemId: string;
  itemName: string;
  quantity: number;
  unit: string;
  batchNo: string;
  vehicle: string;
  remarks: string;
}

export type JobWorkStatus = "At Vendor" | "Partially Received" | "Closed";

export interface JobWorkReceipt {
  id: string;
  date: string;
  productId: string;
  productName: string;
  productQty: number;
  scrapTypeId: string;
  scrapTypeName: string;
  scrapQty: number;
  remarks: string;
}

export interface JobWork {
  id: string;
  jwNo: string;
  date: string;
  vendorId: string;
  vendorName: string;
  process: string;
  materialId: string;
  materialName: string;
  unit: string;
  quantity: number;
  expectedDate: string;
  warehouseId: string;
  status: JobWorkStatus;
  remarks: string;
  receipts: JobWorkReceipt[];
}

/** itemId -> warehouseId -> quantity */
export type WarehouseStock = Record<string, Record<string, number>>;

export interface DocState {
  warehouses: Warehouse[];
  warehouseStock: WarehouseStock;
  requisitions: PurchaseRequisition[];
  purchaseOrders: PurchaseOrder[];
  receipts: GoodsReceipt[];
  quotations: Quotation[];
  salesOrders: SalesOrder[];
  deliveries: DeliveryNote[];
  transfers: MaterialTransfer[];
  jobWorks: JobWork[];
}
