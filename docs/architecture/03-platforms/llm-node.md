# LLM-node — Qwen3.8-27B op vLLM (C4130)

Dit is de kern van het antwoordgenereren. Het huidige model en de huidige
node staan in [ADR-016](../07-decision-records/ADR-016-qwen-op-c4130-via-vllm.md).
De historie (GPT-OSS-120B op gx10 → DeepSeek → GPT-OSS-120B op
`c4130-4xv100` → DeepSeek → Qwen3.8-27B) staat onderaan.

## Huidige situatie (sinds 2026-10-10)

| Aspect | Waarde |
|---|---|
| Model | **Qwen3.8-27B**, NVFP4-kwantisatie + DFlash2 (speculative decoding) |
| Engine | **vLLM** (V100-build), tensor-parallel over 4× V100-SXM2-32GB |
| Context | 262K tokens |
| Endpoint | OpenAI-compatibel, `http://127.0.0.1:8080/v1` (app draait op dezelfde host) |
| Model-id | `qwen3.8-27b` |
| Gedeeld met | scrib-r, de andere zoekapps en de interne agents |

De LLM-dienst wordt buiten deze repo beheerd. `gemeente-search` is alleen
een consument: alles wat de app nodig heeft is `LLM_BASE_URL`, `LLM_MODEL`
en `LLM_API_KEY` in `.env`.

## Configuratie in `app.py` (`call_llm()`)

- `max_tokens = 1800`, met één retry op `6000` als het antwoord leeg terugkomt
  omdat het budget op is (zie ADR-013), `temperature = 0.2`.
- `chat_template_kwargs: {enable_thinking: false}`: bij Qwen3 zet dit de
  reasoning-fase uit, zodat het hele budget naar `content` gaat. Dat is
  precies wat de vlag hoort te doen. Bij GPT-OSS werd hij genegeerd (zie
  ADR-014 §2).
- CJK-haakjes worden genormaliseerd naar ASCII, zodat de `[n]`-citaten
  betrouwbaar geparsed worden.
- Prompt-budgetten (`MAX_TOTAL_SOURCE_CHARS = 8200`,
  `MAX_SOURCES_IN_CONTEXT = 16`, `COMPARE_MAX_MUNIS = 8`) zijn nog afgestemd
  op een context van 4096 tokens. Dat werkt, maar benut de 262K niet (open
  vervolgactie, ADR-016 §6).

## Terugvalpad

Valt de lokale dienst weg, dan kan elke OpenAI-compatibele provider worden
gebruikt. Het geteste pad is de DeepSeek API:

```
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-pro
LLM_API_KEY=<eigen key>
```

Dan de service herstarten. Let op: vragen van burgers gaan dan naar een
externe provider (zie [ADR-013](../07-decision-records/ADR-013-deepseek-tijdelijke-failover.md)).

## Mogelijkheden en beperkingen

| Aspect | Mogelijkheid | Beperking |
|---|---|---|
| Nederlands | Sterk, citeert correct als de prompt het eist | Hallucinatie zonder bron blijft mogelijk |
| Context | 262K tokens | App-budgetten benutten dit nog niet |
| Privacy | Vragen verlaten de eigen infrastructuur niet | Geldt niet in de DeepSeek-terugval |
| Kosten | Geen per-token kosten | Beheer van GPU-host en model (gedeeld) |
| Gedeelde node | Eén dienst voor alle apps | Drukte bij andere consumenten raakt de latency |

## Historie

| Periode | Model | Node | ADR |
|---|---|---|---|
| tot 2026-08-21 | GPT-OSS-120B (llama.cpp, `UD-Q4_K_XL`) | gx10 (GB10, 128 GB unified) | [ADR-004](../07-decision-records/ADR-004-gpt-oss-120b-llama-cpp.md) |
| 2026-08-21 → 08-23 | DeepSeek API | extern | [ADR-013](../07-decision-records/ADR-013-deepseek-tijdelijke-failover.md) |
| 2026-08-23 → 09-10 | GPT-OSS-120B (llama.cpp, 3× V100) | `c4130-4xv100` (verkocht 2026-09-11) | [ADR-014](../07-decision-records/ADR-014-verhuizing-naar-c4130.md) |
| 2026-09-10 → 10-10 | DeepSeek API (`deepseek-v4-pro`) | extern | [ADR-016](../07-decision-records/ADR-016-qwen-op-c4130-via-vllm.md) §1 |
| sinds 2026-10-10 | Qwen3.8-27B (vLLM) | nieuwe C4130 (datacenter) | [ADR-016](../07-decision-records/ADR-016-qwen-op-c4130-via-vllm.md) |

De oorspronkelijke modelkeuze kwam uit een benchmark op gx10.
GPT-OSS-120B (MoE, 5,1 B actief) haalde daar ~50 tokens/s. Een dens model van
vergelijkbare kwaliteit (Gemma 4 31B) haalde 6,4 t/s en viel af op snelheid.

Zie [05-cross-cutting-concerns/rag-and-context-window.md](../05-cross-cutting-concerns/rag-and-context-window.md)
voor hoe het contextvenster wordt beheerd.
