#!/usr/bin/env python3
"""Live web-monitor voor de gemeente-onboarding pipeline (poort 8906).

De valkuil: state.json van de grote/trap-crawls is honderden MB's (almere
823MB, delft 278MB, apeldoorn 114MB). Een gewone json.load() op die bestanden
kost tientallen seconden per stuk, dus de tellers (`pending`-URLs, `docs`,
`pdfs`) worden hier uit de ruwe tekst gescand i.p.v. de array te parsen.

De snapshot draait in een achtergrond-thread; de HTTP handler serveert altijd
de laatst voltooide snapshot, dus een trage poll blokkeert de pagina nooit.
"""
import json
import os
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUEUE_PATH = REPO / "scripts" / "onboarding_queue.json"
DATA = REPO / "data"
PORT = int(os.environ.get("MONITOR_PORT", "8906"))
POLL_SECONDS = 3
STATE_TTL = 30   # min. tijd tussen twee state.json-herlezingen per gemeente

# state.json is single-line JSON: {"seen": [...], "pending": [...], "docs": N, "pdfs": N}
# (json.dumps met default-separators -> spatie na ":" en ",").  seen/pending zijn
# gesorteerde lijsten URL-strings; URLs zijn percent-encoded, dus bevatten géén
# ruwe comma/quote/[...] -- alleen de JSON-delimiters doen dat.  De sleutels
# staan in vaste volgorde: ...seen], "pending": [...], "docs": N, "pdfs": N}
#
# Vroeger zat hier een regex met (.*?) over het héle (tot 823MB) bestand; dat
# backtrackte minutenlang en matchte een "docs" die in een URL-query zat (te laag
# getal).  Daarom nu: tellers vanaf de staart (waar docs/pdf als getal staan) en
# de pending-array afgebakend met bytes.find/rfind -- lineair, geen backtracking.
_DOCS = re.compile(rb'"docs":\s*(\d+)')
_PDFS = re.compile(rb'"pdfs":\s*(\d+)')
_PEND_END = b'], "docs":'          # einde van de pending-array, vlak voor de docs-sleutel
_PEND_OPEN = b'"pending": ['        # begin van de pending-array (sleutel + spatie + "[")


def _scan_state(path: Path):
    """-> (docs, pdfs, pending_count) uit state.json zonder json.parse.

    Eén lineaire lezing + bytes.find/rfind (C-snel).  docs/pdf staan als getal op
    het einde; de pending-array wordt afgebakend tussen `], "pending": [` en
    `], "docs":`, daarna top-level komma's tellen (element = komma + 1)."""
    try:
        raw = path.read_bytes()
    except OSError:
        return (0, 0, 0)

    docs = pdfs = 0
    m = _DOCS.search(raw)
    if m:
        docs = int(m.group(1))
    m = _PDFS.search(raw)
    if m:
        pdfs = int(m.group(1))

    pending = 0
    # einde van de pending-array: de laatste `], "docs":` vóór de docs-sleutel.
    pend_end = raw.rfind(_PEND_END)
    if pend_end != -1:
        # begin: de `], "pending": [` die de seen-array afsluit (vóór pend_end).
        start = raw.rfind(_PEND_OPEN, 0, pend_end)
        if start != -1:
            body = raw[start + len(_PEND_OPEN):pend_end]
            pending = body.count(b",") + 1 if body.strip() else 0
    return docs, pdfs, pending


_cache = {}
def file_mtime(path: Path):
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def active_slugs() -> set[str]:
    """Slugs met een draaiend crawl.py-proces, uit /proc cmdlines (geen ps-spawn)."""
    slugs = set()
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                cmd = open(f"/proc/{pid}/cmdline", "rb").read()
            except OSError:
                continue
            if b"crawl.py" not in cmd:
                continue
            parts = cmd.replace(b"\x00", b" ").decode(errors="replace").split()
            if "--municipality" in parts:
                slugs.add(parts[parts.index("--municipality") + 1])
    except Exception:
        pass
    return slugs


