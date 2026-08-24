#!/usr/bin/env python3
"""Alternate source for a municipality whose live site blocks us (CloudFront 403).

Pulls the site's archived HTML from the Wayback Machine and writes the SAME
`data/<slug>/crawl/docs.jsonl` (plus `state.json`) that `crawl.py` produces, so
`ingest.py` -> `build_index.py` -> the app pick it up unchanged.  The `url`
field keeps the ORIGINAL dalfsen.nl URL (so citations read naturally and
sha1(url) ids stay stable); only the *fetch* goes through web.archive.org.

Usage:
    scripts/wayback_crawl.py --municipality dalfsen [--limit 100] [--from 2022]

Env:
    WAYBACK_CONCURRENCY  (default 6)
    WAYBACK_DELAY        (default 0.2s between requests; polite vs web.archive.org)
"""
import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import muni
from crawl import html_extract, now_iso  # reuse the exact extraction + id logic

CONCURRENCY = int(os.environ.get("WAYBACK_CONCURRENCY", "6"))
DELAY = float(os.environ.get("WAYBACK_DELAY", "0.2"))
CDX = "http://web.archive.org/cdx/search/cdx"
MIN_HTML_CHARS = 80


def cdx_urls(slug: str, domain: str, from_year: str | None) -> list[tuple[str, str]]:
    """[(timestamp, original_url)] — recent HTML snapshots for the site's domain.

    `collapse=urlkey` dedupes to one (latest) snapshot per URL; `mimetype:text/html`
    drops PDFs/images; `statuscode:200` drops redirects/404s."""
    params = {
        "url": domain,
        "matchType": "domain",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "collapse": "urlkey",
        "fl": "timestamp,original",
    }
    if from_year:
        params["from"] = from_year
    with httpx.Client(timeout=120) as c:
        r = c.get(CDX, params=params)
        r.raise_for_status()
    out = []
    for line in r.text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        ts, url = parts
        out.append((ts, url))
    print(f"cdx: {len(out)} archived html urls for {domain}", flush=True)
    return out


def wayback_url(ts: str, original: str) -> str:
    # `id_` flag = raw original page, no wayback banner/js injected.
    return f"https://web.archive.org/web/{ts}id_/{original}"


async def fetch_one(client: httpx.AsyncClient, ts: str, url: str, site: str):
    """-> doc record (or None), reusing crawl.py's extractor + field layout."""
    for _ in range(3):  # web.archive.org 429s under load; retry politely
        try:
            r = await client.get(wayback_url(ts, url), follow_redirects=True)
        except httpx.HTTPError:
            await asyncio.sleep(1.0)
            continue
        if r.status_code == 429:
            await asyncio.sleep(3.0)
            continue
        if r.status_code != 200:
            return None
        text = r.text
        break
    else:
        return None

    try:
        title, text, pub = html_extract(url, text)
    except Exception:
        return None  # one bad page must never kill the whole run
    if len(text.strip()) < MIN_HTML_CHARS:
        return None
    return {
        "id": hashlib.sha1(url.encode()).hexdigest(),
        "url": url,
        "title": title,
        "text": text.strip(),
        "doc_type": "html",
        "published_at": pub,
        "fetched_at": now_iso(),
        "source_path": None,
        "pages": None,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "site": site,
    }


async def run(slug: str, limit: int, from_year: str | None):
    m = muni.get(slug)
    start_url = m.get("start_url") or f"https://www.{slug}.nl/"
    domain = start_url.split("//", 1)[1].rstrip("/")
    site = domain.split("/")[0]

    crawl_dir = muni.data_dir(slug) / "crawl"
    crawl_dir.mkdir(parents=True, exist_ok=True)
    docs_path = crawl_dir / "docs.jsonl"
    state_path = crawl_dir / "state.json"

    urls = cdx_urls(slug, site, from_year)
    # keep only the municipality's own hosts (subdomains included) — drop
    # anything CDX matched on the domain but that isn't in scope.
    base = ".".join(site.split(".")[-2:])

    def host_of(u: str) -> str:
        return u.split("//", 1)[1].split("/")[0].split(":")[0].lower()

    urls = [
        (ts, u) for ts, u in urls
        if host_of(u) == site.lower() or host_of(u).endswith("." + base)
    ]
    if limit:
        urls = urls[:limit]
    print(f"fetching {len(urls)} archived pages for {slug}", flush=True)

    # Resumable: skip URLs we already wrote (append-mode below), so a re-run
    # after a crash picks up where it left off instead of re-fetching 9k pages.
    done_ids = set()
    if docs_path.exists():
        for line in docs_path.read_text(encoding="utf-8").splitlines():
            try:
                done_ids.add(json.loads(line)["id"])
            except Exception:
                pass
    urls = [(ts, u) for ts, u in urls if hashlib.sha1(u.encode()).hexdigest() not in done_ids]
    print(f"{len(urls)} remaining after skipping {len(done_ids)} already-done", flush=True)

    sem = asyncio.Semaphore(CONCURRENCY)
    seen, docs = 0, 0
    t0 = time.time()
    out = open(docs_path, "a", encoding="utf-8")

    async def worker(ts, url):
        nonlocal seen, docs
        async with sem:
            await asyncio.sleep(DELAY)
            doc = await fetch_one(client, ts, url, site)
        seen += 1
        if doc:
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
            out.flush()
            docs += 1
        if seen % 100 == 0:
            rate = seen / max(time.time() - t0, 1e-6)
            print(f"  {seen}/{len(urls)}  {docs} docs  {rate:.1f}/s", flush=True)

    async with httpx.AsyncClient(
        timeout=30, headers={"User-Agent": "GemeenteZoek/1.0 (wayback; polite)"}
    ) as client:
        await asyncio.gather(*(worker(ts, u) for ts, u in urls))

    out.close()
    total = sum(1 for _ in docs_path.read_text(encoding="utf-8").splitlines())
    # state.json so the monitor + any downstream tooling see a finished crawl.
    state_path.write_text(json.dumps({
        "seen": [], "pending": [], "docs": total, "pdfs": 0,
    }, ensure_ascii=False), encoding="utf-8")
    print(f"done: {docs} new docs this run, {total} total in {docs_path}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    muni.add_muni_arg(p)
    p.add_argument("--limit", type=int, default=0, help="cap for a validation run")
    p.add_argument("--from", dest="from_year", default="2022", help="earliest snapshot year")
    args = p.parse_args()
    asyncio.run(run(args.municipality, args.limit, args.from_year))
