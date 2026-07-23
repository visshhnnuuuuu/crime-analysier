# Crime Analyser — Dev Handoff

Last updated: 2026-07-23 (final submission pass). Everything below marked
✅ has been personally run and verified against live services (Postgres,
Neo4j, a free LLM via OpenRouter) — not just written and assumed correct.
Items marked ❌ are not started. This handoff reflects the state after a
full bug-fix and re-verification pass on submission day, including a
final smoke test across every endpoint.

## Summary for reviewers

11 of 13 planned phases are built and verified working. The two not
started — Kannada voice (ASR/TTS) and the full multi-entity relational
schema — were flagged as the two highest-effort items in the original
plan document from day one, and are scoped out here with clear reasons,
rough effort estimates, and suggested next steps rather than rushed or
faked. Every known issue below, including two found during today's final
testing pass, is documented honestly.

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

# 5. Load data (one-time, or after editing seed_data.py) -- ORDER MATTERS:
cd packages/ml-models/hotspot && python3 seed_data.py && cd ../../..
# copy records.json into every module folder that needs it (rag, forecasting,
# risk_flagging, text_to_sql -- text_to_cypher no longer needs its own copy,
# see "Neo4j sync" note below)
cd packages/ml-models/text_to_sql
python3 -c "from text_to_sql import setup_table, load_data; setup_table(); load_data('records.json')"
cd ../../../packages/etl
python3 postgres_to_neo4j.py   # Postgres must be loaded FIRST -- this reads from Postgres, not records.json
python3 embed_documents.py

