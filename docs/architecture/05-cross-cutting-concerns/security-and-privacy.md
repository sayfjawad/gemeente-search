# Beveiliging & privacy

## Dreigingsmodel

De applicatie verwerkt **alleen publieke data**: gemeentelijke webpagina's en
openbare raadsstukken. Er is geen persoonsgebonden of vertrouwelijke data van
gebruikers, geen accounts en geen opslag van vraaggeschiedenis.

## Open toegang zonder authenticatie

Toegang is open (geen login). De afweging: de data is publiek en de kost van
een auth-laag weegt niet op tegen het risico. Zie
[ADR-011](../07-decision-records/ADR-011-open-toegang-zonder-authenticatie.md).

## Secrets

- `.env` bevat `SMTP_PASSWORD` en `LLM_API_KEY` (leeg — de LLM is lokaal).
- `.env` staat in `.gitignore` en wordt **nooit** gecommit.
- `LLM_API_KEY` is overbodig maar behouden voor OpenAI-compatible tools die
  een key verwachten.

## Gegevens van derden

- **Gedownloade PDF's en indexen blijven lokaal** en worden niet hergepubliceerd
  of in git opgenomen (ADR-009). Alleen fragmenten en (voor PDF's) losse
  pagina-afbeeldingen worden aan de gebruiker getoond, met verwijzing naar de
  officiële bron.
- **Crawl-beleefdheid**: concurrency 3, vertraging 0,4 s, robots.txt
  gerespecteerd (met één beargumenteerde uitzondering voor raadsinformatie,
  ADR-007).

## Netwerk

- Publiek verkeer eindigt op TLS (edge-VPS); intern verkeer loopt over
  Tailscale.
- De LLM draait lokaal; **queries verlaten het netwerk niet** naar een externe
  API-provider.

## Beperkingen (bewust geaccepteerd)

- Geen rate-limiting of anti-abuse op de publieke endpoint.
- Geen audit-trail van queries.
- Eén shared service zonder scheiding van corpora op netwerkniveau (alle
  gemeenten in één proces).

Zie [11-roadmap](../11-roadmap/roadmap.md) voor eventuele verhardingen.
