# Kosten & schaling

## Kostmodel

Het systeem heeft **geen per-token kosten** (de LLM draait lokaal op de gx10)
en **geen per-request kosten** van een vector-DB of externe API. De kosten
zijn kapitaal- en beheerkosten:

| Component | Kostenpost |
|---|---|
| gx10-node | aanschaf + stroom (eenmalig, gedeeld) |
| GPU-node (Z8) | bestaand, gedeeld |
| Edge-VPS | vaste maandkosten, gedeeld |
| Schijf | opslag van PDF's + indexen (zie schaling hieronder) |
| Beheer | tijd van de beheerder voor onboarding |

## Schijfkosten per gemeente

De dominante kost is de opslag van de gedownloade PDF's (`data/<slug>/pdfs/`),
niet de index of embeddings. Gemeten over 6 gemeenten (totaal ~15,4 GB):

| Gemeente | Inwoners (circa) | Grootte |
|---|---|---|
| Barendrecht | ~50k | 147 MB |
| Vijfheerenlanden | ~60k | 217 MB |
| IJsselstein | ~33k | 1,4 GB |
| Houten | ~50k | 1,5 GB |
| Nieuwegein | ~65k | 4,1 GB |
| Utrecht | ~370k | 8,4 GB |

**Gemiddeld ~2,6 GB, mediaan ~1,4 GB per gemeente.** De spreiding is groot en
wordt vooral bepaald door het volume aan downloadbare PDF's (raadsstukken,
verordeningen, beleidsdocumenten), niet door inwonertal.

### Extrapolatie naar alle Nederlandse gemeenten (~342)

| Klasse | Aantal (schatting) | GB/gemeente | Subtotaal |
|---|---|---|---|
| Kleine gemeenten | ~300 | 0,2–1,5 | 60–450 GB |
| Middelgrote gemeenten | ~30 | 1,5–4 | 45–120 GB |
| Grote steden | ~10 | 4–20 | 40–200 GB |
| **Totaal** | **~342** | | **~150–770 GB → orde 0,5–1 TB** |

**Conclusie**: alle gemeenten onboarden kost ruwweg **0,5 tot 1 TB schijf**,
gedomineerd door PDF's. De index + embeddings zijn daar een kleine fractie
van (tientallen tot honderden MB per gemeente).

## Waar de echte bottleneck zit

Niet de schijf, maar het **in-memory ontwerp** (ADR-003): bij ~342 gemeenten
zou één service alle corpora in het geheugen moeten houden of per request
moeten laden. Dat is de schaalvraag die de
[roadmap](../11-roadmap/netherlands-scaling.md) adresseert — met de GB-cijfers
als onderbouwing.
