#  Criminal Agent Platform (Crime Intelligence Platform)

An intelligent conversational AI and crime analytics platform providing a natural-language interface and analytics layer over state crime databases. Built on a **RAG + Knowledge Graph + Geospatial/ML** stack with robust governance baked into every layer.

---

##  How It Works

The platform processes crime records (FIRs, biometrics, financial transactions, socio-economic data) through four distinct architectural layers:

```
  ┌──────────────────────────────────────────────────────────┐
  │  INTERFACE LAYER (Next.js Chat, Map, Network Graph)   │
  └────────────────────────────▲─────────────────────────────┘
                               │ (REST / WebSockets)
  ┌────────────────────────────┴─────────────────────────────┐
  │  REASONING & ANALYTICS (FastAPI router + ML Models)   │
  └────────────────────────────▲─────────────────────────────┘
                               │ (SQL / Cypher / Vector)
  ┌────────────────────────────┴─────────────────────────────┐
  │  KNOWLEDGE LAYER (Postgres, Neo4j Graph, pgvector)     │
  └────────────────────────────▲─────────────────────────────┘
                               │ (ETL Pipelines)
  ┌────────────────────────────┴─────────────────────────────┐
  │  DATA SOURCES (CCTNS records, Financial logs, Census)  │
  └──────────────────────────────────────────────────────────┘
```

1. **Query Translation & Routing**: Users input text or voice queries in English or Kannada. The FastAPI reasoning engine analyzes the intent and routes the query:
   - **Lookup questions** (e.g. status of a specific case) are translated to standard SQL.
   - **Criminal network questions** (relationships between accused) are translated to Cypher graph queries.
   - **Analytical queries** (crime trends or similar past cases) utilize pgvector embeddings and ML models.
2. **Contextual Synthesis**: The LLM synthesizes a response, citing specific source records to ensure transparency and accountability.
3. **Governance & Audit**: Every query is role-scoped, and details are written to an append-only audit trail.

---

##  Repository Structure (Turborepo)

This repository is set up as a Turborepo monorepo:

```
criminal-agent-platform/
├── apps/
│   ├── web/                        # Next.js frontend (Chat UI, Dashboards, Map, Graphs)
│   └── api/                        # FastAPI backend (Query Routing, API routes)
├── packages/
│   ├── ml-models/                  # ML models (KDE Hotspots, Forecasting, SHAP explanation)
│   ├── etl/                        # ETL pipelines (Postgres to Neo4j, document embedding)
│   ├── eslint-config/              # Shared linting configs (JS/TS)
│   ├── typescript-config/          # Shared typescript configurations
│   └── ui/                         # Shared React component library
├── infra/                          # Dockerfiles and Kubernetes manifests
└── docker-compose.yml              # Local database services setup (Postgres + Neo4j + Redis)
```

---

## 🛠️ Quickstart

### 1. Set Up Environment Variables
Copy `.env.example` to `.env` and fill in the required keys for the databases, AI endpoints, and auth servers:
```bash
cp .env.example .env
```

### 2. Launch Local Databases
Use docker-compose to start PostgreSQL (+ PostGIS + pgvector), Neo4j, and Redis:
```bash
docker compose up -d
```

### 3. Install JavaScript Workspace Dependencies
Install node dependencies for the root and workspaces:
```bash
npm install
```

### 4. Install Python Dependencies
Set up the virtual environment and install Python libraries (from the root or backend directory):
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Run the Project
* Run the Next.js frontend in development mode:
  ```bash
  npm run dev --workspace=web
  ```
* Run the FastAPI backend:
  ```bash
  source .venv/bin/activate
  uvicorn apps.api.app.main:app --reload
  ```
