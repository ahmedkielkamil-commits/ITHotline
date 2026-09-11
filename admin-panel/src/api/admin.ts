import { apiFetch } from "./client";
import type {
  ApiBusinessDetail,
  ApiProviderDetail,
  ApiUserSummary,
  LoginResponse,
  Paginated,
} from "./types";

export function login(email: string, password: string) {
  return apiFetch<LoginResponse>("/auth/admin/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify({ email, password }),
  });
}

export function listPendingProviders(params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.offset != null) query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query}` : "";
  return apiFetch<Paginated<ApiProviderDetail>>(`/admin/providers/pending${suffix}`);
}

export function listPendingBusinesses(params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.offset != null) query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query}` : "";
  return apiFetch<Paginated<ApiBusinessDetail>>(`/admin/businesses/pending${suffix}`);
}

export function listUsers(params?: {
  status?: string;
  role?: string;
  search?: string;
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.role) query.set("role", params.role);
  if (params?.search) query.set("search", params.search);
  if (params?.limit != null) query.set("limit", String(params.limit));
  if (params?.offset != null) query.set("offset", String(params.offset));
  const suffix = query.toString() ? `?${query}` : "";
  return apiFetch<Paginated<ApiUserSummary>>(`/admin/users${suffix}`);
}

export function approveProvider(providerId: number) {
  return apiFetch<ApiProviderDetail>(`/admin/providers/${providerId}/approve`, {
    method: "POST",
  });
}

export function rejectProvider(providerId: number, reason?: string) {
  return apiFetch<ApiProviderDetail>(`/admin/providers/${providerId}/reject`, {
    method: "POST",
    body: JSON.stringify(reason ? { reason } : {}),
  });
}

export function approveBusiness(businessId: number) {
  return apiFetch<ApiBusinessDetail>(`/admin/businesses/${businessId}/approve`, {
    method: "POST",
  });
}

export function rejectBusiness(businessId: number, reason?: string) {
  return apiFetch<ApiBusinessDetail>(`/admin/businesses/${businessId}/reject`, {
    method: "POST",
    body: JSON.stringify(reason ? { reason } : {}),
  });
}

export function setUserStatus(userRef: string, status: "approved" | "suspended") {
  return apiFetch<ApiUserSummary>(`/admin/users/${encodeURIComponent(userRef)}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function parseNumericId(userRef: string): number | null {
  const parts = userRef.split("-");
  if (parts.length < 2) return null;
  const id = Number(parts[parts.length - 1]);
  return Number.isFinite(id) ? id : null;
}
