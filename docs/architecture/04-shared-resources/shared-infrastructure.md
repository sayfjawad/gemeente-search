# Gedeelde infrastructuur

`gemeente-search` deelt de fysieke en logische infrastructuur met de andere
zoekapps op dit account. Deze gedeeldheid is een bewuste keuze
([D5 — hergebruik](../01-architecture-principles/architectural-drivers.md)),
met als gevolg ook een gedeelde verantwoordelijkheid voor versies en capaciteit.

## GPU-node (Z8, Z8)

- **Rol**: draait de service (poort 8905, systemd `--user`) én de
  BGE-M3-embedding voor de offline pijplijn.
- **Hardware**: 2× Tesla V100 (32 GB totaal).
- **Deling**: dezelfde node draait de units van wilders/yesilgoz/lift-normen/
  abo-ali/slimme-archief op poorten 8902–8905.

## Gedeelde Python-venv

- Pad: `/data/git/lift-normen-search/.venv`.
- Bevat: `fastapi`, `uvicorn`, `torch`, `transformers`, `numpy`, `httpx`,
  `pymupdf`, `playwright`, `trafilatura`, `beautifulsoup4`, `lxml`.
- **Risico**: een versie-upgrade voor het ene project raakt alle andere. Zie
  [constraints C2](../01-architecture-principles/constraints.md).

## gx10-node (LLM)

- Adres: `100.64.x.x:8083` (Tailscale), draait llama.cpp met GPT-OSS-120B.
- Gedeeld met de zusterapps die dezelfde LLM gebruiken.

## Edge-VPS

- nginx + certbot; publieke TLS-terminatie; proxyt per hostname/pad naar de
  juiste poort op de GPU-node over Tailscale.

## Hugging Face-modelcache

- Pad: `/data/huggingface` (via `HF_HOME`).
- Bevat onder meer `BAAI/bge-m3`, gedeeld door de zoekapps die BGE-M3
  gebruiken.

## Tailscale (netwerk)

- Verbindt de nodes via `100.x.y.z`-adressen; de service bereikt de LLM en de
  VPS bereikt de service.

## Gevolgen voor gemeente-search

1. **Poortkeuze**: 8905 is het volgende vrije nummer in de reeks.
2. **Geen eigen venv**: dependencies volgen het lift-normen-search-project.
3. **Capaciteitsdeling**: pieken in de ene app (bijv. een crawl) kunnen de
   andere raken — voor deze demonstratie-belasting acceptabel.
4. **Secrets**: SMTP-wachtwoord en (lege) LLM-key staan lokaal in `.env`,
   nooit in git.
