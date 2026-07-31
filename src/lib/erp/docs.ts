/** Procurement, sales-cycle, transfer, FOC and job-work actions. */
import type {
  DeliveryNote,
  GoodsReceipt,
  JobWork,
  MaterialTransfer,
  PoLine,
  PurchaseOrder,
  PurchaseRequisition,
  Quotation,
  SalesDocLine,
  SalesOrder,
  SalesOrderLine,
} from "./doc-types";
import type { ErpState } from "./types";
import { applyMovement, logAudit, today, uid, update } from "./store";

const r2 = (n: number) => Math.round(n * 100) / 100;

/* ---------------- document numbering ---------------- */

export const DOC_PREFIX = {
  PR: "PR",
  PO: "PO",
  GRN: "GRN",
  QT: "QT",
  SO: "SO",
  DN: "DN",
  FOC: "FOC",
  TR: "TR",
  JW: "JW",
} as const;

export type DocKind = keyof typeof DOC_PREFIX;

function existingNumbers(s: ErpState, kind: DocKind): string[] {
  switch (kind) {
    case "PR":
      return s.requisitions.map((d) => d.prNo);
    case "PO":
      return s.purchaseOrders.map((d) => d.poNo);
    case "GRN":
      return s.receipts.map((d) => d.grnNo);
    case "QT":
      return s.quotations.map((d) => d.quoteNo);
    case "SO":
      return s.salesOrders.map((d) => d.soNo);
    case "DN":
    case "FOC":
      return s.deliveries.map((d) => d.dnNo);
    case "TR":
      return s.transfers.map((d) => d.transferNo);
    case "JW":
      return s.jobWorks.map((d) => d.jwNo);
  }
}

/** `PR-2026-00001` — sequential per document type and calendar year. */
export function nextDocNo(s: ErpState, kind: DocKind, date = today()) {
  const prefix = DOC_PREFIX[kind];
  const year = date.slice(0, 4);
  const head = `${prefix}-${year}-`;
  const nums = existingNumbers(s, kind)
    .filter((n) => n.startsWith(head))
    .map((n) => Number(n.slice(head.length)))
    .filter((n) => Number.isFinite(n));
  return `${head}${String((nums.length ? Math.max(...nums) : 0) + 1).padStart(5, "0")}`;
}

/* ---------------- warehouse stock ---------------- */

export function whQty(s: ErpState, itemId: string, warehouseId: string) {
  return s.warehouseStock[itemId]?.[warehouseId] ?? 0;
}

export function whAdd(s: ErpState, itemId: string, warehouseId: string, qty: number) {
  const map = (s.warehouseStock[itemId] ??= {});
  const next = r2((map[warehouseId] ?? 0) + qty);
  if (next < 0) throw new Error("Insufficient stock at the selected warehouse");
  map[warehouseId] = next;
}

export function warehouseName(s: ErpState, id: string) {
  return s.warehouses.find((w) => w.id === id)?.name ?? id;
}

export function defaultWarehouse(s: ErpState) {
  return s.warehouses[0]?.id ?? "w1";
}

/* ---------------- purchase requisitions ---------------- */

export interface PrDraft {
  date: string;
  department: string;
  requester: string;
  materialId: string;
  quantity: number;
  priority: PurchaseRequisition["priority"];
  requiredDate: string;
  reason: string;
}

export function createRequisition(draft: PrDraft, username: string) {
  let prNo = "";
  update((s) => {
    const mat = s.materials.find((m) => m.id === draft.materialId);
    if (!mat) throw new Error("Select a material");
    if (draft.quantity <= 0) throw new Error("Quantity must be greater than zero");
    prNo = nextDocNo(s, "PR", draft.date);
    s.requisitions.unshift({
      id: uid(),
      prNo,
      date: draft.date,
      department: draft.department,
      requester: draft.requester || username,
      materialId: mat.id,
      materialName: mat.name,
      quantity: draft.quantity,
      unit: mat.unit,
      priority: draft.priority,
      requiredDate: draft.requiredDate,
      reason: draft.reason,
      status: "Pending",
    });
    logAudit(s, username, "CREATE", "requisition", `${prNo} · ${draft.quantity} ${mat.unit} ${mat.name}`);
    return s;
  });
  return prNo;
}

