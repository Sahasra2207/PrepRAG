from collections import Counter
from pathlib import Path
import threading
import chromadb
from sentence_transformers import SentenceTransformer

from .config import CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL

_lock = threading.Lock()
_client = None
_collection = None
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        # Downloads the model on first use if it is not cached locally.
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(filename: str, chunks: list[str]) -> int:
    if not chunks:
        return 0

    embedder = _get_embedder()
    embeddings = embedder.encode(chunks, normalize_embeddings=True).tolist()
    collection = _get_collection()

    # Use unique IDs so re-uploading a file does not overwrite unrelated chunks.
    import uuid
    ids = [f"{uuid.uuid4().hex}_{i}" for i in range(len(chunks))]
    metadatas = [{"filename": filename, "chunk_index": i} for i in range(len(chunks))]

    with _lock:
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    return len(chunks)


def query_chunks(question: str, top_k: int = 4) -> list[dict]:
    collection = _get_collection()
    if collection.count() == 0:
        return []

    query_embedding = _get_embedder().encode([question], normalize_embeddings=True).tolist()
    result = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    items = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    for doc, meta, distance in zip(docs, metas, distances):
        items.append({
            "text": doc,
            "filename": (meta or {}).get("filename", "Unknown document"),
            "chunk_index": int((meta or {}).get("chunk_index", 0)),
            "distance": float(distance) if distance is not None else None,
        })
    return items


def list_documents() -> list[dict]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["metadatas"])
    counts = Counter()
    for meta in data.get("metadatas", []):
        if meta:
            counts[meta.get("filename", "Unknown document")] += 1
    return [{"filename": name, "chunks": count} for name, count in sorted(counts.items())]


def total_chunks() -> int:
    return _get_collection().count()


def clear_collection() -> None:
    global _collection
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def get_all_chunks() -> list[dict]:
    """Return indexed text and metadata for local extractive quiz generation."""
    collection = _get_collection()
    if collection.count() == 0:
        return []
    data = collection.get(include=["documents", "metadatas"])
    items = []
    for text, meta in zip(data.get("documents", []), data.get("metadatas", [])):
        meta = meta or {}
        items.append({
            "text": text or "",
            "filename": meta.get("filename", "Unknown document"),
            "chunk_index": int(meta.get("chunk_index", 0)),
        })
    return items
