"""
Retrieval policy on top of Chroma + sentence-transformers.

Design goals
------------
- **Stage 1 (today):** dense semantic search with optional metadata filters.
- **Stage 2 (extension hook):** oversample + post-filter / re-rank without
  breaking callers — increase `oversample` or plug in a cross-encoder later.
- **Stage 3 (future):** true hybrid (BM25 / sparse) or hosted vector DB —
  keep the `retrieve()` signature stable and swap `KnowledgeStore` internals.

All agent-facing retrieval should go through `retrieve()` so techniques stay
centralized.
"""

from __future__ import annotations

import os
import re
from typing import Any

from knowledge_store import knowledge_store

# Keep in sync with knowledge_graph.classify_partselect_url vocabulary.
PAGE_KINDS = frozenset(
    {
        "model",
        "part",
        "blog",
        "repair",
        "category",
        "ptl",
        "other",
        "external",
        "unknown",
    }
)


def _token_boost(query: str, doc: str) -> float:
    """Cheap lexical overlap score for re-ranking (no extra index)."""
    q = (query or "").lower()
    d = (doc or "").lower()
    toks = {t for t in re.findall(r"[a-z0-9]{4,}", q) if len(t) >= 4}
    if not toks:
        return 0.0
    hits = sum(1 for t in toks if t in d)
    return hits / max(1, len(toks))


def retrieve(
    query: str,
    *,
    top_k: int = 5,
    page_kind: str | None = None,
    oversample: int = 1,
    rerank_lexical: bool = False,
) -> dict[str, Any]:
    """
    Primary retrieval entry for tools and future APIs.

    Parameters
    ----------
    query:
        Natural language or keyword query (embedded as-is).
    top_k:
        Number of hits to return after optional re-ranking.
    page_kind:
        If set, restrict to Chroma metadata ``page_kind`` (e.g. ``model``).
    oversample:
        Request ``top_k * oversample`` (capped by PARTSELECT_QUERY_MAX_TOP_K)
        from Chroma before truncating / re-ranking.
    rerank_lexical:
        If True, re-order oversampled hits using token overlap with ``query``.
    """
    q = (query or "").strip()
    if not q:
        return {"matches": [], "strategy": "none", "reason": "empty_query"}

    if page_kind is not None and page_kind not in PAGE_KINDS:
        return {
            "matches": [],
            "strategy": "rejected",
            "reason": f"invalid_page_kind:{page_kind}",
        }

    store = knowledge_store()
    max_k = int(os.environ.get("PARTSELECT_QUERY_MAX_TOP_K", "12"))
    mult = max(1, int(oversample))
    n_fetch = min(max_k, max(top_k, top_k * mult))

    where = {"page_kind": page_kind} if page_kind else None
    raw = store.query(q, top_k=n_fetch, where=where)
    matches: list[dict] = list(raw.get("matches") or [])

    strat = "semantic"
    if page_kind:
        strat += "+metadata(page_kind)"
    if rerank_lexical and matches:
        strat += "+lexical_rerank"
        matches.sort(
            key=lambda m: (
                -_token_boost(q, str(m.get("text") or "")),
                float(m.get("distance") or 0.0),
            )
        )
    matches = matches[: max(1, top_k)]

    return {
        "matches": matches,
        "strategy": strat,
        "requested_top_k": top_k,
        "fetched": n_fetch,
        "page_kind_filter": page_kind,
    }
