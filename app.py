"""Gemeente IJsselstein smart search — FastAPI backend.

- POST /api/search   semantic search over all crawled chunks (HTML + PDF)
- POST /api/ask      RAG: retrieve + GPT-OSS-120B answer with [n] citations
- GET  /api/documents list of indexed documents
- GET  /pdf-image/{id}  rendered PNG of the PDF page a chunk is on
- GET  /pdf/{file}      the source PDF (Range requests, #page=N deep links)
- GET  /api/statistics  usage stats
- /                     single-page frontend (static/index.html)

Same GPU-retrieval pattern as wilders-search / lift-normen-search: cosine
similarity over the whole BGE-M3 embedding matrix (no FAISS at this scale),
LLM is GPT-OSS-120B served by llama.cpp on the gx10 node.
"""
import hashlib
import mimetypes
import os
import re
import sqlite3
from pathlib import Path
from urllib.parse import quote

mimetypes.add_type("image/webp", ".webp")

import httpx
import numpy as np
import pymupdf as fitz
import torch
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from embedder import Embedder

BASE = Path(__file__).parent
DATA_DIR = BASE / "data"
PDF_DIR = DATA_DIR / "pdfs"
STATS_DB = BASE / "stats.sqlite"  # outside data/ so re-indexing keeps history

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://100.64.x.x:8083/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-oss-120b")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "none")

app = FastAPI(title="Gemeente IJsselstein zoeken")


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/pdf/"):
        # In-app browsers (WhatsApp/Instagram) treat a bare PDF response as
        # ambiguous and fail to open it; explicit inline disposition fixes it.
        response.headers["Content-Disposition"] = "inline"
    elif path == "/" or path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


_state: dict = {}


@app.on_event("startup")
def load_index():
    db = sqlite3.connect(DATA_DIR / "index.sqlite", check_same_thread=False)
    db.row_factory = sqlite3.Row
    emb = np.load(DATA_DIR / "embeddings.npy")
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    matrix = torch.from_numpy(emb).to(device)
    documents = {
        r["id"]: dict(r) for r in db.execute("SELECT * FROM documents ORDER BY id")
    }
    _state.update(
        db=db, matrix=matrix, device=device,
        embedder=Embedder(device=device, max_length=1024),
        documents=documents,
        pdf_docs={},
    )
    print(f"index loaded: {matrix.shape[0]} chunks over {len(documents)} documents on {device}")


# ------------------------------------------------------------------ retrieval
def chunk_row_to_dict(row: sqlite3.Row, score: float | None = None) -> dict:
    doc = _state["documents"].get(row["document"], {})
    is_pdf = doc.get("doc_type") == "pdf"
    d = {
        "id": row["id"],
        "document": row["document"],
        "document_title": doc.get("title") or row["document"],
        "doc_type": doc.get("doc_type", "html"),
        "page_start": row["page_start"],
        "page_end": row["page_end"],
        "text": row["text"],
        "url": doc.get("url", ""),          # source hyperlink (HTML page / CDN PDF)
        "published_at": doc.get("published_at"),
    }
    if is_pdf:
        filename = doc.get("filename") or f"{row['document']}.pdf"
        d["pdf_url"] = f"/pdf/{filename}#page={row['page_start']}"
        d["image_url"] = f"/pdf-image/{row['id']}"
    else:
        d["pdf_url"] = None
        d["image_url"] = None
    if score is not None:
        d["score"] = round(score, 4)
    return d


def retrieve(query: str, top_k: int, document: str | None = None) -> list[dict]:
    st = _state
    q = st["embedder"].encode([query]).to(st["device"])
    scores = (st["matrix"] @ q.T).squeeze(1).float()
    if document:
        mask_ids = {
            r["id"] for r in st["db"].execute("SELECT id FROM chunks WHERE document=?", (document,))
        }
        mask = torch.tensor(
            [i in mask_ids for i in range(scores.shape[0])], device=scores.device
        )
        scores = torch.where(mask, scores, torch.tensor(-1.0, device=scores.device))
    k = min(top_k, scores.shape[0])
    vals, idx = torch.topk(scores, k)
    results = []
    for score, cid in zip(vals.tolist(), idx.tolist()):
        if score < 0:
            continue
        row = st["db"].execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
        results.append(chunk_row_to_dict(row, score))
    return results


