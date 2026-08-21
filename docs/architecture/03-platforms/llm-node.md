# LLM-node — GPT-OSS-120B op de gx10

Dit is de kern van het antwoordgenereren. De keuze is beargumenteerd in
[ADR-004](../07-decision-records/ADR-004-gpt-oss-120b-llama-cpp.md) en berust
op de `gx10-llm-benchmarks`.

## Hardware: waarom dit zo belangrijk is

De gx10 (NVIDIA DGX Spark-klasse, ASUS Ascent GX10) heeft:

- **GB10 Grace Blackwell Superchip**, 128 GB unified memory (~124,5 GB GPU),
- ~**273 GB/s** geheugenbandbreedte,
- SM 12.1.

Inferentie op zo'n node is **memory-bandwidth-bound**: de tokens per seconde
zijn ruwweg `bandbreedte ÷ grootte-van-het-actieve-model-in-GB`. Daarom:

| Modeltype | Actief gewicht | Verwachte t/s |
|---|---|---|
| Dense 120B | ~120 GB | ~2 (onbruikbaar) |
| MoE (GPT-OSS-120B) | ~5,1 GB actief van 117 GB | ~50 |

**MoE wint op deze hardware omdat per token maar een klein deel van de
experts actief is.**

## Het gekozen model: GPT-OSS-120B

- **Herkomst**: OpenAI, Mixture-of-Experts, 5,1 B actief / 117 B totaal.
- **Kwantisatie**: `UD-Q4_K_XL`, ~**59 GB** op schijf — bewust met 15–20 GB
  marge op de 128 GB (context + KV-cache zonder OOM).
- **Inference-engine**: llama.cpp, geëxposeerd als OpenAI-compatible
  `/v1/chat/completions` op `100.64.x.x:8083`.
- **Benchmark**: perfecte antwoordscores én **53,4 tokens/s**.

## Configuratie in `app.py`

- `max_tokens = 1800`, `temperature = 0.2` (voorspelbaar, lage creativiteit).
- **`chat_template_kwargs: {enable_thinking: false}`** — essentieel: GPT-OSS
  is een reasoning-model dat anders zijn redenering in het `thinking`-blok
  stopt en een **lege `content`** teruggeeft. Zonder deze toggle breekt de
  applicatie.
- Normalisatie van CJK-haakjes naar ASCII zodat de `[n]`-citaten van het model
  betrouwbaar geparsed kunnen worden.

## Mogelijkheden en beperkingen

| Aspect | Mogelijkheid | Beperking |
|---|---|---|
| Nederlands | Sterk, coherent, citeert correct als de prompt het eist | Hallucinatie zonder bron blijft mogelijk |
| Snelheid | 53 t/s op eigen hardware, geen API-kosten | Latentie = bandbreedte / actief gewicht |
| Context | 4096 tokens (n_ctx) bruikbaar | Beperkt bronnen per antwoord (zie 05) |
| Reasoning | Zet logisch stappen | Moet via `enable_thinking:false` op "antwoordmodus" |
| Kwantisatie | 59 GB past met marge | Te ver kwantiseren kost kwaliteit |
| Privacy | Queries verlaten het netwerk niet (lokaal) | Beheerlast van model + gx10 |

## Overwogen alternatieven (benchmark)

- **Nemotron-3.5-Lightning-30B-A3B** (58,1 t/s, 35 GB): runner-up, ook MoE;
  vereist eveneens `enable_thinking:false`.
- **Gemma 4 31B**: perfecte scores maar slechts 6,4 t/s (dense) — afgevallen
  op snelheid.

Zie [05-cross-cutting-concerns/rag-and-context-window.md](../05-cross-cutting-concerns/rag-and-context-window.md)
voor hoe het contextvenster wordt beheerd.
