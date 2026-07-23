"""
Named Entity Recognition (Phase 2)

Extracts structured entities from case_notes text using an LLM prompt
(rather than a trained NER model, given time constraints). Validates
output shape before returning, since free-tier LLMs can occasionally
return malformed JSON.
"""

import os
import json
import re
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

ENTITY_TYPES = [
    "PERSON", "LOCATION", "DATE", "CRIME_TYPE", "POLICE_STATION",
    "FIR_NUMBER", "ORGANIZATION", "WEAPON", "VEHICLE", "MONEY_AMOUNT"
]

EXPECTED_SCHEMA = {t: [] for t in ENTITY_TYPES}


def extract_entities(text):
    prompt = f"""Extract named entities from this police case note. Return ONLY a
JSON object with these exact keys, each mapping to a list of strings found
in the text (empty list if none found):

{json.dumps(EXPECTED_SCHEMA, indent=2)}

Entity type guide:
- PERSON: names of people (complainants, witnesses, suspects)
- LOCATION: streets, areas, landmarks
- DATE: any dates or date expressions
- CRIME_TYPE: type of crime mentioned
- POLICE_STATION: station names
- FIR_NUMBER: case/FIR numbers
- ORGANIZATION: companies, institutions
- WEAPON: any weapon mentioned
- VEHICLE: any vehicle mentioned
- MONEY_AMOUNT: any monetary amounts

Text: "{text}"

Output ONLY the JSON object, no explanation, no markdown fences."""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.split("<|")[0]  # strip any leaked reasoning tokens

    # Prefer content inside a ```json ... ``` fence if present
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    json_str = fence_match.group(1).strip() if fence_match else raw

    # Fallback: grab the first {...} block if there's still stray text around it
    if not json_str.startswith("{"):
        brace_match = re.search(r"\{.*\}", json_str, re.DOTALL)
        json_str = brace_match.group(0) if brace_match else json_str

    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError:
        return {"error": "Failed to parse entity extraction output", "raw": raw}

    return validate_schema(parsed)


def validate_schema(parsed):
    """Ensure every expected key exists and is a list, even if the LLM missed one."""
    result = {}
    for entity_type in ENTITY_TYPES:
        value = parsed.get(entity_type, [])
        result[entity_type] = value if isinstance(value, list) else []
    return result


def extract_from_records(records_path="records.json", limit=5):
    """Batch test: run extraction on the first `limit` records."""
    with open(records_path) as f:
        records = json.load(f)

    results = []
    for rec in records[:limit]:
        entities = extract_entities(rec["case_notes"])
        results.append({"fir_number": rec["fir_number"], "entities": entities})
    return results


if __name__ == "__main__":
    sample_results = extract_from_records(limit=3)
    for r in sample_results:
        print(f"\n{r['fir_number']}:")
        for entity_type, values in r["entities"].items():
            if values:
                print(f"  {entity_type}: {values}")