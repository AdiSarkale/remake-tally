import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatCurrency, formatNumber } from "@/lib/format";
import type { ProductOut } from "@/lib/api/types";

export interface LineItem {
  product_id: string;
  quantity: number;
  rate: number;
  discount_percent: number;
  gst_rate: number | null;
}

export function emptyLine(): LineItem {
  return { product_id: "", quantity: 1, rate: 0, discount_percent: 0, gst_rate: null };
}

export function LineItemsEditor({
  lines,
  onChange,
  products,
}: {
  lines: LineItem[];
  onChange: (lines: LineItem[]) => void;
  products: ProductOut[];
}) {
  const update = (index: number, patch: Partial<LineItem>) => {
    onChange(lines.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  };

  const productById = (id: string) => products.find((p) => p.id === id);

  const totals = lines.reduce(
    (acc, l) => {
      const p = productById(l.product_id);
      const gross = l.quantity * l.rate;
      const taxable = gross * (1 - l.discount_percent / 100);
      const gst = taxable * ((l.gst_rate ?? p?.gst_rate ?? 0) / 100);
      acc.taxable += taxable;
      acc.gst += gst;
      acc.total += taxable + gst;
      return acc;
    },
    { taxable: 0, gst: 0, total: 0 },
  );

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded-md border scrollbar-thin">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left text-xs text-muted-foreground">
              <th className="min-w-52 px-3 py-2 font-medium">Product</th>
              <th className="w-24 px-3 py-2 font-medium">Qty</th>
              <th className="w-28 px-3 py-2 font-medium">Rate</th>
              <th className="w-24 px-3 py-2 font-medium">Disc %</th>
              <th className="w-24 px-3 py-2 font-medium">GST %</th>
              <th className="w-28 px-3 py-2 text-right font-medium">Total</th>
              <th className="w-10 px-2 py-2" />
            </tr>
          </thead>
          <tbody>
            {lines.map((line, i) => {
              const p = productById(line.product_id);
              const taxable = line.quantity * line.rate * (1 - line.discount_percent / 100);
              const total = taxable * (1 + (line.gst_rate ?? p?.gst_rate ?? 0) / 100);
              return (
                <tr key={i} className="border-b last:border-0">
                  <td className="px-2 py-1.5">
                    <Select
                      value={line.product_id}
                      onValueChange={(v) => {
                        const prod = productById(v);
                        update(i, { product_id: v, rate: prod?.selling_price ?? line.rate });
                      }}
                    >
                      <SelectTrigger className="h-8 w-full">
                        <SelectValue placeholder="Select product" />
                      </SelectTrigger>
                      <SelectContent>
                        {products.map((prod) => (
                          <SelectItem key={prod.id} value={prod.id}>
                            {prod.name} <span className="text-muted-foreground">({prod.code})</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="px-2 py-1.5">
                    <Input
                      type="number"
                      min={0}
                      step="any"
                      className="tabular h-8"
                      value={line.quantity}
                      onChange={(e) => update(i, { quantity: Number(e.target.value) })}
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <Input
                      type="number"
                      min={0}
                      step="any"
                      className="tabular h-8"
                      value={line.rate}
                      onChange={(e) => update(i, { rate: Number(e.target.value) })}
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      step="any"
                      className="tabular h-8"
                      value={line.discount_percent}
                      onChange={(e) => update(i, { discount_percent: Number(e.target.value) })}
                    />
                  </td>
                  <td className="px-2 py-1.5">
                    <Input
                      type="number"
                      min={0}
                      max={100}
                      step="any"
                      className="tabular h-8"
                      placeholder={p ? String(p.gst_rate) : "18"}
                      value={line.gst_rate ?? ""}
                      onChange={(e) => update(i, { gst_rate: e.target.value === "" ? null : Number(e.target.value) })}
                    />
                  </td>
                  <td className="tabular px-3 py-1.5 text-right">{formatCurrency(total)}</td>
                  <td className="px-2 py-1.5">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-7 text-muted-foreground hover:text-destructive"
                      disabled={lines.length === 1}
                      onClick={() => onChange(lines.filter((_, idx) => idx !== i))}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between">
        <Button type="button" variant="outline" size="sm" onClick={() => onChange([...lines, emptyLine()])}>
          <Plus className="size-3.5" /> Add line
        </Button>
        <div className="flex gap-5 text-xs text-muted-foreground">
          <span>
            Taxable <span className="tabular font-medium text-foreground">{formatCurrency(totals.taxable)}</span>
          </span>
          <span>
            GST <span className="tabular font-medium text-foreground">{formatCurrency(totals.gst)}</span>
          </span>
          <span>
            Total <span className="tabular font-semibold text-foreground">{formatCurrency(totals.total)}</span>
          </span>
        </div>
      </div>
      <p className="text-[11px] text-muted-foreground">
        Quantities in product units; leave GST blank to use the product master rate ({formatNumber(products[0]?.gst_rate ?? 18, 0)}% typical).
      </p>
    </div>
  );
}
