# ADR-007: Raadsinformatie-crawl met bewuste robots.txt-uitzondering

* **Status:** Accepted
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Het gemeenteraadsarchief (vergaderstukken, besluitenlijsten, moties, technische
vragen) leeft op `<slug>.raadsinformatie.nl`, een Notubiz-"ris2"-applicatie.
Deze content is wettelijk openbaar (Gemeentewet / Woo), maar de `robots.txt`
van die host geeft een `Disallow` af — gericht op zoekmachines, niet op een
login-muur. Zonder dit archief mist de index precies het soort formele,
beslissende content waar burgers vragen over stellen.

## 2. Besluit

`crawl_raad.py` crawlt het raadsarchief toch, maar:
- alleen wat **publiek server-gerenderd** is (sitemap, vergaderpagina's,
  besluitenlijsten, module-lijsten, document-PDF's);
- **niet** de JS-geladen agenda-items/attachments (die zitten achter een
  per-pagina nonce en een "members"-permissie);
- **polite**: begrensde concurrency (default 4) en een delay (0,3 s).

## 3. Consequenties

### 3.1. Voordelen

* Volledigheid: raadsbesluiten en formele stukken zijn doorzoekbaar en
  citeerbaar — precies de content die "heeft de raad hier iets over besloten?"
  kan beantwoorden.
* Wettelijk openbare informatie wordt toegankelijker gemaakt.

### 3.2. Nadelen

* Negeert een robots.txt-directive — bewust en beargumenteerd (openbaarheid bij
  wet), maar het is een normafwijking die gedocumenteerd en verdedigbaar moet
  blijven.
* De nonce-gated agenda-items worden gemist (de bijlagen bij een vergadering
  zijn niet allemaal server-gerenderd), dus het archief is niet 100% compleet.

## 4. Alternatieven

1. **robots.txt respecteren**: verliest het hele raadsarchief — onacceptabel
   voor de beoogde volledigheid. Verworpen.
2. **Notubiz JSON-API voor agenda-items**: technisch compleet, maar gated
   achter nonce/members-permissie en dus niet stabiel scrape-baar. Verworpen
   voor nu; kan later alsnog.

## 5. Referenties

* [`crawl_raad.py`](../../../crawl_raad.py)
