#!/usr/bin/env python3
"""Run the existing staging pipeline with ALIGNMENT RESEARCH as the source.

This deliberately makes ZERO edits to pipeline.py or feeds.py (the news ingester,
built in a parallel session). It reuses every stage of that pipeline — canonical-URL
dedupe, dedupe against already-published cases, news_queue staging — and only swaps:

  * the feed module   feeds.py          -> research_feeds.py   (org RSS + arXiv + AF/LW)
  * the pre-filter    news harm-words   -> research signal words

Everything downstream is unchanged and shared: the same news_queue rows, the same local
Qwen risk-routing daemon, the same Opus relevance gate, the same human apply step.
Research items are distinguishable by `source`/feed label (org:<slug>, arxiv:*, community:*).

Usage:
    python3 research_pipeline.py --dry     # collect + filter, touch nothing
    python3 research_pipeline.py           # stage into news_queue (status='new')
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline
import research_feeds

# Swap the source. pipeline.run() calls the module-global `feeds`, so rebinding it here
# redirects the whole pipeline without touching that file.
pipeline.feeds = research_feeds
pipeline.prefilter = research_feeds.prefilter

if __name__ == "__main__":
    dry = "--dry" in sys.argv
    print("• source: alignment research (org registry + arXiv + Alignment Forum/LessWrong)")
    fresh = pipeline.run(stage_only=dry)
    if dry:
        print(f"\n[dry run] {len(fresh)} items would be staged. Nothing written.")
        for it in fresh[:15]:
            print(f"   - [{it.get('feed','')}] {it.get('title','')[:100]}")
