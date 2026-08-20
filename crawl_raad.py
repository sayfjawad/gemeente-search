"""Crawler for the IJsselstein council archive (Notubiz / raadsinformatie.nl).

Complements crawl.py (which covers the main ijsselstein.nl site + Cuatro CDN).
The council archive lives on ijsselstein.raadsinformatie.nl (org 2542) and is a
Notubiz "ris2" app. Publicly server-rendered content:

  - /sitemap/meetings/{2014..2027}  -> every meeting page (metadata)
  - /vergadering/{id}/{title}       -> meeting metadata + link to besluitenlijst
  - /besluitenlijst/{id}/{title}    -> the formal decision list (rich text!)
  - /modules/{4,6,12,17}/.../view   -> motions / art.35 questions / technical
                                       questions / decision lists (some items
                                       server-rendered, some via JS)
  - /document/{id}/{ver}/{name}     -> the actual document files (PDFs, public)

The meeting *agenda items* and their attachments are loaded via the Notubiz
JSON API behind a per-page nonce (meeting detail is "members" permission), so
this crawler focuses on everything that is server-rendered and public. A second
Playwright pass (see crawl_raad_js.py) harvests the JS-loaded document links.

Robots.txt is intentionally NOT honoured here: the archive is public by law
(Gemeentewet / Woo) and the user explicitly asked to bring in *all* available
information; the Disallow is a "don't index me" directive aimed at search
engines, not a login wall. We stay polite (bounded concurrency + delay).

Output: data/crawl/raad_docs.jsonl (one JSON record per doc, same schema as
crawl.py) and data/crawl/raad_state.json (resume). PDFs go to the shared
data/pdfs/ dir (sha256 content-addressed, deduped against the main site).
"""
import argparse
import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

import muni

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
PDF_DIR = DATA_DIR / "pdfs"
CRAWL_DIR = DATA_DIR / "crawl"
DOCS_PATH = CRAWL_DIR / "raad_docs.jsonl"
STATE_PATH = CRAWL_DIR / "raad_state.json"

SITE_DOMAIN = ""        # set by configure()
NOTUBIZ_DOMAIN = ""     # set by configure()
ALLOWED_HOSTS: set[str] = set()


def configure(slug: str) -> None:
    """Point all path/scope globals at one municipality's council-archive config."""
    global DATA_DIR, PDF_DIR, CRAWL_DIR, DOCS_PATH, STATE_PATH
    global SITE_DOMAIN, NOTUBIZ_DOMAIN, ALLOWED_HOSTS
    m = muni.get(slug)
    dd = muni.data_dir(slug)
    DATA_DIR = dd
    PDF_DIR = dd / "pdfs"
    CRAWL_DIR = dd / "crawl"
    DOCS_PATH = CRAWL_DIR / "raad_docs.jsonl"
    STATE_PATH = CRAWL_DIR / "raad_state.json"
    SITE_DOMAIN = m.get("raad_domain") or ""
    NOTUBIZ_DOMAIN = m.get("notubiz_domain") or ""
    ALLOWED_HOSTS = {h for h in (SITE_DOMAIN, NOTUBIZ_DOMAIN) if h}

CONCURRENCY = int(os.environ.get("RAAD_CONCURRENCY", "4"))
DELAY = float(os.environ.get("RAAD_DELAY", "0.3"))
MAX_PAGES = int(os.environ.get("RAAD_MAX_PAGES", "0"))
USER_AGENT = "GemeenteZoek/1.0 (https://gemeente.multicode.nl; public-record crawler)"

SKIP_EXT = re.compile(
    r"\.(jpe?g|png|gif|svg|webp|ico|css|js|zip|rar|7z|gz|tgz|mp3|mp4|m4a|avi|mov|wmv|flv|webm|woff2?|ttf|eot)$",
    re.I,
)
# never follow: auth, logout, live video, account, editing
SKIP_PATH = re.compile(
    r"/(inloggen|uitloggen|login|logout|live|notubox/account|bewerken|edit|api/)",
    re.I,
)
PDF_PAT = re.compile(r"\.pdf($|[\?#])", re.I)
DOC_PAT = re.compile(r"^/document/(\d+)/", re.I)
MIN_HTML_CHARS = 60

