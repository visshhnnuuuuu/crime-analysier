"""
Intent Classification + Query Router (Phase 3)
Classifies a query as Lookup / Relationship / Analytical and routes
to the correct backend, with a confidence threshold + fallback.
"""

import os
import re
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

VALID_INTENTS = {"lookup": "sql", "relationship": "cypher", "analytical": "rag"}

def classify_intent(question):
    prompt = f"""Classify this police-records question into exactly ONE category:

- lookup: simple fact retrieval, filters, counts (e.g. "how many thefts at X station")
- relationship: connections between entities, graph-style questions (e.g. "which accused are linked to more than 2 cases")
- analytical: open-ended, needs synthesis/explanation from case narratives (e.g. "what patterns exist in market thefts")

Question: "{question}"

Output ONLY one word: lookup, relationship, or analytical.
Then on a new line output a confidence score 0-100.

Format:
<intent>
<confidence>"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.split("<|")[0]  # strip any leaked reasoning tokens
    text = raw.strip().lower()
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    intent = "lookup"
    confidence = 0
    for l in lines:
        if l in VALID_INTENTS:
            intent = l
        m = re.search(r"\d+", l)
        if m:
            confidence = int(m.group())

    return intent, confidence


def route_query(question, confidence_threshold=50):
    intent, confidence = classify_intent(question)

    if confidence < confidence_threshold:
        return {
            "error": "Low confidence in query intent — please rephrase.",
            "detected_intent": intent,
            "confidence": confidence,
        }

    backend = VALID_INTENTS[intent]
    return {"backend": backend, "intent": intent, "confidence": confidence}


if __name__ == "__main__":
    tests = [
        "How many theft cases were filed at MG Road PS?",
        "Which accused are linked to more than 2 cases?",
        "What patterns exist in market street thefts?",
    ]
    for q in tests:
        print(q, "->", route_query(q))