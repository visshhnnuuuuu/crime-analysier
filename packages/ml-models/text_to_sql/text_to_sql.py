"""
Text-to-SQL (Phase 5)

Loads FIR records into Postgres, injects schema into a prompt, asks the
LLM to generate parameterized SQL, validates it's safe, executes it,
and synthesizes a cited answer.
"""

import os
import json
import re
import psycopg2
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

DB_CONFIG = {
    "host": "localhost",
    "port": "5432",
    "dbname": "postgres",
    "user": "postgres",
    "password": "crimepass123",
}

SCHEMA = """
Table: fir_records
Columns:
  fir_number TEXT PRIMARY KEY
  police_station TEXT
  date_filed DATE
  crime_type TEXT
  status TEXT
  latitude FLOAT
  longitude FLOAT
  accused_name TEXT
  case_notes TEXT
"""


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def setup_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fir_records (
            fir_number TEXT PRIMARY KEY,
            police_station TEXT,
            date_filed DATE,
            crime_type TEXT,
            status TEXT,
            latitude FLOAT,
            longitude FLOAT,
            accused_name TEXT,
            case_notes TEXT
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def load_data(records_path="records.json"):
    with open(records_path) as f:
        records = json.load(f)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("TRUNCATE fir_records;")
    for r in records:
        cur.execute("""
            INSERT INTO fir_records (fir_number, police_station, date_filed, crime_type, status, latitude, longitude, accused_name, case_notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (fir_number) DO NOTHING;
        """, (r["fir_number"], r["police_station"], r["date_filed"], r["crime_type"],
              r["status"], r["latitude"], r["longitude"], r["accused_name"], r["case_notes"]))
    conn.commit()
    cur.close()
    conn.close()
    print(f"Loaded {len(records)} records into Postgres")


def generate_sql(question):
    prompt = f"""You are a SQL generator. Given this schema:
{SCHEMA}

Write a SINGLE PostgreSQL SELECT query (read-only, no writes) to answer:
"{question}"

Rules:
- Only SELECT statements, never INSERT/UPDATE/DELETE/DROP
- Use LIMIT 20 unless the question asks for a count/aggregate
- Output ONLY the raw SQL, no explanation, no markdown fences

SQL:"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    sql = response.choices[0].message.content.strip()
    sql = re.sub(r"^```sql|```$", "", sql, flags=re.MULTILINE).strip()
    return sql


def is_safe(sql):
    lowered = sql.lower()
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate", "--", ";--"]
    if not lowered.strip().startswith("select"):
        return False
    return not any(word in lowered for word in forbidden)


def run_query(sql):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def answer_query(question):
    sql = generate_sql(question)
    if not is_safe(sql):
        return {"error": "Generated SQL failed safety validation", "sql": sql}

    results = run_query(sql)
    return {"sql": sql, "results": results, "n_results": len(results)}


if __name__ == "__main__":
    setup_table()
    load_data("records.json")
    result = answer_query("How many theft cases were filed at MG Road PS?")
    print("SQL:", result.get("sql"))
    print("Results:", result.get("results"))