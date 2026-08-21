# ADR-008: Gecureerde referentiedocumenten voor kennishiaten

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Sommige regels staan niet op de gemeentesite maar bij een landelijke instantie.
Concreet: de vergunningpagina's van de gemeente verwijzen voor de feitelijke
"vergunningsvrij bouwen"-criteria naar het Omgevingsloket / het Besluit
bouwwerken leefomgeving (Bbl). Die content is verspreid over interactieve
tools en daardoor niet (netjes) crawlbaar — terwijl burgers er juist concrete
vragen over stellen ("mag ik een serre van 6×4 m in mijn 8×6 m tuin plaatsen?").

## 2. Besluit

`scripts/add_reference.py` voegt één beknopte, nauwkeurig gebronde samenvatting
van die landelijke regels toe als een gewoon document-record
(`reference_docs.jsonl`), die door `ingest.py`/`build_index.py` net als elke
andere pagina wordt gechunkt en ge-embed. De gemeentenaam wordt bij generatie
gesubstitueerd, zodat het document per gemeente correct aansluit.

## 3. Consequenties

### 3.1. Voordelen

* Concrete, regelgebaseerde antwoorden op bouwvragen die anders onbeantwoord
  zouden blijven.
* Eenvoudig mechanisme (een normale doc-record) — geen aparte codepaden.

### 3.2. Nadelen

* Handmatige curatie: de samenvatting moet accuraat blijven en opnieuw worden
  gegenereerd als de regels wijzigen (er is geen automatische sync met het
  Omgevingsloket).
* Risico dat een verouderde samenvatting als "actueel" antwoord wordt gegeven —
  de bronvermelding (omgevingsloket.nl) staat erbij, maar de tekst zelf is een
  momentopname.

## 4. Alternatieven

1. **Het Omgevingsloket zelf crawlen**: de regels zijn interactief/JS-gedreven
   en daardoor niet stabiel scrape-baar. Verworpen.
2. **Het gat laten bestaan**: burgers krijgen "weet ik niet" op een veelgestelde
   vraag — onacceptabel gezien het doel. Verworpen.

## 5. Referenties

* [`scripts/add_reference.py`](../../../scripts/add_reference.py)
