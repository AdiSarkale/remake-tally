import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type * as T from "./types";

// ---------- Auth ----------
export function useLogin() {
  return useMutation({
    mutationFn: (body: T.LoginRequest) => api.post<T.TokenResponse>("/auth/login", body),
  });
}

export function useMe(enabled = true) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<T.UserOut>("/auth/me"),
    enabled,
    staleTime: 60_000,
  });
}

// ---------- Dashboard / settings / audit ----------
export function useDashboard() {
  return useQuery({ queryKey: ["dashboard"], queryFn: () => api.get<T.DashboardOut>("/dashboard") });
}

export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => api.get<T.SettingsOut>("/settings"), retry: false });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.SettingsIn) => api.put<T.SettingsOut>("/settings", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
}

export function useAuditLog(limit = 100) {
  return useQuery({
    queryKey: ["audit", limit],
    queryFn: () => api.get<T.AuditOut[]>(`/audit?limit=${limit}`),
  });
}

// ---------- Masters ----------
function partyHooks(kind: "customers" | "suppliers") {
  const key = [kind];
  const useList = () =>
    useQuery({ queryKey: key, queryFn: () => api.get<T.PartyOut[]>(`/masters/${kind}`) });
  const useCreate = () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (body: T.PartyIn) => api.post<T.PartyOut>(`/masters/${kind}`, body),
      onSuccess: () => qc.invalidateQueries({ queryKey: key }),
    });
  };
  const useUpdate = () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: ({ id, ...body }: T.PartyIn & { id: string }) =>
        api.put<T.PartyOut>(`/masters/${kind}/${id}`, body),
      onSuccess: () => qc.invalidateQueries({ queryKey: key }),
    });
  };
  const useDelete = () => {
    const qc = useQueryClient();
    return useMutation({
      mutationFn: (id: string) => api.delete(`/masters/${kind}/${id}`),
      onSuccess: () => qc.invalidateQueries({ queryKey: key }),
    });
  };
  return { useList, useCreate, useUpdate, useDelete };
}

const customerHooks = partyHooks("customers");
const supplierHooks = partyHooks("suppliers");
export const useCustomers = customerHooks.useList;
export const useCreateCustomer = customerHooks.useCreate;
export const useUpdateCustomer = customerHooks.useUpdate;
export const useDeleteCustomer = customerHooks.useDelete;
export const useSuppliers = supplierHooks.useList;
export const useCreateSupplier = supplierHooks.useCreate;
export const useUpdateSupplier = supplierHooks.useUpdate;
export const useDeleteSupplier = supplierHooks.useDelete;

export function useProducts() {
  return useQuery({ queryKey: ["products"], queryFn: () => api.get<T.ProductOut[]>("/masters/products") });
}
export function useCreateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.ProductIn) => api.post<T.ProductOut>("/masters/products", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["products"] }),
  });
}
export function useUpdateProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.ProductIn & { id: string }) =>
      api.put<T.ProductOut>(`/masters/products/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useMaterials() {
  return useQuery({ queryKey: ["materials"], queryFn: () => api.get<T.RawMaterialOut[]>("/masters/materials") });
}
export function useCreateMaterial() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.RawMaterialIn) => api.post<T.RawMaterialOut>("/masters/materials", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["materials"] }),
  });
}

export function useScrapTypes() {
  return useQuery({ queryKey: ["scrap-types"], queryFn: () => api.get<T.ScrapTypeOut[]>("/masters/scrap-types") });
}
export function useCreateScrapType() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.ScrapTypeIn) => api.post<T.ScrapTypeOut>("/masters/scrap-types", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scrap-types"] }),
  });
}

export function usePlants() {
  return useQuery({ queryKey: ["plants"], queryFn: () => api.get<T.PlantOut[]>("/masters/plants") });
}
export function useCreatePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.PlantIn) => api.post<T.PlantOut>("/masters/plants", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plants"] }),
  });
}
export function useUpdatePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.PlantIn & { id: string }) => api.put<T.PlantOut>(`/masters/plants/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plants"] }),
  });
}
export function useDeletePlant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/masters/plants/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plants"] }),
  });
}

