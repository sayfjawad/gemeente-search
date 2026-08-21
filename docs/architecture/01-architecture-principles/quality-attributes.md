# Kwaliteitsattributen

De kwaliteitseisen en hoe het systeem ze realiseert, geordend als
prioriteitsladder.

## Primaire kwaliteiten (leidend)

### 1. Herleidbaarheid (verifieerbaarheid)
- Elk antwoord: beweringen → `[n]`-citaten → concrete chunk → bronpagina of
  PDF-pagina(-afbeelding).
- Vragen kunnen niet over gemeenten heen "lekken".

### 2. Volledigheid
- Agentic fallback haalt ontbrekende informatie op voordat er wordt opgegeven.

### 3. Juistheid van de taal
- Meertalig embeddingmodel (BGE-M3) dat Nederlands goed dekt.
- Nederlandstalige system-prompt met expliciete citatieregels.
- Reasoning-model met thinking **uit** (anders leeg antwoord; zie ADR-004).

## Secundaire kwaliteiten (belangrijk, niet leidend)

### 4. Performance / latentie
- Retrieval is sub-seconde (in-memory matrixproduct op GPU).
- LLM-inferentie is de bottleneck: tientallen tokens/s, beperkt door
  bandbreedte. Voor een antwoord van ~250 tokens enkele seconden.

### 5. Schaalbare onboardbaarheid
- Nieuwe gemeente = register-entry + pipeline, geen code. Doorlooptijd
  minuten tot uren (crawl), afhankelijk van sitegrootte.

### 6. Beschikbaarheid
- systemd `--user` herstart de unit bij crash; state.json en docs.jsonl maken
  de crawl hervatbaar; geen single point of failure in een externe API (LLM
  is lokaal).

## Tertiaire kwaliteiten (bewust beperkt)

### 7. Schaal naar gelijktijdige gebruikers
- Eén Uvicorn-worker, in-memory state per gemeente. Gebouwd voor
  enkelvoudige/demonstratie-belasting, niet voor miljoenen hits. Zie
  [11-roadmap](../11-roadmap/roadmap.md) voor het schaalpad.

### 8. Beveiliging in de klassieke zin
- Geen authenticatie (open toegang, ADR-011), geen gebruikersdata. Het
  beveiligingsmodel is: publieke data in, publieke antwoorden uit, secrets
  buiten git.
