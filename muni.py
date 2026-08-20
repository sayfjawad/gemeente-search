"""Municipality registry loader — single source of truth for which
municipalities are searchable and their crawl/agentic/council-archive config.

municipalities.json is a flat list of objects:
  {slug, name, enabled, logo, website, start_url, search_url, cdn_prefix,
   raad_domain?, notubiz_domain?}

Every script + app.py resolves its data paths and site config through this
module, so onboarding a municipality is one registry entry (then run
crawl / crawl_raad / ingest / build_index for its slug).
"""
import json
from pathlib import Path

BASE = Path(__file__).parent
REGISTRY_PATH = BASE / "municipalities.json"


def load_registry() -> list[dict]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def enabled() -> list[dict]:
    return [m for m in load_registry() if m.get("enabled", True)]


def enabled_slugs() -> list[str]:
    return [m["slug"] for m in enabled()]


def primary_slug() -> str:
    slugs = enabled_slugs()
    return slugs[0] if slugs else "ijsselstein"


def get(slug: str) -> dict:
    for m in load_registry():
        if m["slug"] == slug:
            return m
    raise KeyError(f"unknown municipality: {slug!r}")


def data_dir(slug: str) -> Path:
    return BASE / "data" / slug


def pdf_dir(slug: str) -> Path:
    return data_dir(slug) / "pdfs"


def add_muni_arg(parser) -> None:
    parser.add_argument(
        "--municipality",
        default=primary_slug(),
        help="municipality slug (default: %(default)s)",
    )
