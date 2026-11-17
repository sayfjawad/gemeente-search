#!/usr/bin/env python3
"""Enable finished municipalities: set enabled=True in municipalities.json and
mark onboarding_queue.json entries 'done'. Usage: _enable.py <slug> [slug...]"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MUNI = ROOT / "municipalities.json"
QUEUE = ROOT / "scripts" / "onboarding_queue.json"

slugs = sys.argv[1:]

muni = json.loads(MUNI.read_text(encoding="utf-8"))
queue = json.loads(QUEUE.read_text(encoding="utf-8"))

qmap = {q["slug"]: q for q in queue}

for slug in slugs:
    # municipalities.json
    entry = next((m for m in muni if m.get("slug") == slug), None)
    if entry is None:
        q = qmap.get(slug, {})
        entry = {
            "slug": slug, "name": q.get("name", slug), "enabled": True,
            "logo": None, "website": q.get("website", ""),
            "start_url": q.get("website", ""), "search_url": "",
            "cdn_prefix": "",
        }
        muni.append(entry)
    else:
        entry["enabled"] = True
        if not entry.get("website"):
            entry["website"] = qmap.get(slug, {}).get("website", "")
        if not entry.get("start_url"):
            entry["start_url"] = entry.get("website", "")
    # queue
    if slug in qmap:
        qmap[slug]["status"] = "done"
        qmap[slug]["error"] = None
    print(f"enabled {slug}")

MUNI.write_text(json.dumps(muni, indent=1, ensure_ascii=False), encoding="utf-8")
QUEUE.write_text(json.dumps(queue, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote municipalities.json + onboarding_queue.json")
