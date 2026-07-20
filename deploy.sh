#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# AI Problems Index — one-command deploy
#
#   ./deploy.sh atlas            dump DB → build → publish the Risk Atlas
#   ./deploy.sh research         build → publish the Research Library page
#   ./deploy.sh orgs             dump alignment_orgs → build → publish the org directory
#   ./deploy.sh page <slug> <file>   publish any canonical HTML file to a slug
#   ./deploy.sh all              atlas + research + all canonical pages
#   ./deploy.sh verify           check every page is live and non-empty
#   ./deploy.sh dump             refresh atlas_issues.json only (no publish)
#
# Flags:  --dry-run   build + validate, do not write to the DB
#
# Requires: ssh access to the db host, python3, node (for JS syntax check; optional)
# ---------------------------------------------------------------------------
set -euo pipefail

# ---- config -------------------------------------------------------------
# Real values are NOT committed. Set them via environment, or drop a local
# .aipi.env next to this script (gitignored). See .env.example.
[ -f "$(dirname "$0")/.aipi.env" ] && . "$(dirname "$0")/.aipi.env"

WORKDIR="${AIPI_WORKDIR:-$HOME/backups/ai-risk-db-factcheck}"
SSH_HOST="${AIPI_SSH_HOST:?set AIPI_SSH_HOST (ssh alias of the db host)}"
PGC="${AIPI_PG_CONTAINER:?set AIPI_PG_CONTAINER (postgres container name)}"
DB="${AIPI_DB:?set AIPI_DB (database name)}"
PAGES_ROLE="${AIPI_PAGES_ROLE:-school}"   # owns the `pages` table
KB_ROLE="${AIPI_KB_ROLE:-school}"         # owns real_issues / research_library
DRY_RUN=0

for a in "$@"; do [ "$a" = "--dry-run" ] && DRY_RUN=1; done

c_ok(){ printf '\033[32m✓\033[0m %s\n' "$*"; }
c_info(){ printf '\033[36m•\033[0m %s\n' "$*"; }
c_warn(){ printf '\033[33m!\033[0m %s\n' "$*"; }
c_err(){ printf '\033[31m✗\033[0m %s\n' "$*" >&2; }
die(){ c_err "$*"; exit 1; }

psql_as(){ # psql_as <role> ; reads SQL from stdin
  ssh "$SSH_HOST" "docker exec -i $PGC psql -U $1 -d $DB -q"
}
psql_q(){ # psql_q <role> <sql>  → single value
  ssh "$SSH_HOST" "docker exec -i $PGC psql -U $1 -d $DB -At -c \"$2\""
}

# canonical hand-maintained pages: slug|file (built by hand, published as-is)
CANONICAL_PAGES=(
  "ai-problems-index|index_live.html"
  "ai-environmental-impact|env7_content.html"
  "ai-moral-patienthood|moral_content.html"
  "ai-datacenter-action|dca_content_v2.html"
)

# ---------------------------------------------------------------------------
publish_file(){ # publish_file <slug> <file>
  local slug="$1" file="$2"
  [ -f "$WORKDIR/$file" ] || die "missing file: $WORKDIR/$file"
  preflight "$slug" "$file"

  # pick a dollar-quote tag that does not appear in the content
  local tag
  tag=$(python3 - "$WORKDIR/$file" <<'PY'
import sys
h=open(sys.argv[1],encoding='utf-8',errors='replace').read()
for t in ['dep1','dep2','dep3','dep4','xq7','zz9']:
    if f'${t}$' not in h: print(t); break
else: raise SystemExit("no safe dollar tag")
PY
)
  local bytes; bytes=$(wc -c < "$WORKDIR/$file" | tr -d ' ')

  if [ "$DRY_RUN" = "1" ]; then
    c_warn "[dry-run] would publish $file → $slug ($bytes bytes, tag \$$tag\$)"
    return 0
  fi

  python3 - "$WORKDIR/$file" "$slug" "$tag" > "$WORKDIR/.deploy_apply.sql" <<'PY'
import sys
path, slug, tag = sys.argv[1], sys.argv[2], sys.argv[3]
h = open(path, encoding='utf-8').read()
print("\\set ON_ERROR_STOP on")
print("BEGIN;")
print(f"UPDATE pages SET content_html=${tag}${h}${tag}$, updated_at=now() WHERE slug='{slug}';")
print(f"SELECT length(content_html) AS bytes FROM pages WHERE slug='{slug}';")
print("COMMIT;")
PY
  psql_as "$PAGES_ROLE" < "$WORKDIR/.deploy_apply.sql" >/dev/null
  rm -f "$WORKDIR/.deploy_apply.sql"

  local live; live=$(psql_q "$PAGES_ROLE" "SELECT length(content_html) FROM pages WHERE slug='$slug';" | tr -d ' \r')
  [ -n "$live" ] || die "publish failed: $slug not found in pages"
  c_ok "published $slug  ($live bytes live)"
}

