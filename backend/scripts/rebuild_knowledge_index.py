from __future__ import annotations

import argparse

from knowledge_store import KnowledgeStore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Limit chunks (0 = no limit)")
    args = ap.parse_args()

    store = KnowledgeStore()
    out = store.rebuild(limit=(args.limit or None))
    print(out)


if __name__ == "__main__":
    main()

