import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Status → semantic color. Color communicates state, not decoration.
const STATUS_TONE: Record<string, string> = {
  // success
  paid: "bg-success/15 text-success border-success/30",
  delivered: "bg-success/15 text-success border-success/30",
  received: "bg-success/15 text-success border-success/30",
  accepted: "bg-success/15 text-success border-success/30",
  converted: "bg-success/15 text-success border-success/30",
  available: "bg-success/15 text-success border-success/30",
  completed: "bg-success/15 text-success border-success/30",
  active: "bg-success/15 text-success border-success/30",
  // warning
  partial: "bg-warning/15 text-warning border-warning/30",
  "partially delivered": "bg-warning/15 text-warning border-warning/30",
  partially_received: "bg-warning/15 text-warning border-warning/30",
  pending: "bg-warning/15 text-warning border-warning/30",
  sent: "bg-warning/15 text-warning border-warning/30",
  loading: "bg-warning/15 text-warning border-warning/30",
  planned: "bg-warning/15 text-warning border-warning/30",
  draft: "bg-warning/15 text-warning border-warning/30",
  "accepted with deviation": "bg-warning/15 text-warning border-warning/30",
  // info / operational
  open: "bg-info/15 text-info border-info/30",
  "in transit": "bg-info/15 text-info border-info/30",
  invoiced: "bg-info/15 text-info border-info/30",
  "in progress": "bg-info/15 text-info border-info/30",
  // critical
  unpaid: "bg-destructive/15 text-destructive border-destructive/30",
  overdue: "bg-destructive/15 text-destructive border-destructive/30",
  rejected: "bg-destructive/15 text-destructive border-destructive/30",
  cancelled: "bg-destructive/15 text-destructive border-destructive/30",
  delayed: "bg-destructive/15 text-destructive border-destructive/30",
  expired: "bg-destructive/15 text-destructive border-destructive/30",
  inactive: "bg-destructive/15 text-destructive border-destructive/30",
};

export function StatusBadge({ status, className }: { status: string | null | undefined; className?: string }) {
  if (!status) return <span className="text-muted-foreground">—</span>;
  const tone = STATUS_TONE[status.toLowerCase()] ?? "bg-secondary text-secondary-foreground border-border";
  return (
    <Badge variant="outline" className={cn("font-medium capitalize whitespace-nowrap", tone, className)}>
      {status}
    </Badge>
  );
}
