"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, getDashboard } from "@/lib/api";
import type { Dashboard, DashboardLeadRef, Priority } from "@/lib/types";

// Priority is an ordinal scale, so it takes one hue light→dark rather than four
// categorical colors. The steps live in globals.css as CSS variables so dark
// mode is a re-stepped ramp validated against the dark surface, not a flip —
// and so there is no hydration flash from reading the media query in JS.
const PRIORITY_FILL: Record<Priority, string> = {
  HOT: "var(--priority-hot)",
  WARM: "var(--priority-warm)",
  COLD: "var(--priority-cold)",
  LOW: "var(--priority-low)",
};

const PRIORITY_ORDER: Priority[] = ["HOT", "WARM", "COLD", "LOW"];

function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString();
}

function daysFromToday(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  const then = new Date(y, m - 1, d);
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.round((then.getTime() - now.getTime()) / 86_400_000);
}

/** A headline number. Not a one-bar chart. */
function StatTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "urgent";
}) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        {label}
      </p>
      <p
        className={`mt-2 text-3xl font-bold tabular-nums ${
          tone === "urgent" && Number(value) > 0
            ? "text-red-600 dark:text-red-400"
            : "text-zinc-900 dark:text-zinc-50"
        }`}
      >
        {value}
      </p>
      {hint && (
        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">{hint}</p>
      )}
    </div>
  );
}

function LeadRow({ lead, note }: { lead: DashboardLeadRef; note?: string }) {
  return (
    <li className="group relative flex items-center gap-3 px-4 py-2.5 transition hover:bg-zinc-50 dark:hover:bg-zinc-900">
      <span className="w-8 shrink-0 text-right text-sm font-bold tabular-nums text-zinc-900 dark:text-zinc-50">
        {lead.lead_score}
      </span>
      <div className="min-w-0 flex-1">
        <Link
          href={`/leads/${lead.lead_id}`}
          className="truncate text-sm font-medium text-zinc-900 after:absolute after:inset-0 after:content-[''] group-hover:underline dark:text-zinc-50"
        >
          {lead.company_name}
        </Link>
        <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
          {lead.pain_category || lead.city || "—"}
        </p>
      </div>
      {note && (
        <span className="shrink-0 text-xs text-zinc-500 dark:text-zinc-400">{note}</span>
      )}
    </li>
  );
}

