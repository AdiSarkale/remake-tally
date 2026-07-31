import { useSyncExternalStore } from "react";
import { buildSeedState } from "./seed";
import type {
  ErpState,
  InventoryMovement,
  ItemKind,
  MovementType,
  ProductionEntry,
  ScrapEntry,
} from "./types";

const STORAGE_KEY = "minitally-erp-state-v1";

let serverSnapshot: ErpState | null = null;
function getSeed(): ErpState {
  if (!serverSnapshot) serverSnapshot = buildSeedState();
  return serverSnapshot;
}

let state: ErpState | null = null;
const listeners = new Set<() => void>();

function load(): ErpState {
  if (typeof window === "undefined") return getSeed();
  if (state) return state;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    state = raw ? (JSON.parse(raw) as ErpState) : buildSeedState();
  } catch {
    state = buildSeedState();
  }
  return state;
}

function commit(next: ErpState) {
  state = next;
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* quota — ignore */
    }
  }
  listeners.forEach((l) => l());
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => {
    listeners.delete(l);
  };
}

export function useErp<T>(selector: (s: ErpState) => T): T {
  const snapshot = useSyncExternalStore(subscribe, load, getSeed);
  // Selector runs on the cached snapshot reference so derived arrays/objects
  // stay stable between renders (otherwise useSyncExternalStore loops).
  const ref = useRef<{ snapshot: ErpState; value: T } | null>(null);
  if (!ref.current || ref.current.snapshot !== snapshot) {
    ref.current = { snapshot, value: selector(snapshot) };
  }
  return ref.current.value;
}


export function getState(): ErpState {
  return load();
}

export function resetDemoData() {
  commit(buildSeedState());
}

export function restoreState(raw: string) {
  commit(JSON.parse(raw) as ErpState);
}

export function update(fn: (s: ErpState) => ErpState) {
  commit(fn(structuredClone(load())));
}

export const uid = () => Math.random().toString(36).slice(2, 10);
export const today = () => new Date().toISOString().slice(0, 10);

export function logAudit(s: ErpState, user: string, action: string, entity: string, detail: string) {
  s.audit.unshift({ id: uid(), at: new Date().toISOString(), user, action, entity, detail });
  s.audit = s.audit.slice(0, 400);
}

/* ------------------------------------------------------------------ */
/* Inventory engine — every stock change flows through here             */
/* ------------------------------------------------------------------ */

interface MoveInput {
  itemKind: ItemKind;
  itemId: string;
  type: MovementType;
  quantity: number;
  reference: string;
  reason: string;
  date?: string;
  userId?: string;
}

export function applyMovement(s: ErpState, input: MoveInput): InventoryMovement {
  const bucket =
    input.itemKind === "product" ? s.products : input.itemKind === "material" ? s.materials : s.scrapTypes;
  const item = bucket.find((i) => i.id === input.itemId);
  if (!item) throw new Error("Item not found for stock movement");

  const delta =
    input.type === "IN" ? input.quantity : input.type === "OUT" ? -input.quantity : input.quantity - item.stock;
  const nextBalance = Math.round((item.stock + delta) * 1000) / 1000;
  if (nextBalance < 0) throw new Error(`Insufficient stock for ${item.name} (available ${item.stock})`);
  item.stock = nextBalance;

  const movement: InventoryMovement = {
    id: uid(),
    date: input.date ?? today(),
    itemKind: input.itemKind,
    itemId: item.id,
    itemName: item.name,
    type: input.type,
    quantity: input.type === "ADJUST" ? Math.abs(delta) : input.quantity,
    unit: item.unit,
    balance: nextBalance,
    reference: input.reference,
    reason: input.reason,
    userId: input.userId ?? "system",
  };
  s.movements.unshift(movement);
  return movement;
}

export function nextBatchNo(s: ErpState) {
  const nums = s.production
    .map((p) => Number(p.batchNo.replace(/\D/g, "")))
    .filter((n) => !Number.isNaN(n));
  const next = (nums.length ? Math.max(...nums) : 0) + 1;
  return `BATCH-${String(next).padStart(4, "0")}`;
}

