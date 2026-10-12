"""Compatibility facade for SQLAlchemy models; definitions live under app.modules."""

from app.modules._base import _uuid, Role, ItemKind, MovementType, InvoiceStatus, QuotationStatus, SalesOrderStatus, DispatchStatus, PurchaseOrderStatus
from app.modules.core.models import User, Party, Product, RawMaterial, ScrapType, AuditLog, CompanySettings
from app.modules.inventory.models import InventoryMovement
from app.modules.production.models import BillOfMaterials, BomLine, ProductionEntry, ProductionConsumption, ScrapEntry, Workcenter, WorkcenterMaterial, Routing, RoutingOperation, ProductionOrder, ProductionOrderOperation
from app.modules.hr.models import Employee, EmployeeSkill
from app.modules.sales.models import Invoice, InvoiceLine, Quotation, QuotationLine, SalesOrder, SalesOrderLine, DeliveryNote, DeliveryLine, CustomerPO, CustomerPOLine
from app.modules.purchasing.models import SupplierProduct, Plant, Warehouse, PurchaseOrder, PurchaseOrderLine, GRN, GRNLine
from app.modules.finance.models import CustomerPayment, SupplierPayment
from app.modules.dispatch.models import Dispatch

__all__ = ["_uuid","Role","ItemKind","MovementType","InvoiceStatus","QuotationStatus","SalesOrderStatus","DispatchStatus","PurchaseOrderStatus","User","Party","Product","RawMaterial","BillOfMaterials","BomLine","ScrapType","InventoryMovement","ProductionEntry","ProductionConsumption","ScrapEntry","AuditLog","CompanySettings","Invoice","CustomerPayment","SupplierPayment","InvoiceLine","Quotation","QuotationLine","SalesOrder","SalesOrderLine","DeliveryNote","DeliveryLine","Dispatch","SupplierProduct","Plant","Warehouse","PurchaseOrder","PurchaseOrderLine","GRN","GRNLine","CustomerPO","CustomerPOLine","Workcenter","WorkcenterMaterial","Routing","RoutingOperation","Employee","EmployeeSkill","ProductionOrder","ProductionOrderOperation"]
