# gemeente-search

Slimme, geciteerde zoekmachine over de websites van **alle 342 Nederlandse
gemeenten**. Je stelt een vraag in gewone taal en krijgt één samenhangend
antwoord. Elke bewering verwijst naar de exacte bronpagina of PDF-pagina van
de gemeente, inclusief een afbeelding van die PDF-pagina. Zo hoef je niet
blind te vertrouwen op een taalmodel dat bedragen, termijnen of regels zou
kunnen verzinnen.

Live: **[gemeente.multicode.nl](https://gemeente.multicode.nl)** (landingpagina)
· **[/zoek](https://gemeente.multicode.nl/zoek)** (de zoek-app)
· **[/stats](https://gemeente.multicode.nl/stats)** (gebruik)

## Waarom dit bestaat

Gemeentelijke informatie staat verspreid over de hoofdsite, losse PDF's
(verordeningen, beleidsstukken), het productaanbod van het Digitaal Loket en
het gemeenteraadsarchief. Een burger die wil weten of een serre
vergunningsvrij is, of op welke vergoeding hij recht heeft, moet zelf door al
die bronnen heen. Dit project haalt die bronnen gestructureerd binnen
(crawlen), maakt ze semantisch doorzoekbaar (RAG) en laat een taalmodel er
één praktisch, geciteerd antwoord van maken.

## Architectuur

```
┌──────────────────────────────────────────────────────────────────────┐
│  Offline: per-gemeente ingestiepijplijn  (scripts/onboard_all.py)    │
│                                                                      │
│   crawl.py            hoofdsite + PDF's (+ crawl-trap-afweer)        │
│   crawl_raad.py       gemeenteraadsarchief (Notubiz/raadsinformatie) │
│   scripts/wayback_crawl.py  fallback voor sites die ons blokkeren    │
│   scripts/add_reference.py  gecureerde landelijke regels             │
│        │  (elk → data/<slug>/crawl/*.jsonl, op de NAS)               │
│        ▼  ingest.py  (dedup + chunking)                              │
│   data/<slug>/index.sqlite   (documents, chunks)                     │
│        │  build_index.py  (BGE-M3; fp16 op GPU, fp32 op CPU)         │
│        ▼                                                             │
│   data/<slug>/embeddings.npy (n_chunks × 1024, L2-genormaliseerd)    │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  Online: app.py  (FastAPI, :8905)                                    │
│                                                                      │
│   POST /api/search ──┐                                               │
│   POST /api/ask ─────┼─▶ muni_match: gemeente uit de vraag halen     │
│   POST /api/compare ─┘   retrieve(): cosine sim over embeddings.npy  │
│                          + (zwakke match) agentic fallback →         │
│                            de eigen zoekmachine van de gemeentesite  │
│                          + LLM (OpenAI-compatibel; productie:        │
│                            Qwen3.8-27B op vLLM, zelf gehost)         │
│   GET /pdf-image/… ────▶ PyMuPDF pagina-render → PNG                 │
│   GET /pdf/… ──────────▶ volledige bron-PDF (Range, #page=N)         │
└──────────────────────────────────────────────────────────────────────┘
```

**Productie** (sinds 2026-09/10): de app draait als systemd `--user`-unit op
een GPU-server in een datacenter, naast een gedeelde, zelf-gehoste LLM-dienst
(Qwen3.8-27B op vLLM, 4× V100). Query-embedding draait op de CPU, omdat de
GPU's voor het taalmodel zijn. De crawl-data en PDF's (~420 GB) staan op een
NAS via NFS; de indexen (~21 GB) op lokale schijf. Een aparte edge-VPS doet
TLS (nginx + certbot) en proxyt over een privé mesh-VPN. Zie
[ADR-016](docs/architecture/07-decision-records/ADR-016-qwen-op-c4130-via-vllm.md),
[ADR-017](docs/architecture/07-decision-records/ADR-017-hosting-op-c4130-met-nas-data.md)
en [deployment](docs/architecture/09-operations/deployment.md).

## Features

- **Alle 342 gemeenten in één service**: per gemeente een eigen index. Je
  kiest de gemeente in de dropdown, of de app haalt hem uit je vraag ("hoe
  duur is een paspoort in Utrecht?"). Dat doet `muni_match.py`
  deterministisch, zonder LLM, en het herkent ook aliassen (dorpen/kernen) en
  houdt rekening met gemeentenamen die ook gewone woorden zijn (Houten,
  Buren, Best, …). Zie [ADR-001](docs/architecture/07-decision-records/ADR-001-multi-gemeente-register.md).
- **Vraag stellen** (`/api/ask`): RAG-antwoord in het Nederlands met
  `[n]`-citaten per bewering, die verwijzen naar de genummerde bronnen.
- **Gemeenten vergelijken** (`/api/compare`): één vraag over 2–8 gemeenten
  tegelijk ("vergelijk de afvalstoffenheffing in Utrecht en Amersfoort"). Het
  antwoord staat naast elkaar, met bronnen per gemeente.
- **Agentic fallback**: scoort de semantische retrieval zwak, dan gebruikt
  het systeem de eigen zoekmachine van de gemeentesite en haalt de
  top-pagina's live op. Zie [ADR-005](docs/architecture/07-decision-records/ADR-005-agentic-fallback.md).
- **PDF-pagina-afbeeldingen**: elke PDF-bron toont de bijbehorende pagina als
  PNG (`/pdf-image/{slug}/{chunk_id}`), on-demand gerenderd.
- **Zoeken** (`/api/search`): kale semantische zoekresultaten zonder
  LLM-antwoord.
- **Gebruiksstatistieken**: `/api/statistics` + de pagina `/stats` (queries
  per modus, unieke IP's, per dag) uit `stats.sqlite`.
- **UI zonder build-stap**: `static/index.html` (landing, `/`),
  `static/zoek.html` (zoek-app, `/zoek`) en `static/stats.html` (`/stats`),
  met light/dark-thema en gemeentelogo's in `static/logos/`.

## API

| endpoint | methode | omschrijving |
|---|---|---|
| `/api/search` | POST | semantisch zoeken, `{query, top_k, document?, municipality?}` |
| `/api/ask` | POST | RAG-antwoord, `{question, top_k, document?, history?, known_source_ids?, municipality?}` |
| `/api/compare` | POST | vergelijking over gemeenten, `{question, municipalities?, top_k?}` (zonder lijst: gedetecteerd uit de vraag) |
| `/api/municipalities` | GET | ingeschakelde gemeenten (slug, naam, logo, website) |
| `/api/documents` | GET | geïndexeerde documenten van een gemeente |
| `/api/statistics` | GET | gebruiksstatistieken |
| `/pdf-image/{slug}/{chunk_id}` | GET | PNG-render van de PDF-pagina van die chunk |
| `/pdf/{slug}/{filename}` | GET | volledige bron-PDF (Range-requests, `#page=N`) |
| `/`, `/zoek`, `/stats` | GET | landingpagina, zoek-app, statistiekenpagina |

## Benodigdheden

| Wat | Waarvoor | Opmerking |
|---|---|---|
| Python 3.10+ | alles | pakketten in [`requirements.txt`](requirements.txt) |
| Playwright + Chromium | `crawl.py` | voor JS-zware gemeentesites |
| OpenAI-compatibel LLM-endpoint | `/api/ask`, `/api/compare` | zelf gehost (vLLM/llama.cpp/Ollama) of een API; `/api/search` werkt zonder |
| BGE-M3 (~2,3 GB, via Hugging Face) | embeddings | wordt bij eerste gebruik in `HF_HOME` gezet |
| GPU (optioneel) | `build_index.py` | sneller bulk-embedden; queries draaien prima op CPU |
| RAM | de service | alle geladen indexen + embeddings staan in het geheugen |
| Schijf | data | per gemeente 0,1–8 GB aan PDF's; alle 342 samen ~420 GB crawl/PDF + ~21 GB index |
| SMTP (optioneel) | `scripts/notify.py` | e-mail bij onboarding-mijlpalen |

## Lokaal draaien

```bash
git clone https://github.com/sayfjawad/gemeente-search.git && cd gemeente-search

# 1. venv + deps
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install playwright && .venv/bin/playwright install chromium

# 2. config
cp .env.example .env          # vul LLM_BASE_URL / LLM_MODEL (/ LLM_API_KEY) in

# 3. één gemeente onboarden (register-entry staat al in municipalities.json)
.venv/bin/python3 crawl.py --municipality ijsselstein        # hoofdsite + PDF's
.venv/bin/python3 crawl_raad.py --municipality ijsselstein   # raadsarchief (optioneel)
.venv/bin/python3 scripts/add_reference.py --municipality ijsselstein
.venv/bin/python3 ingest.py --municipality ijsselstein       # → index.sqlite
.venv/bin/python3 build_index.py --municipality ijsselstein  # → embeddings.npy

# 4. draaien
.venv/bin/python3 -m uvicorn app:app --port 8905
# → http://localhost:8905/zoek
```

Alleen gemeenten met `"enabled": true` in `municipalities.json` én een
gebouwde index worden geladen. Meer in
[local-development](docs/architecture/08-development/local-development.md).

## Productie-deploy

Kort samengevat (volledig in [deployment.md](docs/architecture/09-operations/deployment.md)):

```bash
cp deploy/gemeente-search.service ~/.config/systemd/user/
systemctl --user daemon-reload && systemctl --user enable --now gemeente-search
```

Productie is een **kopie** van deze repo (geen git-checkout): wijzigingen
eerst hier committen en pushen, daarna kopiëren (zonder `data/`, `.env`,
`.venv`, `stats.sqlite`) en de service herstarten. Na het bouwen van een
nieuwe index is ook een herstart nodig.

## Landelijke uitrol (alle 342 gemeenten)

- **`scripts/onboard_all.py`**: de orchestrator. Per gemeente: `crawl.py` →
  `ingest.py` → `build_index.py` → register op `enabled` → app herstarten →
  controleren via `/api/municipalities`. De voortgang staat in
  `scripts/onboarding_queue.json` en is hervatbaar na een crash of reboot.
  Een kwaliteitsgate (`ONBOARD_MIN_DOCS`, standaard 50) houdt gemeenten met
  een lege crawl offline.
- **`scripts/monitor.py`**: live web-monitor op poort **8906** met per
  gemeente de status, gecrawlde docs en de index-omvang.
- **`scripts/wayback_crawl.py`**: fallback voor sites die ons blokkeren. Haalt
  de gearchiveerde HTML uit de Wayback Machine in hetzelfde
  `docs.jsonl`-formaat. Citaties houden de originele URL.
- **Crawl-trap-afweer**: `crawl.py` weert URL-ruimtes die de frontier laten
  exploderen (file-transfer-portalen, session-tokens, facet- en
  paginatie-parameters, raadskalenders). Opruimen kan met
  `scripts/strip_traps.py`, `scripts/prune_junk.py`,
  `scripts/analyze_traps.py` en `scripts/reingest_stripped.py`. Zie
  [ADR-015](docs/architecture/07-decision-records/ADR-015-crawl-trap-verdediging.md).
- **Hulpscripts**: `scripts/_enable.py <slug…>` (gemeente inschakelen),
  `scripts/_finish.py` (los ingest + index draaien),
  `scripts/fetch_logos.py` (gemeentelogo's ophalen).
- Afwijkingen per gemeente (`skip_paths`, `product_sitemap`, `aliases`, …):
  [per-gemeente-afwijkingen.md](docs/architecture/03-platforms/per-gemeente-afwijkingen.md).

## Over de brondata

De zware afgeleide data zit bewust **niet** in deze repo (zie
[ADR-009](docs/architecture/07-decision-records/ADR-009-brondata-niet-in-git.md)):
gedownloade PDF's, crawl-tekst, `index.sqlite` en `embeddings.npy`. Alles is
opnieuw te crawlen en te bouwen. In productie zijn `data/<slug>/crawl` en
`data/<slug>/pdfs` symlinks naar een NAS-share. Alleen de `docs.jsonl` van de
eerste zes, met de hand ge-onboarde gemeenten staat nog in git, van vóór die
migratie. De brondata is openbare gemeente-informatie.

## Architectuurbesluiten (ADR's)

| ADR | Besluit |
|---|---|
| [001](docs/architecture/07-decision-records/ADR-001-multi-gemeente-register.md) | Multi-gemeente register (`municipalities.json`) |
| [002](docs/architecture/07-decision-records/ADR-002-bge-m3-embeddings.md) | BGE-M3 als embeddingmodel |
| [003](docs/architecture/07-decision-records/ADR-003-in-memory-cosine-similarity.md) | In-memory cosine similarity, geen vector-DB |
| [004](docs/architecture/07-decision-records/ADR-004-gpt-oss-120b-llama-cpp.md) | GPT-OSS-120B via llama.cpp *(vervangen door 016)* |
| [005](docs/architecture/07-decision-records/ADR-005-agentic-fallback.md) | Agentic fallback via de zoekfunctie van de site |
| [006](docs/architecture/07-decision-records/ADR-006-crawl-strategie.md) | Crawlstrategie |
| [007](docs/architecture/07-decision-records/ADR-007-raadsinformatie-robots-uitzondering.md) | Robots-uitzondering voor het raadsarchief |
| [008](docs/architecture/07-decision-records/ADR-008-curated-reference-docs.md) | Gecureerde landelijke referentiedocumenten |
| [009](docs/architecture/07-decision-records/ADR-009-brondata-niet-in-git.md) | Brondata niet in git |
| [010](docs/architecture/07-decision-records/ADR-010-deploy-topologie-hergebruikt.md) | Deploy-topologie hergebruikt van zusterprojecten |
| [011](docs/architecture/07-decision-records/ADR-011-open-toegang-zonder-authenticatie.md) | Open toegang zonder authenticatie |
| [012](docs/architecture/07-decision-records/ADR-012-single-page-frontend-met-bronkaarten.md) | Frontend zonder build-stap, met bronkaarten |
| [013](docs/architecture/07-decision-records/ADR-013-deepseek-tijdelijke-failover.md) | DeepSeek als tijdelijke failover *(vervangen)* |
| [014](docs/architecture/07-decision-records/ADR-014-verhuizing-naar-c4130.md) | GPT-OSS-120B op c4130-4xv100 *(vervangen door 016)* |
| [015](docs/architecture/07-decision-records/ADR-015-crawl-trap-verdediging.md) | Crawl-trap-verdediging |
| [016](docs/architecture/07-decision-records/ADR-016-qwen-op-c4130-via-vllm.md) | **Huidig LLM**: zelf-gehoste Qwen3.8-27B via vLLM |
| [017](docs/architecture/07-decision-records/ADR-017-hosting-op-c4130-met-nas-data.md) | **Huidige hosting**: GPU-server in datacenter, data op NAS, embeddings op CPU |

## Documentatie

De volledige architectuur staat in [`docs/architecture/`](docs/architecture/README.md)
(genummerd 00–13), plus het projectjournaal
[docs/project-journey.md](docs/project-journey.md).

Contact of een gemeente laten toevoegen: via
[stichtingduurzaamai.nl](https://stichtingduurzaamai.nl).
