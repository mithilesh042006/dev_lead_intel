"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import LeadCard from "@/app/components/LeadCard";
import SaveLeadsBar from "@/app/components/SaveLeadsBar";
import ProgressPanel from "@/app/components/ProgressPanel";
import SearchForm from "@/app/components/SearchForm";
import {
  ApiError,
  cancelSearch,
  csvUrl,
  getJob,
  getLeads,
  savedLeadIds,
  startSearch,
} from "@/lib/api";
import { isTerminal, type Job, type Lead, type SearchBody } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

export default function Home() {
  const [job, setJob] = useState<Job | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [alreadySaved, setAlreadySaved] = useState<Set<string>>(new Set());

  // Held in a ref so the polling effect does not restart on every tick.
  const jobIdRef = useRef<string | null>(null);
  const busy = job !== null && !isTerminal(job.status);

  // Fetches the job and, once it has finished, its leads — then commits both.
  //
  // Order matters. Setting a terminal status flips `busy` to false, which tears
  // down the polling effect. If the leads request were still in flight at that
  // moment its result would be discarded and the page would claim "no leads"
  // for a job that has them. So leads are fetched BEFORE the status is
  // committed, and the only thing that invalidates the result is a newer
  // search having replaced this job.
  const syncJob = useCallback(async (id: string): Promise<void> => {
    const next = await getJob(id);
    if (jobIdRef.current !== id) return;

    if (isTerminal(next.status) && next.lead_count > 0) {
      const result = await getLeads(id);
      if (jobIdRef.current !== id) return;
      setLeads(result.leads);
    }
    setJob(next);
  }, []);

  const handleSubmit = useCallback(
    async (body: SearchBody) => {
      setError(null);
      setLeads([]);
      setJob(null);
      setCancelling(false);
      setSelected(new Set());
      try {
        const { job_id } = await startSearch(body);
        jobIdRef.current = job_id;
        // A fully cached search can finish before the first poll fires, so this
        // has to be able to land the leads too — not just the status.
        await syncJob(job_id);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to start the search.");
      }
    },
    [syncJob],
  );

  const handleCancel = useCallback(async () => {
    if (!jobIdRef.current) return;
    setCancelling(true);
    try {
      setJob(await cancelSearch(jobIdRef.current));
    } catch {
      // A job that finished between render and click is not an error worth
      // showing — the next poll reports the real status.
    } finally {
      setCancelling(false);
    }
  }, []);

  // Poll while the job is in flight; stop as soon as it reaches a terminal state.
  useEffect(() => {
    if (!busy) return;
    const id = jobIdRef.current;
    if (!id) return;

    let stopped = false;
    const timer = setInterval(async () => {
      if (stopped) return;
      try {
        await syncJob(id);
      } catch (err) {
        if (stopped) return;
        setError(err instanceof ApiError ? err.message : "Lost contact with the API.");
      }
    }, POLL_INTERVAL_MS);

    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [busy, syncJob]);

  // Which leads are already saved. Failure here is not worth surfacing — the
  // page simply shows nothing as saved.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ids = await savedLeadIds();
        if (!cancelled) setAlreadySaved(new Set(ids));
      } catch {
        /* saving may be disabled; leave the set empty */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leads]);

  function toggleLead(leadId: string, next: boolean) {
    setSelected((current) => {
      const updated = new Set(current);
      if (next) updated.add(leadId);
      else updated.delete(leadId);
      return updated;
    });
  }

  const finished = job !== null && isTerminal(job.status);
  // Keyed off the job's own count, not the local array. If the two ever
  // disagree the job is the truth, and claiming "no leads" for a job that
  // reports five is the worst possible answer.
  const noResults = finished && job.lead_count === 0;

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <header className="mb-5">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-3xl">
            Search
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Finds local businesses, reads their customer reviews for software pain
            points, and turns the best ones into cold-call-ready leads.
          </p>
        </header>

        <SearchForm onSubmit={handleSubmit} disabled={busy} />

        {error && (
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        {job && (
          <div className="mt-6">
            <ProgressPanel job={job} onCancel={handleCancel} cancelling={cancelling} />
          </div>
        )}

        {leads.length > 0 && job && (
          <section className="mt-10">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                {leads.length} qualified lead{leads.length === 1 ? "" : "s"}
              </h2>
              {job.has_csv && (
                <div className="flex gap-2">
                  <a
                    href={csvUrl(job.job_id, "leads")}
                    className="rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
                  >
                    Export CSV
                  </a>
                  <a
                    href={csvUrl(job.job_id, "evidence")}
                    className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-white dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                  >
                    Evidence CSV
                  </a>
                </div>
              )}
            </div>

            {/* Saving is explicit and per-lead (§28): only the ticked leads
                reach the database. */}
            <div className="mb-5">
              <SaveLeadsBar
                jobId={job.job_id}
                selectedIds={[...selected]}
                totalLeads={leads.length}
                onSelectAll={() => setSelected(new Set(leads.map((l) => l.lead_id)))}
                onClear={() => setSelected(new Set())}
                onSaved={(ids) => {
                  setAlreadySaved((current) => new Set([...current, ...ids]));
                  setSelected(new Set());
                }}
              />
            </div>

            <div className="space-y-5">
              {leads.map((lead, i) => (
                <LeadCard
                  key={lead.lead_id}
                  lead={lead}
                  rank={i + 1}
                  selected={selected.has(lead.lead_id)}
                  onSelect={toggleLead}
                  alreadySaved={alreadySaved.has(lead.lead_id)}
                />
              ))}
            </div>
          </section>
        )}

        {noResults && job.status !== "failed" && (
          <div className="mt-6 rounded-xl border border-zinc-200 bg-white p-6 text-center dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              No qualified leads found.
            </p>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Try widening the rating range or lowering the minimum review count —
              most businesses in a given area sit outside a narrow band.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
