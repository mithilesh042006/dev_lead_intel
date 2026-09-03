# AI Lead Intelligence — Backend (Phase 1 MVP)

Implements the Phase 1 pipeline from
[`AI_Lead_Intelligence_Sales_Prospecting_Platform.md`](../AI_Lead_Intelligence_Sales_Prospecting_Platform.md):

```
Input → Apify → businesses → reviews → pre-filter → LLM → website+email
      → opportunity → lead score → cold-call pitch → CSV
```

No API server and no UI yet — that is deliberate (§42). The first thing to
prove is that five real leads are useful to the sales team.

## Setup

```bash
cd dev_backend
venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env      # then fill in APIFY_API_TOKEN and your LLM key
```

## Run

```bash
# Offline — full pipeline on sample data, zero Apify credits spent
venv/Scripts/python.exe -u scripts/run_pipeline.py --dry-run

# Live
venv/Scripts/python.exe -u scripts/run_pipeline.py \
    --location "Chennai" \
    --category "Clothing Stores" \
    --min-rating 3.0 --max-rating 4.0 \
    --min-reviews 20 --limit 5
```

Use `-u` (unbuffered) so progress appears as it happens rather than at the end.

Output lands in `data/out/`:

| File | Grain |
|---|---|
| `leads_<stamp>.csv` | One row per lead — the §20 schema |
| `leads_<stamp>_evidence.csv` | One row per analysed review — every pain point, kept |

The second file exists because §20's one-row-per-business grain would otherwise
discard the supporting evidence that §12 requires be preserved.

## Cost control

The disk cache in `data/cache/` is the main defence for the Apify free tier
($5/month). Re-running the same search costs **zero credits** — only genuinely
new searches hit the network. LLM responses are cached the same way, keyed by
model + place + review text, so tuning scoring weights or the CSV layout is free.

`--no-cache` bypasses it. Delete `data/cache/` to force a full refresh.

### Measured costs

| Item | Actual |
|---|---|
| Apify: 10 Chennai places × 20 reviews | **$0.16** per run |
| Apify free tier | $5/month → **~30 fresh searches** |
| OpenAI `gpt-5.4-mini` | pay-per-token, no daily cap |
| Gemini free tier | 20 requests/day, per model |

This pipeline spends roughly `candidates + 2 × leads_returned` LLM requests — a
5-candidate / 5-lead run measured **13 calls**.

On Gemini's free tier that is most of one day's quota, which is why the default
is now OpenAI. If you switch back to Gemini, note the cap is per model, so
`gemini-3.5-flash` and `gemini-3.6-flash` each get their own 20/day.

Opportunity detection and pitch generation run only for the leads actually
returned, not for every candidate, which is why a wide candidate pool is cheap.

If the quota runs out mid-run the job does not fail — leads, scores and
evidence are complete, and the run is marked `partial` with the missing pitches
named in the warnings.

### Recovering a paid-for Apify run

If a run succeeds on Apify but the pipeline crashes afterwards, the data is
already paid for. Pull it into the cache instead of re-running:

```bash
venv/Scripts/python.exe scripts/seed_cache_from_run.py <run_id> \
    --category "Clothing Stores" --location "Chennai"
```

### Switching LLM provider

`LLM_PROVIDER=auto` picks the backend from the model name — `gpt*`/`o*` go to
OpenAI, anything else to Gemini — so changing provider is one line in `.env`:

```env
LLM_MODEL=gpt-5.4-mini        # OpenAI  (default)
LLM_MODEL=gemini-3.6-flash    # Gemini
```

Set `LLM_PROVIDER` explicitly to `openai` or `gemini` to override the guess.
Backends live in `app/services/llm_backends.py`; the prompts, caching and
evidence-binding above them are provider-agnostic.

Two things to know:

- **Switching models invalidates the LLM cache** (the model is part of the cache
  key), so analyses re-run. Apify credits are untouched.
- Some newer OpenAI models reject a custom `temperature`. The backend detects
  this on first use and retries with the model's default rather than failing.

