"""
FastAPI wrapper around the three ML modules (Phase 12 — endpoint contracts).

Endpoints:
  GET /analytics/hotspots
  GET /analytics/trends
  GET /analytics/risk-flags
"""

import sys
import os
from fastapi import FastAPI, HTTPException

# Make each sibling module importable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "..", "hotspot"))
sys.path.append(os.path.join(BASE_DIR, "..", "forecasting"))
sys.path.append(os.path.join(BASE_DIR, "..", "risk_flagging"))
sys.path.append(os.path.join(BASE_DIR, "..", "rag"))

from rag_pipeline import ingest_records, answer_query
from hotspot_detection import get_hotspots
from trend_forecasting import get_trends
from risk_flagging import get_risk_flags

HOTSPOT_DATA = os.path.join(BASE_DIR, "..", "hotspot", "records.json")
FORECAST_DATA = os.path.join(BASE_DIR, "..", "forecasting", "records.json")
RISK_DATA = os.path.join(BASE_DIR, "..", "risk_flagging", "records.json")
RAG_DATA = os.path.join(BASE_DIR, "..", "rag", "records.json")

app = FastAPI(title="Crime Analyser — ML Models API")
ingest_records(records_path=RAG_DATA)


@app.get("/analytics/hotspots")
def hotspots():
    try:
        return get_hotspots(records_path=HOTSPOT_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/trends")
def trends():
    try:
        return get_trends(records_path=FORECAST_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/risk-flags")
def risk_flags():
    try:
        return get_risk_flags(records_path=RISK_DATA)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def health():
    return {"status": "ok", "endpoints": ["/analytics/hotspots", "/analytics/trends", "/analytics/risk-flags"]}

from pydantic import BaseModel

class ChatQuery(BaseModel):
    query: str

@app.post("/chat/query")
def chat_query(payload: ChatQuery):
    try:
        return answer_query(payload.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))