#!/usr/bin/env python3
"""Strip crawl-trap lines from data/<slug>/crawl/docs.jsonl.

Removes exactly the junk the fixed crawl.py would no longer follow:
file-transfer portals (cryptshare/crypt/bestand/filetransfer/...), session-token
path params (;jsessionid=/;phpsessid=), and faceted-search/pagination query
params (tx_solr/languageswitch/nav_id/chash/searchtype, and the TRAP_PARAMS
blocklist).  The original is renamed to docs.jsonl.bak-traps-<ts> before the
cleaned file replaces it, so a mistake is recoverable.  Idempotent: re-running
drops nothing extra.

Usage:
    scripts/strip_traps.py --dry-run [--min-trap 20]
    scripts/strip_traps.py [--min-trap 20] [--slug a --slug b]
"""
import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

# Mirrors crawl.py fits_scope() / TRAP_* exactly.  Keep in sync.
TRAP_PARAMS = {
    "searchbase", "sp", "f", "freetext", "datefrom", "dateto", "datetill",
    "offset", "page", "start", "sort", "filter", "facet",
}
TRAP_PARAM_SUBSTR = ("tx_solr", "languageswitch", "nav_id", "chash", "searchtype")
PORTAL = re.compile(
    r"^(crypt|cryptshare|bestand|bestandverzenden|filetransfer|fileshare|almereconnect)\d*\.",
    re.I,
)
SESSION = re.compile(r";(jsessionid|phpsessid)=[^/?#]+", re.I)


def is_trap(url: str) -> bool:
    p = urlparse(url)
    if PORTAL.match(p.netloc.split(":")[0].lower()):
        return True
    if SESSION.search(p.path.lower()):
        return True
    for key in parse_qs(p.query):
        k = key.lower()
        if k in TRAP_PARAMS:
            return True
        kd = unquote(key).lower()
        if kd in TRAP_PARAMS:
            return True
        if any(sub in kd for sub in TRAP_PARAM_SUBSTR):
            return True
    return False


def count_slug(docs: Path) -> tuple[int, int]:
    kept = drop = 0
    with open(docs, encoding="utf-8") as f:
        for ln in f:
            if not ln.strip():
                continue
            try:
                url = json.loads(ln)["url"]
            except Exception:
                kept += 1
                continue
            if is_trap(url):
                drop += 1
            else:
                kept += 1
    return kept, drop


def strip_slug(docs: Path) -> tuple[int, int]:
    tmp = docs.with_name("docs.jsonl.clean.tmp")
    kept = drop = 0
    with open(docs, encoding="utf-8") as fi, open(tmp, "w", encoding="utf-8") as fo:
        for ln in fi:
            if not ln.strip():
                continue
            try:
                url = json.loads(ln)["url"]
            except Exception:
                fo.write(ln)
                kept += 1
                continue
            if is_trap(url):
                drop += 1
            else:
                fo.write(ln)
                kept += 1
    if drop == 0:
        tmp.unlink()
        return kept, 0
    ts = time.strftime("%Y%m%d-%H%M%S")
    bak = docs.with_name(f"docs.jsonl.bak-traps-{ts}")
    docs.replace(bak)   # original (with junk) -> backup
    tmp.replace(docs)   # cleaned -> docs.jsonl
    return kept, drop


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-trap", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--slug", action="append", default=[])
    args = ap.parse_args()

    repo = Path(__file__).resolve().parent.parent
    slugs = args.slug
    if not slugs:
        for d in sorted((repo / "data").iterdir()):
            docs = d / "crawl" / "docs.jsonl"
            if not docs.exists():
                continue
            _, drop = count_slug(docs)
            if drop >= args.min_trap:
                slugs.append(d.name)

    tot_kept = tot_drop = 0
    for s in sorted(slugs):
        docs = repo / "data" / s / "crawl" / "docs.jsonl"
        if not docs.exists():
            print(f"{s:26s} NO docs.jsonl")
            continue
        kept, drop = strip_slug(docs)
        print(f"{s:26s} kept={kept:7d}  dropped={drop:7d}")
        tot_kept += kept
        tot_drop += drop
    print(f"\nTOTAL over {len(slugs)} slugs: dropped {tot_drop}, kept {tot_kept}")


if __name__ == "__main__":
    main()
