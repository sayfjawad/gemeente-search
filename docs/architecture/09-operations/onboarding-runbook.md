# Onboarding-runbook (nieuwe gemeente)

Stap-voor-stap voor het onboarden van een gemeente. `onboard_barendrecht.sh`
is het referentie-script; pas slug/namen aan.

## 1. Register bijwerken

Voeg een entry toe aan `municipalities.json`:

```json
{
  "slug": "voorbeeld",
  "name": "Voorbeeldstad",
  "site_url": "https://www.voorbeeldstad.nl",
  "aliases": ["voorbeeldstad", "oude-naam"],
  "raad_domain": "raadsinformatie.voorbeeldstad.nl",
  "notubiz_domain": "voorbeeldstad.notubiz.nl"
}
```

Optioneel: `product_sitemap` (Digitaal Loket) en `skip_paths`.

## 2. Crawlen

```bash
python crawl.py --municipality voorbeeld           # hoofdsite (hervatbaar)
python crawl_raad.py --municipality voorbeeld      # raadsarchief (optioneel)
python scripts/add_reference.py --municipality voorbeeld   # gecureerde referenties (optioneel)
```

## 3. Indexeren & embedden

```bash
python ingest.py --municipality voorbeeld          # dedup + chunk → index.sqlite
python build_index.py --municipality voorbeeld     # BGE-M3 → embeddings.npy
```

## 4. Herstart & verifieer

```bash
systemctl --user restart gemeente-search.service
curl localhost:8905/api/statistics | jq '."voorbeeld"'
```

Controleer: aantal documenten/chunks > 0, index- en embeddings-grootte
plausibel.

## 5. Test

Stel een steekproefvraag via de UI of `/api/ask` en controleer dat het
antwoord bronnen citeert.

## Mijlpalen-notificaties

`scripts/notify.py` mailt bij mijlpalen (crawl klaar, raadsarchief klaar,
index gebouwd, service herstart) via TransIP SMTP — zie
[05-cross-cutting-concerns/observability-and-statistics.md](../05-cross-cutting-concerns/observability-and-statistics.md).

## Foutherstel

- **Crawl onderbroken**: herstart `python crawl.py --municipality <slug>`;
  `data/<slug>/crawl/state.json` hervat de voortgang.
- **Dubbelen**: `ingest.py` dedupliceert op canonical URL.
- **Te grote PDF-set**: controleer `skip_paths` en het CDN-robotsbeleid.
