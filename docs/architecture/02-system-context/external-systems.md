# Externe systemen

## Gemeentewebsites + CDN

- **Rol**: primaire bron (diensten, regelingen, PDF-uploads).
- **Protocol**: HTTPS; sitemap als ingang; Playwright rendert dynamische
  pagina's.
- **CDN**: `cuatro.sim-cdn.nl` host veel PDF's; de crawler respecteert ook de
  robots.txt van het CDN.
- **Beleefdheid**: concurrency 3, vertraging 0,4 s; hervatbaar via `state.json`.

## raadsinformatie.nl (Notubiz)

- **Rol**: gemeenteraadsarchief (vergaderingen, besluiten, moties).
- **Protocol**: apart crawlpad (`crawl_raad.py`) via het `ris2`-endpoint.
- **Uitzondering**: robots.txt wordt hier bewust *niet* gehonoreerd, op grond
  van Gemeentewet/Woo (publieke plicht); zie
  [ADR-007](../07-decision-records/ADR-007-raadsinformatie-robots-uitzondering.md).

## gx10-node — LLM (llama.cpp)

- **Rol**: genereert de antwoorden.
- **Endpoint**: `http://100.64.x.x:8083/v1`, OpenAI-compatible.
- **Model**: `gpt-oss-120b` (UD-Q4_K_XL, 59 GB). Zie
  [03-platforms/llm-node.md](../03-platforms/llm-node.md).

## GPU-node (Z8) — embeddings & service

- **Rol**: draait de service (systemd `--user`, poort 8905) én de
  BGE-M3-embedding voor de offline pijplijn.
- **Hardware**: 2× Tesla V100.

## Edge-VPS (nginx + certbot)

- **Rol**: publieke ingang, TLS-terminatie, reverse proxy naar de GPU-node
  over Tailscale.

## TransIP SMTP

- **Rol**: e-mailnotificaties tijdens onboarding (mijlpalen), via
  `scripts/notify.py`; wachtwoord uit `.env` (niet in git).

## Hugging Face (modelcache)

- **Rol**: eenmalige download van `BAAI/bge-m3`; lokaal gecached in
  `/data/huggingface` (gedeeld met de zusterprojecten).