function WorkList({
  title,
  description,
  leads,
  empty,
  noteFor,
}: {
  title: string;
  description: string;
  leads: DashboardLeadRef[];
  empty: string;
  noteFor?: (lead: DashboardLeadRef) => string | undefined;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
      <div className="border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
        <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
          {title}
          {leads.length > 0 && (
            <span className="ml-2 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
              {leads.length}
            </span>
          )}
        </h2>
        <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{description}</p>
      </div>
      {leads.length === 0 ? (
        <p className="px-5 py-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
          {empty}
        </p>
      ) : (
        <ul className="divide-y divide-zinc-100 py-1 dark:divide-zinc-800">
          {leads.map((l) => (
            <LeadRow key={l.lead_id} lead={l} note={noteFor?.(l)} />
          ))}
        </ul>
      )}
    </section>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await getDashboard();
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load the dashboard.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const maxPain = data
    ? Math.max(1, ...data.by_pain_category.map((c) => c.count))
    : 1;

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <header className="mb-5">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-3xl">
            Dashboard
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Your saved pipeline and what needs a call today.
          </p>
        </header>

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        {loading && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}

        {data && data.total_leads === 0 && (
          <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              Nothing saved yet.
            </p>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Run a search and save the leads worth keeping — this page fills in
              from there.
            </p>
            <Link
              href="/"
              className="mt-4 inline-block rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900"
            >
              Start a search
            </Link>
          </div>
        )}

        {data && data.total_leads > 0 && (
          <div className="space-y-6">
            {/* KPI row — headline numbers, no chart needed */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Saved leads" value={data.total_leads} />
              <StatTile
                label="Overdue"
                value={data.overdue.length}
                hint="follow-up date has passed"
                tone="urgent"
              />
              <StatTile
                label="Never contacted"
                value={data.leads_never_contacted}
                hint={`${data.leads_contacted} contacted so far`}
              />
              <StatTile
                label="Top score"
                value={data.top_score}
                hint={`${data.average_score} average`}
              />
            </div>

            {/* Priority mix: part-to-whole on an ordered scale → one stacked
                bar in a single hue, with a legend and direct labels so identity
                is never carried by color alone. */}
            <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
                Priority mix
              </h2>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                {data.total_leads} saved lead{data.total_leads === 1 ? "" : "s"}
              </p>

              <div className="mt-4 flex h-3 w-full gap-0.5 overflow-hidden rounded-full">
                {PRIORITY_ORDER.map((p) => {
                  const count =
                    data.by_priority.find((b) => b.priority === p)?.count ?? 0;
                  if (count === 0) return null;
                  return (
                    <div
                      key={p}
                      style={{
                        width: `${(count / data.total_leads) * 100}%`,
                        backgroundColor: PRIORITY_FILL[p],
                      }}
                      title={`${p}: ${count}`}
                    />
                  );
                })}
              </div>

              <ul className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
                {PRIORITY_ORDER.map((p) => {
                  const count =
                    data.by_priority.find((b) => b.priority === p)?.count ?? 0;
                  return (
                    <li key={p} className="flex items-center gap-2">
                      <span
                        aria-hidden="true"
                        className="h-2.5 w-2.5 rounded-sm"
                        style={{ backgroundColor: PRIORITY_FILL[p] }}
                      />
                      {/* Label and value in ink, not the series color. */}
                      <span className="text-xs text-zinc-600 dark:text-zinc-300">{p}</span>
                      <span className="text-xs font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
                        {count}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>

            {/* Worklists — the reason to open this page */}
            <div className="grid gap-6 lg:grid-cols-2">
              <WorkList
                title="Overdue follow-ups"
                description="You said you would call back, and the date has passed."
                leads={data.overdue}
                empty="Nothing overdue."
                noteFor={(l) =>
                  l.next_followup_on
                    ? `${Math.abs(daysFromToday(l.next_followup_on))}d late`
                    : undefined
                }
              />
              <WorkList
                title="Due this week"
                description="Follow-ups committed to in the next 7 days."
                leads={data.due_soon}
                empty="Nothing due this week."
                noteFor={(l) =>
                  l.next_followup_on ? formatDate(l.next_followup_on) : undefined
                }
              />
              <WorkList
                title="Not contacted yet"
                description="Saved but never followed up, highest score first."
                leads={data.needs_attention}
                empty="Every saved lead has been contacted."
              />
              <WorkList
                title="Recently saved"
                description="The last few leads you kept."
                leads={data.recent}
                empty="Nothing saved yet."
              />
            </div>

            {/* Magnitude across categories → bars in one hue, sorted, labelled */}
            {data.by_pain_category.length > 0 && (
              <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
                <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">
                  Pain categories
                </h2>
                <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                  What your saved leads are struggling with — the demand signal
                  for what to build.
                </p>
                <ul className="mt-4 space-y-2.5">
                  {data.by_pain_category.map((c) => (
                    <li key={c.category} className="flex items-center gap-3">
                      <span className="w-44 shrink-0 truncate text-xs text-zinc-600 dark:text-zinc-300">
                        {c.category}
                      </span>
                      <div className="h-2.5 flex-1">
                        <div
                          className="h-full rounded-[3px]"
                          style={{
                            width: `${(c.count / maxPain) * 100}%`,
                            backgroundColor: PRIORITY_FILL.WARM,
                          }}
                        />
                      </div>
                      <span className="w-6 shrink-0 text-right text-xs font-semibold tabular-nums text-zinc-900 dark:text-zinc-50">
                        {c.count}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
