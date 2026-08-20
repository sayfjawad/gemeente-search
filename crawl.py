"""Production crawler for a Dutch municipality site (default ijsselstein.nl).

Captures ALL same-host content:
  - HTML pages -> clean text via trafilatura (BeautifulSoup fallback)
  - PDFs       -> binary streamed to data/pdfs/<sha256>.pdf, page count via
                  PyMuPDF (text NOT stored here; ingest.py re-opens the PDF
                  for page-level chunking + page screenshots)

Seeding is sitemap-first (the authoritative page list), so every main-site
page is covered even if it's not BFS-reachable from the homepage; link
discovery from each page then finds the CDN-hosted PDF uploads. Respects
robots.txt (both the site's and the CDN's), is resumable
(data/crawl/state.json), and polite (bounded concurrency + per-request delay).

Output: data/crawl/docs.jsonl — one JSON record per document:
  {id, url, title, text, doc_type: html|pdf, published_at, fetched_at,
   source_path (pdf only), pages (pdf only), sha256, site}

Env knobs:
  START_URL          (default https://www.ijsselstein.nl/)
  MAX_PAGES          (default 0 = unlimited; set >0 for a small validation run)
  CRAWL_CONCURRENCY  (default 3)
  CRAWL_DELAY        (default 0.4s between requests)
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
import urllib.robotparser as robotparser
from playwright.async_api import async_playwright
import fitz  # PyMuPDF

import muni

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
PDF_DIR = DATA_DIR / "pdfs"
CRAWL_DIR = DATA_DIR / "crawl"
DOCS_PATH = CRAWL_DIR / "docs.jsonl"
STATE_PATH = CRAWL_DIR / "state.json"

START_URL = ""          # set by configure()
SITE_DOMAIN = ""        # set by configure()
BASE_DOMAIN = ""        # set by configure()
CDN_UPLOAD_PREFIX = ""  # set by configure()
PRODUCT_SITEMAP = ""    # set by configure() — Digitaal Loket product catalog

MAX_PAGES = int(os.environ.get("MAX_PAGES", "0"))
CONCURRENCY = int(os.environ.get("CRAWL_CONCURRENCY", "3"))
DELAY = float(os.environ.get("CRAWL_DELAY", "0.4"))
USER_AGENT = "GemeenteZoek/1.0 (https://gemeente.multicode.nl; polite crawler)"

# Documents uploaded to the site live on the SimGroep "Cuatro" CDN, scoped to
# this municipality's tenant uploads dir (e.g. ijsselstein13cb44).
CDN_HOST = "cuatro.sim-cdn.nl"


def configure(slug: str) -> None:
    """Point all path/scope globals at one municipality's data + site config."""
    global DATA_DIR, PDF_DIR, CRAWL_DIR, DOCS_PATH, STATE_PATH
    global START_URL, SITE_DOMAIN, BASE_DOMAIN, CDN_UPLOAD_PREFIX, PRODUCT_SITEMAP, SKIP_PATHS
    m = muni.get(slug)
    dd = muni.data_dir(slug)
    DATA_DIR = dd
    PDF_DIR = dd / "pdfs"
    CRAWL_DIR = dd / "crawl"
    DOCS_PATH = CRAWL_DIR / "docs.jsonl"
    STATE_PATH = CRAWL_DIR / "state.json"
    START_URL = m.get("start_url") or f"https://www.{slug}.nl/"
    SITE_DOMAIN = urlparse(START_URL).netloc.split(":")[0]
    BASE_DOMAIN = ".".join(SITE_DOMAIN.split(".")[-2:])
    CDN_UPLOAD_PREFIX = m.get("cdn_prefix", "")
    PRODUCT_SITEMAP = m.get("product_sitemap", "")
    SKIP_PATHS = [re.compile(x, re.I) for x in m.get("skip_paths", [])]

