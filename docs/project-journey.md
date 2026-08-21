# Projectjournaal — het avontuur van gemeente-search

Dit document is het *verhaal* achter de formele
[architectuurdocumentatie](architecture/README.md). Waar de architectuur het
"wat" en "waarom" per keuze vastlegt, beschrijft dit journaal **hoe we hier zijn
gekomen**: wat er is bereikt, welke problemen we onderweg tegenkwamen en wat dat
uiteindelijk heeft opgeleverd. Het is bedoeld als eerlijke terugblik — inclusief
de dingen die niet in één keer lukten.

## Samenvatting

Van één vraag ("kan ik een serre plaatsen in mijn tuin?") naar een
**multi-gemeente RAG-zoekmachine** die op dit moment **5 gemeenten** doorzoekbaar
maakt en vragen beantwoordt met geciteerde bronnen. Onderweg zijn we
tegen de grenzen aangelopen van het taalmodel, van crawlers op vier verschillende
CMS'en, en van semantische retrieval — en elke keer is daar een werkbare oplossing
uit gekomen. Het resultaat staat live op
[gemeente.multicode.nl](https://gemeente.multicode.nl).

---

## Wat hebben we bereikt

### 1. Een werkende, geciteerde vraag-en-antwoorddienst over gemeentelijke info

Een burger typt een vraag in gewone taal ("mag ik een serre plaatsen, mijn tuin
is 8×6 m en ik wil een serre van 6×4 m?") en krijgt één samenhangend Nederlands
antwoord terug waarin elke bewering is voorzien van een `[n]`-citaat naar de
exacte bronpagina of PDF-pagina van de gemeente. De bijbehorende PDF-pagina wordt
meteen als afbeelding getoond, zodat je niet blind hoeft te vertrouwen op een
taalmodel dat bedragen, termijnen of regels zou kunnen verzinnen.

### 2. Van één gemeente naar een multi-gemeente platform

Het begon als een pilot voor IJsselstein. De app is herbouwd tot een
**data-gedreven multi-gemeente systeem**: `municipalities.json` is het register
(slug, naam, logo, start-URL, zoek-URL, CDN-prefix, raadsarchief-domein), en elke
gemeente heeft zijn eigen gescheiden data in `data/<slug>/`. Onboarden van een
nieuwe gemeente is nu **één register-entry plus een pijplijn-run** (crawl → ingest
→ build_index), in plaats van code aanpassen. Zie
[ADR-001](architecture/07-decision-records/ADR-001-multi-gemeente-register.md).

### 3. Vijf gemeenten live, met gescheiden indexen

| Gemeente | Documenten (docs) | Bijzonderheden |
| :--- | ---: | :--- |
| **IJsselstein** | 2.012 | de oorspronkelijke pilot; Notubiz-raadsarchief + Cuatro-CDN |
| **Nieuwegein** | 2.191 | TYPO3; witte logo → `logo_bg`-tegel |
| **Vijfheerenlanden** | 789 | 1 site voor **16 dorpen/steden**, via `aliases` (Ameide t/m Zijderveld) |
| **Utrecht** | 5.355 | TYPO3 + het Digitaal Loket productaanbod (315 burgerproducten) |
| **Houten** | 1.857 | TYPO3/OpenGemeenten; zeer PDF-rijk (Woo-openbaarmakingen) |
| **Totaal** | **± 12.200** | Barendrecht is in onboarding (register klaar, index loopt) |

De Vijfheerenlanden-constructie is het vermelden waard: één gemeente bedient 16
dorpen/steden vanaf één website. In plaats van 16 losse indexen hebben we één
index met 16 `aliases`, zodat een inwoner van "Leerdam" gewoon "Leerdam" kan
kiezen en dezelfde data gebruikt.

### 4. Agentic fallback — "staat het niet in de index, haal het op"

Semantische retrieval kan zwak scoren (bijv. een vraag in een andere bewoording
dan de bron). In plaats van "geen antwoord" te geven, valt het systeem dan terug
op de **eigen zoekmachine van de gemeentesite** en haalt de beste pagina's live
op als `agentic`-bronnen. Het motto van de gebruiker werd letterlijk de
feature: *"als je iets niet vindt, dan moet het opgehaald worden van de gemeente
op agentic wijze."* Zie
[ADR-005](architecture/07-decision-records/ADR-005-agentic-fallback.md).

### 5. Gemeenteraadsarchieven ontsloten

Naast de hoofdsite wordt ook het **raadsarchief** gecrawld (moties,
besluiten, vergaderstukken). IJsselstein en Barendrecht draaien op Notubiz/
raadsinformatie.nl; Nieuwegein, Vijfheerenlanden en Houten draaien op **iBabs**
(`*.bestuurlijkeinformatie.nl`) — een ander platform waarvoor de crawler nog
moet worden gebouwd (open item).

### 6. Gecureerde referenties waar de gemeentesite tekortschiet

Sommige regels staan niet op de gemeentesite maar op landelijke portalen (zoals
het Omgevingsloket). Voor de serre-vraag — hét oorspronkelijke voorbeeld — is een
**gecureerd referentiedocument** toegevoegd met de vergunningsvrije-bouwregels,
zodat dat gat wél beantwoordbaar werd. Zie
[ADR-008](architecture/07-decision-records/ADR-008-curated-references.md).

### 7. Een volledige, gedisciplineerde architectuurdocumentatie

Het project heeft een ODP-stijl architectuurdossier gekregen (00–13): visie,
scope, principes, contextdiagram, platforms, cross-cutting concerns, **12 ADR's**
en PlantUML-diagrammen. Elke niet-triviale keuze is daarmee onderbouwd — niet
alleen "wat" er staat, maar ook "waarom" en "waarom niet anders".

---

## Problemen die we tegenkwamen (en hoe we ze oplosten)

| # | Probleem | Oorzaak | Oplossing |
| :-: | :--- | :--- | :--- |
| 1 | **Leeg antwoord** van het taalmodel | GPT-OSS-120B is een reasoning-model: zonder expliciete instelling gaat het hele token-budget naar intern redeneren (`reasoning_content`) en blijft `content` leeg. | Altijd `chat_template_kwargs: {"enable_thinking": false}` + `max_tokens ≥ 600` sturen (app gebruikt 1800). |
| 2 | **400 "exceeds context size"** bij rijke antwoorden | De gx10 llama.cpp-server meldt `n_ctx=4096`, ondanks `-c 16384` op de cmdline (vermoedelijk een GGUF-`context_length`-metadatum die clampt). Een agentic fetch met meerdere lange chunks duwde de prompt over de limiet. | `fit_sources()` met `MAX_TOTAL_SOURCE_CHARS=8200` budgetteert de brontekst; `AGENTIC_MAX_CHUNKS` verlaagd. (n_ctx verhogen is een open vervolgactie.) |
| 3 | **Citaties niet als "geciteerd" gemarkeerd / niet klikbaar** | GPT-OSS geeft citaties soms als full-width CJK-haakjes `【6】` / `［6］`; de ASCII-regex `\[...\]` herkende die niet. | Server-side normaliseren naar `[6]` + frontend-regex verbreed naar `[\[【［…\]】］]`. |
| 4 | **Crawler bleef steken** bij een `MAX_PAGES`-limiet | Een frontier-URL werd gedropt vóórdat hij verwerkt was (`pending` naar 0 terwijl er nog werk was), waardoor de crawl vroegtijdig stopte. | Fresh start zonder cap + de frontier-verwerking zo aangepast dat de limiet ná verwerking wordt toegepast. |
| 5 | **Dubbele documenten door http→https** | TYPO3-sitemaps listen vaak `http://` terwijl de site `https` serveert; zonder normalisatie werd elke pagina twee keer gecrawld (bijv. ~459 dubbele http-docs in het raadsarchief). | `canonicalize()`/`canon_url()` forceert http→https; ingest dedupt sowieso op canonieke URL. |
| 6 | **Quadro K2200 GPU (sm_50) niet ondersteund** | torch 2.8.0 vereist sm_70+; de K2200 wordt genegeerd. | Benigne waarschuwing — de app draait op een wél ondersteunde GPU. Gedocumenteerd, niets kapot. |
| 7 | **MuPDF XObject-waarschuwingen** bij ingest | Bepaalde PDF's bevatten verwijzingen naar ontbrekende XObject-resources. | Niet-fataal: tekst wordt alsnog geëxtraheerd; alleen logruis. |
| 8 | **robots.txt-quirks** | (a) Sommige TYPO3-sites (Houten) geven 500 op httpx' robots-fetch terwijl curl 200 geeft → crawler ging zonder robots verder. (b) Zie #5 (http-sitemaps). | `fetch_robots` retourneert `None` en de crawl gaat door; er glippen hooguit een paar `Disallow`'d wizardstappen in (eindige, kleine ruis). |
| 9 | **CMS-diversiteit** | Elke gemeente heeft een ander CMS: Cuatro (IJsselstein), TYPO3 (Nieuwegein/Utrecht/Houten), custom (Vijfheerenlanden), WordPress (Barendrecht). Raadsarchieven: Notubiz vs iBabs. | Per-gemeente config in `municipalities.json` (`cdn_prefix`, `search_url`, `skip_paths`, `product_sitemap`, `raad_domain`); iBabs-crawler is een open item. |
| 10 | **Eindeloze URL-parameters** op portal-host | Subdomeinen als `mijn.`/`afspraak.`/`digid.` genereren oneindig geparametriseerde URLs. | `SKIP_HOST`-regex sluit deze interactive/SSO-hosts uit vóór de crawl. |
| 11 | **De serre-vraag was niet beantwoordbaar** | De vergunningsvrije-bouwregels staan niet op de gemeentesite (verwijst naar omgevingsloket.nl). | Gecureerd referentiedocument met de landelijke regels (zie #6 hierboven). |
| 12 | **Agentic fetch: de site-zoekmachine leek onbereikbaar** | De Cuatro-zoekmachine is client-side JS tegen een interne Solr (`solr-slave.simsearch.nl`, privé-IP's); `?query=` gaf alleen "nog geen zoekresultaten". | Ontdekt dat de resultaten tóch server-rendered zijn via `/zoeken?trefwoord=<query>` — dus op te halen met httpx, geen browser nodig. |
| 13 | **Langdradige vragen scoren zwak** | BGE-M3 rankt korte trefwoorden goed, maar een lange natuurlijke vraag ("wat kost een paspoort in Utrecht") verdunt de sleutelterm en duwt de juiste pagina naar ~plek 10, buiten het char-budget. | Korte, schone queries raken hem top-3; een re-ranker / query-rewriting pass staat op de roadmap. |

---

## Wat dit heeft opgeleverd

- **Een live, bruikbare dienst** op [gemeente.multicode.nl](https://gemeente.multicode.nl) die
  vijf gemeenten dekt en burgers één geciteerd antwoord geeft in plaats van een
  doolhof aan pagina's.
- **Een herbruikbaar onboarding-proces**: één register-entry + één pijplijn-run
  (met e-mailmijlpalen via `scripts/notify.py`) maakt een nieuwe gemeente
  doorzoekbaar. Barendrecht is hiermee al in onboarding.
- **Een gedocumenteerde architectuur** met ADR-discipline, waardoor elke keuze
  navolgbaar is en volgende collega's niet opnieuw dezelfde kuilen hoeven te
  graven.
- **Een blauwdruk voor schaling naar heel Nederland**: de multi-gemeente
  architectuur, de CMS-playbook-kennis (Cuatro/TYPO3/custom/WordPress, Notubiz/
  iBabs) en de inschatting van kosten/opslag per gemeente liggen klaar (zie
  [11-roadmap/netherlands-scaling.md](architecture/11-roadmap/netherlands-scaling.md)).

---

## Ondersteunde gemeenten

De toepassing ondersteunt op dit moment de volgende **vijf** gemeenten:

- **IJsselstein**
- **Nieuwegein**
- **Vijfheerenlanden** (16 dorpen/steden: Ameide, Everdingen, Hagestein,
  Hei- en Boeicop, Hoef en Haag, Kedichem, Leerbroek, Leerdam, Lexmond, Meerkerk,
  Nieuwland, Oosterwijk, Schoonrewoerd, Tienhoven aan de Lek, Vianen, Zijderveld)
- **Utrecht**
- **Houten**

> **Beperkt door beperkte middelen.** De dienst is bewust beperkt tot deze
> gemeenten, omdat elke gemeente een eigen crawl-, indexeer- en onderhoudsinspanning
> vergt die met de huidige middelen maar voor een handvol gemeenten kan worden
> gedragen. Wil je dat jouw gemeente wordt toegevoegd, of wil je meedenken over
> hoe dit breder kan worden opgeschaald? Neem dan contact op met
> [stichtingduurzaamai.nl](https://stichtingduurzaamai.nl).

---

*Dit journaal is een momentopname en wordt bijgewerkt naarmate het project groeit.*
