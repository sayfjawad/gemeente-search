"""Fully autonomous onboarding of all remaining Dutch municipalities.

Runs the same crawl -> ingest -> build_index -> enable -> restart pipeline as
onboard_barendrecht.sh, looped over the ~336 municipalities in
gemeenten_336.json. Bulk/blind mode: no per-site CMS inspection, no
council-archive (Notubiz/iBabs) crawl, no reference curation -- just the
main-site crawler with whatever defaults muni.py/crawl.py already fall back
to safely. New municipalities' crawl/ and pdfs/ are created as symlinks into
the NAS (/mnt/nas-gemeente) from the start, matching the convention used for
the 6 already-onboarded municipalities -- never touches local disk on the Z8.

Pipelined, not strictly sequential (since 2026-08-23): crawling (own site,
no shared per-site rate limit between municipalities) and "finishing"
(ingest/build_index/enable/restart -- the last step hits the one shared
gemeente-search.service, serialized via RESTART_LOCK) run as two separate
worker pools, sized by ONBOARD_CRAWL_CONCURRENCY (default 6) and
ONBOARD_FINISH_CONCURRENCY (default 3). A municipality moves
pending -> crawled -> done/failed; as soon as one finishes crawling it's
handed to the finish pool while the crawl pool immediately starts the next
one -- a continuous pipeline, not fixed-size lockstep batches.

Resumable: progress (including the crawled-but-not-finished-yet state)
is persisted in onboarding_queue.json after every step, so a restart
(crash, reboot, systemd Restart=on-failure) picks up where it left off
rather than re-doing finished work.

One email per municipality outcome (not per pipeline step -- 336 of those
would flood the inbox), plus a batch-summary email every 20 completions and a
final summary when the whole queue is done. Every email carries a plain-
arithmetic forecast report (build_progress_report()) -- no AI involved.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_LIST = REPO / "scripts" / "gemeenten_336.json"
QUEUE_PATH = REPO / "scripts" / "onboarding_queue.json"
REGISTRY_PATH = REPO / "municipalities.json"
LOG = REPO / "scripts" / "onboard_all.log"
NAS_ROOT = Path("/mnt/nas-gemeente")
PY = str(REPO / ".venv" / "bin" / "python3")

# How many municipalities crawl concurrently, and how many run
# ingest+build_index+restart/verify ("finish") concurrently. Different
# municipalities hit different servers -- no shared per-site rate limit
# between them -- so this is a host-resource question, not a politeness
# one (crawl.py's own CRAWL_CONCURRENCY/CRAWL_DELAY handle politeness
# *within* a single site). Started at 6/3 on 2026-08-23 after confirming
# the host (80 cores, 754GB RAM) was barely touched by one crawl at a time;
# bump via env if monitoring during a run shows more headroom.
CRAWL_CONCURRENCY_MUNI = int(os.environ.get("ONBOARD_CRAWL_CONCURRENCY", "6"))
FINISH_CONCURRENCY = int(os.environ.get("ONBOARD_FINISH_CONCURRENCY", "3"))

# A crawl that fetches nothing still ingests and builds an (empty) index
# without erroring, so before 2026-08-24 a failed crawl was published as a
# live municipality: 14 of the first 236 reached the dropdown with 0-24
# documents. Nothing below this many documents gets enabled; it is marked
# failed instead, so it shows up for a retry rather than silently going live.
# The smallest healthy corpus so far is ~365 documents (Baarle-Nassau).
MIN_DOCUMENTS = int(os.environ.get("ONBOARD_MIN_DOCS", "50"))

# save_queue()/upsert_registry_entry() read-modify-write a shared JSON file;
# multiple worker threads calling either at once (now that crawling and
# finishing both run concurrently) need to not interleave. restart/verify
# hits the one shared gemeente-search.service -- two concurrent restarts
# would step on each other, so that specific call is fully serialized.
QUEUE_LOCK = threading.Lock()
REGISTRY_LOCK = threading.Lock()
RESTART_LOCK = threading.Lock()
TALLY_LOCK = threading.Lock()


def log(msg: str) -> None:
    line = f"[{__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def _du_bytes(path: Path) -> int:
    """Aggregate size via `du` (fast, doesn't follow symlinks -- so this
    correctly counts only local files under REPO/data, not the NAS content
    the crawl/pdfs symlinks point at, when called on REPO/data)."""
    if not path.exists():
        return 0
    try:
        r = subprocess.run(["du", "-sb", str(path)], capture_output=True, text=True, timeout=60)
        return int(r.stdout.split()[0]) if r.returncode == 0 and r.stdout.strip() else 0
    except Exception:
        return 0


def _fmt_mb(mb: float) -> str:
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.0f} MB"


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    if days:
        return f"{days}d {hours}u"
    if hours:
        return f"{hours}u {minutes}m"
    return f"{minutes}m"


def build_progress_report() -> str:
    """Plain arithmetic progress/forecast report, no AI involved -- static
    ratios from completed municipalities projected onto what's left. Meant
    to be rough (per the user's explicit ask), not precise: with only a
    handful of completed municipalities at any given time, especially early
    in the run, the per-capita ratios below are a thin sample."""
    done = [q for q in QUEUE if q["status"] == "done"]
    failed = [q for q in QUEUE if q["status"] == "failed"]
    pending = [q for q in QUEUE if q["status"] in ("pending", "crawled")]

    total_local_mb = _du_bytes(REPO / "data") / (1024 * 1024)
    total_nas_mb = _du_bytes(NAS_ROOT) / (1024 * 1024)

    sample_pop = sum(q.get("pop", 0) for q in done)
    sample_local_mb = sum(_du_bytes(REPO / "data" / q["slug"]) for q in done) / (1024 * 1024)
    sample_nas_mb = sum(_du_bytes(NAS_ROOT / q["slug"]) for q in done) / (1024 * 1024)
    remaining_pop = sum(q.get("pop", 0) for q in pending)

    extra_local_mb = extra_nas_mb = None
    if sample_pop > 0:
        extra_local_mb = (sample_local_mb / sample_pop) * remaining_pop
        extra_nas_mb = (sample_nas_mb / sample_pop) * remaining_pop

    durations = [q["duration_s"] for q in done if q.get("duration_s")]
    avg_duration_s = sum(durations) / len(durations) if durations else None
    eta_s = avg_duration_s * len(pending) if avg_duration_s else None

    lines = [
        "=== Prognose-rapport (simpele berekening op basis van aantallen/inwoners, geen AI) ===",
        "",
        f"Voortgang: {len(done)} live, {len(failed)} mislukt, {len(pending)} resterend (van {len(QUEUE)})",
        "",
        "Tijdsinschatting (gemiddelde doorlooptijd afgeronde gemeentes x resterend aantal):",
    ]
    if avg_duration_s:
        lines.append(f"  Gemiddeld per gemeente: {_fmt_duration(avg_duration_s)}")
        lines.append(f"  Resterende tijd (ruw):  {_fmt_duration(eta_s)}")
    else:
        lines.append("  (nog geen doorlooptijd gemeten -- verschijnt na de eerstvolgende afronding)")

    lines += [
        "",
        "Schijfgebruik-prognose (geschaald naar inwonertal, ruwe indicatie):",
        f"  {'':<26}{'Nu':>10}{'Erbij verwacht':>18}{'Totaal verwacht':>18}",
    ]
    if extra_local_mb is not None:
        lines.append(
            f"  {'Embeddings-DB (lokaal)':<26}{_fmt_mb(total_local_mb):>10}"
            f"{_fmt_mb(extra_local_mb):>18}{_fmt_mb(total_local_mb + extra_local_mb):>18}"
        )
        lines.append(
            f"  {'Ruwe crawl-data (NAS)':<26}{_fmt_mb(total_nas_mb):>10}"
            f"{_fmt_mb(extra_nas_mb):>18}{_fmt_mb(total_nas_mb + extra_nas_mb):>18}"
        )
    else:
        lines.append(f"  {'Embeddings-DB (lokaal)':<26}{_fmt_mb(total_local_mb):>10}{'onbekend':>18}{'onbekend':>18}")
        lines.append(f"  {'Ruwe crawl-data (NAS)':<26}{_fmt_mb(total_nas_mb):>10}{'onbekend':>18}{'onbekend':>18}")

    if done:
        sample = ", ".join(f"{q['name']} ({q.get('pop', '?')} inw.)" for q in done)
        lines.append(f"  Gebaseerd op {len(done)} afgeronde gemeente(n): {sample}")
        lines.append("  Ruwe indicatie -- weinig datapunten, geen garantie op nauwkeurigheid.")

    return "\n".join(lines)


def notify(subject: str, body: str) -> None:
    try:
        body = f"{body}\n\n{build_progress_report()}"
    except Exception as e:
        log(f"build_progress_report() failed, sending without it: {e}")
    try:
        r = subprocess.run(
            [PY, str(REPO / "scripts" / "notify.py"), subject],
            input=body, text=True, cwd=REPO, timeout=60, check=False,
            capture_output=True,
        )
        if r.returncode != 0:
            # notify.py ran but failed (bad SMTP creds, network, etc.) --
            # this used to be swallowed silently (check=False, result never
            # inspected), so a real send failure looked identical to a
            # successful send from this pipeline's point of view.
            log(f"notify() FAILED (exit {r.returncode}) for {subject!r}: {r.stderr.strip()}")
    except Exception as e:
        log(f"notify() itself failed: {e}")


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def load_queue() -> list[dict]:
    if QUEUE_PATH.exists():
        return json.loads(QUEUE_PATH.read_text())
    munis = json.loads(SOURCE_LIST.read_text())
    seen_slugs = set()
    queue = []
    for m in munis:
        slug = slugify(m["name"])
        base_slug = slug
        n = 2
        while slug in seen_slugs:
            slug = f"{base_slug}-{n}"
            n += 1
        seen_slugs.add(slug)
        queue.append({
            "slug": slug, "name": m["name"], "website": m["website"],
            "prov": m["prov"], "pop": m["pop"], "tier": m["tier"],
            "status": "pending", "error": None,
        })
    save_queue(queue)
    return queue


def atomic_write(path: Path, text: str) -> None:
    """Write via a temp file + rename.

    `write_text` truncates before writing, so a reader that opens the file in
    that window sees zero bytes. municipalities.json is read by every crawl.py /
    ingest.py / build_index.py subprocess and by muni.py, and with several
    finishes running concurrently that window is hit for real: Dordrecht failed
    on 2026-08-24 with "Expecting value: line 1 column 1" from ingest.py.
    A rename is atomic, so readers see either the old or the new file.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def save_queue(queue: list[dict]) -> None:
    with QUEUE_LOCK:
        atomic_write(QUEUE_PATH, json.dumps(queue, ensure_ascii=False, indent=1))


def registry_entries() -> list[dict]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(entries: list[dict]) -> None:
    atomic_write(REGISTRY_PATH, json.dumps(entries, ensure_ascii=False, indent=2) + "\n")


def index_doc_count(slug: str) -> int:
    """Documents in a municipality's built index; -1 if it is unreadable."""
    path = REPO / "data" / slug / "index.sqlite"
    if not path.exists():
        return -1
    try:
        con = sqlite3.connect(path)
        try:
            return con.execute("select count(*) from documents").fetchone()[0]
        finally:
            con.close()
    except Exception:
        return -1


def upsert_registry_entry(entry: dict) -> None:
    with REGISTRY_LOCK:
        entries = registry_entries()
        for i, e in enumerate(entries):
            if e["slug"] == entry["slug"]:
                entries[i] = entry
                save_registry(entries)
                return
        entries.append(entry)
        save_registry(entries)


def run_step(name: str, slug: str, *args: str) -> tuple[bool, str]:
    cmd = [PY, name, "--municipality", slug, *args]
    log(f"  -> {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=6 * 3600)
    except subprocess.TimeoutExpired:
        return False, f"{name} timed out after 6h"
    tail = "\n".join((r.stdout + r.stderr).splitlines()[-25:])
    if r.returncode != 0:
        return False, f"{name} exit {r.returncode}:\n{tail}"
    log(f"  ok: {tail.splitlines()[-1] if tail else ''}")
    return True, tail


def ensure_nas_symlinks(slug: str) -> None:
    data_dir = REPO / "data" / slug
    data_dir.mkdir(parents=True, exist_ok=True)
    nas_crawl = NAS_ROOT / slug / "crawl"
    nas_pdfs = NAS_ROOT / slug / "pdfs"
    nas_crawl.mkdir(parents=True, exist_ok=True)
    nas_pdfs.mkdir(parents=True, exist_ok=True)
    local_crawl = data_dir / "crawl"
    local_pdfs = data_dir / "pdfs"
    if not local_crawl.exists() and not local_crawl.is_symlink():
        local_crawl.symlink_to(nas_crawl)
    if not local_pdfs.exists() and not local_pdfs.is_symlink():
        local_pdfs.symlink_to(nas_pdfs)


def restart_service_and_verify(slug: str) -> tuple[bool, str]:
    """Restart gemeente-search.service and poll /api/municipalities until the
    new slug shows up, instead of a fixed sleep. The old fixed sleep(20) was
    a false-negative machine once the registry grew: on 2026-08-24 the
    service took 45s to reload ~226 municipalities into memory at startup
    (each with its own sqlite connection + embeddings.npy load), so a batch
    of ~42 municipalities that finished around then were wrongly marked
    'failed' even though their data was completely fine -- confirmed by
    re-checking /api/municipalities after the fact. Startup time only grows
    as more municipalities get enabled, so a fixed wait keeps getting worse;
    polling doesn't have that failure mode."""
    r = subprocess.run(["systemctl", "--user", "restart", "gemeente-search.service"], capture_output=True, text=True)
    if r.returncode != 0:
        return False, f"service restart failed: {r.stderr}"
    deadline = time.time() + 180
    last_detail = "no response yet"
    while time.time() < deadline:
        time.sleep(5)
        try:
            r2 = subprocess.run(
                ["curl", "-s", "-m", "10", "http://127.0.0.1:8905/api/municipalities"],
                capture_output=True, text=True,
            )
            if slug in r2.stdout:
                return True, "verified in /api/municipalities"
            last_detail = "responding but slug not yet present (still loading?)" if r2.stdout else "no response"
        except Exception as e:
            last_detail = f"verification request failed: {e}"
    return False, f"restarted but not found in /api/municipalities after 180s polling ({last_detail})"


def maybe_send_tally(total: int) -> None:
    with TALLY_LOCK:
        done = len([q for q in QUEUE if q["status"] == "done"])
        if done and done % 20 == 0 and done != maybe_send_tally.last_tally:
            maybe_send_tally.last_tally = done
            failed = len([q for q in QUEUE if q["status"] == "failed"])
            remaining = len([q for q in QUEUE if q["status"] in ("pending", "crawled")])
            notify(
                f"Tussenstand landelijke uitrol: {done}/{total}",
                f"{done} gemeentes live, {failed} mislukt (overgeslagen), {remaining} nog te gaan.",
            )


maybe_send_tally.last_tally = 0


def crawl_one(item: dict) -> bool:
    """Crawl step only. Returns True on success (item moves to 'crawled',
    picked up by finish_one next), False on failure (item marked 'failed',
    notified, pipeline moves on)."""
    slug, name = item["slug"], item["name"]
    start_ts = time.time()
    log(f"=== {name} ({slug}) CRAWL START ===")

    entry = {
        "slug": slug, "name": name, "enabled": False,
        "logo": None, "website": item["website"],
        "start_url": item["website"], "search_url": "", "cdn_prefix": "",
    }
    upsert_registry_entry(entry)
    ensure_nas_symlinks(slug)

    ok, detail = run_step("crawl.py", slug)
    if not ok:
        item["status"] = "failed"
        item["error"] = f"crawl: {detail}"
        item["duration_s"] = round(time.time() - start_ts)
        save_queue(QUEUE)
        notify(
            f"Gemeente-onboarding FOUT: {name}",
            f"{name} ({slug}) is mislukt bij stap 'crawl'.\n\n{detail}\n\n"
            f"Wordt overgeslagen, pipeline gaat door met de volgende gemeente. "
            f"Zie {LOG} op de Z8 voor het volledige log.",
        )
        log(f"=== {name} FAILED at crawl ===")
        return False

    item["status"] = "crawled"
    item["crawl_duration_s"] = round(time.time() - start_ts)
    save_queue(QUEUE)
    log(f"=== {name} CRAWL DONE, queued for finish ===")
    return True


def finish_one(item: dict, total: int) -> None:
    """ingest -> build_index -> enable -> restart/verify -> notify. Runs
    concurrently across municipalities (bounded by FINISH_CONCURRENCY) --
    except restart/verify, which is serialized (RESTART_LOCK) since every
    municipality shares the one gemeente-search.service."""
    slug, name = item["slug"], item["name"]
    start_ts = time.time()
    crawl_duration = item.get("crawl_duration_s", 0)

    for step_name, script in (("ingest", "ingest.py"), ("build_index", "build_index.py")):
        ok, detail = run_step(script, slug)
        if not ok:
            item["status"] = "failed"
            item["error"] = f"{step_name}: {detail}"
            item["duration_s"] = crawl_duration + round(time.time() - start_ts)
            save_queue(QUEUE)
            notify(
                f"Gemeente-onboarding FOUT: {name}",
                f"{name} ({slug}) is mislukt bij stap '{step_name}'.\n\n{detail}\n\n"
                f"Wordt overgeslagen, pipeline gaat door met de volgende gemeente. "
                f"Zie {LOG} op de Z8 voor het volledige log.",
            )
            log(f"=== {name} FAILED at {step_name} ===")
            return

    doc_count = index_doc_count(slug)
    if doc_count < MIN_DOCUMENTS:
        item["status"] = "failed"
        item["error"] = f"kwaliteitsgate: slechts {doc_count} documenten geïndexeerd"
        item["duration_s"] = crawl_duration + round(time.time() - start_ts)
        save_queue(QUEUE)
        notify(
            f"Gemeente-onboarding FOUT: {name}",
            f"{name} ({slug}) leverde maar {doc_count} documenten op "
            f"(drempel {MIN_DOCUMENTS}). De crawl heeft vrijwel niets gevonden, "
            f"dus de gemeente wordt NIET live gezet.\n\n"
            f"Meestal ligt het aan een ontbrekende/lege sitemap, een site die "
            f"ons blokkeert, of een JS-only site zonder volgbare links. "
            f"Staat als 'failed' in de queue voor een gerichte retry.",
        )
        log(f"=== {name} FAILED quality gate ({doc_count} docs) ===")
        return

    entry = {
        "slug": slug, "name": name, "enabled": True,
        "logo": None, "website": item["website"],
        "start_url": item["website"], "search_url": "", "cdn_prefix": "",
    }
    upsert_registry_entry(entry)

    with RESTART_LOCK:
        ok, detail = restart_service_and_verify(slug)
    if not ok:
        item["status"] = "failed"
        item["error"] = f"restart/verify: {detail}"
        item["duration_s"] = crawl_duration + round(time.time() - start_ts)
        save_queue(QUEUE)
        notify(
            f"Gemeente-onboarding FOUT: {name}",
            f"{name} ({slug}): index is gebouwd maar {detail}. "
            f"Wordt overgeslagen, pipeline gaat door.",
        )
        log(f"=== {name} FAILED at restart/verify ===")
        return

    item["status"] = "done"
    item["error"] = None
    item["duration_s"] = crawl_duration + round(time.time() - start_ts)
    save_queue(QUEUE)
    done = len([q for q in QUEUE if q["status"] == "done"])
    failed = len([q for q in QUEUE if q["status"] == "failed"])
    remaining = len([q for q in QUEUE if q["status"] in ("pending", "crawled")])
    notify(
        f"Gemeente live: {name}",
        f"{name} is live op https://gemeente.multicode.nl (kies '{name}' in de dropdown).\n\n"
        f"Voortgang landelijke uitrol: {done} live, {failed} mislukt, {remaining} nog te gaan.",
    )
    log(f"=== {name} DONE ({done} total done, {remaining} remaining) ===")
    maybe_send_tally(total)


def main() -> None:
    global QUEUE
    QUEUE = load_queue()
    total = len(QUEUE)
    already_done = len([q for q in QUEUE if q["status"] == "done"])
    log(
        f"onboarding queue loaded: {total} municipalities, {already_done} already done "
        f"(crawl concurrency={CRAWL_CONCURRENCY_MUNI}, finish concurrency={FINISH_CONCURRENCY})"
    )

    if already_done == 0:
        notify(
            "Gemeente-onboarding gestart",
            f"Autonome landelijke onboarding is gestart op de Z8: {total} gemeentes in de wachtrij, "
            f"{CRAWL_CONCURRENCY_MUNI}x gelijktijdig crawlen, {FINISH_CONCURRENCY}x gelijktijdig verwerken "
            f"(ingest/index/live-zetten). Je krijgt een mail per gemeente (klaar of mislukt), plus een "
            f"tussenstand elke 20 gemeentes.",
        )

    to_crawl = [q for q in QUEUE if q["status"] == "pending"]
    # Resuming after an interrupted run: pick up anything that finished
    # crawling last time but never got to ingest/index/restart.
    to_finish_immediately = [q for q in QUEUE if q["status"] == "crawled"]

    with ThreadPoolExecutor(max_workers=FINISH_CONCURRENCY, thread_name_prefix="finish") as finish_pool:
        for item in to_finish_immediately:
            finish_pool.submit(finish_one, item, total)

        with ThreadPoolExecutor(max_workers=CRAWL_CONCURRENCY_MUNI, thread_name_prefix="crawl") as crawl_pool:
            crawl_futures = {crawl_pool.submit(crawl_one, item): item for item in to_crawl}
            for fut in as_completed(crawl_futures):
                item = crawl_futures[fut]
                try:
                    crawled_ok = fut.result()
                except Exception as e:
                    log(f"crawl_one crashed for {item['slug']}: {e}")
                    crawled_ok = False
                if crawled_ok:
                    finish_pool.submit(finish_one, item, total)
        # crawl_pool drained (context exit waits for it); finish_pool keeps
        # running whatever's still queued/in-flight until this outer `with`
        # exits below, which is exactly "next crawl batch runs while the
        # previous batch's onboarding finishes" -- continuously, not in
        # lockstep batches of exactly N.

    done = len([q for q in QUEUE if q["status"] == "done"])
    failed = [q for q in QUEUE if q["status"] == "failed"]
    log(f"=== QUEUE COMPLETE: {done} done, {len(failed)} failed ===")
    failed_lines = "\n".join(f"- {q['name']}: {q['error']}" for q in failed) or "(geen)"
    notify(
        "Landelijke gemeente-onboarding VOLTOOID",
        f"Alle {total} gemeentes zijn verwerkt.\n\n{done} live op gemeente.multicode.nl.\n"
        f"{len(failed)} mislukt (overgeslagen, main-site crawl only -- geen raadsarchief):\n{failed_lines}",
    )


if __name__ == "__main__":
    QUEUE: list[dict] = []
    try:
        main()
    except Exception as e:
        log(f"FATAL orchestrator error: {e}")
        notify("Gemeente-onboarding: orchestrator crashte", f"De onboarding-pipeline zelf is gecrasht: {e}\n\nZie {LOG} op de Z8.")
        sys.exit(1)
