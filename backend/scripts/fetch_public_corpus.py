from __future__ import annotations

import argparse
from pathlib import Path

import httpx


DATASETS = {
    # CSV corpus (parts/repairs/blogs)
    "zehuiwu": [
        (
            "all_parts.csv",
            "https://raw.githubusercontent.com/zehuiwu/partselect-agent/main/data/all_parts.csv",
        ),
        (
            "all_repairs.csv",
            "https://raw.githubusercontent.com/zehuiwu/partselect-agent/main/data/all_repairs.csv",
        ),
        (
            "partselect_blogs.csv",
            "https://raw.githubusercontent.com/zehuiwu/partselect-agent/main/data/partselect_blogs.csv",
        ),
    ],
    # JSONL corpus (products/repairs/blogs)
    "vaibhav": [
        (
            "product_details_with_main_image.jsonl",
            "https://raw.githubusercontent.com/VaibhavBhandari2999/PartSelect_RAG/main/backend/data/parts1/enriched/product_details_with_main_image.jsonl",
        ),
        (
            "repairs.jsonl",
            "https://raw.githubusercontent.com/VaibhavBhandari2999/PartSelect_RAG/main/backend/data/repair_data/repairs.jsonl",
        ),
        (
            "filtered_articles.jsonl",
            "https://raw.githubusercontent.com/VaibhavBhandari2999/PartSelect_RAG/main/backend/data/blog_data/filtered_articles.jsonl",
        ),
    ],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=sorted(DATASETS.keys()), required=True)
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]
    out_dir = base / "knowledge" / "raw" / "data" / "public"
    out_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        for filename, url in DATASETS[args.source]:
            out_path = out_dir / f"{args.source}__{filename}"
            print(f"Downloading {url} -> {out_path}")
            r = client.get(url)
            r.raise_for_status()
            out_path.write_bytes(r.content)

    print({"ok": True, "out_dir": str(out_dir)})


if __name__ == "__main__":
    main()

