"use client";

import { useState } from "react";
import Link from "next/link";

import { ApiError, saveLeads } from "@/lib/api";

interface Props {
  jobId: string;
  selectedIds: string[];
  totalLeads: number;
  onSelectAll: () => void;
  onClear: () => void;
  onSaved: (leadIds: string[]) => void;
}

export default function SaveLeadsBar({
  jobId,
  selectedIds,
  totalLeads,
  onSelectAll,
  onClear,
  onSaved,
}: Props) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ created: number; updated: number } | null>(
    null,
  );

  const count = selectedIds.length;
  const allSelected = count === totalLeads && totalLeads > 0;

  async function commit() {
    setSaving(true);
    setError(null);
    try {
      const outcome = await saveLeads(jobId, selectedIds);
      setResult({ created: outcome.created, updated: outcome.updated });
      onSaved(outcome.lead_ids);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save those leads.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-xl border border-zinc-200 bg-white px-4 py-3 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-zinc-600 dark:text-zinc-300">
          {count === 0 ? (
            "Select the leads worth keeping"
          ) : (
            <>
              <span className="font-semibold text-zinc-900 dark:text-zinc-50">{count}</span>{" "}
              of {totalLeads} selected
            </>
          )}
        </span>

        <button
          onClick={allSelected ? onClear : onSelectAll}
          className="text-xs font-medium text-zinc-500 underline underline-offset-2 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          {allSelected ? "Clear all" : "Select all"}
        </button>

        <div className="ml-auto flex items-center gap-3">
          {result && (
            <span className="text-xs text-emerald-700 dark:text-emerald-300">
              {result.created > 0 && `${result.created} saved`}
              {result.created > 0 && result.updated > 0 && ", "}
              {/* A refresh is not a new lead — say which happened. */}
              {result.updated > 0 && `${result.updated} refreshed`}
            </span>
          )}
          <Link
            href="/leads"
            className="text-xs font-medium text-zinc-500 underline underline-offset-2 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            View saved leads
          </Link>
          <button
            onClick={() => void commit()}
            disabled={count === 0 || saving}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition
                       hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40
                       dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            {saving ? "Saving…" : `Save ${count > 0 ? count : ""} lead${count === 1 ? "" : "s"}`}
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}
