"""
Kannada Language Support (Phase 7)
"""

import os
import re
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)


def _clean_translation(text):
    text = text.strip()
    text = re.sub(r"^(english |kannada )?translation:\s*", "", text, flags=re.IGNORECASE)
    text = text.strip("\"'“”‘’")
    return text.strip()


def _call_translation_model(prompt, fallback_text):
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b:free",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content
        if not raw or not raw.strip():
            return fallback_text, "empty_response"
        raw = raw.split("<|")[0]
        return _clean_translation(raw), None
    except Exception as e:
        return fallback_text, str(e)


def translate_to_english(text):
    prompt = f"""Translate the following Kannada text to English.
Output ONLY the translation, no explanation, no notes.

Kannada text: "{text}"

English translation:"""
    return _call_translation_model(prompt, fallback_text=text)


def translate_to_kannada(text):
    prompt = f"""Translate the following English text to Kannada.
Output ONLY the translation, no explanation, no notes.

English text: "{text}"

Kannada translation:"""
    return _call_translation_model(prompt, fallback_text=text)


def synthesize_answer(result):
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
    english_query, translate_in_error = translate_to_english(text)

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
    if translate_in_error:
        result["translate_in_warning"] = f"Kannada->English translation failed, used original text as-is: {translate_in_error}"

    if "answer" not in result:
        result["answer"] = synthesize_answer(result)

    answer_kannada, translate_out_error = translate_to_kannada(result["answer"])
    result["answer_kannada"] = answer_kannada
    if translate_out_error:
        result["translate_out_warning"] = f"English->Kannada translation failed, showing English only: {translate_out_error}"

    return result