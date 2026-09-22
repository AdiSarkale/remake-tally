

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createFileRoute,
} from "@tanstack/react-router";

import {
  FileText,
  Plus,
  Printer,
  Trash2,
} from "lucide-react";

import { toast } from "sonner";

import {
  AppShell,
} from "@/components/erp/AppShell";

import {
  PageHeader,
  StatCard,
} from "@/components/erp/PageHeader";

import {
  DataTable,
} from "@/components/erp/DataTable";

import {
  Badge,
} from "@/components/ui/badge";

import {
  Button,
} from "@/components/ui/button";

import {
  Input,
} from "@/components/ui/input";

import {
  Label,
} from "@/components/ui/label";

import {
  Textarea,
} from "@/components/ui/textarea";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  createInvoice,
  getCustomers,
  getInvoice,
  getInvoices,
  getNextInvoiceNumber,
  getProducts,
  getSettings,
  updateInvoiceStatus,
  type InvoiceData,
  type InvoiceInput,
  type InvoiceStatus,
  type PartyData,
  type ProductData,
  type SettingsData,
} from "@/lib/api";

import {
  dmy,
  inr,
  num,
} from "@/lib/erp/format";


export const Route = createFileRoute(
  "/invoices",
)({
  head: () => ({
    meta: [
      {
        title:
          "Sales Invoices — MiniTally ERP",
      },
      {
        name: "description",
        content:
          "GST sales invoices with payment tracking and finished-goods stock deduction.",
      },
    ],
  }),

  component: () => (
    <AppShell>
      <InvoicesPage />
    </AppShell>
  ),
});


interface LineDraft {
  productId: string;
  quantity: number;
  rate: number;
  discountPercent: number;
  gstRate: number | null;
}


interface PreviewLine {
  productId: string;
  productName: string;
  hsn: string;
  unit: string;

  quantity: number;
  rate: number;
  discountPercent: number;

  gstRate: number;

  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  total: number;
}


interface PreviewTotals {
  subTotal: number;
  discountTotal: number;
  taxable: number;
  cgst: number;
  sgst: number;
  igst: number;
  roundOff: number;
  grandTotal: number;
}


function today(): string {
  return new Date()
    .toISOString()
    .slice(0, 10);
}


function emptyLine(): LineDraft {
  return {
    productId: "",
    quantity: 1,
    rate: 0,
    discountPercent: 0,
    gstRate: null,
  };
}


function stateCode(
  gstin: string,
): string {
  return gstin
    ?.trim()
    .slice(0, 2) ?? "";
}


function calculateLine(
  product: ProductData,
  line: LineDraft,
  interState: boolean,
): PreviewLine {

  const gstRate =
    line.gstRate ??
    product.gst_rate;

  const gross =
    Math.round(
      line.quantity *
        line.rate *
        100,
    ) / 100;

  const discount =
    Math.round(
      gross *
        (line.discountPercent / 100) *
        100,
    ) / 100;

  const taxable =
    Math.round(
      (gross - discount) *
        100,
    ) / 100;

  const gst =
    Math.round(
      taxable *
        (gstRate / 100) *
        100,
    ) / 100;

  const cgst = interState
    ? 0
    : Math.round(
        (gst / 2) * 100,
      ) / 100;

  const sgst = interState
    ? 0
    : Math.round(
        (gst / 2) * 100,
      ) / 100;

  const igst = interState
    ? gst
    : 0;

  const total =
    Math.round(
      (taxable + gst) * 100,
    ) / 100;

  return {
    productId: product.id,
    productName: product.name,
    hsn: product.hsn,
    unit: product.unit,

    quantity: line.quantity,
    rate: line.rate,
    discountPercent:
      line.discountPercent,

    gstRate,

    taxable,
    cgst,
    sgst,
    igst,
    total,
  };
}