export function setPrStatus(id: string, status: PurchaseRequisition["status"], username: string) {
  update((s) => {
    const pr = s.requisitions.find((p) => p.id === id);
    if (!pr) throw new Error("Requisition not found");
    if (pr.status === "Converted to PO") throw new Error("This PR is already converted to a PO");
    pr.status = status;
    pr.approvedBy = username;
    logAudit(s, username, "UPDATE", "requisition", `${pr.prNo} ${status.toLowerCase()}`);
    return s;
  });
}

/* ---------------- purchase orders ---------------- */

export interface PoLineDraft {
  materialId: string;
  quantity: number;
  rate: number;
  gstPercent: number;
}

export interface PoDraft {
  date: string;
  supplierId: string;
  expectedDate: string;
  paymentTerms: string;
  warehouseId: string;
  status: PurchaseOrder["status"];
  prIds: string[];
  lines: PoLineDraft[];
}

function buildPoLine(s: ErpState, l: PoLineDraft): PoLine {
  const mat = s.materials.find((m) => m.id === l.materialId);
  if (!mat) throw new Error("Material not found");
  const taxable = r2(l.quantity * l.rate);
  const tax = r2((taxable * l.gstPercent) / 100);
  return {
    materialId: mat.id,
    materialName: mat.name,
    unit: mat.unit,
    quantity: l.quantity,
    receivedQty: 0,
    rate: l.rate,
    gstPercent: l.gstPercent,
    taxable,
    tax,
    total: r2(taxable + tax),
  };
}

export function createPurchaseOrder(draft: PoDraft, username: string) {
  let poNo = "";
  update((s) => {
    const supplier = s.suppliers.find((x) => x.id === draft.supplierId);
    if (!supplier) throw new Error("Select a supplier");
    const lines = draft.lines.filter((l) => l.materialId && l.quantity > 0).map((l) => buildPoLine(s, l));
    if (!lines.length) throw new Error("Add at least one material line");

    poNo = nextDocNo(s, "PO", draft.date);
    const id = uid();
    const prs = s.requisitions.filter((p) => draft.prIds.includes(p.id));
    const po: PurchaseOrder = {
      id,
      poNo,
      supplierId: supplier.id,
      supplierName: supplier.name,
      date: draft.date,
      expectedDate: draft.expectedDate,
      paymentTerms: draft.paymentTerms,
      warehouseId: draft.warehouseId,
      status: draft.status,
      prIds: prs.map((p) => p.id),
      prNos: prs.map((p) => p.prNo),
      lines,
      subTotal: r2(lines.reduce((t, l) => t + l.taxable, 0)),
      tax: r2(lines.reduce((t, l) => t + l.tax, 0)),
      grandTotal: r2(lines.reduce((t, l) => t + l.total, 0)),
    };
    prs.forEach((p) => {
      p.status = "Converted to PO";
      p.poId = id;
      p.poNo = poNo;
    });
    s.purchaseOrders.unshift(po);
    logAudit(s, username, "CREATE", "purchase-order", `${poNo} · ${supplier.name} · ₹${po.grandTotal}`);
    return s;
  });
  return poNo;
}

export function setPoStatus(id: string, status: PurchaseOrder["status"], username: string) {
  update((s) => {
    const po = s.purchaseOrders.find((p) => p.id === id);
    if (!po) throw new Error("Purchase order not found");
    po.status = status;
    logAudit(s, username, "UPDATE", "purchase-order", `${po.poNo} marked ${status}`);
    return s;
  });
}

