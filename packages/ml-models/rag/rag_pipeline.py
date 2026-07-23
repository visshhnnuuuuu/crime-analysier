"""
RAG Pipeline (Phase 4) — English only, in-memory vector store.

chunk -> embed -> store -> retrieve (top-k cosine) -> citation-enforced
answer -> validate citations exist before returning.
"""

import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 5

_model = None
_store = []  # list of {"fir_number": ..., "text": ..., "embedding": np.array}


def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def chunk_text(text, chunk_size=512, overlap=50):
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        start = end - overlap
    return chunks


def ingest_records(records_path="records.json"):
    global _store
    model = get_model()
    with open(records_path) as f:
        records = json.load(f)

    _store = []
    for rec in records:
        for chunk in chunk_text(rec["case_notes"]):
            emb = model.encode(chunk)
            _store.append({"fir_number": rec["fir_number"], "text": chunk, "embedding": emb})

    print(f"Ingested {len(_store)} chunks from {len(records)} records")


def retrieve(query, top_k=TOP_K):
    model = get_model()
    q_emb = model.encode(query)

    scored = []
    for item in _store:
        sim = np.dot(q_emb, item["embedding"]) / (
            np.linalg.norm(q_emb) * np.linalg.norm(item["embedding"])
        )
        scored.append((sim, item))

    scored.sort(key=lambda x: -x[0])
    return [
        {"fir_number": item["fir_number"], "text": item["text"], "similarity": float(sim)}
        for sim, item in scored[:top_k]
    ]


def build_prompt(query, retrieved_chunks):
    context_block = "\n\n".join(
        f"[Source: {c['fir_number']}]\n{c['text']}" for c in retrieved_chunks
    )
    return f"""You are a police records assistant. Answer using ONLY the context below.
Every factual claim MUST end with a citation in the form (Source: <fir_number>).
If the context doesn't contain the answer, say so explicitly.

Context:
{context_block}

Question: {query}

Answer (with citations):"""


def has_valid_citations(answer_text, retrieved_chunks):
    valid_ids = {c["fir_number"] for c in retrieved_chunks}
    return any(f"(Source: {fid})" in answer_text for fid in valid_ids)


from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

def call_llm(prompt):
    response = client.chat.completions.create(
        model="openai/gpt-oss-20b:free",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content
    return raw.split("<|")[0]  # strip any leaked reasoning tokens

def answer_query(query):
    chunks = retrieve(query)
    if not chunks:
        return {"answer": "No relevant records found.", "sources": []}

    prompt = build_prompt(query, chunks)
    answer = call_llm(prompt)

    if not has_valid_citations(answer, chunks):
        stricter = prompt + "\n\nReminder: cite (Source: <fir_number>) for every claim."
        answer = call_llm(stricter)
        if not has_valid_citations(answer, chunks):
            return {"answer": "Could not produce a properly cited answer.", "sources": []}

    return {"answer": answer, "sources": [c["fir_number"] for c in chunks]}


if __name__ == "__main__":
    ingest_records("records.json")
    result = answer_query("What thefts happened near a market street?")
    print(result["answer"])
    print("\nSources:", result["sources"])
    