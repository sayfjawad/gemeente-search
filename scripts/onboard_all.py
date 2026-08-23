"""Fully autonomous onboarding of all remaining Dutch municipalities.

Runs the same crawl -> ingest -> build_index -> enable -> restart pipeline as
onboard_barendrecht.sh, but looped over the ~336 municipalities in
gemeenten_336.json, one at a time. Bulk/blind mode: no per-site CMS
inspection, no council-archive (Notubiz/iBabs) crawl, no reference curation
-- just the main-site crawler with whatever defaults muni.py/crawl.py already
fall back to safely. New municipalities' crawl/ and pdfs/ are created as
symlinks into the NAS (/mnt/nas-gemeente) from the start, matching the
convention used for the 6 already-onboarded municipalities -- never touches
local disk on the Z8.

Resumable: progress is persisted in onboarding_queue.json after every
municipality, so a restart (crash, reboot, systemd Restart=on-failure) picks
up where it left off rather than re-doing finished work.

One email per municipality outcome (not per pipeline step -- 336 of those
would flood the inbox), plus a batch-summary email every 20 completions and a
final summary when the whole queue is done.
"""
import json
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_LIST = REPO / "scripts" / "gemeenten_336.json"
QUEUE_PATH = REPO / "scripts" / "onboarding_queue.json"
REGISTRY_PATH = REPO / "municipalities.json"
LOG = REPO / "scripts" / "onboard_all.log"
NAS_ROOT = Path("/mnt/nas-gemeente")
PY = str(REPO / ".venv" / "bin" / "python3")


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
    pending = [q for q in QUEUE if q["status"] == "pending"]

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


def save_queue(queue: list[dict]) -> None:
    QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False, indent=1))


def registry_entries() -> list[dict]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(entries: list[dict]) -> None:
    REGISTRY_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_registry_entry(entry: dict) -> None:
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
    r = subprocess.run(["systemctl", "--user", "restart", "gemeente-search.service"], capture_output=True, text=True)
    if r.returncode != 0:
        return False, f"service restart failed: {r.stderr}"
    import time
    time.sleep(20)
    try:
        r2 = subprocess.run(
            ["curl", "-s", "-m", "10", "http://127.0.0.1:8905/api/municipalities"],
            capture_output=True, text=True,
        )
        if slug in r2.stdout:
            return True, "verified in /api/municipalities"
        return False, "restarted but not found in /api/municipalities"
    except Exception as e:
        return False, f"verification request failed: {e}"


def onboard_one(item: dict) -> None:
    slug, name = item["slug"], item["name"]
    start_ts = time.time()
    log(f"=== {name} ({slug}) START ===")

    entry = {
        "slug": slug, "name": name, "enabled": False,
        "logo": None, "website": item["website"],
        "start_url": item["website"], "search_url": "", "cdn_prefix": "",
    }
    upsert_registry_entry(entry)
    ensure_nas_symlinks(slug)

    for step_name, script in (("crawl", "crawl.py"), ("ingest", "ingest.py"), ("build_index", "build_index.py")):
        ok, detail = run_step(script, slug)
        if not ok:
            item["status"] = "failed"
            item["error"] = f"{step_name}: {detail}"
            item["duration_s"] = round(time.time() - start_ts)
            save_queue(QUEUE)
            notify(
                f"Gemeente-onboarding FOUT: {name}",
                f"{name} ({slug}) is mislukt bij stap '{step_name}'.\n\n{detail}\n\n"
                f"Wordt overgeslagen, pipeline gaat door met de volgende gemeente. "
                f"Zie {LOG} op de Z8 voor het volledige log.",
            )
            log(f"=== {name} FAILED at {step_name} ===")
            return

    entry["enabled"] = True
    upsert_registry_entry(entry)
    ok, detail = restart_service_and_verify(slug)
    if not ok:
        item["status"] = "failed"
        item["error"] = f"restart/verify: {detail}"
        item["duration_s"] = round(time.time() - start_ts)
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
    item["duration_s"] = round(time.time() - start_ts)
    save_queue(QUEUE)
    done = len([q for q in QUEUE if q["status"] == "done"])
    failed = len([q for q in QUEUE if q["status"] == "failed"])
    remaining = len([q for q in QUEUE if q["status"] == "pending"])
    notify(
        f"Gemeente live: {name}",
        f"{name} is live op https://gemeente.multicode.nl (kies '{name}' in de dropdown).\n\n"
        f"Voortgang landelijke uitrol: {done} live, {failed} mislukt, {remaining} nog te gaan.",
    )
    log(f"=== {name} DONE ({done} total done, {remaining} remaining) ===")


def main() -> None:
    global QUEUE
    QUEUE = load_queue()
    total = len(QUEUE)
    already_done = len([q for q in QUEUE if q["status"] == "done"])
    log(f"onboarding queue loaded: {total} municipalities, {already_done} already done")

    if already_done == 0:
        notify(
            "Gemeente-onboarding gestart",
            f"Autonome landelijke onboarding is gestart op de Z8: {total} gemeentes in de wachtrij. "
            f"Je krijgt een mail per gemeente (klaar of mislukt), plus een tussenstand elke 20 gemeentes.",
        )

    processed_this_run = 0
    for item in QUEUE:
        if item["status"] == "done":
            continue
        onboard_one(item)
        processed_this_run += 1
        done = len([q for q in QUEUE if q["status"] == "done"])
        failed = len([q for q in QUEUE if q["status"] == "failed"])
        if done and done % 20 == 0 and processed_this_run:
            remaining = len([q for q in QUEUE if q["status"] == "pending"])
            notify(
                f"Tussenstand landelijke uitrol: {done}/{total}",
                f"{done} gemeentes live, {failed} mislukt (overgeslagen), {remaining} nog te gaan.",
            )

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
