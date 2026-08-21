# ADR-005: Agentic fallback naar de site-eigen zoekmachine

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Semantische retrieval over embeddings rankt exacte termen en afkortingen vaak
slecht (de embedding "lijkt op" een bredere betekenis, niet op de exacte
string). Tegelijk is de index niet altijd compleet — nieuw geplaatste content
staat er nog niet in tot de volgende crawl. De wens was expliciet: "staat het
niet in de index, haal het dan op".

## 2. Besluit

Wanneer de hoogste cosinescore onder een drempel (`AGENTIC_THRESHOLD = 0.50`)
ligt — en er geen documentfilter of chatgeschiedenis actief is — bevraagt
`app.py` de eigen zoekmachine van de gemeentesite (`/zoeken?trefwoord=...`, een
server-gerenderde keyword-zoeker). De top-pagina's (max 3) worden live
opgehaald, hun tekst wordt geëxtraheerd en gechunkt, en maximaal 4 chunks worden
als extra bronnen geïnjecteerd (gemarkeerd `agentic: true`). Zo complementeert
de keyword-zoeker de embeddings.

## 3. Consequenties

### 3.1. Voordelen

* Volledigheid: exacte termen/afkortingen die de embeddings missen, worden toch
  gevonden.
* Antwoorden op content die nog niet (her-)gecrawld is.
* Alleen geactiveerd bij zwakke retrieval — normale vragen blijven puur
  op de (snelle) index.

### 3.2. Nadelen

* Extra latency (site-search + N pagina-fetches) per vraag met zwakke match.
* Fragiel: afhankelijk van de specifieke HTML-markup van de zoekresultaten
  (`div.search-results li[class*='__result']`), die per gemeente/leverancier
  kan verschillen — een gemeente met een andere zoeklay-out levert dan geen
  agentic-resultaten op.
* Geen caching van de opgehaalde pagina's; elke zwakke vraag doet opnieuw de
  fetches.

## 4. Alternatieven

1. **Altijd puur-RAG, geen fallback**: simpel en snel, maar mist exacte termen
   en niet-geïndexeerde content. Verworpen (voldeed niet aan de expliciete
   "haal het op"-wens).
2. **Altijd de site-search erbij**: volledig, maar traag en overbodig wanneer
   de index het antwoord al heeft. Verworpen.

## 5. Referenties

* [`app.py: agentic_fetch()`](../../../app.py)
* [`app.py: site_search()`](../../../app.py)
