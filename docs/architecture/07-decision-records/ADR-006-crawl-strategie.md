# ADR-006: Crawlstrategie — sitemap-first BFS + Playwright, robots.txt gerespecteerd

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Gemeentesites zijn doorgaans TYPO3-/CMS-gedreven, renderen een deel van de
content via JavaScript, en hosten hun PDF-uploads op een aparte CDN (Cuatro,
per gemeente een eigen tenant-directory). Een naïeve homepage-BFS mist
sitemap-only pagina's; een pure `httpx`-crawler mist JS-gerenderde content. De
crawl moet compleet, respectvol (robots.txt) en herstartbaar zijn.

## 2. Besluit

`crawl.py` combineert:
- **Sitemap-first seeding** (de gezaghebbende pagina-lijst) plus BFS-link-
  discovery vanaf elke pagina; voor Utrecht ook de Digitaal-Loket-
  productcatalogus-sitemap.
- **Playwright (Chromium, headless)** voor het renderen van HTML-pagina's.
- **trafilatura** voor tekstextractie (BeautifulSoup als fallback); PyMuPDF
  voor PDF-paginacount (tekst wordt pas bij ingestie geëxtraheerd).
- **robots.txt** van zowel de site als de CDN wordt gerespecteerd.
- **Canonicalisatie** (`http→https`, strip cache-buster-query/fragment) tegen
  dubbel crawlen.
- **Scope-bewaking**: HTML alleen van de site (+ subdomeinen), PDF alleen van de
  CDN-tenant van die gemeente; interactieve portal-/appointment-/SSO-hosts en
  oneindige filter-URL's worden uitgesloten. De gelaagde trap-verdediging
  (inclusief `CALENDAR_TRAP` voor raads-kalenders) is uitgewerkt in ADR-015.
- **Herstartbaar + polite**: checkpoint in `state.json`, begrensde concurrency
  (default 3) en een per-request delay (0,4 s).

## 3. Consequenties

### 3.1. Voordelen

* Compleet (sitemap dekt ook niet-BFS-bereikbare pagina's), respectvol
  (robots.txt + delay + concurrency), en herstartbaar zonder opnieuw beginnen.
* JS-gerenderde content wordt wel meegenomen.

### 3.2. Nadelen

* Playwright is zwaar en trager dan kale `httpx`-requests.
* De scope-regels (`SKIP_HOST`/`SKIP_PATH`/per-gemeente `skip_paths`) zijn
  heuristieken die per gemeente-aanbieder kunnen afwijken en dus onderhoud
  vragen bij het onboarden van een nieuwe gemeente.

## 4. Alternatieven

1. **Officiële API's / Open Data-portalen**: niet uniform beschikbaar per
   gemeente; zou per gemeente een aparte connector vereisen. Verworpen als
   primaire strategie.
2. **Kale httpx zonder JavaScript**: mist JS-gerenderde content. Verworpen.
3. **robots.txt negeren** (zoals bij het raadsarchief, ADR-007): voor de
   hoofdsite niet nodig en niet wenselijk — de content is via de sitemap
   gewoon bereikbaar. Verworpen.

## 5. Referenties

* [`crawl.py`](../../../crawl.py)
