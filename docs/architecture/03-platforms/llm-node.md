# LLM-node — GPT-OSS-120B op c4130-4xv100

Dit is de kern van het antwoordgenereren. De keuze voor GPT-OSS-120B is
beargumenteerd in [ADR-004](../07-decision-records/ADR-004-gpt-oss-120b-llama-cpp.md)
en berust op de `gx10-llm-benchmarks`. **De node zelf is sindsdien gewijzigd**:
oorspronkelijk gx10, sinds 2026-08-23 `c4130-4xv100` — zie
[ADR-013](../07-decision-records/ADR-013-deepseek-tijdelijke-failover.md) (de
tussenliggende DeepSeek-periode) en
[ADR-014](../07-decision-records/ADR-014-verhuizing-naar-c4130.md) (de
permanente verhuizing). Wat hieronder staat beschrijft de huidige
c4130-situatie; de gx10-hardwareparagraaf is ter historie bewaard onderaan.

## Huidige hardware: c4130-4xv100

`c4130-4xv100` (Dell PowerEdge C4130, Tailscale `100.64.0.13`) heeft:

- **4× NVIDIA Tesla V100-SXM2-32GB**, onderling verbonden met **NVLink,
  300 GB/s**,
- GPT-OSS-120B draait verdeeld over **3 van de 4 kaarten** (GPU 1, 2, 3) via
  llama.cpp's `--tensor-split`; de vierde kaart (GPU 0) is dedicated aan
  scrib-r's whisperx-transcriptie, bewust gescheiden om GPU-contentie tussen
  transcriptie en het taalmodel te vermijden (zie scrib-r's eigen
  ADR-009 voor de volledige afweging, inclusief een verworpen 4-kaarten-variant).
- Live gemeten doorvoer tijdens de migratie: **~102 tokens/s** (korte test,
  geen formele benchmark) — sneller dan de eerder gemeten 53,4 t/s op gx10,
  al is dat geen apples-to-appels vergelijking (andere hardware-klasse,
  geen herhaald benchmark op c4130 zelf).

## Het gekozen model: GPT-OSS-120B (ongewijzigd)

- **Herkomst**: OpenAI, Mixture-of-Experts, 5,1 B actief / 117 B totaal.
- **Kwantisatie**: `UD-Q4_K_XL`, ~**63 GB** op schijf (bestand:
  `gpt-oss-120b-UD-Q4_K_XL-00001/2-of-00002.gguf`, rechtstreeks van
  HuggingFace (`unsloth/gpt-oss-120b-GGUF`) naar c4130 gehaald, niet
  overgezet vanaf gx10).
- **Inference-engine**: llama.cpp, geëxposeerd als OpenAI-compatible
  `/v1/chat/completions` op **`100.64.0.13:8080`** (was `100.64.x.x:8083` op
  gx10) — bewust gepubliceerd op het tailnet-IP (niet `0.0.0.0`) zodat ook
  andere apps op het tailnet (`wilders-search`/`yesilgoz-search`) dezelfde
  node kunnen gebruiken.

## Configuratie in `app.py` — en een correctie op de oorspronkelijke aanname

- `max_tokens = 1800` (met een retry naar `6000` bij een lege,
  budget-uitgeputte respons — zie ADR-013), `temperature = 0.2`.
- **De `chat_template_kwargs: {enable_thinking: false}`-vlag uit ADR-004 is
  géén universeel GPT-OSS/harmony-mechanisme** — dat bleek pas tijdens de
  DeepSeek-periode (ADR-013) en is expliciet vastgelegd in ADR-014 §2. Het
  is de Qwen/Nemotron-conventie. Voor GPT-OSS-120B's harmony-formaat is het
  correcte sturingsmechanisme **`reasoning_effort`** (`low`/`medium`/`high`)
  als apart veld in het request-JSON — bevestigd via een live test tijdens
  de c4130-migratie (`reasoning_effort: "low"` hield het antwoord kort en
  `content` bleef gevuld). `gemeente-search` stuurt dit veld nog niet mee
  (open vervolgactie, zie ADR-014 §6); de bestaande `enable_thinking`-vlag
  wordt door de server simpelweg genegeerd, en de retry-logica vangt de
  resterende gevallen op waarin het model toch te veel denkt.
- Normalisatie van CJK-haakjes naar ASCII zodat de `[n]`-citaten van het
  model betrouwbaar geparsed kunnen worden.

## Mogelijkheden en beperkingen

| Aspect | Mogelijkheid | Beperking |
|---|---|---|
| Nederlands | Sterk, coherent, citeert correct als de prompt het eist | Hallucinatie zonder bron blijft mogelijk |
| Snelheid | ~102 t/s op c4130, geen API-kosten | Geen formele herhaalde benchmark op c4130 |
| Context | 4096 tokens (n_ctx) bruikbaar | Beperkt bronnen per antwoord (zie 05) |
| Reasoning | Zet logisch stappen | Correcte sturing is `reasoning_effort`, niet (meer verondersteld) `enable_thinking` |
| Kwantisatie | 63 GB past ruim binnen c4130's 3×32GB | Te ver kwantiseren kost kwaliteit |
| Privacy | Queries verlaten het tailnet niet (lokaal) | Beheerlast van model + c4130, nu gedeeld met meerdere apps |
| Gedeelde node | Eén node voor scrib-r, abo-ali-search, wilders/yesilgoz-search én dit project | Grotere blast radius bij een storing dan een dedicated node |

## Historie: gx10-hardware (2026-08-21 t/m 2026-08-23, gepensioneerd)

De gx10 (NVIDIA DGX Spark-klasse, ASUS Ascent GX10) had:

- **GB10 Grace Blackwell Superchip**, 128 GB unified memory (~124,5 GB GPU),
- ~**273 GB/s** geheugenbandbreedte,
- SM 12.1.

Inferentie op zo'n node is memory-bandwidth-bound: tokens per seconde zijn
ruwweg `bandbreedte ÷ grootte-van-het-actieve-model-in-GB`. GPT-OSS-120B
haalde daar (als MoE, ~5,1 GB actief van 117 GB) ~50 t/s. Verkocht
2026-08-24 — zie ADR-013/ADR-014 voor de aanleiding en opvolging.

### Overwogen alternatieven (oorspronkelijke gx10-benchmark, blijft relevant)

- **Nemotron-3.5-Lightning-30B-A3B** (58,1 t/s, 35 GB): runner-up, ook MoE;
  vereist eveneens `enable_thinking:false` (deze conventie klopt wél voor
  dit modelfamilie).
- **Gemma 4 31B**: perfecte scores maar slechts 6,4 t/s (dense) — afgevallen
  op snelheid.

Zie [05-cross-cutting-concerns/rag-and-context-window.md](../05-cross-cutting-concerns/rag-and-context-window.md)
voor hoe het contextvenster wordt beheerd.
