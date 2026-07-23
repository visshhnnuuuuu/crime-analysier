# packages/etl — Data Pipelines & ETL Services

Structures raw transactional data into graph and vector formats for the
knowledge layer. Both scripts below are tested and confirmed working
against a live Postgres + Neo4j instance (883 records).

---

## Scripts

### 1. Relational to Graph ETL (`postgres_to_neo4j.py`)
- **What it does**: Reads all records from the `fir_records` table in
  Postgres (the transactional source of truth) and rebuilds the Neo4j
  graph from it — `Case` and `Accused` nodes, `ACCUSED_IN` relationships.
- **Verified**: `python3 postgres_to_neo4j.py` → synced 883/883 records.
- **Not yet built**: this is a manual/on-demand script, not a scheduled
  job. No Celery or cron wiring exists yet — running it nightly would
  need that added.
- **Not yet modeled**: only Case + Accused nodes exist. Victim, Location,
  and Unit as separate linked entities are not yet in the graph schema.

### 2. Document Embedder (`embed_documents.py`)
- **What it does**: Chunks `case_notes` text, embeds each chunk with
  `sentence-transformers` (`all-MiniLM-L6-v2`, English-only), and writes
  the vectors to a local JSON file (`embeddings.json`) — not pgvector.
- **Why JSON and not pgvector**: the pgvector extension isn't installed
  on this Postgres instance. The record shape (`fir_number`, `chunk`,
  `embedding`) mirrors a pgvector table 1:1, so swapping in real pgvector
  later is a drop-in change, not a rewrite.
- **Verified**: `python3 embed_documents.py` → 883 records processed,
  883 chunks embedded.
- **Not yet built**: no multilingual embedding model — English only.
  Kannada/multilingual embedding is a separate, unbuilt piece.

## How this connects to the rest of the system

- `postgres_to_neo4j.py` output is what `packages/ml-models/text_to_cypher/`
  queries against.
- `embed_documents.py`'s `embeddings.json` is a standalone artifact right
  now — `packages/ml-models/rag/rag_pipeline.py` currently does its own
  in-memory embedding rather than reading from this file. Wiring RAG to
  read from this shared embeddings.json instead of re-embedding on every
  boot is a reasonable next improvement, not yet done.