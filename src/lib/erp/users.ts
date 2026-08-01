import { logAudit, uid, update, getState } from "./store";
import type { Role, User } from "./types";

export interface UserDraft {
  username: string;
  fullName: string;
  email: string;
  role: Role;
  password: string;
  active: boolean;
}

type Result = { ok: boolean; error?: string };

export function validatePassword(pwd: string): string | null {
  if (pwd.trim().length < 6) return "Password must be at least 6 characters";
  return null;
}

/** Admin-only: create a new user account. */
export function createUser(draft: UserDraft, actor: string): Result {
  const username = draft.username.trim().toLowerCase();
  if (!username) return { ok: false, error: "Username is required" };
  if (!draft.fullName.trim()) return { ok: false, error: "Full name is required" };
  const pwdError = validatePassword(draft.password);
  if (pwdError) return { ok: false, error: pwdError };
  if (getState().users.some((u) => u.username.toLowerCase() === username))
    return { ok: false, error: "That username already exists" };

  const user: User = {
    id: uid(),
    username,
    fullName: draft.fullName.trim(),
    email: draft.email.trim(),
    role: draft.role,
    password: draft.password,
    active: draft.active,
  };
  update((s) => {
    s.users.push(user);
    logAudit(s, actor, "CREATE", "users", `User ${user.username} created with role ${user.role}`);
    return s;
  });
  return { ok: true };
}

/** Admin-only: edit profile fields (never the password). */
export function updateUser(
  id: string,
  patch: Pick<UserDraft, "fullName" | "email" | "role" | "active">,
  actor: string,
): Result {
  const state = getState();
  const target = state.users.find((u) => u.id === id);
  if (!target) return { ok: false, error: "User not found" };
  if (!patch.fullName.trim()) return { ok: false, error: "Full name is required" };
  if (target.role === "Admin" && patch.role !== "Admin") {
    const admins = state.users.filter((u) => u.role === "Admin" && u.active).length;
    if (admins <= 1) return { ok: false, error: "At least one active Admin is required" };
  }
  if (target.active && !patch.active && target.role === "Admin") {
    const admins = state.users.filter((u) => u.role === "Admin" && u.active).length;
    if (admins <= 1) return { ok: false, error: "At least one active Admin is required" };
  }
  update((s) => {
    const u = s.users.find((x) => x.id === id);
    if (u) {
      u.fullName = patch.fullName.trim();
      u.email = patch.email.trim();
      u.role = patch.role;
      u.active = patch.active;
    }
    logAudit(s, actor, "UPDATE", "users", `User ${target.username} updated (role ${patch.role}, ${patch.active ? "active" : "disabled"})`);
    return s;
  });
  return { ok: true };
}

/** Admin-only: set another user's password without knowing the old one. */
export function resetUserPassword(id: string, newPassword: string, actor: string): Result {
  const target = getState().users.find((u) => u.id === id);
  if (!target) return { ok: false, error: "User not found" };
  const pwdError = validatePassword(newPassword);
  if (pwdError) return { ok: false, error: pwdError };
  update((s) => {
    const u = s.users.find((x) => x.id === id);
    if (u) u.password = newPassword;
    logAudit(s, actor, "RESET", "users", `Password reset for ${target.username}`);
    return s;
  });
  return { ok: true };
}

/** Admin-only: enable / disable sign-in for a user. */
export function setUserActive(id: string, active: boolean, actor: string): Result {
  const state = getState();
  const target = state.users.find((u) => u.id === id);
  if (!target) return { ok: false, error: "User not found" };
  if (!active && target.role === "Admin") {
    const admins = state.users.filter((u) => u.role === "Admin" && u.active).length;
    if (admins <= 1) return { ok: false, error: "At least one active Admin is required" };
  }
  update((s) => {
    const u = s.users.find((x) => x.id === id);
    if (u) u.active = active;
    logAudit(s, actor, "UPDATE", "users", `${target.username} ${active ? "enabled" : "disabled"}`);
    return s;
  });
  return { ok: true };
}

export function generatePassword(): string {
  const chars = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789";
  const bytes = new Uint32Array(10);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}