# ---------------------------------------------------------------- agentic fetch
# When semantic retrieval is weak (max cosine score below AGENTIC_THRESHOLD),
# fall back to the site's own search engine — a server-rendered, Solr-backed
# *keyword* search at /zoeken?trefwoord=... — fetch the top pages and inject
# their text as sources. This is the "if it's not in the index, go get it"
# behaviour the user asked for: the keyword search complements the embeddings
# (great for exact terms/abbreviations the embeddings rank poorly).
AGENTIC_THRESHOLD = 0.50
AGENTIC_MAX_RESULTS = 3     # site-search pages to fetch
AGENTIC_MAX_CHUNKS = 4      # total injected chunks (cap LLM context)
AGENTIC_CHUNK_CHARS = 1500
SITE_SEARCH_URL = "https://www.ijsselstein.nl/zoeken"
AGENTIC_UA = "GemeenteZoek/1.0 (https://gemeente.multicode.nl; agentic-search)"
AGENTIC_NAV_TAGS = ("header", "nav", "footer", "script", "style", "noscript", "form")


def site_search(query: str, max_results: int = AGENTIC_MAX_RESULTS) -> list[dict]:
    url = f"{SITE_SEARCH_URL}?trefwoord={quote(query)}"
    try:
        r = httpx.get(url, timeout=20.0, follow_redirects=True,
                      headers={"User-Agent": AGENTIC_UA})
        r.raise_for_status()
    except Exception as e:
        print(f"agentic site_search failed: {e}")
        return []
    soup = BeautifulSoup(r.text, "lxml")
    results = []
    for li in soup.select("div.search-results li[class*='__result']"):
        a = li.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if href.startswith("/"):
            href = "https://www.ijsselstein.nl" + href
        if "ijsselstein.nl" not in href:
            continue
        title = a.get_text(" ", strip=True)
        results.append({"title": title, "url": href,
                        "snippet": li.get_text(" ", strip=True)[:400]})
        if len(results) >= max_results:
            break
    return results


def extract_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in AGENTIC_NAV_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    return soup.get_text(" ", strip=True)


def chunk_text(text: str, limit: int = AGENTIC_CHUNK_CHARS) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return [text] if text else []
    parts, cur = [], ""
    for sentence in re.split(r"(?<=[.;:])\s+", text):
        if cur and len(cur) + len(sentence) + 1 > limit:
            parts.append(cur.strip())
            cur = sentence
        else:
            cur = f"{cur} {sentence}".strip()
    if cur:
        parts.append(cur.strip())
    return parts


async def agentic_fetch(question: str) -> list[dict]:
    hits = site_search(question)
    if not hits:
        return []
    sources = []
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True,
                                 headers={"User-Agent": AGENTIC_UA}) as client:
        for hit in hits:
            try:
                r = await client.get(hit["url"])
                if r.status_code != 200:
                    continue
                text = extract_page_text(r.text)
                if len(text) < 80:
                    continue
            except Exception as e:
                print(f"agentic fetch_page failed {hit['url']}: {e}")
                continue
            digest = hashlib.sha1(hit["url"].encode()).hexdigest()[:12]
            for j, piece in enumerate(chunk_text(text)):
                if len(piece) < 40:
                    continue
                sources.append({
                    "id": f"agentic:{digest}:{j}",
                    "document": f"agentic:{digest}",
                    "document_title": hit["title"],
                    "doc_type": "html",
                    "page_start": None,
                    "page_end": None,
                    "text": piece,
                    "url": hit["url"],
                    "published_at": None,
                    "pdf_url": None,
                    "image_url": None,
                    "score": None,
                    "agentic": True,
                })
                if len(sources) >= AGENTIC_MAX_CHUNKS:
                    return sources
    return sources


# ---------------------------------------------------------------- usage stats
def _stats_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(STATS_DB, timeout=10)
    conn.execute("""CREATE TABLE IF NOT EXISTS queries (
        ts TEXT DEFAULT (datetime('now')), mode TEXT, ip TEXT, query TEXT)""")
    return conn


def client_ip(request: Request) -> str:
    ip = request.headers.get("x-real-ip") or ""
    if not ip:
        fwd = request.headers.get("x-forwarded-for", "")
        ip = fwd.split(",")[0].strip()
    return ip or (request.client.host if request.client else "unknown")


def log_query(request: Request, mode: str, query: str):
    try:
        with _stats_conn() as conn:
            conn.execute(
                "INSERT INTO queries (mode, ip, query) VALUES (?,?,?)",
                (mode, client_ip(request), query[:500]),
            )
    except Exception as e:
        print(f"stats logging failed: {e}")


