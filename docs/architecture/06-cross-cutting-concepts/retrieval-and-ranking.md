# Retrieval & ranking

Het proces van "vraag" naar "set van bronnen die in de prompt gaan".

## Stap 1 — Query-embedding

De vraag wordt met BGE-M3 ge-embed op de GPU (L2-genormaliseerd), identiek aan
hoe de chunks zijn ge-embed. Door de normalisatie is het inproduct gelijk aan
de cosine-similariteit.

## Stap 2 — Scoring

```
scores = embeddings_matrix @ query_embedding.T
```

Dit is één matrix-vector-product over de hele corpus van de gemeente
(`n_chunks × 1024` @ `1024 × 1`). Op de GPU is dit sub-seconde, ook voor
tienduizenden chunks.

## Stap 3 — Top-k selectie

`torch.topk` levert de beste k chunks. Deze worden geordend op score en
vervolgens door de budgetbeperking gehaald (≤ 16 bronnen, ≤ ~8200 tekens).

## Stap 4 — Drempel & fallback

- Score **≥ 0.50**: de topmatches zijn voldoende; door naar genereren.
- Score **< 0.50**: de vraag valt vermoedelijk buiten de corpus. De
  agentic fallback treedt in werking (ADR-005):
  1. roep de site-eigen zoekmachine aan met de query,
  2. neem de top `AGENTIC_MAX_RESULTS` (3) resultaatpagina's,
  3. knip die in chunks van `AGENTIC_CHUNK_CHARS` (1500) tekens,
  4. neem de beste `AGENTIC_MAX_CHUNKS` (4) chunks op als bronnen.

## Waarom geen her-ranking?

Een cross-encoder (bijv. BGE-reranker) zou de selectie kunnen verbeteren,
maar:

- voegt een tweede model + latentie toe,
- de corpus is klein en BGE-M3 scoort al sterk,
- de winst is hier niet meetbaar groot.

Het staat als mogelijke verbetering op de
[roadmap](../11-roadmap/roadmap.md).

## Volgorde van voorkeur in het antwoord

De bronnen worden in de prompt opgenomen op volgorde van afnemende score,
zodat het model de sterkste matches het eerst ziet en `[n]`-nummers een
betekenisvolle volgorde hebben.
