#!/usr/bin/env python3
"""Re-ingest + rebuild the done+enabled slugs whose docs.jsonl was stripped of
crawl-trap lines (see strip_traps.py).  Mirrors onboard_all.finish_one's
ingest -> build_index steps (same PY, same args), but without per-slug app
restarts or emails -- the app is restarted ONCE after the whole batch.

Usage:
    scripts/reingest_stripped.py --slugs-file /tmp/reingest_done_slugs.txt
    scripts/reingest_stripped.py --slug aa-en-hunze --slug voorst
"""
import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = str(REPO / ".venv" / "bin" / "python3")


def run_step(script: str, slug: str) -> tuple[bool, str]:
    cmd = [PY, script, "--municipality", slug]
    try:
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=6 * 3600)
    except subprocess.TimeoutExpired:
        return False, f"{script} timed out after 6h"
    tail = "\n".join((r.stdout + r.stderr).splitlines()[-8:])
    if r.returncode != 0:
        return False, f"{script} exit {r.returncode}: {tail}"
    return True, tail.splitlines()[-1] if tail else ""


def reingest_one(slug: str) -> tuple[str, bool, str]:
    ok, detail = run_step("ingest.py", slug)
    if not ok:
        return slug, False, f"ingest: {detail}"
    ok, detail = run_step("build_index.py", slug)
    if not ok:
        return slug, False, f"build_index: {detail}"
    return slug, True, detail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slugs-file", default="/tmp/reingest_done_slugs.txt")
    ap.add_argument("--slug", action="append", default=[])
    ap.add_argument("--concurrency", type=int, default=3)
    args = ap.parse_args()

    slugs = args.slug
    if not slugs and Path(args.slugs_file).exists():
        slugs = [ln.strip() for ln in Path(args.slugs_file).read_text().splitlines() if ln.strip()]
    if not slugs:
        print("no slugs given (--slug or --slugs-file)", file=sys.stderr)
        sys.exit(1)

    print(f"re-ingesting {len(slugs)} slugs (concurrency {args.concurrency})", flush=True)
    t0 = time.time()
    ok_list, fail_list = [], []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(reingest_one, s): s for s in slugs}
        for i, fut in enumerate(as_completed(futs), 1):
            slug, ok, detail = fut.result()
            (ok_list if ok else fail_list).append(slug)
            mark = "OK " if ok else "FAIL"
            print(f"[{i}/{len(slugs)}] {mark} {slug}  {detail[:120]}", flush=True)

    print(f"\n=== re-ingest done in {time.time()-t0:.0f}s: {len(ok_list)} ok, {len(fail_list)} failed ===")
    if fail_list:
        print("FAILED:\n  " + "\n  ".join(fail_list))
        Path("/tmp/reingest_failed_slugs.txt").write_text("\n".join(fail_list))


if __name__ == "__main__":
    main()