/** Goods receipt — raw materials IN, warehouse stock credited, PO progress updated. */
export function receiveGoods(
  poId: string,
  draft: { date: string; warehouseId: string; remarks: string; lines: { materialId: string; quantity: number; batchNo: string }[] },
  username: string,
) {
  let grnNo = "";
  update((s) => {
    const po = s.purchaseOrders.find((p) => p.id === poId);
    if (!po) throw new Error("Purchase order not found");
    if (po.status === "Cancelled") throw new Error("Cancelled PO cannot receive goods");
    const lines = draft.lines.filter((l) => l.quantity > 0);
    if (!lines.length) throw new Error("Enter at least one received quantity");

    grnNo = nextDocNo(s, "GRN", draft.date);
    const grnLines: GoodsReceipt["lines"] = [];

    lines.forEach((l) => {
      const poLineRow = po.lines.find((x) => x.materialId === l.materialId);
      if (!poLineRow) throw new Error("Material is not on this PO");
      const pending = r2(poLineRow.quantity - poLineRow.receivedQty);
      if (l.quantity > pending)
        throw new Error(`Only ${pending} ${poLineRow.unit} of ${poLineRow.materialName} pending on ${po.poNo}`);
      poLineRow.receivedQty = r2(poLineRow.receivedQty + l.quantity);
      applyMovement(s, {
        itemKind: "material",
        itemId: l.materialId,
        type: "IN",
        quantity: l.quantity,
        reference: grnNo,
        reason: `Purchase receipt — ${po.poNo}`,
        date: draft.date,
        userId: username,
      });
      whAdd(s, l.materialId, draft.warehouseId, l.quantity);
      grnLines.push({
        materialId: l.materialId,
        materialName: poLineRow.materialName,
        quantity: l.quantity,
        batchNo: l.batchNo,
      });
    });

    const complete = po.lines.every((l) => l.receivedQty >= l.quantity);
    po.status = complete ? "Completed" : "Partially Received";

    s.receipts.unshift({
      id: uid(),
      grnNo,
      date: draft.date,
      poId: po.id,
      poNo: po.poNo,
      warehouseId: draft.warehouseId,
      lines: grnLines,
      remarks: draft.remarks,
    });
    logAudit(s, username, "CREATE", "goods-receipt", `${grnNo} against ${po.poNo}`);
    return s;
  });
  return grnNo;
}

/* ---------------- quotations & sales orders ---------------- */

export interface SalesLineDraft {
  productId: string;
  quantity: number;
  rate: number;
}

function buildSalesLine(s: ErpState, l: SalesLineDraft): SalesDocLine {
  const p = s.products.find((x) => x.id === l.productId);
  if (!p) throw new Error("Product not found");
  const taxable = r2(l.quantity * l.rate);
  const tax = r2((taxable * p.gstPercent) / 100);
  return {
    productId: p.id,
    productName: p.name,
    unit: p.unit,
    quantity: l.quantity,
    rate: l.rate,
    gstPercent: p.gstPercent,
    taxable,
    tax,
    total: r2(taxable + tax),
  };
}

const docTotals = (lines: SalesDocLine[]) => ({
  taxable: r2(lines.reduce((t, l) => t + l.taxable, 0)),
  tax: r2(lines.reduce((t, l) => t + l.tax, 0)),
  grandTotal: r2(lines.reduce((t, l) => t + l.total, 0)),
});

export function createQuotation(
  draft: { date: string; validUntil: string; customerId: string; notes: string; lines: SalesLineDraft[] },
  username: string,
) {
  let quoteNo = "";
  update((s) => {
    const customer = s.customers.find((c) => c.id === draft.customerId);
    if (!customer) throw new Error("Select a customer");
    const lines = draft.lines.filter((l) => l.productId && l.quantity > 0).map((l) => buildSalesLine(s, l));
    if (!lines.length) throw new Error("Add at least one product line");
    quoteNo = nextDocNo(s, "QT", draft.date);
    const quote: Quotation = {
      id: uid(),
      quoteNo,
      date: draft.date,
      validUntil: draft.validUntil,
      customerId: customer.id,
      customerName: customer.name,
      notes: draft.notes,
      status: "Draft",
      lines,
      ...docTotals(lines),
    };
    s.quotations.unshift(quote);
    logAudit(s, username, "CREATE", "quotation", `${quoteNo} · ${customer.name} · ₹${quote.grandTotal}`);
    return s;
  });
  return quoteNo;
}

export function setQuoteStatus(id: string, status: Quotation["status"], username: string) {
  update((s) => {
    const q = s.quotations.find((x) => x.id === id);
    if (!q) throw new Error("Quotation not found");
    if (q.status === "Converted to SO") throw new Error("Quotation already converted");
    q.status = status;
    logAudit(s, username, "UPDATE", "quotation", `${q.quoteNo} marked ${status}`);
    return s;
  });
}

