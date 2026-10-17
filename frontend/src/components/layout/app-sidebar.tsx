import { Link, useRouterState } from "@tanstack/react-router";
import {
  Boxes,
  Factory,
  FileBarChart,
  LayoutDashboard,
  Settings,
  ShoppingCart,
  TrendingUp,
  Users,
  Wallet,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { BrandLockup, BrandMark } from "@/components/brand/brand-logo";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  area?: string;
  anyArea?: string[];
}

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/sales", label: "Sales", icon: TrendingUp, area: "sales" },
  { to: "/purchasing", label: "Purchase", icon: ShoppingCart, area: "purchase_requests" },
  { to: "/inventory", label: "Inventory", icon: Boxes, area: "inventory" },
  { to: "/production", label: "Production", icon: Factory, area: "production" },
  { to: "/finance", label: "Finance", icon: Wallet, area: "finance" },
  { to: "/hr", label: "HR", icon: Users, anyArea: ["production", "hr"] },
  { to: "/reports", label: "Reports", icon: FileBarChart, area: "reports" },
  { to: "/settings", label: "Settings", icon: Settings, area: "settings" },
];

export function AppSidebar({ collapsed }: { collapsed: boolean }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { can } = useAuth();

  const items = NAV.filter((item) => item.area ? can(item.area) : item.anyArea ? item.anyArea.some((area) => can(area)) : true);

  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r bg-sidebar transition-[width] duration-200",
        collapsed ? "w-14" : "w-56",
      )}
    >
      <div className={cn("flex h-14 items-center border-b", collapsed ? "justify-center px-0" : "gap-2.5 px-4")}>
        <div className="shrink-0">{collapsed ? <BrandMark className="size-7" /> : <BrandLockup compact />}</div>
      </div>

      <ScrollArea className="flex-1 py-3">
        <nav className={cn("flex flex-col gap-0.5", collapsed ? "px-2" : "px-3")}>
          {items.map((item) => {
            const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
            const link = (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors",
                  collapsed && "justify-center px-0",
                  active
                    ? "bg-sidebar-accent text-sidebar-primary"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                )}
              >
                <item.icon className={cn("size-4 shrink-0", active && "text-sidebar-primary")} />
                {!collapsed ? item.label : null}
              </Link>
            );
            if (!collapsed) return link;
            return (
              <Tooltip key={item.to} delayDuration={0}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </nav>
      </ScrollArea>

      {!collapsed ? (
        <div className="border-t px-4 py-3 text-[10px] uppercase tracking-widest text-muted-foreground">
          Data → Intelligence → Control
        </div>
      ) : null}
    </aside>
  );
}
