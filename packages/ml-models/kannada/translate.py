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


def translate_to_kannada(text):
    prompt = f"""Translate the following English text to Kannada.
Output ONLY the translation, no explanation, no notes.

English text: "{text}"

Kannada translation:"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def synthesize_answer(result):
    """
    Builds a short natural-language answer from raw query results
    when the backend (text_to_sql / text_to_cypher) doesn't already
    provide a synthesized 'answer' field.
    """
    if "error" in result:
        return f"The query could not be completed: {result['error']}"

    results = result.get("results", [])
    n = result.get("n_results", len(results))

    if n == 0:
        return "No matching results were found."

    lines = []
    for row in results[:5]:
        parts = [f"{k}: {v}" for k, v in row.items()]
        lines.append(", ".join(parts))

    summary = "; ".join(lines)
    suffix = f" (showing 5 of {n})" if n > 5 else ""
    return f"Found {n} result(s){suffix}: {summary}"


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

    # Synthesize an answer if the backend didn't already provide one
    if "answer" not in result:
        result["answer"] = synthesize_answer(result)

    result["answer_kannada"] = translate_to_kannada(result["answer"])

    return result