export function quoteToSalesOrder(quoteId: string, deliveryDate: string, username: string) {
  let soNo = "";
  update((s) => {
    const q = s.quotations.find((x) => x.id === quoteId);
    if (!q) throw new Error("Quotation not found");
    if (q.soId) throw new Error(`Already converted (${q.soNo})`);
    soNo = nextDocNo(s, "SO");
    const id = uid();
    const lines: SalesOrderLine[] = q.lines.map((l) => ({ ...l, deliveredQty: 0 }));
    const so: SalesOrder = {
      id,
      soNo,
      date: today(),
      deliveryDate,
      customerId: q.customerId,
      customerName: q.customerName,
      notes: q.notes,
      status: "Open",
      lines,
      ...docTotals(lines),
      quoteId: q.id,
      quoteNo: q.quoteNo,
      deliveryNos: [],
    };
    q.status = "Converted to SO";
    q.soId = id;
    q.soNo = soNo;
    s.salesOrders.unshift(so);
    logAudit(s, username, "CREATE", "sales-order", `${soNo} from ${q.quoteNo}`);
    return s;
  });
  return soNo;
}

export function createSalesOrder(
  draft: { date: string; deliveryDate: string; customerId: string; notes: string; lines: SalesLineDraft[] },
  username: string,
) {
  let soNo = "";
  update((s) => {
    const customer = s.customers.find((c) => c.id === draft.customerId);
    if (!customer) throw new Error("Select a customer");
    const built = draft.lines.filter((l) => l.productId && l.quantity > 0).map((l) => buildSalesLine(s, l));
    if (!built.length) throw new Error("Add at least one product line");
    const lines: SalesOrderLine[] = built.map((l) => ({ ...l, deliveredQty: 0 }));
    soNo = nextDocNo(s, "SO", draft.date);
    s.salesOrders.unshift({
      id: uid(),
      soNo,
      date: draft.date,
      deliveryDate: draft.deliveryDate,
      customerId: customer.id,
      customerName: customer.name,
      notes: draft.notes,
      status: "Open",
      lines,
      ...docTotals(lines),
      deliveryNos: [],
    });
    logAudit(s, username, "CREATE", "sales-order", `${soNo} · ${customer.name}`);
    return s;
  });
  return soNo;
}

export function setSoStatus(id: string, status: SalesOrder["status"], username: string) {
  update((s) => {
    const so = s.salesOrders.find((x) => x.id === id);
    if (!so) throw new Error("Sales order not found");
    so.status = status;
    logAudit(s, username, "UPDATE", "sales-order", `${so.soNo} marked ${status}`);
    return s;
  });
}

/* ---------------- delivery notes & FOC ---------------- */

export interface DeliveryDraft {
  date: string;
  soId?: string | undefined;
  customerId: string;
  warehouseId: string;
  vehicleNo: string;
  driverName: string;
  lrNumber: string;
  remarks: string;
  foc: boolean;
  focPurpose?: string | undefined;
  lines: { productId: string; quantity: number }[];
}

/** Dispatch — finished goods leave both the global ledger and the source warehouse. */
export function createDelivery(draft: DeliveryDraft, username: string) {
  let dnNo = "";
  update((s) => {
    const customer = s.customers.find((c) => c.id === draft.customerId);
    if (!customer) throw new Error("Select a customer");
    const lines = draft.lines.filter((l) => l.productId && l.quantity > 0);
    if (!lines.length) throw new Error("Add at least one dispatch line");

    const so = draft.soId ? s.salesOrders.find((x) => x.id === draft.soId) : undefined;
    dnNo = nextDocNo(s, draft.foc ? "FOC" : "DN", draft.date);

    const built: DeliveryNote["lines"] = lines.map((l) => {
      const p = s.products.find((x) => x.id === l.productId);
      if (!p) throw new Error("Product not found");
      if (so) {
        const row = so.lines.find((x) => x.productId === l.productId);
        if (!row) throw new Error(`${p.name} is not on ${so.soNo}`);
        const pending = r2(row.quantity - row.deliveredQty);
        if (l.quantity > pending) throw new Error(`Only ${pending} ${p.unit} of ${p.name} pending on ${so.soNo}`);
        row.deliveredQty = r2(row.deliveredQty + l.quantity);
      }
      return {
        productId: p.id,
        productName: p.name,
        unit: p.unit,
        quantity: l.quantity,
        rate: draft.foc ? 0 : p.sellingPrice,
      };
    });

    built.forEach((l) => {
      applyMovement(s, {
        itemKind: "product",
        itemId: l.productId,
        type: "OUT",
        quantity: l.quantity,
        reference: dnNo,
        reason: draft.foc ? `FOC issue (${draft.focPurpose}) — ${customer.name}` : `Dispatch — ${customer.name}`,
        date: draft.date,
        userId: username,
      });
      whAdd(s, l.productId, draft.warehouseId, -l.quantity);
    });

    if (so) {
      so.deliveryNos.push(dnNo);
      so.status = so.lines.every((l) => l.deliveredQty >= l.quantity) ? "Delivered" : "Partially Delivered";
    }

    s.deliveries.unshift({
      id: uid(),
      dnNo,
      date: draft.date,
      soId: so?.id,
      soNo: so?.soNo,
      customerId: customer.id,
      customerName: customer.name,
      warehouseId: draft.warehouseId,
      vehicleNo: draft.vehicleNo,
      driverName: draft.driverName,
      lrNumber: draft.lrNumber,
      remarks: draft.remarks,
      foc: draft.foc,
      focPurpose: draft.focPurpose,
      lines: built,
    });
    logAudit(
      s,
      username,
      "CREATE",
      draft.foc ? "foc-issue" : "delivery",
      `${dnNo} · ${customer.name} · ${built.length} line(s)`,
    );
    return s;
  });
  return dnNo;
}

