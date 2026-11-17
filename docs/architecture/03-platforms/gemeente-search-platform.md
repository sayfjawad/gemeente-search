# gemeente-search platform (de applicatie)

Eén FastAPI-service die het volledige systeem huisvest: API, retrieval,
promptbouw en statische UI.

## Bouwblokken

| Module | Bestand | Verantwoordelijkheid |
|---|---|---|
| API-laag | `app.py` | `/api/search`, `/api/ask`, `/api/compare`, `/api/municipalities`, `/api/documents`, `/api/statistics`, `/pdf-image/…`, `/pdf/…`, `/stats`, `/zoek` |
| Crawler hoofdsite | `crawl.py` | sitemap-BFS + Playwright + Trafilatura → `data/<slug>/crawl/docs.jsonl` |
| Crawler raadsarchief | `crawl_raad.py` | Notubiz `ris2` → `data/<slug>/crawl/raad_docs.jsonl` |
| Ingest | `ingest.py` | merge 3 bronnen → `data/<slug>/index.sqlite` (dedup, chunk) |
| Embedder | `build_index.py` + `embedder.py` | BGE-M3 → `data/<slug>/embeddings.npy` |
| Register | `muni.py` + `municipalities.json` | gemeente-slugs, data-paden, aliassen |
| Gemeente-detectie | `muni_match.py` | herkent de gemeente(n) in een vraag (deterministisch, geen LLM) voor routing en `/api/compare` |
| Frontend | `static/index.html`, `static/zoek.html`, `static/stats.html` | landingpagina, zoek-app (vanilla JS, bronkaarten, light/dark), gebruiksstatistieken |

## Belangrijkste constanten (`app.py`)

| Constante | Waarde | Betekenis |
|---|---|---|
| `LLM_BASE_URL` | env, productie `http://127.0.0.1:8080/v1` | OpenAI-compatibel endpoint (vLLM) |
| `LLM_MODEL` | env, productie `qwen3.8-27b` | geselecteerd model (default in code nog `gpt-oss-120b`) |
| `AGENTIC_THRESHOLD` | `0.50` | drempel waaronder fallback triggert |
| `AGENTIC_MAX_RESULTS` | `3` | top-resultaten site-zoek |
| `AGENTIC_MAX_CHUNKS` | `4` | chunks per gevonden pagina |
| `AGENTIC_CHUNK_CHARS` | `1500` | tekens per fallback-chunk |
| `MAX_TOTAL_SOURCE_CHARS` | `8200` | tekenbudget bronnen in prompt |
| `MAX_SOURCES_IN_CONTEXT` | `16` | maximaal aantal bronnen |
| `COMPARE_MAX_MUNIS` | `8` | maximaal aantal gemeenten in één vergelijking |

## Retrieval-aanpak

- In-memory: `embeddings.npy` wordt geladen, `matrix @ q.T` berekent de
  cosinus-scores, `torch.topk` levert de top-N. Geen vector-DB.
- Per gemeente een gescheiden index. Alle indexen worden bij het opstarten
  geladen. De slug uit de request bepaalt welke wordt doorzocht. Zonder slug
  probeert `muni_match` de gemeente uit de vraag te halen.
- Query-embedding draait in productie op de CPU (ADR-017).

Zie [embedding-and-retrieval.md](embedding-and-retrieval.md) en
[llm-node.md](llm-node.md).

## Crawl-trap verdediging & per-gemeente afwijkingen

`crawl.py` heeft een gelaagde verdediging tegen oneindige URL-ruimtes
(facet-zoek, TYPO3 Solr, file-transfer-portalen, raads-kalenders) — zie
[ADR-015](../07-decision-records/ADR-015-crawl-trap-verdediging.md).
Gemeente-specifieke configuratieafwijkingen (`skip_paths`,
`product_sitemap`, `cdn_prefix`, `raad_domain`, `notubiz_domain`,
`aliases`) staan in [per-gemeente-afwijkingen.md](per-gemeente-afwijkingen.md).
