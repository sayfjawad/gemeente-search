# Embeddings & retrieval

## Embeddingmodel: BGE-M3

| Eigenschap | Waarde |
|---|---|
| Model | `BAAI/bge-m3` |
| Dimensie | 1024 |
| Precisie opslag | `fp16` (in `embeddings.npy`) |
| Taal | Meertalig, sterk in Nederlands (cruciaal voor gemeentelijke teksten) |
| Uitvoer | L2-genormaliseerd (cosinus = inproduct) |
| Locatie cache | `/data/huggingface` (gedeeld, `HF_HOME`) |
| Hardware | GPU-node (2× V100) |

Keuze beargumenteerd in
[ADR-002](../07-decision-records/ADR-002-bge-m3-embeddings.md).

## Retrieval: in-memory cosine-similariteit

Geen vector-DB, maar een rechttoe-rechtaan matrixproduct op GPU:

```
scores = embeddings_matrix @ query_embedding.T   # alle cosinus-scores
topk   = torch.topk(scores, k)                    # beste k chunks
```

Keuze beargumenteerd in
[ADR-003](../07-decision-records/ADR-003-in-memory-cosine-similarity.md):
de corpus per gemeente is klein genoeg (duizenden tot tienduizenden chunks),
en een vector-DB zou alleen onderhoudslast toevoegen zonder winst.

## Chunking

- **HTML**: gesplitst op tekstlengte, max ~1400 tekens (`MAX_CHUNK_CHARS`).
- **PDF**: **per pagina** gechunked — zodat een citaat verwijst naar een
  concrete pagina die als afbeelding getoond kan worden.
- Minimaal 40 tekens, anders weggegooid (`MIN_TEXT_CHARS`).

## Ranking & selectie

- Top-N chunks op cosine-similariteit.
- Bronnen geordend op score; de prompt krijgt alleen de beste matches binnen
  het budget (≤ 16 bronnen, ≤ ~8200 tekens).
- **Drempel 0.50**: onder deze score triggert de agentic fallback — zie
  [ADR-005](../07-decision-records/ADR-005-agentic-fallback.md) en
  [06-cross-cutting-concepts/retrieval-and-ranking.md](../06-cross-cutting-concepts/retrieval-and-ranking.md).

## Volledige pijplijn

Zie [10-runtime-and-data-flows/data-pipeline.md](../10-runtime-and-data-flows/data-pipeline.md)
voor crawl → chunk → embed.
