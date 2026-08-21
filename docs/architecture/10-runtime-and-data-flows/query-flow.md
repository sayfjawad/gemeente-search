# Query-flow (online)

De route van "vraag" naar "geciteerd antwoord" binnen één request.

```plantuml
@startuml query-flow
!include <C4/C4_Component>

title Query-flow (online request/response)

[Burger] --> (FastAPI app.py) : /api/ask {vraag, slug}

(app.py) --> (embedder.py) : embed(vraag) op GPU (BGE-M3)
(embedder.py) --> (app.py) : query-embedding

(app.py) --> (embeddings.npy) : matrix @ q.T (cosine)
(embeddings.npy) --> (app.py) : top-N chunks

(app.py) --> (agentic fallback) : als score < 0.50
(agentic fallback) --> [site-zoekmachine] : query
[site-zoekmachine] --> (agentic fallback) : top-pagina's
(agentic fallback) --> (app.py) : extra chunks

(app.py) --> (gx10 llama.cpp) : prompt = system + bronnen (≤8200 tekens, ≤16)
(gx10 llama.cpp) --> (app.py) : antwoord met [n]-citaten

(app.py) --> (static/index.html) : antwoord + bronkaarten
(static/index.html) --> (app.py) : /pdf-image/{slug}/{chunk_id} (PDF-pagina's)

@enduml
```

## Stappen

1. **Vraag + slug** binnen via `/api/ask` (of `/api/search` voor directe
   chunk-hits).
2. **Embed** de vraag op de GPU met BGE-M3.
3. **Score** alle chunks van de gemeente via één matrixproduct
   (`embeddings.npy @ q.T`) en neem de top-N.
4. **Drempel**: is de beste score < 0.50, dan **agentic fallback** — site-zoek,
   top-pagina's ophalen, chunks injecteren (ADR-005).
5. **Prompt bouwen**: system-prompt (Nederlands, citatieregels) + vraag +
   geselecteerde bronnen binnen budget (≤ ~8200 tekens, ≤ 16 bronnen).
6. **Genereren**: LLM-call naar de gx10 met
   `chat_template_kwargs: {enable_thinking: false}`, `max_tokens=1800`,
   `temperature=0.2`.
7. **Renderen**: antwoord met `[n]`-citaten; de UI toont bronkaarten,
   markeert geciteerde bronnen, en laadt voor PDF-bronnen de pagina-afbeelding
   via `/pdf-image/{slug}/{chunk_id}`.

## Twee endpoints

- `/api/ask` — volledige RAG: retrieval + LLM + citaten.
- `/api/search` — alleen retrieval (top chunks), voor de "Zoeken"-tab.