@app.get("/api/statistics")
def api_statistics():
    with _stats_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
        by_mode = dict(conn.execute("SELECT mode, COUNT(*) FROM queries GROUP BY mode").fetchall())
        unique_ips = conn.execute("SELECT COUNT(DISTINCT ip) FROM queries").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*), COUNT(DISTINCT ip) FROM queries WHERE date(ts) = date('now')"
        ).fetchone()
        per_day = conn.execute("""
            SELECT date(ts) d, COUNT(*), COUNT(DISTINCT ip)
            FROM queries WHERE ts >= datetime('now','-30 days')
            GROUP BY d ORDER BY d""").fetchall()
        first = conn.execute("SELECT MIN(date(ts)) FROM queries").fetchone()[0]
    return {
        "total_queries": total,
        "search_queries": by_mode.get("search", 0),
        "ask_queries": by_mode.get("ask", 0),
        "unique_ips": unique_ips,
        "today_queries": today[0],
        "today_unique_ips": today[1],
        "since": first,
        "per_day": [{"date": d, "queries": q, "unique_ips": u} for d, q, u in per_day],
    }


class SearchReq(BaseModel):
    query: str
    top_k: int = 20
    document: str | None = None


@app.post("/api/search")
def api_search(req: SearchReq, request: Request):
    if not req.query.strip():
        raise HTTPException(400, "empty query")
    log_query(request, "search", req.query)
    return {"results": retrieve(req.query, min(req.top_k, 100), req.document)}


@app.get("/api/documents")
def api_documents():
    return {"documents": list(_state["documents"].values())}


# ------------------------------------------------------------------------ RAG
ANSWER_SYSTEM = """Je bent een digitale assistent van de gemeente IJsselstein. Burgers stellen
vragen over gemeentelijke diensten, regelingen, procedures en het beleid van
IJsselstein. Je krijgt genummerde fragmenten uit de officiële website en
documenten (PDF's) van de gemeente IJsselstein.

Beantwoord de vraag uitsluitend op basis van de fragmenten:
- Geef een praktisch, helder antwoord in het Nederlands van maximaal circa 300
  woorden. Herhaal geen zinnen of citaten.
- Zet na elke bewering het BRONNUMMER tussen blokhaken in het formaat [3] —
  dat is het nummer voor "Bron:" in het fragment. Gebruik precies dit formaat,
  geen andere haakjes of combinaties.
- Fragmenten die niets met de vraag te maken hebben negeer je volledig.
- Vermeld bedragen, termijnen, locaties en contactgegevens letterlijk zoals ze
  in de fragmenten staan — verzin niets en rond niets af.
- Als fragmenten elkaar tegenspreken (bijv. een oudere pagina vs. een nieuwere),
  benoem dat en geef bij twijfel de meest recente weer.
- Staat het antwoord niet in de fragmenten, zeg dat dan expliciet en verwijs de
  burger naar de website www.ijsselstein.nl of het algemene telefoonnummer —
  maar verzin dat telefoonnummer niet als het niet in de fragmenten staat.
- Blijf feitelijk, neutraal en beknopt.

Opmaak (eenvoudige Markdown, niets anders):
- Zet je meerdere losse punten naast elkaar? Gebruik bullet-punten met "- ".
- Gebruik **vet** voor kernbegrippen en concrete waarden (bijv. **€ 49,80**).
- Gebruik geen kopjes (#) en geen codeblokken."""


def build_excerpts(sources: list[dict]) -> str:
    parts = []
    for i, s in enumerate(sources):
        if s["doc_type"] == "pdf":
            loc = f"PDF, pagina {s['page_start']}"
        else:
            loc = "webpagina"
        parts.append(
            f"[{i+1}] Bron: {s['document_title']} | {loc}\n{s['text']}"
        )
    return "\n\n".join(parts)


MAX_TOTAL_SOURCE_CHARS = 8200  # keep the prompt well under llama.cpp n_ctx=4096


def fit_sources(sources: list[dict], max_chars: int = MAX_TOTAL_SOURCE_CHARS) -> list[dict]:
    """Trim source texts so their total length fits the LLM context budget.

    Sources are ordered most-relevant first, so we keep the head intact and
    truncate/drop the tail. The gx10 llama.cpp server runs n_ctx=4096; without
    this cap an agentic fetch that prepends several long chunks pushes the
    prompt past the limit and returns 400 'exceeds context size'."""
    out, total = [], 0
    for s in sources:
        text = s.get("text", "") or ""
        if total >= max_chars:
            break
        if total + len(text) > max_chars:
            text = text[: max(200, max_chars - total)]
        total += len(text)
        out.append({**s, "text": text})
    return out


def user_turn(question: str, excerpts: str) -> str:
    return f"Fragmenten:\n\n{excerpts}\n\nVraag: {question}"


