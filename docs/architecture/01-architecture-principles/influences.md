# Invloeden uit andere projecten en technieken

De opzet van `gemeente-search` is geen greenfield-ontwerp: hij is bewust
afgeleid van wat in de zusterprojecten al bleek te werken, en van een gerichte
LLM-benchmark op de eigen hardware.

## Projecten die de opzet hebben bepaald

### `lift-normen-search` — het directe blauwdruk-project
- **Gedeelde venv**: dezelfde Python-omgeving met torch/transformers/pymupdf.
- **BGE-M3-embedding-setup**: modelkeuze, 1024-dims, GPU-embedden, `fp16`
  opslag in `.npy`.
- **In-memory cosine-retrieval**: het `matrix @ q.T` + `torch.topk`-patroon.
- **ADR-structuur en -sjabloon**: het arc42-achtige format (Status/Context/
  Besluit/Consequenties/Alternatieven) is hier 1-op-1 overgenomen.
- **Deploy-topologie**: systemd `--user`, nginx + certbot op de edge-VPS,
  Tailscale naar de GPU-node.

### `wilders-search` / `abo-ali-search` / `slimme-archief-zoeker`
- Bewezen dat hetzelfde GPU-retrieval-patroon op meerdere corpora werkt.
- De poortnummers (8902–8905) volgen de reeds bestaande reeks.

### `gx10-llm-benchmarks`
- De doorslaggevende benchmark die **GPT-OSS-120B** als LLM selecteerde
  (perfecte antwoordscores én 53,4 tokens/s) boven alternatieven.
- Leverde de harde lessen: **MoE > dense** op bandbreedte-gelimiteerde
  hardware, niet overkwantiseren, reasoning-modellen hebben een
  thinking-toggle nodig. Zie
  [03-platforms/llm-node.md](../03-platforms/llm-node.md).

### `odp-architecture`
- De **nummering en documentatie-discipline** van deze documentatie zelf
  (00–13), inclusief ADR-verplichting en documentation-as-code.

## Technieken die de aanpak vormden

| Techniek | Invloed |
|---|---|
| **RAG met lokale embeddings** | Geen vector-DB maar in-memory cosinus; de corpus is klein genoeg. |
| **Sitemap-first BFS-crawler** | Voorspelbaar, beleefd (concurrency 3, delay 0,4 s), hervatbaar via state.json. |
| **Trafilatura + Playwright** | Betrouwbare tekstextractie uit dynamische gemeentelijke CMS'en. |
| **MoE-inferentie (llama.cpp)** | Laat een 117B-totaal model op één GB10-node draaien met bruikbare snelheid. |
| **Agentic retrieval** | De fallback-zoekstap is een vorm van tool-use die het systeem vollediger maakt. |

Zie de ADR's voor de onderbouwing per keuze:
[07-decision-records/](../07-decision-records/).
