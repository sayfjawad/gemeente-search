# Randvoorwaarden (constraints)

Harde grenzen waarbinnen het ontwerp móét passen. Anders dan drivers zijn dit
niet-onderhandelbare feiten van de omgeving.

## C1 — Hardware: de GPU's zijn voor het taalmodel

- De productieserver heeft 4× V100-SXM2-32GB (Volta, sm_70), volledig in
  gebruik door de gedeelde LLM-dienst. Zie [ADR-016](../07-decision-records/ADR-016-qwen-op-c4130-via-vllm.md).
- Gevolg: de app embedt queries op de **CPU**, en bulk-embedding bij
  onboarding draait waar een GPU vrij is.
- Volta beperkt de modelkeuze tot engines en kwantisaties die sm_70 nog
  ondersteunen.
- Historisch (gx10, tot 2026-08): inferentie was geheugenbandbreedte-gebonden
  (~273 GB/s). Daarom won een MoE-model.

## C2 — Gedeelde venv en Python-omgeving

De venv wordt gedeeld met `lift-normen-search` (`.venv` is een symlink).
Bibliotheekversies zijn dus een gedeelde afhankelijkheid: een upgrade in het
ene project raakt het andere.

## C3 — Bij voorkeur geen gehoste LLM-API

De LLM draait op eigen hardware. Dat betekent geen per-token kosten en geen
burgervragen bij een externe provider, maar wel beheer van model en GPU's.
Een externe API (DeepSeek) is twee keer als tijdelijke overbrugging gebruikt
(ADR-013, ADR-016 §1). Dat blijft het terugvalpad, niet de standaard.

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

Alles draait onder één account met systemd `--user`. Productie is een kopie
van de repo, geen checkout. Er is geen CI/CD-pijplijn
of scheiding van rollen; de beheerder draait de pipeline handmatig.

Zie [01-architecture-principles/design-principles.md](design-principles.md)
voor hoe deze randvoorwaarden zich vertalen in ontwerpregels.
