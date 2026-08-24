# gemeente-search

Slimme, geciteerde zoekmachine over gemeentelijke websites. Stel een vraag in
gewone taal en krijg één samenhangend antwoord dat citeert naar de exacte
bronpagina of PDF-pagina van de gemeente — inclusief een weergave van die
PDF-pagina, zodat je niet blind hoeft te vertrouwen op een taalmodel dat
bedragen, termijnen of regels zou kunnen verzinnen.

Live: **gemeente.multicode.nl**

## Waarom dit bestaat

Gemeentelijke informatie staat verspreid over de hoofdsite, losse PDF's
(verordeningen, beleidsstukken), het productaanbod van het Digitaal Loket, en
het gemeenteraadsarchief (raadsinformatie.nl). Een burger die wil weten of een
serre vergunningsvrij is, of een uitkering/vergoeding waar hij recht op heeft,
moet zelf door al die bronnen heen ploegen. Dit project haalt die bronnen
gestructureerd binnen (crawlen), maakt ze semantisch doorzoekbaar (RAG), en laat
een taalmodel er één praktisch, geciteerd antwoord van maken.

## Architectuur

```
┌──────────────────────────────────────────────────────────────────────┐
│  Offline: per-gemeente ingestiepijplijn                              │
│                                                                      │
│   crawl.py            hoofdsite + CDN-PDF's (Cuatro)                 │
│   crawl_raad.py       gemeenteraadsarchief (Notubiz/raadsinformatie) │
│   scripts/add_reference.py  gecureerde landelijke regels             │
│        │  (elk → data/<slug>/crawl/*.jsonl)                          │
│        ▼  ingest.py  (dedup + chunking)                              │
│   data/<slug>/index.sqlite   (documents, chunks)                     │
│        │  build_index.py  (BGE-M3, GPU, fp16)                        │
│        ▼                                                             │
│   data/<slug>/embeddings.npy (n_chunks × 1024, L2-genormaliseerd)    │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  Online: app.py  (FastAPI, :8905, GPU-resident)                      │
│                                                                      │
│   POST /api/search ─┐                                                │
│   POST /api/ask ────┼─▶ retrieve(): cosine sim over embeddings.npy   │
│                     │   + (zwakke match) agentic fallback →          │
│                     │     site-eigen zoekmachine                     │
│                     │   + GPT-OSS-120B (llama.cpp op de gx10-node)   │
│   GET /pdf-image/…  ┼─▶ PyMuPDF pagina-render → PNG                  │
│   GET /pdf/…        ┴─▶ volledige bron-PDF (Range/#page=N)           │
└──────────────────────────────────────────────────────────────────────┘
```

Zelfde patroon als de andere GPU-backed zoekapplicaties in dit account
(`wilders-search`, `lift-normen-search`, `slimme-archief-zoeker`): systemd
`--user`-unit op de GPU-machine, nginx-reverse-proxy naar de Tailscale-IP op een
aparte edge-VPS, certbot voor TLS. Het taalmodel draait apart van de app: op de
gx10-node via llama.cpp.

Volledige onderbouwing van elke keuze staat in
[docs/architecture/](docs/architecture/README.md) — inclusief de decision
records.

## Features

- **Meerdere gemeenten in één service**: de index per gemeente is gescheiden,
  de dropdown kiest de gemeente. De landelijke uitrol brengt gemeenten continu
  online (zie "Landelijke uitrol" hieronder); onboarden van één nieuwe gemeente
  is een register-entry plus een pipeline-run (zie
  [ADR-001](docs/architecture/07-decision-records/ADR-001-multi-gemeente-register.md)).
- **Vraag stellen** (`/api/ask`): RAG-antwoord in het Nederlands met
  `[n]`-citaten die verwijzen naar de genummerde bronnen, per bewering.
- **Agentic fallback**: als semantische retrieval zwak scoort (onder een
  drempel), valt het systeem terug op de eigen zoekmachine van de gemeentesite
  (`/zoeken?trefwoord=...`) en haalt het de top-pagina's live op — "staat het
  niet in de index, haal het op" (zie
  [ADR-005](docs/architecture/07-decision-records/ADR-005-agentic-fallback.md)).
