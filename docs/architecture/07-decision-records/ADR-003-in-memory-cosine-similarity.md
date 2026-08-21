# ADR-003: In-memory cosine similarity i.p.v. vectordatabase

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Retrieval moet, gegeven een vraag-embedding, de best-passende chunks vinden uit
de index van de gekozen gemeente. De gangbare aanpak hiervoor is een
vectordatabase (FAISS, Qdrant, pgvector, …) met een
approximate-nearest-neighbour-index.

## 2. Besluit

Geen vectordatabase. Per gemeente staat de volledige embeddingmatrix
(`n_chunks × 1024`, fp16) als één `torch.Tensor` in GPU-geheugen; een
zoekopdracht is één matrix-vector-vermenigvuldiging (`matrix @ query.T`)
gevolgd door `torch.topk`. Metadata (titel, URL, pagina, tekst) staat in
SQLite (`index.sqlite`), opgevraagd per gevonden chunk-id na de topk.

## 3. Consequenties

### 3.1. Voordelen

* Exacte (geen approximate) nearest-neighbour search — bij een corpus van
  duizenden tot tienduizenden chunks per gemeente is een volledige
  matrixvermenigvuldiging op de GPU sneller dan de netwerk-overhead van een
  externe vectordatabase, zonder de index-kwaliteitscompromissen van ANN.
* Geen extra service om te draaien, monitoren of herstarten.
* Documentfiltering (`only document X`) is een simpele boolean mask over
  dezelfde tensor.
* Zelfde patroon als de zusterprojecten — bewezen aanpak.

### 3.2. Nadelen

* Schaalt niet voorbij pakweg honderdduizenden chunks per gemeente zonder
  herontwerp. Ruim binnen de marge voor de huidige gemeenten; heroverweeg bij
  extreme groei van één corpus.
* De hele matrix moet in GPU-geheugen passen; met meerdere gemeenten tegelijk
  in het geheugen is het VRAM-verbruik de som daarvan (zie ADR-001).

## 4. Alternatieven

1. **FAISS** (lokaal): voegt indexbouw- en opslagcomplexiteit toe zonder
   aantoonbaar snelheidsvoordeel op deze schaal. Verworpen, kan later alsnog.
2. **Qdrant/pgvector** (aparte service): introduceert een extra operationele
   afhankelijkheid voor een probleem dat op deze schaal met een simpele
   tensorvermenigvuldiging is opgelost. Verworpen.

## 5. Referenties

* [`app.py: retrieve()`](../../../app.py)
