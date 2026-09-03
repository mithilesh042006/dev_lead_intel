# AI Lead Intelligence — Frontend

Next.js 16 dashboard for the lead pipeline. Implements the two screens in §21 of
the [spec](../AI_Lead_Intelligence_Sales_Prospecting_Platform.md): a search form
and a ranked results view.

## Run

The backend must be running first:

```bash
# terminal 1
cd ../dev_backend
venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000

# terminal 2
npm run dev
```

Open <http://localhost:3000>.

## Configuration

`.env.local` holds one value:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

That is the only environment variable, and it is not a secret. **No API key ever
reaches the browser** (§37) — the Apify and Gemini credentials live server-side
in the FastAPI backend, and this app only ever talks to that backend.

## How it works

`POST /api/search` returns a `job_id` immediately; a search takes minutes, so the
request never stays open (§27). The page then polls `GET /api/jobs/{job_id}`
every 2s for progress, and fetches `GET /api/leads` once the job reaches a
terminal state.

No data-fetching library — a form, an interval, and `fetch` cover it. Adding SWR
or TanStack Query here would buy shared caching this app has no use for.

## Layout

```
app/
  layout.tsx               fonts, metadata, sidebar shell
  page.tsx                 search + polling + results + lead selection
  leads/page.tsx           saved leads
  globals.css              Tailwind v4 theme tokens
  components/
    Sidebar.tsx            persistent nav: Search / Saved leads
    SearchForm.tsx         §5.1 search inputs
    ProgressPanel.tsx      §27 job progress, warnings, cancel
    LeadCard.tsx           §21 results card, optionally selectable
    SaveLeadsBar.tsx       §28 select-and-save action
lib/
  api.ts                   typed client for the §26 endpoints
  types.ts                 mirrors app/schemas/api.py — keep in sync
```

## Design notes

**§33 is visible in the UI, not just the data.** Each card separates what the
customer actually said (the quoted review, with star rating and date) from the
AI's reading of it and from the recommendation. The confidence figure is
labelled as an interpretation rather than presented as fact.

**Cost is surfaced, not hidden.** "Places to scrape" is on the form with its
per-place cost, because that field is what spends Apify credits. Repeating a
search is free — the backend caches by search parameters.

**Partial results are shown as partial.** If the LLM quota runs out mid-run, the
leads and scores are still complete and are displayed, with the warning from the
backend shown above them. The run is not treated as a failure.

## Saving leads

Each result card carries a checkbox. Tick the leads worth calling, press **Save
leads**, and only those rows reach Postgres — a search is not saved wholesale.
Leads already in the database show a **Saved** badge, and re-saving one refreshes
its analysis rather than creating a duplicate.

## Not built yet

Lead status tracking, notes, and team sharing are Phase 3 (§38). There is no
auth — this assumes an internal, local deployment.
