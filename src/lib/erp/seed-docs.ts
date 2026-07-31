import type { DocState, PoLine, SalesDocLine, SalesOrderLine } from "./doc-types";
import type { Customer, Product, RawMaterial, Supplier } from "./types";

const r2 = (n: number) => Math.round(n * 100) / 100;

export function poLine(m: RawMaterial, quantity: number, rate: number, received = 0): PoLine {
  const taxable = r2(quantity * rate);
  const tax = r2(taxable * 0.18);
  return {
    materialId: m.id,
    materialName: m.name,
    unit: m.unit,
    quantity,
    receivedQty: received,
    rate,
    gstPercent: 18,
    taxable,
    tax,
    total: r2(taxable + tax),
  };
}

export function salesLine(p: Product, quantity: number, rate?: number): SalesDocLine {
  const r = rate ?? p.sellingPrice;
  const taxable = r2(quantity * r);
  const tax = r2((taxable * p.gstPercent) / 100);
  return {
    productId: p.id,
    productName: p.name,
    unit: p.unit,
    quantity,
    rate: r,
    gstPercent: p.gstPercent,
    taxable,
    tax,
    total: r2(taxable + tax),
  };
}

export const sumDoc = (lines: { taxable: number; tax: number; total: number }[]) => ({
  taxable: r2(lines.reduce((t, l) => t + l.taxable, 0)),
  tax: r2(lines.reduce((t, l) => t + l.tax, 0)),
  grandTotal: r2(lines.reduce((t, l) => t + l.total, 0)),
});

