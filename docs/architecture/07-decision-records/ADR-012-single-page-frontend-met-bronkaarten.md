# ADR-012: Single-page frontend met bronkaarten en PDF-pagina-afbeeldingen

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

De kernbelofte is herleidbaarheid: elk antwoord moet verifieerbaar zijn tegen
de bron. De UI moet dat afdwingen en zichtbaar maken, terwijl hij ook voor
niet-technische gebruikers prettig moet zijn. De vraag was hoe de frontend op
te zetten (framework vs. statisch) en hoe citaten/bronnen visueel te
presenteren.

## 2. Besluit

Een **single-page frontend** (`static/index.html`, vanilla JS — geen
framework), geserveerd door dezelfde FastAPI-service. Visualisatie van
bronnen via **bronkaarten** met `[n]`-nummerbadges, waarbij **geciteerde
bronnen** visueel gemarkeerd worden (accent aan de linkerrand). Voor
PDF-bronnen wordt de betreffende pagina als **afbeelding** getoond
(`/pdf-image/{slug}/{chunk_id}`). Thema (licht/donker) via CSS-variabelen met
`prefers-color-scheme`, en een expliciete AI-disclaimer.

## 3. Consequenties

### 3.1. Voordelen

* Geen buildstap, geen frontend-toolchain; de SPA wordt als statische asset
  meegeleverd door FastAPI — past bij het single-service-model.
* Bronkaarten met markering maken herleidbaarheid zichtbaar: de gebruiker ziet
  wélke bronnen het antwoord daadwerkelijk droegen.
* PDF-pagina-afbeeldingen lossen het "scan-PDF"-probleem op: ook slecht
  extraheerbare tekst is als beeld controleerbaar.

### 3.2. Nadelen

* Vanilla JS schaalt minder goed bij een complexere interactieve UI dan een
  framework; voor deze scope is dat geen bezwaar.
* Pagina-afbeeldingen vereisen dat de PDF's lokaal bewaard blijven (zie
  ADR-009) en dat chunk_id naar een pagina verwijst (per-pagina-chunking).

## 4. Alternatieven

1. **Vue/React + buildstap**: meer structuur bij groei, maar voegt een
   toolchain en build/deploy-stap toe die niet opweegt tegen de huidige
   eenvoud. Verworpen.
2. **Alleen tekstbronnen (geen afbeeldingen)**: simpeler, maar ondermijnt de
   verifieerbaarheid bij gescande PDF's. Verworpen.

## 5. Referenties

* [`static/index.html`](../../../static/index.html)
* [05-cross-cutting-concerns/source-citation.md](../05-cross-cutting-concerns/source-citation.md)
* [ADR-009: Brondata niet in git](ADR-009-brondata-niet-in-git.md)
