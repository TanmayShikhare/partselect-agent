"""
Lightweight URL / page classification for PartSelect corpora.

Used at index time to attach graph-friendly metadata (page_kind, model_key, …)
to vector chunks without requiring a full graph database. Downstream you can:
- filter Chroma queries by metadata once Chroma supports where= on your version
- import `export_knowledge_edges` output into Neo4j / TigerGraph / etc.
"""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import urlparse

_PARTSELECT_HOST: Final = "partselect.com"

_MODEL_PATH_RE = re.compile(
    r"^/models/([^/]+)/?$",
    re.IGNORECASE,
)


def classify_partselect_url(url: str) -> str:
    """
    Coarse page kind for retrieval filters and graph edges.
    Values are stable lowercase strings.
    """
    u = (url or "").strip()
    if not u:
        return "unknown"
    try:
        p = urlparse(u)
    except Exception:
        return "unknown"
    host = (p.netloc or "").lower()
    if _PARTSELECT_HOST not in host:
        return "external"
    path = (p.path or "").lower()
    if "/models/" in path and "/manufacturer/" not in path and "/mfgmodelnumber/" not in path:
        return "model"
    if "/parts/" in path or "/partdetail/" in path or "ps" in path:
        return "part"
    if "/blog/" in path or "/blogs/" in path:
        return "blog"
    if "/repair/" in path or "symptom" in path:
        return "repair"
    if "/category/" in path or "/categories/" in path:
        return "category"
    if "/advice/" in path or "/ptl" in path:
        return "ptl"
    return "other"


def model_slug_from_url(url: str) -> str | None:
    """PartSelect numeric model token from a /Models/<token>/ URL, or None."""
    u = (url or "").strip()
    if not u:
        return None
    try:
        p = urlparse(u)
    except Exception:
        return None
    if _PARTSELECT_HOST not in (p.netloc or "").lower():
        return None
    m = _MODEL_PATH_RE.match(p.path or "")
    if not m:
        return None
    token = m.group(1)
    if not re.fullmatch(r"[A-Za-z0-9.\-]{4,64}", token):
        return None
    return token


def corpus_row_meta(row: dict) -> dict[str, str]:
    """
    Flat metadata dict safe for Chroma (primitive values only).
    """
    url = str(row.get("url") or "").strip()
    kind = classify_partselect_url(url)
    slug = model_slug_from_url(url) or ""
    out: dict[str, str] = {
        "page_kind": kind,
        "canonical_url": url,
        "model_key": slug,
        "fetched_via": str(row.get("fetched_via") or "").strip(),
        "source_csv": str(row.get("source_csv") or "").strip(),
    }
    return {k: v for k, v in out.items() if v}