/** Links an already-raised invoice back to the delivery note and its sales order. */
export function linkInvoiceToDelivery(deliveryId: string, invoiceNo: string) {
  update((s) => {
    const dn = s.deliveries.find((d) => d.id === deliveryId);
    if (!dn) throw new Error("Delivery note not found");
    dn.invoiceNo = invoiceNo;
    const so = dn.soId ? s.salesOrders.find((x) => x.id === dn.soId) : undefined;
    if (so) {
      so.invoiceNo = invoiceNo;
      so.status = "Invoiced";
    }
    return s;
  });
}

/* ---------------- interplant transfers ---------------- */

export function createTransfer(
  draft: {
    date: string;
    sourceId: string;
    destId: string;
    itemKind: MaterialTransfer["itemKind"];
    itemId: string;
    quantity: number;
    batchNo: string;
    vehicle: string;
    remarks: string;
  },
  username: string,
) {
  let transferNo = "";
  update((s) => {
    if (draft.sourceId === draft.destId) throw new Error("Source and destination must differ");
    const bucket = draft.itemKind === "product" ? s.products : draft.itemKind === "material" ? s.materials : s.scrapTypes;
    const item = bucket.find((i) => i.id === draft.itemId);
    if (!item) throw new Error("Select an item to transfer");
    if (draft.quantity <= 0) throw new Error("Quantity must be greater than zero");
    const available = whQty(s, item.id, draft.sourceId);
    if (draft.quantity > available)
      throw new Error(`Only ${available} ${item.unit} of ${item.name} at ${warehouseName(s, draft.sourceId)}`);

    whAdd(s, item.id, draft.sourceId, -draft.quantity);
    whAdd(s, item.id, draft.destId, draft.quantity);

    transferNo = nextDocNo(s, "TR", draft.date);
    s.transfers.unshift({
      id: uid(),
      transferNo,
      date: draft.date,
      sourceId: draft.sourceId,
      sourceName: warehouseName(s, draft.sourceId),
      destId: draft.destId,
      destName: warehouseName(s, draft.destId),
      itemKind: draft.itemKind,
      itemId: item.id,
      itemName: item.name,
      quantity: draft.quantity,
      unit: item.unit,
      batchNo: draft.batchNo,
      vehicle: draft.vehicle,
      remarks: draft.remarks,
    });
    logAudit(
      s,
      username,
      "CREATE",
      "transfer",
      `${transferNo} · ${draft.quantity} ${item.unit} ${item.name} → ${warehouseName(s, draft.destId)}`,
    );
    return s;
  });
  return transferNo;
}

/* ---------------- job work ---------------- */