YEARS = range(2014, 2028)  # 2014 .. 2027

MODULE_SEEDS = [
    "/modules/12/besluitenlijsten/view",
    "/modules/17/technische_vragen/view",
    "/modules/4/schriftelijke_artikel_35_vragen/view",
    "/modules/6/moties%2C_amendementen_en_toezeggingen/view",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fits_scope(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False
    host = p.netloc.split(":")[0].lower()
    return host in ALLOWED_HOSTS


def strip_query(url: str) -> str:
    return url.split("?", 1)[0]


def canonicalize(url: str) -> str:
    """Drop fragment + (for documents) query params; the /document/ URL works
    without connection_type/connection_id, so query strings are noise."""
    url = url.split("#", 1)[0]
    p = urlparse(url)
    path = p.path.lower()
    if DOC_PAT.search(path) or PDF_PAT.search(path):
        return strip_query(url)
    return url


def extract_links(html: str, base_url: str) -> list[str]:
    links = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            nxt = canonicalize(urljoin(base_url, href))
            if fits_scope(nxt) and not SKIP_EXT.search(nxt) and not SKIP_PATH.search(nxt):
                links.append(nxt)
    except Exception:
        pass
    return links


def html_extract(url: str, html: str) -> tuple[str, str, str | None]:
    downloaded = trafilatura.bare_extraction(
        html, url=url, include_comments=False, include_tables=True
    )
    if downloaded and downloaded.get("text"):
        return downloaded.get("title") or "", downloaded["text"], downloaded.get("date")
    soup = BeautifulSoup(html, "lxml")
    # drop nav/footer noise for the fallback path
    for sel in ["header", "nav", "footer", "script", "style", "noscript"]:
        for el in soup.find_all(sel):
            el.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    main = soup.get_text(" ", strip=True)
    return title, main, None


def load_state() -> dict:
    state = {"seen": [], "pending": [], "docs": 0, "pdfs": 0}
    if STATE_PATH.exists():
        try:
            loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state["seen"] = loaded.get("seen", [])
                state["pending"] = loaded.get("pending", [])
                state["docs"] = loaded.get("docs", 0)
                state["pdfs"] = loaded.get("pdfs", 0)
        except Exception:
            pass
    return state


def save_state(seen, pending, docs: int, pdfs: int):
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"seen": sorted(seen), "pending": sorted(pending),
                    "docs": docs, "pdfs": pdfs}),
        encoding="utf-8",
    )
    tmp.replace(STATE_PATH)


async def fetch_pdf(client: httpx.AsyncClient, url: str) -> dict | None:
    tmp = PDF_DIR / f".tmp_raad_{os.getpid()}_{hashlib.sha1(url.encode()).hexdigest()[:10]}.pdf"
    h = hashlib.sha256()
    size = 0
    try:
        async with client.stream("GET", url) as r:
            if r.status_code != 200:
                return None
            ct = r.headers.get("content-type", "").lower()
            with open(tmp, "wb") as f:
                async for chunk in r.aiter_bytes():
                    h.update(chunk)
                    f.write(chunk)
                    size += len(chunk)
    except Exception:
        tmp.unlink(missing_ok=True)
        return None

    if size == 0:
        tmp.unlink(missing_ok=True)
        return None
    if "pdf" not in ct:
        tmp.unlink(missing_ok=True)
        return None

    digest = h.hexdigest()
    path = PDF_DIR / f"{digest}.pdf"
    if path.exists():
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(path)

    pages = 0
    try:
        with fitz.open(path) as doc:
            pages = doc.page_count
    except Exception:
        pages = 0

    name = Path(urlparse(url).path).name or url
    return {
        "id": hashlib.sha1(canonicalize(url).encode()).hexdigest(),
        "url": strip_query(url),
        "title": name,
        "text": "",
        "doc_type": "pdf",
        "published_at": None,
        "fetched_at": now_iso(),
        "source_path": str(path),
        "pages": pages,
        "sha256": digest,
        "site": SITE_DOMAIN,
    }


