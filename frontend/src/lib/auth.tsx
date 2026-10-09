import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { clearSession, getStoredProfile, getToken, type StoredProfile } from "./api/client";
import { useMe } from "./api/hooks";
import type { Role } from "./api/types";

// Mirrors backend ROLE_PERMISSIONS in app/api/deps.py — used only for
// navigation visibility; the backend enforces the real permissions.
const ROLE_AREAS: Record<Role, Set<string>> = {
  Admin: new Set(["masters", "inventory", "production", "scrap", "sales", "finance", "settings", "reports", "purchase_requests", "hr"]),
  Accountant: new Set(["masters", "inventory", "sales", "reports", "purchase_requests"]),
  Operator: new Set(["production", "scrap", "inventory", "purchase_requests"]),
};

interface AuthState {
  token: string | null;
  profile: StoredProfile | null;
  role: Role | null;
  can: (area: string) => boolean;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const token = getToken();
  const { data: me } = useMe(!!token);
  const stored = getStoredProfile();

  const value = useMemo<AuthState>(() => {
    const profile: StoredProfile | null = me
      ? {
          full_name: me.full_name,
          role: me.role,
          username: me.username,
          company_id: me.company_id,
          company_code: me.company_code,
          company_name: me.company_name,
        }
      : stored;
    const role = (me?.role ?? profile?.role) as Role | null;
    return {
      token,
      profile,
      role,
      can: (area: string) => (role ? (ROLE_AREAS[role]?.has(area) ?? false) : false),
      logout: () => {
        clearSession();
        navigate({ to: "/login" });
      },
    };
  }, [token, me, stored, navigate]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
