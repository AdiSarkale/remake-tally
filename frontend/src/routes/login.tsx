import { createFileRoute } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/lib/api/hooks";
import { storeSession } from "@/lib/api/client";
import { ApiError } from "@/lib/api/client";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — Minitally ERP" },
      { name: "description", content: "Sign in to the Minitally ERP platform." },
      { property: "og:title", content: "Sign in — Minitally ERP" },
      { property: "og:description", content: "Sign in to the Minitally ERP platform." },
    ],
  }),
  component: LoginPage,
});

const schema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});

type FormValues = z.infer<typeof schema>;

function LoginPage() {
  const login = useLogin();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const onSubmit = (values: FormValues) => {
    login.mutate(values, {
      onSuccess: (res) => {
        storeSession(res.access_token, {
          full_name: res.full_name,
          role: res.role,
          username: values.username,
        });
        toast.success(`Welcome back, ${res.full_name}`);
        window.location.assign(res.must_change_password ? "/change-password" : "/");
      },
      onError: (err) => {
        toast.error(err instanceof ApiError ? err.detail : "Sign in failed");
      },
    });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="flex size-11 items-center justify-center rounded-lg bg-primary font-mono text-xl font-bold text-primary-foreground">
            M
          </div>
          <h1 className="mt-4 text-lg font-bold tracking-[0.22em]">MINITALLY</h1>
          <p className="mt-1 text-xs uppercase tracking-widest text-muted-foreground">
            Intelligent ERP Platform
          </p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="space-y-4 rounded-lg border bg-card p-6 shadow-sm"
        >
          <div className="space-y-1.5">
            <Label htmlFor="username">Username</Label>
            <Input id="username" autoComplete="username" autoFocus {...register("username")} />
            {errors.username ? (
              <p className="text-xs text-destructive">{errors.username.message}</p>
            ) : null}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="current-password" {...register("password")} />
            {errors.password ? (
              <p className="text-xs text-destructive">{errors.password.message}</p>
            ) : null}
          </div>
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <p className="mt-6 text-center text-[11px] text-muted-foreground">
          Data → Intelligence → Operations → Control
        </p>
      </div>
    </div>
  );
}
