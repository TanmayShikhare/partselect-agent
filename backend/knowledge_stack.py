"""
Single source of truth for *which models / stores* the knowledge pipeline uses.

Chat model string must stay in sync with `agent.py` unless PARTSELECT_CHAT_MODEL is set.
"""

from __future__ import annotations

import os
from pathlib import Path


def default_chat_model() -> str:
    return os.environ.get("PARTSELECT_CHAT_MODEL", "claude-sonnet-4-6")


def default_embed_model() -> str:
    return os.environ.get(
        "PARTSELECT_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )


def stack_dict(base: Path | None = None) -> dict[str, str]:
    base = base or Path(__file__).resolve().parent
    raw = os.environ.get("PARTSELECT_KNOWLEDGE_RAW_DIR", "knowledge/raw")
    idx = os.environ.get("PARTSELECT_CHROMA_PATH", "knowledge/index")
    coll = os.environ.get("PARTSELECT_CHROMA_COLLECTION", "partselect_knowledge")
    graph = os.environ.get(
        "PARTSELECT_GRAPH_SQLITE", "knowledge/index/knowledge_graph.sqlite"
    )
    return {
        "chat_provider": "Anthropic",
        "chat_model": default_chat_model(),
        "embed_model": default_embed_model(),
        "vector_db": "Chroma (persistent)",
        "chroma_path": str((base / idx).resolve()),
        "chroma_collection": coll,
        "raw_corpus_dir": str((base / raw).resolve()),
        "url_corpus_jsonl": str((base / raw / "data" / "url_corpus.jsonl").resolve()),
        "graph_sqlite": str((base / graph).resolve()),
        "edges_jsonl": str((base / raw / "graph" / "url_edges.jsonl").resolve()),
    }


def format_stack_plan() -> str:
    d = stack_dict()
    lines = [
        "=== PartSelect knowledge stack (env-tunable) ===",
        f"Chat:        {d['chat_provider']}  model={d['chat_model']}",
        f"Embeddings:  {d['embed_model']}  (sentence-transformers, local)",
        f"Vector DB:   {d['vector_db']}",
        f"  path:      {d['chroma_path']}",
        f"  collection:{d['chroma_collection']}",
        f"Corpus raw:  {d['raw_corpus_dir']}",
        f"URL JSONL:   {d['url_corpus_jsonl']}",
        f"Graph SQLite:{d['graph_sqlite']}",
        f"Edges JSONL: {d['edges_jsonl']}",
        "",
        "Retrieval: semantic Chroma (+ optional page_kind metadata, oversample, lexical rerank).",
        "  PARTSELECT_RETRIEVAL_OVERSAMPLE (default 2), PARTSELECT_RETRIEVAL_LEXICAL_RERANK (0/1).",
        "Graph:     SQLite pages + edges beside Chroma; JSONL edges for bulk KG import.",
        "Run:       python scripts/knowledge_ops.py --help",
        "==============================================",
    ]
    return "\n".join(lines)
