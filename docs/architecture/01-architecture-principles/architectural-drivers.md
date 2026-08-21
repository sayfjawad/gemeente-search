# Architectuurdrijvers (drivers)

De architectuur is gestuurd door vijf primaire krachten. Elke keuze in
`07-decision-records/` is uiteindelijk terug te voeren op één of meer van deze
drivers.

## D1 — Herleidbaarheid

Antwoorden moeten verifieerbaar zijn: elke bewering koppelt aan een letterlijk
fragment uit een concrete bron (pagina of PDF-pagina). Dit is de *hoogste*
prioriteit — een onjuist maar zelfverzekerd antwoord is erger dan "weet ik
niet".

**Gevolg:** citaten in de system-prompt verplicht, `[n]`-badges in de UI,
PDF-pagina-afbeeldingen als bewijs.

## D2 — Volledigheid

Als het antwoord niet in de index staat, moet het systeem het proberen op te
halen in plaats van te stoppen. Dit drijft de agentic fallback.

## D3 — Bandbreedte-gelimiteerde inferentie

De LLM draait op de gx10 (GB10, ~273 GB/s geheugenbandbreedte). Inferentie is
**memory-bandwidth-bound**: tokens/s ≈ bandbreedte / modelgrootte-in-GB. Dit
drijft de keuze voor MoE-modellen en voorzichtig kwantiseren. Zie
[03-platforms/llm-node.md](../03-platforms/llm-node.md).

## D4 — Multi-gemeente zonder per-gemeente-code

Nederland telt ~342 gemeenten. Handmatig per gemeente code schrijven schaalt
niet. Dit drijft het register-patroon (`municipalities.json` als single source
of truth) en de data-driven pipeline.

## D5 — Hergebruik boven nieuwbouw

Het account draait al meerdere zoekapps op dezelfde GPU-node, venv en
deploy-topologie. Nieuw bouwen dat het bestaande negeert, is verspilling en
onderhoudslast. Dit drijft het hergebruik van de lift-normen-search venv, de
BGE-M3-setup en de systemd/deploy-aanpak.

Zie [01-architecture-principles/constraints.md](constraints.md) voor de harde
randvoorwaarden die hieruit voortkomen.
