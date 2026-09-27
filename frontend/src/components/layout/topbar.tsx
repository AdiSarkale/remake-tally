import { useEffect, useState } from "react";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { ChevronsLeft, ChevronsRight, Command, LogOut, Moon, Search, Sun, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { useAuth } from "@/lib/auth";
import { useSettings } from "@/lib/api/hooks";

const CRUMB_LABELS: Record<string, string> = {
  sales: "Sales",
  purchasing: "Purchase",
  inventory: "Inventory",
  production: "Production",
  finance: "Finance",
  hr: "HR",
  reports: "Reports",
  settings: "Settings",
};

const PALETTE_PAGES = [
  { to: "/", label: "Dashboard" },
  { to: "/sales", label: "Sales — Invoices, Quotations, Orders" },
  { to: "/purchasing", label: "Purchase — POs, GRNs, Suppliers" },
  { to: "/inventory", label: "Inventory — Stock, Movements, Valuation" },
  { to: "/production", label: "Production — Orders, BOM, Routings, Work Centers" },
  { to: "/finance", label: "Finance — Receivables, Payables, Payments" },
  { to: "/hr", label: "HR — Employees, Skills" },
  { to: "/reports", label: "Reports" },
  { to: "/settings", label: "Settings" },
];

function useTheme() {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    const stored = window.localStorage.getItem("minitally.theme");
    const isDark = stored ? stored === "dark" : true;
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
  }, []);
  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    window.localStorage.setItem("minitally.theme", next ? "dark" : "light");
  };
  return { dark, toggle };
}

export function Topbar({
  collapsed,
  onToggleSidebar,
}: {
  collapsed: boolean;
  onToggleSidebar: () => void;
}) {
  const { profile, logout } = useAuth();
  const { data: settings } = useSettings();
  const { dark, toggle } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const segments = pathname.split("/").filter(Boolean);

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-background px-3">
      <Button variant="ghost" size="icon" className="size-8" onClick={onToggleSidebar} aria-label="Toggle sidebar">
        {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
      </Button>

      <Breadcrumb className="hidden md:block">
        <BreadcrumbList>
          <BreadcrumbItem>
            <BreadcrumbLink href="/">Minitally</BreadcrumbLink>
          </BreadcrumbItem>
          {segments.map((seg, i) => (
            <span key={seg} className="contents">
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                {i === segments.length - 1 ? (
                  <BreadcrumbPage>{CRUMB_LABELS[seg] ?? seg}</BreadcrumbPage>
                ) : (
                  <BreadcrumbLink href={`/${segments.slice(0, i + 1).join("/")}`}>
                    {CRUMB_LABELS[seg] ?? seg}
                  </BreadcrumbLink>
                )}
              </BreadcrumbItem>
            </span>
          ))}
        </BreadcrumbList>
      </Breadcrumb>

      <div className="ml-auto flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="hidden h-8 items-center gap-2 rounded-md border bg-muted/50 px-3 text-xs text-muted-foreground hover:bg-muted sm:flex"
        >
          <Search className="size-3.5" />
          Search pages…
          <kbd className="ml-2 inline-flex items-center gap-0.5 rounded border bg-background px-1 font-mono text-[10px]">
            <Command className="size-2.5" />K
          </kbd>
        </button>

        {settings ? (
          <div className="hidden flex-col items-end leading-none lg:flex">
            <span className="text-xs font-medium">{settings.name}</span>
            <span className="mt-0.5 font-mono text-[10px] text-muted-foreground">FY {settings.financial_year}</span>
          </div>
        ) : null}

        <Button variant="ghost" size="icon" className="size-8" onClick={toggle} aria-label="Toggle theme">
          {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="size-8" aria-label="User menu">
              <UserRound className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-52">
            <DropdownMenuLabel>
              <div className="text-sm">{profile?.full_name ?? "User"}</div>
              <div className="text-xs font-normal text-muted-foreground">{profile?.role ?? ""}</div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={logout}>
              <LogOut className="size-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <CommandDialog open={paletteOpen} onOpenChange={setPaletteOpen}>
        <CommandInput placeholder="Jump to a page or module…" />
        <CommandList>
          <CommandEmpty>No matching page.</CommandEmpty>
          <CommandGroup heading="Navigate">
            {PALETTE_PAGES.map((p) => (
              <CommandItem
                key={p.to}
                onSelect={() => {
                  setPaletteOpen(false);
                  navigate({ to: p.to });
                }}
              >
                {p.label}
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </header>
  );
}
