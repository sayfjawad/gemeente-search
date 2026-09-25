# Systeemlandschap

> **Stand 2026-09-25:** de app draait op **`c4130-4xp100`** (datacenter), niet meer op de Z8 of
> `c4130-4xv100`. Indexen staan op `/data` (NVMe), crawl/PDF's op de NAS (`/mnt/gemeente-live`).
> Zie [ADR-015](../07-decision-records/ADR-015-c4130-4xp100-en-opslagindeling.md).

`gemeente-search` staat niet op zichzelf: het is lid van een **familie van
GPU-backed zoekapplicaties** op dit account, die bewust dezelfde architectuur
en infrastructuur delen.

## De familie

| Project | Domein | Opmerking |
|---|---|---|
| `wilders-search` | Zoeken over politieke transcripten | poort 8902 |
| `yesilgoz-search` | Idem (variant) | poort 8903 |
| `lift-normen-search` | NEN/EN-liftnormen | poort 8904, gedeelde venv, bron-ADR-structuur |
| `abo-ali-search` | Zoeken over transcripten | zelfde GPU-retrieval-patroon |
| `slimme-archief-zoeker` | Archiefzoeker | kopie van wilders-search-patroon |
| **`gemeente-search`** | Gemeentewebsites | **dit project**, poort 8905 |

## Gedeelde infrastructuur

- **GPU-node (Z8)** — 2× Tesla V100; draait de systemd
  `--user`-units (poorten 8902–8905) en de BGE-M3-embeddings.
- **Gedeelde venv** — `/data/git/lift-normen-search/.venv` (torch,
  transformers, pymupdf, fastapi), door de zoekapps hergebruikt.
- **gx10-node (100.64.x.x)** — NVIDIA DGX Spark-klasse (GB10 Grace Blackwell,
  128 GB unified memory); draait llama.cpp en serveert GPT-OSS-120B.
- **Edge-VPS** — nginx + certbot, TLS-terminatie, proxy naar de GPU-node over
  Tailscale.
- **HF-modelcache** — `/data/huggingface`, gedeeld voor de embeddingmodellen.

Zie [04-shared-resources](../04-shared-resources/shared-infrastructure.md) en
[01-architecture-principles/influences.md](../01-architecture-principles/influences.md)
voor de kruisbestuiving tussen deze projecten.