export function useWarehouses() {
  return useQuery({ queryKey: ["warehouses"], queryFn: () => api.get<T.WarehouseOut[]>("/masters/warehouses") });
}
export function useCreateWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.WarehouseIn) => api.post<T.WarehouseOut>("/masters/warehouses", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["warehouses"] }),
  });
}
export function useUpdateWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.WarehouseIn & { id: string }) =>
      api.put<T.WarehouseOut>(`/masters/warehouses/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["warehouses"] }),
  });
}
export function useDeleteWarehouse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/masters/warehouses/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["warehouses"] }),
  });
}

// ---------- BOM ----------
export function useBoms() {
  return useQuery({ queryKey: ["boms"], queryFn: () => api.get<T.BOMOut[]>("/bom") });
}
export function useCreateBom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.BomIn) => api.post<T.BOMOut>("/bom", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boms"] }),
  });
}
export function useUpdateBom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.BomIn & { id: string }) => api.put<T.BOMOut>(`/bom/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boms"] }),
  });
}
export function useDeleteBom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/bom/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["boms"] }),
  });
}

// ---------- Inventory ----------
export function useMovements() {
  return useQuery({ queryKey: ["movements"], queryFn: () => api.get<T.MovementOut[]>("/inventory/movements") });
}
export function useCreateMovement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.MovementIn) => api.post<T.MovementOut>("/inventory/movements", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["movements"] });
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: ["materials"] });
    },
  });
}
export function useValuation() {
  return useQuery({ queryKey: ["valuation"], queryFn: () => api.get<Record<string, unknown>>("/inventory/valuation") });
}

// ---------- Production & scrap ----------
export function useProductionEntries() {
  return useQuery({ queryKey: ["production"], queryFn: () => api.get<T.ProductionOut[]>("/production") });
}
export function useCreateProduction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.ProductionIn) => api.post<T.ProductionOut>("/production", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["production"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
export function useUpdateProductionQuality() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.ProductionQualityIn & { id: string }) =>
      api.patch<T.ProductionOut>(`/manufacturing/production/${id}/quality`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["production"] }),
  });
}

