"""
step2_rag_layer.py
RAG Layer for Kit Management Knowledge Base
============================================
Reads .md files from the knowledge_base/ folder, embeds them using a
free local sentence-transformers model, stores them in ChromaDB, and
provides retrieval functions for the agent prompts.

Dependencies (add to requirements.txt):
    chromadb>=0.4.0
    sentence-transformers>=2.2.0

Usage:
    from step2_rag_layer import retrieve_for_equipment, retrieve_for_kit, build_index

    # Build once on startup (auto-skips if already built)
    build_index()

    # Retrieve relevant chunks before calling Agent 1
    chunks = retrieve_for_equipment(
        material_number="3000-MAT-CUR-150",
        kit_types=["MK_Safety", "UK_Improvement"],
        discrepancies=["volume drift", "missing installation record"],
    )

    # Retrieve for a specific kit
    kit_chunks = retrieve_for_kit("3495770-02002")
"""

import os
import re
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Optional

# ── Constants ────────────────────────────────────────────────────────────────
KNOWLEDGE_DIR  = Path("./knowledge_base")        # where your .md files live
CHROMA_DIR     = Path("./chroma_db")             # persisted vector store
EMBED_MODEL    = "all-MiniLM-L6-v2"             # free, ~80MB, runs CPU-only
COLLECTION     = "kit_knowledge"
CHUNK_SIZE     = 400          # characters per chunk
CHUNK_OVERLAP  = 80           # overlap between consecutive chunks
TOP_K          = 4            # chunks to return per query
INDEX_MANIFEST = CHROMA_DIR / "manifest.json"   # tracks which files are indexed

# ── Lazy singletons (loaded once per Streamlit session) ──────────────────────
_model      = None
_collection = None


