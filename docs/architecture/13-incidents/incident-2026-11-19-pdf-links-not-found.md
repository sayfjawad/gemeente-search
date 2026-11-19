# Incident 2026-11-19: alle PDF-bronlinks geven `{"detail":"not found"}`

- **Datum & duur**: gemeld 2026-11-19, dezelfde dag opgelost. Vermoedelijk kapot
  sinds 2026-09-25 (~8 weken); het begin is afgeleid uit bestandsdata, niet gemeten.
- **Impact**: bij alle 342 gemeenten gaf elke geciteerde PDF
  (`/pdf/<slug>/<sha>.pdf#page=N`) en elk paginabeeld (`/pdf-image/...`) een 404.
  Zoeken en RAG-antwoorden werkten gewoon door (de index staat lokaal), dus de site
  leek gezond. Geen dataverlies: alle 176.035 geïndexeerde PDF's stonden op de NAS.
- **Oorzaak**: `data/<slug>/crawl` en `data/<slug>/pdfs` zijn symlinks naar de
  NAS-data. Bij de verhuizing naar de GPU-server stond die data eerst als lokale
  rsync-kopie (`/mnt/nas-gemeente`); op 2026-09-25 werd de NFS-mount
  `/mnt/gemeente-live` de bron. De `crawl`-links zijn toen omgezet, de `pdfs`-links
  niet, en daarna is de lokale kopie verwijderd. `pdf_file()` geeft voor een
  ontbrekend bestand bewust een 404, dus er was geen foutmelding of crash.
- **Oplossing / mitigatie**: alle 342 `pdfs`-links omgezet naar
  `/mnt/gemeente-live/<slug>/pdfs` (atomair met `ln -sfn` + `mv -T`, geen herstart
  nodig). Daarna een volledige controle: elk PDF-bestand uit elke `index.sqlite`
  bestaat op schijf, en een echte `/pdf/...`-fetch geeft 200/206.
- **Vervolgacties**:
  - De infra-healthcheck controleert nu dat alle `crawl`/`pdfs`-links naar
    `/mnt/gemeente-live` wijzen en dat er geen enkele dangling link is, plus
    (optioneel, ~45 s) dat elk gelinkt bestand bestaat. Zie
    [monitoring](../09-operations/monitoring.md).
  - Regel: verwijder of verplaats een datamap pas nadat `find data -xtype l` leeg
    is en het oude pad nergens meer voorkomt.
  - `scripts/onboard_all.py` gebruikt al `NAS_ROOT = /mnt/gemeente-live`, dus
    nieuwe gemeenten krijgen meteen de juiste links.
