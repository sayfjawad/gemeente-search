# ADR: 016 - Taalmodel: zelf-gehoste Qwen3.8-27B via vLLM (na DeepSeek-overbrugging)

* **Status:** Accepted
* **Datum:** 2026-10-10
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

[ADR-014](ADR-014-verhuizing-naar-c4130.md) had GPT-OSS-120B (llama.cpp)
op `c4130-4xv100` als permanente LLM-node vastgelegd. Die machine is op
2026-09-11 gedecommissioneerd en verkocht. Er was daarna tijdelijk geen
lokale node met genoeg VRAM voor een groot model:

1. **2026-09-10 → 2026-10-10: DeepSeek API** (`deepseek-v4-pro`) als
   overbrugging, hetzelfde patroon als
   [ADR-013](ADR-013-deepseek-tijdelijke-failover.md). Dat werkte goed, maar
   had dezelfde nadelen als toen: per-token kosten, en vragen van burgers
   verlaten de eigen infrastructuur.
2. Een **nieuwe Dell PowerEdge C4130** (4× V100-SXM2-32GB) kwam in het
   datacenter in gebruik. Daar draait sinds 2026-10-10 een gedeelde
   LLM-dienst: **Qwen3.8-27B** (NVFP4-kwantisatie + DFlash2 speculative
   decoding) op **vLLM**, tensor-parallel over alle 4 kaarten, 262K context,
   OpenAI-compatibele API op `:8080`.

De vraag was welk model `gemeente-search` permanent gebruikt.

## 2. Besluit

`gemeente-search` gebruikt de **gedeelde Qwen3.8-27B-dienst op de C4130**:

```
LLM_BASE_URL=http://127.0.0.1:8080/v1   # app en model op dezelfde host
LLM_MODEL=qwen3.8-27b
```

Geen codewijziging nodig: `call_llm()` is generiek OpenAI-compatibel. De
bestaande `chat_template_kwargs: {enable_thinking: false}` is voor Qwen3
precies het **juiste** mechanisme om de reasoning-fase uit te zetten (zie de
correctie in ADR-014 §2: die vlag is de Qwen/Nemotron-conventie, niet die van
GPT-OSS). Het open vervolgpunt uit ADR-014 (`reasoning_effort` toevoegen) is
daarmee vervallen.

DeepSeek blijft het gedocumenteerde terugvalpad: alleen `.env` omzetten en de
service herstarten.

## 3. Consequenties

### 3.1. Voordelen

* Weer geen per-token kosten en geen burgervragen naar een externe provider.
* App en model op dezelfde host → loopback, geen netwerkhop.
* `enable_thinking: false` werkt nu daadwerkelijk zoals bedoeld; minder
  lege antwoorden en minder retries.
* 262K context: het model kan veel meer bronnen aan dan de 4096 tokens waar
  de prompt-budgetten oorspronkelijk voor ontworpen zijn.

### 3.2. Nadelen

* Gedeelde dienst: scrib-r, de andere zoekapps en de agents gebruiken
  hetzelfde model. Drukte daar raakt de latency hier.
* Kleiner model (27B dense) dan GPT-OSS-120B (MoE). In de interne benchmark
  scoort het goed op retrieval-taken, maar er is geen gemeente-specifieke eval.
* De prompt-budgetten in `app.py` (`MAX_TOTAL_SOURCE_CHARS = 8200`,
  `COMPARE_MAX_MUNIS = 8`) zijn nog afgestemd op `n_ctx=4096` en benutten de
  grotere context niet (zie Vervolgacties).

## 4. Alternatieven

1. **DeepSeek API permanent houden.** Verworpen: kosten en
   privacy-overwegingen, zie ADR-013 §1.
2. **Eigen dedicated model voor gemeente-search.** Verworpen: geen vrije
   GPU's; één goed onderhouden gedeelde dienst is eenvoudiger.
3. **GPT-OSS-120B terugzetten op de nieuwe C4130.** Verworpen ten gunste van
   één gedeeld model voor alle apps. Qwen3.8 ondersteunt bovendien tool-calling
   en vision, wat de andere consumenten nodig hebben.

## 5. Referenties

* [ADR-004](ADR-004-gpt-oss-120b-llama-cpp.md) — oorspronkelijke modelkeuze
* [ADR-013](ADR-013-deepseek-tijdelijke-failover.md) /
  [ADR-014](ADR-014-verhuizing-naar-c4130.md) — eerdere overbrugging en node
* [ADR-017](ADR-017-hosting-op-c4130-met-nas-data.md) — waar de app zelf draait
* [`03-platforms/llm-node.md`](../03-platforms/llm-node.md)

## 6. Vervolgacties

* Prompt-budgetten (`MAX_TOTAL_SOURCE_CHARS`, `MAX_SOURCES_IN_CONTEXT`,
  `COMPARE_MAX_MUNIS`) herzien voor de 262K-context.
* Default van `LLM_MODEL` in `app.py` (nu nog `gpt-oss-120b`) gelijktrekken
  met de productiewaarde.
