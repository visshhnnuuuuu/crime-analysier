"""
FastAPI wrapper around the ML modules (Phase 12 — endpoint contracts).
"""

import sys
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "..", "hotspot"))
sys.path.append(os.path.join(BASE_DIR, "..", "forecasting"))
sys.path.append(os.path.join(BASE_DIR, "..", "risk_flagging"))
sys.path.append(os.path.join(BASE_DIR, "..", "rag"))
sys.path.append(os.path.join(BASE_DIR, "..", "text_to_sql"))
sys.path.append(os.path.join(BASE_DIR, "..", "text_to_cypher"))
sys.path.append(os.path.join(BASE_DIR, "..", "kannada"))
sys.path.append(os.path.join(BASE_DIR, "..", "router"))
sys.path.append(os.path.join(BASE_DIR, "..", "audit"))
sys.path.append(os.path.join(BASE_DIR, "..", "auth"))
sys.path.append(os.path.join(BASE_DIR, "..", "..", "etl"))

from rag_pipeline import ingest_records, answer_query
from hotspot_detection import get_hotspots
from trend_forecasting import get_trends
from risk_flagging import get_risk_flags
from text_to_sql import setup_table, load_data, answer_query as sql_answer_query
from text_to_cypher import answer_query as cypher_answer_query
from translate import translate_and_route
from router import route_query
from audit_log import log_event, read_log
from rbac import require_role, require_reviewer
from postgres_to_neo4j import run as run_postgres_to_neo4j
from embed_documents import embed_records
from fastapi import Depends

HOTSPOT_DATA = os.path.join(BASE_DIR, "..", "hotspot", "records.json")
FORECAST_DATA = os.path.join(BASE_DIR, "..", "forecasting", "records.json")
RISK_DATA = os.path.join(BASE_DIR, "..", "risk_flagging", "records.json")
RAG_DATA = os.path.join(BASE_DIR, "..", "rag", "records.json")
SQL_DATA = os.path.join(BASE_DIR, "..", "text_to_sql", "records.json")

app = FastAPI(title="Crime Analyser — ML Models API")
ingest_records(records_path=RAG_DATA)
setup_table()
load_data(records_path=SQL_DATA)


@app.get("/analytics/hotspots")
def hotspots():
    try:
        log_event("query", {"endpoint": "/analytics/hotspots"})
        return get_hotspots(records_path=HOTSPOT_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/trends")
def trends():
    try:
        log_event("query", {"endpoint": "/analytics/trends"})
        return get_trends(records_path=FORECAST_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/risk-flags")
def risk_flags(role: str = Depends(require_role)):
    try:
        log_event("query", {"endpoint": "/analytics/risk-flags", "role": role})
        return get_risk_flags(records_path=RISK_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ReviewAction(BaseModel):
    accused_name: str
    reviewer: str
    decision: str

@app.post("/analytics/risk-flags/review")
def review_risk_flag(payload: ReviewAction, role: str = Depends(require_reviewer)):
    log_event("risk_flag_review", {
        "accused_name": payload.accused_name,
        "reviewer": payload.reviewer,
        "decision": payload.decision,
    })
    return {"status": "logged", "accused_name": payload.accused_name}


@app.get("/audit/log")
def audit_log():
    return {"entries": read_log()}


@app.get("/")
def health():
    return {"status": "ok", "endpoints": ["/analytics/hotspots", "/analytics/trends", "/analytics/risk-flags"]}


class ChatQuery(BaseModel):
    query: str

@app.post("/chat/query")
def chat_query(payload: ChatQuery):
    try:
        log_event("query", {"endpoint": "/chat/query", "query": payload.query})
        return answer_query(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SQLQuery(BaseModel):
    query: str

@app.post("/query/sql")
def sql_query(payload: SQLQuery):
    try:
        log_event("query", {"endpoint": "/query/sql", "query": payload.query})
        return sql_answer_query(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CypherQuery(BaseModel):
    query: str

@app.post("/query/cypher")
def cypher_query(payload: CypherQuery):
    try:
        log_event("query", {"endpoint": "/query/cypher", "query": payload.query})
        return cypher_answer_query(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class KannadaQuery(BaseModel):
    query: str
    backend: str = "sql"

@app.post("/query/kannada")
def kannada_query(payload: KannadaQuery):
    try:
        log_event("query", {"endpoint": "/query/kannada", "query": payload.query, "backend": payload.backend})
        return translate_and_route(payload.query, payload.backend)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RouterQuery(BaseModel):
    query: str

@app.post("/query/auto")
def auto_query(payload: RouterQuery):
    try:
        log_event("query", {"endpoint": "/query/auto", "query": payload.query})
        routing = route_query(payload.query)
        if "error" in routing:
            return routing
        backend = routing["backend"]
        if backend == "sql":
            result = sql_answer_query(payload.query)
        elif backend == "cypher":
            result = cypher_answer_query(payload.query)
        else:
            result = answer_query(payload.query)
        result["detected_intent"] = routing["intent"]
        result["confidence"] = routing["confidence"]
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/etl/run")
def run_etl(role: str = Depends(require_reviewer)):
    """
    Triggers the ETL pipeline: rebuilds the Neo4j graph from the
    current Postgres fir_records table, and re-embeds case_notes into
    the document vector store. Requires the 'reviewer' role since this
    changes what every backend serves.
    """
    try:
        log_event("etl_run", {"triggered_by_role": role})
        neo4j_result = run_postgres_to_neo4j()

        RAG_SOURCE = os.path.join(BASE_DIR, "..", "rag", "records.json")
        embed_result = embed_records(RAG_SOURCE)

        return {
            "status": "ok",
            "neo4j": neo4j_result,
            "embeddings": embed_result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
