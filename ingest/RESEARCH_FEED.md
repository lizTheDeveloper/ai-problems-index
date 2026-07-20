# Alignment-research feed + org registry

A **sibling source** to the news ingester (`feeds.py` / `pipeline.py`, built in a parallel
session). Where that pulls *news about AI risk*, this pulls *alignment research* — and routes it
through the exact same staging queue, classifier, Opus gate and human apply step.

**This makes zero edits to `pipeline.py`, `feeds.py`, `classify_daemon.py` or `opus_review.py`.**

## The one idea

The org directory and the per-risk research feed are **two views of one dataset**:

```
alignment_orgs  ──┬──▶  /x/ai-alignment-orgs      "who's working on what" (public page)
                  └──▶  research_feeds.py         pull each org's RSS → news_queue → scorecard
```

An org row carries both its public description (`name`, `focus`, `risk_vectors`) and its
machine-readable `feed_url`. **Add an org and it appears on the page *and* starts being ingested.**
There is no second list to maintain.

## Files

| File | What it is |
|---|---|
| `orgs_schema.sql` | `alignment_orgs` table + `risk_org_coverage` view (risk → how many orgs) |
| `research_feeds.py` | The feed. Same `collect_all()` contract as `feeds.py` |
| `research_pipeline.py` | Shim: rebinds `pipeline.feeds` and `pipeline.prefilter`, then calls `pipeline.run()` |
| `../builders/build_orgs.py` | Builds the public directory page from the registry |

## Sources

1. **The org registry** — every `alignment_orgs` row with `feed_kind='rss'`. The highest-signal
   source, because it is curated and each item arrives already attributable to an org.
2. **arXiv**, via ~22 *targeted* queries (`"scalable oversight"`, `"deceptive alignment"`,
   `"sandbagging"`…). Deliberately not whole categories — `cs.LG` is ~99% irrelevant here.
3. **Alignment Forum / LessWrong** RSS, where a lot of alignment work appears first.

## Why a separate pre-filter

`pipeline.prefilter` requires a *harm/incident* word (`hack|breach|lawsuit|…`). That is right for
news and wrong for research: it would throw away "Scalable Oversight via Recursive Reward Modeling"
because nothing bad happens in the title. `research_feeds.prefilter` instead requires an AI signal
plus a *research* signal (`alignment|interpretab|oversight|evals|sandbag|…`).

Expect some false positives (an "AIS-Aligned Passive Acoustic" ship-tracking paper matched
`aligned` in testing). That is intentional — the local Qwen router and the Opus relevance gate
downstream are the precision stages; this one is recall-oriented and free.

## Run it

```bash
# one-time
psql < orgs_schema.sql

# refresh the directory + feed health, on demand (no scheduler by design)
python3 research_pipeline.py --dry     # collect + filter, write nothing
python3 research_pipeline.py           # stage into news_queue (status='new')
python3 research_feeds.py --health     # re-check every org feed, write status back to the registry
```

Then the shared downstream stages take over unchanged: `classify_daemon.py` (local Qwen routes
each item to a risk id) → `opus_review.py` (relevance gate) → human review → apply.

Research items are distinguishable in `news_queue` by their feed label: `org:<slug>`,
`arxiv:<query>`, `community:af|lw`.

## Feed health is data

`research_feeds.py` writes `feed_status` / `feed_checked_at` / `feed_items_seen` back to
`alignment_orgs`. The directory page renders this as a **tracked / page only / no feed** badge, so
the page is honest about which orgs we can actually keep current — and `--health` tells you when an
org silently changes its CMS and drops its RSS.

## Database role

Everything runs as **`school`**, which now owns `real_issues`, `pages`, `alignment_orgs` **and
`news_queue`**. `news_queue` was created campus-owned; ownership was transferred (with `campus`
retained as a grantee, and it is a superuser regardless) so the whole pipeline runs under one role.

Rollback, if ever needed:
```sql
ALTER TABLE news_queue OWNER TO campus;
ALTER SEQUENCE news_queue_id_seq OWNER TO campus;
```
