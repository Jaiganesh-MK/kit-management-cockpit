"""
step2_rag_layer.py
RAG Layer — pure Python TF-IDF (no chromadb, no sentence-transformers)
=======================================================================
Reads .md files from knowledge_base/, builds a TF-IDF index in memory,
and retrieves relevant chunks for the agent prompts.

Zero heavy dependencies — only numpy and the standard library.
Works on Python 3.14, Streamlit Cloud, and any other environment.
"""

import os
import re
import json
import math
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter

import numpy as np

# ── Constants ────────────────────────────────────────────────────────────────
KNOWLEDGE_DIR  = Path("./knowledge_base")
INDEX_CACHE    = Path("./rag_index_cache.json")
CHUNK_SIZE     = 400
CHUNK_OVERLAP  = 80
TOP_K          = 4

# ── In-memory store ──────────────────────────────────────────────────────────
_chunks    : List[Dict] = []   # [{"text", "source", "heading"}]
_tfidf_mat : Optional[np.ndarray] = None   # (n_chunks, n_terms)
_vocab     : Dict[str, int] = {}
_idf       : Optional[np.ndarray] = None
_index_hash: str = ""


# ── Text utilities ────────────────────────────────────────────────────────────
def _tokenise(text: str) -> List[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def _chunk_markdown(text: str, source: str) -> List[Dict]:
    current_heading = ""
    chunks: List[Dict] = []
    paragraphs = re.split(r"\n{2,}", text.strip())
    buffer = ""

    for para in paragraphs:
        m = re.match(r"^#{1,3}\s+(.+)", para.strip())
        if m:
            current_heading = m.group(1)

        if len(buffer) + len(para) + 2 > CHUNK_SIZE and buffer:
            chunks.append({"text": buffer.strip(), "source": source,
                           "heading": current_heading})
            buffer = buffer[-CHUNK_OVERLAP:] + "\n\n" + para
        else:
            buffer = (buffer + "\n\n" + para).strip() if buffer else para

    if buffer.strip():
        chunks.append({"text": buffer.strip(), "source": source,
                       "heading": current_heading})
    return chunks


# ── TF-IDF index ─────────────────────────────────────────────────────────────
def _build_tfidf(chunks: List[Dict]):
    global _tfidf_mat, _vocab, _idf

    docs   = [_tokenise(c["text"]) for c in chunks]
    n_docs = len(docs)

    # Build vocabulary
    all_terms = sorted({t for doc in docs for t in doc})
    _vocab    = {t: i for i, t in enumerate(all_terms)}
    n_terms   = len(all_terms)

    # TF matrix
    tf = np.zeros((n_docs, n_terms), dtype=np.float32)
    for di, doc in enumerate(docs):
        counts = Counter(doc)
        total  = max(len(doc), 1)
        for t, cnt in counts.items():
            if t in _vocab:
                tf[di, _vocab[t]] = cnt / total

    # IDF
    df   = np.sum(tf > 0, axis=0).astype(np.float32)
    _idf = np.log((n_docs + 1) / (df + 1)) + 1.0

    # TF-IDF
    _tfidf_mat = tf * _idf

    # L2 normalise rows
    norms = np.linalg.norm(_tfidf_mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    _tfidf_mat /= norms


def _query_vector(query: str) -> np.ndarray:
    tokens = _tokenise(query)
    counts = Counter(tokens)
    vec    = np.zeros(len(_vocab), dtype=np.float32)
    for t, cnt in counts.items():
        if t in _vocab:
            vec[_vocab[t]] = cnt
    vec = vec * _idf
    n   = np.linalg.norm(vec)
    if n > 0:
        vec /= n
    return vec


def _cosine_top_k(query_vec: np.ndarray, k: int) -> List[int]:
    if _tfidf_mat is None or len(_chunks) == 0:
        return []
    scores = _tfidf_mat @ query_vec
    k = min(k, len(scores))
    return list(np.argsort(scores)[::-1][:k])


# ── Manifest / cache ──────────────────────────────────────────────────────────
def _md_dir_hash() -> str:
    h = hashlib.md5()
    for p in sorted(KNOWLEDGE_DIR.glob("**/*.md")):
        h.update(p.read_bytes())
    return h.hexdigest()


def _save_cache(chunks: List[Dict], vocab: Dict, idf: np.ndarray):
    data = {
        "hash":   _md_dir_hash(),
        "chunks": chunks,
        "vocab":  vocab,
        "idf":    idf.tolist(),
    }
    with open(INDEX_CACHE, "w") as f:
        json.dump(data, f)


def _load_cache() -> bool:
    global _chunks, _vocab, _idf, _tfidf_mat, _index_hash
    if not INDEX_CACHE.exists():
        return False
    try:
        with open(INDEX_CACHE) as f:
            data = json.load(f)
        current = _md_dir_hash()
        if data["hash"] != current:
            return False
        _chunks    = data["chunks"]
        _vocab     = data["vocab"]
        _idf       = np.array(data["idf"], dtype=np.float32)
        _index_hash = data["hash"]
        # Rebuild TF-IDF matrix from chunks + loaded vocab/idf
        n_docs  = len(_chunks)
        n_terms = len(_vocab)
        tf      = np.zeros((n_docs, n_terms), dtype=np.float32)
        for di, ch in enumerate(_chunks):
            tokens = _tokenise(ch["text"])
            counts = Counter(tokens)
            total  = max(len(tokens), 1)
            for t, cnt in counts.items():
                if t in _vocab:
                    tf[di, _vocab[t]] = cnt / total
        _tfidf_mat = tf * _idf
        norms      = np.linalg.norm(_tfidf_mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        _tfidf_mat /= norms
        return True
    except Exception:
        return False


# ── Public API ────────────────────────────────────────────────────────────────
def build_index(force: bool = False) -> Dict:
    global _chunks, _index_hash

    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    md_files = sorted(KNOWLEDGE_DIR.glob("**/*.md"))

    if not md_files:
        return {"files": 0, "chunks_added": 0, "files_skipped": 0}

    if not force and _load_cache():
        return {"files": 0, "chunks_added": 0,
                "files_skipped": len(md_files)}

    _chunks = []
    for path in md_files:
        text = path.read_text(encoding="utf-8")
        src  = str(path.relative_to(KNOWLEDGE_DIR))
        _chunks.extend(_chunk_markdown(text, src))

    _build_tfidf(_chunks)

    try:
        _save_cache(_chunks, _vocab, _idf)
    except Exception:
        pass

    return {"files": len(md_files), "chunks_added": len(_chunks),
            "files_skipped": 0}


def _format_results(indices: List[int]) -> str:
    if not indices:
        return ""
    parts = []
    for idx in indices:
        ch      = _chunks[idx]
        heading = ch.get("heading", "")
        source  = ch.get("source", "")
        label   = f"[{source}]{(' — ' + heading) if heading else ''}"
        parts.append(f"{label}\n{ch['text'].strip()}")
    return "\n\n---\n\n".join(parts)


def retrieve_for_equipment(
    material_number: str = "",
    kit_types: Optional[List[str]] = None,
    discrepancies: Optional[List[str]] = None,
    top_k: int = TOP_K,
) -> str:
    if not _chunks:
        return ""
    kit_str  = " ".join(kit_types or [])
    disc_str = " ".join(discrepancies or [])
    query    = " ".join(filter(None, [
        f"equipment {material_number}",
        f"kit types {kit_str}" if kit_str else "",
        f"issues {disc_str}"   if disc_str else "",
        "installation requirements prerequisites mandatory safety deadline",
    ]))
    return _format_results(_cosine_top_k(_query_vector(query), top_k))


def retrieve_for_kit(mstk_number: str, top_k: int = TOP_K) -> str:
    if not _chunks:
        return ""
    query = (f"kit {mstk_number} installation procedure prerequisites "
             f"requirements skills downtime failure mode")
    return _format_results(_cosine_top_k(_query_vector(query), top_k))


def retrieve_raw(query: str, top_k: int = TOP_K) -> str:
    if not _chunks:
        return ""
    return _format_results(_cosine_top_k(_query_vector(query), top_k))


def get_index_stats() -> Dict:
    return {
        "files":  len({c["source"] for c in _chunks}),
        "chunks": len(_chunks),
        "ready":  len(_chunks) > 0,
    }


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Building index...")
    stats = build_index()
    print(f"  Files: {stats['files']}  Chunks: {stats['chunks_added']}")
    s = get_index_stats()
    print(f"Ready: {s['ready']}  Total chunks: {s['chunks']}")
    if s["ready"]:
        r = retrieve_for_equipment("3000-MAT-CUR-150", ["MK_Safety"])
        print("\nSample retrieval:\n", r[:400] if r else "No results")