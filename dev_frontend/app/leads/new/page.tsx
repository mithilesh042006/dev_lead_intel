"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ApiError, createManualLead, manualLeadOptions } from "@/lib/api";
import type { ManualLeadBody, ManualLeadOptions, Priority } from "@/lib/types";

const FIELD =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 " +
  "outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 " +
  "disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 " +
  "dark:focus:border-zinc-400 dark:focus:ring-zinc-100/10";

const LABEL = "mb-1.5 block text-sm font-medium text-zinc-700 dark:text-zinc-300";

const EMPTY: ManualLeadBody = {
  company_name: "",
  category: "",
  city: "",
  address: "",
  phone: "",
  email: "",
  website: "",
  google_maps_url: "",
  rating: null,
  total_reviews: 0,
  pain_point: "",
  pain_category: "",
  pain_severity: "",
  business_impact: "",
  primary_opportunity: "",
  technology_signals: "",
  sales_pitch: "",
  priority: "WARM",
};

function Card({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-950">
      <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{title}</h2>
      {description && (
        <p className="mt-0.5 mb-4 text-xs text-zinc-500 dark:text-zinc-400">
          {description}
        </p>
      )}
      <div className={description ? "" : "mt-4"}>{children}</div>
    </section>
  );
}

export default function NewLeadPage() {
  const router = useRouter();
  const [form, setForm] = useState<ManualLeadBody>(EMPTY);
  const [options, setOptions] = useState<ManualLeadOptions | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Vocabularies come from the API so the form can never offer a value the
  // backend rejects.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await manualLeadOptions();
        if (!cancelled) setOptions(result);
      } catch {
        /* the selects fall back to their own defaults below */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function set<K extends keyof ManualLeadBody>(key: K, value: ManualLeadBody[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const saved = await createManualLead(form);
      router.push(`/leads/${saved.lead_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this lead.");
      setSaving(false);
    }
  }

  const painCategories = options?.pain_categories ?? [];
  const severities = options?.severities ?? ["high", "medium", "low"];
  const priorities: Priority[] = options?.priorities ?? ["HOT", "WARM", "COLD", "LOW"];

  return (
    <div className="min-h-full bg-zinc-50 dark:bg-black">
      <main className="mx-auto w-full max-w-4xl px-4 py-6 sm:px-6 sm:py-8">
        <Link
          href="/leads"
          className="text-sm text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          ← Saved leads
        </Link>

        <header className="mb-5 mt-3">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50 sm:text-3xl">
            Add a lead manually
          </h1>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            For a business the search did not find — a referral, a trade fair,
            a walk-in. Only the company name is required; fill in the rest as
            you learn it.
          </p>
        </header>

        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-200">
            {error}
          </div>
        )}

        <form onSubmit={submit} className="space-y-6">
          <Card title="Business">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className={LABEL} htmlFor="company_name">
                  Company name <span className="text-red-500">*</span>
                </label>
                <input
                  id="company_name"
                  className={FIELD}
                  value={form.company_name}
                  onChange={(e) => set("company_name", e.target.value)}
                  required
                  maxLength={300}
                  disabled={saving}
                  autoFocus
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="category">
                  Category
                </label>
                <input
                  id="category"
                  className={FIELD}
                  placeholder="Clothing store"
                  value={form.category}
                  onChange={(e) => set("category", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="city">
                  City
                </label>
                <input
                  id="city"
                  className={FIELD}
                  placeholder="Chennai"
                  value={form.city}
                  onChange={(e) => set("city", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div className="sm:col-span-2">
                <label className={LABEL} htmlFor="address">
                  Address
                </label>
                <input
                  id="address"
                  className={FIELD}
                  value={form.address}
                  onChange={(e) => set("address", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="rating">
                  Rating (0–5)
                </label>
                <input
                  id="rating"
                  type="number"
                  step={0.1}
                  min={0}
                  max={5}
                  className={FIELD}
                  value={form.rating ?? ""}
                  onChange={(e) =>
                    set("rating", e.target.value === "" ? null : Number(e.target.value))
                  }
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="total_reviews">
                  Total reviews
                </label>
                <input
                  id="total_reviews"
                  type="number"
                  min={0}
                  className={FIELD}
                  value={form.total_reviews}
                  onChange={(e) => set("total_reviews", Number(e.target.value) || 0)}
                  disabled={saving}
                />
              </div>
            </div>
          </Card>

          <Card title="Contact">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={LABEL} htmlFor="phone">
                  Phone
                </label>
                <input
                  id="phone"
                  className={FIELD}
                  placeholder="+91…"
                  value={form.phone}
                  onChange={(e) => set("phone", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="email">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  className={FIELD}
                  value={form.email}
                  onChange={(e) => set("email", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="website">
                  Website
                </label>
                <input
                  id="website"
                  className={FIELD}
                  placeholder="https://…"
                  value={form.website}
                  onChange={(e) => set("website", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="google_maps_url">
                  Google Maps URL
                </label>
                <input
                  id="google_maps_url"
                  className={FIELD}
                  value={form.google_maps_url}
                  onChange={(e) => set("google_maps_url", e.target.value)}
                  disabled={saving}
                />
              </div>
            </div>
          </Card>

          <Card
            title="What they struggle with"
            description="The fact — what you observed or were told, in their words where possible."
          >
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className={LABEL} htmlFor="pain_point">
                  Pain point
                </label>
                <textarea
                  id="pain_point"
                  rows={3}
                  className={FIELD}
                  placeholder="Owner says stock counts never match the shop floor…"
                  value={form.pain_point}
                  onChange={(e) => set("pain_point", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="pain_category">
                  Pain category
                </label>
                <select
                  id="pain_category"
                  className={FIELD}
                  value={form.pain_category}
                  onChange={(e) => set("pain_category", e.target.value)}
                  disabled={saving}
                >
                  <option value="">—</option>
                  {painCategories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className={LABEL} htmlFor="pain_severity">
                  Severity
                </label>
                <select
                  id="pain_severity"
                  className={FIELD}
                  value={form.pain_severity}
                  onChange={(e) => set("pain_severity", e.target.value)}
                  disabled={saving}
                >
                  <option value="">—</option>
                  {severities.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              <div className="sm:col-span-2">
                <label className={LABEL} htmlFor="business_impact">
                  Business impact
                </label>
                <input
                  id="business_impact"
                  className={FIELD}
                  placeholder="Overselling and manual recounts every week"
                  value={form.business_impact}
                  onChange={(e) => set("business_impact", e.target.value)}
                  disabled={saving}
                />
              </div>
            </div>
          </Card>

          <Card
            title="What you would sell them"
            description="Your recommendation — kept separate from the fact above."
          >
            <div className="space-y-4">
              <div>
                <label className={LABEL} htmlFor="primary_opportunity">
                  Software opportunity
                </label>
                <input
                  id="primary_opportunity"
                  className={FIELD}
                  placeholder="Inventory management with barcode stock take"
                  value={form.primary_opportunity}
                  onChange={(e) => set("primary_opportunity", e.target.value)}
                  disabled={saving}
                />
              </div>

              <div>
                <label className={LABEL} htmlFor="technology_signals">
                  Technology they already use
                </label>
                <input
                  id="technology_signals"
                  className={FIELD}
                  placeholder="WordPress, WhatsApp, Razorpay"
                  value={form.technology_signals}
                  onChange={(e) => set("technology_signals", e.target.value)}
                  disabled={saving}
                />
                <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">
                  Comma-separated.
                </p>
              </div>

              <div>
                <label className={LABEL} htmlFor="sales_pitch">
                  Notes / opening
                </label>
                <textarea
                  id="sales_pitch"
                  rows={4}
                  className={FIELD}
                  placeholder="Met at the trade fair; asked us to call in October."
                  value={form.sales_pitch}
                  onChange={(e) => set("sales_pitch", e.target.value)}
                  disabled={saving}
                />
              </div>
            </div>
          </Card>

          <Card
            title="Priority"
            description="Set by hand. A manual lead has no review evidence to score, so this is recorded as your judgement rather than a computed number."
          >
            <div className="flex flex-wrap gap-2">
              {priorities.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => set("priority", p)}
                  disabled={saving}
                  aria-pressed={form.priority === p}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${
                    form.priority === p
                      ? "border-zinc-900 bg-zinc-900 text-white dark:border-zinc-100 dark:bg-zinc-100 dark:text-zinc-900"
                      : "border-zinc-200 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </Card>

          <div className="flex justify-end gap-2">
            <Link
              href="/leads"
              className="rounded-lg border border-zinc-200 px-4 py-2 text-sm font-medium text-zinc-600 transition hover:bg-white dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-900"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={saving || !form.company_name.trim()}
              className="rounded-lg bg-zinc-900 px-6 py-2 text-sm font-semibold text-white transition
                         hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40
                         dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
            >
              {saving ? "Saving…" : "Save lead"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
