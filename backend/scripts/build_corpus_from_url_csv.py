from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Iterable

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Ensure backend root is importable when running as a script.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

load_dotenv(_BACKEND_ROOT / ".env")

from scraper import (  # noqa: E402
    HEADERS,
    fetch_html_via_scrapingbee,
    fetch_html_via_zenrows,
    is_blocked_html,
)


def _iter_csv_urls(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            u = (row.get("url") or "").strip()
            if u:
                yield u


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    # Keep it compact for chunking/search.
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    # Avoid huge boilerplate tails; keep first N chars.
    return "\n".join(lines)[:120_000].strip()


async def _fetch_html_direct(url: str, timeout_s: float = 20.0) -> str | None:
    # trust_env=False avoids accidentally picking up HTTP(S)_PROXY which can break requests.
    async with httpx.AsyncClient(
        timeout=timeout_s, follow_redirects=True, trust_env=False
    ) as client:
        resp = await client.get(url, headers=HEADERS)
        if resp.status_code != 200:
            return None
        if not resp.text:
            return None
        if is_blocked_html(resp.text):
            return None
        return resp.text


async def fetch_html_best_effort(url: str, provider: str) -> tuple[str | None, str]:
    """
    Returns (html, method_used)
    method_used is one of: direct, zenrows, scrapingbee, none
    """
    html = await _fetch_html_direct(url)
    if html:
        return html, "direct"

    if provider in {"zenrows", "any"}:
        html = await fetch_html_via_zenrows(url)
        if html:
            return html, "zenrows"

    if provider in {"scrapingbee", "any"}:
        html = await fetch_html_via_scrapingbee(url)
        if html:
            return html, "scrapingbee"

    return None, "none"


def _safe_out_name(stem: str) -> str:
    s = "".join(c if (c.isalnum() or c in {"-", "_", "."}) else "_" for c in stem)
    return s[:120] or "corpus"


def _load_seen_urls_from_jsonl(path: Path) -> set[str]:
    if not path.exists():
        return set()
    seen: set[str] = set()
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            u = (obj.get("url") if isinstance(obj, dict) else None) or ""
            u = str(u).strip()
            if u:
                seen.add(u)
    return seen


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv-dir",
        default="knowledge/raw/urls_local",
        help="Directory containing *_urls.csv (relative to backend/)",
    )
    ap.add_argument(
        "--csv-glob",
        default="*_urls.csv",
        help="Which CSV files to ingest from csv-dir (glob pattern)",
    )
    ap.add_argument(
        "--out",
        default="knowledge/raw/data/url_corpus.jsonl",
        help="Output JSONL path (relative to backend/)",
    )
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Skip URLs already present in the output JSONL",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max URLs total (0 = no limit)",
    )
    ap.add_argument(
        "--provider",
        choices=["direct", "zenrows", "scrapingbee", "any"],
        default="direct",
        help="How to fetch pages when direct is blocked",
    )
    ap.add_argument(
        "--sleep-ms",
        type=int,
        default=250,
        help="Delay between requests (politeness/backoff)",
    )
    ap.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print progress every N attempted URLs",
    )
    args = ap.parse_args()

    # Fail fast if the chosen provider can't possibly work.
    if args.provider in {"zenrows", "any"}:
        if not (str(__import__("os").environ.get("ZENROWS_API_KEY", "")).strip()):
            if args.provider == "zenrows":
                raise SystemExit(
                    "ZENROWS_API_KEY is not set. Add it to backend/.env to use --provider zenrows."
                )
    if args.provider in {"scrapingbee", "any"}:
        if not (str(__import__("os").environ.get("SCRAPINGBEE_API_KEY", "")).strip()):
            if args.provider == "scrapingbee":
                raise SystemExit(
                    "SCRAPINGBEE_API_KEY is not set. Add it to backend/.env to use --provider scrapingbee."
                )

    base = Path(__file__).resolve().parents[1]
    csv_dir = (base / args.csv_dir).resolve()
    out_path = (base / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not csv_dir.exists():
        raise SystemExit(f"CSV dir not found: {csv_dir}")

    csv_files = sorted(csv_dir.glob(args.csv_glob))
    if not csv_files:
        raise SystemExit(f"No CSVs matched {args.csv_glob!r} in: {csv_dir}")

    seen: set[str] = set()
    if args.resume:
        seen = _load_seen_urls_from_jsonl(out_path)
        print(f"Resume enabled. Preloaded {len(seen)} URLs from {out_path}")

    total = 0
    ok = 0
    blocked = 0
    failed = 0

    with out_path.open("a", encoding="utf-8") as out:
        for csv_path in csv_files:
            for url in _iter_csv_urls(csv_path):
                if args.limit and total >= args.limit:
                    break
                if url in seen:
                    continue
                seen.add(url)
                total += 1

                provider = args.provider
                if provider == "direct":
                    html, method = await fetch_html_best_effort(url, provider="none")
                else:
                    html, method = await fetch_html_best_effort(url, provider=provider)

                if not html:
                    # If direct failed and we didn't allow fallbacks, consider it blocked/failed.
                    # We don't distinguish perfectly; this keeps logging simple.
                    if method == "none":
                        blocked += 1
                    else:
                        failed += 1
                    if args.sleep_ms:
                        time.sleep(args.sleep_ms / 1000.0)
                    continue

                text = _html_to_text(html)
                if not text:
                    failed += 1
                    if args.sleep_ms:
                        time.sleep(args.sleep_ms / 1000.0)
                    continue

                row = {
                    "url": url,
                    "source_csv": str(csv_path.relative_to(base)),
                    "fetched_via": method,
                    "text": text,
                }
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                ok += 1

                if args.sleep_ms:
                    time.sleep(args.sleep_ms / 1000.0)

                if args.progress_every and (total % args.progress_every == 0):
                    print(
                        f"progress: attempted={total} ok={ok} blocked={blocked} failed={failed}"
                    )

            if args.limit and total >= args.limit:
                break

    print(
        f"Done. total={total} ok={ok} blocked={blocked} failed={failed} out={out_path}"
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

