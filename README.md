# AI Problems Index

A skeptical, source-verified knowledge base of AI risks, benefits, and non-problems,
published as a single-page app at **[themultiverse.school/x/ai-problems-index](https://themultiverse.school/x/ai-problems-index)**.

Its flagship is the **Risk Atlas** — a "how are we doing?" scorecard over 52 AI risks. Every
risk carries a live grade, KPI trend markers, a granular timeline of real dated incidents,
its own navigable page, and links to primary evidence for every claim.

> **Brand promise: measured, sourced, not recycled hype.** Every quantitative claim is fetched
> and quote-verified against a primary source. Grades are editorial calls, stated plainly, with
> an explicit confidence tag. Where the alarming version of a risk isn't demonstrated, we say so.

**Start here:** [`docs/RESEARCH.md`](docs/RESEARCH.md) maps every piece of research and data; [`docs/build-log.md`](docs/build-log.md) is the full chronological record; `./deploy.sh` ships it.

This repo is **documentation + build tooling**. The live content lives in Postgres (see §1);
these builders read it and emit the published HTML.

---

## Current state (2026-07-19)

| | |
|---|---|
| Risks in the atlas | **52** (53 in DB; `ai-environmental-footprint` excluded — it has its own tab) |
| Timeline events | **344** real dated incidents (avg **6.6**/risk, range 5–8) |
| KPI markers | **180** (getting-better / getting-worse signals) |
| State | 5 losing · 31 slipping · 12 holding · 4 unknown |
| Evidence | 37 confirmed · 9 contested · 6 estimated |
| Threat level | 12 Severe · 14 High · 18 Moderate · 8 Low |
| Danger kinds | 12 categories |

---

## 1. Where everything lives

| Thing | Location |
|---|---|
| Live site | `https://themultiverse.school/x/<slug>` |
| CMS + data | Postgres on Hetzner, container `$AIPI_PG_CONTAINER`, DB `$AIPI_DB` |
| Page HTML | table `pages` (`content_html`) — owned by **`school`** |
| Risk data | tables `real_issues`, `real_issues_sources` — owned by **`school`** |
| Research library | table `research_library` — owned by **`school`** |
| Working dir (builders, apply-SQL, backups) | `~/backups/ai-risk-db-factcheck/` |
| This repo | `~/SRC/ai-problems-index/` |

**Ownership:** everything — `pages` and all the KB tables — is owned by **`school`**, so every
read and write uses `-U school`. (Historically the KB tables were owned by `campus`, a leftover
from the Neon→Hetzner migration; they were reassigned to `school` so there is a single owner.
`campus` retains read/write grants so nothing that predates the change breaks.)

Publish pattern:
```bash
ssh "$AIPI_SSH_HOST" "docker exec -i $AIPI_PG_CONTAINER psql -U school -d $AIPI_DB -q" < apply_X.sql
```
`apply_X.sql` sets `content_html` via a dollar-quoted string
(`UPDATE pages SET content_html=$tag$…$tag$ WHERE slug='…'`). Choose a `$tag$` that does not
appear in the HTML.

---

## 2. The pages (all under `/x/`)

`ai-problems-index` is an **SPA shell**: it hash-routes and `fetch()`es the other pages into
tabs. Each page also works standalone as a deep link.

| Slug | Tab | What it is |
|---|---|---|
| `ai-problems-index` | (hub) | SPA shell: hero, topic cards, tab bar, router |
| `ai-risk-atlas` | Risk Atlas | **The scorecard** — 52 graded risks, list + per-risk pages (§4) |
| `ai-environmental-impact` | Environment | 7-tab field guide on AI energy/water/grid |
| `ai-datacenter-action` | Local Action | Data-center siting fights + civic leverage ladder |
| `ai-consciousness` | Consciousness | 10 theories of mind + clickable milestone timeline |
| `ai-moral-patienthood` | Moral Patienthood | s-risk, asymmetry matrix, model welfare |
| `ai-fallacies` | Fallacies | 18 recurring bad arguments in AI discourse |
| `ai-creativity` | Creativity | What generative models do/don't do to creative work |
| `ai-copyright` | Copyright | Claim↔rebuttal + consent-based-AI resources for artists |
| `ai-benefits` | Benefits | The upside ledger |
| `ai-non-problems` | Non-Problems | 13 things blamed on AI that are debunked/misunderstood/not-AI |
| `ai-safety-research` | Research | 98-paper filterable library (Anthropic/Apollo/METR/AISI…) |
| `agentic-ai-security-map` | Accountability | Who-to-hold-responsible field map |

**Shared cross-nav:** `builders/nav_block.html` (`nav.xnav`) is prepended to every topic page so
each reaches the hub + siblings when visited directly. It self-hides inside the SPA via
`.apx .xnav{display:none}`.

---

## 3. Data model — `real_issues`

Base columns are the original KB content; `score_*` columns are the scorecard layer.

| Column | Meaning |
|---|---|
| `id`, `title`, `summary`, `description` | identity + prose |
| `why_it_matters`, `what_being_done` | context prose |
| `status`, `icon` | legacy type tag (Critical/Emerging/Ongoing — **no longer rendered**), FA icon |
| `score_state` | **where it stands**: `losing`/`slipping`/`holding`/`contained`/`unknown` |
| `score_trend` | **which way**: `down`/`flat`/`up`/`q` (unmeasured) |
| `score_conf` | **how firm**: `confirmed` (documented cases) / `measured` / `estimated` / `contested` |
| `score_note` | one-line assessment — the editorial call |
| `score_threat` | severity, independent of trajectory: `Severe`/`High`/`Moderate`/`Low` |
| `score_kind` | danger category (12, e.g. "Cyber & misuse", "Loss of control") |
| `score_markers` | jsonb `{better:[…], worse:[…]}` — KPI trend signals |
| `score_cases` | jsonb `[…]` — dated real incidents → the per-risk timeline |

```jsonc
// score_markers
{ "better": [ {"m":"KPI as one sentence","q":"verbatim quote from the page","src":"Publisher, Year","url":"https://…"} ],
  "worse":  [ … ] }

// score_cases  (rendered as the timeline, sorted chronologically)
[ {"title":"headline","when":"May 2024","what":"1–2 sentences","src":"Publisher, Year","url":"https://…","q":"optional quote"} ]
```

`q` (verbatim quote) is required on markers: it forces the researcher to actually fetch the page
and gives a spot-checkable artifact. It surfaces as the link's hover title.

**Two deliberately different things:**
- **Markers = KPIs / broad industry signals** — rates, %, adoption counts, benchmark scores,
  survey stats. *Not* anecdotes. Prefer arXiv, Stanford AI Index, Anthropic, METR, CSET, UK AISI,
  Pew, NCMEC, GAO, EFF. Avoid SEO-aggregator "statistics 2026" sites.
- **Cases = concrete dated incidents** — the vivid "here's an actual time this happened." These
  build the timeline, and their existence is what upgrades a risk's evidence tier to `confirmed`.

**Standing CSAM constraint:** `generative-ncii-csam` and any related markers/cases stay framed as
*reported/alleged*, cite only mainstream reporting or official investigations (Ofcom, state AGs,
NCMEC report counts), and carry **no graphic detail**.

---

## 4. The Risk Atlas is a mini-SPA

### ⚠ It is published as TWO pages
For load speed the atlas is split, and **both must be published together**:

| Slug | Size | Contents |
|---|---|---|
| `ai-risk-atlas` | ~103 KB | light **list view** — tiles, filters, router |
| `ai-risk-atlas-detail` | ~664 KB | the **52 per-risk pages**, fetched on demand |

The list page fetches the detail bundle once in the background (`loadBundle()`), parses out
each `.rx-page`, and injects just the opened risk. If the detail page is stale or missing,
every risk page breaks with "Couldn't load this page." `./deploy.sh atlas` publishes both and
**aborts** if `atlas_detail.html` is missing — never publish one without the other.

`ai-risk-atlas` is itself a router nested inside the hub SPA:

- **List view** (`#rx-list`) — filterable grid of navigational tiles (state filter buttons, a
  "Kind" dropdown, search). Clicking a tile navigates to that risk's page.
- **Per-risk page** (`#p-<id>`) — a real page: hero (icon, title, threat + kind tags,
  State/Trend/Evidence scoreline), assessment, description, markers, **timeline**, why it matters,
  what's being done, sources, "← Back to all risks".

**Routing — a pure function of `location.hash`:**
- Embedded in the hub → `#atlas/<risk-id>`. Standalone → `#<risk-id>`.
- The atlas reads the **last** hash segment; if it matches one of the 52 ids → show that page,
  else the list. Re-derived on *every* `hashchange`, never remembered — so the hub's
  cached/detached-pane reattach self-heals.
- The **hub** router is sub-route aware: `route()` splits the hash on `/`, uses segment 0 as the
  tab id (existing single-segment hashes unchanged), and lets the loaded page handle the rest. A
  `_curTab` guard avoids a reload flash when only the sub-route changes.
- Browser Back and deep-links work in both contexts.

**Timeline ordering:** `case_sortkey()` parses `(year, month)` from the freeform `when` string
(month names and `Qn` quarters; undated month → start of year, undated entirely → sorts last).
Year-only sorting was not enough once timelines got dense — it put "April 2024" before
"February 2024".

### ⚠ CSS-in-Python gotcha (cost us a real bug)
The atlas builder's `STYLE` block **must be a raw string** (`r"""…"""`). A CSS
`content:"\f058"` (Font Awesome glyph) inside a *non-raw* Python string becomes a literal
form-feed byte (0x0C) — a CSS parse error that silently kills **every rule after it**. That
killed the detail-view routing rules, so the list wouldn't hide. Same applies to `\t`, `\n`,
etc. in any `content:` value.

---

## 5. Build & publish

### The easy way — `./deploy.sh`

```bash
./deploy.sh atlas       # dump DB → build → publish BOTH atlas pages (list + detail)
./deploy.sh research    # build + publish the Research Library page
./deploy.sh pages       # publish the hand-maintained canonical pages
./deploy.sh all         # everything, then verify
./deploy.sh verify      # health-check all 14 live pages (HTTP + byte count)
./deploy.sh dump        # refresh atlas_issues.json only
./deploy.sh page <slug> <file>      # publish any HTML file to any slug
./deploy.sh <cmd> --dry-run         # build + validate, write nothing
```

It picks a safe dollar-quote tag automatically, syntax-checks the page's JS with `node`
before publishing (aborts on error), publishes as the correct role, and reads back the live
byte count to confirm. Override the working dir with `AIPI_WORKDIR=…`.

### What it does under the hood

Everything is DB-driven: builders read a JSON dump and emit `content_html`.

```bash
cd ~/backups/ai-risk-db-factcheck

# 1) dump WITH all score_* columns + sources
ssh "$AIPI_SSH_HOST" "docker exec -i $AIPI_PG_CONTAINER psql -U campus -d $AIPI_DB -At -c \"
  SELECT json_agg(t ORDER BY t.title) FROM (
    SELECT i.id,i.title,i.status,i.icon,i.summary,i.description,i.why_it_matters,i.what_being_done,
           i.score_state,i.score_trend,i.score_conf,i.score_note,i.score_markers,
           i.score_threat,i.score_kind,i.score_cases,
           COALESCE((SELECT json_agg(json_build_object('title',s.title,'url',s.url)
                     ORDER BY s.display_order,s.id)
                     FROM real_issues_sources s WHERE s.issue_id=i.id),'[]'::json) AS sources
    FROM real_issues i) t;\"" > atlas_issues.json

# 2) build → atlas_content.html   (prepends nav_block.html; excludes ai-environmental-footprint)
python3 build_atlas.py

# 3) publish as -U school (dollar-quoted UPDATE on pages)
```

Other builders in `builders/`: `build_research.py` (research library page), `nav_block.html`
(shared cross-nav), `gen_scoreboard.py` (**retired** — the old front-page scoreboard; the atlas
is now the single scorecard, and the `risk_scoreboard` table is left in place but unread).

**Reusable timeline component:** `.risktl` (consciousness page — clickable milestones that expand
to a facet breakdown + evidence links) and `.ctl-*` (atlas per-risk timelines). Good candidate for
other risk pages.

---

## 6. Verification discipline

This is the part that protects the brand. Skipping it is how the project breaks.

1. **Never trust subagent self-reports.** After any research fan-out, independently:
   resolve-check every URL, and spot-check load-bearing quotes against the live page. A 403 from
   a real institution (RAND, NYT, Ofcom, OpenAI, GAO) is fine — the page is genuine and just
   bot-blocked. A 404, an unreachable host you can't otherwise confirm, or a page that doesn't
   contain the quote → **drop or re-source it.**
2. **Require a verbatim quote per marker.** It forces a real fetch and leaves something checkable.
3. **Integrity-check restructures** with a token diff (strip tags, compare visible text) so no
   content silently drops when layout changes.
4. **Test the SPA router matrix** after any routing change: cold deep-link → detail;
   list→detail→browser-Back→list; detail→other tab→back→list (must not be stale); standalone
   deep-link. Then check the galactic-map theme and 360px mobile (no horizontal overflow).
5. **Allow asymmetry.** If a risk genuinely has little "getting better" evidence, ship fewer
   markers — never pad to fake balance. Same for cases.
6. **Search:** Tavily, when native web search is exhausted —
   `source ~/.tavily.env && curl -s https://api.tavily.com/search -H "Authorization: Bearer $TAVILY_API_KEY" …`

---

## 7. Repo layout

```
README.md                        this document
builders/
  build_atlas.py                 Risk Atlas builder (list + per-risk pages + timelines)
  build_research.py              research library page builder
  gen_scoreboard.py              RETIRED front-page scoreboard generator
  nav_block.html                 shared cross-nav strip prepended to topic pages
data/
  atlas_issues.snapshot.json     snapshot of the atlas DB dump (all 52 risks + score_*)
  page-sources/env7_content.html canonical source of the Environment field-guide page
docs/
  RESEARCH.md                    WHERE ALL THE RESEARCH LIVES — data, fan-out outputs, tooling
  build-log.md                   full running build log — every change, decision, and audit
deploy.sh                        one-command build + publish + verify
```

`docs/build-log.md` is the detailed provenance: what was researched, what was verified, what was
dropped and why, and the reasoning behind each editorial call.

---

## 8. History

Highlights (full detail in `docs/build-log.md`):

- **2026-07-16** — KB fact-check: fixed 22 misattributions (Hendrycks→Anwar et al.), dead links,
  overstated claims. Method: fetch-and-compare every source.
- **07-17** — Neon→Hetzner migration; the whole index published to `/x/` pages; research library
  ingested.
- **07-18** — Environment page rebuilt from first-principles engineering (not cited journalism);
  cross-nav added to all pages; front page reframed from vanity metrics to a scorecard.
- **07-19** — Atlas became the single scorecard (state/trend/evidence); threat + kind tags; KPI
  markers researched and audited; case studies added; `confirmed` evidence tier; consciousness
  timeline with expandable detail views; atlas rebuilt as a mini-SPA with per-risk pages; and a
  Tavily deep-dive that granulated every timeline to ~6.6 dated events.
