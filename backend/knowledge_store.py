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
                    text = _row_to_text(row)
                    for idx, chunk in enumerate(_chunk_text(text)):
                        yield KnowledgeChunk(
                            text=chunk,
                            source=rel,
                            chunk_id=f"{rel}::row:{i}::chunk:{idx}",
                            meta={"type": "jsonl", "path": rel, "row": i},
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
    def __init__(
        self,
        raw_dir: str = "knowledge/raw",
        index_dir: str = "knowledge/index",
        collection: str = "partselect_knowledge",
        embed_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        base = Path(__file__).resolve().parent
        self.raw_dir = (base / raw_dir).resolve()
        self.index_dir = (base / index_dir).resolve()
        self.collection_name = collection
        self.embed_model_name = embed_model

        self._embedder: Optional[SentenceTransformer] = None
        self._client = chromadb.PersistentClient(
            path=str(self.index_dir),
            settings=Settings(anonymized_telemetry=False),
        )

    def _embedder_instance(self) -> SentenceTransformer:
        if self._embedder is None:
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
        for chunk in iter_knowledge_chunks(self.raw_dir):
            ids.append(chunk.chunk_id)
            docs.append(chunk.text)
            metas.append({**chunk.meta, "source": chunk.source})
            count += 1
            if limit and count >= limit:
                break

            # Batch insert to keep memory reasonable.
            if len(ids) >= 256:
                embeddings = embedder.encode(docs).tolist()
                col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
                ids, docs, metas = [], [], []

        if ids:
            embeddings = embedder.encode(docs).tolist()
            col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

        return {"ok": True, "chunks_indexed": count, "raw_dir": str(self.raw_dir)}

    def query(self, query: str, top_k: int = 5) -> dict:
        q = (query or "").strip()
        if not q:
            return {"matches": []}

        col = self._collection()
        embedder = self._embedder_instance()
        q_emb = embedder.encode([q]).tolist()[0]

        res = col.query(
            query_embeddings=[q_emb],
            n_results=max(1, min(int(top_k), 12)),
            include=["documents", "metadatas", "distances"],
        )

        matches: list[dict] = []
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            matches.append(
                {
                    "text": doc,
                    "source": (meta or {}).get("source", ""),
                    "meta": meta or {},
                    "distance": dist,
                }
            )
        return {"matches": matches}


def knowledge_store() -> KnowledgeStore:
    # Singleton-ish helper (module-level cache).
    global _STORE  # type: ignore
    try:
        return _STORE  # type: ignore
    except Exception:
        _STORE = KnowledgeStore()  # type: ignore
        return _STORE  # type: ignore