async def call_llm(messages: list[dict]) -> str:
    """GPT-OSS-120B via llama.cpp (OpenAI-compatible). GPT-OSS is a reasoning
    model: without enable_thinking:false the whole budget goes to
    reasoning_content and `content` stays empty, so always send it. A generous
    max_tokens leaves room for the (small) reasoning prefix + the real answer."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "max_tokens": 1800,
                "temperature": 0.2,
                "messages": messages,
                "chat_template_kwargs": {"enable_thinking": False},
            },
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"]
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
        # GPT-OSS sometimes emits CJK full-width brackets for citations (【6】/［6］);
        # normalize to ASCII so both citation detection here and the frontend match.
        for a, b in (("【", "["), ("】", "]"), ("［", "["), ("］", "]")):
            answer = answer.replace(a, b)
        return answer


class Turn(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AskReq(BaseModel):
    question: str
    top_k: int = 8
    document: str | None = None
    history: list[Turn] = []
    known_source_ids: list[int] = []


MAX_SOURCES_IN_CONTEXT = 16


@app.post("/api/ask")
async def api_ask(req: AskReq, request: Request):
    if not req.question.strip():
        raise HTTPException(400, "empty question")
    log_query(request, "ask", req.question)

    known_sources = []
    if req.known_source_ids:
        db = _state["db"]
        for cid in req.known_source_ids:
            row = db.execute("SELECT * FROM chunks WHERE id=?", (cid,)).fetchone()
            if row:
                known_sources.append(chunk_row_to_dict(row))
    have = {s["id"] for s in known_sources}

    fresh = retrieve(req.question, min(req.top_k, 40), req.document)
    new_sources = [s for s in fresh if s["id"] not in have]

    agentic_sources: list[dict] = []
    agentic = False
    max_score = max((s.get("score", 0.0) for s in fresh), default=0.0)
    if max_score < AGENTIC_THRESHOLD and not req.document and not req.history:
        try:
            agentic_sources = await agentic_fetch(req.question)
        except Exception as e:
            print(f"agentic fetch failed: {e}")
        agentic = bool(agentic_sources)
        seen_urls = {s["url"] for s in fresh}
        agentic_sources = [s for s in agentic_sources if s["url"] not in seen_urls]

    sources = (known_sources + agentic_sources + new_sources)[:MAX_SOURCES_IN_CONTEXT]
    sources = fit_sources(sources)

    excerpts = build_excerpts(sources)
    messages = [{"role": "system", "content": ANSWER_SYSTEM}]
    messages += [{"role": t.role, "content": t.content} for t in req.history]
    messages.append({"role": "user", "content": user_turn(req.question, excerpts)})

    answer, error = None, None
    try:
        answer = await call_llm(messages)
    except Exception as e:
        error = str(e)

    if answer:
        cited: set[int] = set()
        for group in re.findall(r"\[([\d,\-\s]+)\]", answer):
            for part in re.split(r"[,\s]+", group.strip()):
                if "-" in part:
                    a, _, b = part.partition("-")
                    if a.isdigit() and b.isdigit():
                        cited.update(range(int(a), int(b) + 1))
                elif part.isdigit():
                    cited.add(int(part))
        for i, s in enumerate(sources):
            s["cited"] = (i + 1) in cited

    return {
        "answer": answer,
        "error": error,
        "sources": sources,
        "agentic": agentic,
        "user_message": user_turn(req.question, excerpts),
    }


# ------------------------------------------------------------ page images
MIN_IMAGE_HEIGHT = 100
CROP_PADDING = 12


def get_pdf_doc(filename: str) -> fitz.Document:
    cache = _state["pdf_docs"]
    if filename not in cache:
        cache[filename] = fitz.open(PDF_DIR / filename)
    return cache[filename]


@app.get("/pdf-image/{chunk_id}")
def pdf_image(chunk_id: int):
    row = _state["db"].execute("SELECT * FROM chunks WHERE id=?", (chunk_id,)).fetchone()
    if not row:
        raise HTTPException(404, "not found")
    doc_row = _state["documents"].get(row["document"])
    if not doc_row or doc_row.get("doc_type") != "pdf" or not row["page_start"]:
        raise HTTPException(404, "no image for this source")
    pdf = get_pdf_doc(doc_row["filename"])
    page = pdf[row["page_start"] - 1]

    # Whole-page render (gemeente documents have no clause structure to crop
    # to); bbox is stored NULL so this is the full page at a readable zoom.
    zoom = 1.6
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return Response(
        content=pix.tobytes("png"),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=2592000, immutable"},
    )


app.mount("/pdf", StaticFiles(directory=PDF_DIR), name="pdf")
app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
