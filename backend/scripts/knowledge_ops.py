#!/usr/bin/env python3
"""
Operational playbook for the knowledge layer (vector DB + graph + exports).

Run from backend/ (or anywhere, paths are resolved relative to backend root):

  cd backend && source venv/bin/activate && python scripts/knowledge_ops.py plan
  cd backend && source venv/bin/activate && python scripts/knowledge_ops.py validate
  cd backend && source venv/bin/activate && python scripts/knowledge_ops.py export-edges
  cd backend && source venv/bin/activate && python scripts/knowledge_ops.py build-graph
  cd backend && source venv/bin/activate && python scripts/knowledge_ops.py rebuild-index
  cd backend && source venv/bin/activate && python scripts/knowledge_ops.py prepare-all

Typical release prep (no re-embed unless corpus changed):

  prepare-all --skip-rebuild

Full rebuild after corpus edits (slow, CPU-heavy):

  prepare-all

Environment knobs (see knowledge_stack.format_stack_plan):

  PARTSELECT_CHAT_MODEL, PARTSELECT_EMBED_MODEL, PARTSELECT_CHROMA_PATH,
  PARTSELECT_KNOWLEDGE_RAW_DIR, PARTSELECT_GRAPH_SQLITE, PARTSELECT_EMBED_IGNORE_PROXY, ...
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from graph_sqlite import build_knowledge_graph_sqlite  # noqa: E402
from knowledge_export import run_export_url_edges  # noqa: E402
from knowledge_stack import format_stack_plan, stack_dict  # noqa: E402
def cmd_plan(_args: argparse.Namespace) -> int:
    print(format_stack_plan(), flush=True)
    return 0


def cmd_validate(_args: argparse.Namespace) -> int:
    s = stack_dict(_BACKEND_ROOT)
    corpus = Path(s["url_corpus_jsonl"])
    chroma = Path(s["chroma_path"])
    graph = Path(s["graph_sqlite"])

    print("validate: corpus …", flush=True)
    if not corpus.is_file():
        print(f"  MISSING {corpus}", flush=True)
        return 1
    n_lines = sum(1 for _ in corpus.open("r", encoding="utf-8", errors="ignore"))
    print(f"  url_corpus lines: {n_lines}", flush=True)

    print("validate: chroma …", flush=True)
    if not chroma.is_dir():
        print(f"  MISSING index dir {chroma}", flush=True)
        return 1
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=str(chroma), settings=Settings(anonymized_telemetry=False)
        )
        col = client.get_collection(s["chroma_collection"])
        print(f"  collection={s['chroma_collection']} count={col.count()}", flush=True)
    except Exception as e:
        print(f"  Chroma error: {e}", flush=True)
        return 1

    print("validate: graph sqlite …", flush=True)
    if graph.is_file():
        con = sqlite3.connect(str(graph))
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM pages")
        pc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges")
        ec = cur.fetchone()[0]
        con.close()
        print(f"  {graph} pages={pc} edges={ec}", flush=True)
    else:
        print(f"  (optional) not built yet: {graph}", flush=True)

    return 0


def cmd_export_edges(_args: argparse.Namespace) -> int:
    s = stack_dict(_BACKEND_ROOT)
    out = Path(s["edges_jsonl"])
    n = run_export_url_edges(Path(s["url_corpus_jsonl"]), out)
    print(f"export-edges: wrote {n} lines -> {out}", flush=True)
    return 0


def cmd_build_graph(_args: argparse.Namespace) -> int:
    s = stack_dict(_BACKEND_ROOT)
    stats = build_knowledge_graph_sqlite(
        Path(s["url_corpus_jsonl"]),
        Path(s["graph_sqlite"]),
    )
    print(json.dumps(stats, indent=2), flush=True)
    return 0


def cmd_rebuild_index(_args: argparse.Namespace) -> int:
    script = _BACKEND_ROOT / "scripts" / "rebuild_knowledge_index.py"
    r = subprocess.run([sys.executable, str(script)], cwd=str(_BACKEND_ROOT))
    return int(r.returncode)


def cmd_prepare_all(args: argparse.Namespace) -> int:
    rc = cmd_plan(args)
    if rc:
        return rc
    rc = cmd_validate(args)
    if rc:
        return rc
    rc = cmd_export_edges(args)
    if rc:
        return rc
    rc = cmd_build_graph(args)
    if rc:
        return rc
    if args.skip_rebuild:
        print("prepare-all: skipped rebuild-index (--skip-rebuild)", flush=True)
    else:
        print("prepare-all: running rebuild-index …", flush=True)
        rc = cmd_rebuild_index(args)
        if rc:
            return rc
    print("prepare-all: done.", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Knowledge pipeline operations")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("plan", help="Print stack (LLM, embeddings, paths)")
    sub.add_parser("validate", help="Check corpus + Chroma + optional graph DB")
    sub.add_parser("export-edges", help="Write url_edges.jsonl from url_corpus")
    sub.add_parser("build-graph", help="Build SQLite knowledge_graph.sqlite")
    sub.add_parser("rebuild-index", help="Run rebuild_knowledge_index.py (slow)")
    p_all = sub.add_parser(
        "prepare-all",
        help="plan, validate, export-edges, build-graph; optional rebuild-index",
    )
    p_all.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="Skip Chroma rebuild (use after index already matches corpus)",
    )

    args = ap.parse_args()
    handlers = {
        "plan": cmd_plan,
        "validate": cmd_validate,
        "export-edges": cmd_export_edges,
        "build-graph": cmd_build_graph,
        "rebuild-index": cmd_rebuild_index,
        "prepare-all": cmd_prepare_all,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
