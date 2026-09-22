import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  ClipboardCheck,
} from "lucide-react";
import { toast } from "sonner";

import { AppShell } from "@/components/erp/AppShell";
import {
  PageHeader,
  StatCard,
} from "@/components/erp/PageHeader";
import { DataTable } from "@/components/erp/DataTable";
import {
  DocTrail,
  StatusBadge,
} from "@/components/erp/DocBits";

import { Button } from "@/components/ui/button";

import {
  getSalesOrders,
  updateSalesOrderStatus,
  type SalesOrderData,
  type SalesOrderStatus,
} from "@/lib/api";

import { dmy, inr, num } from "@/lib/erp/format";
import { useAuth } from "@/lib/erp/auth";


export const Route = createFileRoute(
  "/sales/orders",
)({
  head: () => ({
    meta: [
      {
        title: "Sales Orders — MiniTally ERP",
      },
      {
        name: "description",
        content:
          "Track confirmed customer orders, delivery progress and invoicing status.",
      },
      {
        property: "og:title",
        content:
          "Sales Orders — MiniTally ERP",
      },
      {
        property: "og:description",
        content:
          "Sales order to delivery to invoice tracking.",
      },
    ],
  }),

  component: () => (
    <AppShell>
      <SalesOrdersPage />
    </AppShell>
  ),
});


function SalesOrdersPage() {
  const { session } = useAuth();

  const user =
    session?.username ?? "system";

  const [salesOrders, setSalesOrders] =
    useState<SalesOrderData[]>([]);

  const [loading, setLoading] =
    useState(true);


  /* =========================================================
     Load Sales Orders
     ========================================================= */

  async function loadSalesOrders() {
    try {
      setLoading(true);

      const data =
        await getSalesOrders();

      setSalesOrders(data);
    } catch (error) {
      toast.error(
        (error as Error).message ||
          "Failed to load sales orders",
      );
    } finally {
      setLoading(false);
    }
  }


  useEffect(() => {
    void loadSalesOrders();
  }, []);


  /* =========================================================
     Statistics
     ========================================================= */

  const openOrders =
    salesOrders.filter(
      (order) =>
        order.status === "Open" ||
        order.status ===
          "Partially Delivered",
    ).length;


  const orderBookValue =
    salesOrders
      .filter(
        (order) =>
          order.status === "Open" ||
          order.status ===
            "Partially Delivered",
      )
      .reduce(
        (total, order) =>
          total +
          order.grand_total,
        0,
      );


  const deliveredOrders =
    salesOrders.filter(
      (order) =>
        order.status ===
          "Delivered" ||
        order.status ===
          "Invoiced",
    ).length;


  /* =========================================================
     Cancel Sales Order
     ========================================================= */

  async function cancelSalesOrder(
    order: SalesOrderData,
  ) {
    if (
      order.status !== "Open" &&
      order.status !==
        "Partially Delivered"
    ) {
      return;
    }

    try {
      await updateSalesOrderStatus(
        order.id,
        "Cancelled",
      );

      toast.success(
        `${order.so_no} cancelled`,
      );

      await loadSalesOrders();
    } catch (error) {
      toast.error(
        (error as Error).message ||
          "Failed to cancel sales order",
      );
    }
  }


  /* =========================================================
     Delivery Progress
     ========================================================= */

  function deliveredQuantity(
    order: SalesOrderData,
  ) {
    return order.lines.reduce(
      (total, line) =>
        total +
        line.delivered_quantity,
      0,
    );
  }


  function orderedQuantity(
    order: SalesOrderData,
  ) {
    return order.lines.reduce(
      (total, line) =>
        total +
        line.quantity,
      0,
    );
  }


  /* =========================================================
     Render
     ========================================================= */

  return (
    <>
      <PageHeader
        title="Sales Orders"
        subtitle="Confirmed customer orders — deliveries draw against the ordered quantity."
      />


      {/* =====================================================
          Statistics
          ===================================================== */}

      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">

        <StatCard
          label="Open orders"
          value={num(openOrders)}
          tone="primary"
          icon={
            <ClipboardCheck className="h-4 w-4" />
          }
        />

        <StatCard
          label="Order book value"
          value={inr(orderBookValue)}
        />

        <StatCard
          label="Delivered"
          value={num(
            deliveredOrders,
          )}
          tone="success"
        />

        <StatCard
          label="Total orders"
          value={num(
            salesOrders.length,
          )}
        />

      </div>


      {/* =====================================================
          Sales Order Table
          ===================================================== */}

      <DataTable
        rows={salesOrders}
        rowKey={(row) =>
          row.id
        }

        searchable={(row) =>
          `${row.so_no}
           ${row.customer_name}
           ${row.status}
           ${row.quote_no ?? ""}
           ${row.lines
             .map(
               (
                 line,
               ) =>
                 line.product_name,
             )
             .join(" ")}`
        }

        columns={[
          {
            key: "no",
            header: "SO No",
            value: (row) =>
              row.so_no,

            render: (row) => (
              <span className="num font-medium">
                {row.so_no}
              </span>
            ),
          },


          {
            key: "date",
            header: "Date",
            value: (row) =>
              row.order_date,

            render: (row) => (
              <span className="num">
                {dmy(
                  row.order_date,
                )}
              </span>
            ),
          },


          {
            key: "customer",
            header: "Customer",
            value: (row) =>
              row.customer_name,
          },


          {
            key: "delivery",
            header: "Delivery by",
            value: (row) =>
              row.delivery_date ??
              "",

            render: (row) => (
              <span className="num">
                {row.delivery_date
                  ? dmy(
                      row.delivery_date,
                    )
                  : "-"}
              </span>
            ),
          },


          {
            key: "progress",
            header: "Delivered",
            align: "right",

            value: (row) =>
              deliveredQuantity(
                row,
              ),

            render: (row) => (
              <span className="num text-xs">
                {num(
                  deliveredQuantity(
                    row,
                  ),
                )}{" "}
                /{" "}
                {num(
                  orderedQuantity(
                    row,
                  ),
                )}
              </span>
            ),
          },


          {
            key: "value",
            header: "Value",
            align: "right",

            value: (row) =>
              row.grand_total,

            render: (row) => (
              <span className="num">
                {inr(
                  row.grand_total,
                )}
              </span>
            ),
          },


          {
            key: "status",
            header: "Status",

            value: (row) =>
              row.status,

            render: (row) => (
              <StatusBadge
                status={
                  row.status
                }
              />
            ),
          },


          {
            key: "quote",
            header: "Quotation",

            value: (row) =>
              row.quote_no,

            render: (row) => (
              <span className="num text-xs">
                {row.quote_no ||
                  "-"}
              </span>
            ),
          },


          {
            key: "trail",
            header: "Trail",

            render: (row) => (
              <DocTrail
                steps={[
                  row.quote_no ||
                    "",
                  row.so_no,
                ]}
              />
            ),
          },


          {
            key: "actions",
            header: "",
            align: "right",

            render: (row) =>
              row.status ===
                "Open" ||
              row.status ===
                "Partially Delivered" ? (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() =>
                    void cancelSalesOrder(
                      row,
                    )
                  }
                >
                  Cancel
                </Button>
              ) : null,
          },
        ]}
      />

      {loading && (
        <div className="py-8 text-center text-sm text-muted-foreground">
          Loading sales orders...
        </div>
      )}
    </>
  );
}
