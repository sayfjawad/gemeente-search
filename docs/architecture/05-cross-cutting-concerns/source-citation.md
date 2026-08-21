# Bronvermelding & visuele aspecten

De kernbelofte van het systeem is *herleidbaarheid*. Dit document beschrijft
hoe bronvermelding en visualisatie die belofte waarmaken.

## Citaatmechanisme (tekstueel)

1. **System-prompt verplicht citaten**: het model moet elke bewering
   onderbouwen met `[n]`, waar `n` het volgnummer is van de bron in de prompt.
2. **Gestructureerde bronnen**: elke bron wordt als genummerd item aan de
   prompt toegevoegd (titel + fragment), zodat `[n]` eenduidig is.
3. **Normalisatie**: CJK-haakjes worden naar ASCII geconverteerd, zodat
   `[n]`-tokens van het model betrouwbaar terug te vinden zijn in de
   antwoordtekst.

## Visuele aspecten (UI)

`static/index.html` (vanilla JS, geen framework):

- **Licht/donker thema** — CSS-variabelen met `data-theme` en
  `prefers-color-scheme`; respecteert de systeemvoorkeur.
- **Gemeente-selector** — combobox met logo's, gekoppeld aan het register
  (`municipalities.json`).
- **Tabs** — "Vraag stellen" (RAG-antwoord) en "Zoeken" (directe chunk-hits).
- **Antwoordrendering** — markdown, met klikbare `[n]`-badges die naar de
  bijbehorende bronkaart scrollen.
- **Bronkaarten** — elke bron is een kaart met:
  - `[n]`-nummerbadge,
  - titel + URL (doorklikbaar),
  - het letterlijke fragment,
  - **geciteerde kaarten visueel gemarkeerd** (accent aan de linkerrand) zodat
    de gebruiker ziet wélke bronnen het antwoord daadwerkelijk droegen.
- **PDF-pagina-afbeelding** — voor PDF-bronnen wordt de betreffende pagina als
  afbeelding getoond (`/pdf-image/{slug}/{chunk_id}`), zodat de gebruiker de
  claim op de originele pagina kan verifiëren.
- **Disclaimer** — expliciete melding dat antwoorden door AI gegenereerd,
  niet-deterministisch en niet juridisch bindend zijn.

## Waarom dit zo is vormgegeven

- **Vertrouwen door bewijs, niet door autoriteit**: het antwoord *zegt* niet
  alleen wat, het *toont* waar het vandaan komt.
- **Pagina-afbeeldingen bij PDF's** lossen het "scan-PDF"-probleem op: tekst
  die slecht extraheert, is als beeld nog steeds controleerbaar.
- **Gemarkeerde vs. niet-gemarkeerde bronnen** maken eerlijk zichtbaar welke
  fragmenten het model werkelijk gebruikte versus welke alleen op de
  shortlist stonden.

Zie [ADR-012](../07-decision-records/ADR-012-single-page-frontend-met-bronkaarten.md)
voor de keuze van de UI-aanpak.
