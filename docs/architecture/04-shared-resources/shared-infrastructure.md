# Gedeelde infrastructuur

`gemeente-search` deelt de fysieke en logische infrastructuur met de andere
zoekapps. Dat is een bewuste keuze
([D5 — hergebruik](../01-architecture-principles/architectural-drivers.md)).
Het gevolg is ook een gedeelde verantwoordelijkheid voor versies en
capaciteit.

## GPU-server (C4130, datacenter)

- **Rol**: draait de service (`:8905`, systemd `--user`) en de gedeelde
  LLM-dienst (`:8080`). Zie [ADR-017](../07-decision-records/ADR-017-hosting-op-c4130-met-nas-data.md).
- **Hardware**: 4× Tesla V100-SXM2-32GB. Alle vier worden door de LLM
  gebruikt; de app embedt queries daarom op de **CPU**.
- **Deling**: dezelfde host draait ook `lift-normen-search` (8904),
  `politicus-search` (8908) en andere diensten.

## LLM-dienst

- Qwen3.8-27B op vLLM, `127.0.0.1:8080` vanaf de app gezien. Zie
  [03-platforms/llm-node.md](../03-platforms/llm-node.md).

## NAS

- Share `gemeente-data` (~420 GB crawl-tekst + PDF's), via NFS gemount op
  de GPU-server. De `data/<slug>/crawl`- en `data/<slug>/pdfs`-mappen zijn
  symlinks daarheen.
- Dagelijkse backup van de indexen + `stats.sqlite` naar dezelfde share.
  De share wordt gerepliceerd naar een tweede NAS.

## Gedeelde Python-venv

- `.venv` is een symlink naar de venv van `lift-normen-search`.
- Bevat: `fastapi`, `uvicorn`, `torch`, `transformers`, `numpy`, `httpx`,
  `pymupdf`, `playwright`, `trafilatura`, `beautifulsoup4`, `lxml`.
- **Risico**: een versie-upgrade voor het ene project raakt het andere. Zie
  [constraints C2](../01-architecture-principles/constraints.md).

## Edge-VPS

- nginx + certbot; publieke TLS-terminatie; proxyt per hostname naar de
  juiste poort op de GPU-server over het mesh-VPN.

## Hugging Face-modelcache

- Via `HF_HOME` (gezet in de systemd-unit). Bevat onder meer `BAAI/bge-m3`.

## Gevolgen voor gemeente-search

1. **Geen eigen venv**: dependencies volgen het lift-normen-search-project.
2. **Capaciteitsdeling**: drukte op de LLM-dienst door andere apps raakt de
   antwoordtijd hier.
3. **NAS-afhankelijkheid**: zonder NFS-mount werken antwoorden nog, maar
   PDF-weergave niet.
4. **Secrets**: SMTP-wachtwoord en een eventuele LLM-key staan alleen in
   `.env`, nooit in git.
