import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  Boxes,
  Factory,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  ReceiptText,
  Recycle,
  Search,
  Settings,
  Sun,
  Truck,
  Users,
  Wrench,
  Package,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/erp/auth";
import { can } from "@/lib/erp/types";
import { useErp } from "@/lib/erp/store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Gauge;
  area: string;
}

const NAV: { group: string; items: NavItem[] }[] = [
  {
    group: "Overview",
    items: [{ to: "/", label: "Dashboard", icon: LayoutDashboard, area: "inventory" }],
  },
  {
    group: "Masters",
    items: [
      { to: "/masters/customers", label: "Customers", icon: Users, area: "masters" },
      { to: "/masters/suppliers", label: "Suppliers", icon: Truck, area: "masters" },
      { to: "/masters/products", label: "Products", icon: Package, area: "masters" },
      { to: "/masters/materials", label: "Raw Materials", icon: Wrench, area: "masters" },
      { to: "/masters/scrap-types", label: "Scrap Types", icon: Recycle, area: "masters" },
    ],
  },
  {
    group: "Operations",
    items: [
      { to: "/inventory", label: "Inventory", icon: Boxes, area: "inventory" },
      { to: "/production", label: "Production", icon: Factory, area: "production" },
      { to: "/scrap", label: "Scrap", icon: Recycle, area: "scrap" },
      { to: "/invoices", label: "Sales Invoices", icon: ReceiptText, area: "sales" },
    ],
  },
  {
    group: "System",
    items: [{ to: "/settings", label: "Settings", icon: Settings, area: "settings" }],
  },
];

function useTheme() {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    const stored = window.localStorage.getItem("minitally-theme");
    const isDark = stored ? stored === "dark" : true;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);
  const toggle = () => {
    setDark((prev) => {
      const next = !prev;
      document.documentElement.classList.toggle("dark", next);
      window.localStorage.setItem("minitally-theme", next ? "dark" : "light");
      return next;
    });
  };
  return { dark, toggle };
}

function GlobalSearch() {
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  const data = useErp((s) => ({
    products: s.products,
    materials: s.materials,
    customers: s.customers,
    suppliers: s.suppliers,
    production: s.production,
    invoices: s.invoices,
  }));

  const results = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (term.length < 2) return [];
    const hits: { label: string; sub: string; to: string }[] = [];
    data.products
      .filter((p) => `${p.name} ${p.code}`.toLowerCase().includes(term))
      .forEach((p) => hits.push({ label: p.name, sub: `Product · ${p.code}`, to: "/masters/products" }));
    data.materials
      .filter((m) => m.name.toLowerCase().includes(term))
      .forEach((m) => hits.push({ label: m.name, sub: "Raw material", to: "/masters/materials" }));
    data.customers
      .filter((c) => c.name.toLowerCase().includes(term))
      .forEach((c) => hits.push({ label: c.name, sub: "Customer", to: "/masters/customers" }));
    data.suppliers
      .filter((s) => s.name.toLowerCase().includes(term))
      .forEach((s) => hits.push({ label: s.name, sub: "Supplier", to: "/masters/suppliers" }));
    data.production
      .filter((p) => p.batchNo.toLowerCase().includes(term))
      .forEach((p) => hits.push({ label: p.batchNo, sub: `Batch · ${p.productName}`, to: "/production" }));
    data.invoices
      .filter((i) => `${i.invoiceNo} ${i.customerName} ${i.poReference}`.toLowerCase().includes(term))
      .forEach((i) => hits.push({ label: i.invoiceNo, sub: `Invoice · ${i.customerName}`, to: "/invoices" }));
    return hits.slice(0, 8);
  }, [q, data]);

  return (
    <div className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search products, batches, parties…"
        className="pl-9"
      />
      {results.length > 0 && (
        <div className="panel absolute top-full right-0 left-0 z-50 mt-2 overflow-hidden p-1">
          {results.map((r) => (
            <button
              key={`${r.to}-${r.label}`}
              onClick={() => {
                setQ("");
                void navigate({ to: r.to });
              }}
              className="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm hover:bg-accent"
            >
              <span className="font-medium">{r.label}</span>
              <span className="text-xs text-muted-foreground">{r.sub}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { session, ready, logout } = useAuth();
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { dark, toggle } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const company = useErp((s) => s.settings.name);
  const financialYear = useErp((s) => s.settings.financialYear);

  useEffect(() => {
    if (ready && !session) void navigate({ to: "/login" });
  }, [ready, session, navigate]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (!ready || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const role = session.role;

  return (
    <div className="flex min-h-screen w-full bg-background">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-sidebar text-sidebar-foreground transition-transform lg:static lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-16 items-center gap-2 border-b border-sidebar-border px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded bg-sidebar-primary text-sidebar-primary-foreground">
            <Gauge className="h-4 w-4" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold">MiniTally ERP</p>
            <p className="truncate text-[11px] text-sidebar-foreground/60">{company}</p>
          </div>
          <button className="ml-auto lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close menu">
            <X className="h-4 w-4" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {NAV.map((group) => {
            const items = group.items.filter((i) => can(role, i.area));
            if (!items.length) return null;
            return (
              <div key={group.group} className="mb-5">
                <p className="px-2 pb-2 text-[10px] font-semibold tracking-widest text-sidebar-foreground/45 uppercase">
                  {group.group}
                </p>
                <div className="space-y-0.5">
                  {items.map((item) => {
                    const active = pathname === item.to;
                    return (
                      <Link
                        key={item.to}
                        to={item.to}
                        className={cn(
                          "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                          active
                            ? "bg-sidebar-primary font-medium text-sidebar-primary-foreground"
                            : "text-sidebar-foreground/85 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                        )}
                      >
                        <item.icon className="h-4 w-4" />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>
        <div className="border-t border-sidebar-border px-4 py-3 text-[11px] text-sidebar-foreground/55">
          FY {financialYear} · v1.0
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-card/85 px-4 backdrop-blur lg:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setMobileOpen(true)}>
            <Menu className="h-5 w-5" />
          </Button>
          <GlobalSearch />
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="gap-2">
                  <span className="hidden sm:inline">{session.fullName}</span>
                  <Badge variant="secondary" className="text-[10px]">
                    {role}
                  </Badge>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-52">
                <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
                  Signed in as {session.username}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => void navigate({ to: "/settings" })}>
                  <Settings className="mr-2 h-4 w-4" /> Settings & password
                </DropdownMenuItem>
                <DropdownMenuItem onClick={logout}>
                  <LogOut className="mr-2 h-4 w-4" /> Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main className="flex-1 p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
