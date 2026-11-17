#!/usr/bin/env python3
"""Prune junk from a municipality's docs.jsonl using the CURRENT crawl.py
guards (fits_scope), then recompute state.json so a re-crawl resumes cleanly.

Usage: prune_junk.py <slug>

Keeps only docs whose URL still passes fits_scope() (i.e. the new SKIP_HOST /
SKIP_PATH / BEKENDMAKINGEN_TRAP etc. guards reject the junk). Recomputes
state.json with seen=<kept urls>, pending=[].
"""
import json, sys
from pathlib import Path

# crawl.py lives in the repo root (one level up from scripts/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

slug = sys.argv[1]
BASE = Path("/mnt/gemeente-live") / slug / "crawl"
DOCS = BASE / "docs.jsonl"
STATE = BASE / "state.json"

import crawl
crawl.configure(slug)

kept = removed = 0
seen = []
pdfs = 0
out_lines = []
with DOCS.open(encoding="utf-8", errors="replace") as fin:
    for line in fin:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        u = d.get("url", "")
        if not crawl.fits_scope(u):
            removed += 1
            continue
        out_lines.append(line)
        seen.append(u)
        kept += 1
        if d.get("doc_type") == "pdf":
            pdfs += 1

# atomic replace
tmp = DOCS.with_suffix(".pruned.tmp")
tmp.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
tmp.replace(DOCS)

STATE.write_text(
    json.dumps({"seen": sorted(set(seen)), "pending": [], "docs": kept, "pdfs": pdfs},
               ensure_ascii=False),
    encoding="utf-8",
)
print(f"{slug}: kept={kept} removed={removed} pdfs={pdfs}")
