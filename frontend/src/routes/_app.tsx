import { createFileRoute, Outlet, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Topbar } from "@/components/layout/topbar";
import { getToken } from "@/lib/api/client";
import { Skeleton } from "@/components/ui/skeleton";

export const Route = createFileRoute("/_app")({
  component: AppLayout,
});

function AppLayout() {
  const navigate = useNavigate();
  const [checked, setChecked] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      navigate({ to: "/login", replace: true });
      return;
    }
    setCollapsed(window.localStorage.getItem("minitally.sidebar") === "collapsed");
    setChecked(true);
  }, [navigate]);

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="flex flex-col items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-md bg-primary font-mono text-lg font-bold text-primary-foreground">
            M
          </div>
          <Skeleton className="h-3 w-28" />
        </div>
      </div>
    );
  }

  const toggleSidebar = () => {
    setCollapsed((c) => {
      window.localStorage.setItem("minitally.sidebar", c ? "expanded" : "collapsed");
      return !c;
    });
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <AppSidebar collapsed={collapsed} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar collapsed={collapsed} onToggleSidebar={toggleSidebar} />
        <main className="flex-1 overflow-y-auto scrollbar-thin p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
