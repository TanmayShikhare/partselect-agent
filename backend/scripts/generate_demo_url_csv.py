from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import httpx

# Ensure backend root is importable when running as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

load_dotenv(_BACKEND_ROOT / ".env")

from scraper import fetch_html_via_scrapingbee  # noqa: E402


def _abs_ps_url(href: str) -> str | None:
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/"):
        href = "https://www.partselect.com" + href
    if not href.startswith("http"):
        return None
    m = re.search(r"/PS(\d{4,12})\b", href, re.IGNORECASE)
    if not m:
        return None
    return f"https://www.partselect.com/PS{m.group(1)}.htm"


def _norm_url(href: str) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    if href.startswith("/"):
        href = "https://www.partselect.com" + href
    if not href.startswith("http"):
        return None
    return href


async def _extract_links_from_html(html: str, model: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    part_urls: list[str] = []
    follow_urls: list[str] = []
    model_upper = model.upper()

    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        absu = _norm_url(href)
        if not absu:
            continue
        psu = _abs_ps_url(absu)
        if psu:
            part_urls.append(psu)
            continue
        # Follow model section/category pages to discover more parts.
        if f"/Models/{model_upper}/" in absu and "Symptoms" not in absu:
            follow_urls.append(absu.split("#", 1)[0])

    # Dedup preserve order
    def _dedup(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for u in seq:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out

    return _dedup(part_urls), _dedup(follow_urls)


async def _extract_part_urls_from_model(model: str, max_pages: int = 10) -> list[str]:
    model = (model or "").strip()
    if not model:
        return []
    start_url = f"https://www.partselect.com/Models/{model}/"
    queue: list[str] = [start_url]
    seen_pages: set[str] = set()
    part_urls: list[str] = []

    while queue and len(seen_pages) < max_pages:
        url = queue.pop(0)
        if url in seen_pages:
            continue
        seen_pages.add(url)
        html = await fetch_html_via_scrapingbee(url)
        if not html:
            continue
        parts, follows = await _extract_links_from_html(html, model=model)
        part_urls.extend(parts)
        for fu in follows:
            if fu not in seen_pages:
                queue.append(fu)

    # Dedup parts preserve order
    seen: set[str] = set()
    out: list[str] = []
    for u in part_urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--models",
        nargs="+",
        default=["WDT780SAEM1", "WRS325SDHZ", "WRF535SWHZ"],
        help="Model numbers to seed from.",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max URLs to write (part pages + model pages).",
    )
    ap.add_argument(
        "--out",
        default="knowledge/raw/urls_local/demo_urls.csv",
        help="Output CSV path (relative to backend/).",
    )
    args = ap.parse_args()

    out_path = (_BACKEND_ROOT / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    for m in args.models:
        m_up = m.strip().upper()
        if not m_up:
            continue
        urls.append(f"https://www.partselect.com/Models/{m_up}/")
        part_urls = await _extract_part_urls_from_model(m_up, max_pages=12)
        urls.extend(part_urls)
        if len(urls) >= (args.limit * 2):
            break

    # Dedup + cap
    seen: set[str] = set()
    final: list[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        final.append(u)
        if len(final) >= args.limit:
            break

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["url"])
        w.writeheader()
        for u in final:
            w.writerow({"url": u})

    print(f"Wrote {len(final)} URLs -> {out_path}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