# Regression guards: refuse to publish a page that has silently lost a critical feature.
# (Builder/source files in the working dir have been reverted by tooling mid-session before,
#  and a reverted hub shipped once — breaking every per-risk page. Never again.)
preflight(){ # preflight <slug> <file>
  local slug="$1" file="$2" f="$WORKDIR/$file"
  case "$slug" in
    ai-problems-index)
      grep -q "split('/')" "$f" || die "REFUSING: $file lost the sub-route router (#atlas/<risk> would fall back to home)"
      c_ok "preflight: hub sub-route router present" ;;
    ai-risk-atlas)
      grep -q 'rx-tile' "$f" || die "REFUSING: $file has no list tiles"
      grep -q "loadBundle\|rx-page" "$f" || die "REFUSING: $file lost its detail routing"
      c_ok "preflight: atlas list intact" ;;
    ai-alignment-orgs)
      local n; n=$(grep -o 'class="card"' "$f" | wc -l | tr -d ' ')
      [ "${n:-0}" -ge 20 ] || die "REFUSING: org directory has only ${n:-0} org cards"
      c_ok "preflight: org directory has $n orgs" ;;
    ai-risk-atlas-detail)
      # NB: count occurrences, not lines — the built HTML is minified onto a few very long lines,
      # so `grep -c` undercounts (reported 3 for a healthy 52-page bundle).
      local n; n=$(grep -o 'class="rx-page"' "$f" | wc -l | tr -d ' ')
      [ "${n:-0}" -ge 50 ] || die "REFUSING: detail bundle has only ${n:-0} risk pages (expected ~52)"
      c_ok "preflight: detail bundle has $n risk pages" ;;
  esac
}

check_js(){ # check_js <file> — syntax-check the last <script> block if node exists
  command -v node >/dev/null || return 0
  python3 - "$WORKDIR/$1" <<'PY' > /tmp/_aipi_check.js 2>/dev/null || return 0
import sys,re
h=open(sys.argv[1],encoding='utf-8').read()
s=re.findall(r'<script>(.*?)</script>', h, re.S)
print(s[-1] if s else '')
PY
  if [ -s /tmp/_aipi_check.js ]; then
    node --check /tmp/_aipi_check.js >/dev/null 2>&1 \
      && c_ok "JS syntax OK ($1)" || die "JS syntax error in $1 — aborting"
  fi
}

# ---------------------------------------------------------------------------
do_dump(){
  c_info "dumping real_issues (+ score_* + sources) → atlas_issues.json"
  ssh "$SSH_HOST" "docker exec -i $PGC psql -U $KB_ROLE -d $DB -At -c \"
    SELECT json_agg(t ORDER BY t.title) FROM (
      SELECT i.id,i.title,i.status,i.icon,i.summary,i.description,i.why_it_matters,i.what_being_done,
             i.score_state,i.score_trend,i.score_conf,i.score_note,i.score_markers,
             i.score_threat,i.score_kind,i.score_cases,
             COALESCE((SELECT json_agg(json_build_object('title',s.title,'url',s.url)
                       ORDER BY s.display_order,s.id)
                       FROM real_issues_sources s WHERE s.issue_id=i.id),'[]'::json) AS sources
      FROM real_issues i) t;\"" > "$WORKDIR/atlas_issues.json"
  python3 - "$WORKDIR/atlas_issues.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert len(d)>=50, f"suspiciously few risks: {len(d)}"
graded=sum(1 for x in d if x.get('score_state'))
cases=sum(len(x.get('score_cases') or []) for x in d)
print(f"  {len(d)} risks | {graded} graded | {cases} timeline events")
PY
  c_ok "dump complete"
}

