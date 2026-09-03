"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import LeadCard from "@/app/components/LeadCard";
import { ApiError, deleteSavedLead, getSavedLead } from "@/lib/api";
import type { SavedLead } from "@/lib/types";

export default function SavedLeadView({ leadId }: { leadId: string }) {
  const router = useRouter();
  const [lead, setLead] = useState<SavedLead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await getSavedLead(leadId);
        if (!cancelled) setLead(result);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load this lead.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leadId]);

  async function remove() {
    if (!lead) return;
    if (!window.confirm(`Remove "${lead.company_name}" from saved leads?`)) return;
    setRemoving(true);
    try {
      await deleteSavedLead(lead.lead_id);
      // The lead no longer exists, so returning to the list is the only
      // sensible destination.
      router.push("/leads");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove that lead.");
      setRemoving(false);
    }
  }

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-4xl px-6 py-12 sm:py-16">
        <Link
          href="/leads"
          className="text-sm text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          ← Saved leads
        </Link>

        {loading && (
          <p className="mt-8 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}

        {error && (
          <div className="mt-8 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        {lead && (
          <>
            <div className="mb-5 mt-4 flex flex-wrap items-end justify-between gap-3">
              <p className="text-xs text-zinc-400 dark:text-zinc-500">
                Saved {new Date(lead.saved_at).toLocaleString()} from{" "}
                {lead.source_category} in {lead.source_location}
                {lead.llm_model && <> · analysed with {lead.llm_model}</>}
                {/* A snapshot, not a live view — ratings and reviews drift. */}
                <br />
                Snapshot of the analysis at save time. Re-save from a fresh
                search to refresh it.
              </p>
              <button
                onClick={() => void remove()}
                disabled={removing}
                className="shrink-0 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-500 transition hover:border-red-300 hover:text-red-600 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-red-800 dark:hover:text-red-400"
              >
                {removing ? "Removing…" : "Remove lead"}
              </button>
            </div>

            <LeadCard lead={lead} rank={1} />
          </>
        )}
      </main>
    </div>
  );
}
