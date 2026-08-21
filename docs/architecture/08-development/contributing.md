# Bijdragen

## Werkwijze

Documentation-as-code, zelfde discipline als `odp-architecture`:

1. Werk op een feature-branch, niet direct op de hoofdbranch.
2. Houd de **nummering en structuur** van `docs/architecture/` intact.
3. **ADR verplicht** bij een significante architectuurkeuze — volg
   [het sjabloon](../07-decision-records/adr-template.md).
4. Diagrammen in PlantUML, bronbestanden in
   [12-diagrams/](../12-diagrams/).
5. Controleer relatieve links tussen documenten na een verplaatsing.

## Een nieuwe gemeente onboarden

Geen code, maar data + pipeline:

1. Voeg een entry toe aan `municipalities.json` (slug, naam, aliassen,
   optioneel `product_sitemap` / `raad_domain` / `skip_paths`).
2. Draai de pipeline (zie
   [09-operations/onboarding-runbook.md](../09-operations/onboarding-runbook.md)).
3. Verifieer met `/api/statistics`.

## Beoordelingscriteria voor een PR

- Klopt de documentatie met de code? (geen verouderde constanten of paden)
- Is er een ADR voor nieuwe beslissingen?
- Blijft de herleidbaarheid (citaten) intact?
- Respecteert nieuwe code het tekenbudget / contextvenster?