export function useScrap() {
  return useQuery({ queryKey: ["scrap"], queryFn: () => api.get<T.ScrapOut[]>("/scrap") });
}
export function useCreateScrap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.ScrapIn) => api.post<T.ScrapOut>("/scrap", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["scrap"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// ---------- Manufacturing ----------
export function useWorkcenters() {
  return useQuery({ queryKey: ["workcenters"], queryFn: () => api.get<T.WorkcenterOut[]>("/manufacturing/workcenters") });
}
export function useCreateWorkcenter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.WorkcenterIn) => api.post<T.WorkcenterOut>("/manufacturing/workcenters", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workcenters"] }),
  });
}
export function useUpdateWorkcenter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.WorkcenterIn & { id: string }) =>
      api.put<T.WorkcenterOut>(`/manufacturing/workcenters/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["workcenters"] }),
  });
}

export function useRoutings() {
  return useQuery({ queryKey: ["routings"], queryFn: () => api.get<T.RoutingOut[]>("/manufacturing/routings") });
}
export function useCreateRouting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.RoutingIn) => api.post<T.RoutingOut>("/manufacturing/routings", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["routings"] }),
  });
}

export function useEmployees() {
  return useQuery({ queryKey: ["employees"], queryFn: () => api.get<T.EmployeeOut[]>("/manufacturing/employees") });
}
export function useCreateEmployee() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.EmployeeIn) => api.post<T.EmployeeOut>("/manufacturing/employees", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["employees"] }),
  });
}
export function useEmployeeSkills(employeeId: string | null) {
  return useQuery({
    queryKey: ["employee-skills", employeeId],
    queryFn: () => api.get<T.EmployeeSkillOut[]>(`/manufacturing/employees/${employeeId}/skills`),
    enabled: !!employeeId,
  });
}
export function useAddEmployeeSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ employeeId, ...body }: T.EmployeeSkillIn & { employeeId: string }) =>
      api.post<T.EmployeeSkillOut>(`/manufacturing/employees/${employeeId}/skills`, body),
    onSuccess: (_d, v) => qc.invalidateQueries({ queryKey: ["employee-skills", v.employeeId] }),
  });
}

export function useProductionOrders() {
  return useQuery({
    queryKey: ["production-orders"],
    queryFn: () => api.get<T.ProductionOrderOut[]>("/manufacturing/production-orders"),
  });
}
export function useCreateProductionOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.ProductionOrderIn) => api.post<T.ProductionOrderOut>("/manufacturing/production-orders", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["production-orders"] }),
  });
}
export function useAssignOperation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ orderId, operationRowId, ...body }: T.AssignEmployeeIn & { orderId: string; operationRowId: string }) =>
      api.patch<T.ManufacturingAssignmentOut>(
        `/manufacturing/production-orders/${orderId}/operations/${operationRowId}/assignment`,
        body,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["production-orders"] }),
  });
}
export function useManufacturingReport() {
  return useQuery({
    queryKey: ["manufacturing-report"],
    queryFn: () => api.get<T.ManufacturingReportOut>("/manufacturing/reports/production"),
  });
}

// ---------- Sales ----------
export function useInvoices() {
  return useQuery({ queryKey: ["invoices"], queryFn: () => api.get<T.InvoiceOut[]>("/sales/invoices") });
}
export function useCreateInvoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.InvoiceIn) => api.post<T.InvoiceOut>("/sales/invoices", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["invoices"] }),
  });
}
export function useUpdateInvoiceStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.InvoiceStatusIn & { id: string }) =>
      api.patch<T.InvoiceOut>(`/sales/invoices/${id}/status`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["invoices"] });
      qc.invalidateQueries({ queryKey: ["receivables"] });
    },
  });
}

export function useQuotations() {
  return useQuery({ queryKey: ["quotations"], queryFn: () => api.get<T.QuotationOut[]>("/quotations") });
}
export function useCreateQuotation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.QuotationIn) => api.post<T.QuotationOut>("/quotations", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quotations"] }),
  });
}
export function useUpdateQuotationStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.QuotationStatusIn & { id: string }) =>
      api.patch<T.QuotationOut>(`/quotations/${id}/status`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["quotations"] }),
  });
}

export function useSalesOrders() {
  return useQuery({ queryKey: ["sales-orders"], queryFn: () => api.get<T.SalesOrderOut[]>("/sales-orders") });
}
export function useCreateSalesOrderFromQuotation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (quotationId: string) => api.post<T.SalesOrderOut>(`/sales-orders/from-quotation/${quotationId}`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sales-orders"] });
      qc.invalidateQueries({ queryKey: ["quotations"] });
    },
  });
}
export function useUpdateSalesOrderStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.SalesOrderStatusIn & { id: string }) =>
      api.patch<T.SalesOrderOut>(`/sales-orders/${id}/status`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sales-orders"] }),
  });
}

export function useDeliveries() {
  return useQuery({ queryKey: ["deliveries"], queryFn: () => api.get<T.DeliveryOut[]>("/deliveries") });
}
export function useCreateDelivery() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.DeliveryCreate) => api.post<T.DeliveryOut>("/deliveries", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deliveries"] });
      qc.invalidateQueries({ queryKey: ["sales-orders"] });
    },
  });
}

export function useDispatches() {
  return useQuery({ queryKey: ["dispatches"], queryFn: () => api.get<T.DispatchOut[]>("/dispatches") });
}
export function useCreateDispatch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.DispatchIn) => api.post<T.DispatchOut>("/dispatches", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispatches"] }),
  });
}
export function useUpdateDispatchStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.DispatchStatusIn & { id: string }) =>
      api.patch<T.DispatchOut>(`/dispatches/${id}/status`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["dispatches"] }),
  });
}

export function useCustomerPos() {
  return useQuery({ queryKey: ["customer-pos"], queryFn: () => api.get<T.CustomerPOOut[]>("/customer-pos") });
}
export function useCreateCustomerPo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.CustomerPOIn) => api.post<T.CustomerPOOut>("/customer-pos", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customer-pos"] }),
  });
}
export function useDeleteCustomerPo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/customer-pos/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customer-pos"] }),
  });
}

export function usePurchaseRequisitions() {
  return useQuery({
    queryKey: ["purchase-requisitions"],
    queryFn: () => api.get<T.PurchaseRequisitionOut[]>("/purchasing/requisitions"),
  });
}
export function useCreatePurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.PurchaseRequisitionIn) =>
      api.post<T.PurchaseRequisitionOut>("/purchasing/requisitions", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["purchase-requisitions"] }),
  });
}
export function useUpdatePurchaseRequisitionStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: T.PurchaseRequisitionStatus }) =>
      api.patch<T.PurchaseRequisitionOut>(`/purchasing/requisitions/${id}/status`, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["purchase-requisitions"] }),
  });
}

// ---------- Purchasing ----------
export function usePurchaseOrders() {
  return useQuery({ queryKey: ["purchase-orders"], queryFn: () => api.get<T.PurchaseOrderOut[]>("/purchasing/orders") });
}
export function useCreatePurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.PurchaseOrderIn) => api.post<T.PurchaseOrderOut>("/purchasing/orders", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["purchase-orders"] }),
  });
}
export function useUpdatePurchaseOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.PurchaseOrderIn & { id: string }) =>
      api.put<T.PurchaseOrderOut>(`/purchasing/orders/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["purchase-orders"] }),
  });
}

