# Where all the research lives

Everything that backs a claim on the site, and where to find it. The **database is the source
of truth**; the files below are the working artifacts that produced it.

---

## 1. The source of truth — Postgres

Hetzner, container `$AIPI_PG_CONTAINER`, DB `$AIPI_DB`.

| Table | Owner | What it holds |
|---|---|---|
| `real_issues` | `school` | The 53 risks: prose + `score_*` grades + `score_markers` (KPIs) + `score_cases` (timeline events) |
| `real_issues_sources` | `school` | Per-risk source links (`issue_id`, `title`, `url`, `display_order`) |
| `real_issues_rebuttals` | `school` | Counter-arguments per risk |
| `research_library` | `school` | 98 papers (Anthropic / Apollo / METR / UK AISI…) — cols: `org`, `title`, `year`, `type`, `topic`, `key_finding`, `url`, `authors`, `dual_use_note` |
| `accountability_map` | `school` | Geocoded complaint/accountability records |
| `ai_accountability_registry` | `school` | Entity → responsibility mapping |
| `pages` | **`school`** | The published HTML for every `/x/<slug>` page |
| `risk_scoreboard` | `school` | **RETIRED** — the old 15-row front-page scoreboard. Left in place, read by nothing. |

Read the current state any time:
```bash
ssh "$AIPI_SSH_HOST" "docker exec -i $AIPI_PG_CONTAINER psql -U school -d $AIPI_DB -c \
  \"SELECT score_state, count(*) FROM real_issues GROUP BY 1 ORDER BY 2 DESC;\""
```

---

## 2. The working directory — `~/backups/ai-risk-db-factcheck/`

This is where all research and builds actually happen. Durable, not a temp dir.

### Research outputs (raw fan-out results — the provenance of every marker & case)

| File | What it is |
|---|---|
| `fanout_results.json` | **KPI markers** for all 52 risks (12-agent fan-out) — `{id, better[], worse[], trend_suggestion, trend_reason}` |
| `canary_results.json` | The 4-risk canary that validated the marker methodology before the full run |
| `cases_results.json` | **Case studies** — first pass, ~146 dated incidents (13-agent fan-out) |
| `granulate_results.json` | **Timeline granulation** — 200 additional dated events (18-agent Tavily deep-dive) |
| `scorecard_grades.json` | The hand-authored state/trend/confidence grade for each of the 52 risks |
| `datacenter_cases.json` | 22 verified data-center siting cases (Local Action page) |
| `research_lib_dump.json` | Dump of `research_library` used to build the Research page |
| `atlas_issues.json` | The live DB dump the atlas builder reads (regenerate with `./deploy.sh dump`) |
| `*_batches.json`, `*_risks.json` | The batch inputs handed to each fan-out (what each agent was asked) |

### Workflow scripts (the actual research harnesses)

| File | What it ran |
|---|---|
| `markers_fanout.js` | 12 opus agents → KPI markers, verbatim quote required per marker |
| `cases_fanout.js` | 13 opus agents → concrete dated case studies |
| `granulate_fanout.js` | 18 opus agents → deepen every timeline (Tavily-heavy, dedup against existing) |

Re-run one with `Workflow({scriptPath: "<file>"})`. Each embeds its batches, so it is
reproducible as-is. Agent transcripts and per-agent results live under
`~/.claude/projects/-Users-annhoward/…/subagents/workflows/<run-id>/journal.jsonl`.

### Canonical page sources (hand-maintained HTML, published as-is)

| File | Publishes to |
|---|---|
| `env7_content.html` | `ai-environmental-impact` (the 7-tab field guide) |
| `moral_content.html` | `ai-moral-patienthood` |
| `dca_content_v2.html` | `ai-datacenter-action` |
| `index_live.html` | `ai-problems-index` (the SPA hub shell) |
| `atlas_content.html` / `atlas_detail.html` | `ai-risk-atlas` / `ai-risk-atlas-detail` (**generated** — don't hand-edit) |

Older `env2..env6_content.html` are superseded revisions kept for history.

### Apply-SQL (every DB mutation is a saved, replayable file)

`apply_*.sql` — one per change: `apply_scorecard.sql`, `apply_fanout_markers.sql`,
`apply_cases.sql`, `apply_granulate.sql`, `apply_confirmed.sql`, `apply_threat_kind.sql`,
`apply_audit_fixes.sql`, `apply_xnav.sql`, … Each is the exact statement that produced the
current data, so any step can be re-read or replayed.

### The narrative record

`enrichment_loop_log.md` (mirrored here as `docs/build-log.md`) — the full running log: what was
researched, what each audit found, what was dropped and why, and the reasoning behind every
editorial call. **Start here when you want to know why something is the way it is.**

---

## 3. Search tooling

Native web search gets exhausted on long sessions; **Tavily** is the workaround and the primary
research tool for the fan-outs.

```bash
source ~/.tavily.env   # holds TAVILY_API_KEY (chmod 600)
curl -s https://api.tavily.com/search \
  -H "Authorization: Bearer $TAVILY_API_KEY" -H "Content-Type: application/json" \
  -d '{"query":"…","max_results":8,"search_depth":"advanced"}'
```
Also `POST /extract` with `{"urls":[…]}` to pull readable text from JS-heavy pages that `curl`
can't render (used to verify OpenAI's figures, which 403 both WebFetch and curl).

---

## 4. How a claim gets on the site

1. **Research** — a fan-out (or hand research) proposes markers/cases with a source URL and a
   verbatim quote.
2. **Independent verification** — resolve-check *every* URL; spot-check quotes against the live
   page. A 403 from a real institution (RAND, NYT, Ofcom, OpenAI, GAO) is fine. A 404, an
   unconfirmable host, or a page missing the quote → **drop or re-source**.
3. **Audit** — a separate reviewer pass looks for: case-studies-masquerading-as-KPIs, hype
   sourcing (SEO "statistics 2026" sites), obscure/nonsensical metrics, entity mismatches, and
   wrong-direction filing.
4. **Write** — an `apply_*.sql` mutation against `real_issues`.
5. **Build + publish** — `./deploy.sh atlas`.
6. **Verify live** — render checks on the galactic-map theme and 360px mobile; router matrix if
   navigation changed.

Known accepted weak spots (candidates for upgrade to primaries): a Gartner figure cited via a
trade blog, three Wikipedia-sourced uncontroversial facts, one DoD-budget Substack. All had
their quotes verified; only the *publisher tier* is second-best.

---

## 5. Related project docs

- `../README.md` — architecture, data model, build pipeline, verification discipline
- `build-log.md` — the full chronological record
- `~/.claude/projects/-Users-annhoward/memory/ai-risk-kb-factcheck.md` — condensed operational
  memory (gotchas, credentials pointers, prior fact-check findings)
