import type { Invoice, InvoiceLine, Product } from "./types";

export interface LineDraft {
  productId: string;
  quantity: number;
  rate: number;
  discountPercent: number;
}

export const stateCode = (gst: string) => (gst || "").trim().slice(0, 2);

const r2 = (n: number) => Math.round((Number.isFinite(n) ? n : 0) * 100) / 100;

/** Builds a fully priced GST line: taxable value, then CGST+SGST (intra-state) or IGST. */
export function buildLine(product: Product, draft: LineDraft, interState: boolean): InvoiceLine {
  const gross = draft.quantity * draft.rate;
  const discount = (gross * (draft.discountPercent || 0)) / 100;
  const taxable = r2(gross - discount);
  const tax = r2((taxable * product.gstPercent) / 100);
  const half = r2(tax / 2);
  const cgst = interState ? 0 : half;
  const sgst = interState ? 0 : r2(tax - half);
  const igst = interState ? tax : 0;
  return {
    productId: product.id,
    productName: product.name,
    hsnCode: product.hsnCode,
    unit: product.unit,
    quantity: draft.quantity,
    rate: draft.rate,
    discountPercent: draft.discountPercent || 0,
    gstPercent: product.gstPercent,
    taxable,
    cgst,
    sgst,
    igst,
    total: r2(taxable + cgst + sgst + igst),
  };
}

export type InvoiceTotals = Pick<
  Invoice,
  "subTotal" | "discountTotal" | "taxable" | "cgst" | "sgst" | "igst" | "roundOff" | "grandTotal"
>;

export function totalsFor(lines: InvoiceLine[]): InvoiceTotals {
  const subTotal = r2(lines.reduce((t, l) => t + l.quantity * l.rate, 0));
  const taxable = r2(lines.reduce((t, l) => t + l.taxable, 0));
  const cgst = r2(lines.reduce((t, l) => t + l.cgst, 0));
  const sgst = r2(lines.reduce((t, l) => t + l.sgst, 0));
  const igst = r2(lines.reduce((t, l) => t + l.igst, 0));
  const net = r2(taxable + cgst + sgst + igst);
  const grandTotal = Math.round(net);
  return {
    subTotal,
    discountTotal: r2(subTotal - taxable),
    taxable,
    cgst,
    sgst,
    igst,
    roundOff: r2(grandTotal - net),
    grandTotal,
  };
}
