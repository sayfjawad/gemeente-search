# ADR: 013 - Tijdelijke failover naar DeepSeek API (gx10-verkoop)

* **Status:** Superseded door [ADR-014](ADR-014-verhuizing-naar-c4130.md)
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

De gx10-node waarop GPT-OSS-120B draaide (zie [ADR-004](ADR-004-gpt-oss-120b-llama-cpp.md))
werd verkocht op 2026-08-24. Van alle apps die van gx10 afhankelijk waren
bleek na audit alleen `gemeente-search` een echte productie-afhankelijkheid
te hebben (`LLM_BASE_URL=http://100.64.x.x:8083/v1`). Er was op het moment
van de verkoop nog geen vervangende GPU-node ingericht — `/api/ask` mocht
niet zonder LLM komen te zitten terwijl `/api/search` (puur retrieval)
gewoon door moest blijven werken.

## 2. Besluit

`gemeente-search/.env` (gitignored) tijdelijk omgezet naar DeepSeek's
OpenAI-compatibele API (`LLM_BASE_URL=https://api.deepseek.com/v1`,
`LLM_MODEL=deepseek-v4-pro`) in plaats van gx10. Geen codewijziging nodig
voor de omzetting zelf — `call_llm()` deed al een generieke
OpenAI-compatibele POST. Wel bleek tijdens deze periode een reëel probleem:
DeepSeek negeert de llama.cpp-specifieke `chat_template_kwargs:
{enable_thinking: false}`-vlag en kan het volledige `max_tokens`-budget
opmaken aan `reasoning_content` bij een dubbelzinnige/tegenstrijdige
brondataset (`finish_reason: "length"`, lege `content`, ondanks correct
gevonden en geciteerde bronnen) — gereproduceerd op een vraag over
Schiermonnikoog's openingstijden. Dit trof mogelijk al langer een deel van de
live vragen op alle destijds al aangesloten gemeentes, niet alleen nieuwe.
Verholpen door één keer te herproberen met `max_tokens=6000` zodra de eerste
poging leeg terugkomt met `finish_reason=="length"`.

## 3. Consequenties

### 3.1. Voordelen
* Geen downtime van `/api/ask` tijdens de overgangsperiode.
* Sterk model (DeepSeek v4-pro), acceptabele kwaliteit als tijdelijke
  oplossing.
* De retry-met-groter-budget-fix maakt de applicatie robuuster tegen *elk*
  reasoning-model dat zijn budget kan opmaken aan denken — niet DeepSeek-
  specifiek, blijft ook na de omzetting naar ADR-014 nuttig als vangnet.

### 3.2. Nadelen
* Per-token kosten bij een externe partij, voor content (burger- en
  gemeente-informatie) die eerder bewust lokaal bleef (zie ADR-004 §3.1).
* Externe netwerk-afhankelijkheid toegevoegd aan een systeem dat daar
  bewust op vermeden had te bouwen.
* Het `enable_thinking`-mechanisme uit ADR-004 bleek niet universeel: het
  is een llama.cpp/Qwen-achtige conventie, geen garantie bij elke
  OpenAI-compatibele reasoning-provider — deze aanname stond niet expliciet
  in ADR-004, maar had dat wel moeten doen.

## 4. Alternatieven

1. **`/api/ask` tijdelijk uitschakelen, alleen `/api/search` laten werken.**
   Verworpen: onnodig verlies van functionaliteit terwijl een werkend
   extern alternatief (DeepSeek) direct beschikbaar was.
2. **Vervroegd een lokaal Ollama-model draaien op de GPU-node
   (`c4130-4xv100`).** Verworpen op dat moment: geen tijd om dat goed in te
   richten vóór de gx10-verkoopdatum; DeepSeek was de snelste veilige
   overbrugging. (Dit is exact wat later alsnog gebeurde, zie ADR-014 —
   alleen met GPT-OSS-120B in plaats van een kleiner Ollama-model.)

## 5. Referenties
* [ADR-004](ADR-004-gpt-oss-120b-llama-cpp.md) — de oorspronkelijke
  gx10-keuze
* [ADR-014](ADR-014-verhuizing-naar-c4130.md) — de permanente opvolger
* [`app.py: call_llm()`](../../../app.py) — de retry-met-groter-budget-fix
