# AI-Risk Atlas — autonomous news ingester

A twice-weekly pipeline that pulls AI-risk news, filters it for free with a locally-hosted
Qwen, routes each story to the right risk, has **Opus judge true relevance in batches**, and
queues approved items for **your one-command confirm** before anything touches the live atlas.

Human gate: Opus-gated → review report → you run `deploy.sh ingest-apply`. Nothing auto-publishes.

```
[cron 2×/week on hetzner]
  pipeline.py     ingest broad AI feeds → dedupe (canonical URL hash) → keyword pre-filter → stage (news_queue, status='new')
  classify_daemon.py   [on llm-inference box, async]  local Qwen routes each → risk id + polarity, or drops 'none'   → status='classified'
  enrich.py       resolve to primary URL, resolve-check, capture a verbatim quote   → status='enriched'
  opus_review.py  Opus sees the whole risk page + candidates, keeps only TRULY on-topic ones, normalizes to {title,when,what,pol,q,url,src} → status='approved'
  build_review.py emit a review report page (/x/ai-atlas-review) of approved cards
  --- you review, then:
  apply.py [ids]                  merge approved → real_issues.score_cases → deploy.sh atlas
```

## Status (2026-07-20)

**Working & validated on real data:**
- `feeds.py` — broad AI-incident feeds (Google News RSS, GDELT, Hacker News, arXiv). ~1,100 raw / 14 days.
- `pipeline.py` — ingest → dedupe → keyword pre-filter → stage. **Live run: 1,094 raw → 1,045 unique → 304 pre-filtered → staged.** Pre-filter cuts ~70% noise.
- `classify_daemon.py` — local Qwen first pass (qwen3:4b on the `llm-inference` hcloud box — host/endpoint in `AIPI_OLLAMA_URL` (see `.aipi.env`), free/no-key). **Validated:** correctly routed real headlines ("agent security gap"→ai-enabled-hacking/worse, "AI misinformation harms refugees"→automated-manipulation/worse) and dropped a product piece as `none`. ~75s/item on the CPU box — slow but async; ~304 items ≈ 6h, fine with 3–4 days between cycles.
- `opus_review.py` — the batch relevance gate (Opus via the Anthropic key already on hetzner, `claude-opus-4-8`). Built; the relevance test is "does this story truly belong to THIS risk", NOT "does it prove the risk is real". *Not yet run end-to-end.*
- `schema.sql` — `news_queue` staging table (nothing here is live).

**Now built & tested (this session):** enrich.py (real-URL resolve + verbatim quote — tested on live URLs), opus_review.py run end-to-end (correctly DROPPED aggregator-stats items as off-bar), build_review.py (review-queue page), apply.py (merge + deploy, standalone so it doesn't touch deploy.sh). news_queue gained final_url + qwen_quote columns.

**Remaining before going autonomous:**
1. **Real-URL feed volume.** enrich.py already drops opaque Google-News redirects; the live coverage should come from real-URL feeds (GDELT / HN / arXiv / outlet RSS — an agent is supplying a feed set). Point feeds.py at those (drop Google News).
2. **Near-dup dedupe.** One event surfaces from many outlets; URL-hash alone won't catch it. Have Opus dedupe within each risk batch ("these may be the same event — keep the best-sourced") and check against `status='approved'`-but-unpublished rows.
3. **Run the Opus gate once** end-to-end on a real batch; confirm the `decisions[]`/`norm` shape.
4. **`build_review.py` + `deploy.sh ingest-apply`** — the human gate is a review *report* + a one-command apply (the /x/ pages are static DB rows with no POST endpoint, so a confirm *button* can't work).
5. **Wire it:** `classify_daemon` as a systemd service on the llm-inference box; `pipeline.py`→`opus_review.py`→`build_review.py` as a 2×/week cron on hetzner.

## Config
Infra via env or gitignored `.aipi.env`: `AIPI_SSH_HOST`, `AIPI_PG_CONTAINER`, `AIPI_DB`,
`AIPI_KB_ROLE=school`. Ingester extras: `AIPI_OLLAMA_URL` (default localhost:11434),
`AIPI_QWEN_MODEL` (qwen3:4b), `AIPI_OPUS_MODEL` (claude-opus-4-8), `ANTHROPIC_API_KEY`.

## Infra found
- **Free first-pass model:** `qwen3:4b` (and 8b, 1.5b, qwen3-nothink) on Ollama at
  the `llm-inference` hcloud box (CPU-only, open/no-key) — endpoint set via `AIPI_OLLAMA_URL` in the gitignored `.aipi.env`.
- the separate 32B hcloud box now runs custom game models (llama.cpp), not a plain Qwen — not used here.
- Opus for the gate: an `ANTHROPIC_API_KEY` already present on the DB host (sees `claude-opus-4-8`).
