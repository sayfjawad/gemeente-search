# ADR-009: Brondata (PDF's/index/embeddings) niet in git

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

De afgeleide data is groot: de PDF's plus `index.sqlite` en `embeddings.npy`
per gemeente beslaan 0,1–8 GB (samen ~15 GB). Die data is echter volledig
her-crawlbaar/her-bouwbaar uit de openbare gemeentewebsites. De vraag is wat er
wel en niet in de repository thuishoort.

## 2. Besluit

De zware, herbouwbare afgeleide data wordt genegeerd:
`data/<slug>/pdfs/`, `index.sqlite`, `embeddings.npy`, `state.json`,
`*.log`, en de runtime-`stats.sqlite` (plus `.env` met secrets).

De crawl-**tekst** (`data/<slug>/crawl/*.jsonl`) wordt wél gecommit. Die is
klein (het is alleen tekst), en maakt de index herbouwbaar uit de repo zonder
opnieuw te hoeven crawlen.

## 3. Consequenties

### 3.1. Voordelen

* Slanke repo: geen tientallen GB aan binaries.
* Herbouwbaar: een verse clone kan met `ingest.py` + `build_index.py` de index
  en embeddings reconstrueren uit de gecommitte tekst (of opnieuw crawlen).

### 3.2. Nadelen

* Na een verse clone is de index pas na een ingest+build-run bruikbaar.
* De gecommitte crawl-tekst is een momentopname — die kan verouderen tot de
  volgende crawl, dus de repo "weet" niet automatisch dat er nieuwe content is.

## 4. Alternatieven

1. **Git LFS voor de PDF's**: behoudt de binaries, maar voegt LFS-beheer toe
   terwijl de data toch openbaar her-crawlbaar is. Verworpen (overkill).
2. **Alles committen**: repo-bloat van ~15 GB. Verworpen.
3. **Niets committen** (ook de tekst niet): de index is dan niet herbouwbaar
   zonder her-crawl. Verworpen.

## 5. Referenties

* [`.gitignore`](../../../.gitignore)
