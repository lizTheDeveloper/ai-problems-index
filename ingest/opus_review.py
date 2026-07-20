#!/usr/bin/env python3
"""Opus batch relevance gate. Reads news_queue rows the local Qwen routed to a risk
(status='classified'), groups them by risk, and once a risk has >= MIN_BATCH pending,
shows Opus the WHOLE risk page as if those events were added and asks the one question:
does each candidate TRULY belong to THIS risk's timeline?

The test is RELEVANCE, not validity: not "does this prove the risk is real", but
"is this news story genuinely about THIS specific risk, or only tangentially related".

Kept items → status='approved' with a normalized {title,when,what,pol} in `norm`.
Dropped items → status='rejected' with opus_reason. Nothing publishes here; approved
items go to the human review queue (build_review.py) and only merge on confirm.

Env: DB access (as pipeline.py) + ANTHROPIC_API_KEY. AIPI_OPUS_MODEL default claude-opus-4-8.
Run on the DB host (has the key): python3 opus_review.py [--min 2] [--risk <id>]
"""
import os, sys, json, re, subprocess, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import psql, psql_stdin, sq, _load_env
_load_env()

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL   = os.environ.get("AIPI_OPUS_MODEL", "claude-opus-4-8")
MIN_BATCH = 2
RISKS = {r["id"]: r for r in json.load(open(os.path.join(os.path.dirname(__file__), "risks.json")))}

def anthropic(system, user, max_tokens=4000):
    body = json.dumps({"model": MODEL, "max_tokens": max_tokens, "system": system,
                       "messages": [{"role": "user", "content": user}]}).encode()
    req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, headers={
        "x-api-key": API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        d = json.load(r)
    return "".join(b.get("text", "") for b in d.get("content", []))

SYSTEM = (
"You are the editorial gate for a skeptical, source-verified AI-risk atlas. Each risk has a "
"timeline of real, dated events. You are handed CANDIDATE news stories a first-pass model routed "
"to a given risk. Your ONE job: decide whether each candidate TRULY belongs on THIS risk's "
"timeline.\n\n"
"The test is RELEVANCE, not validity. NOT 'does this prove the risk is real'. The question is: is "
"this story genuinely a concrete instance/development OF THIS SPECIFIC RISK, or is it only "
"tangentially related, off-topic, generic AI news, marketing, or a better fit for a different risk? "
"Judge it as if it were already added to the page below: does it fit the page's actual subject?\n\n"
"Be strict. Drop: aggregator 'statistics' roundups, product launches, funding, opinion/hype with no "
"concrete event, duplicates of an event already on the timeline, and anything whose real subject is a "
"different risk. Keep only stories that are clearly, specifically about THIS risk.\n\n"
"For each KEPT story, normalize it to the timeline schema:\n"
"  title: <=12 words, concrete and specific (who/what)\n"
"  when:  the date/period as precise as the source allows (e.g. 'March 2026')\n"
"  what:  1-2 sentences on what concretely happened and why it belongs to THIS risk\n"
"  pol:   'better' (good news / defensive win / mitigation) | 'worse' (bad news / harm or capability "
"advancing) | 'neutral' (mixed)\n\n"
"Reply ONLY JSON: {\"decisions\":[{\"id\":<candidate id>,\"keep\":true|false,\"reason\":\"<short>\","
"\"norm\":{\"title\":\"\",\"when\":\"\",\"what\":\"\",\"pol\":\"\"}}]}  (omit norm when keep=false).")

def review_risk(rid, cands):
    r = RISKS.get(rid, {})
    existing = psql(f"SELECT c->>'when' || ' — ' || (c->>'title') FROM real_issues, "
                    f"jsonb_array_elements(coalesce(score_cases,'[]'::jsonb)) c WHERE id='{sq(rid)}'").splitlines()
    page = (f"RISK: {r.get('title', rid)}  (id={rid})\n"
            f"SUMMARY: {r.get('summary','')}\n\n"
            f"EXISTING TIMELINE (do not duplicate these):\n" + "\n".join(f"  - {e}" for e in existing if e))
    cand_txt = "\n\n".join(
        f"CANDIDATE id={c['id']}\n  title: {c['title']}\n  source: {c['source']}\n  blurb: {c['blurb'][:300]}\n"
        f"  url: {c['url']}\n  first-pass guess: {c['qwen_pol']} — {c['qwen_why']}"
        for c in cands)
    user = (page + "\n\n" + "="*60 + "\nCANDIDATES ROUTED TO THIS RISK — judge each for true relevance:\n\n"
            + cand_txt)
    out = anthropic(SYSTEM, user)
    m = re.search(r"\{.*\}", out, re.S)
    if not m: raise RuntimeError("no JSON from Opus")
    return json.loads(m.group()).get("decisions", [])

def run(min_batch=MIN_BATCH, only=None):
    where = "status='enriched'" + (f" AND qwen_risk='{sq(only)}'" if only else "")
    # robust: pull rows as JSON (no delimiter fragility with real titles/sources)
    raw = psql(f"SELECT coalesce(json_agg(json_build_object('id',id,'risk',qwen_risk,'title',title,"
               f"'blurb',coalesce(blurb,''),'source',coalesce(source,''),'url',coalesce(final_url,url),"
               f"'qwen_pol',coalesce(qwen_pol,''),'qwen_why',coalesce(qwen_why,''),"
               f"'q',coalesce(qwen_quote,''))),'[]') FROM news_queue WHERE {where}")
    by = {}
    for r in json.loads(raw or "[]"):
        by.setdefault(r["risk"], []).append(r)
    ready = {k: v for k, v in by.items() if len(v) >= min_batch}
    print(f"risks with >= {min_batch} pending: {len(ready)}  (skipping {len(by)-len(ready)} under-batch)")
    kept = dropped = 0
    for rid, cands in ready.items():
        print(f"\n▸ {rid}  ({len(cands)} candidates)")
        try:
            decisions = review_risk(rid, cands)
        except Exception as e:
            print(f"  ERROR {e}"); continue
        dmap = {d["id"]: d for d in decisions}
        sql = ["BEGIN;"]
        for c in cands:
            d = dmap.get(c["id"])
            if not d:
                continue
            if d.get("keep") and d.get("norm"):
                n = d["norm"]; n["url"] = c["url"]; n["src"] = c["source"]
                if c.get("q") and not n.get("q"):
                    n["q"] = c["q"]            # verbatim quote captured at enrich (source-integrity)
                sql.append("UPDATE news_queue SET opus_verdict='keep', opus_reason='{}', norm='{}'::jsonb, "
                           "status='approved', updated_at=now() WHERE id={};".format(
                               sq(d.get("reason","")), sq(json.dumps(n, ensure_ascii=False)), c["id"]))
                kept += 1; print(f"  ✓ keep  #{c['id']}  {n.get('title','')[:55]}")
            else:
                sql.append("UPDATE news_queue SET opus_verdict='drop', opus_reason='{}', status='rejected', "
                           "updated_at=now() WHERE id={};".format(sq(d.get("reason","")), c["id"]))
                dropped += 1; print(f"  ✗ drop  #{c['id']}  ({d.get('reason','')[:45]})")
        sql.append("COMMIT;")
        psql_stdin("\n".join(sql) + "\n")
    print(f"\n✓ Opus gate: kept={kept} → approved (review queue) | dropped={dropped}")

if __name__ == "__main__":
    mn = MIN_BATCH; only = None
    if "--min" in sys.argv: mn = int(sys.argv[sys.argv.index("--min")+1])
    if "--risk" in sys.argv: only = sys.argv[sys.argv.index("--risk")+1]
    run(mn, only)
