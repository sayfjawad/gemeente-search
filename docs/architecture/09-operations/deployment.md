# Deployment

De deploy-topologie is **hergebruikt** uit de zusterprojecten (zie
[ADR-010](../07-decision-records/ADR-010-deploy-topologie-hergebruikt.md)).

## Componenten

```
Internet ──HTTPS──► Edge-VPS (nginx + certbot)
                        │ Tailscale
                        ▼
              GPU-node (Z8) systemd --user
                   gemeente-search.service :8905
                        │ HTTP (Tailscale)
                        ▼
              gx10-node llama.cpp :8083 (gpt-oss-120b)
```

## Service-unit

`deploy/gemeente-search.service`:

- **Type**: systemd `--user` unit (draait onder het beheerder-account).
- **Poort**: 8905.
- **WorkingDirectory**: `%h/git/gemeente-search`.
- **Gedrag**: automatische herstart bij crash.

```bash
systemctl --user daemon-reload
systemctl --user enable --now gemeente-search.service
systemctl --user status gemeente-search.service
```

## Omgevingsvariabelen

Via `.env` in de projectroot (niet in git):

| Variabele | Waarde |
|---|---|
| `LLM_BASE_URL` | `http://100.64.x.x:8083/v1` |
| `LLM_MODEL` | `gpt-oss-120b` |
| `LLM_API_KEY` | `none` (lokaal model, key niet nodig) |
| `SMTP_PASSWORD` | TransIP SMTP-wachtwoord |

## Releaseproces

Geen CI/CD: de beheerder pullt de wijziging, herstart de unit en verifieert.
Wijzigingen aan de corpus (nieuwe/geactualiseerde gemeente) verlopen via de
onboarding-pipeline, niet via een code-deploy.

## Herstart na index-wijziging

Na `build_index.py` voor een gemeente moet de service herstart worden zodat
de nieuwe `embeddings.npy` in het geheugen komt (de service laadt index en
embeddings bij start).
