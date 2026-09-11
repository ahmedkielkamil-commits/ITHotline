import { useEffect, useState } from "react";
import { useAuth } from "./auth/AuthContext";
import { LoginScreen } from "./auth/LoginScreen";
import { AdminDataProvider, useAdminData } from "./context/AdminDataContext";
import type { BusinessApproval, DisputeEntry, Provider, UserRow } from "./lib/mappers";
import {
  LayoutDashboard,
  Ticket,
  UserCheck,
  Building2,
  Users,
  BarChart3,
  Phone,
  AlertTriangle,
  Clock,
  CheckCircle2,
  ChevronRight,
  Star,
  Info,
  X,
  Search,
  MapPin,
  Wifi,
  Monitor,
  Server,
  Shield,
  Plus,
} from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// ─── Types ────────────────────────────────────────────────────────────────────

type Screen = "overview" | "live-tickets" | "provider-approvals" | "business-approvals" | "users" | "analytics";

interface TicketRow {
  id: string;
  business: string;
  category: string;
  urgency: "critical" | "high" | "normal";
  status: "Open" | "Claimed" | "En route" | "On site";
  tech: string | null;
  elapsed: string;
  escalated?: boolean;
}

interface SupportQuestion {
  id: string;
  user: string;
  snippet: string;
  time: string;
}

interface AvailableProvider {
  id: string;
  name: string;
  phone: string;
  specialty: string;
}

// ─── Mock Data (screens without admin API endpoints) ─────────────────────────

const TICKETS: TicketRow[] = [
  { id: "T-1041", business: "Meridian Legal Group", category: "Network", urgency: "critical", status: "Open", tech: null, elapsed: "18 min", escalated: true },
  { id: "T-1039", business: "Copper & Vale Roasters", category: "Network", urgency: "high", status: "Open", tech: null, elapsed: "14 min", escalated: true },
  { id: "T-1042", business: "Northgate Dental", category: "Hardware", urgency: "high", status: "Claimed", tech: "Dex Okafor", elapsed: "6 min" },
  { id: "T-1038", business: "Lighthouse Bookkeeping", category: "Software", urgency: "normal", status: "En route", tech: "Sara Pham", elapsed: "22 min" },
  { id: "T-1036", business: "Vantage Realty", category: "Security", urgency: "normal", status: "On site", tech: "Marcus Webb", elapsed: "41 min" },
  { id: "T-1035", business: "Orion Staffing Co.", category: "Server", urgency: "high", status: "On site", tech: "Keisha Tran", elapsed: "1h 2min" },
  { id: "T-1033", business: "Blue Pines Pediatrics", category: "Hardware", urgency: "normal", status: "Claimed", tech: "Dex Okafor", elapsed: "3 min" },
];

const SUPPORT_QUESTIONS: SupportQuestion[] = [
  { id: "Q-81", user: "Helen Chu (Amber Peak)", snippet: "Hi — we signed up but haven't received our login credentials yet...", time: "9 min ago" },
  { id: "Q-82", user: "Tomas Reyes (Fernwood)", snippet: "Is there a way to update our service address? We moved locations last week.", time: "34 min ago" },
  { id: "Q-83", user: "Marcus Webb (Provider)", snippet: "Getting an error on the dispatch app — 'unable to connect' after update.", time: "1h ago" },
];

const AVAILABLE_PROVIDERS: AvailableProvider[] = [
  { id: "AP-1", name: "Dex Okafor", phone: "(503) 812-4401", specialty: "Network / VoIP" },
  { id: "AP-2", name: "Sara Pham", phone: "(503) 774-9203", specialty: "macOS / Cloud" },
  { id: "AP-3", name: "Keisha Tran", phone: "(503) 651-0078", specialty: "Windows / Security" },
  { id: "AP-4", name: "Jordan Reese", phone: "(503) 445-3310", specialty: "Hardware / Printer" },
];

const TICKET_TREND = [
  { week: "Jun 3", tickets: 18 }, { week: "Jun 10", tickets: 22 }, { week: "Jun 17", tickets: 19 },
  { week: "Jun 24", tickets: 28 }, { week: "Jul 1", tickets: 31 }, { week: "Jul 8", tickets: 26 },
  { week: "Jul 15", tickets: 34 },
];

const CATEGORY_DATA = [
  { category: "Network", count: 42 }, { category: "Hardware", count: 38 }, { category: "Software", count: 27 },
  { category: "Security", count: 19 }, { category: "Server", count: 14 },
];

