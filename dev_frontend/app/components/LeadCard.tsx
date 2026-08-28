"use client";

import { useState } from "react";
import type { Lead, Priority } from "@/lib/types";

const PRIORITY_STYLES: Record<Priority, string> = {
  HOT: "bg-red-50 text-red-700 ring-red-600/20 dark:bg-red-950/40 dark:text-red-300 dark:ring-red-400/20",
  WARM: "bg-amber-50 text-amber-700 ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-400/20",
  COLD: "bg-sky-50 text-sky-700 ring-sky-600/20 dark:bg-sky-950/40 dark:text-sky-300 dark:ring-sky-400/20",
  LOW: "bg-zinc-100 text-zinc-600 ring-zinc-500/20 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-400/20",
};

const SEVERITY_STYLES: Record<string, string> = {
  high: "text-red-600 dark:text-red-400",
  medium: "text-amber-600 dark:text-amber-400",
  low: "text-zinc-500 dark:text-zinc-400",
};

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
      {children}
    </h4>
  );
}

function ScoreBar({ label, value, weight }: { label: string; value: number; weight: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="w-24 shrink-0 text-xs text-zinc-500 dark:text-zinc-400">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        <div
          className="h-full rounded-full bg-zinc-800 dark:bg-zinc-300"
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
      <span className="w-14 shrink-0 text-right text-xs tabular-nums text-zinc-600 dark:text-zinc-300">
        {value.toFixed(0)}
        <span className="text-zinc-400 dark:text-zinc-500"> ×{weight}</span>
      </span>
    </div>
  );
}

