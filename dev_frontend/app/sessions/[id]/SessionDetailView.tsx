"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import LeadCard from "@/app/components/LeadCard";
import { ApiError, getSession } from "@/lib/api";
import type { SessionDetail } from "@/lib/types";

export default function SessionDetailView({ id }: { id: number }) {
  const [session, setSession] = useState<SessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await getSession(id);
        if (!cancelled) setSession(result);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Could not load this session.",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-4xl px-6 py-12 sm:py-16">
        <Link
          href="/sessions"
          className="text-sm text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          ← All sessions
        </Link>

        {loading && (
          <p className="mt-8 text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        )}

        {error && (
          <div className="mt-8 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        {session && (
          <>
            <header className="mb-8 mt-4">
              <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-3xl">
                {session.name}
              </h1>
              <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
                {session.category} · {session.location} · rating {session.min_rating}–
                {session.max_rating} · min {session.minimum_reviews} reviews ·{" "}
                {session.lead_count} lead{session.lead_count === 1 ? "" : "s"}
              </p>
              <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
                Saved {new Date(session.created_at).toLocaleString()}
                {session.llm_model && <> · analysed with {session.llm_model}</>}
              </p>
              {/* A snapshot, not a live view — say so, because ratings and
                  reviews drift after the fact. */}
              <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
                This is a snapshot of the results as they were when saved. Re-run
                the search to see current data.
              </p>
            </header>

            {session.warnings.length > 0 && (
              <ul className="mb-6 space-y-1.5">
                {session.warnings.map((w, i) => (
                  <li
                    key={i}
                    className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
                  >
                    {w}
                  </li>
                ))}
              </ul>
            )}

            <div className="space-y-5">
              {session.leads.map((lead, i) => (
                <LeadCard key={lead.lead_id} lead={lead} rank={i + 1} />
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
