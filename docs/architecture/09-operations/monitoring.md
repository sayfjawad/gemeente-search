# Monitoring

## Wat er is

- **`/api/statistics`** — corpus-statistieken per gemeente (documenten,
  chunks, index-/embedding-grootte).
- **systemd-status** — `systemctl --user status gemeente-search.service`
  (uptime, herstarts).
- **Onboarding-mijlpalen** — e-mailnotificaties via `scripts/notify.py`.
- **Crawl-voortgang** — `state.json` (aantal bezochte URL's) en
  `docs.jsonl` (aantal geoogste documenten).

## Handmatige controles

| Vraag | Commando / bron |
|---|---|
| Draait de service? | `systemctl --user status gemeente-search` |
| Bereikbaar van buiten? | `curl https://<domein>/api/municipalities` |
| LLM-node bereikbaar? | `curl http://100.64.x.x:8083/v1/models` |
| Corpus van gemeente X compleet? | `curl localhost:8905/api/statistics` |
| Schijfgebruik | `du -sh data/*/` |

## Wat er (nog) niet is

- Geen gecentraliseerde metrics (Prometheus) of dashboards.
- Geen alerting bij falende pipeline of volle schijf.
- Geen query- of foutlog-analyse.

Deze beperkingen passen bij het single-beheerder-model. Verhardingen
(alerting op schijfruimte, healthchecks, een licht metrics-endpoint) staan op
de [roadmap](../11-roadmap/roadmap.md).
