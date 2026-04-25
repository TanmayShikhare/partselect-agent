"""
Build a small SQLite knowledge graph from url_corpus.jsonl.

Nodes are primarily **pages** (URL). Optional **model_key** edges link MFG tokens
to model pages. **Inventory** edges link pages back to the source CSV stem.

This complements Chroma (vector similarity); use SQL for exact URL / model
lookups and multi-hop planning without pulling a full Neo4j stack yet.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from knowledge_graph import classify_partselect_url, model_slug_from_url


def build_knowledge_graph_sqlite(
    corpus_path: Path,
    out_path: Path,
) -> dict[str, int]:
    corpus_path = corpus_path.resolve()
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(str(out_path))
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE meta (k TEXT PRIMARY KEY NOT NULL, v TEXT NOT NULL)"
    )
    cur.execute("INSERT INTO meta VALUES ('schema_version', '1')")

    cur.execute(
        """
        CREATE TABLE pages (
            url TEXT PRIMARY KEY NOT NULL,
            page_kind TEXT NOT NULL,
            source_csv TEXT,
            model_key TEXT,
            fetched_via TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE edges (
            src TEXT NOT NULL,
            rel TEXT NOT NULL,
            dst TEXT NOT NULL,
            PRIMARY KEY (src, rel, dst)
        )
        """
    )
    cur.execute("CREATE INDEX idx_edges_src ON edges(src)")
    cur.execute("CREATE INDEX idx_edges_dst ON edges(dst)")
    cur.execute("CREATE INDEX idx_edges_rel ON edges(rel)")
    cur.execute("CREATE INDEX idx_pages_kind ON pages(page_kind)")
    cur.execute("CREATE INDEX idx_pages_model ON pages(model_key)")

    pages = 0
    edges = 0

    def add_edge(src: str, rel: str, dst: str) -> None:
        nonlocal edges
        cur.execute(
            "INSERT OR IGNORE INTO edges (src, rel, dst) VALUES (?, ?, ?)",
            (src, rel, dst),
        )
        if cur.rowcount:
            edges += 1

    with corpus_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            url = str(row.get("url") or "").strip()
            if not url:
                continue
            kind = classify_partselect_url(url)
            slug = model_slug_from_url(url) or ""
            src_csv = str(row.get("source_csv") or "").strip()
            via = str(row.get("fetched_via") or "").strip()
            cur.execute(
                """
                INSERT OR REPLACE INTO pages (url, page_kind, source_csv, model_key, fetched_via)
                VALUES (?, ?, ?, ?, ?)
                """,
                (url, kind, src_csv or None, slug or None, via or None),
            )
            pages += 1

            add_edge(url, "rdf:type", kind)
            if src_csv:
                add_edge(url, "from_csv", src_csv)
            if slug:
                add_edge(slug, "model_page", url)
                add_edge(url, "model_key", slug)

    conn.commit()
    conn.close()
    return {"pages_upserted": pages, "edges_inserted": edges, "out": str(out_path)}
