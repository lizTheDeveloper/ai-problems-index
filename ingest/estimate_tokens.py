#!/usr/bin/env python3
"""Estimate the Opus-gate token cost of an ingest run, from the REAL prompts.

The local Qwen first pass is free (self-hosted) but time-bound; the Opus relevance gate is the
only step that spends API tokens. This reconstructs opus_review.py's actual prompt — same SYSTEM
string, same per-risk page with its real existing timeline, same candidate block — and measures
it, rather than guessing a per-item constant.

    python3 estimate_tokens.py                # estimate from a live collect
    python3 estimate_tokens.py items.json     # estimate from a saved item set

Token counting: Anthropic's tokenizer is not bundled here, so this uses chars/3.6, which is
conservative for English prose with URLs (real ratio is typically 3.8-4.2 chars/token). Treat
the output as an upper bound, and note it is an ESTIMATE, not a billed figure.
"""
import os, sys, json, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import research_feeds as rf
import opus_review

CHARS_PER_TOKEN = 3.6

# claude-opus-4-8 list pricing, USD per million tokens.
PRICE_IN, PRICE_OUT = 5.00, 25.00


def toks(s):
    return int(len(s or "") / CHARS_PER_TOKEN) + 1


def main():
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        items = json.load(open(sys.argv[1]))
        print(f"loaded {len(items)} items from {sys.argv[1]}")
    else:
        print("collecting live (org feeds + page/sitemap scrape)…")
        items = rf.org_feeds() + rf.page_feeds()
    kept = [i for i in items if rf.prefilter(i)]
    print(f"raw={len(items)}  past prefilter={len(kept)}")

    # Risks: candidates get routed across risks by Qwen. We do not know the split in advance,
    # so model it as an even spread over the risks that actually exist — the per-call overhead
    # (SYSTEM + risk page) is what this is sensitive to, and that scales with CALLS not items.
    risk_rows = [r for r in rf.psql(
        "SELECT id||E'\\t'||coalesce(title,'')||E'\\t'||coalesce(summary,'') FROM real_issues").splitlines() if r]
    risks = [r.split("\t") for r in risk_rows]
    n_risks = len(risks)

    # real existing-timeline text per risk (this is included in every call for that risk)
    tl = {}
    for line in rf.psql(
            "SELECT id||E'\\t'||count(*)::text||E'\\t'||coalesce(sum(length(c->>'title'))+sum(length(coalesce(c->>'when',''))),0)::text "
            "FROM real_issues, jsonb_array_elements(coalesce(score_cases,'[]'::jsonb)) c GROUP BY id").splitlines():
        p = line.split("\t")
        if len(p) == 3:
            tl[p[0]] = (int(p[1]), int(p[2]))

    system_t = toks(opus_review.SYSTEM)

    # per-candidate block, measured on the real items
    cand_chars = 0
    for c in kept:
        cand_chars += len(
            f"CANDIDATE id=000000\n  title: {c.get('title','')}\n  source: {c.get('source','')}\n"
            f"  blurb: {(c.get('blurb') or '')[:300]}\n  url: {c.get('url','')}\n"
            f"  first-pass guess: worse — routed by first-pass model on topical match")
    cand_t = int(cand_chars / CHARS_PER_TOKEN)

    # per-risk page overhead, summed over risks that get at least one candidate
    per_call_over = 0
    for rid, title, summary in risks:
        n, chars = tl.get(rid, (0, 0))
        page_chars = len(f"RISK: {title}  (id={rid})\nSUMMARY: {summary}\n\nEXISTING TIMELINE (do not duplicate these):\n") \
                     + chars + n * 8
        per_call_over += system_t + int(page_chars / CHARS_PER_TOKEN)

    # opus_review batches per risk: one call per risk holding all its candidates
    calls = min(n_risks, max(1, len(kept)))
    overhead_t = int(per_call_over * (calls / max(n_risks, 1)))

    in_t = overhead_t + cand_t
    # output: kept items get a full norm object (~90 tok), dropped get a short reason (~25 tok).
    # The gate is deliberately strict; assume 35% survive.
    keep_rate = 0.35
    out_t = int(len(kept) * (keep_rate * 90 + (1 - keep_rate) * 25))

    # Not every prefiltered item reaches Opus: the local model routes each to a risk or to
    # 'none', and 'none' is dropped for free. Measured drop rate on a real sample was ~1 in 6.
    QWEN_DROP = float(os.environ.get("AIPI_QWEN_DROP", "0.35"))
    to_opus = int(len(kept) * (1 - QWEN_DROP))
    scale = to_opus / max(len(kept), 1)
    cand_t = int(cand_t * scale)
    out_t = int(out_t * scale)
    in_t = overhead_t + cand_t

    cost = in_t / 1e6 * PRICE_IN + out_t / 1e6 * PRICE_OUT
    print(f"""
Opus relevance gate — estimate for ONE run
  candidates entering the gate : {len(kept):,}
  Opus calls (batched by risk) : {calls}
  input tokens                 : {in_t:,}
     of which per-call overhead: {overhead_t:,}  (SYSTEM + risk page + existing timeline)
     of which candidate text   : {cand_t:,}
  output tokens                : {out_t:,}   (assuming ~{int(keep_rate*100)}% kept)
  ------------------------------------------------------------
  estimated cost               : ${cost:,.2f}   (@ ${PRICE_IN}/M in, ${PRICE_OUT}/M out)

  local first pass (free, no tokens):
     hetzner CPU box, qwen3:4b  : {len(kept):,} x ~75s   = {len(kept)*75/3600:>6,.1f} h
     M3 Max MLX, Qwen3-30B-A3B  : {len(kept):,} x ~0.78s = {len(kept)*0.78/60:>6,.1f} min   <-- measured
  after local routing, ~{int((1-QWEN_DROP)*100)}% reach the Opus gate: {to_opus:,} candidates

  NOTE: chars/{CHARS_PER_TOKEN} approximation, no tokenizer -> treat as an upper bound.
""")


if __name__ == "__main__":
    main()
