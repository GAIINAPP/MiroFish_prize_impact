# stock_seed — Future price-impact prediction (MiroFish-powered)

Our layer on top of the vendored **MiroFish** engine (`../backend`, `../frontend`).
MiroFish is a multi-agent "swarm intelligence" prediction engine: feed it **seed
materials** + a natural-language **prediction requirement**, it builds a GraphRAG,
spins up a population of agents (OASIS), simulates their social evolution, and
returns a prediction report.

**Our goal:** for a given stock, assemble *seed materials* from **price history +
related news** (from the shared Postgres DB), drive MiroFish with a price-impact
`simulation_requirement`, and return a **future price-impact prediction**.

## Data flow

```
symbol, horizon
      │
      ▼
 db.py          ── read price history + related news from Postgres
      │
      ▼
 seed_builder.py ── render seed files:
      │             • <SYMBOL>_market_report.md  (price action, trend, key stats)
      │             • <SYMBOL>_news_digest.md     (related headlines + summaries)
      ▼
 mirofish_client.py ── drive the MiroFish Flask API (:5001):
      │   1. POST /api/graph/ontology/generate  (multipart: files[], simulation_requirement)
      │   2. POST /api/graph/build               (build GraphRAG)
      │   3. POST /api/simulation/...            (run OASIS simulation)
      │   4. POST /api/report/generate           (generate prediction report)
      ▼
 orchestrator.py ── glue: symbol → seeds → pipeline → PricePrediction
      │
      ▼
 api.py (FastAPI) ── POST /predict {symbol, horizon_days} → prediction report
```

The `simulation_requirement` is templated, e.g.:
> "Predict the likely price impact and direction of **{SYMBOL}** over the next
> **{N}** trading days given its recent price action and the related news below.
> Estimate direction (up/down/flat), a rough magnitude band, key drivers, and
> confidence."

## Architecture

- **MiroFish engine** runs as its own process (its Flask backend on `:5001`,
  optional Next frontend on `:3000`) — `../backend`, started via `../backend/run.py`
  or `../docker-compose.yml`. We treat it as a black-box HTTP API.
- **`stock_seed`** (this package, FastAPI) is the thin orchestrator: pulls our
  data, builds seeds, calls MiroFish, returns predictions. Matches the other
  `services/*` conventions (FastAPI + Pydantic + uvicorn).

## Prerequisites / decisions (need input)

1. **LLM** — MiroFish uses an OpenAI-SDK-format endpoint (`LLM_API_KEY`,
   `LLM_BASE_URL`, `LLM_MODEL_NAME`). Options: point it at **Gemini's
   OpenAI-compat endpoint** (we already have `GEMINI_API_KEY`), or the Qwen
   endpoint MiroFish recommends. → TBD.
2. **Zep** — MiroFish needs `ZEP_API_KEY` (getzep.com) for graph memory.
   → do we have/want a Zep account? MiroFish won't run without it.
3. **DB tables** — exact tables/columns for **price history** and **related
   news** (we know `akshay.stock_master` for the master, and the news table the
   frontend `/api/news` reads). → confirm the price-history + news schema so
   `db.py` queries are real.
4. **Cost** — MiroFish simulations are LLM-heavy (README warns to start with
   <40 rounds). We'll expose `sim_rounds`/agent-count knobs and default low.
5. **Git** — `services/price_impact` currently carries MiroFish's `.git`
   (shallow clone). Decide: keep as upstream-trackable vendored engine, or
   re-init as our own service repo. → TBD.

## Status

Scaffold only. `mirofish_client.py` is written to the real API contract above;
`db.py` / `seed_builder.py` / `orchestrator.py` are interfaces with TODOs
pending the decisions above.
