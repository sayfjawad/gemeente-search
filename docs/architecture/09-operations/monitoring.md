# Monitoring

## Wat er is

- **`/api/statistics`** — corpus-statistieken per gemeente (documenten,
  chunks, index-/embedding-grootte).
- **systemd-status** — `systemctl --user status gemeente-search.service`
  (uptime, herstarts).
- **`/stats`** — publieke pagina met het gebruik over tijd (uit `stats.sqlite`).
- **Onboarding-mijlpalen** — e-mailnotificaties via `scripts/notify.py`.
- **Live onboarding-monitor** — `scripts/monitor.py` (poort 8906) tijdens
  een landelijke uitrol.
- **Crawl-voortgang** — `state.json` (aantal bezochte URL's) en
  `docs.jsonl` (aantal geoogste documenten).

## Handmatige controles

| Vraag | Commando / bron |
|---|---|
| Draait de service? | `systemctl --user status gemeente-search` |
| Bereikbaar van buiten? | `curl https://<domein>/api/municipalities` |
| LLM-dienst bereikbaar? | `curl http://127.0.0.1:8080/v1/models` (op de GPU-server) |
| Corpus van gemeente X compleet? | `curl localhost:8905/api/statistics` |
| Schijfgebruik | `du -shL data/*/` (volgt de NAS-symlinks) |
| NAS-mount aanwezig? | `ls data/<slug>/pdfs/` geeft geen fout |
| Wijzen alle links naar de NAS-mount? | `readlink data/*/pdfs data/*/crawl \| sed 's#/[^/]*/[a-z]*$##' \| sort \| uniq -c` geeft één regel, `/mnt/gemeente-live`; `find data/*/pdfs data/*/crawl -maxdepth 0 -xtype l` is leeg |
| Bestaat elke geciteerde PDF? | per gemeente: elke `documents.filename` (doc_type `pdf`) uit `index.sqlite` staat in `data/<slug>/pdfs/`, en `curl -r 0-0 localhost:8905/pdf/<slug>/<bestand>` geeft 206 (zie incident 2026-11-19) |

## Wat er (nog) niet is

- Geen gecentraliseerde metrics (Prometheus) of dashboards.
- Geen alerting bij falende pipeline of volle schijf.
- Geen query- of foutlog-analyse.

Deze beperkingen passen bij het single-beheerder-model. Verhardingen
(alerting op schijfruimte, healthchecks, een licht metrics-endpoint) staan op
de [roadmap](../11-roadmap/roadmap.md).
