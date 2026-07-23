"""
Text-to-Cypher (Phase 6)

Mirrors FIR data into Neo4j as a graph (Case, Accused nodes + relationships),
injects graph schema into a prompt, generates Cypher, validates it's
read-only, executes it, returns results.
"""

import os
import json
import re
from neo4j import GraphDatabase
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "crimepass123"

GRAPH_SCHEMA = """
Nodes:
  (:Case {fir_number, police_station, date_filed, crime_type, status, latitude, longitude})
  (:Accused {name})

Relationships:
  (:Accused)-[:ACCUSED_IN]->(:Case)
"""

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def load_graph(records_path="records.json"):
    with open(records_path) as f:
        records = json.load(f)

    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")  # clean slate
        for r in records:
            session.run("""
                MERGE (c:Case {fir_number: $fir_number})
                SET c.police_station = $police_station,
                    c.date_filed = $date_filed,
                    c.crime_type = $crime_type,
                    c.status = $status,
                    c.latitude = $latitude,
                    c.longitude = $longitude
                MERGE (a:Accused {name: $accused_name})
                MERGE (a)-[:ACCUSED_IN]->(c)
            """, fir_number=r["fir_number"], police_station=r["police_station"],
                 date_filed=r["date_filed"], crime_type=r["crime_type"],
                 status=r["status"], latitude=r["latitude"], longitude=r["longitude"],
                 accused_name=r["accused_name"])

    print(f"Loaded {len(records)} records into Neo4j graph")


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
    load_graph("records.json")
    result = answer_query("Which accused are linked to more than 2 cases?")
    print("Cypher:", result.get("cypher"))
    print("Results:", result.get("results")[:10] if result.get("results") else result)


