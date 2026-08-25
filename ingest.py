"""docs.jsonl -> index.sqlite ingestion for the gemeente smart search.

Reads the crawler output (data/<slug>/crawl/docs.jsonl: one JSON record per
document) and builds data/<slug>/index.sqlite with a `documents` table (id,
title, url, doc_type html|pdf, filename, pages, published_at, site) and a
`chunks` table (id, document, page_start, page_end, text, bbox_y0, bbox_y1).

Chunking:
  - HTML documents are chunked by sentence boundaries (~1400 chars). No page
    or bbox; the frontend links straight to the source URL.
  - PDF documents are chunked per page (a page longer than ~1400 chars is
    split at sentence boundaries, all parts keeping page_start == page_end).
    bbox_y0/bbox_y1 are left NULL so /pdf-image renders the whole page.

Deduplication: the crawler can collect the same page under http:// and https://
(or with a trailing slash / cache-buster query), so URLs are canonicalized
(http->https, strip query, strip trailing slash) and a second pass keeps only
the first record per canonical URL (preferring a pdf-type record's file).

PDFs are resolved by *filename* inside the municipality's own pdfs/ dir (they
are sha256 content-addressed), so the crawler's stored `source_path` is only a
hint and the committed *.jsonl stays valid across directory moves.

Embeddings are built separately by build_index.py (needs the GPU); kept out of
this pass so the parsing/chunking logic can be re-run quickly without the GPU.

Run per municipality: `python3 ingest.py --municipality <slug>`.
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymupdf as fitz
import signal

import muni

# All crawl outputs are merged into one index. docs.jsonl = main site
# (crawl.py), raad_docs.jsonl = council archive (crawl_raad.py),
# reference_docs.jsonl = curated national-rules summaries (scripts/add_reference.py).
MAX_CHUNK_CHARS = 1400
MIN_TEXT_CHARS = 40  # drop near-empty chunks

SKIP_PATH = re.compile(r"/(rss|search|zoeken)([/?]|$)", re.I)


def canon_url(url: str) -> str:
    """Normalize http->https, drop cache-buster/query strings, strip trailing
    slash. Used only for dedup -- the original URL is still stored."""
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    url = url.split("?", 1)[0]
    url = url.split("#", 1)[0]
    if url.endswith("/") and not url.endswith("://"):
        # keep the bare origin ("https://host/") intact, strip deeper paths
        if url.count("/") > 2:
            url = url.rstrip("/")
    return url


def split_long(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return [text] if text else []
    parts, cur = [], ""
    for sentence in re.split(r"(?<=[.;:])\s+", text):
        # A "sentence" with no [.;:] at all (e.g. a listing/table page dumped
        # as one blob) can itself be huge -- seen in practice: a single
        # Dordrecht page with no punctuation produced one ~1.24M-char
        # "sentence", which as one unsplit chunk repeatedly stalled the
        # embedding step for 90+ minutes. Hard-wrap any oversized piece
        # (independent of the accumulation logic below) so no chunk can ever
        # come out larger than a small multiple of `limit`.
        if len(sentence) > limit * 4:
            for i in range(0, len(sentence), limit):
                piece = sentence[i:i + limit].strip()
                if piece:
                    parts.append(piece)
            cur = ""
            continue
        if cur and len(cur) + len(sentence) + 1 > limit:
            parts.append(cur.strip())
            cur = sentence
        else:
            cur = f"{cur} {sentence}".strip()
    if cur:
        parts.append(cur.strip())
    return parts


# Hard cap on pages parsed per PDF. Seen in practice: two 127MB PDFs in
# Dordrecht's crawl (thousands of pages each) drove chunk_pdf() to grind at
# ~100% CPU for 2+ hours per ingest attempt -- genuinely compute-bound
# page-by-page text extraction, not an I/O stall, so a timeout around the
# whole subprocess (run_step's 6h) never helps in practice. Better to index
# the first N pages of a monster PDF than let one file stall a municipality
# indefinitely; N is generous enough that this never bites a normal document.
MAX_PDF_PAGES = 500


PDF_TIMEOUT_S = 45  # hard wall-clock budget per PDF; corrupt/huge scans can make
# MuPDF spin forever, so skip a PDF that exceeds this instead of hanging ingest.
MAX_PDF_SIZE_MB = 20  # skip very large scans (annual reports etc.) that make MuPDF
# render for minutes while holding the GIL (the SIGALRM timeout cannot interrupt it).


class _PDFTimeout(Exception):
    pass


def _pdf_timeout_handler(signum, frame):
    raise _PDFTimeout()


def chunk_pdf(path: Path, doc_id: str) -> list[dict]:
    chunks = []
    try:
        if path.stat().st_size > MAX_PDF_SIZE_MB * 1024 * 1024:
            print(f"  ! SKIP {path.name}: {path.stat().st_size // 1048576}MB > {MAX_PDF_SIZE_MB}MB", flush=True)
            return chunks
    except OSError:
        pass
    prev_handler = signal.signal(signal.SIGALRM, _pdf_timeout_handler)
    signal.alarm(PDF_TIMEOUT_S)
    try:
        with fitz.open(path) as pdf:
            n_pages = pdf.page_count
            if n_pages > MAX_PDF_PAGES:
                print(f"  ! {path.name}: {n_pages} pages, indexing first {MAX_PDF_PAGES} only", flush=True)
            for pno, page in enumerate(pdf, start=1):
                if pno > MAX_PDF_PAGES:
                    break
                text = page.get_text("text").strip()
                for piece in split_long(text):
                    if len(piece) >= MIN_TEXT_CHARS:
                        chunks.append({
                            "document": doc_id,
                            "page_start": pno,
                            "page_end": pno,
                            "text": piece,
                            "bbox_y0": None,
                            "bbox_y1": None,
                        })
    except _PDFTimeout:
        print(f"  ! TIMEOUT {path.name} after {PDF_TIMEOUT_S}s: skipping", flush=True)
    except Exception as e:
        print(f"  ! failed to parse {path.name}: {e}", flush=True)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev_handler)
    return chunks


def main():
    parser = argparse.ArgumentParser()
    muni.add_muni_arg(parser)
    args = parser.parse_args()

    dd = muni.data_dir(args.municipality)
    pdf_dir = dd / "pdfs"
    db_path = dd / "index.sqlite"
    docs_sources = [
        dd / "crawl" / "docs.jsonl",
        dd / "crawl" / "raad_docs.jsonl",
        dd / "crawl" / "reference_docs.jsonl",
    ]

    sources = [p for p in docs_sources if p.exists()]
    if not sources:
        print("no crawl output; run crawl.py / crawl_raad.py first", flush=True)
        return
    print(f"reading {len(sources)} crawl source(s) for {args.municipality}", flush=True)

    dd.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.executescript(
        """
        CREATE TABLE documents (
            id TEXT PRIMARY KEY, title TEXT, url TEXT, doc_type TEXT,
            filename TEXT, pages INTEGER, published_at TEXT, site TEXT
        );
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY,
            document TEXT, page_start INTEGER, page_end INTEGER,
            text TEXT, bbox_y0 REAL, bbox_y1 REAL
        );
        CREATE INDEX idx_chunks_doc ON chunks(document);
        """
    )

    # ---- pass 1: dedup by canonical URL, prefer the pdf record ----
    best: dict[str, dict] = {}
    order: list[str] = []
    n_html = n_pdf = 0
    for src in sources:
        for line in open(src, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            url = d.get("url", "")
            if not url or SKIP_PATH.search(url):
                continue
            key = canon_url(url)
            d["url"] = url
            if key in best:
                # a pdf record (with a real file) beats an html record at the same URL
                if d.get("doc_type") == "pdf" and best[key].get("doc_type") != "pdf":
                    best[key] = d
            else:
                best[key] = d
                order.append(key)

    chunk_id = 0
    total_chunks = 0
    for key in order:
        d = best[key]
        doc_id = d["id"]
        doc_type = d.get("doc_type", "html")
        title = (d.get("title") or "").strip() or urlparse(d["url"]).path.rsplit("/", 1)[-1] or d["url"]
        title = unquote(title)  # PDF filenames are URL-encoded (Coalitieakkoord%20'Samen...')
        if doc_type == "pdf":
            n_pdf += 1
            filename = Path(d.get("source_path", "")).name or f"{doc_id}.pdf"
            db.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)",
                (doc_id, title, d["url"], "pdf", filename,
                 d.get("pages"), d.get("published_at"), d.get("site")),
            )
            src = pdf_dir / filename
            chunks = chunk_pdf(src, doc_id) if src.exists() else []
        else:
            n_html += 1
            db.execute(
                "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?)",
                (doc_id, title, d["url"], "html", None,
                 None, d.get("published_at"), d.get("site")),
            )
            chunks = [
                {"document": doc_id, "page_start": None, "page_end": None,
                 "text": piece, "bbox_y0": None, "bbox_y1": None}
                for piece in split_long(d.get("text", ""))
                if len(piece) >= MIN_TEXT_CHARS
            ]

        for c in chunks:
            db.execute(
                "INSERT INTO chunks VALUES (?,?,?,?,?,?,?)",
                (chunk_id, c["document"], c["page_start"], c["page_end"],
                 c["text"], c["bbox_y0"], c["bbox_y1"]),
            )
            chunk_id += 1
        total_chunks += len(chunks)

    db.commit()
    n_docs = db.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    db.close()
    print(f"done: {n_docs} documents ({n_html} html, {n_pdf} pdf), "
          f"{total_chunks} chunks -> {db_path}", flush=True)


if __name__ == "__main__":
    main()
