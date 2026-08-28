"use client";

import { useState } from "react";
import type { SearchBody } from "@/lib/types";

interface Props {
  onSubmit: (body: SearchBody) => void;
  disabled: boolean;
}

const FIELD =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 " +
  "outline-none transition focus:border-zinc-900 focus:ring-2 focus:ring-zinc-900/10 " +
  "disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 " +
  "dark:focus:border-zinc-400 dark:focus:ring-zinc-100/10";

const LABEL =
  "mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500 dark:text-zinc-400";

export default function SearchForm({ onSubmit, disabled }: Props) {
  const [location, setLocation] = useState("Chennai");
  const [category, setCategory] = useState("Clothing Stores");
  const [minRating, setMinRating] = useState(3.0);
  const [maxRating, setMaxRating] = useState(5.0);
  const [minimumReviews, setMinimumReviews] = useState(20);
  const [limit, setLimit] = useState(5);
  const [maxPlaces, setMaxPlaces] = useState(10);
  const [strictFilters, setStrictFilters] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (maxRating < minRating) {
      setError("Maximum rating must be greater than or equal to minimum rating.");
      return;
    }
    setError(null);
    onSubmit({
      location: location.trim(),
      category: category.trim(),
      min_rating: minRating,
      max_rating: maxRating,
      minimum_reviews: minimumReviews,
      limit,
      max_places: maxPlaces,
      strict_filters: strictFilters,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
    >
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="sm:col-span-1">
          <label className={LABEL} htmlFor="location">
            Location
          </label>
          <input
            id="location"
            className={FIELD}
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Chennai"
            required
            minLength={2}
            disabled={disabled}
          />
        </div>

        <div className="sm:col-span-1">
          <label className={LABEL} htmlFor="category">
            Category
          </label>
          <input
            id="category"
            className={FIELD}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Clothing Stores"
            required
            minLength={2}
            disabled={disabled}
          />
        </div>

        <div>
          <label className={LABEL}>Rating range</label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              className={FIELD}
              value={minRating}
              onChange={(e) => setMinRating(Number(e.target.value))}
              step={0.1}
              min={0}
              max={5}
              disabled={disabled}
              aria-label="Minimum rating"
            />
            <span className="text-sm text-zinc-400">to</span>
            <input
              type="number"
              className={FIELD}
              value={maxRating}
              onChange={(e) => setMaxRating(Number(e.target.value))}
              step={0.1}
              min={0}
              max={5}
              disabled={disabled}
              aria-label="Maximum rating"
            />
          </div>
        </div>

        <div>
          <label className={LABEL} htmlFor="minimum-reviews">
            Minimum reviews
          </label>
          <input
            id="minimum-reviews"
            type="number"
            className={FIELD}
            value={minimumReviews}
            onChange={(e) => setMinimumReviews(Number(e.target.value))}
            min={0}
            disabled={disabled}
          />
        </div>

        <div>
          <label className={LABEL} htmlFor="limit">
            Leads to return
          </label>
          <input
            id="limit"
            type="number"
            className={FIELD}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            min={1}
            max={25}
            disabled={disabled}
          />
        </div>

        <div>
          <label className={LABEL} htmlFor="max-places">
            Places to scrape
          </label>
          <input
            id="max-places"
            type="number"
            className={FIELD}
            value={maxPlaces}
            onChange={(e) => setMaxPlaces(Number(e.target.value))}
            min={1}
            max={50}
            disabled={disabled}
          />
          {/* This is the knob that spends Apify credits — surfaced, not hidden. */}
          <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">
            Drives cost: ~$0.016 per place. Repeating a search is free (cached).
          </p>
        </div>
      </div>

      <label className="mt-5 flex items-start gap-2.5">
        <input
          type="checkbox"
          checked={strictFilters}
          onChange={(e) => setStrictFilters(e.target.checked)}
          disabled={disabled}
          className="mt-0.5 h-4 w-4 rounded border-zinc-300 dark:border-zinc-700"
        />
        <span className="text-xs text-zinc-500 dark:text-zinc-400">
          <span className="font-medium text-zinc-700 dark:text-zinc-300">
            Strict filters
          </span>
          {" — return nothing rather than relax the rating range. Off by default: "}
          {"Google surfaces high-rated businesses first, so a narrow band often "}
          {"matches nothing. Scoring still prefers ~3.5 stars either way."}
        </span>
      </label>

      {error && (
        <p className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}

      <button
        type="submit"
        disabled={disabled}
        className="mt-6 w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-semibold text-white
                   transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50
                   dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300 sm:w-auto sm:px-8"
      >
        {disabled ? "Searching…" : "Find Leads"}
      </button>
    </form>
  );
}
