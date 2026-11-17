# ADR-001: Multi-gemeente via één register + per-gemeente index

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Het project begon als single-gemeente (IJsselstein), maar moest binnen een dag
opschalen naar meerdere gemeenten (Nieuwegein, Vijfheerenlanden, Utrecht,
Houten, Barendrecht). De kernvraag: één gedeelde index voor alle gemeenten, of
één index per gemeente — en hoe de per-gemeente configuratie (website, zoek-URL,
CDN-prefix, raadsarchief-domein) beheerd moet worden zonder code per gemeente te
dupliceren.

## 2. Besluit

Eén `municipalities.json`-register als single source of truth (geladen via
`muni.py`), met per gemeente een entry `{slug, name, enabled, logo, website,
start_url, search_url, cdn_prefix?, product_sitemap?, skip_paths?,
raad_domain?, notubiz_domain?, aliases?}`. Elke gemeente krijgt een eigen
datamap `data/<slug>/` met een eigen `index.sqlite` en `embeddings.npy`. Eén
FastAPI-service laadt bij startup álle `enabled` gemeenten in het geheugen en
kiest op basis van de `municipality`-parameter (of de dropdown in de UI) welke
index wordt gebruikt. Onboarden is één register-entry plus één pipeline-run.

## 3. Consequenties

### 3.1. Voordelen

* Strikte corpus-isolatie: de ene gemeente "lekt" nooit in het antwoord van de
  andere, en een her-crawl/rebuild van één gemeente raakt de andere niet.
* Onboarden is configuratie, geen code — geen per-gemeente forks of
  conditionele takken.
* Eén service om te draaien/monitoren (in plaats van N), maar N onafhankelijke
  indexen qua data.

### 3.2. Nadelen

* Het geheugenverbruik schaalt lineair met het aantal gemeenten (elke index +
  embeddingmatrix staat in RAM/VRAM). Bij de huidige 6 gemeenten geen
  probleem; bij tientallen gemeenten een aandachtspunt.
* Geen queries over gemeentegrenzen heen (niet nodig voor deze usecase).
* Het register is handmatig onderhouden — er is geen validatie dat een nieuwe
  gemeente ook daadwerkelijk gecrawld/geïndexeerd is (de app slaat een gemeente
  zonder index stilletjes over).

## 4. Alternatieven

1. **Eén gedeelde index met een `gemeente`-tag per chunk**: minder geheugen,
   maar kruisbesmetting bij retrieval en een volledige re-index bij het
   toevoegen van één gemeente. Verworpen.
2. **Eén service per gemeente** (per gemeente een eigen poort/systemd-unit):
   maximale isolatie, maar N× operationele overhead voor een project dat één
   persoon beheert. Verworpen.

## 5. Referenties

* [`muni.py`](../../../muni.py)
* [`municipalities.json`](../../../municipalities.json)
* [`app.py: load_index()`](../../../app.py)
* [per-gemeente-afwijkingen](../03-platforms/per-gemeente-afwijkingen.md)
