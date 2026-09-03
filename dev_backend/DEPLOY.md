# Deploying the backend to Render

The service is defined in [`render.yaml`](render.yaml) at `rootDir: dev_backend`.

## 1. Push the repo

```bash
git add -A
git commit -m "Add Render deployment config"
git push origin main
```

`.env`, `venv/`, `data/cache/` and `data/out/` are gitignored — verify before
pushing that no secret is staged:

```bash
git status --porcelain | grep -i env    # should print nothing
```

## 2. Create the service

Render dashboard → **New → Blueprint** → pick this repo. It reads `render.yaml`
and creates a web service. Or create a Web Service manually with:

| Setting | Value |
|---|---|
| Root Directory | `dev_backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` |
| Health Check Path | `/api/health` |

## 3. Set the secrets

Four values are marked `sync: false` and **must** be set in the dashboard —
they are deliberately absent from git:

| Variable | Value |
|---|---|
| `APIFY_API_TOKEN` | Your Apify token |
| `OPENAI_API_KEY` | Your OpenAI key |
| `DATABASE_URL` | The Neon connection string |
| `CORS_ORIGINS` | Your deployed frontend origin, e.g. `https://your-app.vercel.app` |

`CORS_ORIGINS` is comma-separated and has no wildcard. Until it names the
frontend's real origin, the browser blocks every request — the API holds real
credentials, so `*` is not offered.

Everything else (`LLM_MODEL`, the cost knobs) is already in `render.yaml` and
can be edited there or overridden in the dashboard.

## 4. Verify

```bash
curl https://<your-service>.onrender.com/api/health
```

Expect `"status": "ok"` with `apify_configured`, `openai`/`gemini_configured`
and `database_ready` all true. `database_ready: false` means `DATABASE_URL` is
wrong or Neon is unreachable — searches still work, saving leads does not.

---

## Things that behave differently once deployed

### One worker, on purpose

Search jobs live in an in-process registry
([`app/services/job_store.py`](app/services/job_store.py)), not in Redis. With
two workers a job created in worker A returns 404 when the frontend polls it and
lands on worker B. **Do not raise `--workers`** without moving the job store to
Redis first (§27 Phase 3).

### The filesystem is ephemeral

Render gives a fresh disk on every deploy and restart. Two consequences:

- **`data/cache` is wiped**, so the Apify cache starts cold. A repeat search
  that costs nothing locally costs ~$0.016/place again after a deploy. This is
  the one that costs real money.
- **`data/out` is wiped.** Harmless: every CSV endpoint builds its file in
  memory, so exports work with that directory absent — verified by deleting it
  and re-exporting.

To keep the cache, uncomment the `disk:` block in `render.yaml` (needs a paid
instance type). On the free plan, accept the cold cache and keep
`MAX_PLACES_PER_SEARCH` low.

### The free plan sleeps

A free service spins down after ~15 minutes idle and takes ~50s to wake. Since
a search runs for minutes on a background thread, a spin-down mid-search kills
the job and the frontend's polling starts returning 404. For real use this needs
a paid instance; for demos, run a search while someone is watching.

Job history is in memory either way, so a restart loses jobs. Saved leads are in
Postgres and survive.

### There is no authentication

§37 asks for it and it does not exist. A public Render URL means anyone who
finds it can run searches that spend your Apify credits and OpenAI tokens, and
can read or delete saved leads. Before sharing the URL, add an API key check or
put the service behind Render's IP allowlist.

## Rolling back

Render keeps previous deploys — **Deploys → … → Redeploy** on the last good one.
Database schema changes are not versioned (no Alembic), so a rollback that
crosses a schema change needs the table changes undone by hand.