do_atlas(){
  do_dump
  c_info "building atlas (list + detail bundle)"
  ( cd "$WORKDIR" && python3 build_atlas.py )
  check_js atlas_content.html
  # The atlas is split in two for load speed:
  #   ai-risk-atlas         → light list view (tiles + filters + router)
  #   ai-risk-atlas-detail  → the 52 per-risk pages, fetched on demand/in background
  # BOTH must be published together or risk pages go stale / fail to load.
  publish_file "ai-risk-atlas" "atlas_content.html"
  [ -f "$WORKDIR/atlas_detail.html" ] \
    && publish_file "ai-risk-atlas-detail" "atlas_detail.html" \
    || die "atlas_detail.html missing — detail pages would break; aborting"
}

do_orgs(){
  c_info "dumping alignment_orgs → orgs_dump.json"
  ssh "$SSH_HOST" "docker exec -i $PGC psql -U $KB_ROLE -d $DB -At -c \"
    SELECT coalesce(json_agg(t ORDER BY t.name),'[]'::json) FROM (
      SELECT slug,name,acronym,url,feed_url,feed_kind,country,org_type,founded,focus,
             risk_vectors,confirmed,notes,feed_status
      FROM alignment_orgs) t;\"" > "$WORKDIR/orgs_dump.json"
  python3 - "$WORKDIR/orgs_dump.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert len(d)>=20, f"suspiciously few orgs: {len(d)}"
print(f"  {len(d)} orgs | {sum(1 for o in d if o.get('feed_kind')=='rss')} with rss feeds")
PY
  c_info "building org directory"
  ( cd "$WORKDIR" && python3 build_orgs.py )
  check_js orgs_content.html
  publish_file "ai-alignment-orgs" "orgs_content.html"
}

do_research(){
  c_info "building research library"
  ( cd "$WORKDIR" && python3 build_research.py ) || { c_warn "build_research.py failed/skipped"; return 0; }
  publish_file "ai-safety-research" "research_content.html"
}

do_pages(){
  for entry in "${CANONICAL_PAGES[@]}"; do
    local slug="${entry%%|*}" file="${entry##*|}"
    if [ -f "$WORKDIR/$file" ]; then
      check_js "$file"
      publish_file "$slug" "$file"
    else
      c_warn "skip $slug — $file not present"
    fi
  done
}

do_verify(){
  c_info "verifying live pages"
  local slugs=(ai-problems-index ai-risk-atlas ai-risk-atlas-detail ai-alignment-orgs ai-environmental-impact
               ai-datacenter-action ai-consciousness ai-moral-patienthood ai-fallacies
               ai-creativity ai-copyright ai-benefits ai-non-problems ai-safety-research
               agentic-ai-security-map)
  local fail=0
  for s in "${slugs[@]}"; do
    local code len
    code=$(curl -s -o /dev/null -w '%{http_code}' -L --max-time 25 "https://themultiverse.school/x/$s")
    len=$(psql_q "$PAGES_ROLE" "SELECT length(content_html) FROM pages WHERE slug='$s';" | tr -d ' \r')
    if [ "$code" = "200" ] && [ "${len:-0}" -gt 2000 ]; then
      c_ok "$s  (HTTP $code, ${len} bytes)"
    else
      c_err "$s  (HTTP $code, len=${len:-?})"; fail=1
    fi
  done
  [ "$fail" = "0" ] && c_ok "all pages healthy" || die "some pages unhealthy"
}

# ---------------------------------------------------------------------------
cmd="${1:-}"
case "$cmd" in
  dump)     do_dump ;;
  atlas)    do_atlas ;;
  orgs)     do_orgs ;;
  research) do_research ;;
  page)     [ $# -ge 3 ] || die "usage: deploy.sh page <slug> <file>"; check_js "$3"; publish_file "$2" "$3" ;;
  pages)    do_pages ;;
  all)      do_atlas; do_orgs; do_research; do_pages; do_verify ;;
  verify)   do_verify ;;
  *)        sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
