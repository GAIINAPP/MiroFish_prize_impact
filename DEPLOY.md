# Deploying MiroFish + stock_seed (price-impact)

Two things run together (root `docker-compose.yml`):

| Service      | Ports        | What it is                                             |
| ------------ | ------------ | ------------------------------------------------------ |
| `mirofish`   | 3000, 5001   | MiroFish frontend (sim/graphs UI) + Flask backend API  |
| `stock_seed` | 8090         | Our orchestrator — seeds a project from stock+news     |

## 1. Configure `.env`
```bash
cp .env.example .env
# fill in:
#   LLM_API_KEY      = <GEMINI_API_KEY>     (Gemini, OpenAI-compat endpoint — already templated)
#   ZEP_API_KEY      = <your zep key>       (REQUIRED — MiroFish won't boot without it)
#   DATABASE_URL     = postgres://…?sslmode=require   (shared read-only DB)
```
LLM is preset to Gemini: `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`,
`LLM_MODEL_NAME=gemini-2.5-flash`.

## 2. Run
```bash
docker compose up -d          # pulls mirofish image, builds stock_seed
docker compose logs -f mirofish stock_seed
```
- MiroFish frontend → http://HOST:3000
- MiroFish backend  → http://HOST:5001/health
- stock_seed        → http://HOST:8090/health

## 3. Point the gaiin-frontend at it
Set these server-side env vars for gaiin-frontend (read via `getServerEnv`):
```
STOCK_SEED_URL=http://HOST:8090
MIROFISH_FRONTEND_URL=http://HOST:3000
# optional override; default is {base}/process/{projectId}
# MIROFISH_PROJECT_URL_TEMPLATE={base}/process/{projectId}
```
The frontend's `/api/price-impact` route calls `stock_seed /project` (server-side,
so the DB host never reaches the browser) and embeds `MIROFISH_FRONTEND_URL` at
`/process/<projectId>` in the beta workspace.

## User flow
Beta workspace → open a stock → **"Price-impact sim"** (header button) → pick a
horizon → **Run simulation**. `stock_seed` reads the stock's price history +
related news, builds seed files, creates a MiroFish project, and the pane embeds
MiroFish's `/process/:projectId` so the live graph-build → OASIS simulation →
report renders inline.

## Status
- ✅ **Data path validated** against the live DB — `stock_seed` builds a clean
  OHLC market report + news digest (with sentiment) from `akshay.stock_prices_daily`
  and `news.market_news`.
- ⏳ **Full simulation** needs `ZEP_API_KEY` + MiroFish booted with the Gemini
  LLM; the client's graph/sim/report **poll routes** (`mirofish_client.py`) still
  need verifying against a running backend.
- ⏳ **VM deploy** — Docker Compose is ready; drop it on the target box (same
  pattern as the other services) and expose 3000/8090 behind the domain.

## Notes
- The Postgres host is internal infra — kept server-side in `stock_seed`; never
  surfaces in any client response.
- Sims are LLM-heavy; keep rounds/agents modest (MiroFish warns < 40 rounds).
