# Codeerconventies

## Algemeen

- **Python 3**, single-service monolith: houd modules klein en
  verantwoordelijk (crawl, raad, ingest, embed, api, muni).
- **Configuratie boven code** voor gemeente-specifieke zaken: alles via
  `municipalities.json`, niet hardcoded in modules.
- **Constanten expliciet** bovenaan `app.py` (LLM-URL, model, drempels,
  budgetten) — het zijn architectuur-parameters, geen magische getallen.

## Data & bestanden

- **Bronnen/PDF's/indexen nooit in git** (`.gitignore`: `data/*/pdfs/`,
  `embeddings.npy`, `index.sqlite`, `stats.sqlite`, `state.json`, `logs`).
- **Secrets in `.env`**, nooit gecommit.
- Corpus per gemeente onder `data/<slug>/`.

## HTTP & externe calls

- Beleefd crawlen: concurrency 3, delay 0,4 s, robots.txt respecteren (met
  de gedocumenteerde uitzondering voor raadsinformatie).
- Externe LLM-calls via de OpenAI-compatible client; normaliseer uitvoer
  defensief (bijv. CJK-haakjes → ASCII).

## Foutafhandeling

- Fouten in de pipeline moeten de pipeline hervatbaar laten (append-only
  `docs.jsonl`, `state.json`).
- De API geeft nette foutmeldingen als de LLM of een index ontbreekt, in
  plaats van een stacktrace naar de client.

## Documentatie

- Bij elke significante keuze: een **ADR** in
  `docs/architecture/07-decision-records/` (sjabloon volgen).
- Diagrammen in PlantUML onder `12-diagrams/`.
