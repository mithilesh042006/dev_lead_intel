"use client";

import { useEffect, useState } from "react";

import LeadCard from "@/app/components/LeadCard";
import { ApiError, deleteSavedLead, listSavedLeads } from "@/lib/api";
import type { SavedLead } from "@/lib/types";

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
            Leads you chose to keep, highest score first. Each is a snapshot of
            the analysis at the time it was saved — re-save from a fresh search
            to refresh one.
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
            <p className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
              {leads.length} saved lead{leads.length === 1 ? "" : "s"}
            </p>
            <div className="space-y-5">
              {leads.map((lead, i) => (
                <div key={lead.lead_id}>
                  <LeadCard lead={lead} rank={i + 1} />
                  <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2 px-1">
                    <span className="text-xs text-zinc-400 dark:text-zinc-500">
                      Saved {new Date(lead.saved_at).toLocaleDateString()} from{" "}
                      {lead.source_category} in {lead.source_location}
                    </span>
                    <button
                      onClick={() => void remove(lead.lead_id, lead.company_name)}
                      disabled={removing === lead.lead_id}
                      className="text-xs font-medium text-zinc-400 transition hover:text-red-600 disabled:opacity-50 dark:hover:text-red-400"
                    >
                      {removing === lead.lead_id ? "Removing…" : "Remove"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