# 6. Run the API
cd ../ml-models/api
uvicorn main:app --reload --port 8000
# -> http://127.0.0.1:8000/docs
```

**Important — data reload order**: `postgres_to_neo4j.py` is the single
source of truth for what's in Neo4j. It reads from Postgres, not
`records.json`. If you regenerate seed data, you must reload Postgres
*before* running the Neo4j sync, or you'll sync stale data. This bit us
once during today's fix pass — worth flagging clearly here.

## What's verified working (✅)

| Module | Path | What it does |
|---|---|---|
| Seed data | `ml-models/hotspot/seed_data.py` | Faker-generated FIR records, 883 rows, **fixed seed (42)**, deterministic. Fixed today: `date_filed` year and `fir_number` year now match (both derive from the same date — previously records were dated 2025 but numbered `.../2026`); repeat-offender name pools are guaranteed unique from each other and from one-off names, so case histories can't be silently merged by a name collision. |
| RAG chatbot | `ml-models/rag/rag_pipeline.py` | Chunk → embed → in-memory retrieval → LLM answer with enforced citations. Fixed today: strips leaked reasoning tokens from LLM output before citation-checking. **Verified in final smoke test**: returned a correctly-hedged, cited answer when no matching records existed. |
| Text-to-SQL | `ml-models/text_to_sql/text_to_sql.py` | NL question → generated SQL → executed against Postgres → cited answer. Fixed today: DB credentials now read from env vars (`PG_HOST`, `PG_PORT`, etc.) with local defaults; strips leaked reasoning tokens. **Verified in final smoke test**: correct SQL generated, correct count (67) returned for a real query. |
| Text-to-Cypher | `ml-models/text_to_cypher/text_to_cypher.py` | NL question → generated Cypher → executed against Neo4j. Changed today: no longer loads its own copy of the graph from `records.json` — delegates to `postgres_to_neo4j.py` so there's one authoritative write path into Neo4j instead of two scripts that could silently overwrite each other. **Verified in final smoke test**: correct Cypher generated, returned 32 accused persons linked to 3+ cases. |
| Hotspot detection | `ml-models/hotspot/hotspot_detection.py` | DBSCAN on lat/long, `eps=0.005` tuned for current dataset density. **Verified in final smoke test**: 3 clean clusters (521 / 305 / 40 cases), 17 noise points — no fragmentation, sensible output. |
| Trend forecasting | `ml-models/forecasting/trend_forecasting.py` | Seasonal decomposition + anomaly flagging on daily case counts. **Verified in final smoke test**: correctly flagged the seeded spike window (days 300–310 in `seed_data.py`) as anomalous — actual counts jumped to 9–10/day against an expected ~2–3/day baseline, exactly as designed. 14 anomalies detected total. |
| Risk flagging | `ml-models/risk_flagging/risk_flagging.py` | XGBoost + SHAP, outputs flag + plain-language reasons, never a raw score. Fixed today: `random_state=42` added so flags are reproducible across repeated calls on the same data — previously the model retrained fresh (with no fixed seed) on every API call, which is a bad property for something feeding a human-review workflow. **Verified in final smoke test**: 30 individuals flagged, each with 3 human-readable factors and a `reviewed: False` gate. See known issue #1 below re: SHAP differentiation. |
| RBAC | `ml-models/auth/rbac.py` | `viewer` can read; `reviewer`-only can action a review. Verified via role-header tests. |
| Audit logging | `ml-models/audit/audit_log.py` | Every query + review action logged to `audit.log` with timestamp, role, details |
| Intent router | `ml-models/router/router.py` | Classifies query as lookup/relationship/analytical, routes to sql/cypher/rag with confidence threshold. Fixed today: strips leaked reasoning tokens before parsing intent/confidence (previously this could silently fail over to a default low-confidence result without any visible error). |
| Kannada text layer | `ml-models/kannada/translate.py` | LLM-prompted translation (Kannada↔English) wired into all three backends (sql/cypher/rag) via `/query/kannada`. **Text only — no ASR or TTS, see "Not started" below.** Fixed today: added error handling (falls back to untranslated text with a warning flag instead of crashing the whole request on API failure), strips leaked reasoning tokens, strips common LLM wrapper artifacts (quotes, "Translation:" prefixes). **Known limitation found in final smoke test** — see known issue #12 below re: proper-noun mistranslation. |
| NER | `ml-models/ner/ner_extraction.py` | LLM-based entity extraction (10 types). Verified on 3 sample records — correct extraction, schema validated. |
| ETL: Postgres → Neo4j | `etl/postgres_to_neo4j.py` | Rebuilds graph from Postgres as source of truth — now the **single** write path for Neo4j (see Text-to-Cypher note above). Fixed today: delete scoped to `Case`/`Accused` labels only (previously `MATCH (n) DETACH DELETE n` would wipe the *entire* graph, including any future node types like Victim/Unit/Court the moment they're added); null-guard on `accused_name` (previously a null name could merge unrelated cases into one shared node); credentials moved to env vars; wrapped in error handling instead of raising raw exceptions on connection failure. |
| ETL: Document embedder | `etl/embed_documents.py` | Chunks + embeds case notes → `embeddings.json`. Verified: 883/883 embedded. |
| API | `ml-models/api/main.py` | 9 live endpoints (below) |

### Live endpoints (all tested via curl / `/docs` / smoke test)

- `POST /chat/query` — RAG chatbot
- `POST /query/sql` — Text-to-SQL
- `POST /query/cypher` — Text-to-Cypher
- `POST /query/kannada` — Kannada text translation + routing to sql/cypher/rag
- `POST /query/auto` — router auto-dispatch (intent classification → backend)
- `GET /analytics/hotspots` — requires `X-User-Role` header
- `GET /analytics/trends` — requires `X-User-Role` header
- `GET /analytics/risk-flags` — requires `X-User-Role: viewer` or `reviewer`
- `POST /analytics/risk-flags/review` — requires `X-User-Role: reviewer`
- `POST /etl/run` — requires `X-User-Role: reviewer`, re-syncs Neo4j + re-embeds

## Known issues / rough edges (be honest with the team about these)

1. **SHAP explanations are weakly differentiated — confirmed with real
   test data.** In today's final smoke test, `n_distinct_crime_types` had
   an identical impact value (`6.353392601013184`) across all 30 flagged
   individuals, while the other two features (`prior_case_count`,
   `avg_days_between_offenses`) showed `0.0` impact for every person. The
   underlying split is real (tree dump confirms it), but the model
   likely needs more/better features or regularization tuning to produce
   genuinely individualized explanations. Not blocking, but don't oversell
   this part in a demo.
2. **No pgvector** — `embed_documents.py` writes to a local JSON file
   instead, because pgvector isn't installed on the Postgres image used
   here. The record shape matches a pgvector table 1:1 for an easy swap
   later.
3. **RAG doesn't yet read from `etl/embeddings.json`.** `rag_pipeline.py`
   does its own in-memory embedding on every boot rather than reusing the
   ETL module's output. Wiring these together is a reasonable next step.
4. **No scheduled/background ETL.** `postgres_to_neo4j.py` and
   `embed_documents.py` are manual scripts — there's no Celery, cron, or
   scheduled trigger beyond the manual `/etl/run` endpoint. If a scheduled
   sync is needed, that has to be built.
5. **All LLM-calling modules use a free model
   (`openai/gpt-oss-20b:free` via OpenRouter)** which occasionally leaks
   internal reasoning tokens into raw output. As of today's fix pass, all
   modules (`translate.py`, `router.py`, `rag_pipeline.py`,
   `text_to_sql.py`, `text_to_cypher.py`, `ner_extraction.py`)
   consistently strip this (`raw.split("<|")[0]`) before parsing —
   previously this was inconsistent across modules. Still a fragility
   point if the model's output format shifts.
6. **Single flat schema, not the full relational model.** Current
   `fir_records` table has one row per case with a single `accused_name`
   string. See "Not started" below.
7. **NER is LLM-prompted, not a trained model.** `ner_extraction.py` uses
   the same free LLM to extract entities via prompting rather than a
   fine-tuned NER model. This works well on the tested samples but hasn't
   been validated at scale or against edge cases (multiple people in one
   note, ambiguous dates, etc.).
8. **NER not wired into the API** — no `/extract/entities` endpoint exists yet.
9. **Neo4j / Postgres reload ordering is a manual footgun.** If you
   regenerate seed data, Postgres must be reloaded *before*
   `postgres_to_neo4j.py` runs, or Neo4j will silently sync stale data
   (the sync will "succeed" and report a record count, giving no
   indication it synced old data). We hit this ourselves during today's
   fix pass. See the Quick Start section above for the correct order.
10. **OpenRouter free-tier daily rate limit is real and will be hit
    under normal testing/demo load.** Free-tier `:free` models are capped
    at 50 requests/day without adding credits (1000/day with ~$10 added
    to the account). This limit was hit during today's testing — every
    LLM-calling module (translate, router, rag, sql, cypher, ner) shares
    this same quota, so heavy use of any one of them depletes it for all
    the others. The quota resets daily (confirmed reset ≈ midnight UTC).
    A production deployment needs a paid tier or a self-hosted model
    before it can support anything beyond light demo/dev use — this is
    not a code bug, it's an infrastructure/budget decision for the team.
11. **Kannada translation can mistranslate domain-specific proper nouns
    and initialisms.** Verified today: the Kannada phrase for "MG Road"
    ("ಎಂಜಿ ರೋಡ್") was translated by the free LLM as **"N G Road"**
    instead of "MG Road." This caused a downstream SQL lookup to
    correctly return zero results for a station name that doesn't exist
    under that spelling — the system failed *safely* (no crash, no
    hallucinated answer, a clear "could not produce a grounded answer"
    response) but the underlying translation was factually wrong. Small
    free LLMs are not reliable at transliterating initialisms/proper
    nouns that don't have a clean phonetic mapping. **Mitigation not yet
    implemented**: adding a short glossary of known station names (and
    other fixed domain terms) to the translation prompt in
    `translate.py`, so the model treats them as fixed terms rather than
    translating them freely, would meaningfully reduce this — flagged as
    a good first improvement for whoever picks this up next.

## Not started (❌) — genuinely out of scope for this submission

- **Kannada ASR/TTS (voice).** Only text-translation exists (see Kannada
  text layer above). Full voice requires downloading and integrating
  real speech models (IndicConformer for ASR, IndicTTS for TTS per the
  original plan) — this is new ML infrastructure, not a code change, and
  needs real audio test files to validate. Rough estimate for a properly
  tested implementation: **1–2 full days**, not fittable into this
  submission window. Reusing a hosted option (e.g. Bhashini's CONVERSE,
  already used by UP Police's 112 helpline) instead of building ASR/TTS
  from scratch is worth evaluating first, per the original plan doc.

- **Full relational schema** — Victim, Complainant, Unit, Court as
  separate linked entities, multi-accused cases. This is a structural
  change touching Postgres schema, `seed_data.py`, `text_to_sql.py`'s
  schema prompt, `text_to_cypher.py`'s graph schema, and every module
  reading `records.json`'s shape. Rough estimate: **~1 full day**,
  including re-verification of every downstream module. A smaller,
  bounded first step (e.g. just adding a `Victim` table with one FK link,
  without touching Unit/Court/multi-accused) is a reasonable next PR
  rather than the full redesign at once.

## LLM provider

Using **OpenRouter** (openrouter.ai) with the free model
`openai/gpt-oss-20b:free` — no billing required at the base tier, but
subject to OpenRouter's free-tier daily rate limits (see known issue #10
above) and to free-model availability changing over time. If this model
stops being free, check `https://openrouter.ai/api/v1/models` for
current `:free` options and swap the model string in `rag_pipeline.py`,
`text_to_sql.py`, `text_to_cypher.py`, `router.py`, `ner_extraction.py`,
and `translate.py`.

**Before any live demo**, check current quota status — a 429 rate-limit
error mid-demo is the most likely live-demo failure mode with this
setup, and it's an infrastructure limit, not a code bug.

## Data consistency — important

All modules read from **copies** of the same `records.json` (883 rows,
seeded, deterministic). If you regenerate seed data, you **must**:
1. Re-copy `records.json` into every module folder that uses it
   (`rag`, `forecasting`, `risk_flagging`, `text_to_sql`).
2. Reload Postgres (`setup_table()` + `load_data()` from `text_to_sql.py`).
3. **Then** run `postgres_to_neo4j.py` (it reads from Postgres, not
   `records.json` — running it before step 2 syncs stale data).
4. Run `embed_documents.py` to refresh embeddings.

A cleaner fix — one shared data path instead of per-folder copies —
would remove this footgun entirely and is worth doing before this goes
further.