# Deployment

Zie [ADR-017](../07-decision-records/ADR-017-hosting-op-c4130-met-nas-data.md)
voor het waarom. De oorspronkelijke topologie staat in
[ADR-010](../07-decision-records/ADR-010-deploy-topologie-hergebruikt.md).

## Componenten

```
Internet ──HTTPS──► Edge-VPS (nginx + certbot)
                        │ mesh-VPN
                        ▼
              GPU-server (C4130), systemd --user
                gemeente-search.service :8905  ── BGE-M3 op CPU
                        │ loopback
                        ▼
              LLM-dienst vLLM :8080 (qwen3.8-27b, 4× V100)

data/                     → lokale schijf  (index.sqlite, embeddings.npy)
data/<slug>/crawl, pdfs   → NFS-mount NAS-share gemeente-data
```

## Service-unit

[`deploy/gemeente-search.service`](../../../deploy/gemeente-search.service)
is gelijk aan de unit in productie:

- systemd `--user`-unit onder het beheerder-account, poort 8905.
- `WorkingDirectory=%h/git/gemeente-search`, `EnvironmentFile=.env`,
  `HF_HOME` naar de gedeelde modelcache.
- `Restart=always`.

```bash
cp deploy/gemeente-search.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now gemeente-search.service
loginctl enable-linger "$USER"     # blijft draaien zonder ingelogde sessie
```

## Omgevingsvariabelen (`.env`, niet in git)

| Variabele | Productiewaarde | Opmerking |
|---|---|---|
| `LLM_BASE_URL` | `http://127.0.0.1:8080/v1` | elk OpenAI-compatibel endpoint |
| `LLM_MODEL` | `qwen3.8-27b` | |
| `LLM_API_KEY` | (lokaal niet nodig) | wel nodig bij een externe provider |
| `CUDA_VISIBLE_DEVICES` | leeg / niet gezet | GPU's zijn voor de LLM; embedden op CPU |
| `SMTP_*`, `MAIL_FROM`, `MAIL_TO` | | alleen voor onboarding-mails (`scripts/notify.py`) |

Zie [`.env.example`](../../../.env.example).

## Releaseproces

Er is geen CI/CD. Productie is een **kopie** van deze repo (geen
git-checkout):

1. Wijziging committen en pushen naar deze repo.
2. Bestanden naar de server kopiëren (bijv. `rsync` van de code, **zonder**
   `data/`, `.env`, `.venv` en `stats.sqlite`).
3. `systemctl --user restart gemeente-search` en verifiëren met
   `curl https://<domein>/api/municipalities`.

Houd repo en productie gelijk. Controleren kan door checksums van de
code-bestanden aan beide kanten te vergelijken.

## Herstart na index-wijziging

De service laadt bij het opstarten alle indexen en embeddings in het geheugen.
Na `build_index.py` voor een gemeente is dus een herstart nodig.
`scripts/onboard_all.py` doet dat automatisch.
