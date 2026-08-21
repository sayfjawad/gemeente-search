# gemeente-search platform (de applicatie)

Eén FastAPI-service die het volledige systeem huisvest: API, retrieval,
promptbouw en statische UI.

## Bouwblokken

| Module | Bestand | Verantwoordelijkheid |
|---|---|---|
| API-laag | `app.py` | `/api/search`, `/api/ask`, `/api/municipalities`, `/api/documents`, `/api/statistics`, `/pdf-image/…`, `/pdf/…` |
| Crawler hoofdsite | `crawl.py` | sitemap-BFS + Playwright + Trafilatura → `data/<slug>/crawl/docs.jsonl` |
| Crawler raadsarchief | `crawl_raad.py` | Notubiz `ris2` → `data/<slug>/crawl/raad_docs.jsonl` |
| Ingest | `ingest.py` | merge 3 bronnen → `data/<slug>/index.sqlite` (dedup, chunk) |
| Embedder | `build_index.py` + `embedder.py` | BGE-M3 → `data/<slug>/embeddings.npy` |
| Register | `muni.py` + `municipalities.json` | gemeente-slugs, data-paden, aliassen |
| Frontend | `static/index.html` | SPA (vanilla JS), thema, gemeente-selector, bronkaarten |

## Belangrijkste constanten (`app.py`)

| Constante | Waarde | Betekenis |
|---|---|---|
| `LLM_BASE_URL` | `http://100.64.x.x:8083/v1` | llama.cpp-endpoint |
| `LLM_MODEL` | `gpt-oss-120b` | geselecteerd model |
| `AGENTIC_THRESHOLD` | `0.50` | drempel waaronder fallback triggert |
| `AGENTIC_MAX_RESULTS` | `3` | top-resultaten site-zoek |
| `AGENTIC_MAX_CHUNKS` | `4` | chunks per gevonden pagina |
| `AGENTIC_CHUNK_CHARS` | `1500` | tekens per fallback-chunk |
| `MAX_TOTAL_SOURCE_CHARS` | `8200` | tekenbudget bronnen in prompt |
| `MAX_SOURCES_IN_CONTEXT` | `16` | maximaal aantal bronnen |

## Retrieval-aanpak

- In-memory: `embeddings.npy` wordt geladen, `matrix @ q.T` berekent de
  cosinus-scores, `torch.topk` levert de top-N. Geen vector-DB.
- Per gemeente een gescheiden index; de slug uit de request bepaalt welke
  geladen wordt.

Zie [embedding-and-retrieval.md](embedding-and-retrieval.md) en
[llm-node.md](llm-node.md).