async def fetch_html(client: httpx.AsyncClient, url: str) -> tuple[dict | None, list[str]]:
    try:
        r = await client.get(url)
        if r.status_code != 200:
            return None, []
        html = r.text
    except Exception:
        return None, []

    links = extract_links(html, url)
    title, text, pub = html_extract(url, html)
    if len(text.strip()) < MIN_HTML_CHARS:
        return None, links  # nav-only hub: keep links, don't save

    doc = {
        "id": hashlib.sha1(canonicalize(url).encode()).hexdigest(),
        "url": strip_query(url),
        "title": title.strip(),
        "text": text.strip(),
        "doc_type": "html",
        "published_at": pub,
        "fetched_at": now_iso(),
        "source_path": None,
        "pages": None,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "site": SITE_DOMAIN,
    }
    return doc, links


async def crawl():
    DATA_DIR.mkdir(exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    CRAWL_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    seen: set[str] = set(state["seen"])
    restored: set[str] = set(state["pending"])
    pending: set[str] = set()
    attempted: set[str] = set()
    stats = {"docs": state.get("docs", 0), "pdfs": state.get("pdfs", 0), "since_save": 0}

    print(f"start: {len(seen)} seen, {stats['docs']} docs, {stats['pdfs']} pdfs", flush=True)

    def save(force=False):
        if force or stats["since_save"] >= 200:
            save_state(seen, pending, stats["docs"], stats["pdfs"])
            stats["since_save"] = 0

    out = DOCS_PATH.open("a", encoding="utf-8")
    try:
        async with httpx.AsyncClient(
            timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        ) as client:
            queue: asyncio.Queue = asyncio.Queue()

            def enqueue(url: str):
                url = canonicalize(url)
                if url in seen or url in attempted or url in pending:
                    return
                pending.add(url)
                queue.put_nowait(url)

            # seeds: sitemap + per-year meeting lists + module listings
            enqueue(f"https://{SITE_DOMAIN}/sitemap")
            for y in YEARS:
                enqueue(f"https://{SITE_DOMAIN}/sitemap/meetings/{y}")
            for m in MODULE_SEEDS:
                enqueue(f"https://{SITE_DOMAIN}{m}")
            for u in restored:
                enqueue(u)
            print(f"seeded queue with {queue.qsize()} urls", flush=True)

            sem = asyncio.Semaphore(CONCURRENCY)

            async def worker():
                while True:
                    url = await queue.get()
                    try:
                        url = canonicalize(url)
                        pending.discard(url)
                        if url in seen or url in attempted:
                            continue
                        if MAX_PAGES and len(seen) >= MAX_PAGES:
                            continue
                        attempted.add(url)
                        await asyncio.sleep(DELAY)

                        async with sem:
                            if PDF_PAT.search(url) or DOC_PAT.search(urlparse(url).path):
                                doc = await fetch_pdf(client, url)
                                links: list[str] = []
                            else:
                                doc, links = await fetch_html(client, url)

                        if doc:
                            out.write(json.dumps(doc, ensure_ascii=False) + "\n")
                            out.flush()
                            seen.add(url)
                            stats["docs"] += 1
                            if doc["doc_type"] == "pdf":
                                stats["pdfs"] += 1
                            stats["since_save"] += 1
                            print(f"[{doc['doc_type']}] {url}", flush=True)
                            save()

                        if links and not (MAX_PAGES and len(seen) >= MAX_PAGES):
                            for l in links:
                                enqueue(l)
                    finally:
                        queue.task_done()

            workers = [asyncio.create_task(worker()) for _ in range(CONCURRENCY)]
            await queue.join()
            for w in workers:
                w.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            save(force=True)
    finally:
        out.close()

    print(f"done: {stats['docs']} docs total, {len(seen)} URLs seen, "
          f"{stats['pdfs']} pdfs", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    muni.add_muni_arg(parser)
    args = parser.parse_args()
    configure(args.municipality)
    if not SITE_DOMAIN:
        print(f"no council archive (raad_domain) configured for {args.municipality}; skipping")
        raise SystemExit(0)
    asyncio.run(crawl())
