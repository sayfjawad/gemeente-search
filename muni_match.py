"""Detect which municipality a free-text question is about.

Used to route a cross-municipality query ("wat zijn de regels in de gemeente
Utrecht?") to the right index without the user picking it from the dropdown.
Deterministic — no LLM round-trip, so it's instant and free.  Accent-folds both
sides, matches every enabled municipality's name + aliases with word boundaries,
longest-name-first, and guards the handful of Dutch municipality names that
collide with ordinary words (Houten=wooden, Buren=neighbours, …).

Returns a slug, or None when nothing matches or the match is ambiguous.
"""
import re
import unicodedata
from typing import Optional

import muni

# Municipality names that are also ordinary Dutch/English words.  For these we
# only accept a bare match when a locative signal word sits right before/after
# ("in Houten", "uit Best") — otherwise "een houten schutting" would route to
# Houten.  An explicit "gemeente X" / "stad X" always wins regardless.
COMMON_WORD = {
    "assen", "beek", "bergen", "best", "buren", "duiven", "hoorn", "houten",
    "huizen", "kampen", "losser", "putten", "sluis", "steenbergen", "stein",
    "waterland",
}

# Locative signals that make a bare common-word match plausible.
SIGNAL = {
    "in", "van", "uit", "naar", "bij", "voor", "te", "binnen", "buiten",
    "woon", "wonen", "woonachtig", "gemeente", "gemeenten", "stad", "regio",
    "provincie",
}

# Common shorthands the registry itself doesn't carry as aliases.  Keys are
# accent-folded; values are accent-folded registry NAMES (resolved to a slug
# via the registry so we never hardcode a slug).
EXTRA_ALIAS = {
    "den bosch": "s-hertogenbosch",
    "s-hertogenbosch": "s-hertogenbosch",
    "s hertogenbosch": "s-hertogenbosch",
    "s-gravenhage": "den-haag",
    "the hague": "den-haag",
    "den haag": "den-haag",
}


def _fold(s: str) -> str:
    """Lowercase + accent-fold (NFKD) + drop leading apostrophes, so
    "'s-Hertogenbosch" == "s-hertogenbosch" and "Súdwest-Fryslân" == "sudwest-fryslan"."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip().lstrip("'’")


def _clean_name(name: str) -> str:
    """Drop display disambiguation like 'Bergen (L)' -> 'Bergen'."""
    return re.sub(r"\s*\(.*?\)\s*", " ", name).strip()


def _candidates() -> list[dict]:
    """All matchable (folded_string, slug) pairs, longest-name-first."""
    out, seen = [], set()
    for m in muni.enabled():
        slug = m["slug"]
        for nm in [m["name"]] + (m.get("aliases") or []):
            key = _fold(_clean_name(nm))
            if not key or (key, slug) in seen:
                continue
            seen.add((key, slug))
            out.append(_cand(key, slug))
    # shorthands -> registry name -> slug(s)
    name2slugs: dict[str, set[str]] = {}
    for m in muni.enabled():
        name2slugs.setdefault(_fold(_clean_name(m["name"])), set()).add(m["slug"])
    for alias, target in EXTRA_ALIAS.items():
        key = _fold(alias)
        if any(c["match"] == key for c in out):
            continue
        for slug in name2slugs.get(target, ()):
            out.append(_cand(key, slug))
    out.sort(key=lambda c: (-c["nwords"], c["common"], len(c["match"])))
    return out


def _cand(key: str, slug: str) -> dict:
    return {
        "match": key,
        "slug": slug,
        "common": key in COMMON_WORD,
        "nwords": len(key.split()),
        "re": re.compile(r"(?<![a-z0-9])" + re.escape(key) + r"(?![a-z0-9])"),
    }


_CACHE: Optional[list[dict]] = None


def candidates() -> list[dict]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _candidates()
    return _CACHE


def _context_tokens(span: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9']+", span) if t]

def _hits(question: str, extra_signals: frozenset[str] = frozenset()) -> list[tuple[dict, int, int, bool, bool]]:
    """Collect non-overlapping municipality matches, longest-first at each
    position.  Bare common-word matches are rejected unless a signal word
    (SIGNAL + extra_signals) sits right before/after the name."""
    q = _fold(question)
    if not q:
        return []
    sig = SIGNAL | extra_signals

    # (candidate, start, end, explicit, signaled)
    hits: list[tuple[dict, int, int, bool, bool]] = []
    for c in candidates():
        for m in c["re"].finditer(q):
            s, e = m.span()
            before = _context_tokens(q[max(0, s - 24):s])
            after = _context_tokens(q[e:e + 24])
            prev_tok = before[-1] if before else ""
            next_tok = after[0] if after else ""
            explicit = prev_tok in ("gemeente", "gemeenten", "stad") or \
                any(t in ("gemeente", "gemeenten", "stad") for t in before[-3:])
            signaled = prev_tok in sig or next_tok in sig
            hits.append((c, s, e, explicit, signaled))
            break  # first occurrence per candidate is enough

    # Suppress a hit only when a strictly-longer kept match fully contains it
    # ("Bergen op Zoom" swallows "Bergen").  Equal-length hits are NOT
    # suppressed — two slugs can share one match string ("Bergen" -> bergen-l
    # and bergen-nh), and dropping one would silently pick an arbitrary side.
    hits.sort(key=lambda h: (h[1], -(h[2] - h[1])))
    kept: list[tuple[dict, int, int, bool, bool]] = []
    for h in hits:
        if any(k[1] <= h[1] and h[2] <= k[2] and (k[2] - k[1]) > (h[2] - h[1])
               for k in kept):
            continue
        kept.append(h)

    # Reject bare matches of common words ("houten schutting").
    return [h for h in kept if not h[0]["common"] or h[3] or h[4]]


def detect_all(question: str) -> list[str]:
    """Return the distinct municipality slugs named in the question, in the
    order they appear.  Used by the cross-municipality comparison endpoint.

    Compared with detect() it also treats list separators ("en"/"of"/"versus")
    as signals, so a bare common-word name in a list — "vergelijks paspoort-
    kosten in Best en Utrecht" — is read as a municipality, not the adjective."""
    seen: set[str] = set()
    out: list[str] = []
    for c, _s, _e, _explicit, _signaled in _hits(question, extra_signals=frozenset({"en", "of", "versus", "vs"})):
        if c["slug"] not in seen:
            seen.add(c["slug"])
            out.append(c["slug"])
    return out


def detect(question: str) -> Optional[str]:
    """Return the municipality slug the question is about, or None."""
    kept = _hits(question)
    if not kept:
        return None

    # Rank: explicit > signaled > bare; then longest name.  Ambiguous tie -> None.
    rank = lambda h: (2 if h[3] else 1 if h[4] else 0, h[0]["nwords"])
    kept.sort(key=rank, reverse=True)
    best = kept[0]
    top = rank(best)
    if sum(1 for h in kept if h[0]["slug"] != best[0]["slug"] and rank(h) == top):
        return None
    return best[0]["slug"]