export function createProduction(
  draft: Omit<ProductionEntry, "id" | "batchNo" | "productName"> & { batchNo?: string },
  username: string,
) {
  update((s) => {
    const product = s.products.find((p) => p.id === draft.productId);
    if (!product) throw new Error("Select a product");
    const batchNo = draft.batchNo?.trim() || nextBatchNo(s);
    if (s.production.some((p) => p.batchNo === batchNo)) throw new Error("Batch number already exists");

    const entry: ProductionEntry = {
      ...draft,
      id: uid(),
      batchNo,
      productName: product.name,
      consumption: draft.consumption.map((c) => {
        const mat = s.materials.find((m) => m.id === c.materialId);
        if (!mat) throw new Error("Raw material not found");
        return { ...c, materialName: mat.name, unit: mat.unit };
      }),
    };

    // Raw materials out first so a shortage aborts the whole entry.
    entry.consumption.forEach((c) =>
      applyMovement(s, {
        itemKind: "material",
        itemId: c.materialId,
        type: "OUT",
        quantity: c.quantity,
        reference: batchNo,
        reason: "Production consumption",
        date: entry.date,
        userId: username,
      }),
    );
    applyMovement(s, {
      itemKind: "product",
      itemId: entry.productId,
      type: "IN",
      quantity: entry.quantity,
      reference: batchNo,
      reason: "Production output",
      date: entry.date,
      userId: username,
    });

    s.production.unshift(entry);
    logAudit(s, username, "CREATE", "production", `${batchNo}: ${entry.quantity} × ${product.name}`);
    return s;
  });
}

export function createScrap(draft: Omit<ScrapEntry, "id" | "productName" | "scrapTypeName">, username: string) {
  update((s) => {
    const product = s.products.find((p) => p.id === draft.productId);
    const type = s.scrapTypes.find((t) => t.id === draft.scrapTypeId);
    if (!product || !type) throw new Error("Select a product and a scrap type");
    const entry: ScrapEntry = {
      ...draft,
      id: uid(),
      productName: product.name,
      scrapTypeName: type.name,
    };
    applyMovement(s, {
      itemKind: "scrap",
      itemId: type.id,
      type: "IN",
      quantity: entry.quantity,
      reference: entry.batchNo || "-",
      reason: `Scrap: ${entry.reason}`,
      date: entry.date,
      userId: username,
    });
    s.scrap.unshift(entry);
    logAudit(s, username, "CREATE", "scrap", `${entry.quantity} ${type.unit} ${type.name} — ${entry.reason}`);
    return s;
  });
}

export function stockMovement(input: MoveInput, username: string) {
  update((s) => {
    const mv = applyMovement(s, { ...input, userId: username });
    logAudit(s, username, input.type, "inventory", `${mv.itemName} ${mv.type} ${mv.quantity} ${mv.unit}`);
    return s;
  });
}

/* ------------------------------------------------------------------ */
/* Derived metrics                                                      */
/* ------------------------------------------------------------------ */

export function inventoryValue(s: ErpState) {
  const fg = s.products.reduce((t, p) => t + p.stock * p.costPrice, 0);
  const rm = s.materials.reduce((t, m) => t + m.stock * m.cost, 0);
  const sc = s.scrapTypes.reduce((t, x) => t + x.stock * x.sellingRate, 0);
  return { fg, rm, sc, total: fg + rm + sc };
}

export function lowStockItems(s: ErpState) {
  return [
    ...s.products
      .filter((p) => p.stock <= p.minStock)
      .map((p) => ({ id: p.id, name: p.name, stock: p.stock, min: p.minStock, unit: p.unit, kind: "Finished good" })),
    ...s.materials
      .filter((m) => m.stock <= m.minStock)
      .map((m) => ({ id: m.id, name: m.name, stock: m.stock, min: m.minStock, unit: m.unit, kind: "Raw material" })),
  ];
}

export function seriesLastDays(s: ErpState, days: number) {
  const out: { date: string; label: string; produced: number; scrap: number }[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000).toISOString().slice(0, 10);
    out.push({
      date: d,
      label: d.slice(5),
      produced: s.production.filter((p) => p.date === d).reduce((t, p) => t + p.quantity, 0),
      scrap: s.scrap.filter((x) => x.date === d).reduce((t, x) => t + x.quantity, 0),
    });
  }
  return out;
}

export function scrapStats(s: ErpState) {
  const day = today();
  const month = day.slice(0, 7);
  const daily = s.scrap.filter((x) => x.date === day).reduce((t, x) => t + x.quantity, 0);
  const monthly = s.scrap.filter((x) => x.date.startsWith(month)).reduce((t, x) => t + x.quantity, 0);
  const producedMonth = s.production
    .filter((p) => p.date.startsWith(month))
    .reduce((t, p) => t + p.quantity, 0);
  const byReason = new Map<string, number>();
  s.scrap.forEach((x) => byReason.set(x.reason, (byReason.get(x.reason) ?? 0) + x.quantity));
  const topReasons = [...byReason.entries()]
    .map(([reason, qty]) => ({ reason, qty: Math.round(qty * 10) / 10 }))
    .sort((a, b) => b.qty - a.qty)
    .slice(0, 5);
  return {
    daily,
    monthly,
    percent: producedMonth ? (monthly / (producedMonth + monthly)) * 100 : 0,
    topReasons,
  };
}
