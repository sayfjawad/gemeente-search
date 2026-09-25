# ADR: 015 - Verhuizing naar c4130-4xp100 (datacenter) en opslagindeling

* **Status:** Accepted
* **Datum:** 2026-09-25
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

`c4130-4xv100` (ADR-014) is op 2026-09-11 verkocht. De vervanger **`c4130-4xp100`**
(ook Dell C4130, 4× V100-SXM2-32GB) staat sinds 2026-09-21/22 in het datacenter,
naast de NAS'en `rs815p-1`/`-2`. De service, de offline pijplijn en GPT-OSS-120B
draaien daar nu. Daarnaast is de landelijke onboarding (342 gemeenten) gegroeid tot
**~21 GB aan indexen** en **~419 GB aan crawl-data en PDF's**. Er stond ook een lokale
kopie van die crawl-data van 419 GB op de kleine systeemschijf, naast de NAS.

## 2. Besluit

- **Host:** `c4130-4xp100`, systemd `--user`-unit `gemeente-search`, poort 8905.
  LLM = GPT-OSS-120B op dezelfde machine (`LLM_BASE_URL=http://127.0.0.1:8080/v1`).
- **Indexen** (`index.sqlite` + `embeddings.npy` per gemeente, plus `stats.sqlite`)
  staan op de **NVMe-schijf `/data`**, in `/data/gemeente-search/`. De paden in de
  app blijven gelijk via symlinks: `data/` en `stats.sqlite` wijzen daarheen. Regel
  van de host: *alle data op `/data`, nooit op de systeemschijf*.
- **Crawl-data en PDF's** staan uitsluitend op de NAS-share `gemeente-data`, via
  NFS gemount op **`/mnt/gemeente-live`**. `data/<slug>/crawl` is een symlink naar
  `/mnt/gemeente-live/<slug>/crawl`. De share wordt 's nachts gerepliceerd naar
  `rs815p-2`. De oude lokale kopie (`/mnt/nas-gemeente`, byte-voor-byte gelijk aan
  de NAS) is verwijderd, en `scripts/onboard_all.py` gebruikt nu `/mnt/gemeente-live`.
- **Backup van de indexen:** één handmatige kopie, geen nachtelijke job, naar de NAS
  in `gemeente-data/_index-backup/` (en daarmee ook op `rs815p-2`). Opnieuw draaien
  na een onboarding- of herindexeerronde met `search-index-backup.sh` (zie de infra-repo).

## 3. Gevolgen

### 3.1. Voordelen
* Eén bron voor crawl/PDF (de NAS, gerepliceerd); 419 GB vrij op de systeemschijf.
* Indexen lokaal op NVMe, dus snel (SQLite over NFS is traag en foutgevoelig).
* Een defecte schijf in de c4130 kost geen dagen herbouwen: de indexen staan als
  backup op de NAS.

### 3.2. Nadelen
* Ingest en onboarding lezen de crawl-data over NFS. Dat werkt, maar is trager dan
  lokaal lezen.
* De indexbackup is handmatig. Na een nieuwe onboardingronde moet iemand eraan
  denken hem opnieuw te draaien.

## 4. Overwogen alternatieven
* **Lokale crawl-kopie op `/data` houden:** sneller voor ingest, maar een tweede
  kopie die kan afwijken van de NAS. Afgewezen.
* **Nachtelijke indexbackup:** afgewezen; een losse backup volstaat, want de indexen
  veranderen alleen bij een onboarding.

## 5. Referenties
* [ADR-014](ADR-014-verhuizing-naar-c4130.md) (voorganger, c4130-4xv100)
* Infra-documentatie van de eigenaar (privé): opslag, NAS-replicatie, schijfindeling c4130
