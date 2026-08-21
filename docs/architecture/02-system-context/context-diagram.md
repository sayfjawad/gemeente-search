# Contextdiagram

```plantuml
@startuml context
!include <C4/C4_Context>

Person(burger, "Burger", "stelt een gemeentelijke vraag in de browser")

System(gemeente_search, "gemeente-search", "FastAPI-service op de GPU-node, poort 8905")

System_Ext(llm, "gx10-node (llama.cpp)", "serveert GPT-OSS-120B via /v1")
System_Ext(edge, "Edge-VPS (nginx)", "TLS-terminatie + reverse proxy")
System_Ext(gemeente_site, "Gemeentewebsite + CDN", "HTML + PDF's")
System_Ext(raad, "raadsinformatie.nl (Notubiz)", "raadsarchief")
System_Ext(smtp, "TransIP SMTP", "e-mailnotificaties")

Rel(burger, edge, "HTTPS", "")
Rel(edge, gemeente_search, "HTTP (Tailscale)", "")
Rel(gemeente_search, llm, "HTTP /v1/chat/completions", "")
Rel(gemeente_search, gemeente_site, "crawlt", "offline pijplijn")
Rel(gemeente_search, raad, "crawlt", "offline pijplijn")
Rel(gemeente_search, smtp, "notificaties", "onboarding")

@enduml
```

## Uitleg

- **Burger → Edge-VPS → service**: publiek verkeer eindigt op TLS op de VPS;
  de VPS proxyt over Tailscale naar de service op de GPU-node (poort 8905).
- **Service → gx10-node**: alleen tijdens het beantwoorden; de LLM draait
  lokaal op `100.64.x.x:8083`, geen externe API.
- **Crawl-relaties zijn offline**: de crawler draait als aparte
  pipeline-stappen, niet als onderdeel van het request/response-pad.

Zie [external-systems.md](external-systems.md) voor details per systeem en
[data-flow-overview.md](data-flow-overview.md) voor de stromen.
