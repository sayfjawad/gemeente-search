# Observability & statistieken

## Endpoint

`/api/statistics` geeft per gemeente inzicht in het corpus: aantal documenten,
chunks en de grootte van de index/embeddings. Bedoeld om na een onboarding te
verifiëren dat de pipeline compleet heeft gedraaid.

## Onboarding-mijlpalen (e-mail)

`scripts/notify.py` verstuurt via TransIP SMTP een e-mail op mijlpalen
(crawl klaar, raadsarchief klaar, index gebouwd, service herstart). Zo is het
onboarden van een gemeente te volgen zonder op de node te zitten.

## Logging & foutafhandeling

- De crawler is **hervatbaar**: `state.json` houdt de crawl-voortgang bij,
  `docs.jsonl` is append-only; een onderbroken crawl hervat waar hij stopte.
- `ingest.py` dedupliceert op canonical URL, zodat een her-draai niet
  dubbelt.
- De LLM-call normaliseert uitvoer en heeft een foutpad; de service geeft een
  nette foutmelding terug als de gx10-node onbereikbaar is.

## Wat er (nog) niet is

- Geen gecentraliseerde metrics (Prometheus o.i.d.) of dashboards.
- Geen alerting.
- Geen query-logging voor analyse.

Dit past bij het single-beheerder-model; uitbreiding staat op de
[roadmap](../11-roadmap/roadmap.md).
