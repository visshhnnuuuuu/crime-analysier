"""
Relational to Graph ETL — single source of truth for the Neo4j graph.
Rebuilds the Neo4j graph from the live fir_records table in Postgres
(rather than from the source records.json), so the graph always
reflects whatever is currently the transactional source of truth.
text_to_cypher.py delegates to this module rather than doing its own
independent load, so there's only one write path into Neo4j.
"""

import os
import psycopg2
from neo4j import GraphDatabase

PG_CONFIG = {
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
    "dbname": os.environ.get("PG_DBNAME", "postgres"),
    "user": os.environ.get("PG_USER", "postgres"),
    "password": os.environ.get("PG_PASSWORD", "crimepass123"),
}

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "crimepass123")


def fetch_records_from_postgres():
    conn = psycopg2.connect(**PG_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT fir_number, police_station, date_filed, crime_type,
               status, latitude, longitude, accused_name
        FROM fir_records;
    """)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def rebuild_graph(records):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            # Scoped delete: only Case/Accused nodes, so future entity
            # types (Victim, Unit, Court, etc.) added elsewhere aren't
            # silently wiped on every sync.
            session.run("MATCH (n:Case) DETACH DELETE n")
            session.run("MATCH (n:Accused) DETACH DELETE n")
            for r in records:
                # null-guard: avoid merging unrelated cases into one shared null node
                accused_name = r["accused_name"] or "Unknown"
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
                     date_filed=str(r["date_filed"]), crime_type=r["crime_type"],
                     status=r["status"], latitude=r["latitude"], longitude=r["longitude"],
                     accused_name=accused_name)
    finally:
        driver.close()


def run():
    """Entry point -- what a nightly Celery task or /etl endpoint would call."""
    try:
        records = fetch_records_from_postgres()
    except Exception as e:
        return {"status": "error", "stage": "postgres_fetch", "detail": str(e)}

    try:
        rebuild_graph(records)
    except Exception as e:
        return {"status": "error", "stage": "neo4j_write", "detail": str(e)}

    return {"status": "ok", "records_synced": len(records)}


if __name__ == "__main__":
    result = run()
    if result["status"] == "ok":
        print(f"Synced {result['records_synced']} records from Postgres into Neo4j")
    else:
        print(f"Sync failed at {result['stage']}: {result['detail']}")