def _get_model():
    """Load the sentence-transformer model once."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(EMBED_MODEL)
        except ImportError:
            raise ImportError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers chromadb"
            )
    return _model


def _get_collection():
    """Get or create the ChromaDB collection."""
    global _collection
    if _collection is None:
        try:
            import chromadb
        except ImportError:
            raise ImportError(
                "chromadb not installed. Run: pip install chromadb sentence-transformers"
            )
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = client.get_or_create_collection(
            name=COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# ── Text chunking ─────────────────────────────────────────────────────────────
def _chunk_markdown(text: str, source: str) -> List[Dict]:
    """
    Split a markdown document into overlapping chunks.
    Tries to break on double-newlines (paragraph boundaries) first,
    falls back to character splitting.
    Returns list of dicts with keys: text, source, heading.
    """
    # Extract the current H1/H2 heading for each chunk (for metadata)
    current_heading = ""
    chunks = []
    paragraphs = re.split(r"\n{2,}", text.strip())

    buffer = ""
    for para in paragraphs:
        # Track headings for metadata context
        heading_match = re.match(r"^#{1,3}\s+(.+)", para.strip())
        if heading_match:
            current_heading = heading_match.group(1)

        # Build chunks respecting CHUNK_SIZE
        if len(buffer) + len(para) + 2 > CHUNK_SIZE and buffer:
            chunks.append({
                "text":    buffer.strip(),
                "source":  source,
                "heading": current_heading,
            })
            # Overlap: keep last CHUNK_OVERLAP chars
            buffer = buffer[-CHUNK_OVERLAP:] + "\n\n" + para
        else:
            buffer = (buffer + "\n\n" + para).strip() if buffer else para

    if buffer.strip():
        chunks.append({
            "text":    buffer.strip(),
            "source":  source,
            "heading": current_heading,
        })

    return chunks


# ── Manifest (tracks which files are indexed) ────────────────────────────────
def _load_manifest() -> Dict[str, str]:
    """Returns {filepath: md5_hash} of currently indexed files."""
    if INDEX_MANIFEST.exists():
        with open(INDEX_MANIFEST, "r") as f:
            return json.load(f)
    return {}


def _save_manifest(manifest: Dict[str, str]):
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_MANIFEST, "w") as f:
        json.dump(manifest, f, indent=2)


def _file_hash(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


# ── Build / update index ──────────────────────────────────────────────────────
def build_index(force: bool = False) -> Dict[str, int]:
    """
    Scan KNOWLEDGE_DIR for .md files, embed any that are new or changed,
    and add them to ChromaDB. Returns stats dict.

    Args:
        force: if True, re-index everything even if unchanged.
    """
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    md_files = sorted(KNOWLEDGE_DIR.glob("**/*.md"))

    if not md_files:
        return {"files": 0, "chunks": 0, "skipped": 0}

    manifest  = {} if force else _load_manifest()
    model     = _get_model()
    coll      = _get_collection()

    stats = {"files": 0, "chunks_added": 0, "files_skipped": 0}

    for md_path in md_files:
        file_key  = str(md_path.relative_to(KNOWLEDGE_DIR))
        file_hash = _file_hash(md_path)

        if not force and manifest.get(file_key) == file_hash:
            stats["files_skipped"] += 1
            continue

        # Remove old chunks for this file before re-indexing
        try:
            existing = coll.get(where={"source": file_key})
            if existing["ids"]:
                coll.delete(ids=existing["ids"])
        except Exception:
            pass

        # Read and chunk
        text   = md_path.read_text(encoding="utf-8")
        chunks = _chunk_markdown(text, file_key)
        if not chunks:
            continue

        # Embed
        texts      = [c["text"] for c in chunks]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        # Build IDs and metadata
        ids       = [f"{file_key}::chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": c["source"], "heading": c["heading"]} for c in chunks]

        coll.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        manifest[file_key] = file_hash
        stats["files"]        += 1
        stats["chunks_added"] += len(chunks)

    _save_manifest(manifest)
    return stats


# ── Retrieval helpers ─────────────────────────────────────────────────────────
def _embed_query(query: str) -> List[float]:
    return _get_model().encode([query], show_progress_bar=False)[0].tolist()


def _format_chunks(results: Dict) -> str:
    """
    Format ChromaDB query results into a clean string block for the LLM prompt.
    """
    docs      = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas",  [[]])[0]
    if not docs:
        return ""

    lines = []
    for doc, meta in zip(docs, metadatas):
        source  = meta.get("source", "unknown")
        heading = meta.get("heading", "")
        label   = f"[{source}] {('— ' + heading) if heading else ''}".strip()
        lines.append(f"{label}\n{doc.strip()}")

    return "\n\n---\n\n".join(lines)


def retrieve_for_equipment(
    material_number: str,
    kit_types: Optional[List[str]] = None,
    discrepancies: Optional[List[str]] = None,
    top_k: int = TOP_K,
) -> str:
    """
    Retrieve knowledge base chunks relevant to this equipment's analysis.

    Args:
        material_number: e.g. "3000-MAT-CUR-150"
        kit_types: list of kit type strings e.g. ["MK_Safety", "UK_Improvement"]
        discrepancies: list of discrepancy descriptions from Agent 1 analysis
        top_k: number of chunks to return

    Returns:
        Formatted string ready to inject into the Agent 1 prompt.
    """
    coll = _get_collection()
    if coll.count() == 0:
        return ""

    # Build a rich query combining all context signals
    kit_str  = ", ".join(kit_types)   if kit_types      else ""
    disc_str = "; ".join(discrepancies) if discrepancies else ""

    query = " ".join(filter(None, [
        f"equipment {material_number}",
        f"kit types {kit_str}"   if kit_str  else "",
        f"issues: {disc_str}"    if disc_str else "",
        "installation requirements prerequisites mandatory safety",
    ]))

    results = coll.query(
        query_embeddings=[_embed_query(query)],
        n_results=min(top_k, coll.count()),
        include=["documents", "metadatas"],
    )
    return _format_chunks(results)


def retrieve_for_kit(mstk_number: str, top_k: int = TOP_K) -> str:
    """
    Retrieve knowledge base chunks specifically about a kit MSTK.

    Args:
        mstk_number: e.g. "3495770-02002"
        top_k: number of chunks to return

    Returns:
        Formatted string ready to inject into the kit reasoning context.
    """
    coll = _get_collection()
    if coll.count() == 0:
        return ""

    query = (
        f"kit {mstk_number} installation procedure prerequisites "
        f"requirements skills downtime failure mode"
    )
    results = coll.query(
        query_embeddings=[_embed_query(query)],
        n_results=min(top_k, coll.count()),
        include=["documents", "metadatas"],
    )
    return _format_chunks(results)


def retrieve_raw(query: str, top_k: int = TOP_K) -> str:
    """
    Free-form retrieval for the chat assistant.

    Args:
        query: any natural language question
        top_k: number of chunks to return
    """
    coll = _get_collection()
    if coll.count() == 0:
        return ""

    results = coll.query(
        query_embeddings=[_embed_query(query)],
        n_results=min(top_k, coll.count()),
        include=["documents", "metadatas"],
    )
    return _format_chunks(results)


def get_index_stats() -> Dict:
    """Return stats about the current index (file count, chunk count)."""
    try:
        coll     = _get_collection()
        manifest = _load_manifest()
        return {
            "files":  len(manifest),
            "chunks": coll.count(),
            "ready":  coll.count() > 0,
        }
    except Exception:
        return {"files": 0, "chunks": 0, "ready": False}


# ── Standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Building knowledge base index...")
    stats = build_index()
    print(f"  Files indexed : {stats['files']}")
    print(f"  Chunks added  : {stats['chunks_added']}")
    print(f"  Files skipped : {stats['files_skipped']}")

    index_stats = get_index_stats()
    print(f"\nIndex ready: {index_stats['ready']}")
    print(f"Total chunks in store: {index_stats['chunks']}")

    if index_stats["ready"]:
        print("\nTest retrieval for equipment...")
        result = retrieve_for_equipment(
            material_number="3000-MAT-CUR-150",
            kit_types=["MK_Safety"],
            discrepancies=["volume drift"],
        )
        print(result[:500] if result else "No results.")
