# Incidenten

- [2026-08-21: lege antwoorden ondanks correcte bronnen (DeepSeek)](incident-2026-08-21-deepseek-lege-antwoorden.md)
- [2026-08-23: onboarding-pipeline kan de live service niet herstarten](incident-2026-08-23-onboarding-restart-falen.md)
- [2026-11-19: alle PDF-bronlinks geven "not found" (vergeten symlinks na NAS-verhuizing)](incident-2026-11-19-pdf-links-not-found.md)

## Registratie-format

Als zich een incident voordoet, wordt hier per incident een bestand
aangemaakt (`incident-YYYY-MM-DD-<korte-naam>.md`) met:

- **Datum & duur**
- **Impact** (welke gebruikers/functies geraakt)
- **Oorzaak** (root cause)
- **Oplossing / mitigatie**
- **Vervolgacties** (voorkom herhaling; verwijs naar een ADR indien het
  ontwerp aangepast moet worden)

Bekende kwetsbaarheden die in de toekomst tot een incident kunnen leiden
staan gedocumenteerd in
[09-operations/monitoring.md](../09-operations/monitoring.md) en
[05-cross-cutting-concerns/error-handling-and-resilience.md](../05-cross-cutting-concerns/error-handling-and-resilience.md).
