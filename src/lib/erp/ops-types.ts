/**
 * Operational domain types — PPC, design, quality, maintenance, dispatch,
 * HR, accounts, security, administration, CRM, approvals and notifications.
 * Every record is a flat, serialisable shape so the generic RecordPage engine
 * can render, create and edit it without bespoke forms.
 */

export type Severity = "Low" | "Medium" | "High" | "Critical";

/* ---------------- PPC / machines ---------------- */

export interface Machine {
  id: string;
  code: string;
  name: string;
  department: string;
  capacityPerHour: number;
  status: string; // Running | Idle | Under Maintenance | Breakdown
  installedOn: string;
}

export interface ProductionPlan {
  id: string;
  planNo: string;
  date: string;
  soNo: string;
  productName: string;
  plannedQty: number;
  producedQty: number;
  machineName: string;
  shift: string;
  startDate: string;
  dueDate: string;
  priority: string;
  status: string; // Planned | In Progress | Completed | Delayed | On Hold
}

/* ---------------- Design & development ---------------- */

export interface DesignRequest {
  id: string;
  drNo: string;
  date: string;
  customerName: string;
  productName: string;
  dieNo: string;
  version: string;
  requirement: string;
  designer: string;
  status: string; // Drafting | Internal Review | Sent to Customer | Revision | Approved | Released
  approvedBy: string;
  approvedOn: string;
}

/* ---------------- Quality ---------------- */

export interface Inspection {
  id: string;
  qcNo: string;
  date: string;
  stage: string; // Incoming | In-process | Final
  reference: string;
  itemName: string;
  inspectedQty: number;
  acceptedQty: number;
  rejectedQty: number;
  inspector: string;
  result: string; // Accepted | Rejected | Accepted with Deviation
  remarks: string;
}

export interface Ncr {
  id: string;
  ncrNo: string;
  date: string;
  source: string; // Incoming | In-process | Final | Customer
  description: string;
  severity: Severity;
  rootCause: string;
  correction: string;
  capaAction: string;
  owner: string;
  dueDate: string;
  status: string; // Open | Under Investigation | CAPA Implemented | Verified | Closed
}

export interface Complaint {
  id: string;
  complaintNo: string;
  date: string;
  customerName: string;
  invoiceNo: string;
  issue: string;
  severity: Severity;
  assignedTo: string;
  rootCause: string;
  resolution: string;
  status: string; // Open | Investigating | Resolved | Closed
  closedOn: string;
}

export interface Calibration {
  id: string;
  instrumentNo: string;
  instrument: string;
  location: string;
  lastCalibrated: string;
  nextDue: string;
  agency: string;
  certificateNo: string;
}

/* ---------------- Maintenance ---------------- */

export interface MaintenancePlan {
  id: string;
  machineName: string;
  type: string; // Preventive | Lubrication | AMC | Inspection
  frequencyDays: number;
  lastDone: string;
  nextDue: string;
  technician: string;
  checklist: string;
}

export interface Breakdown {
  id: string;
  ticketNo: string;
  date: string;
  machineName: string;
  problem: string;
  downtimeMinutes: number;
  technician: string;
  sparesUsed: string;
  cost: number;
  status: string; // Open | In Progress | Resolved
}

export interface SparePart {
  id: string;
  code: string;
  name: string;
  machineName: string;
  stock: number;
  minStock: number;
  unitCost: number;
  location: string;
}

/* ---------------- Dispatch & logistics ---------------- */

export interface Dispatch {
  id: string;
  dispatchNo: string;
  date: string;
  dnNo: string;
  customerName: string;
  transporter: string;
  vehicleNo: string;
  driverName: string;
  driverPhone: string;
  lrNumber: string;
  podRef: string;
  status: string; // Planned | Loading | In Transit | Delivered | Delayed
  deliveredOn: string;
}

/* ---------------- HR ---------------- */

export interface Employee {
  id: string;
  empCode: string;
  name: string;
  department: string;
  designation: string;
  doj: string;
  mobile: string;
  monthlySalary: number;
  skillLevel: string;
  status: string; // Active | On Notice | Exited
}

export interface AttendanceRecord {
  id: string;
  date: string;
  empCode: string;
  empName: string;
  status: string; // Present | Absent | Leave | Half Day | Week Off
  inTime: string;
  outTime: string;
  overtimeHours: number;
}

