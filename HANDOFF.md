# Crime Analyser — Dev Handoff

Last updated: 2026-07-23. Everything below marked ✅ has been personally
run and verified against live services (Postgres, Neo4j, a free LLM via
OpenRouter) — not just written and assumed correct. Items marked 🟡 are
built but not fully tested. Items marked ❌ are not started.

## Quick start

```bash
# 1. Clone and enter repo
cd crime-analysier

# 2. Python env
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Start backing services
docker run --name pg-crime -e POSTGRES_PASSWORD=crimepass123 -p 5432:5432 -d postgres:16
docker run --name neo4j-crime -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/crimepass123 -d neo4j:5

# 4. Set your own free LLM key (see "LLM provider" below)
export OPENROUTER_API_KEY="your-key"

# 5. Load data (one-time, or after editing seed_data.py)
cd packages/ml-models/hotspot && python3 seed_data.py && cd ../../..
# then copy records.json into every module folder that needs it (see below)

# 6. Run the API
cd packages/ml-models/api
uvicorn main:app --reload --port 8000
# -> http://127.0.0.1:8000/docs
```

## What's verified working (✅)

| Module | Path | What it does |
|---|---|---|
| Seed data | `ml-models/hotspot/seed_data.py` | Faker-generated FIR records, 883 rows, **fixed seed (42)** — deterministic, do not remove the seed |
| RAG chatbot | `ml-models/rag/rag_pipeline.py` | Chunk → embed → in-memory retrieval → LLM answer with enforced citations |
| Text-to-SQL | `ml-models/text_to_sql/text_to_sql.py` | NL question → generated SQL → executed against Postgres → cited answer |
| Text-to-Cypher | `ml-models/text_to_cypher/text_to_cypher.py` | NL question → generated Cypher → executed against Neo4j |
| Hotspot detection | `ml-models/hotspot/hotspot_detection.py` | DBSCAN on lat/long, `eps=0.005` tuned for current dataset density |
| Trend forecasting | `ml-models/forecasting/trend_forecasting.py` | Seasonal decomposition + anomaly flagging on daily case counts |
| Risk flagging | `ml-models/risk_flagging/risk_flagging.py` | XGBoost + SHAP, outputs flag + plain-language reasons, never a raw score |
| RBAC | `ml-models/auth/rbac.py` | `viewer` can read; `reviewer`-only can action a review. Verified via role-header tests. |
| Audit logging | `ml-models/audit/audit_log.py` | Every query + review action logged to `audit.log` with timestamp, role, details |
| ETL: Postgres → Neo4j | `etl/postgres_to_neo4j.py` | Rebuilds graph from Postgres as source of truth. Verified: 883/883 synced. |
| ETL: Document embedder | `etl/embed_documents.py` | Chunks + embeds case notes → `embeddings.json`. Verified: 883/883 embedded. |
| API | `ml-models/api/main.py` | 6 live endpoints (below) |

### Live endpoints (all tested via curl / `/docs`)

- `POST /chat/query` — RAG chatbot
- `POST /query/sql` — Text-to-SQL
- `GET /analytics/hotspots` — requires `X-User-Role` header
- `GET /analytics/trends` — requires `X-User-Role` header
- `GET /analytics/risk-flags` — requires `X-User-Role: viewer` or `reviewer`
- `POST /analytics/risk-flags/review` — requires `X-User-Role: reviewer`

## Known issues / rough edges (be honest with the team about these)

1. **SHAP explanations are weakly differentiated.** In risk flagging, the
   top-factor "impact" value is nearly identical across most flagged
   individuals rather than varying meaningfully case-to-case. The
   underlying split is real (verified via tree dump), but the model likely
   needs more/better features or regularization tuning to produce more
   individualized explanations. Not blocking, but don't oversell this part.
2. **No pgvector** — `embed_documents.py` writes to a local JSON file
   instead, because pgvector isn't installed on the Postgres image used
   here. The record shape matches a pgvector table 1:1 for an easy swap
   later.
3. **RAG doesn't yet read from `etl/embeddings.json`.** `rag_pipeline.py`
   does its own in-memory embedding on every boot rather than reusing the
   ETL module's output. Wiring these together is a reasonable next step.
4. **No scheduled/background ETL.** `postgres_to_neo4j.py` is a manual
   script — there's no Celery, cron, or `/etl/run` trigger wired up
   despite what an earlier README draft implied. If a scheduled sync is
   needed, that has to be built.
5. **Text-to-SQL / Text-to-Cypher use a free LLM (`openai/gpt-oss-20b:free`
   via OpenRouter)** which occasionally leaks internal reasoning tokens
   into raw output. There's a regex-based cleanup layer in both generators
   to strip this, tested and currently working, but it's a known fragility
   point if the model's output format shifts.
6. **Single flat schema, not the full relational model.** Current
   `fir_records` table has one row per case with a single `accused_name`
   string. The plan's fuller schema (separate Victim, Complainant, Unit,
   Court entities, multi-accused cases) is not implemented.

## Not started (❌)

- **NER** (10 entity types) — no extraction pipeline exists
- **Intent router** — `ml-models/router/router.py` exists in the repo but
  has not been tested or verified by this handoff; check it before relying
  on it
- **Kannada / multilingual layer** — no ASR, translation, or TTS pipeline;
  `embed_documents.py` is English-only (`all-MiniLM-L6-v2`)
- **Real `CaseMaster` schema depth** — see known issue #6 above

## LLM provider

Using **OpenRouter** (openrouter.ai) with the free model
`openai/gpt-oss-20b:free` — no billing required, but subject to
OpenRouter's free-tier rate limits (worth checking their site for current
limits) and to free-model availability changing over time. If this model
stops being free, check `https://openrouter.ai/api/v1/models` for current
`:free` options and swap the model string in `rag_pipeline.py`,
`text_to_sql.py`, and `text_to_cypher.py`.

## Data consistency — important

All modules currently read from **copies** of the same `records.json`
(883 rows, seeded, deterministic). If you regenerate seed data, you
**must** re-copy `records.json` into every module folder that uses it,
and re-run `postgres_to_neo4j.py` / `embed_documents.py` / the SQL and
Cypher module loaders to refresh the databases. A cleaner fix — using one
shared data path instead of per-folder copies — would remove this
footgun entirely and is worth doing before this goes further.
