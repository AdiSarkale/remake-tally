import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";

const TONES: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  Pending: "outline",
  Draft: "outline",
  Sent: "secondary",
  Approved: "default",
  Accepted: "default",
  Rejected: "destructive",
  Cancelled: "destructive",
  "Converted to PO": "secondary",
  "Converted to SO": "secondary",
  "Partially Received": "secondary",
  "Partially Delivered": "secondary",
  Completed: "default",
  Delivered: "default",
  Invoiced: "default",
  Open: "outline",
  "At Vendor": "secondary",
  Closed: "default",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={TONES[status] ?? "outline"} className="whitespace-nowrap">
      {status}
    </Badge>
  );
}

/** Small "PR → PO → GRN" style trail shown on document rows. */
export function DocTrail({ steps }: { steps: (string | undefined)[] }) {
  const chain = steps.filter(Boolean) as string[];
  if (!chain.length) return <span className="text-muted-foreground text-xs">—</span>;
  return (
    <span className="num text-muted-foreground text-xs">
      {chain.map((s, i) => (
        <span key={s + i}>
          {i > 0 && <span className="px-1 opacity-60">→</span>}
          {s}
        </span>
      ))}
    </span>
  );
}

export function Field({ label, children, full }: { label: string; children: ReactNode; full?: boolean }) {
  return (
    <div className={full ? "col-span-2" : "col-span-2 sm:col-span-1"}>
      <p className="text-muted-foreground mb-1.5 text-xs font-medium">{label}</p>
      {children}
    </div>
  );
}
