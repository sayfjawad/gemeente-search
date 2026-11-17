# ADR-015: Crawl-trap verdediging — oneindige URL-ruimtes uitsluiten

* **Status:** Accepted
* **Datum:** 2026-08-25
* **Auteur:** Sayf (met Hermes)

## 1. Context en probleemstelling

Gemeentesites — en vooral hun raads-/subdomeinen — genereren in de praktijk
oneindige URL-ruimtes die een sitemap-first BFS-crawler laten vastlopen: elke
gevonden pagina voegt weer nieuwe URL's toe, waardoor de frontier nooit leeg
raakt en een gemeente urenlang in de onboarding blijft hangen. In augustus
2026 concreet gezien:

- **Facet-/filter-zoekpagina's** (`?searchbase=`/`?sp=`/`?f=`/`?freetext=`) —
  Aa en Hunze: 173k van 179k URL's; Heerde-nieuws-paginatie 68k van 70k.
- **TYPO3 Solr-facetten** (`tx_solr[...]`, taalwisselaar `languageswitch`) —
  Almere 104k, idem Apeldoorn/Delft/Leeuwarden/Best.
- **File-transfer-/secure-messaging-portalen** (Cryptshare e.d.) met
  `;jsessionid=`-URL's — Delft 217k, Apeldoorn 89k, Gennep 94k, Leeuwarden
  86k, Rijswijk 72k documenten, allemaal ruis.
- **Raads-agenda-/activiteitenkalenders** — Enkhuizen
  (`gemeenteraad.enkhuizen.nl/kalender/{jaar}/{maand}` plus doorlopende
  id's 999–5993): **~130k pagina's = 97% van de hele crawl**, terwijl de
  échte hoofdsite maar 2.541 pagina's telt. De crawl draaide uren door; de
  frontier ('14 URL's te gaan') werd nooit 0 omdat elke kalenderpagina de
  volgende maand/dag weer enqueuede. Veel van die pagina's zijn 404's
  ("Pagina niet gevonden") of navigatie-shells zonder content.
- **Raads-/registerportaal-queryparams** — Maashorst
  (`gemeenteraad.gemeentemaashorst.nl/Agenda/Document?documentId=&agendaItemId=`,
  `People/Details?categoryId=`, `subsidies…/Request/Details?regulationId=`):
  hetzelfde document/vergaderstuk verschijnt onder tientallen combinaties.
- **Digitaal-Loket-formulierflows** — Maashorst
  (`dloket.gemeentemaashorst.nl/{burger,bedrijf}/startform?id=…`):
  transactieformulieren zonder doorzoekbare content, traag JS-gerenderd.

Zonder afvangst produceert zo'n crawl een corpus dat voor ~97% uit ruis
bestaat, blokkeert het de onboarding-queue, en vervuilt het de zoekindex.

## 2. Besluit

`crawl.py` krijgt een gelaagde verdediging, allemaal gecontroleerd in één
centraal scopefilter (`fits_scope()`), zodat een trap-URL nooit de frontier
in komt — ongeacht of hij via de sitemap, link-discovery of een hervatte
`state.json` wordt aangeboden:

| Laag | Patroon | Doel |
|---|---|---|
| `SKIP_HOST` | `^(mijn\|afspraak\|formulieren\|…\|portal)\d*\.` | interactieve portal-/afspraak-/SSO-subdomeinen |
| `SKIP_HOST_PORTAL` | `^(crypt\|cryptshare\|bestand\|…\|fileshare)\d*\.` | file-transfer-/secure-messaging-portalen |
| `SESSION_PATH` | `;(jsessionid\|phpsessid)=…` | Java/PHP-sessietokens in het pad |
| `SKIP_EXT` / `SKIP_PATH` | extensies & `/(login\|…\|afspraak\|startform\|select-idp)` | binaries en formulier-/login-/formulierflow-paden |
| `TRAP_PARAMS` | `searchbase, sp, f, freetext, offset, page, …` | facet-/paginatie-queryparameters |
| `TRAP_PARAM_SUBSTR` | `tx_solr, languageswitch, nav_id, chash, searchtype` | TYPO3 Solr-/taalwisselaar-parameters |
| **`CALENDAR_TRAP`** | `/(kalender\|agenda)/\d` | raads-agenda-/activiteitenkalenders (nieuw) |
| `STRIP_QUERY_PARAMS` | `documentid, agendaitemid, categoryid, regulationid` | raads-/registerportaal-navigatieparameters strippen (dedupe) |

Daarnaast blijft het per-gemeente `skip_paths`-veld bestaan voor
gemeente-specifieke vallen die niet generiek te vangen zijn; de actuele lijst
staat in
[per-gemeente-afwijkingen](../03-platforms/per-gemeente-afwijkingen.md).

**`CALENDAR_TRAP` (nieuw, 2026-08-25)** matcht bewust alleen een losstaand
`/kalender/`- of `/agenda/`-segment gevolgd door een cijfer, zodat een
legitieme `/afvalkalender`-pagina (afvalophaalkalender) nooit wordt
uitgesloten.

## 3. Consequenties

### 3.1. Voordelen

* De frontier kan niet meer exploderen; een crawl termineert in plaats van
  urenlang ruis te verzamelen.
* Één centraal filter (`fits_scope()`) in plaats van verspreide checks.
* Generieke lagen beschermen álle gemeenten zonder per-gemeente configuratie;
  `skip_paths` blijft als ontsnappingsklep voor échte site-specifieke vallen.

### 3.2. Nadelen

* Heuristisch: een patroon kan een legitieme pagina uitsluiten als een
  gemeente een echte content-sectie onder `/kalender/` of `?filter=` heeft.
  `CALENDAR_TRAP` is daarom expres smal gehouden.
* Nieuwe trap-klassen vereisen een nieuwe laag + ADR-update; dit is bewust
  doorlopend onderhoud in plaats van een eenmalige oplossing.

## 4. Alternatieven

1. **Alleen per-gemeente `skip_paths`** (geen generieke lagen): zou de
   Enkhuizen-klasse per gemeente handmatig vereisen en pas na het eerste
   vastlopen ontdekt worden. Verworpen als primaire verdediging (blijft als
   ontsnappingsklep).
2. **Hard limiet op het aantal URL's per gemeente** (`MAX_PAGES`): stopt de
   crawl, maar markeert de gemeente niet compleet en laat de junk-URL's al in
   het corpus staan. Verworpen als enige maatregel.
3. **HTTP-status checken en 404's uitsluiten**: vangt de 404-kalenderpagina's,
   maar niet de "200 maar leeg/navigatie"-shells die dezelfde trap vormen.
   Verworpen als enige maatregel.

## 5. Referenties

* [`crawl.py`](../../../crawl.py)
* [ADR-006: Crawlstrategie](ADR-006-crawl-strategie.md)
* [per-gemeente-afwijkingen](../03-platforms/per-gemeente-afwijkingen.md)
