# Business-context

## Probleem

Gemeentelijke informatie voor burgers staat verspreid over meerdere, slecht
samenhangende bronnen:

- de **hoofdsite** van de gemeente (diensten, regelingen, procedures);
- **downloadbare PDF's** (verordeningen, beleidsstukken, raadsbesluiten);
- het **productaanbod van het Digitaal Loket** (bijv. Utrecht);
- het **gemeenteraadsarchief** op raadsinformatie.nl (vergaderingen,
  besluitenlijsten, moties, technische vragen);
- en soms **landelijke instanties** (Omgevingsloket / Bbl) waar de gemeente
  voor het echte antwoord naar doorverwijst.

Een burger die wil weten of een serre vergunningsvrij is, waar hij recht op
heeft, of wat een uittreksel kost, moet zelf door die bronnen ploegen — en
stuit daarbij op PDF's die niet doorzoekbaar zijn op "vraag"-niveau.

## Oplossing

`gemeente-search` haalt die bronnen gestructureerd binnen (crawlen), maakt ze
semantisch doorzoekbaar (RAG met BGE-M3-embeddings), en laat een taalmodel
(GPT-OSS-120B) er één praktisch, geciteerd antwoord van maken. Elk antwoord
verwijst per bewering terug naar de bronpagina of PDF-pagina, en toont voor
PDF-bronnen een afbeelding van de betreffende pagina — zodat de gebruiker niet
blind hoeft te vertrouwen op het taalmodel.

## Doelgroep

- **Burgers** die een gerichte gemeentelijke vraag hebben en een citeerbaar
  antwoord willen in plaats van een zoekresultatenlijst.
- **De beheerder** (eigenaar van dit account) die het systeem met minimale
  operationele last draait en eenvoudig nieuwe gemeenten onboardt.

## Positionering

Dit is een **single-user, openbare demonstratie/toepassing** — geen
multi-tenant SaaS, geen formele overheidsapplicatie. De kwaliteitseis is
herleidbaarheid (citaten) en volledigheid ("haal het op als het niet in de
index staat"), niet schaal naar miljoenen gebruikers. Zie
[scope-and-boundaries.md](scope-and-boundaries.md).
