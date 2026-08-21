# ADR-011: Open toegang zonder authenticatie

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

De service ontsluit uitsluitend **publieke** gemeentelijke informatie. Er is
geen gebruikersdata, geen personalisatie en geen bevoordeelde content. Toch
moet er een bewuste keuze zijn over toegangscontrole: moeten gebruikers
inloggen, of is de service open toegankelijk?

## 2. Besluit

De service is **open toegankelijk zonder authenticatie**: geen login, geen
sessies, geen rate-limiting op de publieke endpoints. De beveiliging berust op
het feit dat er alleen publieke data in en uit gaat, plus het buiten git
houden van secrets (`.env`).

## 3. Consequenties

### 3.1. Voordelen

* Geen auth-laag, geen sessiebeheer, geen wachtwoord/account-flow te
  onderhouden — past bij het single-beheerder-model.
* Direct bruikbaar voor burgers (geen drempel).
* Klein aanvalsoppervlak: er valt weinig te misbruiken (geen PII, geen
  schrijfacties).

### 3.2. Nadelen

* Geen bescherming tegen misbruik (scrapen, flooden); een kwaadwillende kan
  de (gedeelde) GPU-node belasten.
* Geen audit-trail van wie wat vroeg.
* Geen netwerk-scheiding tussen gemeenten — alle corpora in één open service.

## 4. Alternatieven

1. **Basis-auth / token**: beschermt tegen bot-verkeer, maar voegt een
   sleutel-uitdeling en beheerdrempel toe voor burgers. Verworpen omdat de
   data publiek is.
2. **Per-gemeente API-key voor interne ontsluiting**: alleen relevant als de
   service naar gemeenten zelf zou worden aangeboden; nu niet aan de orde.

## 5. Referenties

* [05-cross-cutting-concerns/security-and-privacy.md](../05-cross-cutting-concerns/security-and-privacy.md)
* [00-overview/scope-and-boundaries.md](../00-overview/scope-and-boundaries.md)
* [`.env.example`](../../../.env.example)
