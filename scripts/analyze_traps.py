#!/usr/bin/env python3
"""Read-only trap analysis for problem municipalities."""
import json, re, sys
from collections import Counter
from pathlib import Path

SLUGS = ["breda","coevorden","deventer","dordrecht","gorinchem","maashorst",
         "molenlanden","ridderkerk","zoetermeer","venlo","olst-wijhe","land-van-cuijk"]

BASE = Path("/mnt/gemeente-live")

for slug in SLUGS:
    docs = BASE / slug / "crawl" / "docs.jsonl"
    if not docs.exists():
        print(f"\n### {slug}: no docs.jsonl")
        continue
    host_c = Counter()
    path_c = Counter()
    total = 0
    pdfs = 0
    for line in docs.open(encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        total += 1
        u = d.get("url", "")
        if d.get("doc_type") == "pdf":
            pdfs += 1
        m = re.match(r"https?://([^/]+)(/.*)?$", u)
        if not m:
            continue
        host = m.group(1)
        path = m.group(2) or "/"
        host_c[host] += 1
        segs = path.split("/")
        first2 = "/".join(segs[:2]) if len(segs) > 2 else path
        path_c[first2] += 1
    print(f"\n### {slug}: docs={total} pdfs={pdfs}")
    print("  HOSTS:")
    for h, n in host_c.most_common(6):
        print(f"    {n:>8}  {h}")
    print("  PATH (first 2 segs):")
    for p, n in path_c.most_common(8):
        print(f"    {n:>8}  {p}")
