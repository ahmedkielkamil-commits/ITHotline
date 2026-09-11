export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AdminUser {
  adminid: number;
  firstName: string;
  lastName: string;
  email: string;
}

export interface ApiProviderDetail {
  id: string;
  itid: number;
  firstName: string;
  lastName: string;
  name: string;
  email: string;
  phone: string | null;
  status: string;
  tier: string;
  availability?: boolean;
  service_radius_m?: number | null;
  skills: string[];
  vouchedBy?: string | null;
  vouchedRelationship?: string | null;
  lat?: number | null;
  lng?: number | null;
  daysWaiting?: number | null;
}

export interface ApiBusinessDetail {
  id: string;
  businessid: number;
  name: string;
  email: string;
  address: string;
  category: string;
  status: string;
  owner?: string;
  contact?: string;
  lat?: number | null;
  lng?: number | null;
  daysWaiting?: number | null;
}

export interface ApiUserSummary {
  id: string;
  type: "business" | "provider";
  name: string;
  email: string;
  status: string;
  phone?: string | null;
  region?: string | null;
  subtype?: string | null;
}

export interface LoginResponse {
  token: string;
  admin: AdminUser;
}
