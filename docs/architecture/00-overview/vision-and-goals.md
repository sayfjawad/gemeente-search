# Visie & doelen

## Visie

Eén toegankelijke zoekingang die de versnipperde informatie van *elke*
Nederlandse gemeente samenhangend, doorzoekbaar en **citeerbaar** maakt — in
gewone taal, met per bewering een bronverwijzing, en zonder dat de gebruiker
hoeft te weten in welke PDF of op welke site het antwoord stond.

## Doelen

1. **Herleidbaarheid boven relevantie.** Elk antwoord is terug te voeren op een
   letterlijk fragment uit een concrete bronpagina of PDF-pagina (niet alleen
   "iets dat erop lijkt").
2. **Volledigheid.** Als het antwoord niet in de index staat, probeert het
   systeem het via de site-eigen zoekmachine op te halen (agentic fallback)
   voordat het "weet ik niet" zegt.
3. **Multi-gemeente zonder code per gemeente.** Onboarden is één
   register-entry plus één pipeline-run; geen per-gemeente forks.
4. **Lage operationele kost.** Hergebruik van bestaande GPU/infra en de
   bewezen deploy-topologie van de zusterprojecten.
5. **Eerlijk over de AI.** De UI draagt een expliciete disclaimer dat
   antwoorden gegenereerd en niet-deterministisch zijn en geen juridische
   status hebben.

## Niet-doelen

- Geen vervanging van de gemeentelijke website of het officiële kanaal.
- Geen juridisch bindend advies.
- Geen gebruikersaccounts, personalisatie of audit-trail per gebruiker.
- Geen automatische her-crawl op schema (geen scheduler).

Zie [scope-and-boundaries.md](scope-and-boundaries.md) voor de volledige
afbakening.
