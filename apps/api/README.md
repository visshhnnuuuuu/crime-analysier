# 🧠 apps/api — Backend API Service (FastAPI)

This is the FastAPI-based backend application representing the **Reasoning & Analytics Layer** of the platform.

---

## 🛠️ Tech Stack & Key Services

* **API Core**: FastAPI (asynchronous, auto-generated OpenAPI docs).
* **Database Driver**: SQLAlchemy + PostgreSQL/PostGIS (structured data & geospatial queries).
* **Graph Engine**: Neo4j community/shortest-path Cypher endpoints.
* **Cache & Session Management**: Redis for cheap and quick chat history buffer tracking.
* **Task Management**: Celery + Redis for asynchronous background tasks (ETL, report generation, analytics).
* **Auth Provider**: Keycloak token checking and custom role middleware validation.

---

## 📁 Directory Structure

```
apps/api/
├── app/
│   ├── main.py                 # FastAPI application initializer
│   ├── config.py               # Environment configuration settings (.env parses here)
│   ├── routes/                 # Route/controller handlers
│   │   ├── auth.py             # Keycloak RBAC validators
│   │   ├── chat.py             # Conversational agent query stream
│   │   ├── fir.py              # Case retrieval and timelines
│   │   └── analytics.py        # Crime hotspots, forecasting, and graphs
│   ├── models/                 # SQLAlchemy schemas (FIR, PERSON, CASE_PERSON)
│   ├── services/               # Core business/reasoning logic
│   │   ├── chat_service.py     # Natural language query router (SQL/Cypher/Vector)
│   │   ├── rag_service.py      # pgvector search queries
│   │   └── graph_service.py    # Neo4j query generator and analyzer
│   ├── middleware/             # Role scoping, query restrictions, and audit logs
│   └── prompts/                # Structured templates for prompt generation (RAG, translation)
├── migrations/                 # Alembic DB migration files
└── tests/                      # Pytest unit and integration suites
```

---

## 🚀 Running the API

Ensure your Python virtual environment is activated and requirements are installed:
```bash
# Activate virtual environment from root
source ../../.venv/bin/activate

# Start uvicorn development server
uvicorn app.main:app --reload --port 8000
```

The API docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).
