# Lokaal ontwikkelen

## Vereisten

- **Python 3.10+** en de pakketten uit [`requirements.txt`](../../../requirements.txt)
  (of een symlink `.venv` naar de gedeelde venv, zie
  [04-shared-resources](../04-shared-resources/shared-infrastructure.md)).
- **Playwright + Chromium** voor de crawler (JS-zware gemeentesites).
- **Een OpenAI-compatibel LLM-endpoint** voor `/api/ask` en `/api/compare`
  (lokale vLLM/llama.cpp/Ollama, of een API zoals DeepSeek). `/api/search`
  werkt zonder LLM.
- **Optioneel een GPU** voor `build_index.py` (BGE-M3 bulk-embedding). Op
  CPU werkt het ook, maar langzamer. Queries embedden prima op CPU.
- Schijfruimte: per gemeente 0,1–8 GB aan PDF's. Alle 342 samen ~420 GB.
- `HF_HOME` naar een map waar BGE-M3 (~2,3 GB) gecachet kan worden.

## Setup

```bash
git clone https://github.com/sayfjawad/gemeente-search.git
cd gemeente-search
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install playwright && .venv/bin/playwright install chromium
cp .env.example .env        # vul LLM_* (en optioneel SMTP_*) in
```

## De pijplijn stap voor stap

```bash
# 1. Crawl de hoofdsite (per gemeente; hervatbaar)
.venv/bin/python3 crawl.py --municipality <slug>

# 2. Crawl het raadsarchief (optioneel)
.venv/bin/python3 crawl_raad.py --municipality <slug>

# 3. Voeg gecureerde referenties toe (optioneel)
.venv/bin/python3 scripts/add_reference.py --municipality <slug>

# 4. Bouw de index (dedup + chunk)
.venv/bin/python3 ingest.py --municipality <slug>

# 5. Embed de chunks
.venv/bin/python3 build_index.py --municipality <slug>
```

Zet daarna `"enabled": true` voor de gemeente in `municipalities.json`, of
gebruik `scripts/_enable.py <slug>`.

Voor veel gemeenten tegelijk: `scripts/onboard_all.py` (zie het
[onboarding-runbook](../09-operations/onboarding-runbook.md)).

## De service lokaal draaien

```bash
.venv/bin/python3 -m uvicorn app:app --port 8905
```

Test: `curl localhost:8905/api/municipalities`, of open
`http://localhost:8905/zoek`.

## Tips

- De crawler is hervatbaar (`state.json`): een onderbroken crawl gaat verder
  waar hij stopte.
- `ingest.py` en `build_index.py` zijn idempotent en kunnen veilig opnieuw
  draaien.
- Zonder GPU: `CUDA_VISIBLE_DEVICES= ` forceert CPU.
