#!/usr/bin/env python3
"""Detached finish runner: ingest -> build_index for one municipality.

Usage: _finish.py <slug> <logfile> [skip_ingest]

Run via a launcher that Popen's this with start_new_session=True so it survives
the gateway. Logs everything to <logfile> and exits non-zero on failure.
"""
import subprocess, sys, time
from pathlib import Path

slug = sys.argv[1]
logfile = sys.argv[2]
skip_ingest = len(sys.argv) > 3 and sys.argv[3] == "skip_ingest"

CWD = str(Path(__file__).resolve().parent.parent)
VENV = str(Path(CWD) / ".venv" / "bin" / "python3")

steps = [] if skip_ingest else ["ingest.py"]
steps += ["build_index.py"]

with open(logfile, "w") as f:
    f.write(f"# finish {slug} started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.flush()
    for step in steps:
        f.write(f"\n=== {step} {slug} ===\n")
        f.flush()
        t0 = time.time()
        r = subprocess.run(
            [VENV, step, "--municipality", slug],
            cwd=CWD, stdout=f, stderr=subprocess.STDOUT, text=True,
        )
        f.write(f"\n=== {step} exit {r.returncode} in {time.time()-t0:.0f}s ===\n")
        f.flush()
        if r.returncode != 0:
            f.write(f"FINISH FAILED at {step}\n")
            f.flush()
            sys.exit(r.returncode)
    f.write(f"\nFINISH OK {slug}\n")
    f.flush()

print(f"OK {slug}")
