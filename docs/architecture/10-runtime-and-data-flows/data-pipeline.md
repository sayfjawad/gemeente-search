# Datapijplijn (offline)

De volledige route van "publieke bron" naar "doorzoekbare index".

```plantuml
@startuml data-pipeline
!include <C4/C4_Component>

title Datapijplijn (offline batch)

[Gemeentesite + CDN] --> (crawl.py) : sitemap BFS + Playwright + Trafilatura
[raadsinformatie.nl] --> (crawl_raad.py) : ris2 (Notubiz)
[Curated referenties] --> (scripts/add_reference.py)

(crawl.py) --> data/<slug>/crawl/docs.jsonl
(crawl_raad.py) --> data/<slug>/crawl/raad_docs.jsonl
(scripts/add_reference.py) --> data/<slug>/crawl/reference_docs.jsonl

data/<slug>/crawl/docs.jsonl --> (ingest.py) : dedup op canonical URL, chunking
data/<slug>/crawl/raad_docs.jsonl --> (ingest.py)
data/<slug>/crawl/reference_docs.jsonl --> (ingest.py)

(ingest.py) --> data/<slug>/index.sqlite : documents + chunks
data/<slug>/index.sqlite --> (build_index.py) : BGE-M3 (GPU)
(build_index.py) --> data/<slug>/embeddings.npy : fp16, n_chunks x 1024

@enduml
```

## Stap-voor-stap

1. **crawl.py** — sitemap-first BFS over de hoofdsite; Playwright rendert
   dynamische pagina's; Trafilatura extraheert leesbare tekst. Downloadt
   PDF-uploads. Respecteert robots.txt (site én CDN). Hervatbaar via
   `data/<slug>/crawl/state.json` → `data/<slug>/crawl/docs.jsonl`.
2. **crawl_raad.py** — apart pad voor het raadsarchief (Notubiz `ris2`),
   jaren 2014–2027, per module-seed. robots.txt wordt hier bewust niet
   gehonoreerd (ADR-007) → `data/<slug>/crawl/raad_docs.jsonl`.
3. **scripts/add_reference.py** — voegt gecureerde landelijke referenties toe
   (bijv. "vergunningsvrij bouwen", Omgevingsloket/Bbl) →
   `data/<slug>/crawl/reference_docs.jsonl`.
4. **ingest.py** — merge van de drie bronnen; dedupliceert op canonical URL;
   chunked (HTML ~1400 tekens, PDF per pagina); minimale tekstlengte 40;
   schrijft `data/<slug>/index.sqlite` (tabellen `documents` + `chunks`).
5. **build_index.py** — leest de chunks, embedt met BGE-M3 op GPU
   (`TOKEN_BUDGET=16384`, batches op tokenlengte), slaat op als `fp16`
   `data/<slug>/embeddings.npy` (n_chunks × 1024).

## Eigenschappen

- **Idempotent**: ingest en build_index zijn herhaalbaar.
- **Hervatbaar**: crawl is append-only en state-gestuurd.
- **Per gemeente gescheiden**: alles onder `data/<slug>/`.

Zie [query-flow.md](query-flow.md) voor de online kant.
