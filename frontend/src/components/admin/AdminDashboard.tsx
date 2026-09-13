"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Cloud,
  FileText,
  LayoutDashboard,
  MessageSquare,
  RefreshCw,
  Search,
  TriangleAlert,
  UserRound,
  Users,
  Zap,
} from "lucide-react";

import { adminApi, type AdminOverview, type AdminPerson } from "@/lib/api/admin";
import {
  AuthRequiredError,
  ForbiddenError,
  toUserMessage,
} from "@/lib/api/client";
import { getCurrentSession, isSupabaseConfigured } from "@/lib/supabase/client";
import { useSupabaseSession } from "@/lib/supabase/useSupabaseSession";
import { applyAuthSession } from "@/lib/workspace/syncWorkspace";
import { Logo } from "@/components/ui/Logo";
import { Toaster } from "@/components/ui/Toaster";
import { UserMenu } from "@/components/auth/UserMenu";
import { useAuthStore } from "@/store/useAuthStore";
import { cn } from "@/lib/cn";
import {
  formatMoney,
  formatNumber,
  formatWhen,
  kindLabel,
  statusLabel,
} from "./format";

type Gate = "loading" | "denied" | "ready" | "error";
type PeopleFilter = "all" | "user" | "guest";

export function AdminDashboard() {
  const router = useRouter();
  const initSession = useAuthStore((state) => state.initSession);
  const user = useAuthStore((state) => state.user);
  const isAdmin = useAuthStore((state) => state.usage?.admin === true);

  const [gate, setGate] = useState<Gate>("loading");
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [peopleFilter, setPeopleFilter] = useState<PeopleFilter>("all");
  const [sessionReady, setSessionReady] = useState(!isSupabaseConfigured());

  useSupabaseSession();

  useEffect(() => {
    initSession();
    if (!isSupabaseConfigured()) {
      setSessionReady(true);
      return;
    }
    let cancelled = false;
    void getCurrentSession().then(async (session) => {
      if (session) await applyAuthSession(session);
      if (!cancelled) setSessionReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, [initSession]);

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setGate((current) => (current === "ready" ? current : "loading"));
    setRefreshing(true);
    setError(null);
    try {
      const overview = await adminApi.overview();
      setData(overview);
      setGate("ready");
    } catch (err) {
      if (err instanceof AuthRequiredError || err instanceof ForbiddenError) {
        setData(null);
        setGate("denied");
        return;
      }
      setError(toUserMessage(err, "Could not load operations."));
      setGate((current) => (current === "ready" ? "ready" : "error"));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (!sessionReady) return;
    void load();
  }, [load, sessionReady, user?.id]);

  useEffect(() => {
    if (gate === "denied") {
      router.replace("/");
      return;
    }
    if (gate === "error" && !isAdmin) {
      router.replace("/");
    }
  }, [gate, isAdmin, router]);

  if (gate === "denied" || (gate === "error" && !isAdmin) || gate === "loading") {
    return <div className="min-h-[100dvh] bg-paper" aria-busy={gate === "loading"} />;
  }

  return (
    <div className="flex min-h-[100dvh] flex-col bg-paper text-ink">
      <header className="border-b border-line bg-paper">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link href="/admin" className="flex items-center gap-2.5 rounded-md">
            <Logo />
            <span className="hidden rounded-full bg-olive-soft px-2 py-0.5 text-label font-semibold uppercase tracking-[0.08em] text-olive sm:inline">
              Operations
            </span>
          </Link>
          <nav className="flex items-center gap-1.5 sm:gap-2">
            <Link
              href="/about"
              className="rounded-lg px-2.5 py-1.5 text-ui font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink"
            >
              About
            </Link>
            <Link
              href="/privacy"
              className="rounded-lg px-2.5 py-1.5 text-ui font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink"
            >
              Privacy
            </Link>
            <Link
              href="/"
              className="rounded-lg px-2.5 py-1.5 text-ui font-medium text-ink-muted transition-colors hover:bg-surface hover:text-ink"
            >
              Workspace
            </Link>
            <UserMenu />
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
        {gate === "error" && (
          <GateCard
            title="Couldn’t load operations"
            body={error || "The API did not return the operator snapshot."}
            actionLabel="Try again"
            onAction={() => void load()}
          />
        )}
        {gate === "ready" && data && (
          <DashboardBody
            data={data}
            query={query}
            onQuery={setQuery}
            peopleFilter={peopleFilter}
            onPeopleFilter={setPeopleFilter}
            refreshing={refreshing}
            onRefresh={() => void load(true)}
          />
        )}
      </main>
      <Toaster />
    </div>
  );
}

function DashboardBody({
  data,
  query,
  onQuery,
  peopleFilter,
  onPeopleFilter,
  refreshing,
  onRefresh,
}: {
  data: AdminOverview;
  query: string;
  onQuery: (value: string) => void;
  peopleFilter: PeopleFilter;
  onPeopleFilter: (value: PeopleFilter) => void;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  const needle = query.trim().toLowerCase();
  const people = useMemo(() => {
    return data.people.filter((person) => {
      if (peopleFilter !== "all" && person.actor_type !== peopleFilter) return false;
      if (!needle) return true;
      return [person.label, person.email, person.migrated_to]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle));
    });
  }, [data.people, needle, peopleFilter]);

  const uploads = useMemo(() => {
    if (!needle) return data.uploads;
    return data.uploads.filter((item) =>
      [item.filename, item.owner_label, item.status, item.index_error]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle))
    );
  }, [data.uploads, needle]);

  const events = useMemo(() => {
    if (!needle) return data.events;
    return data.events.filter((item) =>
      [item.actor_label, item.kind, item.provider, item.category, item.message]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle))
    );
  }, [data.events, needle]);

  return (
    <div className="animate-rise-in">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-label font-semibold uppercase tracking-[0.08em] text-olive">
            Operator
          </p>
          <h1 className="mt-1 text-h1 font-semibold tracking-[-0.02em] text-ink sm:text-display">
            Operations
          </h1>
          <p className="mt-1.5 max-w-xl text-body text-ink-muted">
            Everyone using DocuSage — guests and signed-in accounts — plus uploads,
            errors, and remaining provider budget.
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-2 self-start rounded-lg border border-line bg-surface px-3 py-2 text-ui font-medium text-ink shadow-card transition-colors hover:border-line-strong hover:bg-surface-muted disabled:opacity-60"
        >
          <RefreshCw className={cn("h-4 w-4 text-olive", refreshing && "animate-spin")} />
          {refreshing ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <p className="mt-3 text-meta text-ink-subtle">
        Updated {formatWhen(data.generated_at)}
      </p>

      <section className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard
          label="Signed in"
          value={formatNumber(data.totals.signed_in_users)}
          icon={Users}
        />
        <StatCard
          label="Guests"
          value={formatNumber(data.totals.guest_sessions)}
          icon={UserRound}
        />
        <StatCard
          label="Uploads"
          value={formatNumber(data.totals.pdfs)}
          hint={
            data.totals.failed_pdfs
              ? `${data.totals.failed_pdfs} failed`
              : "All files"
          }
          icon={FileText}
        />
        <StatCard
          label="Questions"
          value={formatNumber(data.totals.questions_this_month)}
          hint={`${formatNumber(data.totals.questions_today)} today`}
          icon={MessageSquare}
        />
        <StatCard
          label="Issues · 7d"
          value={formatNumber(data.totals.errors_recent)}
          tone={data.totals.errors_recent > 0 ? "warn" : "ok"}
          icon={TriangleAlert}
        />
      </section>

      <section className="mt-4 grid gap-3 lg:grid-cols-2">
        <GroqCard groq={data.groq} />
        <AzureCard azure={data.azure} />
      </section>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-icon" />
          <span className="sr-only">Search people, uploads, and errors</span>
          <input
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="Search people, files, or errors"
            className="w-full rounded-xl border border-line bg-surface py-2.5 pl-9 pr-3 text-ui text-ink shadow-card outline-none placeholder:text-ink-subtle"
          />
        </label>
        <div className="flex rounded-xl border border-line bg-surface p-1 shadow-card">
          {(
            [
              ["all", "Everyone"],
              ["user", "Signed in"],
              ["guest", "Guests"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => onPeopleFilter(id)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-meta font-medium transition-colors",
                peopleFilter === id
                  ? "bg-olive text-white"
                  : "text-ink-muted hover:text-ink"
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(20rem,0.8fr)]">
        <Panel
          title="People"
          count={people.length}
          empty="No one matches this view yet."
        >
          <PeopleTable people={people} />
        </Panel>
        <Panel
          title="Recent issues"
          count={events.length}
          empty="No recorded errors yet. New failures will appear here."
        >
          <EventList events={events} />
        </Panel>
      </section>

      <section className="mt-4">
        <Panel
          title="Uploads"
          count={uploads.length}
          empty="No documents have been uploaded yet."
        >
          <UploadsTable uploads={uploads} />
        </Panel>
      </section>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "default" | "warn" | "ok";
}) {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <p className="text-label font-semibold uppercase tracking-[0.08em] text-ink-subtle">
          {label}
        </p>
        <Icon
          className={cn(
            "h-4 w-4",
            tone === "warn" ? "text-warn" : "text-ink-icon"
          )}
        />
      </div>
      <p className="mt-2 text-h1 font-semibold tracking-[-0.03em] text-ink">{value}</p>
      {hint && <p className="mt-1 text-meta text-ink-muted">{hint}</p>}
    </div>
  );
}

function GroqCard({ groq }: { groq: AdminOverview["groq"] }) {
  const requestPct = remainingPercent(groq.remaining_requests, groq.limit_requests);
  const tokenPct = remainingPercent(groq.remaining_tokens, groq.limit_tokens);
  const low = (requestPct != null && requestPct <= 20) || (tokenPct != null && tokenPct <= 20);

  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-label font-semibold uppercase tracking-[0.08em] text-ink-subtle">
            Groq
          </p>
          <h2 className="mt-1 text-title font-semibold text-ink">Rate limit left</h2>
        </div>
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-olive-soft text-olive">
          <Zap className="h-4 w-4" />
        </span>
      </div>

      {!groq.configured ? (
        <p className="mt-4 text-body text-ink-muted">
          No Groq calls recorded yet. Remaining requests will appear after the
          first answer is generated.
        </p>
      ) : (
        <div className="mt-4 space-y-3">
          <Meter
            label="Requests"
            remaining={groq.remaining_requests}
            limit={groq.limit_requests}
            reset={groq.reset_requests}
          />
          <Meter
            label="Tokens"
            remaining={groq.remaining_tokens}
            limit={groq.limit_tokens}
            reset={groq.reset_tokens}
          />
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-meta text-ink-muted">
            <span>{formatNumber(groq.requests_today)} calls today</span>
            <span>{formatNumber(groq.tokens_used_today)} tokens today</span>
            <span>Updated {formatWhen(groq.updated_at)}</span>
          </div>
          {groq.last_error && (
            <p className="rounded-lg border border-warn-line bg-warn-soft px-3 py-2 text-meta text-warn">
              Last error: {groq.last_error}
            </p>
          )}
          {low && !groq.last_error && (
            <p className="text-meta text-warn">Headroom is low — fallbacks may start soon.</p>
          )}
        </div>
      )}
    </div>
  );
}

function AzureCard({ azure }: { azure: AdminOverview["azure"] }) {
  const remainingPct =
    azure.remaining_usd != null && azure.credit_start_usd > 0
      ? Math.max(0, Math.min(100, (azure.remaining_usd / azure.credit_start_usd) * 100))
      : null;
  const low = remainingPct != null && remainingPct <= 25;

  return (
    <div className="rounded-2xl border border-line bg-surface p-5 shadow-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-label font-semibold uppercase tracking-[0.08em] text-ink-subtle">
            Azure
          </p>
          <h2 className="mt-1 text-title font-semibold text-ink">Hosting credit</h2>
        </div>
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-olive-soft text-olive">
          <Cloud className="h-4 w-4" />
        </span>
      </div>

      <div className="mt-4 flex items-end justify-between gap-3">
        <div>
          <p className="text-display font-semibold tracking-[-0.03em] text-ink">
            {formatMoney(azure.remaining_usd)}
          </p>
          <p className="mt-1 text-meta text-ink-muted">
            of {formatMoney(azure.credit_start_usd)}
            {azure.expires ? ` · ends ${azure.expires}` : ""}
          </p>
        </div>
        <p className="text-meta text-ink-subtle">
          {azure.source === "manual"
            ? "From spend you set"
            : azure.source === "estimate"
              ? "Estimated from VM hours"
              : "Add spend or start date in .env"}
        </p>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-sunken">
        <div
          className={cn("h-full rounded-full", low ? "bg-warn" : "bg-olive")}
          style={{ width: `${remainingPct ?? 0}%` }}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-meta text-ink-muted">
        <span>Spent {formatMoney(azure.spend_usd)}</span>
        <span>~{formatMoney(azure.estimated_monthly_usd)} / month if the VM stays on</span>
        <span>{formatMoney(azure.hourly_usd)} / hour</span>
      </div>
      {azure.source === "unknown" && (
        <p className="mt-3 text-meta text-ink-muted">
          Remaining is unknown until you set <code>AZURE_SPEND_USD</code> or{" "}
          <code>AZURE_CREDIT_STARTED_AT</code>.
        </p>
      )}
    </div>
  );
}

function Meter({
  label,
  remaining,
  limit,
  reset,
}: {
  label: string;
  remaining: number | null;
  limit: number | null;
  reset: string | null;
}) {
  const pct = remainingPercent(remaining, limit);
  return (
    <div>
      <div className="flex items-center justify-between text-meta">
        <span className="font-medium text-ink">{label}</span>
        <span className="text-ink-muted">
          {remaining == null || limit == null
            ? "Waiting for headers"
            : `${formatNumber(remaining)} / ${formatNumber(limit)} left`}
          {reset ? ` · reset ${reset}` : ""}
        </span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-sunken">
        <div
          className={cn(
            "h-full rounded-full",
            pct != null && pct <= 20 ? "bg-warn" : "bg-sage"
          )}
          style={{ width: `${pct ?? 0}%` }}
        />
      </div>
    </div>
  );
}

function remainingPercent(remaining: number | null, limit: number | null): number | null {
  if (remaining == null || limit == null || limit <= 0) return null;
  return Math.max(0, Math.min(100, (remaining / limit) * 100));
}

function Panel({
  title,
  count,
  empty,
  children,
}: {
  title: string;
  count: number;
  empty: string;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
      <header className="flex items-center justify-between gap-3 border-b border-line px-4 py-3 sm:px-5">
        <h2 className="text-title font-semibold text-ink">{title}</h2>
        <span className="text-meta text-ink-subtle">{count}</span>
      </header>
      {count === 0 ? (
        <p className="px-4 py-10 text-center text-body text-ink-muted sm:px-5">{empty}</p>
      ) : (
        children
      )}
    </section>
  );
}

function PeopleTable({ people }: { people: AdminPerson[] }) {
  return (
    <div className="scroll-area overflow-x-auto">
      <table className="min-w-full text-left text-ui">
        <thead className="text-label font-semibold uppercase tracking-[0.06em] text-ink-subtle">
          <tr className="border-b border-line">
            <th className="px-4 py-2.5 font-semibold sm:px-5">Who</th>
            <th className="px-3 py-2.5 font-semibold">Type</th>
            <th className="px-3 py-2.5 font-semibold">Last seen</th>
            <th className="px-3 py-2.5 font-semibold">PDFs</th>
            <th className="px-3 py-2.5 font-semibold">Questions</th>
            <th className="px-4 py-2.5 font-semibold sm:px-5">Note</th>
          </tr>
        </thead>
        <tbody>
          {people.map((person) => (
            <tr key={`${person.actor_type}:${person.actor_id}`} className="border-b border-line last:border-0">
              <td className="px-4 py-3 sm:px-5">
                <p className="font-medium text-ink">{person.label}</p>
                <p className="text-meta text-ink-subtle">
                  Joined {formatWhen(person.created_at)}
                </p>
              </td>
              <td className="px-3 py-3">
                <TypeBadge type={person.actor_type} />
              </td>
              <td className="px-3 py-3 text-ink-muted">{formatWhen(person.last_seen_at)}</td>
              <td className="px-3 py-3 text-ink">
                {formatNumber(person.pdfs)}
                {person.failed_pdfs > 0 && (
                  <span className="ml-1 text-meta text-danger">{person.failed_pdfs} failed</span>
                )}
              </td>
              <td className="px-3 py-3 text-ink">{formatNumber(person.questions)}</td>
              <td className="px-4 py-3 text-ink-muted sm:px-5">
                {person.migrated_to ? `Moved to ${person.migrated_to}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function UploadsTable({ uploads }: { uploads: AdminOverview["uploads"] }) {
  return (
    <div className="scroll-area overflow-x-auto">
      <table className="min-w-full text-left text-ui">
        <thead className="text-label font-semibold uppercase tracking-[0.06em] text-ink-subtle">
          <tr className="border-b border-line">
            <th className="px-4 py-2.5 font-semibold sm:px-5">File</th>
            <th className="px-3 py-2.5 font-semibold">Owner</th>
            <th className="px-3 py-2.5 font-semibold">Status</th>
            <th className="px-3 py-2.5 font-semibold">Pages</th>
            <th className="px-4 py-2.5 font-semibold sm:px-5">When</th>
          </tr>
        </thead>
        <tbody>
          {uploads.map((item) => (
            <tr key={item.document_id} className="border-b border-line last:border-0">
              <td className="px-4 py-3 sm:px-5">
                <p className="max-w-[16rem] truncate font-medium text-ink" title={item.filename}>
                  {item.filename}
                </p>
                {item.index_error && (
                  <p className="mt-0.5 max-w-sm text-meta text-danger">{item.index_error}</p>
                )}
              </td>
              <td className="px-3 py-3 text-ink-muted">{item.owner_label}</td>
              <td className="px-3 py-3">
                <StatusBadge status={item.status} />
              </td>
              <td className="px-3 py-3 text-ink-muted">{item.total_pages || "—"}</td>
              <td className="px-4 py-3 text-ink-muted sm:px-5">{formatWhen(item.uploaded_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EventList({ events }: { events: AdminOverview["events"] }) {
  return (
    <ul className="divide-y divide-line">
      {events.slice(0, 20).map((event) => (
        <li key={event.event_id} className="px-4 py-3 sm:px-5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-ui font-medium text-ink">
                {kindLabel(event.kind)}
                {event.provider ? ` · ${event.provider}` : ""}
                {event.category ? ` · ${event.category.replace(/_/g, " ")}` : ""}
              </p>
              <p className="mt-0.5 text-meta text-ink-muted">
                {event.actor_label}
                {event.route ? ` · ${event.route}` : ""}
              </p>
              {event.message && (
                <p className="mt-1 text-meta leading-relaxed text-ink-subtle break-anywhere">
                  {event.message}
                </p>
              )}
            </div>
            <time className="shrink-0 text-meta text-ink-subtle">
              {formatWhen(event.created_at)}
            </time>
          </div>
        </li>
      ))}
    </ul>
  );
}

function TypeBadge({ type }: { type: string }) {
  const guest = type === "guest";
  return (
    <span
      className={cn(
        "inline-flex rounded-full px-2 py-0.5 text-label font-semibold uppercase tracking-[0.06em]",
        guest ? "bg-surface-sunken text-ink-muted" : "bg-olive-soft text-olive"
      )}
    >
      {guest ? "Guest" : "Signed in"}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "failed"
      ? "bg-danger-soft text-danger"
      : status === "ready"
        ? "bg-olive-soft text-olive"
        : "bg-warn-soft text-warn";
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-label font-semibold uppercase tracking-[0.06em]", tone)}>
      {statusLabel(status)}
    </span>
  );
}

function GateCard({
  title,
  body,
  actionLabel,
  onAction,
  actionDisabled,
  href,
  error,
}: {
  title: string;
  body: string;
  actionLabel: string;
  onAction?: () => void;
  actionDisabled?: boolean;
  href?: string;
  error?: string | null;
}) {
  return (
    <div className="mx-auto max-w-lg pt-10 text-center">
      <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-olive-soft text-olive">
        <LayoutDashboard className="h-5 w-5" />
      </span>
      <h1 className="mt-5 text-h1 font-semibold tracking-[-0.02em] text-ink">{title}</h1>
      <p className="mx-auto mt-2 max-w-md text-body leading-relaxed text-ink-muted">{body}</p>
      {error && (
        <p className="mx-auto mt-3 flex max-w-md items-start gap-2 rounded-xl border border-danger-line bg-danger-soft px-3 py-2 text-left text-meta text-danger">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </p>
      )}
      <div className="mt-6">
        {href ? (
          <Link
            href={href}
            className="inline-flex rounded-lg bg-olive px-4 py-2.5 text-ui font-medium text-white shadow-card transition-colors hover:bg-olive-dark"
          >
            {actionLabel}
          </Link>
        ) : (
          <button
            type="button"
            onClick={onAction}
            disabled={actionDisabled}
            className="inline-flex rounded-lg bg-olive px-4 py-2.5 text-ui font-medium text-white shadow-card transition-colors hover:bg-olive-dark disabled:opacity-60"
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  );
}
