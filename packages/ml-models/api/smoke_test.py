"""
Quick smoke test — hits one query per backend so you can eyeball
that nothing is silently broken before submission. Run with the API
already running on localhost:8000.
"""

import requests

BASE = "http://127.0.0.1:8000"

def show(label, resp):
    print(f"\n{'='*20} {label} {'='*20}")
    print(f"Status: {resp.status_code}")
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


# 1. RAG
show("RAG /chat/query", requests.post(
    f"{BASE}/chat/query",
    json={"query": "What thefts happened near a market street?"}
))

# 2. Text-to-SQL
show("Text-to-SQL /query/sql", requests.post(
    f"{BASE}/query/sql",
    json={"query": "How many theft cases were filed at MG Road PS?"}
))

# 3. Text-to-Cypher
show("Text-to-Cypher /query/cypher", requests.post(
    f"{BASE}/query/cypher",
    json={"query": "Which accused are linked to more than 2 cases?"}
))

# 4. Kannada (text translation + SQL backend)
show("Kannada /query/kannada", requests.post(
    f"{BASE}/query/kannada",
    json={
        "query": "ಎಂಜಿ ರೋಡ್ ಠಾಣೆಯಲ್ಲಿ ಎಷ್ಟು ಕಳ್ಳತನ ಪ್ರಕರಣಗಳು ದಾಖಲಾಗಿವೆ?",
        "backend": "sql"
    }
))

# 5. Router auto-dispatch
show("Router /query/auto", requests.post(
    f"{BASE}/query/auto",
    json={"query": "What patterns exist in market street thefts?"}
))

# 6. Risk flags (needs role header)
show("Risk flags /analytics/risk-flags", requests.get(
    f"{BASE}/analytics/risk-flags",
    headers={"X-User-Role": "viewer"}
))

# 7. Hotspots
show("Hotspots /analytics/hotspots", requests.get(
    f"{BASE}/analytics/hotspots",
    headers={"X-User-Role": "viewer"}
))

# 8. Trends
show("Trends /analytics/trends", requests.get(
    f"{BASE}/analytics/trends",
    headers={"X-User-Role": "viewer"}
))

print("\n\nDone. Check each block above for:")
print("- No 500 errors / exceptions")
print("- Answers reference real data (not empty/garbled)")
print("- Kannada answer_kannada field looks like actual Kannada, no translate_*_warning present")
print("- Risk flags return at least a few flagged individuals")