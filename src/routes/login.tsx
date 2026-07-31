import { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { Gauge, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/erp/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — MiniTally ERP" },
      { name: "description", content: "Secure role-based sign in for the MiniTally manufacturing ERP." },
      { property: "og:title", content: "Sign in — MiniTally ERP" },
      { property: "og:description", content: "Secure role-based sign in for the MiniTally manufacturing ERP." },
    ],
  }),
  component: LoginPage,
});

const DEMO = [
  { role: "Admin", username: "admin", password: "admin123" },
  { role: "Accountant", username: "accounts", password: "accounts123" },
  { role: "Operator", username: "operator", password: "operator123" },
];

function LoginPage() {
  const { login, session, ready } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (ready && session) void navigate({ to: "/" });
  }, [ready, session, navigate]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    const res = login(username, password);
    setBusy(false);
    if (!res.ok) {
      toast.error(res.error ?? "Login failed");
      return;
    }
    toast.success("Welcome back");
    void navigate({ to: "/" });
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="bg-sidebar text-sidebar-foreground hidden flex-col justify-between p-12 lg:flex">
        <div className="flex items-center gap-2">
          <div className="bg-sidebar-primary text-sidebar-primary-foreground flex h-9 w-9 items-center justify-center rounded">
            <Gauge className="h-5 w-5" />
          </div>
          <span className="text-lg font-semibold">MiniTally ERP</span>
        </div>
        <div className="max-w-md">
          <h2 className="text-3xl font-semibold tracking-tight">
            Shop floor to ledger, without the spreadsheet chaos.
          </h2>
          <p className="text-sidebar-foreground/70 mt-4 text-sm leading-relaxed">
            Track production batches, raw material consumption, scrap and stock valuation in one lightweight system
            built for small manufacturers.
          </p>
          <div className="mt-10 grid grid-cols-3 gap-4 text-xs">
            {["Production", "Inventory", "Scrap"].map((x) => (
              <div key={x} className="border-sidebar-border rounded-md border px-3 py-2">
                {x}
              </div>
            ))}
          </div>
        </div>
        <p className="text-sidebar-foreground/50 text-xs">Role based access · JWT sessions · Audit logged</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
          <p className="text-muted-foreground mt-1 text-sm">Use your MiniTally credentials to continue.</p>
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <Label htmlFor="username" className="mb-1.5 block text-xs">
                Username
              </Label>
              <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            </div>
            <div>
              <Label htmlFor="password" className="mb-1.5 block text-xs">
                Password
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={busy}>
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sign in
            </Button>
          </form>

          <div className="panel mt-6 p-3">
            <p className="text-muted-foreground mb-2 text-[11px] font-semibold tracking-wider uppercase">
              Demo accounts
            </p>
            <div className="space-y-1">
              {DEMO.map((d) => (
                <button
                  key={d.username}
                  onClick={() => {
                    setUsername(d.username);
                    setPassword(d.password);
                  }}
                  className="hover:bg-accent flex w-full items-center justify-between rounded px-2 py-1.5 text-xs"
                >
                  <span className="font-medium">{d.role}</span>
                  <span className="num text-muted-foreground">
                    {d.username} / {d.password}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