function calculateTotals(
  lines: PreviewLine[],
): PreviewTotals {

  const subTotal =
    lines.reduce(
      (sum, line) =>
        sum +
        line.quantity *
          line.rate,
      0,
    );

  const discountTotal =
    lines.reduce(
      (sum, line) =>
        sum +
        line.quantity *
          line.rate *
          (line.discountPercent /
            100),
      0,
    );

  const taxable =
    lines.reduce(
      (sum, line) =>
        sum + line.taxable,
      0,
    );

  const cgst =
    lines.reduce(
      (sum, line) =>
        sum + line.cgst,
      0,
    );

  const sgst =
    lines.reduce(
      (sum, line) =>
        sum + line.sgst,
      0,
    );

  const igst =
    lines.reduce(
      (sum, line) =>
        sum + line.igst,
      0,
    );

  const beforeRound =
    taxable +
    cgst +
    sgst +
    igst;

  const grandTotal =
    Math.round(
      beforeRound,
    );

  const roundOff =
    Math.round(
      (grandTotal -
        beforeRound) *
        100,
    ) / 100;

  return {
    subTotal:
      Math.round(
        subTotal * 100,
      ) / 100,

    discountTotal:
      Math.round(
        discountTotal * 100,
      ) / 100,

    taxable:
      Math.round(
        taxable * 100,
      ) / 100,

    cgst:
      Math.round(
        cgst * 100,
      ) / 100,

    sgst:
      Math.round(
        sgst * 100,
      ) / 100,

    igst:
      Math.round(
        igst * 100,
      ) / 100,

    roundOff,

    grandTotal,
  };
}


