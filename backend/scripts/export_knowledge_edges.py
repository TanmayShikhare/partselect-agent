"""
Export lightweight graph edges from url_corpus.jsonl for external KG tools.

Outputs JSONL lines:
  {"subject": "<url>", "predicate": "from_csv", "object": "<source_csv>", "page_kind": "..."}

Run from repo root:
  cd backend && source venv/bin/activate && python scripts/export_knowledge_edges.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from knowledge_graph import classify_partselect_url  # noqa: E402


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
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n = 0
    with corpus.open("r", encoding="utf-8", errors="ignore") as fin, out_path.open(
        "w", encoding="utf-8"
    ) as fout:
        for line in fin:
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
            src_csv = str(row.get("source_csv") or "").strip()
            edge = {
                "subject": url,
                "predicate": "from_csv",
                "object": src_csv,
                "page_kind": classify_partselect_url(url),
            }
            fout.write(json.dumps(edge, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} edges to {out_path}", flush=True)


if __name__ == "__main__":
    main()
