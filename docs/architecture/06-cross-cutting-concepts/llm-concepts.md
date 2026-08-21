# LLM-concepten

De concepten die nodig zijn om de keuzes rond het taalmodel te begrijpen.

## Mixture-of-Experts (MoE) vs dense

- **Dense**: elk token activeert álle parameters. Nauwkeurig, maar op
  bandbreedte-gelimiteerde hardware is de snelheid `bandbreedte ÷ totaal-GB`.
- **MoE**: elk token activeert slechts een deel van de experts (bij
  GPT-OSS-120B: ~5,1 B actief van 117 B totaal). Het volledige model moet
  wél in geheugen, maar per token hoeft er maar een klein deel gelezen te
  worden → veel hogere t/s.

Dit is dé reden dat GPT-OSS-120B het wint van dense modellen op de gx10. Zie
[03-platforms/llm-node.md](../03-platforms/llm-node.md).

## Kwantisatie

Het gewicht van het model wordt van hogere precisie (fp16) naar lagere
(bijv. Q4) gebracht om geheugen te besparen. De afruil: kleinere footprint
tegen een klein kwaliteitsverlies. GPT-OSS-120B draait als `UD-Q4_K_XL`
(~59 GB). Belangrijk inzicht uit de benchmark: **kwantiseer niet tot het
randje** — houd 15–20 GB marge voor context en KV-cache.

## Contextvenster (n_ctx)

Het aantal tokens dat de LLM per verzoek in- en uitvoert. Hier 4096. Bepaalt
hoeveel bronnen er per antwoord bij kunnen. Zie
[05-cross-cutting-concerns/rag-and-context-window.md](../05-cross-cutting-concerns/rag-and-context-window.md).

## Reasoning-modellen en de thinking-toggle

GPT-OSS is een reasoning-model: het wil standaard zijn redenering in een
`thinking`-blok zetten. Via `chat_template_kwargs: {enable_thinking: false}`
wordt het op "antwoordmodus" gezet — anders blijft `content` leeg en krijgt
de gebruiker niets. Dit geldt óók voor de runner-up
(Nemotron-3.5-Lightning). Een generieke les: **reasoning-modellen hebben per
familie een eigen thinking-toggle**.

## Temperatuur

`temperature = 0.2`: laag, zodat antwoorden voorspelbaar en feitelijk zijn in
plaats van creatief. Belangrijk bij citeerbare antwoorden.

## Chat-template & tool-calling

llama.cpp exposeert een OpenAI-compatible `/v1/chat/completions`. De service
praat dus met een standaard-interface, terwijl de uitvoering volledig lokaal
is — het beste van beide: geen vendor lock-in, wél bekende API-vorm.
