# Scope & grenzen

## Binnen scope

- Crawlen van de hoofdsite (HTML + PDF-uploads) en het gemeenteraadsarchief
  (raadsinformatie.nl) van meerdere gemeenten.
- Eén semantisch doorzoekbare index **per gemeente** (gescheiden corpora).
- Eén samenhangend, geciteerd antwoord per vraag (RAG).
- Per bewering een bronverwijzing; voor PDF-bronnen een pagina-afbeelding.
- Meerdere gemeenten bedienen vanuit **één service**, met een selector in de UI.
- Gecureerde referentiedocumenten voor landelijke regels die niet op de
  gemeentesite staan.

## Buiten scope (bewust niet gebouwd)

- **Geen juridisch bindend advies** — het antwoord is een hulpmiddel; zie de
  disclaimer in de UI.
- **Geen accounts / multi-tenant scheiding / audit-trail** — open, gedeelde
  toegang (zie [ADR-011](../07-decision-records/ADR-011-open-toegang-zonder-authenticatie.md)).
- **Geen scheduler** — her-crawl is een handmatige pipeline-run.
- **Geen redistributie van de PDF's** — die blijven lokaal (zie
  [ADR-009](../07-decision-records/ADR-009-brondata-niet-in-git.md)).
- **Geen queries over gemeentegrenzen heen** — elke vraag is voor één gemeente.

## Aannames

- Gemeentesites zijn benaderbaar via HTTP(S) en sitemap; raadsarchieven via
  raadsinformatie.nl (Notubiz). Gemeenten met een afwijkende aanbieder vereisen
  een eigen crawl-configuratie.
- De gx10-node (LLM) en de GPU-node (embeddings) zijn bereikbaar via Tailscale.