export default function LeadCard({ lead, rank }: { lead: Lead; rank: number }) {
  const [showDetail, setShowDetail] = useState(false);
  const s = lead.scores;
  const topEvidence = lead.evidence[0];

  return (
    <article className="rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      {/* --- Header --- */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-100 p-5 dark:border-zinc-800">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-zinc-400 dark:text-zinc-500">#{rank}</span>
            <h3 className="truncate text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {lead.company_name}
            </h3>
          </div>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            {lead.category || "—"}
            {lead.rating !== null && <> · {lead.rating.toFixed(1)}★</>}
            {lead.total_reviews > 0 && <> · {lead.total_reviews.toLocaleString()} reviews</>}
            {lead.city && <> · {lead.city}</>}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-2xl font-bold tabular-nums text-zinc-900 dark:text-zinc-50">
              {s.lead_score}
            </div>
            <div className="text-[10px] uppercase tracking-wide text-zinc-400">/ 100</div>
          </div>
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset ${PRIORITY_STYLES[s.priority]}`}
          >
            {s.priority}
          </span>
        </div>
      </div>

      <div className="space-y-5 p-5">
        {/* --- §33 FACT: what the customer actually said --- */}
        <section>
          <SectionLabel>Customer pain point · fact</SectionLabel>
          {lead.pain_point ? (
            <>
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                {lead.pain_point}
              </p>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                {lead.pain_category} ·{" "}
                <span className={SEVERITY_STYLES[lead.pain_severity] ?? ""}>
                  {lead.pain_severity} severity
                </span>
              </p>
              {topEvidence && (
                <blockquote className="mt-3 border-l-2 border-zinc-300 pl-3 dark:border-zinc-700">
                  <p className="text-sm italic text-zinc-600 dark:text-zinc-300">
                    “{topEvidence.review_text}”
                  </p>
                  <cite className="mt-1 block text-xs not-italic text-zinc-400 dark:text-zinc-500">
                    {topEvidence.review_rating !== null && `${topEvidence.review_rating}★`}
                    {topEvidence.review_date &&
                      ` · ${new Date(topEvidence.review_date).toLocaleDateString()}`}
                    {lead.evidence.length > 1 &&
                      ` · +${lead.evidence.length - 1} more supporting review${lead.evidence.length > 2 ? "s" : ""}`}
                  </cite>
                </blockquote>
              )}
            </>
          ) : (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              No software-related pain point found in the analysed reviews.
            </p>
          )}
        </section>

        {/* --- §33 INTERPRETATION + RECOMMENDATION --- */}
        {lead.primary_opportunity && (
          <section>
            <SectionLabel>Software opportunity · AI interpretation</SectionLabel>
            <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
              {lead.primary_opportunity}
            </p>
            {lead.secondary_opportunities.length > 0 && (
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                Also: {lead.secondary_opportunities.join(" · ")}
              </p>
            )}
            <p className="mt-2 text-xs text-zinc-400 dark:text-zinc-500">
              {Math.round(lead.confidence * 100)}% confidence — an interpretation, not a
              confirmed fact about this business.
            </p>
          </section>
        )}

        {/* --- Contact + tech --- */}
        <section className="grid gap-4 sm:grid-cols-2">
          <div>
            <SectionLabel>Contact</SectionLabel>
            <dl className="space-y-1 text-sm">
              <div className="flex gap-2">
                <dt className="w-14 shrink-0 text-zinc-400">Phone</dt>
                <dd className="min-w-0 text-zinc-700 dark:text-zinc-300">
                  {lead.phone ? (
                    <a href={`tel:${lead.phone}`} className="hover:underline">
                      {lead.phone}
                    </a>
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </dd>
              </div>
              <div className="flex gap-2">
                <dt className="w-14 shrink-0 text-zinc-400">Email</dt>
                <dd className="min-w-0 truncate text-zinc-700 dark:text-zinc-300">
                  {lead.email ? (
                    <a href={`mailto:${lead.email}`} className="hover:underline">
                      {lead.email}
                    </a>
                  ) : (
                    <span className="text-zinc-400">—</span>
                  )}
                </dd>
              </div>
            </dl>
          </div>

          <div>
            <SectionLabel>Technology</SectionLabel>
            {lead.technology_signals.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {lead.technology_signals.map((sig) => (
                  <span
                    key={sig}
                    className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
                  >
                    {sig}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-400">
                {lead.website_reachable ? "None detected" : "No reachable website"}
              </p>
            )}
          </div>
        </section>

        {/* --- Pitch --- */}
        {lead.sales_pitch && (
          <section>
            <SectionLabel>Cold-call opening</SectionLabel>
            <div className="rounded-lg bg-zinc-50 p-4 dark:bg-zinc-900">
              <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                {lead.sales_pitch}
              </p>
              <button
                onClick={() => navigator.clipboard?.writeText(lead.sales_pitch)}
                className="mt-3 text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
              >
                Copy pitch
              </button>
            </div>
          </section>
        )}

        {/* --- Score breakdown --- */}
        <section>
          <button
            onClick={() => setShowDetail((v) => !v)}
            className="text-xs font-medium text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            {showDetail ? "Hide" : "Show"} score breakdown &amp; all evidence
          </button>

          {showDetail && (
            <div className="mt-4 space-y-4">
              <div className="space-y-2">
                <ScoreBar label="Software pain" value={s.software_pain_score} weight="40%" />
                <ScoreBar label="Potential" value={s.business_potential_score} weight="25%" />
                <ScoreBar label="Evidence" value={s.review_evidence_score} weight="20%" />
                <ScoreBar label="Digital" value={s.digital_presence_score} weight="10%" />
                <ScoreBar label="Contact" value={s.contactability_score} weight="5%" />
              </div>

              <ul className="space-y-1 text-xs text-zinc-500 dark:text-zinc-400">
                {s.notes.map((note, i) => (
                  <li key={i}>· {note}</li>
                ))}
              </ul>

              {lead.evidence.length > 0 && (
                <div>
                  <SectionLabel>All supporting reviews</SectionLabel>
                  <ul className="space-y-3">
                    {lead.evidence.map((ev, i) => (
                      <li
                        key={i}
                        className="border-l-2 border-zinc-200 pl-3 dark:border-zinc-700"
                      >
                        <p className="text-sm text-zinc-600 dark:text-zinc-300">
                          “{ev.review_text}”
                        </p>
                        <p className="mt-1 text-xs text-zinc-400 dark:text-zinc-500">
                          {ev.review_rating !== null && `${ev.review_rating}★ · `}
                          {ev.pain_category} · {ev.severity} ·{" "}
                          {Math.round(ev.confidence * 100)}% confidence
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      {/* --- Actions --- */}
      <div className="flex flex-wrap gap-2 border-t border-zinc-100 px-5 py-3 dark:border-zinc-800">
        {lead.google_maps_url && (
          <a
            href={lead.google_maps_url}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            View on Maps
          </a>
        )}
        {lead.website && (
          <a
            href={lead.website}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Visit website
          </a>
        )}
      </div>
    </article>
  );
}
