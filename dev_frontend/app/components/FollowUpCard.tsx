"use client";

import { useEffect, useState } from "react";

import { ApiError, addFollowUp, deleteFollowUp, listFollowUps } from "@/lib/api";
import type { FollowUp } from "@/lib/types";

const FIELD =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 " +
  "outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 " +
  "disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 " +
  "dark:focus:border-zinc-400 dark:focus:ring-zinc-100/10";

const LABEL = "mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300";

function today(): string {
  // Local date, not toISOString() — that shifts to UTC and can log the wrong
  // day for anyone east or west of it.
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatDate(iso: string): string {
  // Parse as a local date; "2026-09-03" alone is treated as UTC midnight.
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString();
}

export default function FollowUpCard({ leadId }: { leadId: string }) {
  const [followups, setFollowups] = useState<FollowUp[]>([]);
  const [methods, setMethods] = useState<string[]>(["Call"]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [happenedOn, setHappenedOn] = useState(today());
  const [method, setMethod] = useState("Call");
  const [outcome, setOutcome] = useState("");
  const [notes, setNotes] = useState("");
  const [nextOn, setNextOn] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await listFollowUps(leadId);
        if (!cancelled) {
          setFollowups(result.followups);
          setMethods(result.methods);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Could not load follow-ups.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leadId]);

  function resetForm() {
    setHappenedOn(today());
    setMethod("Call");
    setOutcome("");
    setNotes("");
    setNextOn("");
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const entry = await addFollowUp(leadId, {
        happened_on: happenedOn,
        method,
        outcome,
        notes,
        next_followup_on: nextOn || null,
      });
      setFollowups((current) => [entry, ...current]);
      resetForm();
      setAdding(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save that follow-up.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    if (!window.confirm("Delete this follow-up?")) return;
    try {
      await deleteFollowUp(leadId, id);
      setFollowups((current) => current.filter((f) => f.id !== id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not delete that follow-up.");
    }
  }

  return (
    <section className="mt-5 rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 p-5 dark:border-zinc-800">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          Follow-Up History
        </h2>
        {!adding && (
          <button
            onClick={() => setAdding(true)}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition
                       hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            + Add Follow-Up
          </button>
        )}
      </div>

      {error && (
        <p className="border-b border-zinc-100 px-5 py-3 text-sm text-red-600 dark:border-zinc-800 dark:text-red-400">
          {error}
        </p>
      )}

      {adding && (
        <form onSubmit={submit} className="border-b border-zinc-100 p-5 dark:border-zinc-800">
          <h3 className="mb-4 text-base font-semibold text-zinc-900 dark:text-zinc-50">
            Add Follow-Up
          </h3>

          <div className="space-y-4">
            <div>
              <label className={LABEL} htmlFor="fu-date">
                Date
              </label>
              <input
                id="fu-date"
                type="date"
                required
                className={FIELD}
                value={happenedOn}
                onChange={(e) => setHappenedOn(e.target.value)}
                disabled={saving}
              />
            </div>

            <div>
              <label className={LABEL} htmlFor="fu-method">
                Method
              </label>
              <select
                id="fu-method"
                className={FIELD}
                value={method}
                onChange={(e) => setMethod(e.target.value)}
                disabled={saving}
              >
                {methods.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className={LABEL} htmlFor="fu-outcome">
                Outcome
              </label>
              <input
                id="fu-outcome"
                className={FIELD}
                placeholder="Interested / No response / Meeting…"
                value={outcome}
                onChange={(e) => setOutcome(e.target.value)}
                maxLength={300}
                disabled={saving}
              />
            </div>

            <div>
              <label className={LABEL} htmlFor="fu-notes">
                Notes
              </label>
              <textarea
                id="fu-notes"
                rows={4}
                className={FIELD}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                maxLength={4000}
                disabled={saving}
              />
            </div>

            <div>
              <label className={LABEL} htmlFor="fu-next">
                Next Follow-Up
              </label>
              <input
                id="fu-next"
                type="date"
                className={FIELD}
                value={nextOn}
                // The backend rejects a next date before the follow-up date;
                // min stops the browser offering one in the first place.
                min={happenedOn}
                onChange={(e) => setNextOn(e.target.value)}
                disabled={saving}
              />
            </div>
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                resetForm();
                setAdding(false);
                setError(null);
              }}
              disabled={saving}
              className="rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-600
                         transition hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700
                         dark:text-zinc-400 dark:hover:bg-zinc-900"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition
                         hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900
                         dark:hover:bg-zinc-300"
            >
              {saving ? "Saving…" : "Save Follow-Up"}
            </button>
          </div>
        </form>
      )}

      <div className="p-5">
        {loading ? (
          <p className="text-center text-sm text-zinc-500 dark:text-zinc-400">Loading…</p>
        ) : followups.length === 0 ? (
          <p className="py-6 text-center text-sm text-zinc-500 dark:text-zinc-400">
            No follow-ups yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {followups.map((f) => (
              <li
                key={f.id}
                className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {formatDate(f.happened_on)}
                      <span className="ml-2 rounded-md bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                        {f.method}
                      </span>
                    </p>
                    {f.outcome && (
                      <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">
                        {f.outcome}
                      </p>
                    )}
                    {f.notes && (
                      <p className="mt-1 whitespace-pre-wrap text-sm text-zinc-500 dark:text-zinc-400">
                        {f.notes}
                      </p>
                    )}
                    {f.next_followup_on && (
                      <p className="mt-2 text-xs font-medium text-zinc-500 dark:text-zinc-400">
                        Next follow-up: {formatDate(f.next_followup_on)}
                      </p>
                    )}
                  </div>
                  <button
                    onClick={() => void remove(f.id)}
                    className="shrink-0 text-xs font-medium text-zinc-400 transition hover:text-red-600 dark:hover:text-red-400"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