function InvoicesPage() {

  const [
    invoices,
    setInvoices,
  ] = useState<InvoiceData[]>(
    [],
  );

  const [
    products,
    setProducts,
  ] = useState<ProductData[]>(
    [],
  );

  const [
    customers,
    setCustomers,
  ] = useState<PartyData[]>(
    [],
  );

  const [
    settings,
    setSettings,
  ] = useState<SettingsData | null>(
    null,
  );

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    saving,
    setSaving,
  ] = useState(false);

  const [
    open,
    setOpen,
  ] = useState(false);

  const [
    view,
    setView,
  ] = useState<InvoiceData | null>(
    null,
  );

  const [
    nextNumber,
    setNextNumber,
  ] = useState("");

  const [
    form,
    setForm,
  ] = useState({
    date: today(),
    customerId: "",
    poReference: "",
    notes: "",
    paidPercent: 0,
  });

  const [
    lines,
    setLines,
  ] = useState<LineDraft[]>([
    emptyLine(),
  ]);

  const [paymentPercent, setPaymentPercent] = useState("");

  const customer =
    customers.find(
      (item) =>
        item.id ===
        form.customerId,
    );


  const interState =
    customer
      ? stateCode(
          customer.gst_number,
        ) !==
        stateCode(
          settings?.gst_number ?? "",
        )
      : false;


  const preview =
    useMemo(() => {

      const built =
        lines
          .filter(
            (line) =>
              line.productId &&
              line.quantity > 0,
          )
          .map((line) => {

            const product =
              products.find(
                (item) =>
                  item.id ===
                  line.productId,
              );

            if (!product) {
              return null;
            }

            return calculateLine(
              product,
              line,
              interState,
            );
          })
          .filter(
            (
              line,
            ): line is PreviewLine =>
              line !== null,
          );

      return {
        built,
        totals:
          calculateTotals(
            built,
          ),
      };

    }, [
      lines,
      products,
      interState,
    ]);


  const paidAmount =
    Math.round(
      preview.totals.grandTotal *
        (form.paidPercent /
          100) *
        100,
    ) / 100;


  const balanceAmount =
    Math.round(
      (
        preview.totals.grandTotal -
        paidAmount
      ) * 100,
    ) / 100;


  const derivedStatus: InvoiceStatus =
    form.paidPercent >= 100
      ? "Paid"
      : form.paidPercent > 0
        ? "Partial"
        : "Unpaid";


  async function loadData() {

    try {

      setLoading(true);

      const [
        invoiceData,
        productData,
        customerData,
        settingsData,
      ] = await Promise.all([
        getInvoices(),
        getProducts(),
        getCustomers(),
        getSettings(),
      ]);

      setInvoices(
        invoiceData,
      );

      setProducts(
        productData,
      );

      setCustomers(
        customerData.filter(
          (item) =>
            item.kind ===
            "customer",
        ),
      );

      setSettings(
        settingsData,
      );

    } catch (error) {

      toast.error(
        error instanceof Error
          ? error.message
          : "Could not load invoice data",
      );

    } finally {

      setLoading(false);
    }
  }


  useEffect(() => {
    void loadData();
  }, []);


  async function loadNextNumber() {

    try {

      const data =
        await getNextInvoiceNumber();

      setNextNumber(
        data.invoice_no,
      );

    } catch (error) {

      toast.error(
        error instanceof Error
          ? error.message
          : "Could not get invoice number",
      );
    }
  }


  function resetForm() {

    setForm({
      date: today(),
      customerId: "",
      poReference: "",
      notes: "",
      paidPercent: 0,
    });

    setLines([
      emptyLine(),
    ]);
  }


  function updateLine(
    index: number,
    patch: Partial<LineDraft>,
  ) {

    setLines(
      (previous) =>
        previous.map(
          (
            line,
            currentIndex,
          ) =>
            currentIndex ===
            index
              ? {
                  ...line,
                  ...patch,
                }
              : line,
        ),
    );
  }


  async function submit() {

    if (saving) {
      return;
    }


    if (!form.customerId) {

      toast.error(
        "Select a customer",
      );

      return;
    }


    const validLines =
      lines.filter(
        (line) =>
          line.productId &&
          line.quantity > 0,
      );


    if (!validLines.length) {

      toast.error(
        "Add at least one product",
      );

      return;
    }


    const productIds =
      validLines.map(
        (line) =>
          line.productId,
      );


    if (
      new Set(productIds).size !==
      productIds.length
    ) {

      toast.error(
        "The same product is listed twice — merge those lines",
      );

      return;
    }


    for (
      const line of validLines
    ) {

      const product =
        products.find(
          (item) =>
            item.id ===
            line.productId,
        );


      if (!product) {

        toast.error(
          "Product not found",
        );

        return;
      }


      if (
        line.quantity >
        product.stock
      ) {

        toast.error(
          `${product.name}: only ${num(
            product.stock,
          )} ${
            product.unit
          } available`,
        );

        return;
      }
    }


    try {

      setSaving(true);


      const payload: InvoiceInput = {
        invoice_date:
          form.date,

        customer_id:
          form.customerId,

        po_reference:
          form.poReference,

        notes:
          form.notes,

        status:
          derivedStatus,

        paid_percent:
          Math.min(
            100,
            Math.max(
              0,
              form.paidPercent,
            ),
          ),

        lines:
          validLines.map(
            (line) => ({
              product_id:
                line.productId,

              quantity:
                line.quantity,

              rate:
                line.rate,

              discount_percent:
                line.discountPercent,

              gst_rate:
                line.gstRate,
            }),
          ),
      };


      const created =
        await createInvoice(
          payload,
        );


      toast.success(
        `Invoice ${created.invoice_no} created`,
      );


      setOpen(false);

      resetForm();

      await loadData();

    } catch (error) {

      toast.error(
        error instanceof Error
          ? error.message
          : "Could not create invoice",
      );

    } finally {

      setSaving(false);
    }
  }


  async function openInvoice(
    invoice: InvoiceData,
  ) {

    try {

      const full =
        await getInvoice(
          invoice.id,
        );

      setView(full);

    } catch (error) {

      toast.error(
        error instanceof Error
          ? error.message
          : "Could not load invoice",
      );
    }
  }


  const changeStatus = async (
  invoice: InvoiceData,
  status: InvoiceStatus,
  paidPercent?: number,
) => {
  try {
    const updated = await updateInvoiceStatus(
      invoice.id,
      status,
      paidPercent,
    );

    setView(updated);

    setPaymentPercent("");
  } catch (error) {
    console.error(error);
  }
};


  const month =
    new Date()
      .toISOString()
      .slice(0, 7);


  const monthInvoices =
    invoices.filter(
      (invoice) =>
        invoice.invoice_date.startsWith(
          month,
        ),
    );


  const monthValue =
    monthInvoices.reduce(
      (sum, invoice) =>
        sum +
        invoice.grand_total,
      0,
    );


  const monthTax =
    monthInvoices.reduce(
      (sum, invoice) =>
        sum +
        invoice.cgst +
        invoice.sgst +
        invoice.igst,
      0,
    );


  const outstanding =
    invoices
      .filter(
        (invoice) =>
          invoice.status ===
            "Unpaid" ||
          invoice.status ===
            "Partial",
      )
      .reduce(
        (sum, invoice) =>
          sum +
          invoice.balance_amount,
        0,
      );


  return (
    <>
      <PageHeader
        title="Sales Invoices"
        subtitle="GST invoices with payment tracking and finished-goods stock deduction."
        actions={
          <Button
            onClick={async () => {
              resetForm();
              await loadNextNumber();
              setOpen(true);
            }}
          >
            <Plus className="mr-1 h-4 w-4" />
            New invoice
          </Button>
        }
      />


      <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">

        <StatCard
          label="Invoices raised"
          value={num(
            invoices.length,
          )}
        />

        <StatCard
          label="Sales this month"
          value={inr(
            monthValue,
          )}
          tone="success"
        />

        <StatCard
          label="GST this month"
          value={inr(
            monthTax,
          )}
        />

        <StatCard
          label="Outstanding"
          value={inr(
            outstanding,
          )}
          tone="warning"
        />

      </div>


      <DataTable
        rows={invoices}
        rowKey={(invoice) =>
          invoice.id
        }
        pageSize={12}
        empty={
          loading
            ? "Loading invoices..."
            : "No invoices yet."
        }
        searchable={(invoice) =>
          `${invoice.invoice_no}
           ${invoice.customer_name}
           ${invoice.po_reference}
           ${invoice.status}`
        }
        columns={[
          {
            key: "invoice",
            header: "Invoice no.",
            value: (invoice) =>
              invoice.invoice_no,
            className:
              "num text-xs font-medium",
          },

          {
            key: "date",
            header: "Date",
            value: (invoice) =>
              invoice.invoice_date,
            render: (invoice) =>
              dmy(
                invoice.invoice_date,
              ),
          },

          {
            key: "customer",
            header: "Customer",
            value: (invoice) =>
              invoice.customer_name,
          },

          {
            key: "taxable",
            header: "Taxable",
            align: "right",
            value: (invoice) =>
              invoice.taxable_total,
            render: (invoice) =>
              inr(
                invoice.taxable_total,
              ),
          },

          {
            key: "gst",
            header: "GST",
            align: "right",
            value: (invoice) =>
              invoice.cgst +
              invoice.sgst +
              invoice.igst,
            render: (invoice) =>
              inr(
                invoice.cgst +
                invoice.sgst +
                invoice.igst,
              ),
          },

          {
            key: "total",
            header: "Total",
            align: "right",
            value: (invoice) =>
              invoice.grand_total,
            render: (invoice) => (
              <span className="num font-semibold">
                {inr(
                  invoice.grand_total,
                )}
              </span>
            ),
          },

          {
            key: "paid",
            header: "Paid",
            align: "right",
            value: (invoice) =>
              invoice.paid_amount,
            render: (invoice) =>
              inr(
                invoice.paid_amount,
              ),
          },

          {
            key: "balance",
            header: "Balance",
            align: "right",
            value: (invoice) =>
              invoice.balance_amount,
            render: (invoice) => (
              <span className="num">
                {inr(
                  invoice.balance_amount,
                )}
              </span>
            ),
          },

          {
            key: "status",
            header: "Status",
            value: (invoice) =>
              invoice.status,
            render: (invoice) => (
              <Badge
                variant={
                  invoice.status ===
                  "Paid"
                    ? "secondary"
                    : invoice.status ===
                        "Partial"
                      ? "default"
                      : invoice.status ===
                          "Cancelled"
                        ? "destructive"
                        : "outline"
                }
              >
                {invoice.status}
              </Badge>
            ),
          },

          {
            key: "actions",
            header: "",
            align: "right",
            render: (
              invoice,
            ) => (
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  void openInvoice(
                    invoice,
                  )
                }
              >
                <FileText className="mr-1 h-4 w-4" />
                Open
              </Button>
            ),
          },
        ]}
      />


      {/* =====================================================
          NEW INVOICE
          ===================================================== */}

      <Dialog
        open={open}
        onOpenChange={setOpen}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">

          <DialogHeader>

            <DialogTitle>
              New sales invoice
            </DialogTitle>

            <DialogDescription>
              Invoice number{" "}
              <span className="num font-medium">
                {nextNumber ||
                  "Loading..."}
              </span>
              .
              {" "}
              {interState
                ? "IGST"
                : "CGST + SGST"}
              {" "}
              will be applied.
            </DialogDescription>

          </DialogHeader>


          <div className="grid gap-3 sm:grid-cols-4">

            <div className="sm:col-span-2">

              <Label className="mb-1.5 block text-xs">
                Customer
              </Label>

              <Select
                value={
                  form.customerId
                }
                onValueChange={(
                  value,
                ) =>
                  setForm({
                    ...form,
                    customerId:
                      value,
                  })
                }
              >

                <SelectTrigger>
                  <SelectValue placeholder="Select customer" />
                </SelectTrigger>

                <SelectContent>
                  {customers.map(
                    (item) => (
                      <SelectItem
                        key={item.id}
                        value={item.id}
                      >
                        {item.name}
                      </SelectItem>
                    ),
                  )}
                </SelectContent>

              </Select>

            </div>


            <div>

              <Label className="mb-1.5 block text-xs">
                Invoice date
              </Label>

              <Input
                type="date"
                value={
                  form.date
                }
                onChange={(
                  event,
                ) =>
                  setForm({
                    ...form,
                    date:
                      event.target
                        .value,
                  })
                }
              />

            </div>


            <div>

              <Label className="mb-1.5 block text-xs">
                PO reference
              </Label>

              <Input
                value={
                  form.poReference
                }
                onChange={(
                  event,
                ) =>
                  setForm({
                    ...form,
                    poReference:
                      event.target
                        .value,
                  })
                }
              />

            </div>

          </div>


          {/* Lines */}

          <div className="mt-3 space-y-2">

            <div className="flex items-center justify-between">

              <Label className="text-xs">
                Invoice lines
              </Label>

              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setLines(
                    (
                      previous,
                    ) => [
                      ...previous,
                      emptyLine(),
                    ],
                  )
                }
              >
                <Plus className="mr-1 h-3.5 w-3.5" />
                Add line
              </Button>

            </div>


            {lines.map(
              (
                line,
                index,
              ) => {

                const product =
                  products.find(
                    (item) =>
                      item.id ===
                      line.productId,
                  );


                const effectiveGst =
                  line.gstRate ??
                  product?.gst_rate ??
                  0;


                const customGst =
                  line.gstRate !==
                  null;


                return (
                  <div
                    key={index}
                    className="grid grid-cols-12 gap-2 rounded-md border p-2"
                  >

                    {/* Product */}

                    <div className="col-span-12 sm:col-span-4">

                      <Label className="mb-1 block text-[10px] text-muted-foreground">
                        Product
                      </Label>

                      <Select
                        value={
                          line.productId
                        }
                        onValueChange={(
                          value,
                        ) => {

                          const selected =
                            products.find(
                              (
                                item,
                              ) =>
                                item.id ===
                                value,
                            );

                          updateLine(
                            index,
                            {
                              productId:
                                value,

                              rate:
                                selected?.selling_price ??
                                0,

                              gstRate:
                                null,
                            },
                          );
                        }}
                      >

                        <SelectTrigger>
                          <SelectValue placeholder="Select product" />
                        </SelectTrigger>

                        <SelectContent>

                          {products.map(
                            (
                              item,
                            ) => (
                              <SelectItem
                                key={
                                  item.id
                                }
                                value={
                                  item.id
                                }
                              >
                                {
                                  item.code
                                }{" "}
                                ·{" "}
                                {
                                  item.name
                                }
                              </SelectItem>
                            ),
                          )}

                        </SelectContent>

                      </Select>

                    </div>


                    {/* Quantity */}

                    <div className="col-span-4 sm:col-span-2">

                      <Label className="mb-1 block text-[10px] text-muted-foreground">
                        Qty
                        {product
                          ? ` (${num(
                              product.stock,
                            )} available)`
                          : ""}
                      </Label>

                      <Input
                        type="number"
                        min="0"
                        step="0.01"
                        value={
                          line.quantity
                        }
                        onChange={(
                          event,
                        ) =>
                          updateLine(
                            index,
                            {
                              quantity:
                                Number(
                                  event
                                    .target
                                    .value,
                                ),
                            },
                          )
                        }
                      />

                    </div>


                    {/* Rate */}

                    <div className="col-span-4 sm:col-span-2">

                      <Label className="mb-1 block text-[10px] text-muted-foreground">
                        Rate
                      </Label>

                      <Input
                        type="number"
                        min="0"
                        step="0.01"
                        value={
                          line.rate
                        }
                        onChange={(
                          event,
                        ) =>
                          updateLine(
                            index,
                            {
                              rate:
                                Number(
                                  event
                                    .target
                                    .value,
                                ),
                            },
                          )
                        }
                      />

                    </div>


                    {/* Discount */}

                    <div className="col-span-4 sm:col-span-1">

                      <Label className="mb-1 block text-[10px] text-muted-foreground">
                        Disc %
                      </Label>

                      <Input
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={
                          line.discountPercent
                        }
                        onChange={(
                          event,
                        ) =>
                          updateLine(
                            index,
                            {
                              discountPercent:
                                Number(
                                  event
                                    .target
                                    .value,
                                ),
                            },
                          )
                        }
                      />

                    </div>


                    {/* GST */}

                    <div className="col-span-4 sm:col-span-1">

                      <Label className="mb-1 block text-[10px] text-muted-foreground">
                        GST %
                      </Label>

                      <Input
                        type="number"
                        min="0"
                        max="100"
                        step="0.01"
                        value={
                          effectiveGst
                        }
                        onChange={(
                          event,
                        ) =>
                          updateLine(
                            index,
                            {
                              gstRate:
                                Number(
                                  event
                                    .target
                                    .value,
                                ),
                            },
                          )
                        }
                      />

                      <p className="mt-0.5 text-[9px] text-muted-foreground">
                        {customGst
                          ? "Custom"
                          : "Master"}
                      </p>

                    </div>


                    {/* Amount */}

                    <div className="col-span-10 text-right sm:col-span-1">

                      <Label className="mb-1 block text-[10px] text-muted-foreground">
                        Amount
                      </Label>

                      <div className="num py-2 text-xs font-medium">
                        {inr(
                          preview.built[
                            index
                          ]?.total ??
                            0,
                        )}
                      </div>

                    </div>


                    {/* Delete */}

                    <div className="col-span-2 flex items-end justify-end sm:col-span-1">

                      <Button
                        variant="ghost"
                        size="icon"
                        disabled={
                          lines.length ===
                          1
                        }
                        onClick={() =>
                          setLines(
                            (
                              previous,
                            ) =>
                              previous.filter(
                                (
                                  _,
                                  lineIndex,
                                ) =>
                                  lineIndex !==
                                  index,
                              ),
                          )
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>

                    </div>

                  </div>
                );
              },
            )}

          </div>


          {/* Bottom */}

          <div className="mt-3 grid gap-4 lg:grid-cols-2">

            {/* Notes + payment */}

            <div>

              <Label className="mb-1.5 block text-xs">
                Notes
              </Label>

              <Textarea
                rows={3}
                value={
                  form.notes
                }
                onChange={(
                  event,
                ) =>
                  setForm({
                    ...form,
                    notes:
                      event.target
                        .value,
                  })
                }
              />


              <div className="mt-4 rounded-lg border p-3">

                <div className="mb-3 flex items-center justify-between">

                  <div>

                    <p className="text-sm font-medium">
                      Payment
                    </p>

                    <p className="text-xs text-muted-foreground">
                      Enter how much of the invoice has been paid.
                    </p>

                  </div>

                  <Badge
                    variant={
                      derivedStatus ===
                      "Paid"
                        ? "secondary"
                        : derivedStatus ===
                            "Partial"
                          ? "default"
                          : "outline"
                    }
                  >
                    {
                      derivedStatus
                    }
                  </Badge>

                </div>


                <div>

                  <Label className="mb-1.5 block text-xs">
                    Paid %
                  </Label>

                  <Input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={
                      form.paidPercent
                    }
                    onChange={(
                      event,
                    ) => {

                      let value =
                        Number(
                          event
                            .target
                            .value,
                        );

                      if (
                        !Number.isFinite(
                          value,
                        )
                      ) {
                        value = 0;
                      }

                      value =
                        Math.min(
                          100,
                          Math.max(
                            0,
                            value,
                          ),
                        );

                      setForm({
                        ...form,
                        paidPercent:
                          value,
                      });
                    }}
                  />

                </div>


                <div className="mt-3 space-y-1.5">

                  <Row
                    label="Invoice total"
                    value={inr(
                      preview
                        .totals
                        .grandTotal,
                    )}
                  />

                  <Row
                    label={`Paid (${num(
                      form.paidPercent,
                      2,
                    )}%)`}
                    value={inr(
                      paidAmount,
                    )}
                  />

                  <div className="border-t pt-2">

                    <Row
                      label="Balance"
                      value={inr(
                        balanceAmount,
                      )}
                      bold
                    />

                  </div>

                </div>

              </div>

            </div>


            {/* Totals */}

            <div className="rounded-lg border p-4">

              <h3 className="mb-3 text-sm font-semibold">
                Invoice totals
              </h3>

              <div className="space-y-2">

                <Row
                  label="Sub total"
                  value={inr(
                    preview
                      .totals
                      .subTotal,
                  )}
                />

                <Row
                  label="Discount"
                  value={`− ${inr(
                    preview
                      .totals
                      .discountTotal,
                  )}`}
                />

                <Row
                  label="Taxable value"
                  value={inr(
                    preview
                      .totals
                      .taxable,
                  )}
                />


                {interState ? (
                  <Row
                    label="IGST"
                    value={inr(
                      preview
                        .totals
                        .igst,
                    )}
                  />
                ) : (
                  <>
                    <Row
                      label="CGST"
                      value={inr(
                        preview
                          .totals
                          .cgst,
                      )}
                    />

                    <Row
                      label="SGST"
                      value={inr(
                        preview
                          .totals
                          .sgst,
                      )}
                    />
                  </>
                )}


                <Row
                  label="Round off"
                  value={inr(
                    preview
                      .totals
                      .roundOff,
                  )}
                />


                <div className="border-t pt-2">

                  <Row
                    label="Grand total"
                    value={inr(
                      preview
                        .totals
                        .grandTotal,
                    )}
                    bold
                  />

                </div>

              </div>

            </div>

          </div>


          <DialogFooter>

            <Button
              variant="outline"
              onClick={() =>
                setOpen(false)
              }
            >
              Cancel
            </Button>

            <Button
              disabled={saving}
              onClick={() =>
                void submit()
              }
            >
              {saving
                ? "Saving..."
                : "Save invoice"}
            </Button>

          </DialogFooter>

        </DialogContent>
      </Dialog>


      {/* =====================================================
          VIEW INVOICE
          ===================================================== */}

      <Dialog
        open={
          !!view
        }
        onOpenChange={(
          isOpen,
        ) => {

          if (!isOpen) {
            setView(null);
          }
        }}
      >

        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">

          {view && (
            <>

              <DialogHeader>

                <DialogTitle>
                  Tax invoice{" "}
                  {view.invoice_no}
                </DialogTitle>

                <DialogDescription>
                  {dmy(
                    view.invoice_date,
                  )}{" "}
                  ·{" "}
                  {
                    view.customer_name
                  }
                </DialogDescription>

              </DialogHeader>


              <div
                id="invoice-print"
                className="space-y-4 text-sm"
              >

                {/* Company/customer */}

                <div className="grid gap-4 sm:grid-cols-2">

                  <div>

                    <p className="font-semibold">
                      {
                        settings?.name ??
                        "Company"
                      }
                    </p>

                    <p className="text-xs text-muted-foreground">
                      {
                        settings?.address
                      }
                    </p>

                    <p className="num text-xs text-muted-foreground">
                      GSTIN{" "}
                      {
                        settings?.gst_number ||
                        "—"
                      }
                    </p>

                  </div>


                  <div className="sm:text-right">

                    <p className="font-semibold">
                      {
                        view.customer_name
                      }
                    </p>

                    <p className="text-xs text-muted-foreground">
                      {
                        customers.find(
                          (
                            item,
                          ) =>
                            item.id ===
                            view.customer_id,
                        )?.address ??
                        ""
                      }
                    </p>

                    <p className="num text-xs text-muted-foreground">
                      GSTIN{" "}
                      {
                        customers.find(
                          (
                            item,
                          ) =>
                            item.id ===
                            view.customer_id,
                        )?.gst_number ||
                        "—"
                      }
                    </p>

                  </div>

                </div>


                {/* Lines */}

                <div className="overflow-x-auto">

                  <table className="w-full text-xs">

                    <thead>

                      <tr className="border-b bg-muted/50 text-left">

                        <th className="px-2 py-2">
                          Item
                        </th>

                        <th className="px-2 py-2">
                          HSN
                        </th>

                        <th className="px-2 py-2 text-right">
                          Qty
                        </th>

                        <th className="px-2 py-2 text-right">
                          Rate
                        </th>

                        <th className="px-2 py-2 text-right">
                          Disc
                        </th>

                        <th className="px-2 py-2 text-right">
                          GST
                        </th>

                        <th className="px-2 py-2 text-right">
                          Taxable
                        </th>

                        <th className="px-2 py-2 text-right">
                          Total
                        </th>

                      </tr>

                    </thead>


                    <tbody>

                      {view.lines.map(
                        (
                          line,
                          index,
                        ) => (

                          <tr
                            key={
                              index
                            }
                            className="border-b last:border-0"
                          >

                            <td className="px-2 py-2">
                              {
                                line.product_name
                              }
                            </td>

                            <td className="num px-2 py-2">
                              {
                                line.hsn
                              }
                            </td>

                            <td className="num px-2 py-2 text-right">
                              {num(
                                line.quantity,
                              )}{" "}
                              {
                                line.unit
                              }
                            </td>

                            <td className="num px-2 py-2 text-right">
                              {inr(
                                line.rate,
                              )}
                            </td>

                            <td className="num px-2 py-2 text-right">
                              {num(
                                line.discount_percent,
                                2,
                              )}
                              %
                            </td>

                            <td className="num px-2 py-2 text-right">
                              {num(
                                line.gst_rate,
                                2,
                              )}
                              %
                            </td>

                            <td className="num px-2 py-2 text-right">
                              {inr(
                                line.taxable,
                              )}
                            </td>

                            <td className="num px-2 py-2 text-right font-medium">
                              {inr(
                                line.total,
                              )}
                            </td>

                          </tr>

                        ),
                      )}

                    </tbody>

                  </table>

                </div>


                {/* Totals */}

                <div className="ml-auto w-full max-w-sm space-y-1.5">

                  <Row
                    label="Taxable"
                    value={inr(
                      view.taxable_total,
                    )}
                  />

                  {view.inter_state ? (
                    <Row
                      label="IGST"
                      value={inr(
                        view.igst,
                      )}
                    />
                  ) : (
                    <>
                      <Row
                        label="CGST"
                        value={inr(
                          view.cgst,
                        )}
                      />

                      <Row
                        label="SGST"
                        value={inr(
                          view.sgst,
                        )}
                      />
                    </>
                  )}

                  <Row
                    label="Round off"
                    value={inr(
                      view.round_off,
                    )}
                  />

                  <Row
                    label="Grand total"
                    value={inr(
                      view.grand_total,
                    )}
                    bold
                  />

                  <div className="border-t pt-2">

                    <Row
                      label="Paid"
                      value={inr(
                        view.paid_amount,
                      )}
                    />

                    <Row
                      label="Balance"
                      value={inr(
                        view.balance_amount,
                      )}
                      bold
                    />

                  </div>

                </div>


                {view.notes && (
                  <p className="text-xs text-muted-foreground">
                    Notes:{" "}
                    {view.notes}
                  </p>
                )}

              </div>


             {/* Payment controls */}

                <div className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center gap-2">

                    <Badge
                      variant={
                        view.status === "Paid"
                          ? "secondary"
                          : view.status === "Partial"
                            ? "default"
                            : view.status === "Cancelled"
                              ? "destructive"
                              : "outline"
                      }
                    >
                      {view.status}
                    </Badge>

                    {/* Partial payment percentage */}
                    {view.status !== "Paid" &&
                      view.status !== "Cancelled" && (
                        <>
                          <Input
                            type="number"
                            min="1"
                            max="99"
                            step="1"
                            placeholder="Payment %"
                            className="w-28"
                            value={paymentPercent}
                            onChange={(e) =>
                              setPaymentPercent(e.target.value)
                            }
                          />

                          <Button
                            variant="outline"
                            size="sm"
                            disabled={
                              !paymentPercent ||
                              Number(paymentPercent) <= 0 ||
                              Number(paymentPercent) >= 100
                            }
                            onClick={() =>
                              void changeStatus(
                                view,
                                "Partial",
                                Number(paymentPercent),
                              )
                            }
                          >
                            Mark Partial
                          </Button>
                        </>
                      )}

                    {/* Mark Paid */}
                    {view.status !== "Paid" &&
                      view.status !== "Cancelled" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            void changeStatus(
                              view,
                              "Paid",
                            )
                          }
                        >
                          Mark Paid
                        </Button>
                      )}

                    {/* Mark Unpaid */}
                    {view.status !== "Unpaid" &&
                      view.status !== "Cancelled" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            const currentPaymentPercent =
                              view.grand_total > 0
                                ? Math.round(
                                    (view.paid_amount / view.grand_total) * 100,
                                  )
                                : 0;
                            setPaymentPercent(view.status  === 'Partial' ?  String(currentPaymentPercent) : '');
                            void changeStatus(
                              view,
                              "Unpaid",
                            );
                          }}
                        >
                          Mark Unpaid
                        </Button>
                      )}

                    {/* Cancel */}
                    {view.status !== "Cancelled" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          void changeStatus(
                            view,
                            "Cancelled",
                          )
                        }
                      >
                        Cancel
                      </Button>
                    )}

                  </div>

                  {/* Current payment information */}
                  {view.grand_total > 0 && (
                    <div className="mt-3 text-sm text-muted-foreground">
                      <div className="flex flex-wrap gap-4">
                        <span>
                          Total: ₹{view.grand_total.toFixed(2)}
                        </span>

                        <span>
                          Paid: ₹{view.paid_amount.toFixed(2)}
                        </span>

                        <span>
                          Balance: ₹{view.balance_amount.toFixed(2)}
                        </span>
                      </div>
                    </div>
                  )}
                </div>


              <DialogFooter>

                <Button
                  variant="outline"
                  onClick={() =>
                    window.print()
                  }
                >
                  <Printer className="mr-1 h-4 w-4" />
                  Print / PDF
                </Button>

              </DialogFooter>

            </>
          )}

        </DialogContent>

      </Dialog>

    </>
  );
}


function Row({
  label,
  value,
  bold = false,
}: {
  label: string;
  value: string;
  bold?: boolean;
}) {

  return (
    <div className="flex items-center justify-between gap-4">

      <span
        className={
          bold
            ? "font-semibold"
            : "text-muted-foreground"
        }
      >
        {label}
      </span>

      <span
        className={
          bold
            ? "num font-bold"
            : "num"
        }
      >
        {value}
      </span>

    </div>
  );
}
