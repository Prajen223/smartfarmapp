import { AdminUser } from "./types";

const TOKEN_KEY = "farmsaathi_admin_token";
const USER_KEY = "farmsaathi_admin_user";

export function getAdminToken(): string | null {
    if (typeof window === "undefined") return null;
    return sessionStorage.getItem(TOKEN_KEY);
}

export function setAdminToken(token: string): void {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(TOKEN_KEY, token);
}

export function getAdminUser(): AdminUser | null {
    if (typeof window === "undefined") return null;
    const raw = sessionStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
        return JSON.parse(raw) as AdminUser;
    } catch {
        return null;
    }
}

export function setAdminUser(user: AdminUser): void {
    if (typeof window === "undefined") return;
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAdminSession(): void {
    if (typeof window === "undefined") return;
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
}
