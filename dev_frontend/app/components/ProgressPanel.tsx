"use client";

import type { Job } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued",
  search: "Searching Google Maps",
  filter: "Filtering businesses",
  website: "Analysing websites",
  analyse: "Analysing reviews with AI",
  pitch: "Writing cold-call pitches",
  export: "Building CSV",
  done: "Done",
  cancelled: "Cancelled",
  failed: "Failed",
};

interface Props {
  job: Job;
  onCancel: () => void;
  cancelling: boolean;
}

export default function ProgressPanel({ job, onCancel, cancelling }: Props) {
  const running = job.status === "running" || job.status === "queued";

  return (
    <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            {STAGE_LABELS[job.stage] ?? job.stage}
          </p>
          <p className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400">
            {job.message || `${job.category} in ${job.location}`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="text-sm font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
            {job.progress}%
          </span>
          {running && (
            <button
              onClick={onCancel}
              disabled={cancelling}
              className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-600
                         transition hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700
                         dark:text-zinc-400 dark:hover:bg-zinc-900"
            >
              {cancelling ? "Cancelling…" : "Cancel"}
            </button>
          )}
        </div>
      </div>

      <div
        className="mt-3 h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800"
        role="progressbar"
        aria-valuenow={job.progress}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            job.status === "failed"
              ? "bg-red-500"
              : job.status === "cancelled"
                ? "bg-zinc-400"
                : "bg-zinc-900 dark:bg-zinc-100"
          }`}
          style={{ width: `${job.progress}%` }}
        />
      </div>

      {/* §35 — a partial run still delivers leads; say what is missing rather
          than pretending the run failed. */}
      {job.warnings.length > 0 && (
        <ul className="mt-4 space-y-1.5">
          {job.warnings.map((w, i) => (
            <li
              key={i}
              className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
            >
              {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
