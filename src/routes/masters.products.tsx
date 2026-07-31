import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/erp/AppShell";
import { MasterPage } from "@/components/erp/MasterPage";
import { Badge } from "@/components/ui/badge";
import { inr, num } from "@/lib/erp/format";

export const Route = createFileRoute("/masters/products")({
  head: () => ({
    meta: [
      { title: "Products — MiniTally ERP" },
      { name: "description", content: "Finished goods master with HSN, GST rate, pricing and minimum stock levels." },
      { property: "og:title", content: "Products — MiniTally ERP" },
      { property: "og:description", content: "Finished goods master with HSN, GST rate, pricing and stock levels." },
    ],
  }),
  component: () => (
    <AppShell>
      <MasterPage
        title="Products"
        subtitle="Finished goods produced and sold."
        entity="products"
        defaults={{ stock: 0 }}
        searchable={(r) => `${r.code} ${r.name} ${r.category} ${r.hsnCode}`}
        fields={[
          { name: "code", label: "Product Code", required: true },
          { name: "name", label: "Product Name", required: true },
          { name: "category", label: "Category" },
          { name: "unit", label: "Unit", placeholder: "PCS / KG" },
          { name: "sellingPrice", label: "Selling Price", type: "number", step: "0.01" },
          { name: "costPrice", label: "Cost Price", type: "number", step: "0.01" },
          { name: "hsnCode", label: "HSN Code" },
          { name: "gstPercent", label: "GST %", type: "number", step: "0.01" },
          { name: "minStock", label: "Minimum Stock", type: "number" },
        ]}
        columns={[
          { key: "code", header: "Code", value: (r) => String(r.code), className: "num text-xs" },
          { key: "name", header: "Product", value: (r) => String(r.name) },
          { key: "category", header: "Category", value: (r) => String(r.category) },
          {
            key: "stock",
            header: "Stock",
            align: "right",
            value: (r) => Number(r.stock ?? 0),
            render: (r) => (
              <span className="num">
                {Number(r.stock ?? 0) <= Number(r.minStock ?? 0) ? (
                  <Badge variant="destructive">{num(Number(r.stock ?? 0))}</Badge>
                ) : (
                  num(Number(r.stock ?? 0))
                )}{" "}
                <span className="text-muted-foreground text-xs">{String(r.unit ?? "")}</span>
              </span>
            ),
          },
          {
            key: "price",
            header: "Rate",
            align: "right",
            value: (r) => Number(r.sellingPrice ?? 0),
            render: (r) => <span className="num">{inr(Number(r.sellingPrice ?? 0))}</span>,
          },
          {
            key: "gst",
            header: "GST",
            align: "right",
            value: (r) => Number(r.gstPercent ?? 0),
            render: (r) => <span className="num">{Number(r.gstPercent ?? 0)}%</span>,
          },
        ]}
      />
    </AppShell>
  ),
});
