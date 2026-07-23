"""
Relational to Graph ETL
Rebuilds the Neo4j graph from the live fir_records table in Postgres
(rather than from the source records.json), so the graph always
reflects whatever is currently the transactional source of truth.
"""

import psycopg2
from neo4j import GraphDatabase

PG_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "dbname": "postgres",
    "user": "postgres",
    "password": "crimepass123",
}

NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "crimepass123"


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
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
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
                 date_filed=str(r["date_filed"]), crime_type=r["crime_type"],
                 status=r["status"], latitude=r["latitude"], longitude=r["longitude"],
                 accused_name=r["accused_name"])
    driver.close()


def run():
    """Entry point -- what a nightly Celery task or /etl endpoint would call."""
    records = fetch_records_from_postgres()
    rebuild_graph(records)
    return {"status": "ok", "records_synced": len(records)}


if __name__ == "__main__":
    result = run()
    print(f"Synced {result['records_synced']} records from Postgres into Neo4j")