def read_state(slug: str):
    """Tellers uit state.json.  Herlezen gebeurt alleen als de mtime nieuwer is
    dan de laatste lezing ÉN er >= STATE_TTL seconden verstreken zijn — de
    crawler herschrijft state.json elke checkpoint (mtime ververst dus continu),
    maar op een 823MB bestand is elke herlezing duur.  Tussen checkpoints
    verandert de inhoud toch niet zinvol voor een monitor."""
    p = DATA / slug / "crawl" / "state.json"
    mt = file_mtime(p)
    if mt is None:
        return (0, 0, 0)
    prev = _cache.get(("st", slug))
    if prev and time.time() - prev[2] < STATE_TTL:
        return prev[1]          # throttle: nog niet opnieuw lezen
    if prev and prev[0] == mt:
        prev = (mt, prev[1], time.time())
        _cache[("st", slug)] = prev
        return prev[1]
    try:
        val = _scan_state(p)
    except Exception:
        val = (0, 0, 0)
    _cache[("st", slug)] = (mt, val, time.time())
    return val


def read_index(slug: str):
    """(docs, chunks) uit index.sqlite — alleen voor done/crawled gemeentes."""
    p = DATA / slug / "index.sqlite"
    mt = file_mtime(p)
    if mt is None:
        return (0, 0)
    prev = _cache.get(("ix", slug))
    if prev and prev[0] == mt:
        return prev[1]
    try:
        con = sqlite3.connect(p)
        try:
            docs = con.execute("select count(*) from documents").fetchone()[0]
            chunks = con.execute("select count(*) from chunks").fetchone()[0]
            val = (docs, chunks)
        finally:
            con.close()
    except Exception:
        val = (0, 0)
    _cache[("ix", slug)] = (mt, val, time.time())
    return val


def compute():
    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8")) or []
    running = active_slugs()
    rows, agg = [], {"done": 0, "pending": 0, "crawled": 0, "failed": 0,
                     "crawl_docs": 0, "crawl_pdfs": 0, "pending_urls": 0,
                     "idx_docs": 0, "idx_chunks": 0}
    for q in queue:
        slug, name, status = q["slug"], q["name"], q["status"]
        agg[status] = agg.get(status, 0) + 1
        if slug in running:
            cd, pdfs, pend = read_state(slug)
        else:
            cd, pdfs, pend = 0, 0, 0
        # index.sqlite bestaat (en verandert) alleen voor reeds afgeronde
        # gemeentes; de lopende/onbekende hebben nog geen index.
        if status in ("done", "crawled"):
            idx_docs, idx_chunks = read_index(slug)
        else:
            idx_docs, idx_chunks = 0, 0
        agg["crawl_docs"] += cd
        agg["crawl_pdfs"] += pdfs
        agg["pending_urls"] += pend
        agg["idx_docs"] += idx_docs
        agg["idx_chunks"] += idx_chunks
        rows.append({"slug": slug, "name": name, "status": status,
                     "error": q.get("error"),
                     "crawl_docs": cd, "pdfs": pdfs, "pending_urls": pend,
                     "idx_docs": idx_docs, "idx_chunks": idx_chunks})
    order = {"pending": 0, "crawled": 1, "failed": 2, "done": 3}
    rows.sort(key=lambda r: (order[r["status"]], r["name"].lower()))
    return {"ts": time.time(), "agg": agg, "rows": rows}


LATEST = {"ts": 0, "agg": None, "rows": []}


def refresh_loop():
    while True:
        t0 = time.time()
        try:
            LATEST.update(compute())
        except Exception as e:
            LATEST["error"] = str(e)
        # slaap tot de poll-interval vol is; een trage compute vertraagt dus
        # alleen de volgende poll, blokkeert de HTTP handler nooit.
        time.sleep(max(0.5, POLL_SECONDS - (time.time() - t0)))


