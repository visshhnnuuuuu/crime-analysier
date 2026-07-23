"""
Audit Logging (Phase 11)
Logs every query, endpoint hit, and risk-flag review action to a
file for accountability. Nothing here blocks or slows requests down --
it's a fire-and-forget append.
"""

import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.log")


def log_event(event_type, details):
    """
    event_type: e.g. "query", "risk_flag_review"
    details: dict of relevant info (endpoint, query text, backend, etc.)
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_log(limit=50):
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH) as f:
        lines = f.readlines()
    return [json.loads(l) for l in lines[-limit:]]


if __name__ == "__main__":
    log_event("query", {"endpoint": "/query/sql", "query": "test question"})
    print(read_log())
