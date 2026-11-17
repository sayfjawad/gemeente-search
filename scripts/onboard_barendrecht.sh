#!/bin/bash
# Onboard gemeente Barendrecht — full pipeline, emails at each milestone.
# Designed to run fully detached (survives SSH logout).
cd "$(dirname "$0")/.." || exit 1
SLUG=barendrecht
PY=".venv/bin/python3"
LOGDIR="data/$SLUG/crawl"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/onboard.log"

log()  { echo "[$(date '+%F %T')] $*" >>"$LOG"; }
notify() { printf '%s' "$2" | "$PY" scripts/notify.py "$1" >>"$LOG" 2>&1 || true; }

log "onboard start"
notify "Barendrecht onboarding gestart" "Onboarding van gemeente Barendrecht is gestart. Je krijgt een mail per stap en bij voltooiing."

step() {
  local name="$1"; shift
  log "=== $name START ==="
  if "$@" >>"$LOG" 2>&1; then
    log "=== $name OK ==="
    notify "Barendrecht: $name klaar" "$name voltooid."
    return 0
  else
    log "=== $name FAILED ==="
    notify "Barendrecht: $name FOUT" "$name is mislukt. Zie $LOGDIR/onboard.log op de Z8."
    return 1
  fi
}

step "crawl hoofdsite" "$PY" crawl.py --municipality "$SLUG" || exit 1
step "crawl raadsinformatie (Notubiz)" "$PY" crawl_raad.py --municipality "$SLUG" || exit 1
step "add_reference" "$PY" scripts/add_reference.py --municipality "$SLUG" || exit 1
step "ingest" "$PY" ingest.py --municipality "$SLUG" || exit 1
step "build_index (GPU)" "$PY" build_index.py --municipality "$SLUG" || exit 1

log "restart service"
if systemctl --user restart gemeente-search >>"$LOG" 2>&1; then
  log "service restarted"
else
  notify "Barendrecht: restart FOUT" "Index is gebouwd maar de herstart van de service is mislukt. Controleer met: systemctl --user status gemeente-search"
  exit 1
fi

sleep 8
MAIN_DOCS=$(wc -l < data/$SLUG/crawl/docs.jsonl 2>/dev/null || echo 0)
RAAD_DOCS=$(wc -l < data/$SLUG/crawl/raad_docs.jsonl 2>/dev/null || echo 0)
IN_API=$(curl -s -m 10 http://127.0.0.1:8905/api/municipalities | grep -c barendrecht)

if [ "$IN_API" -ge 1 ]; then
  notify "Barendrecht onboarding VOLTOOID" "Gemeente Barendrecht is live op https://gemeente.multicode.nl — $MAIN_DOCS webpagina's + $RAAD_DOCS raadsdocumenten in de index. Kies 'Barendrecht' in de dropdown."
else
  notify "Barendrecht onboarding: CONTROLEER" "Index gebouwd ($MAIN_DOCS webpagina's + $RAAD_DOCS raadsdocumenten) maar Barendrecht staat niet in /api/municipalities. Controleer de service op de Z8."
fi

log "onboard done"