const TOP_PROVIDERS = [
  { name: "Dex Okafor", jobs: 47, rating: 4.9, earned: "$5,640" },
  { name: "Sara Pham", jobs: 39, rating: 4.8, earned: "$4,680" },
  { name: "Marcus Webb", jobs: 36, rating: 4.7, earned: "$4,320" },
  { name: "Jordan Reese", jobs: 28, rating: 4.6, earned: "$3,360" },
  { name: "Keisha Tran", jobs: 21, rating: 3.9, earned: "$2,520" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

const categoryIcon = (cat: string) => {
  const map: Record<string, React.ReactNode> = {
    Network: <Wifi size={13} />, Hardware: <Monitor size={13} />, Server: <Server size={13} />,
    Security: <Shield size={13} />, Software: <Star size={13} />,
  };
  return map[cat] ?? <Info size={13} />;
};

const urgencyPill = (u: TicketRow["urgency"]) => {
  if (u === "critical") return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700">Critical</span>;
  if (u === "high") return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">High</span>;
  return <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-600">Normal</span>;
};

const statusBadge = (s: TicketRow["status"]) => {
  const map: Record<TicketRow["status"], string> = {
    Open: "text-gray-500", Claimed: "text-teal-700", "En route": "text-blue-600", "On site": "text-green-600",
  };
  return <span className={`text-xs font-medium ${map[s]}`}>{s}</span>;
};

const tierBadge = (tier: Provider["tier"]) => {
  if (tier === "Shadow") return <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-violet-100 text-violet-700">Shadow</span>;
  return <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-teal-100 text-teal-700">Practitioner</span>;
};

const userStatusPill = (s: UserRow["status"]) => {
  if (s === "Active") return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-teal-100 text-teal-700"><span className="w-1.5 h-1.5 rounded-full bg-teal-500 inline-block" />Active</span>;
  if (s === "Pending") return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700"><span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />Pending</span>;
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><span className="w-1.5 h-1.5 rounded-full bg-red-500 inline-block" />Suspended</span>;
};

// ─── Stat Tile ────────────────────────────────────────────────────────────────

function StatTile({ label, value, accent, sub }: { label: string; value: string | number; accent?: "amber" | "teal" | "green"; sub?: string }) {
  const valueClass = accent === "amber" ? "text-amber-600" : accent === "teal" ? "text-teal-700" : accent === "green" ? "text-green-700" : "text-foreground";
  return (
    <div className="flex-1 min-w-0 bg-card rounded-xl border border-border px-4 py-3">
      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${valueClass}`}>{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, children, highlight }: { title: string; children: React.ReactNode; highlight?: boolean }) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${highlight ? "border-violet-300 bg-violet-50" : "border-border bg-card"}`}>
      <p className={`text-xs font-semibold uppercase tracking-wide mb-2 ${highlight ? "text-violet-600" : "text-muted-foreground"}`}>{title}</p>
      {children}
    </div>
  );
}

// ─── Toast ────────────────────────────────────────────────────────────────────

function Toast({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-2 bg-teal-700 text-white text-sm font-medium px-4 py-2.5 rounded-xl">
      <CheckCircle2 size={14} />{message}
    </div>
  );
}

// ─── Overview ─────────────────────────────────────────────────────────────────

function OverviewScreen({
  onNav,
  providers,
  businesses,
}: {
  onNav: (s: Screen, id?: string) => void;
  providers: Provider[];
  businesses: BusinessApproval[];
}) {
  return (
    <div className="flex flex-col gap-5 h-full overflow-y-auto pr-1">
      <div className="flex gap-3">
        <StatTile label="Open Tickets" value={7} />
        <StatTile label="Unclaimed >10 min" value={2} accent="amber" />
        <StatTile label="Providers Available" value={4} accent="teal" />
        <StatTile label="Jobs Completed (week)" value={31} />
      </div>
      <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
        <div className="flex flex-col gap-2 min-h-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pending Providers</span>
            <button onClick={() => onNav("provider-approvals")} className="text-xs text-primary font-medium hover:underline">View all</button>
          </div>
          {providers.length === 0 ? (
            <p className="text-xs text-muted-foreground italic px-1">No pending provider applications.</p>
          ) : (
            providers.map((p) => (
            <button key={p.id} onClick={() => onNav("provider-approvals", p.id)} className="w-full text-left bg-card border border-border rounded-xl px-3.5 py-3 hover:border-primary/30 hover:bg-accent transition-colors group">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">{p.name}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">{p.region}</p>
                </div>
                {tierBadge(p.tier)}
              </div>
              <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1"><Clock size={11} />{p.daysWaiting > 0 ? `Waiting ${p.daysWaiting} ${p.daysWaiting === 1 ? "day" : "days"}` : "Awaiting review"}</p>
            </button>
            ))
          )}
        </div>
        <div className="flex flex-col gap-2 min-h-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Pending Businesses</span>
            <button onClick={() => onNav("business-approvals")} className="text-xs text-primary font-medium hover:underline">View all</button>
          </div>
          {businesses.length === 0 ? (
            <p className="text-xs text-muted-foreground italic px-1">No pending business applications.</p>
          ) : (
            businesses.map((b) => (
            <button key={b.id} onClick={() => onNav("business-approvals", b.id)} className="w-full text-left bg-card border border-border rounded-xl px-3.5 py-3 hover:border-primary/30 hover:bg-accent transition-colors group">
              <p className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">{b.name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{b.category}</p>
              <div className="flex items-center justify-between mt-2">
                <p className="text-xs text-muted-foreground">{b.referralSource}</p>
                <p className="text-xs text-muted-foreground flex items-center gap-1"><Clock size={11} />{b.daysWaiting > 0 ? `${b.daysWaiting}d` : "New"}</p>
              </div>
            </button>
            ))
          )}
        </div>
        <div className="flex flex-col gap-2 min-h-0">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Support Questions</span>
            <button className="text-xs text-primary font-medium hover:underline">View all</button>
          </div>
          {SUPPORT_QUESTIONS.map((q) => (
            <button key={q.id} className="w-full text-left bg-card border border-border rounded-xl px-3.5 py-3 hover:border-primary/30 hover:bg-accent transition-colors group">
              <div className="flex items-center justify-between gap-2 mb-1">
                <p className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors truncate">{q.user}</p>
                <span className="text-xs text-muted-foreground shrink-0">{q.time}</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">{q.snippet}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Live Tickets ─────────────────────────────────────────────────────────────

function LiveTicketsScreen() {
  const escalated = TICKETS.filter((t) => t.escalated);
  const normal = TICKETS.filter((t) => !t.escalated);
  return (
    <div className="flex gap-4 h-full min-h-0">
      <div className="flex-1 flex flex-col gap-4 min-w-0 overflow-y-auto pr-1">
        {escalated.length > 0 && (
          <div className="rounded-xl border-2 border-amber-400 bg-amber-50 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 bg-amber-100 border-b border-amber-300">
              <div className="flex items-center gap-2">
                <AlertTriangle size={14} className="text-amber-600" />
                <span className="text-xs font-bold uppercase tracking-wide text-amber-700">Escalation Alert — Unclaimed Past Timer</span>
              </div>
              <button className="flex items-center gap-1.5 bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold px-3 py-1.5 rounded-lg transition-colors">
                <Phone size={12} />Call Providers
              </button>
            </div>
            <table className="w-full text-sm">
              <tbody>
                {escalated.map((t) => (
                  <tr key={t.id} className="border-b border-amber-200 last:border-0">
                    <td className="px-4 py-3 font-medium text-foreground">{t.business}</td>
                    <td className="px-3 py-3"><span className="flex items-center gap-1.5 text-muted-foreground text-xs">{categoryIcon(t.category)}{t.category}</span></td>
                    <td className="px-3 py-3">{urgencyPill(t.urgency)}</td>
                    <td className="px-3 py-3">{statusBadge(t.status)}</td>
                    <td className="px-3 py-3 text-xs text-muted-foreground">—</td>
                    <td className="px-3 py-3 text-xs font-semibold text-amber-600 flex items-center gap-1"><Clock size={11} />{t.elapsed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="bg-card border border-border rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/60">
                {["Business", "Category", "Urgency", "Status", "Assigned Tech", "Time in State"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {normal.map((t) => (
                <tr key={t.id} className="border-b border-border last:border-0 hover:bg-muted/40 transition-colors">
                  <td className="px-4 py-3 font-medium text-foreground">{t.business}</td>
                  <td className="px-3 py-3"><span className="flex items-center gap-1.5 text-muted-foreground text-xs">{categoryIcon(t.category)}{t.category}</span></td>
                  <td className="px-3 py-3">{urgencyPill(t.urgency)}</td>
                  <td className="px-3 py-3">{statusBadge(t.status)}</td>
                  <td className="px-3 py-3 text-xs text-foreground">{t.tech ?? <span className="text-muted-foreground">Unassigned</span>}</td>
                  <td className="px-3 py-3 text-xs text-muted-foreground"><span className="flex items-center gap-1"><Clock size={11} />{t.elapsed}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="w-56 shrink-0 flex flex-col gap-2">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Available Now</span>
        </div>
        {AVAILABLE_PROVIDERS.map((p) => (
          <div key={p.id} className="bg-card border border-border rounded-xl px-3 py-2.5">
            <p className="text-sm font-semibold text-foreground">{p.name}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{p.specialty}</p>
            <a href={`tel:${p.phone}`} className="mt-2 flex items-center gap-1.5 text-xs text-teal-700 font-medium hover:text-teal-800 transition-colors">
              <Phone size={11} />{p.phone}
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Provider Approvals ───────────────────────────────────────────────────────

function ProviderApprovalScreen({ providerId }: { providerId?: string }) {
  const { pendingProviders, approveProvider, rejectProvider } = useAdminData();
  const [selected, setSelected] = useState<Provider | null>(null);
  const [declineReason, setDeclineReason] = useState("");
  const [showDecline, setShowDecline] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (pendingProviders.length === 0) {
      setSelected(null);
      return;
    }
    const match = providerId
      ? pendingProviders.find((p) => p.id === providerId)
      : pendingProviders[0];
    setSelected(match ?? pendingProviders[0]);
    setShowDecline(false);
  }, [pendingProviders, providerId]);

  const handleAction = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
    setShowDecline(false);
    setDeclineReason("");
  };

  const handleApprove = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await approveProvider(selected.itid);
      handleAction(`Approved ${selected.name}`);
    } catch (err) {
      handleAction(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  };

  const handleDecline = async () => {
    if (!selected || !declineReason.trim()) return;
    setBusy(true);
    try {
      await rejectProvider(selected.itid, declineReason.trim());
      handleAction(`Declined ${selected.name}`);
    } catch (err) {
      handleAction(err instanceof Error ? err.message : "Decline failed");
    } finally {
      setBusy(false);
    }
  };

  if (pendingProviders.length === 0) {
    return <p className="text-sm text-muted-foreground">No pending provider applications.</p>;
  }

  if (!selected) return null;

  return (
    <div className="flex gap-4 h-full min-h-0">
      <div className="w-52 shrink-0 flex flex-col gap-2 overflow-y-auto">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Applicants ({pendingProviders.length})</span>
        {pendingProviders.map((p) => (
          <button key={p.id} onClick={() => { setSelected(p); setShowDecline(false); }}
            className={`w-full text-left rounded-xl border px-3 py-2.5 transition-colors ${selected.id === p.id ? "border-primary/40 bg-accent" : "border-border bg-card hover:bg-muted/40"}`}>
            <p className="text-sm font-semibold text-foreground">{p.name}</p>
            <div className="flex items-center justify-between mt-1">{tierBadge(p.tier)}<span className="text-xs text-muted-foreground">{p.daysWaiting > 0 ? `${p.daysWaiting}d` : "New"}</span></div>
          </button>
        ))}
      </div>
      <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-1 min-w-0">
        {toast && <Toast message={toast} />}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3"><h2 className="text-lg font-bold text-foreground">{selected.name}</h2>{tierBadge(selected.tier)}</div>
            <p className="text-xs text-muted-foreground mt-1">{selected.region} · {selected.daysWaiting > 0 ? `Applied ${selected.daysWaiting} ${selected.daysWaiting === 1 ? "day" : "days"} ago` : "Recently applied"}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Section title="Experience"><p className="text-sm text-foreground leading-relaxed">{selected.experience}</p></Section>
          <Section title="Skills">
            <div className="flex flex-wrap gap-1.5">{selected.skills.map((s) => (<span key={s} className="px-2 py-0.5 bg-muted text-xs font-medium text-foreground rounded-md">{s}</span>))}</div>
          </Section>
          <Section title="Certifications">
            {selected.certifications.length > 0 ? (
              <ul className="space-y-1">{selected.certifications.map((c) => (<li key={c} className="text-sm text-foreground flex items-center gap-2"><CheckCircle2 size={12} className="text-teal-600 shrink-0" />{c}</li>))}</ul>
            ) : (
              <p className="text-sm text-muted-foreground">No certifications on file.</p>
            )}
          </Section>
          {selected.tier === "Shadow" && selected.vouchedBy && (
            <Section title="Vouched By" highlight>
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-violet-100 flex items-center justify-center shrink-0">
                  <UserCheck size={14} className="text-violet-600" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground">{selected.vouchedBy.name}</p>
                  <p className="text-xs text-muted-foreground">{selected.vouchedBy.relationship}</p>
                </div>
              </div>
            </Section>
          )}
          {selected.tier === "Practitioner" && selected.referralConfirmed !== undefined && (
            <Section title="Referral Status">
              <div className={`flex items-center gap-2 text-sm font-medium ${selected.referralConfirmed ? "text-teal-700" : "text-amber-600"}`}>
                {selected.referralConfirmed ? <CheckCircle2 size={14} /> : <AlertTriangle size={14} />}
                Referral {selected.referralConfirmed ? "Confirmed" : "Pending Confirmation"}
              </div>
            </Section>
          )}
        </div>
        {selected.tier === "Practitioner" && (
          <div className="bg-card border border-border rounded-xl px-4 py-3">
            <p className="text-xs text-muted-foreground">Shadow job history is not available via the admin API yet.</p>
          </div>
        )}
        <div className="flex flex-col gap-3 pt-1">
          {!showDecline ? (
            <div className="flex gap-2">
              <button onClick={() => void handleApprove()} disabled={busy} className="flex-1 bg-primary hover:bg-teal-700 disabled:opacity-60 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors">Approve</button>
              <button onClick={() => handleAction(`Info requested for ${selected.name}`)} className="flex-1 bg-muted hover:bg-border text-foreground text-sm font-semibold py-2.5 rounded-xl transition-colors">Request More Info</button>
              <button onClick={() => setShowDecline(true)} className="flex-1 bg-red-50 hover:bg-red-100 text-red-700 text-sm font-semibold py-2.5 rounded-xl border border-red-200 transition-colors">Decline</button>
            </div>
          ) : (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-red-700">Decline — Reason Required</span>
                <button onClick={() => setShowDecline(false)} className="text-muted-foreground hover:text-foreground transition-colors"><X size={15} /></button>
              </div>
              <textarea value={declineReason} onChange={(e) => setDeclineReason(e.target.value)} placeholder="Explain why this application is being declined..." rows={3}
                className="w-full text-sm bg-white border border-red-200 rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-red-400" />
              <div className="flex gap-2">
                <button onClick={() => void handleDecline()} disabled={!declineReason.trim() || busy}
                  className="flex-1 bg-red-700 disabled:opacity-40 hover:bg-red-800 text-white text-sm font-semibold py-2 rounded-lg transition-colors">Confirm Decline</button>
                <button onClick={() => setShowDecline(false)} className="flex-1 bg-muted text-foreground text-sm font-semibold py-2 rounded-lg hover:bg-border transition-colors">Cancel</button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Business Approvals ───────────────────────────────────────────────────────

// Minimal SVG map placeholder that draws a pin and street grid
function MiniMap({ lat, lng, name }: { lat: number; lng: number; name: string }) {
  // Generate a simple pseudo-map with grid lines and a pin
  const seed = lat * 100 + lng * 100;
  const lines = Array.from({ length: 6 }, (_, i) => ({
    key: `v-${i}`,
    x1: (i * 37 + (seed % 20)) % 220, y1: 0, x2: (i * 37 + (seed % 20) + 15) % 220, y2: 100,
  }));
  const hlines = Array.from({ length: 4 }, (_, i) => ({
    key: `h-${i}`,
    y: i * 28 + 8, x1: 0, x2: 220,
  }));

  return (
    <div className="w-full h-28 bg-[#e8f0eb] rounded-xl overflow-hidden relative border border-border">
      <svg width="100%" height="100%" viewBox="0 0 220 112" preserveAspectRatio="xMidYMid slice">
        {/* Background tint */}
        <rect width="220" height="112" fill="#dce8dc" />
        {/* Horizontal streets */}
        {hlines.map((l) => (
          <line key={l.key} x1={l.x1} y1={l.y} x2={l.x2} y2={l.y} stroke="#b8ccb8" strokeWidth="6" />
        ))}
        {/* Vertical streets */}
        {lines.map((l) => (
          <line key={l.key} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} stroke="#b8ccb8" strokeWidth="6" />
        ))}
        {/* Pin */}
        <circle cx="110" cy="52" r="10" fill="#0f766e" opacity="0.2" />
        <circle cx="110" cy="52" r="5" fill="#0f766e" />
      </svg>
      <div className="absolute bottom-2 left-2.5 bg-white/90 backdrop-blur-sm rounded-md px-2 py-1 flex items-center gap-1 shadow-sm">
        <MapPin size={10} className="text-primary shrink-0" />
        <span className="text-[10px] font-medium text-foreground truncate max-w-[140px]">{name}</span>
      </div>
    </div>
  );
}

function BusinessApprovalsScreen({ businessId }: { businessId?: string }) {
  const { pendingBusinesses, approveBusiness, rejectBusiness } = useAdminData();
  const [selected, setSelected] = useState<BusinessApproval | null>(null);
  const [declineReason, setDeclineReason] = useState("");
  const [showDecline, setShowDecline] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (pendingBusinesses.length === 0) {
      setSelected(null);
      return;
    }
    const match = businessId
      ? pendingBusinesses.find((b) => b.id === businessId)
      : pendingBusinesses[0];
    setSelected(match ?? pendingBusinesses[0]);
    setShowDecline(false);
  }, [pendingBusinesses, businessId]);

  const handleAction = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
    setShowDecline(false);
    setDeclineReason("");
  };

  const handleApprove = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await approveBusiness(selected.businessid);
      handleAction(`Approved ${selected.name}`);
    } catch (err) {
      handleAction(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setBusy(false);
    }
  };

  const handleDecline = async () => {
    if (!selected || !declineReason.trim()) return;
    setBusy(true);
    try {
      await rejectBusiness(selected.businessid, declineReason.trim());
      handleAction(`Declined ${selected.name}`);
    } catch (err) {
      handleAction(err instanceof Error ? err.message : "Decline failed");
    } finally {
      setBusy(false);
    }
  };

  if (pendingBusinesses.length === 0) {
    return <p className="text-sm text-muted-foreground">No pending business applications.</p>;
  }

  if (!selected) return null;

  return (
    <div className="flex gap-4 h-full min-h-0">
      {/* List */}
      <div className="w-52 shrink-0 flex flex-col gap-2 overflow-y-auto">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Applicants ({pendingBusinesses.length})</span>
        {pendingBusinesses.map((b) => (
          <button key={b.id} onClick={() => { setSelected(b); setShowDecline(false); }}
            className={`w-full text-left rounded-xl border px-3 py-2.5 transition-colors ${selected.id === b.id ? "border-primary/40 bg-accent" : "border-border bg-card hover:bg-muted/40"}`}>
            <p className="text-sm font-semibold text-foreground">{b.name}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{b.category}</p>
            <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1"><Clock size={10} />{b.daysWaiting > 0 ? `${b.daysWaiting}d waiting` : "New application"}</p>
          </button>
        ))}
      </div>

      {/* Detail */}
      <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-1 min-w-0">
        {toast && <Toast message={toast} />}

        <div>
          <h2 className="text-lg font-bold text-foreground">{selected.name}</h2>
          <p className="text-xs text-muted-foreground mt-1">{selected.id} · {selected.daysWaiting > 0 ? `Applied ${selected.daysWaiting} ${selected.daysWaiting === 1 ? "day" : "days"} ago` : "Recently applied"}</p>
        </div>

        {/* Map */}
        <MiniMap lat={selected.lat} lng={selected.lng} name={selected.address} />

        {/* Form fields */}
        <div className="grid grid-cols-2 gap-3">
          <Section title="Business Name"><p className="text-sm font-medium text-foreground">{selected.name}</p></Section>
          <Section title="Category"><p className="text-sm text-foreground">{selected.category}</p></Section>
          <Section title="Business Address">
            <p className="text-sm text-foreground flex items-start gap-1.5"><MapPin size={13} className="text-muted-foreground shrink-0 mt-0.5" />{selected.address}</p>
          </Section>
          <Section title="Owner / Primary Contact">
            <p className="text-sm font-medium text-foreground">{selected.owner}</p>
          </Section>
          <Section title="Phone">
            {selected.phone !== "—" ? (
              <a href={`tel:${selected.phone}`} className="text-sm text-teal-700 font-medium flex items-center gap-1.5 hover:underline"><Phone size={13} />{selected.phone}</a>
            ) : (
              <p className="text-sm text-muted-foreground">Not provided</p>
            )}
          </Section>
          <Section title="Contact Email">
            <p className="text-sm text-foreground">{selected.referralSource}</p>
          </Section>
        </div>

        {/* Actions */}
        {!showDecline ? (
          <div className="flex gap-2 pt-1">
            <button onClick={() => void handleApprove()} disabled={busy} className="flex-1 bg-primary hover:bg-teal-700 disabled:opacity-60 text-white text-sm font-semibold py-2.5 rounded-xl transition-colors">Approve</button>
            <button onClick={() => handleAction(`Info requested for ${selected.name}`)} className="flex-1 bg-muted hover:bg-border text-foreground text-sm font-semibold py-2.5 rounded-xl transition-colors">Request More Info</button>
            <button onClick={() => setShowDecline(true)} className="flex-1 bg-red-50 hover:bg-red-100 text-red-700 text-sm font-semibold py-2.5 rounded-xl border border-red-200 transition-colors">Decline</button>
          </div>
        ) : (
          <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-red-700">Decline — Reason Required</span>
              <button onClick={() => setShowDecline(false)} className="text-muted-foreground hover:text-foreground"><X size={15} /></button>
            </div>
            <textarea value={declineReason} onChange={(e) => setDeclineReason(e.target.value)} placeholder="Explain why this application is being declined..." rows={3}
              className="w-full text-sm bg-white border border-red-200 rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-red-400" />
            <div className="flex gap-2">
              <button onClick={() => void handleDecline()} disabled={!declineReason.trim() || busy}
                className="flex-1 bg-red-700 disabled:opacity-40 hover:bg-red-800 text-white text-sm font-semibold py-2 rounded-lg transition-colors">Confirm Decline</button>
              <button onClick={() => setShowDecline(false)} className="flex-1 bg-muted text-foreground text-sm font-semibold py-2 rounded-lg hover:bg-border transition-colors">Cancel</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── User Management ──────────────────────────────────────────────────────────

function UsersScreen() {
  const { users, suspendUser, reactivateUser, updateUserLocal } = useAdminData();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<UserRow | null>(null);
  const [suspendOpen, setSuspendOpen] = useState(false);
  const [suspendReason, setSuspendReason] = useState("");
  const [noteText, setNoteText] = useState("");
  const [showNoteBox, setShowNoteBox] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const filtered = users.filter((u) =>
    u.name.toLowerCase().includes(query.toLowerCase()) ||
    u.role.toLowerCase().includes(query.toLowerCase()) ||
    u.region.toLowerCase().includes(query.toLowerCase())
  );

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 2500); };

  const handleSuspend = async () => {
    if (!selected || !suspendReason.trim()) return;
    setBusy(true);
    try {
      await suspendUser(selected.id);
      setSelected((s) => (s ? { ...s, status: "Suspended" } : s));
      setSuspendOpen(false);
      setSuspendReason("");
      showToast(`${selected.name} suspended`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Suspend failed");
    } finally {
      setBusy(false);
    }
  };

  const handleReactivate = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await reactivateUser(selected.id);
      setSelected((s) => (s ? { ...s, status: "Active" } : s));
      showToast(`${selected.name} reactivated`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Reactivate failed");
    } finally {
      setBusy(false);
    }
  };

  const handleAddNote = () => {
    if (!selected || !noteText.trim()) return;
    const newDispute: DisputeEntry = {
      id: `D-${Date.now()}`, date: new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
      type: "Complaint", note: noteText, resolvedBy: "Admin",
    };
    const nextDisputes = [...selected.disputes, newDispute];
    updateUserLocal(selected.id, { disputes: nextDisputes });
    setSelected((s) => (s ? { ...s, disputes: nextDisputes } : s));
    setNoteText("");
    setShowNoteBox(false);
    showToast("Dispute note added (local only)");
  };

  const disputeTypeColor = (type: DisputeEntry["type"]) => {
    if (type === "Business refused payment") return "bg-red-100 text-red-700";
    if (type === "Tech no-show") return "bg-amber-100 text-amber-700";
    if (type === "Complaint") return "bg-orange-100 text-orange-700";
    return "bg-gray-100 text-gray-600";
  };

  return (
    <div className="flex gap-4 h-full min-h-0">
      {/* Table */}
      <div className="flex-1 flex flex-col gap-3 min-w-0 overflow-hidden">
        {toast && <Toast message={toast} />}
        {/* Search */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, role, or region..."
            className="w-full pl-9 pr-4 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary" />
        </div>

        {/* Table */}
        <div className="flex-1 overflow-y-auto bg-card border border-border rounded-xl">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="border-b border-border bg-muted/80 backdrop-blur-sm">
                {["Name", "Role", "Status", "Rating", "Region", "Joined"].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((u) => (
                <tr key={u.id} onClick={() => { setSelected(u); setSuspendOpen(false); setShowNoteBox(false); }}
                  className={`border-b border-border last:border-0 cursor-pointer transition-colors ${selected?.id === u.id ? "bg-accent" : "hover:bg-muted/40"}`}>
                  <td className="px-4 py-3 font-medium text-foreground">{u.name}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${u.role === "Provider" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"}`}>{u.role}</span>
                  </td>
                  <td className="px-4 py-3">{userStatusPill(u.status)}</td>
                  <td className="px-4 py-3 text-xs text-foreground">{u.rating !== null ? <span className="flex items-center gap-1"><Star size={11} className="text-amber-400 fill-amber-400" />{u.rating}</span> : <span className="text-muted-foreground">—</span>}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{u.region}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{u.joinDate}</td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">No users match your search.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Side panel */}
      {selected && (
        <div className="w-72 shrink-0 flex flex-col gap-4 overflow-y-auto border-l border-border pl-4">
          {/* Profile */}
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="text-sm font-bold text-foreground">{selected.name}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{selected.email}</p>
              </div>
              {userStatusPill(selected.status)}
            </div>
            <div className="space-y-1.5 text-xs text-muted-foreground">
              <div className="flex items-center gap-2"><Phone size={11} />{selected.phone}</div>
              <div className="flex items-center gap-2"><MapPin size={11} />{selected.region}</div>
              <div className="flex items-center gap-2"><Clock size={11} />Joined {selected.joinDate}</div>
              {selected.rating !== null && (
                <div className="flex items-center gap-2"><Star size={11} className="text-amber-400 fill-amber-400" />{selected.rating} avg rating</div>
              )}
            </div>
          </div>

          {/* Dispute log */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Dispute Log ({selected.disputes.length})</span>
              <button onClick={() => setShowNoteBox((v) => !v)} className="flex items-center gap-1 text-xs text-primary font-medium hover:underline">
                <Plus size={11} />Add Note
              </button>
            </div>

            {showNoteBox && (
              <div className="mb-3 flex flex-col gap-2">
                <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} placeholder="Describe the dispute or note..." rows={3}
                  className="w-full text-xs bg-card border border-border rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-primary" />
                <div className="flex gap-2">
                  <button onClick={handleAddNote} disabled={!noteText.trim()} className="flex-1 bg-primary disabled:opacity-40 hover:bg-teal-700 text-white text-xs font-semibold py-1.5 rounded-lg transition-colors">Save</button>
                  <button onClick={() => { setShowNoteBox(false); setNoteText(""); }} className="flex-1 bg-muted text-foreground text-xs font-semibold py-1.5 rounded-lg hover:bg-border transition-colors">Cancel</button>
                </div>
              </div>
            )}

            {selected.disputes.length === 0 ? (
              <p className="text-xs text-muted-foreground italic">No disputes on record.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {selected.disputes.map((d) => (
                  <div key={d.id} className="bg-card border border-border rounded-xl p-3">
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${disputeTypeColor(d.type)}`}>{d.type}</span>
                      <span className="text-[10px] text-muted-foreground shrink-0">{d.date}</span>
                    </div>
                    <p className="text-xs text-foreground leading-relaxed">{d.note}</p>
                    <p className="text-[10px] text-muted-foreground mt-1.5">Resolved by {d.resolvedBy}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2 mt-auto pt-2 border-t border-border">
            {selected.status === "Active" ? (
              <button onClick={() => setSuspendOpen(true)} className="w-full bg-red-50 hover:bg-red-100 text-red-700 text-sm font-semibold py-2.5 rounded-xl border border-red-200 transition-colors">
                Suspend Account
              </button>
            ) : selected.status === "Suspended" ? (
              <button onClick={() => void handleReactivate()} disabled={busy} className="w-full bg-teal-50 hover:bg-teal-100 text-teal-700 text-sm font-semibold py-2.5 rounded-xl border border-teal-200 transition-colors disabled:opacity-60">
                Reactivate Account
              </button>
            ) : (
              <p className="text-xs text-muted-foreground text-center">Pending accounts must be approved from the Approvals screens.</p>
            )}
          </div>

          {/* Suspend confirm */}
          {suspendOpen && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-red-700">Confirm Suspension</span>
                <button onClick={() => { setSuspendOpen(false); setSuspendReason(""); }} className="text-muted-foreground hover:text-foreground"><X size={14} /></button>
              </div>
              <p className="text-xs text-muted-foreground">This will immediately revoke access for <span className="font-semibold text-foreground">{selected.name}</span>. A reason is required.</p>
              <textarea value={suspendReason} onChange={(e) => setSuspendReason(e.target.value)} placeholder="Reason for suspension..." rows={2}
                className="w-full text-xs bg-white border border-red-200 rounded-lg px-3 py-2 text-foreground placeholder:text-muted-foreground resize-none focus:outline-none focus:ring-1 focus:ring-red-400" />
              <div className="flex gap-2">
                <button onClick={() => void handleSuspend()} disabled={!suspendReason.trim() || busy} className="flex-1 bg-red-700 disabled:opacity-40 hover:bg-red-800 text-white text-xs font-semibold py-2 rounded-lg transition-colors">Suspend</button>
                <button onClick={() => { setSuspendOpen(false); setSuspendReason(""); }} className="flex-1 bg-muted text-foreground text-xs font-semibold py-2 rounded-lg hover:bg-border transition-colors">Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Analytics ────────────────────────────────────────────────────────────────

function AnalyticsScreen() {
  return (
    <div className="flex flex-col gap-5 h-full overflow-y-auto pr-1">
      {/* Stat cards */}
      <div className="flex gap-3">
        <StatTile label="Total Tickets (all time)" value="1,284" />
        <StatTile label="Completion Rate" value="96.4%" accent="teal" sub="of dispatched jobs completed" />
        <StatTile label="Median Response Time" value="8 min" sub="ticket open → tech claimed" />
        {/* Prominent money tile */}
        <div className="flex-1 min-w-0 bg-primary rounded-xl px-4 py-3 relative overflow-hidden">
          <div className="absolute inset-0 opacity-10">
            <div className="absolute -right-4 -top-4 w-24 h-24 rounded-full border-[12px] border-white" />
            <div className="absolute -right-1 bottom-2 w-12 h-12 rounded-full border-[6px] border-white" />
          </div>
          <p className="text-xs text-white/70 font-medium uppercase tracking-wide mb-1">Paid to Local Techs</p>
          <p className="text-2xl font-bold text-white">$20,520</p>
          <p className="text-xs text-white/60 mt-0.5">this calendar year</p>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Line chart */}
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">Tickets per Week</p>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={TICKET_TREND} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <XAxis dataKey="week" tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid rgba(0,0,0,0.08)", boxShadow: "0 2px 8px rgba(0,0,0,0.08)" }} />
              <Line type="monotone" dataKey="tickets" stroke="#0f766e" strokeWidth={2} dot={{ r: 3, fill: "#0f766e" }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Bar chart */}
        <div className="bg-card border border-border rounded-xl p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">Tickets by Category</p>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={CATEGORY_DATA} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
              <XAxis dataKey="category" tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid rgba(0,0,0,0.08)", boxShadow: "0 2px 8px rgba(0,0,0,0.08)" }} />
              <Bar dataKey="count" fill="#0f766e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top providers table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-2.5 border-b border-border bg-muted/50">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Top Providers by Jobs Completed</span>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">#</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Provider</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Jobs</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Avg Rating</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">Total Earned</th>
            </tr>
          </thead>
          <tbody>
            {TOP_PROVIDERS.map((p, i) => (
              <tr key={p.name} className="border-b border-border last:border-0 hover:bg-muted/40 transition-colors">
                <td className="px-4 py-3 text-xs font-bold text-muted-foreground">{i + 1}</td>
                <td className="px-4 py-3 font-medium text-foreground">{p.name}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-primary rounded-full" style={{ width: `${(p.jobs / 50) * 100}%` }} />
                    </div>
                    <span className="text-xs font-semibold text-foreground">{p.jobs}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-foreground">
                  <span className="flex items-center gap-1"><Star size={11} className="text-amber-400 fill-amber-400" />{p.rating}</span>
                </td>
                <td className="px-4 py-3 text-xs font-semibold text-teal-700">{p.earned}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

const NAV_ITEMS: { id: Screen; label: string; icon: React.ReactNode; badgeKey?: "tickets" | "providers" | "businesses" }[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard size={16} /> },
  { id: "live-tickets", label: "Live Tickets", icon: <Ticket size={16} />, badgeKey: "tickets" },
  { id: "provider-approvals", label: "Provider Approvals", icon: <UserCheck size={16} />, badgeKey: "providers" },
  { id: "business-approvals", label: "Business Approvals", icon: <Building2 size={16} />, badgeKey: "businesses" },
  { id: "users", label: "Users", icon: <Users size={16} /> },
  { id: "analytics", label: "Analytics", icon: <BarChart3 size={16} /> },
];

function Sidebar({
  active,
  onNav,
  badges,
  adminEmail,
  onLogout,
}: {
  active: Screen;
  onNav: (s: Screen) => void;
  badges: { tickets: number; providers: number; businesses: number };
  adminEmail?: string;
  onLogout: () => void;
}) {
  return (
    <aside className="w-52 shrink-0 flex flex-col bg-[#f9fafb] border-r border-border h-full">
      <div className="px-4 py-4 border-b border-border flex items-center gap-2.5">
        <div className="w-7 h-7 rounded-lg bg-primary flex items-center justify-center shrink-0">
          <Phone size={13} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-bold text-foreground leading-none">IT Hotline</p>
          <p className="text-[10px] text-muted-foreground mt-0.5">Admin Console</p>
        </div>
      </div>
      <nav className="flex-1 px-2 py-3 flex flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const isActive = active === item.id;
          const badge = item.badgeKey ? badges[item.badgeKey] : undefined;
          return (
            <button key={item.id} onClick={() => onNav(item.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive ? "bg-accent text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>
              <span className={isActive ? "text-primary" : "text-muted-foreground"}>{item.icon}</span>
              <span className="flex-1 text-left">{item.label}</span>
              {badge !== undefined && badge > 0 && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full ${isActive ? "bg-primary text-white" : "bg-muted-foreground/20 text-muted-foreground"}`}>{badge}</span>
              )}
            </button>
          );
        })}
      </nav>
      <div className="px-4 py-3 border-t border-border space-y-2">
        <p className="text-xs text-muted-foreground truncate">{adminEmail ?? "Admin"}</p>
        <button onClick={onLogout} className="text-xs text-red-600 hover:text-red-700 font-medium">Sign out</button>
      </div>
    </aside>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────

function AdminConsole() {
  const { admin, logout } = useAuth();
  const { pendingProviders, pendingBusinesses, loading, error } = useAdminData();
  const [screen, setScreen] = useState<Screen>("overview");
  const [detailId, setDetailId] = useState<string | undefined>();

  const handleNav = (s: Screen, id?: string) => { setScreen(s); setDetailId(id); };

  const screenTitle: Record<Screen, string> = {
    overview: "Overview", "live-tickets": "Live Ticket Monitor", "provider-approvals": "Provider Approvals",
    "business-approvals": "Business Approvals", users: "User Management", analytics: "Analytics",
  };

  const badges = {
    tickets: 7,
    providers: pendingProviders.length,
    businesses: pendingBusinesses.length,
  };

  const adminInitial = admin?.firstName?.charAt(0) ?? "A";

  return (
    <div className="flex h-screen bg-background font-[Inter,sans-serif] overflow-hidden">
      <Sidebar
        active={screen}
        onNav={(s) => handleNav(s)}
        badges={badges}
        adminEmail={admin?.email}
        onLogout={logout}
      />
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center justify-between px-6 py-3.5 border-b border-border bg-background shrink-0">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">{screenTitle[screen]}</span>
            {detailId && (<><ChevronRight size={13} /><span>{detailId}</span></>)}
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted px-2.5 py-1 rounded-full">
              <div className={`w-1.5 h-1.5 rounded-full ${loading ? "bg-amber-500" : "bg-teal-500"}`} />
              {loading ? "Syncing" : "Live"}
            </div>
            <div className="flex items-center gap-2 bg-muted px-2.5 py-1.5 rounded-full">
              <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center">
                <span className="text-[9px] font-bold text-primary">{adminInitial}</span>
              </div>
              <span className="text-xs font-medium text-foreground">{admin?.firstName ?? "Admin"}</span>
            </div>
          </div>
        </header>
        {error && (
          <div className="mx-6 mt-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
            {error}
          </div>
        )}
        <div className="flex-1 overflow-hidden px-6 py-5">
          {screen === "overview" && (
            <OverviewScreen
              onNav={handleNav}
              providers={pendingProviders}
              businesses={pendingBusinesses}
            />
          )}
          {screen === "live-tickets" && <LiveTicketsScreen />}
          {screen === "provider-approvals" && <ProviderApprovalScreen providerId={detailId} />}
          {screen === "business-approvals" && <BusinessApprovalsScreen businessId={detailId} />}
          {screen === "users" && <UsersScreen />}
          {screen === "analytics" && <AnalyticsScreen />}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  const { token } = useAuth();
  if (!token) return <LoginScreen />;
  return (
    <AdminDataProvider>
      <AdminConsole />
    </AdminDataProvider>
  );
}