export function createJobWorkOut(
  draft: {
    date: string;
    vendorId: string;
    process: string;
    materialId: string;
    quantity: number;
    expectedDate: string;
    warehouseId: string;
    remarks: string;
  },
  username: string,
) {
  let jwNo = "";
  update((s) => {
    const vendor = s.suppliers.find((x) => x.id === draft.vendorId);
    const mat = s.materials.find((m) => m.id === draft.materialId);
    if (!vendor || !mat) throw new Error("Select a vendor and a material");
    if (draft.quantity <= 0) throw new Error("Quantity must be greater than zero");

    jwNo = nextDocNo(s, "JW", draft.date);
    applyMovement(s, {
      itemKind: "material",
      itemId: mat.id,
      type: "OUT",
      quantity: draft.quantity,
      reference: jwNo,
      reason: `Job work out — ${vendor.name} (${draft.process})`,
      date: draft.date,
      userId: username,
    });
    whAdd(s, mat.id, draft.warehouseId, -draft.quantity);

    const jw: JobWork = {
      id: uid(),
      jwNo,
      date: draft.date,
      vendorId: vendor.id,
      vendorName: vendor.name,
      process: draft.process,
      materialId: mat.id,
      materialName: mat.name,
      unit: mat.unit,
      quantity: draft.quantity,
      expectedDate: draft.expectedDate,
      warehouseId: draft.warehouseId,
      status: "At Vendor",
      remarks: draft.remarks,
      receipts: [],
    };
    s.jobWorks.unshift(jw);
    logAudit(s, username, "CREATE", "job-work", `${jwNo} · ${draft.quantity} ${mat.unit} ${mat.name} → ${vendor.name}`);
    return s;
  });
  return jwNo;
}

export function receiveJobWork(
  jobWorkId: string,
  draft: {
    date: string;
    productId: string;
    productQty: number;
    scrapTypeId: string;
    scrapQty: number;
    remarks: string;
    close: boolean;
  },
  username: string,
) {
  update((s) => {
    const jw = s.jobWorks.find((x) => x.id === jobWorkId);
    if (!jw) throw new Error("Job work order not found");
    if (jw.status === "Closed") throw new Error("This job work order is already closed");
    const product = s.products.find((p) => p.id === draft.productId);
    if (!product || draft.productQty <= 0) throw new Error("Enter the finished quantity received");
    const scrapType = draft.scrapTypeId ? s.scrapTypes.find((t) => t.id === draft.scrapTypeId) : undefined;

    applyMovement(s, {
      itemKind: "product",
      itemId: product.id,
      type: "IN",
      quantity: draft.productQty,
      reference: jw.jwNo,
      reason: `Job work in — ${jw.vendorName}`,
      date: draft.date,
      userId: username,
    });
    whAdd(s, product.id, jw.warehouseId, draft.productQty);

    if (scrapType && draft.scrapQty > 0) {
      applyMovement(s, {
        itemKind: "scrap",
        itemId: scrapType.id,
        type: "IN",
        quantity: draft.scrapQty,
        reference: jw.jwNo,
        reason: `Job work scrap — ${jw.vendorName}`,
        date: draft.date,
        userId: username,
      });
    }

    jw.receipts.push({
      id: uid(),
      date: draft.date,
      productId: product.id,
      productName: product.name,
      productQty: draft.productQty,
      scrapTypeId: scrapType?.id ?? "",
      scrapTypeName: scrapType?.name ?? "",
      scrapQty: scrapType ? draft.scrapQty : 0,
      remarks: draft.remarks,
    });
    jw.status = draft.close ? "Closed" : "Partially Received";
    logAudit(s, username, "CREATE", "job-work", `${jw.jwNo} received ${draft.productQty} × ${product.name}`);
    return s;
  });
}

/* ---------------- KPIs ---------------- */

export function docStats(s: ErpState) {
  return {
    openPrs: s.requisitions.filter((p) => p.status === "Pending").length,
    approvedPrs: s.requisitions.filter((p) => p.status === "Approved").length,
    openPos: s.purchaseOrders.filter((p) => p.status === "Approved" || p.status === "Partially Received").length,
    poValue: r2(
      s.purchaseOrders
        .filter((p) => p.status !== "Cancelled")
        .reduce((t, p) => t + p.grandTotal, 0),
    ),
    openSos: s.salesOrders.filter((o) => o.status === "Open" || o.status === "Partially Delivered").length,
    soValue: r2(
      s.salesOrders.filter((o) => o.status !== "Cancelled").reduce((t, o) => t + o.grandTotal, 0),
    ),
    liveQuotes: s.quotations.filter((q) => q.status === "Draft" || q.status === "Sent").length,
    atVendor: s.jobWorks.filter((j) => j.status !== "Closed").length,
    focIssues: s.deliveries.filter((d) => d.foc).length,
  };
}
