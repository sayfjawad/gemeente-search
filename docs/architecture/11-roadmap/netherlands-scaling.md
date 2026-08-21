# Schaling naar heel Nederland

De vraag: *wat kost het om alle Nederlandse gemeenten te onboarden, en wat
breekt er dan?*

## GB-inschatting per gemeente

Gemeten over 6 gemeenten (totaal ~15,4 GB, zie
[05-kosten](../05-cross-cutting-concerns/costs-and-scaling.md)):

- **Gemiddeld ~2,6 GB**, **mediaan ~1,4 GB** per gemeente.
- Dominant: de gedownloade **PDF's**, niet de index of embeddings.

## Extrapolatie naar ~342 gemeenten

| Klasse | Aantal (schatting) | GB/gemeente | Subtotaal |
|---|---|---|---|
| Kleine gemeenten | ~300 | 0,2–1,5 | 60–450 GB |
| Middelgrote gemeenten | ~30 | 1,5–4 | 45–120 GB |
| Grote steden | ~10 | 4–20 | 40–200 GB |
| **Totaal** | **~342** | | **~150–770 GB → orde 0,5–1 TB** |

**Schijf is dus geen blokkade**: ~0,5–1 TB is triviaal op moderne storage. De
index + embeddings zijn een fractie daarvan.

## Wat wél breekt bij ~342 gemeenten

1. **In-memory ontwerp (ADR-003)** — één service die alle corpora tegelijk in
   het geheugen houdt, schaalt niet naar honderden gemeenten. Oplossing:
   - **lui laden** per gemeente (index + embeddings pas inlezen bij de eerste
     query op die slug), of
   - **per-gemeente-service** / horizontaal sharden over meerdere workers.
2. **Embeddings-tijd** — het embedden van de gezamenlijke corpus kost GPU-tijd;
   bij ~342 gemeenten is dat een lange batch. Oplossing: incrementeel embedden
   (alleen nieuwe chunks), eventueel gedistribueerd.
3. **Crawl-tijd & beleefdheid** — 342 sites crawlen met concurrency 3 en
   delay 0,4 s is traag; maar parallelisatie over gemeenten (per-site
   concurrency) lost dat grotendeels op zonder beleefdheidsverlies per site.
4. **Register & alias-conflicten** — bij ~342 gemeenten groeit het
   aliasbeheer; het register blijft de single source of truth, maar kan een
   validatiestap gebruiken.
5. **Kwaliteitstoets per gemeente** — de steekproeftest per gemeente (runbook)
   wordt arbeidsintensief; een gedeelde evaluatie-set (roadmap fase 4) helpt.

## Aanbevolen volgorde

1. Fix eerst de corpus-switch (lui laden) — de enige échte blokkade.
2. Ga naar object-storage voor PDF's als de schijf op één node knelt.
3. Schaal crawlen door per-gemeente-parallellisatie, niet door de
   per-site-beleefdheid op te voeren.
4. Heroverweeg ADR-003 (vector-DB) pas als meettallen dat rechtvaardigen.

Zie [roadmap.md](roadmap.md) fase 3 voor de bijbehorende items.
