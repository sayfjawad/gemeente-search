# Roadmap

Verbeteringen, geordend van "hoge waarde, lage inspanning" naar "grote
architectuurverandering". Elke stap koppelt terug aan de drivers en
constraints in `01-architecture-principles/`.

## Fase 1 — Kwaliteit & volledigheid (korte termijn)

1. **Cross-encoder her-ranking** — een BGE-reranker over de top-N chunks om de
   selectie scherper te maken (zie
   [06-retrieval](../06-cross-cutting-concepts/retrieval-and-ranking.md)).
2. **Meer gemeente-types dekken** — het register uitbreiden voor gemeenten met
   andere CMS'en/raadsaanbieders (nu: sites met sitemap + Notubiz).
3. **Citaten ook bij fallback-bronnen verifiëren** — de fallback-injecties
   krijgen nu een korter fragment; herleidbaarheid daar versterken.
4. **Fijnere chunking** — semantische (kop-gebaseerde) in plaats van pure
   lengte-chunking voor HTML.

## Fase 2 — Robustheid & operatie (middellange termijn)

5. **Healthchecks & alerting** — een `/healthz`, plus alerting op schijfruimte
   en falende pipeline (zie
   [09-monitoring](../09-operations/monitoring.md)).
6. **Geplande her-crawl** — een scheduler (systemd timer of cron) die de
   corpora periodiek ververst in plaats van handmatig.
7. **Request-queue / meerdere workers** — de single-worker-blokkade opheffen
   voor betere gelijktijdigheid.
8. **Rate-limiting** op de publieke endpoint.

## Fase 3 — Schaal naar heel Nederland (lange termijn)

9. **Corpus-switching zonder herstart** — indexen lui laden per gemeente in
   plaats van alles bij start; of een per-gemeente-service. Zie
   [netherlands-scaling.md](netherlands-scaling.md).
10. **Opslag naar object-storage** — PDF's naar object-storage in plaats van
    lokale schijf, met luie download voor pagina-afbeeldingen.
11. **Vector-DB pas wanneer nodig** — overschakelen naar een vector-DB zodra
    de in-memory aanpak bij honderden gemeenten knelt (ADR-003 heroverwegen).

## Fase 4 — Product & vertrouwen

12. **Meer bronnen** — landelijke instanties (Omgevingsloket, Belastingdienst,
    Rijksoverheid) als gecureerde referenties uitbreiden.
13. **Feedback-loop** — gebruikers kunnen aangeven of een antwoord klopte;
    dat voedt toekomstige her-ranking/evaluatie.
14. **Evaluatie-set** — een set van vragen met verwachte antwoorden per
    gemeente, om regressie bij modelwissel te meten.

## Prioritering achteraf

De volgorde volgt de drivers: eerst herleidbaarheid (1, 3) en volledigheid
(2, 4), dan operationele last (5–8), dan schaal (9–11), en als laatste
product/vertrouwen (12–14).