- **PDF-pagina-afbeeldingen**: elke PDF-bron toont de bijbehorende pagina als
  PNG (`/pdf-image/{slug}/{chunk_id}`), on-demand gerenderd vanuit de bron-PDF.
- **Zoeken** (`/api/search`): kale semantische zoekresultaten, optioneel te
  filteren op één document, zonder LLM-antwoord.
- **Gebruiksstatistieken** (`/api/statistics`): aantal queries per modus,
  unieke IP's, per dag — opgeslagen in `stats.sqlite` (buiten `data/`, zodat
  her-indexeren de historie niet wist).
- Responsive UI zonder build-stap — twee self-contained HTML-bestanden:
  `static/index.html` (landingpagina op `/`) en `static/zoek.html` (de zoek-app op
  `/zoek`), beide met light/dark-theme.

**Ondersteunde gemeenten:** IJsselstein, Nieuwegein, Vijfheerenlanden (16
dorpen/steden), Utrecht en Houten. De dienst is vanwege **beperkte middelen**
bewust beperkt tot deze gemeenten — elke gemeente vraagt een eigen
crawl-, indexeer- en onderhoudsinspanning. Wil je een gemeente laten toevoegen
(of meedenken over opschaling)? Neem contact op via
[stichtingduurzaamai.nl](https://stichtingduurzaamai.nl).

## API

| endpoint | methode | omschrijving |
|---|---|---|
| `/api/search` | POST | semantisch zoeken, `{query, top_k, document?, municipality?}` |
| `/api/ask` | POST | RAG-antwoord, `{question, top_k, document?, history?, known_source_ids?, municipality?}` |
| `/api/municipalities` | GET | lijst van ingeschakelde gemeenten (slug, naam, logo) |
| `/api/documents` | GET | lijst van geïndexeerde documenten per gemeente |
| `/api/statistics` | GET | gebruiksstatistieken (queries, unieke IP's, per dag) |
| `/pdf-image/{slug}/{chunk_id}` | GET | PNG-render van de PDF-pagina van die chunk |
| `/pdf/{slug}/{filename}` | GET | volledige bron-PDF (Range-requests, `#page=N`) |
| `/` | GET | de landingpagina (`static/index.html`) |
| `/zoek` | GET | de zoek-app (`static/zoek.html`) |

## Lokaal draaien

Vereist: Python 3.10+, een GPU (of geduld op CPU), en bereikbaarheid van de
gx10-node voor het taalmodel (`LLM_BASE_URL` in `.env`). De runtime-venv wordt
gedeeld met `lift-normen-search` (`/data/git/lift-normen-search/.venv`, een
bewezen
ML-stack met torch/transformers/pymupdf/fastapi).

```bash
# 1. venv + deps (of symlink naar de gedeelde venv)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install playwright && .venv/bin/playwright install chromium

# 2. één gemeente onboarden (register-entry staat al in municipalities.json):
.venv/bin/python3 crawl.py --municipality ijsselstein        # hoofdsite + PDF's
.venv/bin/python3 crawl_raad.py --municipality ijsselstein   # raadsarchief (optioneel)
.venv/bin/python3 scripts/add_reference.py --municipality ijsselstein
.venv/bin/python3 ingest.py --municipality ijsselstein       # → index.sqlite
.venv/bin/python3 build_index.py --municipality ijsselstein  # → embeddings.npy (GPU)

# 3. draaien
cp .env.example .env    # vul LLM_BASE_URL + SMTP_* in
.venv/bin/python3 -m uvicorn app:app --port 8905
```

Een volledige onboarding draait via
[`scripts/onboard_barendrecht.sh`](scripts/onboard_barendrecht.sh) (detached,
met e-mail per mijlpaal).

## Landelijke uitrol (alle ~342 gemeenten)

De automatische onboarding van heel Nederland draait als systemd-unit op de
GPU-machine en is resumable/fault-tolerant:

- **`scripts/onboard_all.py`** — de orchestrator. Per gemeente:
  `crawl.py` → `ingest.py` → `build_index.py` → register flippen naar
  `enabled` → app herstarten → verifiëren via `/api/municipalities`. Voortgang
  staat in `scripts/onboarding_queue.json` (`pending`/`crawled`/`done`/`failed`
  per slug); een crash of reboot pakt op waar hij was. Een kwaliteitsgate
  (`ONBOARD_MIN_DOCS`, default 50) voorkomt dat een gemeente met een lege crawl
  live gaat — die wordt `failed` met een duidelijke reden.
- **`scripts/monitor.py`** — live web-monitor op poort **8906**: per gemeente
  een tabel met status, gecrawlde docs, nog-te-verwerken URLs, en
  index-docs/chunks, met ▲▼-deltas die per poll veranderen. Gebouwd omdat een
  uitrol van deze omvang zonder zicht "voelt alsof er niets gebeurt tot het fout
  gaat".
- **`scripts/wayback_crawl.py`** — fallback voor sites die ons blokkeren
  (CloudFront 403): trekt de gearchiveerde HTML van de site uit de Wayback
  Machine en schrijft hetzelfde `docs.jsonl`-formaat, zodat de rest van de
  pipeline er niets van merkt. Citaties behouden de originele URL; alleen de
  fetch loopt via `web.archive.org`. Gebruikt voor Dalfsen (9126 docs live).
- **Crawl-trap-afweer**: `crawl.py` weert de vier traps die gemeentelijke sites
  de frontier laten exploderen — file-transfer portals
  (`cryptshare.`/`bestand.`/`filetransfer.`-subdomeinen), `;jsessionid=`-session-tokens,
  en faceted-search/paginatie query-params (`tx_solr`, `chash`, `offset`, …). Die
  leverden ooit ~1,3M junk-pagina's op over 70 gemeenten; de opruimscripts zijn
  `scripts/strip_traps.py` (herschrijft `docs.jsonl` minus trap-lines, met backup)
  en `scripts/reingest_stripped.py` (re-ingest + rebuild van de live gemeenten).

De crawl-output en PDF's staan op de NAS (`/mnt/nas-gemeente/<slug>/`,
bereikbaar via `data/<slug>/crawl`- en `data/<slug>/pdfs`-symlinks) — zie
"Over de brondata" hieronder.

## Over de brondata

De zware afgeleide data zit bewust **niet** in deze repo (zie
[ADR-009](docs/architecture/07-decision-records/ADR-009-brondata-niet-in-git.md)):
`data/<slug>/pdfs/` (de gedownloade PDF's, per gemeente 0,1–8 GB),
`index.sqlite`, en `embeddings.npy`. Sinds de NAS-migratie staat ook de
crawl-*tekst* (`data/<slug>/crawl/*.jsonl`) niet meer in git — de `crawl/`- en
`pdfs/`-mappen zijn symlinks naar `/mnt/nas-gemeente/<slug>/`, zodat de uitrol
van alle ~342 gemeenten niet lokaal schijft maar op de NAS landt. De brondata
is openbare gemeente-informatie, dus er is geen auteursrechtelijk bezwaar,
alleen een praktisch: grootte en her-crawlbaarheid.

## Documentatie

De volledige architectuur staat in `docs/architecture/`, gestructureerd met
dezelfde **nummering als `odp-architecture`** (00–13):

- [docs/project-journey.md](docs/project-journey.md) — het projectjournaal: wat is
  er bereikt, welke problemen kwamen we tegen, en wat heeft het opgeleverd
- [docs/architecture/](docs/architecture/README.md) — index & navigatietabel
- [00-overview](docs/architecture/00-overview/) — context, visie, scope, glossary
- [01-principes](docs/architecture/01-architecture-principles/) — drivers, constraints, invloeden uit andere projecten
- [02-systeemcontext](docs/architecture/02-system-context/) — contextdiagram, externe systemen
- [03-platforms](docs/architecture/03-platforms/) — de applicatie, de LLM-node (GPT-OSS-120B), embeddings & retrieval
- [05-cross-cutting concerns](docs/architecture/05-cross-cutting-concerns/) — RAG & contextvenster, bronvermelding, kosten & schaling
- [07-decision-records](docs/architecture/07-decision-records/) — ADR's: waarom elke keuze is gemaakt zoals hij is gemaakt
- [11-roadmap](docs/architecture/11-roadmap/) — verbeteringen + schaling naar heel Nederland (GB-inschatting)
- [12-diagrams](docs/architecture/12-diagrams/) — PlantUML-bronnen
