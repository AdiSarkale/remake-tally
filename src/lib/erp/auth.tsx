import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getState, logAudit, update } from "./store";
import type { Role, User } from "./types";
import { apiFetch } from "../api";

const SESSION_KEY = "minitally-session-v1";

export interface Session {
  token: string;
  userId: string;
  username: string;
  fullName: string;
  role: Role;
}

interface AuthValue {
  session: Session | null;
  ready: boolean;
  login: (
    username: string,
    password: string,
  ) => Promise<{ ok: boolean; error?: string }>;
  logout: () => void;
  changePassword: (current: string, next: string) => { ok: boolean; error?: string };
}

const AuthContext = createContext<AuthValue | null>(null);



export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(SESSION_KEY);
      if (raw) setSession(JSON.parse(raw) as Session);
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const data = await apiFetch("/api/v1/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username.trim(),
          password,
        }),
      });

      localStorage.setItem("minitally-token", data.access_token);

      const next: Session = {
        token: data.access_token,
        userId: data.sub ?? username,
        username,
        fullName: data.full_name,
        role: data.role,
      };

      localStorage.setItem(SESSION_KEY, JSON.stringify(next));
      setSession(next);

      return { ok: true };
    } catch (error) {
      return {
        ok: false,
        error:
          error instanceof Error
            ? error.message
            : "Invalid username or password",
      };
    }
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem("minitally-token");
    setSession(null);
  }, []);

  const changePassword = useCallback(
    (current: string, next: string) => {
      if (!session) return { ok: false, error: "Not signed in" };
      if (next.length < 6) return { ok: false, error: "New password must be at least 6 characters" };
      const user = getState().users.find((u) => u.id === session.userId);
      if (!user || user.password !== current) return { ok: false, error: "Current password is incorrect" };
      update((s) => {
        const target = s.users.find((u) => u.id === session.userId);
        if (target) target.password = next;
        logAudit(s, session.username, "UPDATE", "auth", "Password changed");
        return s;
      });
      return { ok: true };
    },
    [session],
  );

  const value = useMemo(
    () => ({ session, ready, login, logout, changePassword }),
    [session, ready, login, logout, changePassword],
  );
  return (
    <AuthContext.Provider value= { value } >
    { children }
    </AuthContext.Provider>
);
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
