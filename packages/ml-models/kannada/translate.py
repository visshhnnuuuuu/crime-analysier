"""
Kannada Language Support (Phase 7)

Translates Kannada queries to English before routing them into the
existing SQL / Cypher / RAG pipelines. Translation only — no changes
to the underlying pipelines themselves.
"""

import os
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)


def translate_to_english(text):
    prompt = f"""Translate the following Kannada text to English.
Output ONLY the translation, no explanation, no notes.

Kannada text: "{text}"

English translation:"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def translate_and_route(text, backend="sql"):
    """
    Translates Kannada text to English, then routes it to the
    requested backend's answer_query function.
    """
    english_query = translate_to_english(text)

    if backend == "sql":
        from text_to_sql import answer_query as sql_answer_query
        result = sql_answer_query(english_query)
    elif backend == "cypher":
        from text_to_cypher import answer_query as cypher_answer_query
        result = cypher_answer_query(english_query)
    elif backend == "rag":
        from rag_pipeline import answer_query as rag_answer_query
        result = rag_answer_query(english_query)
    else:
        return {"error": f"Unknown backend '{backend}'. Use 'sql', 'cypher', or 'rag'."}

    result["translated_query"] = english_query
    result["original_query"] = text
    return result
