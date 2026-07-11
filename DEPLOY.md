# Deployment runbook — MiroFish + stock_seed (price-impact)

Two containers run together (root `docker-compose.yml`):

| Service      | Ports      | What it is                                              |
| ------------ | ---------- | ------------------------------------------------------- |
| `mirofish`   | 3000, 5001 | MiroFish frontend (sim/graphs UI) + Flask backend API   |
| `stock_seed` | 8090       | Our orchestrator — seeds a project from stock + news    |

The gaiin-frontend then calls `stock_seed` and embeds the MiroFish frontend so
users see the live simulation and graphs.

---

## A. Deploy on the VM (Docker Compose)

Run everything **on the VM** (the box that also hosts Postgres). One `.env` at
the repo root feeds both containers.

### 0. Prereqs (one-time)
```bash
docker --version && docker compose version   # need Docker + compose v2
# if missing: curl -fsSL https://get.docker.com | sh
```
Git access to the fork: an SSH deploy key for GAIINAPP, or HTTPS + a token.

### 1. Clone the fork
```bash
cd ~
git clone git@github.com:GAIINAPP/MiroFish_prize_impact.git
# or: git clone https://github.com/GAIINAPP/MiroFish_prize_impact.git
cd MiroFish_prize_impact
```

### 2. Create the `.env` (repo root, next to `docker-compose.yml`)
```bash
cp .env.example .env && nano .env
```
```
LLM_API_KEY=<your GEMINI_API_KEY>
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL_NAME=gemini-2.5-flash
ZEP_API_KEY=<zep key>
DATABASE_URL=postgres://rishabh:rishabh456@136.114.25.215:5432/mydb?sslmode=require
```
`.env` is gitignored — keys never get committed.

### 3. DB reachability from inside Docker
Postgres is on this same box, so the container connects to `136.114.25.215:5432`
(usually works via NAT hairpin). If `stock_seed` can't reach the DB, add to the
`stock_seed` service in `docker-compose.yml` and switch `DATABASE_URL` host to
`host.docker.internal`:
```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### 4. Bring it up
```bash
docker compose up -d --build      # pulls mirofish image, builds stock_seed
docker compose ps
docker compose logs -f mirofish stock_seed
```
MiroFish validates config on boot — it complains loudly if `ZEP_API_KEY` / LLM
config is wrong.

### 5. Verify
```bash
curl -s localhost:5001/health     # MiroFish backend
curl -s localhost:8090/health     # stock_seed
# browser: http://<VM_IP>:3000    # MiroFish frontend

# real seed → project:
curl -s -X POST localhost:8090/project -H 'Content-Type: application/json' \
  -d '{"symbol":"RELIANCE","horizon_days":5}'
# → returns project_id; open http://<VM_IP>:3000/process/<project_id>
```

### 6. Point gaiin-frontend at it
Set server-side env (read via `getServerEnv`) wherever gaiin-frontend runs:
```
STOCK_SEED_URL=http://<VM_IP or domain>:8090
MIROFISH_FRONTEND_URL=http://<VM_IP or domain>:3000
# optional: MIROFISH_PROJECT_URL_TEMPLATE={base}/process/{projectId}
```
Then the beta **"Price-impact sim"** button works end-to-end.

### 7. Expose properly (real users)
- Reverse proxy (Caddy/Nginx) in front so `:3000` / `:8090` sit behind your
  domain over HTTPS.
- **Iframe:** for the embed to render, MiroFish's frontend must allow framing
  from the gaiin domain — the proxy must NOT add `X-Frame-Options:
  DENY/SAMEORIGIN`; with CSP use `frame-ancestors <gaiin-domain>`. Fallback: the
  pane's "Open in new tab".

### 8. Updating
```bash
cd MiroFish_prize_impact && git pull && docker compose up -d --build
```

---

## B. Self-hosting Zep locally (no Zep Cloud dependency)

Optional — for running the memory layer entirely on the box (no external key /
per-call cost). Not implemented yet; use the Zep Cloud free tier to start.

**The facts:**
- MiroFish's `zep-cloud` SDK **does** accept a custom `base_url` (defaults to
  Zep Cloud's `/api/v2`) — see `backend/app/services/graph_builder.py`
  (`Zep(api_key=...)`).
- But there is **no drop-in self-hostable server** for Zep's current v3 Graph
  API. Zep's OSS engine is **Graphiti** (`getzep/graphiti`) — a temporal
  knowledge graph on **FalkorDB** (light, Redis-based) or Neo4j, with an LLM
  (Gemini supported).
- MiroFish uses Zep **only for its graph**: `graph.create`, `graph.set_ontology`
  (custom EntityModel/EdgeModel), `graph.add` / `graph.add_batch` (EpisodeData),
  `graph.search`, `graph.node`, `graph.edge`, `graph.episode`, `graph.delete`.
  Graphiti has direct equivalents (`add_episode`, `search`, node/edge retrieval,
  custom entity/edge types).

### Path A — port MiroFish's Zep layer to Graphiti (recommended)
Robust, fully local. Diverges our fork from upstream.
1. Add a **FalkorDB** service to `docker-compose.yml` (single container).
2. `pip` add `graphiti-core[falkordb]` to `backend/requirements.txt`; configure
   Graphiti's LLM/embedder to the same Gemini creds.
3. Write a `GraphitiGraphBuilder` mirroring `graph_builder.py`'s call sites (the
   ~10 graph ops + ontology above) against Graphiti's API; route
   `ontology_generator.py` / `zep_*` services through it.
4. Drop `ZEP_API_KEY`; point config at FalkorDB.

### Path B — Zep-compatible shim (keeps MiroFish untouched)
Run Graphiti behind a tiny FastAPI facade implementing just the `/api/v2/graph/*`
endpoints the SDK calls, then set the client's `base_url` to the local shim
(`Zep(api_key="local", base_url="http://zep-shim:PORT/api/v2")`). Zero MiroFish
diff, but you must match the SDK's request/response wire format per endpoint
(fiddlier / more brittle than A).

**Recommendation:** free Zep key now to prove the pipeline, then Path A for the
durable self-host.

---

## Notes / gotchas
- The Postgres host is internal infra — kept server-side in `stock_seed`; it must
  never surface in any client response.
- Sims are LLM-heavy; keep rounds/agents modest (MiroFish warns < 40 rounds).
- The `prepare` / `start` request bodies in `stock_seed/mirofish_client.py` are
  the only unverified part (the `/project` + embed flow doesn't touch them);
  confirm them from a live backend's responses when running `/predict`.