### Burn-rate knobs in `.env`

| Variable | Default | Effect |
|---|---|---|
| `MAX_PLACES_PER_SEARCH` | 10 | Places scraped per run |
| `MAX_REVIEWS_PER_PLACE` | 20 | **The main cost driver** |
| `REVIEWS_SORT` | `lowestRanking` | Fetches negative reviews first, so fewer reviews are needed to find pain |
| `MAX_LLM_REVIEWS_PER_BUSINESS` | 12 | Ceiling on reviews sent to the LLM |

## Layout

```
app/
  config.py                  §31 settings, all secrets from .env
  models.py                  §28 domain models
  pipeline.py                §25 orchestration
  providers/
    base.py                  §5.2 MapsProvider ABC
    apify_provider.py        §5.2 Apify implementation
    cache.py                 §34.4 disk cache
  services/
    filtering.py             §6  business filter + dedup
    review_filter.py         §10 keyword pre-filter (free stage)
    llm_service.py           §7/§11/§18/§19 structured LLM calls
    website_service.py       §13/§14 crawl + tech detection
    scoring_service.py       §16/§29 lead scoring rubric
    export_service.py        §20 CSV
  utils/
    text.py                  §34.5 normalisation for dedup
    validators.py            §15 email extraction + MX validation
prompts/                     §32 one file per task
scripts/run_pipeline.py      CLI
scripts/sample_data.py       offline fixtures for --dry-run
```

## Filtering behaviour

§6's filters assume the scraper returns a broad spread of ratings. It does not —
Google Maps surfaces prominent, well-rated businesses first. Every business
returned for "Clothing Stores" in Chennai rated **4.4-5.0**, so a 3.0-4.2 band
matched nothing and the search returned zero leads.

Filtering therefore runs in passes. If the strict filter yields fewer candidates
than requested, rules are dropped one at a time, in this order:

1. rating range
2. minimum review count
3. category match
4. contactability (phone or website)

It stops as soon as enough candidates survive, so the least useful rule is the
first to go and contactability is the last. `permanently_closed` and dedup are
never relaxed.

The rating preference is not lost — it still shapes `business_potential_score`,
which peaks at 3.5 stars. A relaxed 4.9-star business is kept but ranks below a
3.5-star one, and a business whose reviews show no software pain scores in the
teens regardless of rating. Every relaxation is reported in the job warnings.

Pass `strict_filters: true` to get the literal §6 behaviour and accept empty
results.

## Leads with no complaints

A business whose reviews contain no software pain point is still returned, and
still gets an opportunity and a pitch — built from observed capability gaps
(no website, no online payment, no booking system) rather than from customer
feedback.

The distinction is kept explicit, because it matters to whoever makes the call:

| | Pain-based lead | Gap-based lead |
|---|---|---|
| Source | A quoted customer review | Missing capability on their site |
| `pain_point` | Populated | Empty |
| `sales_priority` | Can be `high` | Capped at `medium` |
| Typical score | 60-90 | Under 30 |

The prompts forbid implying anyone complained when no complaint exists, and an
unreachable website yields "capabilities unknown" rather than "they have
nothing" — §12's rule against inventing a problem applies to gaps too.

## Scoring rubric

The spec gives §29's weights but not how each 0–100 subscore is computed. This
implementation defines them in `app/services/scoring_service.py`:

| Subscore | Weight | Derived from |
|---|---:|---|
| Software pain | 40% | 70% worst confirmed problem (severity × confidence) + 30% breadth across distinct pain categories |
| Business potential | 25% | 60% review volume (log scale, saturating at 500) + 40% rating fit (peak at 3.5) |
| Review evidence | 20% | 40% count of reviews supporting the top category + 40% mean confidence + 20% recency |
| Digital presence | 10% | Website 40, e-commerce 20, payments 15, ordering 10, booking 10, WhatsApp 5, social 5, analytics 5 |
| Contactability | 5% | Phone 50, email 35, website 15 |

