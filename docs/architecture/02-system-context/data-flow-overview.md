# Overzicht datastromen

Er zijn twee gescheiden werelden: de **offline pijplijn** (data in) en de
**online query-flow** (antwoorden uit). Ze raken elkaar alleen via de
read-only index per gemeente.

## Offline pijplijn (batch)

```
gemeentesite + CDN ──crawl.py────────┐
raadsinformatie.nl ──crawl_raad.py───┤
curated referenties ──add_reference─┤
                                    ▼
       data/<slug>/crawl/{docs,raad_docs,reference_docs}.jsonl
                                    │ ingest.py (dedup, chunk)
                                    ▼
                     data/<slug>/index.sqlite (documents, chunks)
                                    │ build_index.py (BGE-M3)
                                    ▼
                     data/<slug>/embeddings.npy (fp16, n×1024)
```

Details in
[10-runtime-and-data-flows/data-pipeline.md](../10-runtime-and-data-flows/data-pipeline.md).

## Online query-flow (request/response)

```
vraag (burger)
    │
    ▼
/app.py  →  embed(vraag) op GPU
    │
    ▼
cosine-similariteit vs embeddings.npy → top-N chunks
    │
    ├─ score < 0.50? ──► agentic fallback (site-zoek + fetch)
    │
    ▼
prompt = system + bronnen[top-k] (budget ≤ 8200 tekens, ≤ 16 bronnen)
    │
    ▼
gx10-node: gpt-oss-120b (enable_thinking:false)
    │
    ▼
antwoord met [n]-citaten → UI (bronkaarten + PDF-pagina-afbeelding)
```

Details in
[10-runtime-and-data-flows/query-flow.md](../10-runtime-and-data-flows/query-flow.md).

## Belangrijkste observatie

De pijplijn is **duur en offline** (crawlen kost minuten tot uren, embedden
kost GPU-tijd), de query-flow is **goedkoop en online** (één embedding +
matrixproduct + één LLM-call). Daarom zijn corpus en index per gemeente
opgeslagen als bestanden en in het geheugen geladen — geen externe database in
het requestpad.