export function buildDocSeed(args: {
  products: Product[];
  materials: RawMaterial[];
  customers: Customer[];
  suppliers: Supplier[];
  scrapTypes: { id: string; name: string }[];
  iso: (daysAgo: number) => string;
}): DocState {
  const { products, materials, customers, suppliers, scrapTypes, iso } = args;

  const warehouses: DocState["warehouses"] = [
    { id: "w1", code: "PLT-1", name: "Chakan Plant", location: "Chakan Industrial Area, Pune" },
    { id: "w2", code: "PLT-2", name: "Bhosari Unit", location: "Bhosari MIDC, Pune" },
    { id: "w3", code: "WH-FG", name: "Finished Goods Store", location: "Chakan, Pune" },
  ];

  // Opening allocation: 70% main plant, 30% secondary unit.
  const warehouseStock: DocState["warehouseStock"] = {};
  [...products, ...materials].forEach((i) => {
    warehouseStock[i.id] = { w1: Math.round(i.stock * 0.7), w2: i.stock - Math.round(i.stock * 0.7) };
  });

  const requisitions: DocState["requisitions"] = [
    {
      id: "pr1",
      prNo: "PR-2026-00001",
      date: iso(12),
      department: "Machine Shop",
      requester: "Sunil Patil",
      materialId: materials[0]!.id,
      materialName: materials[0]!.name,
      quantity: 1500,
      unit: materials[0]!.unit,
      priority: "High",
      requiredDate: iso(2),
      reason: "Bar stock running low for shaft line",
      status: "Converted to PO",
      approvedBy: "admin",
      poId: "po1",
      poNo: "PO-2026-00001",
    },
    {
      id: "pr2",
      prNo: "PR-2026-00002",
      date: iso(6),
      department: "Plating",
      requester: "Imran Shaikh",
      materialId: materials[3]!.id,
      materialName: materials[3]!.name,
      quantity: 200,
      unit: materials[3]!.unit,
      priority: "Normal",
      requiredDate: iso(-6),
      reason: "Monthly plating chemical top-up",
      status: "Approved",
      approvedBy: "admin",
    },
    {
      id: "pr3",
      prNo: "PR-2026-00003",
      date: iso(2),
      department: "Dispatch",
      requester: "Amit Jadhav",
      materialId: materials[5]!.id,
      materialName: materials[5]!.name,
      quantity: 800,
      unit: materials[5]!.unit,
      priority: "Urgent",
      requiredDate: iso(-3),
      reason: "Carton stock for export order",
      status: "Pending",
    },
  ];

  const po1Lines = [poLine(materials[0]!, 1500, 66, 1500)];
  const po2Lines = [poLine(materials[1]!, 1000, 72, 400), poLine(materials[4]!, 150, 180, 0)];

  const purchaseOrders: DocState["purchaseOrders"] = [
    {
      id: "po1",
      poNo: "PO-2026-00001",
      supplierId: suppliers[0]!.id,
      supplierName: suppliers[0]!.name,
      date: iso(11),
      expectedDate: iso(4),
      paymentTerms: "30 days credit",
      warehouseId: "w1",
      status: "Completed",
      prIds: ["pr1"],
      prNos: ["PR-2026-00001"],
      lines: po1Lines,
      subTotal: sumDoc(po1Lines).taxable,
      tax: sumDoc(po1Lines).tax,
      grandTotal: sumDoc(po1Lines).grandTotal,
    },
    {
      id: "po2",
      poNo: "PO-2026-00002",
      supplierId: suppliers[1]!.id,
      supplierName: suppliers[1]!.name,
      date: iso(5),
      expectedDate: iso(-4),
      paymentTerms: "Advance 50%",
      warehouseId: "w1",
      status: "Partially Received",
      prIds: [],
      prNos: [],
      lines: po2Lines,
      subTotal: sumDoc(po2Lines).taxable,
      tax: sumDoc(po2Lines).tax,
      grandTotal: sumDoc(po2Lines).grandTotal,
    },
  ];

  const receipts: DocState["receipts"] = [
    {
      id: "grn1",
      grnNo: "GRN-2026-00001",
      date: iso(4),
      poId: "po1",
      poNo: "PO-2026-00001",
      warehouseId: "w1",
      lines: [{ materialId: materials[0]!.id, materialName: materials[0]!.name, quantity: 1500, batchNo: "HT-8841" }],
      remarks: "Test certificate received",
    },
    {
      id: "grn2",
      grnNo: "GRN-2026-00002",
      date: iso(1),
      poId: "po2",
      poNo: "PO-2026-00002",
      warehouseId: "w1",
      lines: [{ materialId: materials[1]!.id, materialName: materials[1]!.name, quantity: 400, batchNo: "SH-2210" }],
      remarks: "Partial lot",
    },
  ];

  const q1 = [salesLine(products[2]!, 400), salesLine(products[3]!, 150)];
  const q2 = [salesLine(products[5]!, 60, 405)];
  const quotations: DocState["quotations"] = [
    {
      id: "qt1",
      quoteNo: "QT-2026-00001",
      date: iso(9),
      validUntil: iso(-6),
      customerId: customers[0]!.id,
      customerName: customers[0]!.name,
      notes: "Prices ex-works Chakan",
      status: "Converted to SO",
      lines: q1,
      ...sumDoc(q1),
      soId: "so1",
      soNo: "SO-2026-00001",
    },
    {
      id: "qt2",
      quoteNo: "QT-2026-00002",
      date: iso(3),
      validUntil: iso(-11),
      customerId: customers[2]!.id,
      customerName: customers[2]!.name,
      notes: "Freight extra",
      status: "Sent",
      lines: q2,
      ...sumDoc(q2),
    },
  ];

  const so1Lines: SalesOrderLine[] = q1.map((l, i) => ({ ...l, deliveredQty: i === 0 ? 250 : 0 }));
  const salesOrders: DocState["salesOrders"] = [
    {
      id: "so1",
      soNo: "SO-2026-00001",
      date: iso(8),
      deliveryDate: iso(-2),
      customerId: customers[0]!.id,
      customerName: customers[0]!.name,
      notes: "Schedule in two lots",
      status: "Partially Delivered",
      lines: so1Lines,
      ...sumDoc(so1Lines),
      quoteId: "qt1",
      quoteNo: "QT-2026-00001",
      deliveryNos: ["DN-2026-00001"],
    },
  ];

  const deliveries: DocState["deliveries"] = [
    {
      id: "dn1",
      dnNo: "DN-2026-00001",
      date: iso(3),
      soId: "so1",
      soNo: "SO-2026-00001",
      customerId: customers[0]!.id,
      customerName: customers[0]!.name,
      warehouseId: "w1",
      vehicleNo: "MH 14 GK 2291",
      driverName: "Balu Kadam",
      lrNumber: "LR-55120",
      remarks: "First lot",
      foc: false,
      lines: [
        {
          productId: products[2]!.id,
          productName: products[2]!.name,
          unit: products[2]!.unit,
          quantity: 250,
          rate: products[2]!.sellingPrice,
        },
      ],
    },
    {
      id: "dn2",
      dnNo: "FOC-2026-00001",
      date: iso(2),
      customerId: customers[1]!.id,
      customerName: customers[1]!.name,
      warehouseId: "w1",
      vehicleNo: "MH 12 QR 8890",
      driverName: "Sagar More",
      lrNumber: "-",
      remarks: "Sample pieces for approval",
      foc: true,
      focPurpose: "Sample",
      lines: [
        {
          productId: products[4]!.id,
          productName: products[4]!.name,
          unit: products[4]!.unit,
          quantity: 25,
          rate: 0,
        },
      ],
    },
  ];

  const transfers: DocState["transfers"] = [
    {
      id: "tr1",
      transferNo: "TR-2026-00001",
      date: iso(4),
      sourceId: "w1",
      sourceName: "Chakan Plant",
      destId: "w2",
      destName: "Bhosari Unit",
      itemKind: "material",
      itemId: materials[1]!.id,
      itemName: materials[1]!.name,
      quantity: 300,
      unit: materials[1]!.unit,
      batchNo: "SH-2210",
      vehicle: "MH 14 AB 1102",
      remarks: "Press shop requirement",
    },
  ];

  const jobWorks: DocState["jobWorks"] = [
    {
      id: "jw1",
      jwNo: "JW-2026-00001",
      date: iso(7),
      vendorId: suppliers[2]!.id,
      vendorName: suppliers[2]!.name,
      process: "Zinc plating",
      materialId: materials[2]!.id,
      materialName: materials[2]!.name,
      unit: materials[2]!.unit,
      quantity: 120,
      expectedDate: iso(-1),
      warehouseId: "w1",
      status: "Partially Received",
      remarks: "Trivalent blue passivation",
      receipts: [
        {
          id: "jwr1",
          date: iso(1),
          productId: products[4]!.id,
          productName: products[4]!.name,
          productQty: 900,
          scrapTypeId: scrapTypes[2]!.id,
          scrapTypeName: scrapTypes[2]!.name,
          scrapQty: 8,
          remarks: "Lot 1 of 2",
        },
      ],
    },
  ];

  return {
    warehouses,
    warehouseStock,
    requisitions,
    purchaseOrders,
    receipts,
    quotations,
    salesOrders,
    deliveries,
    transfers,
    jobWorks,
  };
}
