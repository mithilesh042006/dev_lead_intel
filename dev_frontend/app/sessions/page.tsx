"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, deleteSession, listSessions } from "@/lib/api";
import type { SessionSummary } from "@/lib/types";

function priorityTone(score: number): string {
  if (score >= 80) return "text-red-600 dark:text-red-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  if (score >= 40) return "text-sky-600 dark:text-sky-400";
  return "text-zinc-500 dark:text-zinc-400";
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  // Fetch inline rather than through an extracted callback: every setState
  // then provably follows an await, which is what react-hooks/set-state-in-effect
  // wants. The cancelled flag stops a late response updating an unmounted page.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await listSessions();
        if (!cancelled) {
          setSessions(result.sessions);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load sessions.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function remove(id: number, name: string) {
    if (!window.confirm(`Delete "${name}"? This cannot be undone.`)) return;
    setDeleting(id);
    try {
      await deleteSession(id);
      setSessions((current) => current.filter((s) => s.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete that session.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-4xl px-6 py-12 sm:py-16">
        <header className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-3xl">
            Saved sessions
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Searches you chose to keep. Each is a snapshot of what the leads
            looked like when it was saved.
          </p>
        </header>

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        ) : sessions.length === 0 ? (
          <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              No saved sessions yet.
            </p>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
              Run a search, then press <span className="font-medium">Save session</span> on
              the results to keep it here.
            </p>
          </div>
        ) : (
          <ul className="space-y-3">
            {sessions.map((s) => (
              <li
                key={s.id}
                className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm transition hover:border-zinc-300 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:border-zinc-700"
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <Link
                      href={`/sessions/${s.id}`}
                      className="text-base font-semibold text-zinc-900 hover:underline dark:text-zinc-50"
                    >
                      {s.name}
                    </Link>
                    <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                      {s.category} · {s.location} · rating {s.min_rating}–{s.max_rating} ·{" "}
                      min {s.minimum_reviews} reviews
                    </p>
                    <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
                      {new Date(s.created_at).toLocaleString()}
                      {s.llm_model && <> · {s.llm_model}</>}
                      {s.status !== "completed" && <> · {s.status}</>}
                    </p>
                  </div>

                  <div className="flex items-center gap-4 text-right">
                    <div>
                      <div className="text-sm font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
                        {s.lead_count}
                      </div>
                      <div className="text-[10px] uppercase tracking-wide text-zinc-400">
                        leads
                      </div>
                    </div>
                    <div>
                      <div
                        className={`text-sm font-semibold tabular-nums ${priorityTone(s.top_score)}`}
                      >
                        {s.top_score}
                      </div>
                      <div className="text-[10px] uppercase tracking-wide text-zinc-400">
                        top score
                      </div>
                    </div>
                    <button
                      onClick={() => void remove(s.id, s.name)}
                      disabled={deleting === s.id}
                      className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-500 transition hover:border-red-300 hover:text-red-600 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-red-800 dark:hover:text-red-400"
                    >
                      {deleting === s.id ? "…" : "Delete"}
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
