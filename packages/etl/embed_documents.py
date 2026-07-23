"""
Document Embedder
Converts raw text (case_notes / chargesheets) into vector embeddings
using sentence-transformers, and persists them to a JSON-backed vector
store (embeddings.json) rather than pgvector, since the pgvector
extension is not installed on this Postgres instance. The store shape
mirrors what a pgvector table would hold: fir_number, chunk text, and
the embedding vector, so it's a drop-in swap later if pgvector is
added (INSERT INTO document_embeddings (fir_number, chunk, embedding)).
"""

import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
STORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embeddings.json")

_model = None


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


def embed_records(records_path):
    """Extract: read source records. Transform: chunk + embed. Load: persist to JSON store."""
    with open(records_path) as f:
        records = json.load(f)

    model = get_model()
    store = []

    for rec in records:
        text = rec.get("case_notes", "")
        if not text:
            continue
        for chunk in chunk_text(text):
            embedding = model.encode(chunk).tolist()  # JSON-serializable
            store.append({
                "fir_number": rec["fir_number"],
                "chunk": chunk,
                "embedding": embedding,
            })

    with open(STORE_PATH, "w") as f:
        json.dump(store, f)

    return {"records_processed": len(records), "chunks_embedded": len(store)}


def load_embeddings():
    if not os.path.exists(STORE_PATH):
        return []
    with open(STORE_PATH) as f:
        return json.load(f)


if __name__ == "__main__":
    default_source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ml-models", "rag", "records.json")
    result = embed_records(default_source)
    print(json.dumps(result, indent=2))