export function useGrns() {
  return useQuery({ queryKey: ["grns"], queryFn: () => api.get<T.GRNOut[]>("/purchasing/grns") });
}
export function useCreateGrn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.GRNIn) => api.post<T.GRNOut>("/purchasing/grns", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grns"] });
      qc.invalidateQueries({ queryKey: ["purchase-orders"] });
      qc.invalidateQueries({ queryKey: ["materials"] });
    },
  });
}

export function useSupplierProducts() {
  return useQuery({
    queryKey: ["supplier-products"],
    queryFn: () => api.get<T.SupplierProductOut[]>("/purchasing/supplier-products"),
  });
}
export function useCreateSupplierProduct() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.SupplierProductIn) => api.post<T.SupplierProductOut>("/purchasing/supplier-products", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["supplier-products"] }),
  });
}

// ---------- Finance ----------
export function useReceivables() {
  return useQuery({ queryKey: ["receivables"], queryFn: () => api.get<T.ReceivableOut[]>("/finance/receivables") });
}
export function usePayables() {
  return useQuery({ queryKey: ["payables"], queryFn: () => api.get<T.PayableOut[]>("/finance/payables") });
}
export function useCustomerPayments() {
  return useQuery({
    queryKey: ["customer-payments"],
    queryFn: () => api.get<T.CustomerPaymentOut[]>("/finance/customer-payments"),
  });
}
export function useCreateCustomerPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.CustomerPaymentIn) => api.post<T.CustomerPaymentOut>("/finance/customer-payments", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customer-payments"] });
      qc.invalidateQueries({ queryKey: ["receivables"] });
      qc.invalidateQueries({ queryKey: ["invoices"] });
    },
  });
}
export function useSupplierPayments() {
  return useQuery({
    queryKey: ["supplier-payments"],
    queryFn: () => api.get<T.SupplierPaymentOut[]>("/finance/supplier-payments"),
  });
}
export function useCreateSupplierPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.SupplierPaymentIn) => api.post<T.SupplierPaymentOut>("/finance/supplier-payments", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["supplier-payments"] });
      qc.invalidateQueries({ queryKey: ["payables"] });
    },
  });
}

// ---------- Users ----------
export function useUsers() {
  return useQuery({ queryKey: ["users"], queryFn: () => api.get<T.UserOut[]>("/users") });
}
export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: T.UserCreate) => api.post<T.UserOut>("/users", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}
export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: T.UserUpdate & { id: string }) => api.put<T.UserOut>(`/users/${id}`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
  });
}
export function useResetUserPassword() {
  return useMutation({
    mutationFn: ({ id, ...body }: T.PasswordReset & { id: string }) =>
      api.post(`/users/${id}/reset-password`, body),
  });
}
export function useChangePassword() {
  return useMutation({
    mutationFn: (body: T.PasswordChange) => api.post(`/users/me/change-password`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}
