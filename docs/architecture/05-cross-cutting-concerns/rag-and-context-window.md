# RAG-technieken & contextvenster

Hoe het systeem omgaat met de twee kernvragen van RAG: *wat haal je op*, en
*hoe pas je dat binnen het venster*.

## Contextvenster als schaarse resource

- `n_ctx = 4096` tokens bij de LLM (GPT-OSS-120B).
- Het venster wordt gedeeld door: system-prompt + de vraag + de bronnen + het
  gegenereerde antwoord. Bronnen zijn dus duur.
- Omdat `max_tokens = 1800` gereserveerd is voor het antwoord, blijft er voor
  de bronnen ruwweg de helft van het venster over.

## Hoe het systeem het budget beheert

Twee limieten, beide afgedwongen in `app.py`:

| Limiet | Waarde | Doel |
|---|---|---|
| `MAX_TOTAL_SOURCE_CHARS` | ~8200 tekens | harde bovengrens op de gezamenlijke brontekst in de prompt |
| `MAX_SOURCES_IN_CONTEXT` | 16 | bovengrens op het aantal bronnen |

Daarbovenop:

- **Chunkgrootte begrensd** op ~1400 tekens (HTML) of per PDF-pagina, zodat
  één bron niet het hele venster opslokt.
- **Selectie op score**: alleen de beste matches halen het budget; de rest
  valt af.
- **Citaat-efficiëntie**: de prompt vraagt om `[n]`-verwijzingen in plaats
  van lange bronteksten te herhalen; de UI koppelt `[n]` terug aan de
  bronkaart.

## RAG-flow in stappen

1. **Retrieve** — top-N chunks op cosine-similariteit (zie
   [03-platforms/embedding-and-retrieval.md](../03-platforms/embedding-and-retrieval.md)).
2. **Budgetteren** — bronnen sorteren op score, vullen tot het tekenbudget
   vol is of 16 bronnen bereikt zijn.
3. **Fallback** — is de beste score < 0.50, dan agentic fallback: zoek op de
   site, haal de top-pagina's op, injecteer die chunks (zie ADR-005).
4. **Generate** — system-prompt (Nederlands, citatieregels) + vraag +
   bronnen → LLM → antwoord met `[n]`.
5. **Renderen** — de UI markeert geciteerde bronnen en toont voor PDF's de
   pagina-afbeelding.

## Waarom géén langere context / geen her-ranking?

- **Langer venster is niet gratis**: op een bandbreedte-gelimiteerde node kost
  een groter venster lineair meer geheugen voor de KV-cache en vertraagt het
  de inferentie. 4096 is de bewuste afruil.
- **Geen cross-encoder her-ranking**: de corpus is klein en BGE-M3 scoort al
  goed; her-ranking voegt een tweede model + latentie toe zonder meetbare
  winst hier. Dit is een mogelijke roadmapverbetering (zie
  [11-roadmap](../11-roadmap/roadmap.md)).

Zie [06-cross-cutting-concepts/llm-concepts.md](../06-cross-cutting-concepts/llm-concepts.md)
voor de achterliggende concepten.
