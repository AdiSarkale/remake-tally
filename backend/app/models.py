"""Compatibility facade for SQLAlchemy models; definitions live under app.modules."""

from app.db.session import Base
from app.modules._base import _uuid, Role, ItemKind, EmployeeType, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseRequisitionStatus, PurchaseRequisitionSource, PurchaseOrderStatus
from app.modules.core.models import User, Party, Product, RawMaterial, ScrapType, AuditLog, CompanySettings
from app.modules.core.authorization import EmployeeUserLink, RolePermissionGrant
from app.modules.inventory.models import InventoryMovement
from app.modules.production.models import BillOfMaterials, BomLine, ProductionEntry, ProductionConsumption, ScrapEntry, Workcenter, WorkcenterMaterial, Routing, RoutingOperation, ProductionOrder, ProductionOrderOperation
from app.modules.hr.models import Employee, EmployeeCodeConfig, EmployeeTypeDefinition, EmployeeSkill, HRBranch, EmployeeOrgAssignment
from app.modules.hr.payroll import HRPayrollSettings, HRCalendarDay, EmployeeSalaryProfile, EmployeeAttendance, HRAttendanceImportBatch, HRAttendanceEvent, HRPayrollRun, HRPayrollItem, HRWorkforcePolicyVersion, HRShiftType, HRShiftBreakRule, HRShiftAssignment, HRShiftRosterEntry, HRShiftRosterEntryHistory
from app.modules.hr.leave import HRLeaveType, HRLeaveBalance, HRLeaveRequest, HRLeaveAccrualLedger
from app.modules.sales.models import Invoice, InvoiceLine, Quotation, QuotationLine, SalesOrder, SalesOrderLine, DeliveryNote, DeliveryLine, CustomerPO, CustomerPOLine
from app.modules.purchasing.models import PurchaseRequisition, PurchaseRequisitionLine, SupplierProduct, Plant, Warehouse, PurchaseOrder, PurchaseOrderLine, GRN, GRNLine
from app.modules.finance.models import CustomerPayment, SupplierPayment, FinanceAccount, FinanceJournalEntry, FinanceJournalLine, FinancePayrollAccountMapping
from app.modules.dispatch.models import Dispatch

__all__ = ["Base", "_uuid","Role","ItemKind","EmployeeType","MovementType","InvoiceStatus","QuotationStatus","SalesOrderStatus","DispatchStatus","PurchaseRequisitionStatus","PurchaseRequisitionSource","PurchaseOrderStatus","User","Party","Product","RawMaterial","BillOfMaterials","BomLine","ScrapType","InventoryMovement","ProductionEntry","ProductionConsumption","ScrapEntry","AuditLog","CompanySettings","Invoice","CustomerPayment","SupplierPayment","FinanceAccount","FinanceJournalEntry","FinanceJournalLine","FinancePayrollAccountMapping","InvoiceLine","Quotation","QuotationLine","SalesOrder","SalesOrderLine","DeliveryNote","DeliveryLine","Dispatch","PurchaseRequisition","PurchaseRequisitionLine","SupplierProduct","Plant","Warehouse","PurchaseOrder","PurchaseOrderLine","GRN","GRNLine","CustomerPO","CustomerPOLine","Workcenter","WorkcenterMaterial","Routing","RoutingOperation","Employee","EmployeeCodeConfig","EmployeeTypeDefinition","EmployeeSkill","HRBranch","EmployeeOrgAssignment","ProductionOrder","ProductionOrderOperation","HRPayrollSettings","HRCalendarDay","EmployeeSalaryProfile","EmployeeAttendance","HRAttendanceImportBatch","HRAttendanceEvent","HRPayrollRun","HRPayrollItem","HRWorkforcePolicyVersion","HRShiftType","HRShiftBreakRule","HRShiftAssignment","HRShiftRosterEntry","HRShiftRosterEntryHistory","EmployeeUserLink","RolePermissionGrant","HRLeaveType","HRLeaveBalance","HRLeaveRequest","HRLeaveAccrualLedger"]
