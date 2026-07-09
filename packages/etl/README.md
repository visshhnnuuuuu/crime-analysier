# 🔄 packages/etl — Data Pipelines & ETL Services

This module handles structuring unstructured raw databases into the **Knowledge Layer** (graph and vector formats).

---

## 🛠️ ETL Pipeline Scripts

### 1. Relational to Graph ETL (`postgres_to_neo4j.py`)
* **Objective**: Rebuild the graph database (`Neo4j`) from primary transactional records (`PostgreSQL`).
* **Process**: Links suspects, victims, locations, and transaction IDs. Re-runs nightly as a Celery background task to update relationships and community clusters.

### 2. Document Embedder (`embed_documents.py`)
* **Objective**: Convert raw text (case-diaries, judgments, chargesheets) into mathematical vector embeddings.
* **Process**: Segments documents, runs them through the multilingual `sentence-transformers` models, and uploads vectors directly to the `pgvector` store within PostgreSQL.
