import type { ApiBusinessDetail, ApiProviderDetail, ApiUserSummary } from "../api/types";

export interface Provider {
  id: string;
  itid: number;
  name: string;
  tier: "Shadow" | "Practitioner";
  daysWaiting: number;
  skills: string[];
  vouchedBy?: { name: string; relationship: string };
  shadowJobs?: undefined;
  referralConfirmed?: boolean;
  experience: string;
  certifications: string[];
  region: string;
}

export interface BusinessApproval {
  id: string;
  businessid: number;
  name: string;
  address: string;
  category: string;
  owner: string;
  phone: string;
  referralSource: string;
  daysWaiting: number;
  contact: string;
  lat: number;
  lng: number;
}

export interface UserRow {
  id: string;
  name: string;
  role: "Provider" | "Business";
  status: "Active" | "Suspended" | "Pending";
  rating: number | null;
  joinDate: string;
  email: string;
  phone: string;
  region: string;
  disputes: DisputeEntry[];
}

export interface DisputeEntry {
  id: string;
  date: string;
  type: "Tech no-show" | "Business refused payment" | "Complaint" | "Late arrival";
  note: string;
  resolvedBy: string;
}

function formatTier(tier: string): Provider["tier"] {
  return tier?.toLowerCase() === "practitioner" ? "Practitioner" : "Shadow";
}

function formatDaysWaiting(days: number | null | undefined): number {
  return days ?? 0;
}

export function mapProvider(api: ApiProviderDetail): Provider {
  const tier = formatTier(api.tier);
  const radius =
    api.service_radius_m != null ? `${api.service_radius_m}m service radius` : "Region not set";

  return {
    id: api.id,
    itid: api.itid,
    name: api.name,
    tier,
    daysWaiting: formatDaysWaiting(api.daysWaiting),
    skills: api.skills ?? [],
    vouchedBy:
      api.vouchedBy != null
        ? {
            name: api.vouchedBy,
            relationship: api.vouchedRelationship ?? "Referral",
          }
        : undefined,
    referralConfirmed: tier === "Practitioner" ? true : undefined,
    experience: [
      api.email,
      api.phone ? `Phone: ${api.phone}` : null,
      api.availability != null ? `Available: ${api.availability ? "Yes" : "No"}` : null,
    ]
      .filter(Boolean)
      .join(" · "),
    certifications: [],
    region: radius,
  };
}

export function mapBusiness(api: ApiBusinessDetail): BusinessApproval {
  return {
    id: api.id,
    businessid: api.businessid,
    name: api.name,
    address: api.address || "—",
    category: api.category || "—",
    owner: api.owner ?? api.name,
    phone: "—",
    referralSource: api.email || "Direct signup",
    daysWaiting: formatDaysWaiting(api.daysWaiting),
    contact: api.contact ?? api.email ?? "—",
    lat: api.lat ?? 45.5231,
    lng: api.lng ?? -122.6765,
  };
}

export function mapUser(api: ApiUserSummary): UserRow {
  let status: UserRow["status"] = "Pending";
  if (api.status === "approved") status = "Active";
  if (api.status === "suspended") status = "Suspended";

  return {
    id: api.id,
    name: api.name,
    role: api.type === "provider" ? "Provider" : "Business",
    status,
    rating: null,
    joinDate: "—",
    email: api.email,
    phone: api.phone ?? "—",
    region: api.region ?? api.subtype ?? "—",
    disputes: [],
  };
}

export function userStatusToApi(status: UserRow["status"]): "approved" | "suspended" | null {
  if (status === "Active") return "approved";
  if (status === "Suspended") return "suspended";
  return null;
}
