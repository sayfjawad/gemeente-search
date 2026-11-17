# ADR: 017 - Hosting op de C4130 in het datacenter, brondata op de NAS, embeddings op CPU

* **Status:** Accepted
* **Datum:** 2026-09-25
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Tot september 2026 draaide de service als systemd `--user`-unit op de
GPU-werkstation (HP Z8) thuis ([ADR-010](ADR-010-deploy-topologie-hergebruikt.md)).
Daar speelden drie dingen:

* De landelijke uitrol (alle 342 gemeenten) bracht de crawl-data en PDF's op
  **~420 GB**, en de indexen + embeddings op **~21 GB**. Dat is te veel voor
  de lokale schijf.
* De Z8 is een ontwikkelmachine met een GPU met een instabiele PCIe-link.
  Dat is geen goede plek voor een publieke dienst.
* De nieuwe C4130 en de NAS's kregen een plek in het datacenter, met
  NAS-replicatie en een failover-script.

## 2. Besluit

* **Runtime**: `gemeente-search.service` (systemd `--user`, `:8905`) draait
  op de **C4130 in het datacenter**, naast de andere zoekapps en de gedeelde
  LLM-dienst ([ADR-016](ADR-016-qwen-op-c4130-via-vllm.md)). Deploy is een
  kopie van deze repo naar `~/git/gemeente-search`.
* **Data-indeling**:
  * `data/` → symlink naar lokale schijf (`/data/gemeente-search/data`) met
    per gemeente `index.sqlite` + `embeddings.npy` (snelle random reads bij
    het opstarten en bij queries).
  * `data/<slug>/crawl` en `data/<slug>/pdfs` → symlinks naar een
    NFS-mount van de NAS-share `gemeente-data` (groot, alleen nodig bij
    onboarding en voor PDF-rendering).
  * `stats.sqlite` staat naast `data/`, zodat herindexeren de
    gebruiksstatistieken niet wist.
* **Embeddings op CPU**: de vier V100's van de C4130 worden volledig door de
  LLM gebruikt. Query-embedding met BGE-M3 (één korte tekst per request)
  draait daarom op de CPU (`CUDA_VISIBLE_DEVICES` leeg of de GPU niet
  zichtbaar). Bulk-embedding bij onboarding (`build_index.py`) kan op elke
  machine met een GPU draaien. Het resultaat is gewoon een `.npy`-bestand.
* **Edge**: ongewijzigd. De publieke TLS-terminatie (nginx + certbot) staat
  op een aparte edge-VPS, die over het privé-mesh-VPN naar `:8905` proxyt.
* **Backup**: dagelijks een kopie van de indexen + `stats.sqlite` naar de
  NAS. De NAS-share wordt gerepliceerd naar een tweede NAS.

## 3. Consequenties

### 3.1. Voordelen

* Publieke dienst op datacenter-hardware, los van de ontwikkelmachine.
* Brondata schaalt mee met de NAS in plaats van met de lokale schijf.
* Onboarding en serving hoeven niet op dezelfde GPU te concurreren.

### 3.2. Nadelen

* De service hangt af van de NFS-mount voor PDF-pagina-afbeeldingen
  (`/pdf-image`, `/pdf`). Valt de NAS weg, dan werken de antwoorden nog, maar
  de PDF-weergave niet. Het NAS-failover-script remount en herstart de
  zoekapps.
* CPU-embedding maakt elke query een fractie trager (BGE-M3 is klein; in de
  praktijk ruim onder een seconde).
* Geen git-checkout in productie: de deploy is een kopie. De repo moet dus
  expliciet bijgehouden worden. Toen deze ADR werd geschreven, liep de repo
  bijna drie maanden achter op productie.

## 4. Alternatieven

1. **Op de Z8 blijven.** Verworpen: instabiele GPU-hardware, geen
   datacenter-voorzieningen, te weinig schijf.
2. **Alles op de NAS (ook `index.sqlite` / `embeddings.npy`).** Verworpen:
   opstarttijd en query-latency over NFS voor 342 indexen.
3. **Kubernetes-pod in het k3s-cluster.** Uitgesteld: kan later, maar de
   systemd-unit was de kleinste stap vanaf de bestaande situatie.

## 5. Referenties

* [ADR-009](ADR-009-brondata-niet-in-git.md) — brondata niet in git
* [ADR-010](ADR-010-deploy-topologie-hergebruikt.md) — oorspronkelijke topologie
* [`09-operations/deployment.md`](../09-operations/deployment.md)
