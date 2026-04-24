from __future__ import annotations

import argparse
import csv
import gzip
import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator


def _iter_loc_text(xml_bytes: bytes) -> Iterator[str]:
    it = ET.iterparse(io.BytesIO(xml_bytes), events=("end",))
    for _event, elem in it:
        if elem.tag.endswith("loc") and elem.text:
            yield elem.text.strip()
        elem.clear()


def _filter_in_scope(url: str) -> bool:
    u = url.lower()
    return ("refrigerator" in u) or ("dishwasher" in u)


def write_csv(path: Path, urls: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["url"])
        for u in urls:
            w.writerow([u])
    return len(urls)


def classify_filename(name: str) -> str:
    n = name.lower()
    if "repairs" in n:
        return "repairs"
    if "blogs" in n:
        return "blogs"
    if "categorypages" in n:
        return "categories"
    if "models" in n:
        return "models"
    if "partdetail" in n:
        return "parts"
    if "ptls" in n:
        return "ptls"
    return "other"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in-dir",
        default="knowledge/raw/sitemaps",
        help="Input directory with .xml.gz sitemaps (relative to backend/)",
    )
    ap.add_argument(
        "--out-dir",
        default="knowledge/raw/urls_local",
        help="Output directory for CSVs (relative to backend/)",
    )
    ap.add_argument(
        "--max-urls",
        type=int,
        default=0,
        help="Limit URLs per sitemap file (0 = no limit)",
    )
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]
    in_dir = (base / args.in_dir).resolve()
    out_dir = (base / args.out_dir).resolve()

    if not in_dir.exists():
        raise SystemExit(f"Input dir not found: {in_dir}")

    grouped: dict[str, set[str]] = {}

    for gz_path in sorted(in_dir.glob("*.xml.gz")):
        cat = classify_filename(gz_path.name)
        raw = gzip.decompress(gz_path.read_bytes())
        count = 0
        for url in _iter_loc_text(raw):
            if not _filter_in_scope(url):
                continue
            grouped.setdefault(cat, set()).add(url)
            count += 1
            if args.max_urls and count >= args.max_urls:
                break
        print(f"{gz_path.name}: collected {count} in-scope urls (category={cat})")

    for cat, urls in grouped.items():
        if not urls:
            continue
        out_path = out_dir / f"{cat}_urls.csv"
        n = write_csv(out_path, sorted(urls))
        print(f"Wrote {n} -> {out_path}")


if __name__ == "__main__":
    main()

