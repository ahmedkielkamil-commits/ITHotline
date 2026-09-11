import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as adminApi from "../api/admin";
import { ApiError, clearToken, getToken, setToken } from "../api/client";
import type { AdminUser } from "../api/types";

interface AuthContextValue {
  admin: AdminUser | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<AdminUser | null>(() => {
    const raw = localStorage.getItem("ithotline_admin_profile");
    return raw ? (JSON.parse(raw) as AdminUser) : null;
  });
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [loading, setLoading] = useState(false);

  const logout = useCallback(() => {
    clearToken();
    localStorage.removeItem("ithotline_admin_profile");
    setTokenState(null);
    setAdmin(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setLoading(true);
    try {
      const result = await adminApi.login(email.trim(), password);
      setToken(result.token);
      setTokenState(result.token);
      setAdmin(result.admin);
      localStorage.setItem("ithotline_admin_profile", JSON.stringify(result.admin));
    } finally {
      setLoading(false);
    }
  }, []);

  const value = useMemo(
    () => ({ admin, token, loading, login, logout }),
    [admin, token, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function authErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong";
}
