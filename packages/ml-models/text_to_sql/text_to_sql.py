"""
Text-to-SQL (Phase 5)
Loads FIR records into Postgres, injects schema into a prompt, asks the
LLM to generate parameterized SQL, validates it's safe, executes it,
and synthesizes a cited, grounded answer.
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
    "host": os.environ.get("PG_HOST", "localhost"),
    "port": os.environ.get("PG_PORT", "5432"),
    "dbname": os.environ.get("PG_DBNAME", "postgres"),
    "user": os.environ.get("PG_USER", "postgres"),
    "password": os.environ.get("PG_PASSWORD", "crimepass123"),
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
- police_station values end with " PS" (e.g. 'MG Road PS', 'Whitefield PS', 'Koramangala PS')
- crime_type values are capitalized (e.g. 'Theft', 'Robbery', 'Assault', 'Burglary', 'Fraud')
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
    """
    Defense-in-depth validation beyond keyword blocklisting:
    - must be a single SELECT statement (no stacked statements via ;)
    - no forbidden write/DDL keywords anywhere
    - only references the known fir_records table
    """
    lowered = sql.lower().strip()
    forbidden = ["insert", "update", "delete", "drop", "alter", "truncate",
                 "grant", "revoke", "create", "--", "/*", ";--"]

    if not lowered.startswith("select"):
        return False
    if any(word in lowered for word in forbidden):
        return False

    # reject stacked statements: allow at most one trailing semicolon
    stripped = lowered.rstrip(";").rstrip()
    if ";" in stripped:
        return False

    # only allow references to the known table
    if "fir_records" not in lowered:
        return False

    return True


def run_query(sql):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql)
    cols = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def build_answer_prompt(question, results):
    rows_block = "\n".join(json.dumps(row, default=str) for row in results[:20])
    return f"""You are a police records assistant. Answer the question using
ONLY the data rows below — do not add any name, number, or fact that
is not literally present in these rows. If a row has a fir_number,
cite it in the form (Source: <fir_number>) next to the claim it supports.

Data rows:
{rows_block}

Question: {question}

Write a short, natural-language answer. Every specific value you state
must come directly from the rows above.
Answer:"""


def has_grounded_values(answer_text, results):
    """
    Citation check: if rows include fir_number, require at least one
    (Source: <fir_number>) citation. Otherwise, fall back to checking
    that a real value (string or number) from the results appears in
    the answer (proxy for 'grounded in retrieved data, not hallucinated').
    """
    if not results:
        return False

    fir_numbers = {row["fir_number"] for row in results if row.get("fir_number")}
    if fir_numbers:
        return any(f"(Source: {fid})" in answer_text for fid in fir_numbers)

    candidate_values = set()
    for row in results:
        for v in row.values():
            if isinstance(v, str) and len(v) > 1:
                candidate_values.add(v)
            elif isinstance(v, (int, float)):
                candidate_values.add(str(v))
    return any(val in answer_text for val in candidate_values)


def call_llm(prompt):
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    return raw.split("<|")[0]  # strip any leaked reasoning tokens


def synthesize_answer(question, results):
    if not results:
        return "No matching records were found.", []

    prompt = build_answer_prompt(question, results)
    answer = call_llm(prompt)

    if not has_grounded_values(answer, results):
        stricter = prompt + "\n\nReminder: only use exact values from the data rows, and cite (Source: <fir_number>) if fir_number is present. Do not invent names or numbers."
        answer = call_llm(stricter)
        if not has_grounded_values(answer, results):
            return "Could not produce an answer grounded in the retrieved data.", []

    sources = [row["fir_number"] for row in results if row.get("fir_number")]
    return answer, sources


def answer_query(question):
    sql = generate_sql(question)
    if not is_safe(sql):
        return {"error": "Generated SQL failed safety validation", "sql": sql}

    results = run_query(sql)
    answer, sources = synthesize_answer(question, results)

    return {
        "sql": sql,
        "results": results,
        "n_results": len(results),
        "answer": answer,
        "sources": sources,
    }


if __name__ == "__main__":
    setup_table()
    load_data("records.json")
    result = answer_query("How many theft cases were filed at MG Road PS?")
    print("SQL:", result.get("sql"))
    print("Answer:", result.get("answer"))
    print("Results:", result.get("results"))
