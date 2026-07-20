#!/usr/bin/env python3
"""Confirm step: merge Opus-approved candidates into real_issues.score_cases and redeploy.
This is the human gate — you run it after eyeballing the review queue.

  python3 apply.py 12,15,18      # apply specific approved ids
  python3 apply.py --risk <id>   # apply all approved for one risk
  python3 apply.py --all         # apply every approved item
  python3 apply.py ... --no-deploy   # merge to DB but skip the atlas rebuild

Merges each item's `norm` ({title,when,what,pol,q,url,src}) into its risk's score_cases
(dedup by canonical url + normalized title), marks it status='published', then runs
deploy.sh atlas (dump → build → publish list + detail bundle).
"""
import os, sys, re, json, subprocess
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import psql, psql_stdin, sq, canonical, _load_env
_load_env()
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm_title(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())

def run(ids=None, risk=None, do_all=False, deploy=True):
    where = "status='approved'"
    if ids:   where += " AND id IN (" + ",".join(str(int(i)) for i in ids) + ")"
    if risk:  where += f" AND qwen_risk='{sq(risk)}'"
    raw = psql(f"SELECT coalesce(json_agg(json_build_object('id',id,'risk',qwen_risk,'norm',norm)),'[]') "
               f"FROM news_queue WHERE {where}")
    rows = json.loads(raw or "[]")
    if not rows:
        print("no approved items match."); return
    by = {}
    for r in rows:
        by.setdefault(r["risk"], []).append(r)
    print(f"applying {len(rows)} items across {len(by)} risks")

    touched = []
    for rid, items in by.items():
        cur = json.loads(psql(f"SELECT coalesce(score_cases,'[]') FROM real_issues WHERE id='{sq(rid)}'") or "[]")
        seen_u = {canonical(c.get("url","")) for c in cur}
        seen_t = {norm_title(c.get("title","")) for c in cur}
        added = 0; used_ids = []
        for it in items:
            n = it.get("norm") or {}
            if canonical(n.get("url","")) in seen_u or norm_title(n.get("title","")) in seen_t:
                # already present (near-dup) → mark published, skip insert
                used_ids.append(it["id"]); continue
            case = {"title": n.get("title",""), "when": n.get("when",""), "what": n.get("what",""),
                    "src": n.get("src",""), "url": n.get("url",""), "pol": n.get("pol","worse")}
            if n.get("q"): case["q"] = n["q"]
            cur.append(case); seen_u.add(canonical(case["url"])); seen_t.add(norm_title(case["title"]))
            added += 1; used_ids.append(it["id"])
        j = sq(json.dumps(cur, ensure_ascii=False))
        idlist = ",".join(str(i) for i in used_ids)
        psql_stdin("BEGIN;\n"
                   f"UPDATE real_issues SET score_cases='{j}'::jsonb, updated_at=now() WHERE id='{sq(rid)}';\n"
                   f"UPDATE news_queue SET status='published', updated_at=now() WHERE id IN ({idlist});\n"
                   "COMMIT;\n")
        touched.append(rid); print(f"  {rid}: +{added} new case(s) ({len(used_ids)} approved processed)")

    if deploy:
        print("• deploying atlas …")
        r = subprocess.run(["bash", os.path.join(REPO, "deploy.sh"), "atlas"], cwd=REPO,
                           capture_output=True, text=True)
        print("\n".join(l for l in r.stdout.splitlines() if l.strip())[-800:])
        if r.returncode != 0:
            print("DEPLOY FAILED:", r.stderr[-400:])
    else:
        print("(--no-deploy: merged to DB; run ./deploy.sh atlas to publish)")

if __name__ == "__main__":
    a = sys.argv[1:]
    ids = risk = None; do_all = "--all" in a; deploy = "--no-deploy" not in a
    if "--risk" in a: risk = a[a.index("--risk")+1]
    pos = [x for x in a if not x.startswith("--") and x != (risk or "")]
    if pos: ids = [int(x) for x in pos[0].split(",")]
    run(ids, risk, do_all, deploy)