SKIP_EXT = re.compile(
    r"\.(jpe?g|png|gif|svg|webp|ico|css|js|zip|rar|7z|gz|tgz|mp3|mp4|m4a|avi|mov|wmv|flv|webm|woff2?|ttf|eot)$",
    re.I,
)
SKIP_PATH = re.compile(r"/(login|logout|winkelwagen|api|wp-admin|wp-json|planboard|formulier|afspraak)", re.I)
# Interactive citizen-portal / appointment / SSO subdomains generate endless
# parameterised URLs (mijn.<gemeente>.nl, afspraak.<gemeente>.nl, auth/saml).
# They are navigation forms, not content — exclude the whole host.
# Interactive citizen-portal / appointment / SSO subdomains generate endless
# parameterised URLs (mijn.<gemeente>.nl, afspraak.<gemeente>.nl, auth/saml).
# They are navigation forms, not content — exclude the whole host.
# NOTE: `loket` is deliberately NOT here — the Digitaal Loket's `/nl/producten/`
# product-catalog pages ARE content (seeded from its sitemap, see
# PRODUCT_SITEMAP); its /formulier/ + /afspraak/ wizard flows are skipped via
# SKIP_PATH instead.
SKIP_HOST = re.compile(r"^(mijn|afspraak|formulieren|digitaal|zaak|berichten|open|data|digid|eherkenning|idp|sso|login|account|portal)\d*\.", re.I)
# Per-municipality path exclusions (e.g. a Digitaal Loket's JS search-hub pages
# `/nl` and `/nl/producten`, whose filters generate endless trap URLs). Matched
# against the URL path only; loaded from the registry's `skip_paths` list.
SKIP_PATHS: list = []
PDF_PAT = re.compile(r"\.pdf($|[\?#])", re.I)
MIN_HTML_CHARS = 80


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fits_scope(url: str) -> bool:
    """HTML from the site (+ subdomains); PDF uploads from the site's CDN tenant."""
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False
    host = p.netloc.split(":")[0].lower()
    path = p.path.lower()
    if SKIP_HOST.match(host):
        return False
    if any(rx.match(path) for rx in SKIP_PATHS):
        return False
    if host == SITE_DOMAIN.lower() or host.endswith("." + BASE_DOMAIN.lower()):
        return True
    if host == CDN_HOST:
        return path.startswith(CDN_UPLOAD_PREFIX) and PDF_PAT.search(path)
    return False


def strip_fragment(url: str) -> str:
    return url.split("#", 1)[0]


def canonicalize(url: str) -> str:
    """Normalise a URL so the same page isn't re-crawled under variants:
    drop cache-buster query strings on CDN uploads, and force http -> https
    (TYPO3 sites often list `http://` in their sitemap while the real pages
    are served (and BFS-linked) over https — fetching both doubles the crawl)."""
    p = urlparse(url)
    if p.netloc.split(":")[0].lower() == CDN_HOST:
        return url.split("?", 1)[0]
    if p.scheme == "http":
        url = url.replace("http://", "https://", 1)
    return url


def crude_date(text: str):
    for pat in [r"\b(\d{4}-\d{2}-\d{2})\b", r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b"]:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def html_extract(url: str, html: str) -> tuple[str, str, str | None]:
    downloaded = trafilatura.bare_extraction(
        html, url=url, include_comments=False, include_tables=True
    )
    if downloaded and downloaded.get("text"):
        title = downloaded.get("title") or ""
        text = downloaded["text"]
        pub = downloaded.get("date") or crude_date(text)
        return title, text, pub
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    main = soup.get_text(" ", strip=True)
    return title, main, crude_date(main)


def extract_links(html: str, base_url: str) -> list[str]:
    links = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            nxt = canonicalize(strip_fragment(urljoin(base_url, href)))
            if fits_scope(nxt) and not SKIP_EXT.search(nxt) and not SKIP_PATH.search(nxt):
                links.append(nxt)
    except Exception:
        pass
    return links


# ------------------------------------------------------------------ state
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
        json.dumps({
            "seen": sorted(seen),
            "pending": sorted(pending),
            "docs": docs,
            "pdfs": pdfs,
        }),
        encoding="utf-8",
    )
    tmp.replace(STATE_PATH)


# ---------------------------------------------------------------- robots
async def fetch_robots(host: str):
    rp = robotparser.RobotFileParser()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as rc:
            r = await rc.get(f"https://{host}/robots.txt")
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                return rp
    except Exception:
        pass
    return None


def robots_can_fetch(rp, url: str) -> bool:
    if rp is None:
        return True
    try:
        return rp.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def robots_for(rp_site, rp_cdn, url: str):
    host = urlparse(url).netloc.split(":")[0].lower()
    return rp_cdn if host == CDN_HOST else rp_site


# -------------------------------------------------------------- sitemap
async def fetch_sitemap_urls(client: httpx.AsyncClient) -> list[str]:
    urls: list[str] = []
    try:
        r = await client.get(f"https://{SITE_DOMAIN}/sitemap.xml")
        if r.status_code != 200:
            return urls
        xml = r.text
        if "<sitemapindex" in xml:
            for loc in re.findall(r"<loc>([^<]+)</loc>", xml)[:30]:
                try:
                    cr = await client.get(loc)
                    if cr.status_code == 200:
                        urls += re.findall(r"<loc>([^<]+)</loc>", cr.text)
                except Exception:
                    pass
        else:
            urls = re.findall(r"<loc>([^<]+)</loc>", xml)
    except Exception:
        pass
    return [canonicalize(strip_fragment(u)) for u in urls if fits_scope(u)]


async def fetch_product_sitemap_urls(client: httpx.AsyncClient) -> list[str]:
    """Seed the Digitaal Loket product-catalog pages (PRODUCT_SITEMAP).

    The loket sitemap lists the product pages PLUS the hub pages `/nl` and
    `/nl/producten` (a JS search/filter page that generates endless trap URLs).
    We only keep the deep product pages (>= 3 path segments), never the hubs.
    """
    if not PRODUCT_SITEMAP:
        return []
    urls: list[str] = []
    try:
        r = await client.get(PRODUCT_SITEMAP)
        if r.status_code != 200:
            return urls
        for loc in re.findall(r"<loc>([^<]+)</loc>", r.text):
            u = canonicalize(strip_fragment(loc))
            if not fits_scope(u):
                continue
            if len([s for s in urlparse(u).path.split("/") if s]) < 3:
                continue  # drop /nl and /nl/producten hubs
            urls.append(u)
    except Exception:
        pass
    return urls


