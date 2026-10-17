import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Topbar } from "@/components/layout/topbar";
import { getToken } from "@/lib/api/client";
import { Skeleton } from "@/components/ui/skeleton";
import { BrandMark } from "@/components/brand/brand-logo";

export const Route = createFileRoute("/_app")({
  component: AppLayout,
});

function readSidebarPreference(): boolean {
  try {
    return window.localStorage.getItem("minitally.sidebar") === "collapsed";
  } catch {
    return false;
  }
}

function writeSidebarPreference(collapsed: boolean): void {
  try {
    window.localStorage.setItem("minitally.sidebar", collapsed ? "collapsed" : "expanded");
  } catch {
    // UI state still works when browser storage is unavailable.
  }
}

function AppLayout() {
  const navigate = useNavigate();
  const [checked, setChecked] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      navigate({ to: "/login", replace: true });
      return;
    }
    setCollapsed(readSidebarPreference());
    setChecked(true);
  }, [navigate]);

  useEffect(() => {
    if (!mobileMenuOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileMenuOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobileMenuOpen]);

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <BrandMark className="size-10" />
          <Skeleton className="h-3 w-28" />
        </div>
      </div>
    );
  }

  const toggleSidebar = () => {
    if (window.matchMedia("(max-width: 767px)").matches) {
      setMobileMenuOpen((open) => !open);
      return;
    }
    setCollapsed((current) => {
      const next = !current;
      writeSidebarPreference(next);
      return next;
    });
  };

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      {mobileMenuOpen ? (
        <button
          type="button"
          aria-label="Close navigation menu"
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      ) : null}
      <AppSidebar
        collapsed={collapsed}
        mobileOpen={mobileMenuOpen}
        onMobileNavigate={() => setMobileMenuOpen(false)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar collapsed={collapsed} onToggleSidebar={toggleSidebar} mobileMenuOpen={mobileMenuOpen} />
        <main className="min-h-0 flex-1 overflow-y-auto scrollbar-thin p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
