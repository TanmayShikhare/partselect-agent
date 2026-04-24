from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Iterable

from playwright.sync_api import sync_playwright


BASE = "https://www.partselect.com"


def _write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def _load_seen(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(path.read_text(encoding="utf-8", errors="ignore").splitlines())


def _mark_seen(path: Path, key: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(key.strip() + "\n")


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _safe_text(el) -> str:
    try:
        return _norm_ws(el.inner_text())
    except Exception:
        return ""


def _safe_attr(el, name: str) -> str:
    try:
        return (el.get_attribute(name) or "").strip()
    except Exception:
        return ""


def collect_part_urls(page, appliance: str, max_pages: int) -> list[str]:
    """
    Collect part URLs from PartSelect's category pages.
    This is best-effort; the site may show bot challenges depending on network.
    """
    urls: set[str] = set()
    start = f"{BASE}/{appliance.title()}-Parts.htm"
    page.goto(start, wait_until="domcontentloaded", timeout=60000)
    time.sleep(1.0)

    # Find links that look like part pages.
    for _ in range(max_pages):
        anchors = page.locator("a[href*='/PS']").all()
        for a in anchors:
            href = _safe_attr(a, "href")
            if not href:
                continue
            if href.startswith("/"):
                href = BASE + href
            if re.search(r"/PS\d+.*\.htm", href, flags=re.IGNORECASE):
                urls.add(href.split("?")[0])

        # Try next button if present.
        next_btn = page.locator("a:has-text('Next')").first
        if next_btn and next_btn.count() > 0:
            try:
                next_btn.click(timeout=2000)
                page.wait_for_load_state("domcontentloaded", timeout=60000)
                time.sleep(0.6)
                continue
            except Exception:
                break
        break

    return sorted(urls)


def scrape_part_page(page, url: str) -> dict:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(0.8)

    title = ""
    h1 = page.locator("h1").first
    if h1 and h1.count() > 0:
        title = _safe_text(h1)

    # Pull some common fields used across implementations.
    body_text = _norm_ws(page.locator("body").inner_text()[:20000])

    ps_match = re.search(r"\bPS\d{6,}\b", body_text)
    mfg_match = re.search(r"\bManufacturer\s*#:\s*([A-Z0-9\-]+)\b", body_text, flags=re.IGNORECASE)

    price = ""
    price_el = page.locator("span.price, [data-testid='price']").first
    if price_el and price_el.count() > 0:
        price = _safe_text(price_el)

    return {
        "type": "part",
        "url": url,
        "name": title,
        "part_number": (ps_match.group(0) if ps_match else ""),
        "manufacturer_part_number": (mfg_match.group(1) if mfg_match else ""),
        "price": price,
        "text": body_text,
        "scraped_at": int(time.time()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--appliance", choices=["Refrigerator", "Dishwasher"], default="Refrigerator")
    ap.add_argument("--max-pages", type=int, default=3)
    ap.add_argument("--max-parts", type=int, default=30)
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    base_dir = Path(__file__).resolve().parents[1]
    out_dir = base_dir / "knowledge" / "raw" / "data"
    out_jsonl = out_dir / f"parts_{args.appliance.lower()}.jsonl"
    seen_path = out_dir / f"parts_{args.appliance.lower()}.seen.txt"
    seen = _load_seen(seen_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()

        part_urls = collect_part_urls(page, args.appliance, max_pages=args.max_pages)
        part_urls = [u for u in part_urls if u not in seen][: args.max_parts]

        rows: list[dict] = []
        for i, url in enumerate(part_urls, 1):
            try:
                row = scrape_part_page(page, url)
                rows.append(row)
                _mark_seen(seen_path, url)
                print(f"[{i}/{len(part_urls)}] scraped {url}")
            except Exception as e:
                print(f"[{i}/{len(part_urls)}] failed {url}: {e}")
                _mark_seen(seen_path, url)

        wrote = _write_jsonl(out_jsonl, rows)
        print({"ok": True, "wrote": wrote, "out": str(out_jsonl)})

        ctx.close()
        browser.close()


if __name__ == "__main__":
    main()