# ---------------------------------------------------------------- fetchers
async def fetch_pdf(client: httpx.AsyncClient, url: str) -> dict | None:
    """Stream a PDF to data/pdfs/<sha256>.pdf and return a doc record."""
    tmp = PDF_DIR / f".tmp_{os.getpid()}_{hashlib.sha1(url.encode()).hexdigest()[:10]}.pdf"
    h = hashlib.sha256()
    size = 0
    ct = ""
    last_modified = None
    try:
        async with client.stream("GET", url) as r:
            if r.status_code != 200:
                return None
            ct = r.headers.get("content-type", "").lower()
            last_modified = r.headers.get("last-modified")
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

    digest = h.hexdigest()
    path = PDF_DIR / f"{digest}.pdf"
    if path.exists():
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(path)

    # sanity: only keep as PDF if the URL is .pdf or the server says pdf
    if "pdf" not in ct and not PDF_PAT.search(url):
        path.unlink(missing_ok=True)
        return None

    pages = 0
    try:
        with fitz.open(path) as doc:
            pages = doc.page_count
    except Exception:
        pages = 0

    title = Path(urlparse(url).path).name or url
    return {
        "id": hashlib.sha1(url.encode()).hexdigest(),
        "url": url,
        "title": title,
        "text": "",
        "doc_type": "pdf",
        "published_at": last_modified,
        "fetched_at": now_iso(),
        "source_path": str(path),
        "pages": pages,
        "sha256": digest,
        "site": SITE_DOMAIN,
    }


async def fetch_html(browser, url: str) -> tuple[dict | None, list[str]]:
    """Render an HTML page; return (doc_or_None, links)."""
    page = None
    html = None
    try:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        html = await page.content()
    except Exception:
        html = None
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass

    if not html:
        return None, []

    links = extract_links(html, url)
    title, text, pub = html_extract(url, html)
    if len(text.strip()) < MIN_HTML_CHARS:
        return None, links  # navigation hub: keep links, don't save

    doc = {
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
        "site": SITE_DOMAIN,
    }
    return doc, links


# ------------------------------------------------------------------- crawl
async def crawl():
    DATA_DIR.mkdir(exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    CRAWL_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state()
    seen: set[str] = set(state["seen"])
    restored: set[str] = set(state["pending"])
    pending: set[str] = set()  # fresh frontier for this run
    attempted: set[str] = set()
    stats = {"docs": state.get("docs", 0), "pdfs": state.get("pdfs", 0), "since_save": 0}

    print(f"start: {len(seen)} seen, {len(pending)} pending, "
          f"{stats['docs']} docs, {stats['pdfs']} pdfs", flush=True)

    def save(force=False):
        if force or stats["since_save"] >= 200:
            save_state(seen, pending, stats["docs"], stats["pdfs"])
            stats["since_save"] = 0

    out = DOCS_PATH.open("a", encoding="utf-8")
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            async with httpx.AsyncClient(
                timeout=60.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}
            ) as client:
                robots_site = await fetch_robots(SITE_DOMAIN)
                robots_cdn = await fetch_robots(CDN_HOST)

                queue: asyncio.Queue = asyncio.Queue()

                def enqueue(url: str):
                    url = canonicalize(strip_fragment(url))
                    if url in seen or url in attempted or url in pending:
                        return
                    pending.add(url)
                    queue.put_nowait(url)

                enqueue(START_URL)
                for u in await fetch_sitemap_urls(client):
                    enqueue(u)
                for u in await fetch_product_sitemap_urls(client):
                    enqueue(u)
                for u in restored:  # frontier from a previous run
                    enqueue(u)
                print(f"seeded queue with {queue.qsize()} urls", flush=True)

                sem = asyncio.Semaphore(CONCURRENCY)

                async def worker():
                    while True:
                        url = await queue.get()
                        try:
                            url = canonicalize(strip_fragment(url))
                            pending.discard(url)
                            if url in seen or url in attempted:
                                continue
                            if MAX_PAGES and len(seen) >= MAX_PAGES:
                                continue
                            if not fits_scope(url):
                                continue
                            rp = robots_for(robots_site, robots_cdn, url)
                            if rp and not robots_can_fetch(rp, url):
                                attempted.add(url)
                                continue
                            attempted.add(url)
                            await asyncio.sleep(DELAY)

                            async with sem:
                                if PDF_PAT.search(url):
                                    doc = await fetch_pdf(client, url)
                                    links: list[str] = []
                                else:
                                    doc, links = await fetch_html(browser, url)

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
    asyncio.run(crawl())
