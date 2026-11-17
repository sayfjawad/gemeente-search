# ADR: 014 - Permanente verhuizing naar c4130-4xv100 (GPT-OSS-120B, 3× V100)

* **Status:** Superseded door [ADR-016](ADR-016-qwen-op-c4130-via-vllm.md)
* **Datum:** 2026-08-23
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

De DeepSeek-failover uit [ADR-013](ADR-013-deepseek-tijdelijke-failover.md)
was expliciet tijdelijk — met per-token kosten en een externe
netwerk-afhankelijkheid voor content die eerder bewust lokaal bleef. Op
2026-08-23 werd `c4130-4xv100` (scrib-r's productie-GPU-node, 4× V100-SXM2-32GB,
NVLink 300GB/s) heringericht: GPT-OSS-120B verhuisde daarheen, verdeeld over
3 van de 4 kaarten, met whisperx-transcriptie teruggeschaald naar 1
dedicated worker op de vierde kaart (zie scrib-r's eigen
[ADR-009](https://github.com/sayfjawad/scrib-r/blob/main/architecture/07-decision-records/ADR-009-c4130-gpt-oss-120b.md)
voor de volledige onderbouwing van die node-herinrichting). Dat maakte een
permanente, lokale vervanger beschikbaar voor `/api/ask`.

## 2. Besluit

`gemeente-search/.env` omgezet naar
`LLM_BASE_URL=http://100.64.x.x:8080/v1`, `LLM_MODEL=gpt-oss-120b` — zelfde
model als voorheen op gx10 (zie ADR-004), nu geserveerd vanaf `c4130-4xv100`
in plaats van gx10. Het DeepSeek-blok blijft uitgecommentarieerd in `.env`
staan als terugvalpad. Geen codewijziging nodig: `call_llm()` was al
generiek OpenAI-compatibel en had door ADR-013 al de retry-met-groter-budget-
bescherming tegen lege `content`.

**Correctie op een aanname uit ADR-004**: `chat_template_kwargs:
{enable_thinking: false}` is géén universeel GPT-OSS/harmony-mechanisme,
zoals ADR-004 impliceerde — het is de Qwen/Nemotron-conventie. Voor
GPT-OSS-120B's eigen harmony-formaat is het correcte mechanisme
`reasoning_effort` (`low`/`medium`/`high`) in het request-JSON, bevestigd
tijdens de migratie via een live test op de nieuwe c4130-endpoint
(`content` en `reasoning_content` netjes gescheiden, `reasoning_effort:
"low"` hield het antwoord kort zonder het volledige budget op te maken).
`gemeente-search` blijft voorlopig zonder `reasoning_effort` draaien — de
bestaande `enable_thinking`-vlag wordt door de llama.cpp-server simpelweg
genegeerd (onbekend veld, geen fout), en de ADR-013-retry vangt de
resterende gevallen op. Dit werkt, maar is niet de precieze, bedoelde manier
om het model aan te sturen; toevoegen van `reasoning_effort: "low"` is een
kleine, niet-doorgevoerde verbetering die de retry-noodzaak waarschijnlijk
grotendeels zou wegnemen (zie Vervolgacties).

## 3. Consequenties

### 3.1. Voordelen
* Geen per-token kosten meer, geen content die de tailnet verlaat.
* Zelfde modelkwaliteit als voorheen (GPT-OSS-120B, niet gedegradeerd).
* Live geverifieerd via `/api/ask`: correct geciteerd, feitelijk juist
  Nederlands antwoord.
* Deelt infrastructuur met scrib-r, `abo-ali-search`, en
  `wilders-search`/`yesilgoz-search` — één node om te onderhouden i.p.v.
  een eigen dedicated model per app.

### 3.2. Nadelen
* Nieuwe afhankelijkheid van `c4130-4xv100` en de tailnet-route ernaartoe
  (zelfde nadeel-vorm als gx10 in ADR-004 §3.2, nu een andere node).
  `llama`'s poort moest daarvoor gepubliceerd worden op het tailnet-IP
  (was compose-intern-only) — zie scrib-r ADR-009.
* Gedeelde node: drukte van andere apps (whisperx, `abo-ali-search`,
  wilders/yesilgoz) kan in theorie de latency voor `gemeente-search`
  beïnvloeden, hoewel de GPU's onderling wel geïsoleerd zijn (transcriptie
  op een aparte kaart).
* De `enable_thinking`-vlag in `.env`/`call_llm()` documenteert nu een
  mechanisme dat voor dit model niet meer klopt (zie Besluit) — nog niet
  opgeschoond.

## 4. Alternatieven

1. **DeepSeek permanent houden.** Verworpen — dat was nooit het plan, zie
   ADR-013 §1.
2. **Eigen dedicated kleiner model op de GPU-node (Ollama-patroon van
   zusterprojecten).** Verworpen: zwakkere Nederlandse kwaliteit dan
   GPT-OSS-120B, en de node was toch al beschikbaar voor het grote model —
   geen reden om kwaliteit in te leveren.

## 5. Referenties
* [ADR-004](ADR-004-gpt-oss-120b-llama-cpp.md) — oorspronkelijke
  modelkeuze (nu andere node)
* [ADR-013](ADR-013-deepseek-tijdelijke-failover.md) — de overbrugging die
  dit vervangt
* [`03-platforms/llm-node.md`](../03-platforms/llm-node.md) — bijgewerkte
  node-beschrijving
* scrib-r ADR-009 (`architecture/07-decision-records/ADR-009-c4130-gpt-oss-120b.md`
  in de `scrib-r`-repo) — volledige onderbouwing van de c4130-herinrichting
  zelf

## 6. Vervolgacties
* `reasoning_effort: "low"` toevoegen aan `call_llm()`'s request-body i.p.v.
  (of naast) de nu-onjuiste `enable_thinking`-vlag.
* `03-platforms/llm-node.md` en `.env.example` bijwerken zodra dat gebeurt,
  zodat de documentatie het daadwerkelijke sturingsmechanisme beschrijft.
