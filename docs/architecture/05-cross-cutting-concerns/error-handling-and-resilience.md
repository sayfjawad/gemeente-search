# Foutafhandeling & veerkracht

## Foutpaden en hoe ze worden afgehandeld

| Situatie | Gedrag |
|---|---|
| Geen sterke match in de index (score < 0.50) | Agentic fallback: site-zoek + fetch top-pagina's (ADR-005) |
| Fallback vindt óók niets | Het model antwoordt eerlijk dat het niet gevonden is, in plaats van te hallucineren |
| gx10-node onbereikbaar | Foutmelding naar de client; geen crash van de service |
| Reasoning-model retourneert lege `content` | Voorkómen door `enable_thinking:false` (ADR-004) |
| Crawl onderbroken | Hervatten via `data/<slug>/crawl/state.json` + append-only `docs.jsonl` |
| Dubbele documenten bij her-crawl | Deduplicatie op canonical URL in `ingest.py` |
| Service-crash | systemd `--user` herstart de unit automatisch |

## Veerkrachtprincipes

1. **Idempotente pipeline**: ingest en build_index kunnen herhaald draaien
   zonder schade (dedup, overschrijven van `.npy`).
2. **Fail-open naar volledigheid**: liever een zwakkere poging dan een
   onterecht "weet ik niet".
3. **Geen externe harde afhankelijkheid in het antwoordpad**: de enige externe
   call (LLM) is lokaal; retrieval is puur lokaal (GPU/in-memory).
4. **Onboarding is herstartbaar**: elke stap (crawl → raad → reference →
   ingest → embed → restart) is los uitvoerbaar en idempotent; zie
   [09-operations/onboarding-runbook.md](../09-operations/onboarding-runbook.md).

## Bewuste zwaktes

- Eén Uvicorn-worker: een trage LLM-call blokkeert gelijktijdige requests.
- Geen time-out-schaalvergroting of request-queue. Voor de beoogde
  demonstratie-belasting acceptabel; zie roadmap.
