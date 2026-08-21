# Woordenlijst (glossary)

| Term | Definitie |
|---|---|
| **RAG** | Retrieval-Augmented Generation: eerst relevante fragmenten ophalen, dan het taalmodel het antwoord laten formuleren op basis van alleen die fragmenten. |
| **Corpus** | De verzameling documenten (HTML + PDF + raadsarchief + referenties) van één gemeente. |
| **Chunk** | Een tekstfragment waarin een document is opgeknipt (max. ~1400 tekens, PDF's per pagina). De eenheid van indexeren en ophalen. |
| **Embedding** | Een numerieke vector (1024-dim) die de betekenis van een chunk representeert. |
| **BGE-M3** | Het embeddingmodel (`BAAI/bge-m3`): meertalig (sterk in Nederlands), 1024-dims, op GPU gedraaid. |
| **Cosine-similariteit** | De maat waarmee de afstand tussen vraag-embedding en chunk-embeddings wordt bepaald. |
| **Slug** | De machineleesbare identificator van een gemeente (bijv. `utrecht`), sleutel van `municipalities.json`. |
| **Agentic fallback** | Als de beste cosine-score onder een drempel (0.50) ligt, zoekt het systeem op de site zelf en haalt het de top-pagina's op in plaats van "weet ik niet" te antwoorden. |
| **Canonicalisatie** | URL's normaliseren (http→https, trailing slash, query-strip) zodat dezelfde bron niet dubbel in de index komt. |
| **Deduplicatie** | Het wegfilteren van dubbele documenten op basis van de canonical URL bij ingest. |
| **Notubiz** | De leverancier achter `raadsinformatie.nl`; het raadsarchief heeft een apart crawlpad (`ris2`). |
| **Cuatro CDN** | `cuatro.sim-cdn.nl`, het CDN waar veel gemeentelijke PDF's gehost worden; robots.txt van CDN wordt mee-gerespecteerd. |
| **Trafilatura** | De Python-bibliotheek die uit ruwe HTML de leesbare hoofdtekst extraheert. |
| **Playwright** | Chromium-aansturing die de dynamische pagina's rendert voordat ze geëxtraheerd worden. |
| **MoE** | Mixture-of-Experts: een model waarbij per token maar een deel van de parameters actief is — veel sneller op bandbreedte-gelimiteerde hardware. |
| **Dense model** | Een model waarbij per token álle parameters actief zijn (nauwkeuriger, maar langzamer op de gx10). |
| **llama.cpp** | De C++-inference-engine die de LLM lokaal op de gx10 draait (geen API-dependency). |
| **GX10** | De NVIDIA DGX Spark-klasse node (GB10 Grace Blackwell, 128 GB unified memory) die de LLM serveert. |
| **Tailscale** | Het mesh-VPN waardoor nodes onderling bereikbaar zijn via de `100.x.y.z`-adressen. |
| **systemd `--user`** | De manier waarop de service draait (user-unit, poort 8905, herstart bij crash). |
| **Bronverwijzing / citaat** | De `[n]`-badge in het antwoord die koppelt aan een specifieke chunk uit een specifieke bron. |
| **Contextvenster (n_ctx)** | Het aantal tokens dat de LLM per verzoek kan verwerken (hier 4096); begrenst hoeveel bronnen er per antwoord bij kunnen. |
