"use client";

import { useState } from "react";
import Link from "next/link";

import { ApiError, saveSession } from "@/lib/api";
import type { Job } from "@/lib/types";

interface Props {
  job: Job;
}

type State =
  | { kind: "idle" }
  | { kind: "naming" }
  | { kind: "saving" }
  | { kind: "saved"; id: number; name: string }
  | { kind: "error"; message: string };

export default function SaveSessionBar({ job }: Props) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [name, setName] = useState(`${job.category} in ${job.location}`);

  async function commit() {
    setState({ kind: "saving" });
    try {
      const saved = await saveSession(job.job_id, name.trim() || undefined);
      setState({ kind: "saved", id: saved.id, name: saved.name });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof ApiError ? err.message : "Could not save this session.",
      });
    }
  }

  // Once saved, saving the same results again would just duplicate the row —
  // so the button is replaced by a link to what was saved.
  if (state.kind === "saved") {
    return (
      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-900/50 dark:bg-emerald-950/40">
        <span className="text-sm text-emerald-800 dark:text-emerald-200">
          Saved as <span className="font-semibold">{state.name}</span>
        </span>
        <Link
          href={`/sessions/${state.id}`}
          className="text-sm font-medium text-emerald-800 underline underline-offset-2 hover:no-underline dark:text-emerald-200"
        >
          Open session
        </Link>
      </div>
    );
  }

  if (state.kind === "naming" || state.kind === "saving") {
    const saving = state.kind === "saving";
    return (
      <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
        <label
          htmlFor="session-name"
          className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400"
        >
          Name this session
        </label>
        <div className="flex flex-wrap gap-2">
          <input
            id="session-name"
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void commit();
              if (e.key === "Escape") setState({ kind: "idle" });
            }}
            maxLength={200}
            disabled={saving}
            className="min-w-0 flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm
                       text-zinc-900 outline-none focus:border-zinc-900 focus:ring-2
                       focus:ring-zinc-900/10 disabled:opacity-50 dark:border-zinc-700
                       dark:bg-zinc-900 dark:text-zinc-100"
          />
          <button
            onClick={() => void commit()}
            disabled={saving}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-semibold text-white transition
                       hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900
                       dark:hover:bg-zinc-300"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            onClick={() => setState({ kind: "idle" })}
            disabled={saving}
            className="rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-600
                       transition hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700
                       dark:text-zinc-400 dark:hover:bg-zinc-900"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button
        onClick={() => setState({ kind: "naming" })}
        className="rounded-lg border border-zinc-300 px-4 py-1.5 text-xs font-semibold text-zinc-800
                   transition hover:bg-white dark:border-zinc-700 dark:text-zinc-200
                   dark:hover:bg-zinc-900"
      >
        Save session
      </button>
      {state.kind === "error" && (
        <span className="text-xs text-red-600 dark:text-red-400">{state.message}</span>
      )}
    </div>
  );
}
