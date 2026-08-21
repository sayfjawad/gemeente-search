# Domeinmodel

De kernconcepten en hun onderlinge relaties, onafhankelijk van de technische
implementatie.

## Entiteiten

- **Gemeente** (`municipality`): de overkoepelende entiteit; heeft een `slug`,
  een of meer `aliassen` (bijv. `vijfheerenlanden` + 16 historische/dorpsnamen),
  optioneel een `product_sitemap`, `raad_domain`, `notubiz_domain` en
  `skip_paths`.
- **Document**: één bron — een webpagina, een PDF, een raadsstuk of een
  gecureerde referentie. Heeft een canonical URL en een type.
- **Chunk**: een tekstfragment van een document (HTML: ~1400 tekens; PDF: één
  pagina). De eenheid van zoeken en citeren.
- **Embedding**: de 1024-dim vector van een chunk.
- **Bron** (in het antwoord): een chunk die aan de prompt is toegevoegd en een
  `[n]`-volgnummer heeft.
- **Citaat**: een `[n]`-verwijzing in het antwoord naar een bron.

## Relaties

```
Gemeente 1 ─── n Document ─── n Chunk ─── 1 Embedding
   │
   └── n Alias (doorzoekbaar, zelfde corpus)
```

## Levenscyclus van data

1. **Crawlen** — Documenten ontstaan uit de gemeentesite, het raadsarchief en
   de gecureerde referenties.
2. **Ingesten** — Documenten worden gedupliceerd op canonical URL en
   opgesplitst in chunks.
3. **Embedden** — Elke chunk krijgt een embedding.
4. **Queryen** — Een vraag wordt ge-embed en matcht chunks.
5. **Beantwoorden** — De beste chunks worden bronnen in de prompt; het
   antwoord citeert ze.

## Scheiding van concerns

- **Corpus is per gemeente gescheiden** (eigen `data/<slug>/`).
- **Index (`index.sqlite`)** en **embeddings (`embeddings.npy`)** zijn
  gescheiden artefacten, zodat tekst en vectoren onafhankelijk te herbouwen
  zijn.
- **Register (`municipalities.json`)** is metadata over gemeenten, los van de
  data zelf.

Zie [retrieval-and-ranking.md](retrieval-and-ranking.md) en
[llm-concepts.md](llm-concepts.md).
