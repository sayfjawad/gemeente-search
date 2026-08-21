# Designprincipes

Hoe de drivers en constraints zich vertalen in concrete, herhaalbare
ontwerpregels.

## P1 — Scheid corpora per gemeente

Elke gemeente heeft een eigen index (`data/<slug>/index.sqlite` en
`embeddings.npy`). Vragen worden nooit over gemeenten heen beantwoord. Dit
houdt antwoorden zuiver en maakt schalen per gemeente een kwestie van
onboarden.

## P2 — Data-driven configuratie boven code

Nieuwe gemeenten vereisen géén code: een entry in `municipalities.json`
(aliaslijst, optioneel `product_sitemap`, `raad_domain`, etc.) plus één
pipeline-run. De code leest uitsluitend het register.

## P3 — Herleidbaarheid door citaten, niet door vertrouwen

De system-prompt verplicht het taalmodel om elke bewering te annoteren met
`[n]` die verwijst naar een meegegeven bron. De UI benadrukt geciteerde
bronnen visueel en toont bij PDF's de pagina als beeld. Vertrouw het model
nooit blind.

## P4 — Fail-open naar volledigheid

Als retrieval geen sterke match vindt, stop dan niet: de agentic fallback
doorzoekt de site zelf en injecteert de topresultaten. Liever een poging met
een zwakkere bron dan een onterecht "weet ik niet".

## P5 — Budgetbeheer rond het contextvenster

Het contextvenster (n_ctx=4096) is de schaarse resource. Er geldt een
tekenbudget (`MAX_TOTAL_SOURCE_CHARS` ≈ 8200) en een bronnenplafond
(`MAX_SOURCES_IN_CONTEXT` = 16). Chunks worden begrensd (~1400 tekens), en de
prompt prioriteert de beste matches.

## P6 — Hergebruik wat werkt

De BGE-M3-embedding-setup, de GPU-retrieval-aanpak en de deploy-topologie zijn
bewezen in de zusterprojecten en worden bewust hergebruikt in plaats van
opnieuw uitgevonden. Zie
[influences.md](influences.md).

## P7 — Kwantificeer bewust, niet tot het randje

Modellen worden zo gekwantiseerd dat er 15–20 GB marge op de gx10 overblijft
(geen OOM bij context + KV-cache). "Zo klein mogelijk" is fout — zie
ADR-004 en de benchmark-lessen.
