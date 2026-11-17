# Systeemlandschap

`gemeente-search` staat niet op zichzelf. Het hoort bij een **familie van
zoekapplicaties** die bewust dezelfde architectuur en infrastructuur delen.

## De familie

| Project | Domein | Poort |
|---|---|---|
| `lift-normen-search` | NEN/EN-liftnormen | 8904 (levert de gedeelde venv) |
| **`gemeente-search`** | Gemeentewebsites | **8905 (dit project)** |
| `politicus-search` | Politieke transcripten (opvolger van `wilders-search`/`yesilgoz-search`) | 8908 |
| `slimme-archief-zoeker` | Archiefzoeker | — |

## Gedeelde infrastructuur (sinds oktober 2026)

- **GPU-server (Dell C4130, datacenter)**: 4× V100-SXM2-32GB. Draait de
  zoekapps als systemd `--user`-units én de gedeelde LLM-dienst
  (Qwen3.8-27B op vLLM, `:8080`). Zie
  [ADR-016](../07-decision-records/ADR-016-qwen-op-c4130-via-vllm.md) en
  [ADR-017](../07-decision-records/ADR-017-hosting-op-c4130-met-nas-data.md).
- **NAS (Synology, datacenter)**: crawl-data en PDF's via NFS. Wordt
  gerepliceerd naar een tweede NAS.
- **Edge-VPS**: nginx + certbot, TLS-terminatie, proxy over een privé
  mesh-VPN naar de GPU-server.
- **Gedeelde venv**: die van `lift-normen-search` (torch, transformers,
  pymupdf, fastapi).
- **Hugging Face-cache**: gedeelde `HF_HOME` voor BGE-M3.

Zie [04-shared-resources](../04-shared-resources/shared-infrastructure.md) en
[01-architecture-principles/influences.md](../01-architecture-principles/influences.md).
