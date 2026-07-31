import type { ErpState, InventoryMovement, ProductionEntry, ScrapEntry } from "./types";

/** Deterministic PRNG so seed data is stable across server/client renders. */
function rng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

const iso = (daysAgo: number) => {
  const d = new Date(Date.UTC(2026, 6, 31) - daysAgo * 86400000);
  return d.toISOString().slice(0, 10);
};

export function buildSeedState(): ErpState {
  const rand = rng(20260731);

  const users: ErpState["users"] = [
    {
      id: "u1",
      username: "admin",
      fullName: "Ravi Kulkarni",
      email: "admin@minitally.in",
      role: "Admin",
      password: "admin123",
      active: true,
    },
    {
      id: "u2",
      username: "accounts",
      fullName: "Meera Shah",
      email: "accounts@minitally.in",
      role: "Accountant",
      password: "accounts123",
      active: true,
    },
    {
      id: "u3",
      username: "operator",
      fullName: "Sunil Patil",
      email: "shopfloor@minitally.in",
      role: "Operator",
      password: "operator123",
      active: true,
    },
  ];

  const products: ErpState["products"] = [
    { id: "p1", code: "FG-1001", name: "MS Hex Bolt M12", category: "Fasteners", unit: "PCS", sellingPrice: 18.5, costPrice: 11.2, hsnCode: "7318", gstPercent: 18, minStock: 2000, stock: 5400 },
    { id: "p2", code: "FG-1002", name: "MS Hex Nut M12", category: "Fasteners", unit: "PCS", sellingPrice: 7.25, costPrice: 4.1, hsnCode: "7318", gstPercent: 18, minStock: 3000, stock: 1850 },
    { id: "p3", code: "FG-2001", name: "Sheet Metal Bracket A", category: "Pressed Parts", unit: "PCS", sellingPrice: 96, costPrice: 58, hsnCode: "7326", gstPercent: 18, minStock: 500, stock: 1240 },
    { id: "p4", code: "FG-2002", name: "Sheet Metal Bracket B", category: "Pressed Parts", unit: "PCS", sellingPrice: 112, costPrice: 71, hsnCode: "7326", gstPercent: 18, minStock: 400, stock: 320 },
    { id: "p5", code: "FG-3001", name: "Aluminium Spacer 20mm", category: "Machined", unit: "PCS", sellingPrice: 34, costPrice: 19.5, hsnCode: "7616", gstPercent: 18, minStock: 1000, stock: 2760 },
    { id: "p6", code: "FG-3002", name: "Machined Shaft 150mm", category: "Machined", unit: "PCS", sellingPrice: 415, costPrice: 268, hsnCode: "8483", gstPercent: 18, minStock: 150, stock: 410 },
  ];

  const materials: ErpState["materials"] = [
    { id: "m1", name: "MS Round Bar 12mm", unit: "KG", cost: 68, stock: 3820, minStock: 800 },
    { id: "m2", name: "MS Sheet 2mm", unit: "KG", cost: 74, stock: 2140, minStock: 600 },
    { id: "m3", name: "Aluminium Rod 25mm", unit: "KG", cost: 246, stock: 540, minStock: 300 },
    { id: "m4", name: "Zinc Plating Chemical", unit: "LTR", cost: 320, stock: 180, minStock: 60 },
    { id: "m5", name: "Cutting Oil", unit: "LTR", cost: 185, stock: 96, minStock: 120 },
    { id: "m6", name: "Packing Carton", unit: "PCS", cost: 24, stock: 1450, minStock: 400 },
  ];

  const scrapTypes: ErpState["scrapTypes"] = [
    { id: "s1", name: "MS Turning Scrap", unit: "KG", sellingRate: 31, stock: 642 },
    { id: "s2", name: "Sheet Offcut", unit: "KG", sellingRate: 28, stock: 388 },
    { id: "s3", name: "Aluminium Chips", unit: "KG", sellingRate: 128, stock: 96 },
    { id: "s4", name: "Rejected Parts", unit: "PCS", sellingRate: 12, stock: 214 },
  ];

  const customers: ErpState["customers"] = [
    { id: "c1", name: "Deccan Auto Components", gstNumber: "27AABCD1234E1Z5", mobile: "+91 98220 41122", email: "purchase@deccanauto.in", address: "Plot 14, MIDC Bhosari, Pune 411026" },
    { id: "c2", name: "Shakti Engineering Works", gstNumber: "27AACSK9911F1ZQ", mobile: "+91 99700 22841", email: "orders@shaktiengg.co.in", address: "Gat 220, Chakan, Pune 410501" },
    { id: "c3", name: "Nova Fabricators Pvt Ltd", gstNumber: "24AAECN5567L1ZB", mobile: "+91 98795 10023", email: "accounts@novafab.com", address: "GIDC Vatva, Ahmedabad 382445" },
    { id: "c4", name: "Kirloskar Spares Depot", gstNumber: "29AAFCK2210M1Z8", mobile: "+91 90080 77341", email: "depot@ksdepot.in", address: "Peenya 2nd Stage, Bengaluru 560058" },
    { id: "c5", name: "Sunrise Traders", gstNumber: "27AAGFS1188K1ZR", mobile: "+91 93250 66710", email: "sunrise.traders@gmail.com", address: "Kalbadevi Road, Mumbai 400002" },
  ];

  const suppliers: ErpState["suppliers"] = [
    { id: "sp1", name: "Bharat Steel Traders", gstNumber: "27AABCB7788G1Z2", contact: "+91 98501 22110", address: "Kalamboli Steel Market, Navi Mumbai 410218" },
    { id: "sp2", name: "Metro Metals & Alloys", gstNumber: "27AAECM3344H1ZP", contact: "+91 98230 44561", address: "Bhosari MIDC, Pune 411026" },
    { id: "sp3", name: "Chem Solutions India", gstNumber: "27AADCC9922J1ZL", contact: "+91 97640 88123", address: "Ambernath MIDC, Thane 421506" },
    { id: "sp4", name: "PackRight Industries", gstNumber: "27AAHFP4455N1ZC", contact: "+91 91300 55420", address: "Wagholi, Pune 412207" },
  ];

  const machines = ["CNC-01", "CNC-02", "Press-100T", "Lathe-05", "Drill-03"];
  const operators = ["Sunil Patil", "Amit Jadhav", "Rakesh Sharma", "Imran Shaikh"];
  const shifts: ProductionEntry["shift"][] = ["A", "B", "C"];
  const reasons = ["Machine setup loss", "Material defect", "Operator error", "Tool wear", "Dimensional reject"];

  const production: ProductionEntry[] = [];
  const scrap: ScrapEntry[] = [];
  const movements: InventoryMovement[] = [];

  let batch = 1;
  for (let day = 13; day >= 0; day--) {
    const entriesToday = 1 + Math.floor(rand() * 2);
    for (let i = 0; i < entriesToday; i++) {
      const product = products[Math.floor(rand() * products.length)];
      const qty = 40 + Math.floor(rand() * 260);
      const batchNo = `BATCH-${String(batch++).padStart(4, "0")}`;
      const mats = [materials[Math.floor(rand() * 3)], materials[5]];
      const entry: ProductionEntry = {
        id: `prod-${batchNo}`,
        batchNo,
        date: iso(day),
        productId: product.id,
        productName: product.name,
        quantity: qty,
        machine: machines[Math.floor(rand() * machines.length)],
        operator: operators[Math.floor(rand() * operators.length)],
        shift: shifts[Math.floor(rand() * shifts.length)],
        remarks: "",
        consumption: mats.map((m) => ({
          materialId: m.id,
          materialName: m.name,
          quantity: Math.round(qty * (m.unit === "PCS" ? 0.1 : 0.35) * 10) / 10,
          unit: m.unit,
        })),
      };
      production.push(entry);

      movements.push({
        id: `mv-${batchNo}-fg`,
        date: entry.date,
        itemKind: "product",
        itemId: product.id,
        itemName: product.name,
        type: "IN",
        quantity: qty,
        unit: product.unit,
        balance: product.stock,
        reference: batchNo,
        reason: "Production output",
        userId: "u3",
      });
      entry.consumption.forEach((c, ci) => {
        movements.push({
          id: `mv-${batchNo}-rm${ci}`,
          date: entry.date,
          itemKind: "material",
          itemId: c.materialId,
          itemName: c.materialName,
          type: "OUT",
          quantity: c.quantity,
          unit: c.unit,
          balance: 0,
          reference: batchNo,
          reason: "Production consumption",
          userId: "u3",
        });
      });

      if (rand() > 0.35) {
        const st = scrapTypes[Math.floor(rand() * scrapTypes.length)];
        const sq = Math.round(qty * (0.01 + rand() * 0.05) * 10) / 10;
        scrap.push({
          id: `scr-${batchNo}`,
          date: entry.date,
          productId: product.id,
          productName: product.name,
          batchNo,
          scrapTypeId: st.id,
          scrapTypeName: st.name,
          quantity: sq,
          reason: reasons[Math.floor(rand() * reasons.length)],
          remarks: "",
        });
        movements.push({
          id: `mv-${batchNo}-scr`,
          date: entry.date,
          itemKind: "scrap",
          itemId: st.id,
          itemName: st.name,
          type: "IN",
          quantity: sq,
          unit: st.unit,
          balance: st.stock,
          reference: batchNo,
          reason: "Production scrap",
          userId: "u3",
        });
      }
    }
  }

  return {
    users,
    customers,
    suppliers,
    products,
    materials,
    scrapTypes,
    movements: movements.reverse(),
    production: production.reverse(),
    scrap: scrap.reverse(),
    audit: [
      { id: "a1", at: `${iso(0)}T08:12:00Z`, user: "admin", action: "LOGIN", entity: "auth", detail: "Admin signed in" },
      { id: "a2", at: `${iso(1)}T17:44:00Z`, user: "operator", action: "CREATE", entity: "production", detail: "Production batch recorded" },
    ],
    settings: {
      name: "Shreeji Precision Works",
      gstNumber: "27AAACS4512P1ZV",
      address: "Gat No. 118, Chakan Industrial Area, Pune 410501",
      invoicePrefix: "SPW/26-27/",
      financialYear: "2026-2027",
    },
  };
}