HTML = """<!doctype html><html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Onboarding monitor</title>
<style>
:root{--bg:#0f1420;--panel:#181f30;--line:#26304a;--fg:#e6ebf5;--dim:#8b96b0;
--ok:#2ec27e;--run:#4a9eff;--fail:#e5534b;--warn:#e8a33d}
*{box-sizing:border-box}
body{margin:0;font:14px/1.45 ui-sans-serif,system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);padding:20px}
h1{font-size:18px;margin:0 0 2px}.sub{color:var(--dim);font-size:12px;margin-bottom:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.card .v{font-size:24px;font-weight:700;font-variant-numeric:tabular-nums}
.card .k{color:var(--dim);font-size:11px;text-transform:uppercase;letter-spacing:.04em}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
thead th{position:sticky;top:0;background:#1d2740;text-align:right;padding:8px 10px;font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.03em;border-bottom:1px solid var(--line);white-space:nowrap}
thead th:first-child,tbody td:first-child{text-align:left}
td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums;white-space:nowrap}
tbody tr:hover{background:#202a45}
.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600}
.b.done{background:rgba(46,194,126,.15);color:var(--ok)}
.b.pending,.b.crawled{background:rgba(74,158,255,.15);color:var(--run)}
.b.failed{background:rgba(229,83,75,.15);color:var(--fail)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.stall{color:var(--warn)} .dead{color:var(--fail)}
.arrow{color:var(--dim)}
#ago{color:var(--dim);font-size:11px;margin-top:10px}
</style></head><body>
<h1>Gemeente-onboarding — live</h1>
<div class="sub">pollt elke 2s · <span class="mono">gecrawld</span> en <span class="mono">nog URLs</span> komen live uit <span class="mono">state.json</span> · <span class="mono">index docs/chunks</span> uit <span class="mono">index.sqlite</span> · ▲▼ = verschil sinds vorige poll</div>
<div class="cards" id="cards"></div>
<table><thead><tr>
<th>Gemeente</th><th>Status</th><th>Gecrawld</th><th>PDF</th><th>Nog URLs</th><th>Index docs</th><th>Chunks</th>
</tr></thead><tbody id="t"></tbody></table>
<div id="ago"></div>
<script>
let prev={};
function fmt(n){return n==null?'–':n.toLocaleString('nl-NL')}
function el(tag,cls,txt){const e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e}
function delta(slug,key,val){const p=prev[slug];prev[slug]=prev[slug]||{};const old=prev[slug][key];prev[slug][key]=val;
  if(old==null||old===val)return'';const d=val-old;const a=el('span','arrow',' '+(d>0?'▲':'▼')+Math.abs(d).toLocaleString('nl-NL'));
  a.style.color=d>0?'var(--ok)':'var(--fail)';return a}
function card(v,k){const c=document.createElement('div');c.className='card';c.append(el('div','v',fmt(v)));c.append(el('div','k',k));return c}
async function poll(){
  try{
    const r=await fetch('/api/snapshot');const d=await r.json();
    if(d.error){document.getElementById('ago').textContent='fout: '+d.error;return}
    const a=d.agg;
    document.getElementById('cards').innerHTML=[
      card(a.done,'done'),card(a.pending,'pending'),card(a.crawled,'crawled'),card(a.failed,'failed'),
      card(a.crawl_docs,'gecrawlde docs'),card(a.pending_urls,'nog URLs'),card(a.idx_docs,'index docs'),card(a.idx_chunks,'chunks')
    ].map(e=>e.outerHTML).join('');
    const tb=document.getElementById('t');tb.innerHTML='';
    for(const m of d.rows){
      const tr=document.createElement('tr');
      tr.append(el('td',null,m.name));
      const tdc=el('td');const bad=el('span','b '+m.status,m.status);tdc.append(bad);tr.append(tdc);
      const cd=el('td','mono');cd.append(document.createTextNode(fmt(m.crawl_docs)));
      if(m.status==='pending'||m.status==='crawled') cd.append(delta(m.slug,'crawl_docs',m.crawl_docs));
      const pu=el('td','mono');pu.append(document.createTextNode(fmt(m.pending_urls)));pu.append(delta(m.slug,'pending',m.pending_urls));
      tr.append(cd, el('td','mono',fmt(m.pdfs)), pu, el('td','mono',fmt(m.idx_docs)), el('td','mono',fmt(m.idx_chunks)));
      tb.append(tr);
    }
    document.getElementById('ago').textContent='bijgewerkt '+new Date(d.ts*1000).toLocaleTimeString('nl-NL');
  }catch(e){document.getElementById('ago').textContent='poll fout: '+e}
}
poll();setInterval(poll,2000);
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/snapshot":
            body = json.dumps(LATEST).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/index.html"):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *a):
        pass


if __name__ == "__main__":
    threading.Thread(target=refresh_loop, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