Every subscore emits a plain-English note, shown in the CLI and available on
`lead.scores.notes`. A rep who cannot see why a lead scored 84 will not trust it.

Verified against the spec's own worked example (§16/§29): ABC Fashion scores
**83 / HOT**.

## Design rules honoured

- **§12 evidence-based.** An LLM verdict is bound to the review that produced
  it. If the model returns a review index that does not exist, the verdict is
  dropped rather than kept without evidence.
- **§33 fact / interpretation / recommendation** are separated in both the CLI
  output and the CSV columns.
- **§15 no fabricated emails.** Every address returned was literally present on
  a page that was fetched. Nothing is guessed from the domain.
- **§35 partial failure.** One dead website, one unparseable business or one
  failed pitch never kills the job; the run is marked `partial` and warnings are
  listed. A fatal LLM error (bad key, retired model) stops early instead of
  repeating the same failure for every candidate.
- **§36 minimal personal data.** Reviewer names and profile data are not
  requested from the scraper.

## API server (Phase 2)

```bash
venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

Interactive docs at <http://127.0.0.1:8000/docs>.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Config check — reports whether keys exist, never their values |
| POST | `/api/search` | Queue a search; returns `{job_id}` immediately (§27) |
| GET | `/api/jobs` | Recent jobs |
| GET | `/api/jobs/{job_id}` | Status, stage, progress %, warnings |
| POST | `/api/search/{job_id}/cancel` | Cooperative cancellation |
| GET | `/api/leads?job_id=` | Full leads with scores and evidence |
| GET | `/api/leads/{lead_id}?job_id=` | One lead |
| GET | `/api/leads/{lead_id}/reviews?job_id=` | Every review collected |
| GET | `/api/leads/{lead_id}/analysis?job_id=` | §33 fact / interpretation / recommendation, split |
| GET | `/api/export/csv?job_id=&kind=` | `leads` or `evidence` CSV download |

Jobs run on a 2-worker thread pool in [job_store.py](app/services/job_store.py)
rather than Celery — §24 keeps Redis out of the MVP, and this needs no extra
services. Swapping in Celery later means replacing `submit()`; the HTTP contract
and the frontend stay unchanged.

Cancellation is cooperative: `JobCancelled` derives from `BaseException`
specifically so the pipeline's `except Exception` (which exists to honour §35)
cannot swallow it.

## Saved sessions (§28)

Postgres (Neon) stores searches the user chooses to keep. **Saving is explicit** —
a search reaches the database only when Save is pressed. Runs are cheap to
repeat thanks to the disk cache, so auto-saving every search would fill the
table with noise nobody asked to keep.

| Table | Holds | §28 mapping |
|---|---|---|
| `search_sessions` | Search parameters and run outcome | `jobs` + lead rollup |
| `saved_leads` | One row per returned lead | `businesses` + `leads` |
| `saved_evidence` | One row per software-related review | `reviews` + `review_analysis` |

A session is a **snapshot**, not a live join. Re-running the same search later
must not silently rewrite what a rep already saved and acted on — ratings move,
reviews get deleted, and a saved session records what was true when it was saved.

Deleting a session cascades to its leads and evidence.

`DATABASE_URL` is optional: leave it empty and the pipeline runs exactly as
before, still writing CSV, with only the save feature disabled. A database that
is unreachable at boot logs the failure and disables saving rather than stopping
the API from serving searches — `GET /api/health` reports `database_ready`.

## Not built yet

- In-flight jobs still live in memory, so restarting the server loses unsaved
  job history. Saved sessions and CSVs on disk survive.
- Authentication (§37) — the API is unauthenticated. Do not expose it publicly.
- `GooglePlacesProvider` — the abstraction is in place, but note the Places API
  caps reviews at 5 per place and its terms restrict storing review content,
  which is why Apify carries the review workload.

## Before commercial use

Review §36. Scraping Google Maps review content via a third-party actor sits
against Google's terms, and the Places API restricts caching review text. Decide
whether to store full review text (current behaviour) or only derived pain
points plus short quotes before this goes near production.
