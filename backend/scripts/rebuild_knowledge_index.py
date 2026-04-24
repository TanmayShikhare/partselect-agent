from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from knowledge_store import KnowledgeStore  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Limit chunks (0 = no limit)")
    args = ap.parse_args()

    store = KnowledgeStore()
    out = store.rebuild(limit=(args.limit or None))
    print(out)


if __name__ == "__main__":
    main()

