"""Fetch official municipality coat-of-arms ("wapen") images from Wikidata/
Wikimedia Commons for every municipality in municipalities.json that has no
logo yet, and write them into static/logos/.

Why Wikidata instead of guessing Commons filenames: property P94 ("coat of
arms image") on each Dutch-municipality item (instance of Q2039348) links
straight to the exact current file, avoiding the mess of Commons full-text
search (which surfaces historic wapens, photos of building facades with a
wapen carved into them, etc. -- verified this empirically: searching for
"Wapen van Tilburg" on Commons ranks four unrelated 2022 photographs above
the actual current SVG).

One exact-name lookup covers 331/336 of the municipalities missing a logo
(cross-checked against municipalities.json before writing this). The
remaining 5 are Frisian-official-name / disambiguated-name mismatches
between Wikidata's Dutch label and our registry's `name` field -- resolved
by hand below via their Wikidata QIDs (found via wbsearchentities), not
guessed.

Idempotent + resumable: skips any municipality that already has `logo` set,
and does one atomic (tmp+rename) write of municipalities.json after every
successful download -- safe to Ctrl-C or kill at any point, safe to re-run.
No service restart needed: app.py's muni.load_registry() re-reads
municipalities.json on every request, and StaticFiles serves static/logos/
straight from disk.
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO / "municipalities.json"
LOGOS_DIR = REPO / "static" / "logos"
LOG_PATH = REPO / "scripts" / "fetch_logos.log"

UA = "gemeente-search-logo-fetch/1.0 (https://gemeente.multicode.nl; stichtingduurzaamai.nl)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
SPARQL_QUERY = """
SELECT ?gemeenteLabel ?wapen WHERE {
  ?gemeente wdt:P31 wd:Q2039348.
  OPTIONAL { ?gemeente wdt:P94 ?wapen. }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "nl". }
}
"""

# Manual QID-resolved overrides for the 5 name mismatches between Wikidata's
# nl label and our registry (found via https://www.wikidata.org/w/api.php
# action=wbsearchentities, then reading each QID's P94 claim directly --
# not guessed). Keyed by our own slug.
OVERRIDES = {
    "bergen-l": "Bergen wapen 2016.svg",  # Q9804, Bergen (Limburg)
    "bergen-nh": "Coat of arms of Bergen (North Holland).svg",  # Q9901
    "dantumadiel": "Coat of arms of Dantumadeel.svg",  # old-spelling Wikidata label
    "de-fryske-marren": "De Fryske Marren wapen.svg",  # Q2114866
    "tytsjerksteradiel": "Coat of arms of Tietjerksteradeel.svg",  # Q840636, old-spelling label
}


def log(msg: str) -> None:
    line = f"[{__import__('datetime').datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


def fetch_wapen_lookup() -> dict[str, str]:
    """name (nl label) -> Commons filename (without 'File:' prefix)."""
    url = f"{SPARQL_ENDPOINT}?{urllib.parse.urlencode({'query': SPARQL_QUERY, 'format': 'json'})}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    lookup: dict[str, str] = {}
    for row in data["results"]["bindings"]:
        name = row["gemeenteLabel"]["value"]
        wapen_url = row.get("wapen", {}).get("value")
        if not wapen_url or name in lookup:
            continue
        # url is .../Special:FilePath/<urlencoded filename>
        filename = urllib.parse.unquote(wapen_url.rsplit("/", 1)[-1])
        lookup[name] = filename
    return lookup


def download_wapen(filename: str, dest_no_ext: Path) -> Path | None:
    """Download a Commons file via Special:FilePath (redirects to the real
    upload.wikimedia.org URL) and save it as dest_no_ext.<ext>. Returns the
    written path, or None if the download didn't look like a real image."""
    ext = Path(filename).suffix.lower() or ".svg"
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(filename)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    # Wikimedia rate-limited us at ~0.4s/request sustained over hundreds of
    # requests (HTTP 429, "Your bot is making too many requests"). Back off
    # and retry a few times with growing delays rather than just failing --
    # the request itself is fine, it's purely a pacing problem.
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                wait = 10 * (attempt + 1)
                log(f"    429 rate-limited, waiting {wait}s (attempt {attempt + 1}/5)")
                time.sleep(wait)
                continue
            raise

    if len(data) < 200:
        return None
    if ext == ".svg":
        head = data[:200].lstrip()
        if not (head.startswith(b"<?xml") or head.startswith(b"<svg")):
            return None
    elif ext == ".png":
        if not data.startswith(b"\x89PNG"):
            return None

    dest = dest_no_ext.with_suffix(ext)
    dest.write_bytes(data)
    return dest


def save_registry(entries: list[dict]) -> None:
    tmp = REGISTRY_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


def main() -> None:
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    log("fetching municipality wapen lookup from Wikidata...")
    lookup = fetch_wapen_lookup()
    log(f"  {len(lookup)} municipalities with a coat-of-arms image on Wikidata")

    entries = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    todo = [m for m in entries if not m.get("logo")]
    log(f"registry: {len(entries)} total, {len(todo)} missing a logo")

    done = failed = no_match = skipped_bad_image = 0
    for m in todo:
        slug, name = m["slug"], m["name"]
        filename = OVERRIDES.get(slug) or lookup.get(name)
        if not filename:
            log(f"  NO MATCH: {slug} ({name!r}) -- not found on Wikidata, needs manual lookup")
            no_match += 1
            continue
        try:
            dest = download_wapen(filename, LOGOS_DIR / slug)
        except Exception as e:
            log(f"  FAILED: {slug} <- {filename}: {e}")
            failed += 1
            time.sleep(0.5)
            continue
        if dest is None:
            log(f"  BAD IMAGE: {slug} <- {filename} (didn't look like a real svg/png, skipped)")
            skipped_bad_image += 1
            time.sleep(0.5)
            continue

        m["logo"] = dest.relative_to(REPO / "static").as_posix()
        save_registry(entries)
        done += 1
        log(f"  ok: {slug} <- {filename} -> {m['logo']}")
        time.sleep(1.2)  # polite pacing against Wikimedia -- 0.4s got us rate-limited (429) after ~265 requests

    log(
        f"=== DONE: {done} fetched, {no_match} no match on Wikidata, "
        f"{failed} download errors, {skipped_bad_image} bad-image, "
        f"{len(todo) - done} still missing ==="
    )

    try:
        import subprocess
        subprocess.run(
            [sys.executable, str(REPO / "scripts" / "notify.py"), "Gemeente-logo's opgehaald"],
            input=(
                f"Logo-fetch klaar: {done} van {len(todo)} ontbrekende logo's opgehaald van Wikidata.\n\n"
                f"Geen match op Wikidata: {no_match}\n"
                f"Downloadfouten: {failed}\n"
                f"Afgekeurd (geen geldige svg/png): {skipped_bad_image}\n\n"
                f"Zie {LOG_PATH} op de Z8 voor het volledige log."
            ),
            text=True, cwd=REPO, timeout=60, check=False,
        )
    except Exception as e:
        log(f"notify() failed: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e}")
        raise
