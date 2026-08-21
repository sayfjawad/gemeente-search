# Lokaal ontwikkelen

## Vereisten

- De **gedeelde venv**: `/data/git/lift-normen-search/.venv` (zie
  [04-shared-resources](../04-shared-resources/shared-infrastructure.md)).
- `HF_HOME=/data/huggingface` voor de modelcache (BGE-M3).
- Toegang tot de gx10-node (`100.64.x.x:8083`) via Tailscale voor de LLM.
- `.env` voor de secrets (SMTP) — niet in git.

## Setup

```bash
cd /data/git/gemeente-search
cp .env.example .env        # vul SMTP_PASSWORD in indien gewenst
source /data/git/lift-normen-search/.venv/bin/activate
```

## De pijplijn stap voor stap

```bash
# 1. Crawl de hoofdsite (per gemeente; hervatbaar)
python crawl.py --municipality <slug>

# 2. Crawl het raadsarchief (optioneel)
python crawl_raad.py --municipality <slug>

# 3. Voeg gecureerde referenties toe (optioneel)
python scripts/add_reference.py --municipality <slug>

# 4. Bouw de index (dedup + chunk)
python ingest.py --municipality <slug>

# 5. Embed de chunks
python build_index.py --municipality <slug>
```

Of alles in één keer voor een nieuwe gemeente:
`scripts/onboard_barendrecht.sh` is het referentie-script (pas de slug aan).

## De service lokaal draaien

```bash
uvicorn app:app --port 8905
```

Test de API: `curl localhost:8905/api/municipalities`.

## Tips

- De crawler is hervatbaar (`state.json`); een onderbroken crawl herstart waar
  hij stopte.
- `ingest.py` en `build_index.py` zijn idempotent: veilig om te herhalen.
- Gebruik `/api/statistics` om na onboarding te verifiëren dat de corpus
  volledig is ingeladen.