export interface LeaveRequest {
  id: string;
  empCode: string;
  empName: string;
  type: string; // Casual | Sick | Earned | Unpaid
  fromDate: string;
  toDate: string;
  days: number;
  reason: string;
  status: string; // Pending | Approved | Rejected
}

export interface TrainingRecord {
  id: string;
  date: string;
  empCode: string;
  empName: string;
  topic: string;
  trainer: string;
  hours: number;
  effectiveness: string;
}

export interface Appraisal {
  id: string;
  period: string;
  empCode: string;
  empName: string;
  rating: number;
  strengths: string;
  improvement: string;
  incrementPercent: number;
  status: string; // Draft | Reviewed | Approved
}

/* ---------------- Accounts ---------------- */

export interface Payment {
  id: string;
  voucherNo: string;
  date: string;
  direction: string; // Received | Paid
  partyType: string; // Customer | Vendor | Employee | Other
  party: string;
  reference: string;
  mode: string; // Cash | NEFT | RTGS | UPI | Cheque
  amount: number;
  remarks: string;
}

export interface Expense {
  id: string;
  voucherNo: string;
  date: string;
  category: string;
  costCenter: string;
  description: string;
  amount: number;
  paidBy: string;
  mode: string;
}

/* ---------------- Security ---------------- */

export interface GatePass {
  id: string;
  gpNo: string;
  date: string;
  direction: string; // Inward | Outward
  type: string; // Returnable | Non-Returnable
  party: string;
  itemDescription: string;
  quantity: number;
  vehicleNo: string;
  issuedBy: string;
  status: string; // Open | Returned | Closed
}

export interface Visitor {
  id: string;
  date: string;
  name: string;
  company: string;
  whomToMeet: string;
  purpose: string;
  inTime: string;
  outTime: string;
  badgeNo: string;
  vehicleNo: string;
}

/* ---------------- Administration ---------------- */

export interface Asset {
  id: string;
  assetCode: string;
  name: string;
  category: string;
  location: string;
  purchaseDate: string;
  value: number;
  custodian: string;
  status: string; // In Use | Idle | Under Repair | Scrapped
}

export interface AdminService {
  id: string;
  date: string;
  service: string; // Housekeeping | Canteen | Uniform | Office Supplies | Utility | Vehicle
  description: string;
  department: string;
  quantity: number;
  cost: number;
  handledBy: string;
  status: string;
}

/* ---------------- CRM ---------------- */

export interface Lead {
  id: string;
  enquiryNo: string;
  date: string;
  customerName: string;
  contact: string;
  productInterest: string;
  expectedQty: number;
  estimatedValue: number;
  source: string; // Referral | Website | Exhibition | Cold Call | Existing Customer
  owner: string;
  status: string; // New | Contacted | Quoted | Negotiation | Won | Lost
  nextFollowUp: string;
}

/* ---------------- Workflow & alerts ---------------- */

export interface ApprovalStage {
  role: string;
  by: string;
  decision: string; // Pending | Approved | Rejected
  on: string;
  remarks: string;
}

export interface ApprovalRequest {
  id: string;
  refNo: string;
  date: string;
  type: string; // Purchase Indent | Leave | Overtime | Price Approval | Expense | Design Release
  subject: string;
  requester: string;
  amount: number;
  currentStage: number;
  stages: ApprovalStage[];
  status: string; // Pending | Approved | Rejected
}

export interface AppNotification {
  id: string;
  at: string;
  category: string;
  severity: Severity;
  message: string;
  link: string;
  read: boolean;
}

export interface OpsState {
  machines: Machine[];
  productionPlans: ProductionPlan[];
  designRequests: DesignRequest[];
  inspections: Inspection[];
  ncrs: Ncr[];
  complaints: Complaint[];
  calibrations: Calibration[];
  maintenancePlans: MaintenancePlan[];
  breakdowns: Breakdown[];
  spares: SparePart[];
  dispatches: Dispatch[];
  employees: Employee[];
  attendance: AttendanceRecord[];
  leaves: LeaveRequest[];
  trainings: TrainingRecord[];
  appraisals: Appraisal[];
  payments: Payment[];
  expenses: Expense[];
  gatePasses: GatePass[];
  visitors: Visitor[];
  assets: Asset[];
  adminServices: AdminService[];
  leads: Lead[];
  approvals: ApprovalRequest[];
  notifications: AppNotification[];
}
