"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, deleteSavedLead, listSavedLeads } from "@/lib/api";
import type { Priority, SavedLead } from "@/lib/types";

const PRIORITY_STYLES: Record<Priority, string> = {
  HOT: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-400/20",
  WARM: "bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-400/20",
  COLD: "bg-sky-50 text-sky-700 ring-sky-600/20 dark:bg-sky-950/40 dark:text-sky-300 dark:ring-sky-400/20",
  LOW: "bg-zinc-100 text-zinc-600 ring-zinc-500/20 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-400/20",
};

export default function SavedLeadsPage() {
  const [leads, setLeads] = useState<SavedLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);

  // Fetch inline so every setState provably follows an await
  // (react-hooks/set-state-in-effect).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await listSavedLeads();
        if (!cancelled) {
          setLeads(result.leads);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load saved leads.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function remove(leadId: string, name: string) {
    if (!window.confirm(`Remove "${name}" from saved leads?`)) return;
    setRemoving(leadId);
    try {
      await deleteSavedLead(leadId);
      setLeads((current) => current.filter((l) => l.lead_id !== leadId));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove that lead.");
    } finally {
      setRemoving(null);
    }
  }

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-4xl px-6 py-12 sm:py-16">
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-3xl">
            Saved leads
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Highest score first. Open one to see its evidence, score breakdown
            and cold-call opening.
          </p>
        </header>

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        ) : leads.length === 0 ? (
          <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              No saved leads yet.
            </p>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Run a search, tick the leads worth keeping, then press{" "}
              <span className="font-medium">Save leads</span>.
            </p>
          </div>
        ) : (
          <>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {leads.length} saved lead{leads.length === 1 ? "" : "s"}
            </p>

            {/* Compact rows: enough to choose one to call, no more. The full
                analysis lives on the detail page. */}
            <ul className="divide-y divide-zinc-200 overflow-hidden rounded-2xl border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-950">
              {leads.map((lead) => (
                <li
                  key={lead.lead_id}
                  className="group relative flex items-center gap-4 px-4 py-3 transition hover:bg-zinc-50 dark:hover:bg-zinc-900"
                >
                  <div className="w-10 shrink-0 text-center">
                    <div className="text-lg font-bold tabular-nums leading-none text-zinc-900 dark:text-zinc-50">
                      {lead.scores.lead_score}
                    </div>
                  </div>

                  <div className="min-w-0 flex-1">
                    {/* Stretched link: the whole row is the target, but the
                        Remove button stays clickable because it is above it. */}
                    <Link
                      href={`/leads/${lead.lead_id}`}
                      className="truncate text-sm font-semibold text-zinc-900 after:absolute after:inset-0 after:content-[''] group-hover:underline dark:text-zinc-50"
                    >
                      {lead.company_name}
                    </Link>
                    <p className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400">
                      {lead.category || "—"}
                      {lead.rating !== null && <> · {lead.rating.toFixed(1)}★</>}
                      {lead.city && <> · {lead.city}</>}
                      {lead.pain_category && <> · {lead.pain_category}</>}
                    </p>
                  </div>

                  <span
                    className={`hidden shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset sm:inline ${PRIORITY_STYLES[lead.scores.priority]}`}
                  >
                    {lead.scores.priority}
                  </span>

                  <span className="hidden w-24 shrink-0 text-right text-xs text-zinc-400 dark:text-zinc-500 md:block">
                    {new Date(lead.saved_at).toLocaleDateString()}
                  </span>

                  <button
                    onClick={() => void remove(lead.lead_id, lead.company_name)}
                    disabled={removing === lead.lead_id}
                    className="relative z-10 shrink-0 rounded-lg px-2 py-1 text-xs font-medium text-zinc-400 transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                  >
                    {removing === lead.lead_id ? "…" : "Remove"}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </main>
    </div>
  );
}
