# Per-gemeente afwijkingen

Het `municipalities.json`-register (zie
[ADR-001](../07-decision-records/ADR-001-multi-gemeente-register.md)) bevat
naast de standaardvelden een aantal optionele per-gemeente velden waarmee een
gemeente afwijkt van de default crawl-/registratieconfiguratie. Deze pagina is
de actuele lijst van die afwijkingen, zodat een toekomstige aanpassing van de
crawler of het register ze kan blijven respecteren.

## Velden

| Veld | Betekenis |
|---|---|
| `skip_paths` | Regex-lijst (matcht op het pad) van URL's die de crawler moet overslaan |
| `product_sitemap` | Extra sitemap-URL voor de Digitaal-Loket-productcatalogus |
| `cdn_prefix` | CDN-tenant-prefix (Cuatro) waar de PDF-uploads staan |
| `raad_domain` | Domein van het raadsarchief (Notubiz `ris2`) |
| `notubiz_domain` | Notubiz-API-domein van het raadsarchief |
| `aliases` | Alternatieve zoektermen (kern-/plaatsnamen) voor de gemeente |

## Huidige afwijkingen

| Gemeente | Veld | Waarde | Reden |
|---|---|---|---|
| ijsselstein | `cdn_prefix` | `/ijsselstein13cb44/uploads/` | CDN-tenant voor PDF-uploads |
| ijsselstein | `raad_domain`, `notubiz_domain` | `ijsselstein.raadsinformatie.nl`, `ijsselstein.notubiz.nl` | raadsarchief (Notubiz) |
| vijfheerenlanden | `aliases` | Ameide, Everdingen, Hagestein, Hei- en Boeicop, Hoef en Haag, Kedichem, Leerbroek, Leerdam, Lexmond, Meerkerk, Nieuwland, Oosterwijk, Schoonrewoerd, Tienhoven aan de Lek, Vianen, Zijderveld | fusiegemeente: 16 kernen als zoekaliassen |
| utrecht | `skip_paths` | `^/nl/?$`, `^/nl/producten/?$` | Digitaal-Loket-hubs genereren eindeloze filter-URL's |
| utrecht | `product_sitemap` | `https://loket.digitaal.utrecht.nl/nl/sitemap.xml` | productcatalogus staat op een apart domein |
| barendrecht | `skip_paths` | `^/feed/`, `^/category/`, `^/tag/`, `^/author/`, `.*/page/\d+` | WordPress-feed/taxonomie/paginatie-traps |
| barendrecht | `raad_domain`, `notubiz_domain` | `barendrecht.raadsinformatie.nl`, `barendrecht.notubiz.nl` | raadsarchief (Notubiz) |
| enkhuizen | `skip_paths` | `^/kalender` | raads-agenda/activiteitenkalender (`gemeenteraad.enkhuizen.nl/kalender/…`) is een oneindige datum-archief-trap (zie ADR-015) |

## Conventie bij een nieuwe afwijking

1. Voeg het veld toe aan de gemeente-entry in `municipalities.json`.
2. Documenteer het in de tabel hierboven.
3. Is het een nieuwe *klasse* van trap/afwijking die meerdere gemeenten zal
   treffen? Overweeg dan een generieke laag in `crawl.py` plus een ADR (zoals
   [ADR-015](../07-decision-records/ADR-015-crawl-trap-verdediging.md)) in
   plaats van een `skip_paths`-regel.
