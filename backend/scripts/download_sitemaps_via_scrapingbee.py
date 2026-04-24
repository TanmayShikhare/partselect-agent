from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv


MASTER_SITEMAP = "https://www.partselect.com/sitemaps/PartSelect.com_Sitemap_Master.xml"


def classify_sitemap(url: str) -> str:
    u = url.lower()
    if "sitemap_repairs" in u:
        return "repairs"
    if "sitemap_blogs" in u:
        return "blogs"
    if "sitemap_categorypages" in u:
        return "categories"
    if "sitemap_ptls" in u:
        return "ptls"
    if "sitemap_models" in u:
        return "models"
    if "sitemap_partdetail" in u:
        return "parts"
    return "other"


def _iter_loc_text(xml_text: str) -> list[str]:
    # Sitemap indexes are simple enough that regex is fine here (fast + no deps).
    # We keep it permissive: <loc>...</loc> can contain whitespace/newlines.
    return [m.group(1).strip() for m in re.finditer(r"<loc>\s*(.*?)\s*</loc>", xml_text)]


def fetch_via_scrapingbee(url: str, api_key: str) -> bytes:
    params = {
        "api_key": api_key,
        "url": url,
        "render_js": "false",
        "block_resources": "true",
    }
    # trust_env=False avoids local proxy env variables breaking calls.
    with httpx.Client(timeout=60.0, follow_redirects=True, trust_env=False) as client:
        r = client.get("https://app.scrapingbee.com/api/v1/", params=params)
        r.raise_for_status()
        return r.content


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out-dir",
        default="knowledge/raw/sitemaps",
        help="Output dir for downloaded sitemaps (relative to backend/)",
    )
    ap.add_argument(
        "--include",
        default="repairs,blogs,models,parts,categories,ptls",
        help="Comma-separated categories: repairs,blogs,models,parts,categories,ptls,other",
    )
    ap.add_argument("--max-sitemaps", type=int, default=0, help="0 = no limit")
    args = ap.parse_args()

    base = Path(__file__).resolve().parents[1]
    load_dotenv(base / ".env")
    api_key = (os.getenv("SCRAPINGBEE_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("SCRAPINGBEE_API_KEY is not set in backend/.env")

    out_dir = (base / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    include = {c.strip().lower() for c in args.include.split(",") if c.strip()}

    master = fetch_via_scrapingbee(MASTER_SITEMAP, api_key).decode("utf-8", errors="ignore")
    sitemap_urls = _iter_loc_text(master)
    chosen: list[str] = []
    for su in sitemap_urls:
        cat = classify_sitemap(su)
        if cat in include:
            chosen.append(su)

    if args.max_sitemaps and args.max_sitemaps > 0:
        chosen = chosen[: args.max_sitemaps]

    for i, su in enumerate(chosen, 1):
        cat = classify_sitemap(su)
        filename = Path(su).name
        dest = out_dir / filename
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[{i}/{len(chosen)}] skip existing {cat}: {filename}")
            continue
        print(f"[{i}/{len(chosen)}] downloading {cat}: {filename}")
        try:
            content = fetch_via_scrapingbee(su, api_key)
        except Exception as e:
            print(f"  failed: {e}")
            continue
        dest.write_bytes(content)
        print(f"  saved {dest} ({len(content)} bytes)")


if __name__ == "__main__":
    main()

