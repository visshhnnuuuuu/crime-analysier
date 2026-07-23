"""
Text-to-Cypher (Phase 6)

Injects graph schema into a prompt, generates Cypher, validates it's
read-only, executes it, returns results. Graph loading is delegated to
postgres_to_neo4j.py, the single source of truth for what's in Neo4j —
this module no longer does its own independent load from records.json,
so two scripts can't silently overwrite each other's graph data.
"""

import os
import re
from neo4j import GraphDatabase
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "crimepass123")

GRAPH_SCHEMA = """
Nodes:
  (:Case {fir_number, police_station, date_filed, crime_type, status, latitude, longitude})
  (:Accused {name})

Relationships:
  (:Accused)-[:ACCUSED_IN]->(:Case)
"""

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def load_graph():
    """
    Delegates to postgres_to_neo4j.run() so there's one authoritative
    load path (Postgres, not records.json directly). Kept as a thin
    wrapper so existing callers of load_graph() don't break.
    """
    from postgres_to_neo4j import run as sync_from_postgres
    return sync_from_postgres()


def generate_cypher(question):
    prompt = f"""You are a Cypher query generator for Neo4j. Given this schema:
{GRAPH_SCHEMA}

Write a SINGLE read-only Cypher query to answer:
"{question}"

Rules:
- Only MATCH/RETURN/WITH/WHERE, never CREATE/DELETE/SET/MERGE
- Output ONLY the raw Cypher query wrapped in a code block, nothing else, no reasoning, no explanation.

````cypher
<your query here>
```"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()

    # Cut off any leaked reasoning/special tokens from the model
    raw = raw.split("<|")[0]

    # Prefer content inside a ```cypher ... ``` fence if present
    fence_match = re.search(r"```(?:cypher)?\s*(.*?)```", raw, re.DOTALL)
    if fence_match:
        cypher = fence_match.group(1).strip()
    else:
        # Fallback: slice from the first real Cypher keyword onward
        keyword_match = re.search(r"\b(MATCH|OPTIONAL MATCH|WITH|CALL|UNWIND)\b", raw, re.IGNORECASE)
        cypher = raw[keyword_match.start():].strip() if keyword_match else raw

    return cypher


def is_safe(cypher):
    lowered = cypher.lower()
    forbidden = ["create", "delete", "set", "merge", "remove", "drop"]
    return not any(word in lowered for word in forbidden)


def run_cypher(cypher):
    with driver.session() as session:
        result = session.run(cypher)
        return [record.data() for record in result]


def answer_query(question):
    cypher = generate_cypher(question)
    if not is_safe(cypher):
        return {"error": "Generated Cypher failed safety validation", "cypher": cypher}

    results = run_cypher(cypher)
    return {"cypher": cypher, "results": results, "n_results": len(results)}


if __name__ == "__main__":
    load_graph()
    result = answer_query("Which accused are linked to more than 2 cases?")
    print("Cypher:", result.get("cypher"))
    print("Results:", result.get("results")[:10] if result.get("results") else result)


