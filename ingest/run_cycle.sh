#!/usr/bin/env bash
# Twice-weekly ingest cycle (runs on the DB host, local mode). Ends at the human review
# queue — it never publishes. Publishing is your manual `python3 apply.py <ids>`.
#
#   pipeline.py    ingest real-URL feeds → dedupe → pre-filter → stage (status='new')
#   enrich.py      resolve primary URL + capture verbatim quote      (classified → enriched)
#   opus_review.py Opus relevance gate, batches per risk             (enriched → approved/rejected)
#   build_review.py render /x/ai-atlas-review of approved candidates
#
# Local-Qwen routing (new → classified) is the SEPARATE classify timer; this cycle just
# processes whatever it has classified so far.
set -euo pipefail
cd "$(dirname "$0")"
[ -f .aipi.env ] && . ./.aipi.env
# Opus key: prefer env, else the host's monitoring env
if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -f /opt/monitoring/.env ]; then
  export ANTHROPIC_API_KEY="$(grep -oE 'ANTHROPIC_API_KEY=[^ ]+' /opt/monitoring/.env | head -1 | cut -d= -f2)"
fi
log(){ echo "[$(date -u +%H:%M:%S)] $*"; }

log "ingest"        ; python3 pipeline.py      || log "pipeline error (continuing)"
log "enrich"        ; python3 enrich.py        || log "enrich error (continuing)"
log "opus gate"     ; python3 opus_review.py   || log "opus_review error (continuing)"
log "review report" ; python3 build_review.py  || log "build_review error"
log "cycle done — review at /x/ai-atlas-review, then: python3 apply.py <ids>"
