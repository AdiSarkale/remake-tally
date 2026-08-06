import type { DocState } from "./doc-types";
import type { OpsState } from "./ops-types";

export type Role = "Admin" | "Accountant" | "Operator";

export interface User {
  id: string;
  username: string;
  fullName: string;
  email: string;
  role: Role;
  password: string; // demo-only; the FastAPI backend stores a bcrypt hash
  active: boolean;
}

export interface Customer {
  id: string;
  name: string;
  gstNumber: string;
  mobile: string;
  email: string;
  address: string;
}

export interface Supplier {
  id: string;
  name: string;
  gstNumber: string;
  contact: string;
  address: string;
}

export interface Product {
  id: string;
  code: string;
  name: string;
  category: string;
  unit: string;
  sellingPrice: number;
  costPrice: number;
  hsnCode: string;
  gstPercent: number;
  minStock: number;
  stock: number;
}

export interface RawMaterial {
  id: string;
  name: string;
  unit: string;
  cost: number;
  stock: number;
  minStock: number;
}

export interface ScrapType {
  id: string;
  name: string;
  unit: string;
  sellingRate: number;
  stock: number;
}

export type ItemKind = "product" | "material" | "scrap";
export type MovementType = "IN" | "OUT" | "ADJUST";

export interface InventoryMovement {
  id: string;
  date: string;
  itemKind: ItemKind;
  itemId: string;
  itemName: string;
  type: MovementType;
  quantity: number;
  unit: string;
  balance: number;
  reference: string;
  reason: string;
  userId: string;
}

export interface ProductionConsumption {
  materialId: string;
  materialName: string;
  quantity: number;
  unit: string;
}

export interface ProductionEntry {
  id: string;
  batchNo: string;
  date: string;
  productId: string;
  productName: string;
  quantity: number;
  machine: string;
  operator: string;
  shift: "A" | "B" | "C";
  remarks: string;
  consumption: ProductionConsumption[];
}

export interface ScrapEntry {
  id: string;
  date: string;
  productId: string;
  productName: string;
  batchNo: string;
  scrapTypeId: string;
  scrapTypeName: string;
  quantity: number;
  reason: string;
  remarks: string;
}

export interface InvoiceLine {
  productId: string;
  productName: string;
  hsnCode: string;
  unit: string;
  quantity: number;
  rate: number;
  discountPercent: number;
  gstPercent: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
}

export type InvoiceStatus = "Paid" | "Unpaid";

export interface Invoice {
  id: string;
  invoiceNo: string;
  date: string;
  customerId: string;
  customerName: string;
  customerGst: string;
  customerAddress: string;
  placeOfSupply: string;
  interState: boolean;
  poReference: string;
  notes: string;
  lines: InvoiceLine[];
  subTotal: number;
  discountTotal: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  roundOff: number;
  grandTotal: number;
  status: InvoiceStatus;
  createdBy: string;
}

export interface AuditLog {
  id: string;
  at: string;
  user: string;
  action: string;
  entity: string;
  detail: string;
}

export interface CompanySettings {
  name: string;
  gstNumber: string;
  address: string;
  invoicePrefix: string;
  financialYear: string;
}

export interface ErpState extends DocState {
  users: User[];
  customers: Customer[];
  suppliers: Supplier[];
  products: Product[];
  materials: RawMaterial[];
  scrapTypes: ScrapType[];
  movements: InventoryMovement[];
  production: ProductionEntry[];
  scrap: ScrapEntry[];
  invoices: Invoice[];
  audit: AuditLog[];
  settings: CompanySettings;
}

export const ROLE_PERMISSIONS: Record<Role, string[]> = {
  Admin: [
    "masters",
    "inventory",
    "production",
    "scrap",
    "sales",
    "procurement",
    "logistics",
    "settings",
    "reports",
  ],
  Accountant: ["masters", "inventory", "sales", "procurement", "reports"],
  Operator: ["production", "scrap", "inventory", "logistics"],
};

export function can(role: Role, area: string) {
  return ROLE_PERMISSIONS[role].includes(area);
}

