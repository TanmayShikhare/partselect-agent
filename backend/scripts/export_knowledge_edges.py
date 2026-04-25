"""
Export lightweight graph edges from url_corpus.jsonl for external KG tools.

Outputs JSONL lines:
  {"subject": "<url>", "predicate": "from_csv", "object": "<source_csv>", "page_kind": "..."}

Run from repo root:
  cd backend && source venv/bin/activate && python scripts/export_knowledge_edges.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from knowledge_export import run_export_url_edges  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--corpus",
        default="knowledge/raw/data/url_corpus.jsonl",
        help="Path relative to backend/",
    )
    ap.add_argument(
        "--out",
        default="knowledge/raw/graph/url_edges.jsonl",
        help="Output JSONL relative to backend/",
    )
    args = ap.parse_args()
    corpus = (_BACKEND_ROOT / args.corpus).resolve()
    out_path = (_BACKEND_ROOT / args.out).resolve()
    n = run_export_url_edges(corpus, out_path)
    print(f"Wrote {n} edges to {out_path}", flush=True)


if __name__ == "__main__":
    main()
