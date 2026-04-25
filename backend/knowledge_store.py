from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import chromadb
from chromadb.config import Settings
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from knowledge_graph import corpus_row_meta


@dataclass(frozen=True)
class KnowledgeChunk:
    text: str
    source: str
    chunk_id: str
    meta: dict


def _chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    t = (text or "").strip()
    if not t:
        return []
    out: list[str] = []
    i = 0
    n = len(t)
    while i < n:
        j = min(n, i + chunk_size)
        out.append(t[i:j].strip())
        if j >= n:
            break
        i = max(0, j - overlap)
    return [c for c in out if c]


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n\n".join(parts).strip()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue


def _iter_csv_rows(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def _row_to_text(row: dict) -> str:
    # Keep it generic so any CSV/JSONL schema works.
    # We preserve key/value formatting so retrieval can match part numbers, models, etc.
    lines: list[str] = []
    for k, v in row.items():
        if v is None:
            continue
        sv = str(v).strip()
        if not sv:
            continue
        lines.append(f"{k}: {sv}")
    return "\n".join(lines).strip()


def _is_url_corpus_row(row: dict) -> bool:
    return isinstance(row, dict) and "text" in row and (
        "url" in row or "source_csv" in row or "fetched_via" in row
    )


def _url_corpus_embed_text(row: dict) -> str | None:
    body = (row.get("text") or "").strip()
    if not body:
        return None
    url = str(row.get("url") or "").strip()
    if url:
        return f"Source URL: {url}\n\n{body}"
    return body


def iter_knowledge_chunks(raw_dir: Path) -> Iterable[KnowledgeChunk]:
    raw_dir = raw_dir.resolve()
    if not raw_dir.exists():
        return

    for path in sorted(raw_dir.rglob("*")):
        if path.is_dir():
            continue
        if path.name.startswith("."):
            continue

        ext = path.suffix.lower()
        rel = str(path.relative_to(raw_dir))

        # Don't index URL inventories; index content corpora/docs instead.
        if rel.startswith("urls_local/") or rel.startswith("urls/") or rel.startswith(
            "sitemaps/"
        ):
            continue

        try:
            if ext in {".md", ".txt"}:
                text = _read_text(path)
                for idx, chunk in enumerate(_chunk_text(text)):
                    yield KnowledgeChunk(
                        text=chunk,
                        source=rel,
                        chunk_id=f"{rel}::chunk:{idx}",
                        meta={"type": "doc", "path": rel},
                    )

            elif ext == ".pdf":
                text = _read_pdf(path)
                for idx, chunk in enumerate(_chunk_text(text)):
                    yield KnowledgeChunk(
                        text=chunk,
                        source=rel,
                        chunk_id=f"{rel}::chunk:{idx}",
                        meta={"type": "pdf", "path": rel},
                    )

            elif ext == ".jsonl":
                for i, row in enumerate(_iter_jsonl(path)):
                    if not isinstance(row, dict):
                        continue
                    if _is_url_corpus_row(row):
                        text = _url_corpus_embed_text(row)
                        if not text:
                            continue
                        base_meta = {
                            "type": "url_corpus",
                            "path": rel,
                            "row": i,
                            **corpus_row_meta(row),
                        }
                    else:
                        text = _row_to_text(row)
                        base_meta = {"type": "jsonl", "path": rel, "row": i}
                    for idx, chunk in enumerate(_chunk_text(text)):
                        yield KnowledgeChunk(
                            text=chunk,
                            source=rel,
                            chunk_id=f"{rel}::row:{i}::chunk:{idx}",
                            meta=base_meta,
                        )

            elif ext == ".csv":
                for i, row in enumerate(_iter_csv_rows(path)):
                    text = _row_to_text(row)
                    for idx, chunk in enumerate(_chunk_text(text)):
                        yield KnowledgeChunk(
                            text=chunk,
                            source=rel,
                            chunk_id=f"{rel}::row:{i}::chunk:{idx}",
                            meta={"type": "csv", "path": rel, "row": i},
                        )
        except Exception:
            # Best effort: skip malformed files/rows.
            continue


class KnowledgeStore:
    """
    Local Chroma persistence + sentence-transformers embeddings.

    Configuration (optional env overrides for deployment / scale tuning):
    - PARTSELECT_KNOWLEDGE_RAW_DIR: relative to backend/ (default knowledge/raw)
    - PARTSELECT_CHROMA_PATH: relative to backend/ (default knowledge/index)
    - PARTSELECT_CHROMA_COLLECTION: collection name (default partselect_knowledge)
    - PARTSELECT_EMBED_MODEL: sentence-transformers model id
    - PARTSELECT_KNOWLEDGE_EMBED_BATCH: embedding batch size (default 256)
    - PARTSELECT_EMBED_IGNORE_PROXY: if "1"/"true", strip HTTP(S)_PROXY before loading
      the embedding model (useful when a corporate proxy blocks Hugging Face).
    """

    def __init__(
        self,
        raw_dir: str | None = None,
        index_dir: str | None = None,
        collection: str | None = None,
        embed_model: str | None = None,
    ) -> None:
        base = Path(__file__).resolve().parent
        raw_dir = raw_dir or os.environ.get("PARTSELECT_KNOWLEDGE_RAW_DIR", "knowledge/raw")
        index_dir = index_dir or os.environ.get("PARTSELECT_CHROMA_PATH", "knowledge/index")
        collection = collection or os.environ.get(
            "PARTSELECT_CHROMA_COLLECTION", "partselect_knowledge"
        )
        embed_model = embed_model or os.environ.get(
            "PARTSELECT_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.raw_dir = (base / raw_dir).resolve()
        self.index_dir = (base / index_dir).resolve()
        self.collection_name = collection
        self.embed_model_name = embed_model
        self.embed_batch_size = max(
            32,
            int(os.environ.get("PARTSELECT_KNOWLEDGE_EMBED_BATCH", "256")),
        )

        # Ensure model caches are writable in constrained environments.
        hf_home = (base / "knowledge" / ".hf").resolve()
        os.environ.setdefault("HF_HOME", str(hf_home))
        os.environ.setdefault(
            "SENTENCE_TRANSFORMERS_HOME", str(hf_home / "sentence-transformers")
        )

        self._embedder: Optional[SentenceTransformer] = None
        self._client = chromadb.PersistentClient(
            path=str(self.index_dir),
            settings=Settings(anonymized_telemetry=False),
        )

    def _embedder_instance(self) -> SentenceTransformer:
        if self._embedder is None:
            if os.environ.get("PARTSELECT_EMBED_IGNORE_PROXY", "").strip().lower() in {
                "1",
                "true",
                "yes",
            }:
                for k in list(os.environ):
                    if k.lower() in {"http_proxy", "https_proxy", "all_proxy"}:
                        os.environ.pop(k, None)
            self._embedder = SentenceTransformer(self.embed_model_name)
        return self._embedder

    def _collection(self):
        return self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"embed_model": self.embed_model_name},
        )

    def rebuild(self, limit: int | None = None) -> dict:
        self.index_dir.mkdir(parents=True, exist_ok=True)
        col = self._collection()

        # Recreate collection by deleting then re-creating (simple + reliable).
        try:
            self._client.delete_collection(self.collection_name)
        except Exception:
            pass
        col = self._collection()

        embedder = self._embedder_instance()

        ids: list[str] = []
        docs: list[str] = []
        metas: list[dict] = []

        count = 0
        batch = self.embed_batch_size
        progress_every = max(500, batch)
        for chunk in iter_knowledge_chunks(self.raw_dir):
            meta = {**chunk.meta, "source": chunk.source}
            # Convenience for LLM citations (duplicate of canonical_url when present).
            if meta.get("canonical_url") and not meta.get("url"):
                meta["url"] = meta["canonical_url"]
            ids.append(chunk.chunk_id)
            docs.append(chunk.text)
            metas.append(meta)
            count += 1
            if limit and count >= limit:
                break

            # Batch insert to keep memory reasonable.
            if len(ids) >= batch:
                embeddings = embedder.encode(docs).tolist()
                col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
                ids, docs, metas = [], [], []
                if count % progress_every == 0:
                    print(
                        f"knowledge index progress: chunks_indexed={count}",
                        flush=True,
                    )

        if ids:
            embeddings = embedder.encode(docs).tolist()
            col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

        return {
            "ok": True,
            "chunks_indexed": count,
            "raw_dir": str(self.raw_dir),
            "index_dir": str(self.index_dir),
            "collection": self.collection_name,
            "embed_model": self.embed_model_name,
            "embed_batch_size": batch,
        }

    def query(
        self,
        query: str,
        top_k: int = 5,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> dict:
        q = (query or "").strip()
        if not q:
            return {"matches": []}

        col = self._collection()
        embedder = self._embedder_instance()
        q_emb = embedder.encode([q]).tolist()[0]

        max_k = int(os.environ.get("PARTSELECT_QUERY_MAX_TOP_K", "12"))
        q_kw: dict = {
            "query_embeddings": [q_emb],
            "n_results": max(1, min(int(top_k), max_k)),
            "include": ["documents", "metadatas", "distances"],
        }
        if where is not None:
            q_kw["where"] = where
        if where_document is not None:
            q_kw["where_document"] = where_document
        res = col.query(**q_kw)

        matches: list[dict] = []
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            m = meta or {}
            url = m.get("url") or m.get("canonical_url") or ""
            matches.append(
                {
                    "text": doc,
                    "url": url,
                    "source": m.get("source", ""),
                    "meta": m,
                    "distance": dist,
                }
            )
        return {"matches": matches}


_STORE: KnowledgeStore | None = None


def knowledge_store() -> KnowledgeStore:
    global _STORE
    if _STORE is None:
        _STORE = KnowledgeStore()
    return _STORE

