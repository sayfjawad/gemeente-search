# ADR-004: GPT-OSS-120B via llama.cpp op de gx10-node (reasoning-model)

* **Status:** Superseded door [ADR-016](ADR-016-qwen-op-c4130-via-vllm.md) (node eerder gewijzigd via [ADR-013](ADR-013-deepseek-tijdelijke-failover.md) / [ADR-014](ADR-014-verhuizing-naar-c4130.md))
* **Datum:** 2026-08-21
* **Auteur:** Sayf (met Claude)

## 1. Context en probleemstelling

Voor het RAG-antwoord is een Nederlandstalig taalmodel nodig dat accuraat
samenvat en strikt citeert. Er waren drie richtingen: een lokaal model via
Ollama op de GPU-node (het patroon van `lift-normen-search`), een externe
API (DeepSeek/OpenAI), of de beschikbare gx10-node die via llama.cpp een groot
model serveert. Een groot model is aantrekkelijk voor de kwaliteit van
Nederlandse juridische/bestuurlijke antwoorden.

## 2. Besluit

GPT-OSS-120B, geserveerd door llama.cpp op de **gx10-node**
(`http://100.64.x.x:8083/v1`, OpenAI-compatibel), bereikbaar over Tailscale.
Omdat GPT-OSS een *reasoning*-model is, stuurt `app.py` altijd
`chat_template_kwargs: {enable_thinking: false}` — anders gaat het hele budget
naar `reasoning_content` en blijft `content` leeg. Aanvullend: `max_tokens`
1800, `temperature` 0.2, en een brontekst-cap van ~8200 tekens (`fit_sources`)
om binnen de llama.cpp-context (`n_ctx=4096`) te blijven.

## 3. Consequenties

### 3.1. Voordelen

* 120B-modelkwaliteit voor Nederlandse antwoorden, zonder per-token API-kosten.
* Lokaal/privé: burger- en gemeente-inhoud verlaat de eigen infra niet.
* Scheiding van zorgen: het embedding-werk (GPU-node) en het LLM-werk
  (gx10-node) kunnen onafhankelijk schalen/herstarten.

### 3.2. Nadelen

* Extra node-afhankelijkheid: als de gx10-node (of de Tailscale-route ernaartoe)
  plat ligt, valt `/api/ask` terug op een foutmelding (zoeken via `/api/search`
  blijft werken).
* De reasoning-quirk vereist een specifieke instelling (`enable_thinking:false`);
  zonder die kennis leverde het model lege antwoorden op.
* De 4096-context is krap; bronteksten moeten worden ingekort, wat een
  afweging is tussen volledigheid en contextbudget.

## 4. Alternatieven

1. **Lokaal Ollama-model (bijv. qwen2.5:32b) op de GPU-node**: zelfde patroon
   als de zusterprojecten, maar een kleiner model levert zwakkere Nederlandse
   juridische antwoorden en concurreert met de embedding-workload om VRAM.
   Verworpen ten gunste van het 120B-model.
2. **DeepSeek/OpenAI API**: geen lokale afhankelijkheid en een sterk model,
   maar stuurt de volledige vraag + bronteksten naar een externe partij en
   introduceert per-token kosten. Verworpen.

## 5. Referenties

* [`app.py: call_llm()`](../../../app.py)
* [`app.py: fit_sources()`](../../../app.py)
* [`.env.example`](../../../.env.example)
