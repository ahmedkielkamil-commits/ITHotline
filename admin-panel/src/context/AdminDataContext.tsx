import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import * as adminApi from "../api/admin";
import {
  mapBusiness,
  mapProvider,
  mapUser,
  type BusinessApproval,
  type Provider,
  type UserRow,
} from "../lib/mappers";

interface AdminDataContextValue {
  pendingProviders: Provider[];
  pendingBusinesses: BusinessApproval[];
  users: UserRow[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  approveProvider: (itid: number) => Promise<void>;
  rejectProvider: (itid: number, reason?: string) => Promise<void>;
  approveBusiness: (businessid: number) => Promise<void>;
  rejectBusiness: (businessid: number, reason?: string) => Promise<void>;
  suspendUser: (userRef: string) => Promise<void>;
  reactivateUser: (userRef: string) => Promise<void>;
  updateUserLocal: (userRef: string, patch: Partial<UserRow>) => void;
}

const AdminDataContext = createContext<AdminDataContextValue | null>(null);

export function AdminDataProvider({ children }: { children: ReactNode }) {
  const [pendingProviders, setPendingProviders] = useState<Provider[]>([]);
  const [pendingBusinesses, setPendingBusinesses] = useState<BusinessApproval[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [providersRes, businessesRes, usersRes] = await Promise.all([
        adminApi.listPendingProviders({ limit: 100 }),
        adminApi.listPendingBusinesses({ limit: 100 }),
        adminApi.listUsers({ limit: 100 }),
      ]);
      setPendingProviders(providersRes.items.map(mapProvider));
      setPendingBusinesses(businessesRes.items.map(mapBusiness));
      setUsers(usersRes.items.map(mapUser));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const approveProvider = useCallback(
    async (itid: number) => {
      await adminApi.approveProvider(itid);
      await refresh();
    },
    [refresh]
  );

  const rejectProvider = useCallback(
    async (itid: number, reason?: string) => {
      await adminApi.rejectProvider(itid, reason);
      await refresh();
    },
    [refresh]
  );

  const approveBusiness = useCallback(
    async (businessid: number) => {
      await adminApi.approveBusiness(businessid);
      await refresh();
    },
    [refresh]
  );

  const rejectBusiness = useCallback(
    async (businessid: number, reason?: string) => {
      await adminApi.rejectBusiness(businessid, reason);
      await refresh();
    },
    [refresh]
  );

  const suspendUser = useCallback(async (userRef: string) => {
    await adminApi.setUserStatus(userRef, "suspended");
    setUsers((prev) =>
      prev.map((u) => (u.id === userRef ? { ...u, status: "Suspended" } : u))
    );
  }, []);

  const reactivateUser = useCallback(async (userRef: string) => {
    await adminApi.setUserStatus(userRef, "approved");
    setUsers((prev) =>
      prev.map((u) => (u.id === userRef ? { ...u, status: "Active" } : u))
    );
  }, []);

  const updateUserLocal = useCallback((userRef: string, patch: Partial<UserRow>) => {
    setUsers((prev) => prev.map((u) => (u.id === userRef ? { ...u, ...patch } : u)));
  }, []);

  const value = useMemo(
    () => ({
      pendingProviders,
      pendingBusinesses,
      users,
      loading,
      error,
      refresh,
      approveProvider,
      rejectProvider,
      approveBusiness,
      rejectBusiness,
      suspendUser,
      reactivateUser,
      updateUserLocal,
    }),
    [
      pendingProviders,
      pendingBusinesses,
      users,
      loading,
      error,
      refresh,
      approveProvider,
      rejectProvider,
      approveBusiness,
      rejectBusiness,
      suspendUser,
      reactivateUser,
      updateUserLocal,
    ]
  );

  return <AdminDataContext.Provider value={value}>{children}</AdminDataContext.Provider>;
}

export function useAdminData() {
  const ctx = useContext(AdminDataContext);
  if (!ctx) throw new Error("useAdminData must be used within AdminDataProvider");
  return ctx;
}
