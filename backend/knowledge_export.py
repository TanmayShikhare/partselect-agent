"""Export lightweight URL edges JSONL (shared by CLI scripts and ops runner)."""

from __future__ import annotations

import json
from pathlib import Path

from knowledge_graph import classify_partselect_url


def run_export_url_edges(corpus_path: Path, out_path: Path) -> int:
    corpus_path = corpus_path.resolve()
    out_path = out_path.resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with corpus_path.open("r", encoding="utf-8", errors="ignore") as fin, out_path.open(
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
    return n
