# Randvoorwaarden (constraints)

Harde grenzen waarbinnen het ontwerp móét passen. Anders dan drivers zijn dit
niet-onderhandelbare feiten van de omgeving.

## C1 — Hardware: gx10 is bandbreedte-gelimiteerd

- NVIDIA GB10 Grace Blackwell Superchip, **128 GB unified memory** (waarvan
  ~124,5 GB naar GPU), ~**273 GB/s** geheugenbandbreedte, SM 12.1.
- Gevolg: inferentie is memory-bandwidth-bound. Een 120 GB-model dat volledig
  actief is, haalt maximaal ~273/120 ≈ 2 tokens/s; een 5 GB actief MoE-model
  haalt tientallen tokens/s. Dit is dé reden dat MoE wint.

## C2 — Gedeelde venv en Python-omgeving

De venv wordt gedeeld met `lift-normen-search`
(`/data/git/lift-normen-search/.venv`). Bibliotheekversies zijn dus een
gedeelde afhankelijkheid: een upgrade in het ene project raakt het andere.

## C3 — Geen gehoste LLM-API

De LLM draait lokaal (llama.cpp), niet bij een externe provider. Gevolg: geen
per-token kosten en geen datalek van queries, maar wél beheer van het model,
de kwantisatie en de geheugendruk op de gx10.

## C4 — Publieke gemeentelijke bronnen zijn niet uniform

- Sites verschillen van CMS (sommige met `product_sitemap`, andere niet).
- Raadsarchieven zitten op `raadsinformatie.nl`, maar robots.txt verschilt per
  gemeente en de Woo/Gemeentewet stelt daar eigen eisen (zie ADR-007).
- PDF's liggen deels op een CDN (`cuatro.sim-cdn.nl`) met eigen robots.txt.

## C5 — Auteursrecht en herpublicatie

Gedownloade PDF's en indexen blijven lokaal en worden **niet** in git
opgenomen of opnieuw gepubliceerd (ADR-009). De service toont alleen
fragmenten en pagina-afbeeldingen, met verwijzing naar de officiële bron.

## C6 — Eén beheerder, geen team

Alles draait onder één account met systemd `--user`. Er is geen CI/CD-pijplijn
of scheiding van rollen; de beheerder draait de pipeline handmatig.

Zie [01-architecture-principles/design-principles.md](design-principles.md)
voor hoe deze randvoorwaarden zich vertalen in ontwerpregels.
