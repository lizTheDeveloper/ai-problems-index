#!/usr/bin/env python3
"""Human review report. Renders the Opus-approved candidates (status='approved') as a page —
grouped by risk, each card shown exactly as it would land on the timeline (date · polarity ·
title · what · source · quote) — plus the one-command apply line. Nothing here is live on the
atlas; this is the queue you eyeball before running apply.py.

Publishes to /x/ai-atlas-review (pages table, -U school). Optionally pings Matrix.
Run:  python3 build_review.py
"""
import os, sys, json, html
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import psql, sq, _load_env
_load_env()
SSH = os.environ.get("AIPI_SSH_HOST", "hetzner")
PGC = os.environ.get("AIPI_PG_CONTAINER", "")
DB  = os.environ.get("AIPI_DB", "")
PAGES_ROLE = os.environ.get("AIPI_PAGES_ROLE", "school")
RISKS = {r["id"]: r["title"] for r in json.load(open(os.path.join(os.path.dirname(__file__), "risks.json")))}
POL = {"better": ("#2ea043", "GOOD NEWS"), "worse": ("#e5484d", "BAD NEWS"), "neutral": ("#8b94a0", "MIXED")}
def esc(s): return html.escape(str(s or ""))

def run():
    raw = psql("SELECT coalesce(json_agg(json_build_object('id',id,'risk',qwen_risk,'norm',norm,"
               "'reason',opus_reason,'source',source) ORDER BY qwen_risk,id),'[]') "
               "FROM news_queue WHERE status='approved'")
    rows = json.loads(raw or "[]")
    by = {}
    for r in rows:
        by.setdefault(r["risk"], []).append(r)
    if not rows:
        print("no approved items to review."); return

    cards = ""
    for rid, items in sorted(by.items()):
        ids = ",".join(str(i["id"]) for i in items)
        cards += (f'<div class="rev-risk"><h2>{esc(RISKS.get(rid, rid))} '
                  f'<span class="rev-count">{len(items)} pending</span></h2>'
                  f'<div class="rev-cmd">apply: <code>python3 ingest/apply.py {ids}</code></div>')
        for it in items:
            n = it.get("norm") or {}
            col, lab = POL.get(n.get("pol"), POL["neutral"])
            cards += (
                f'<div class="rev-card" style="--pc:{col}">'
                f'<div class="rev-top"><span class="rev-when">{esc(n.get("when"))}</span>'
                f'<span class="rev-pol" style="color:{col}">{lab}</span>'
                f'<span class="rev-id">#{it["id"]}</span></div>'
                f'<div class="rev-t">{esc(n.get("title"))}</div>'
                f'<p class="rev-what">{esc(n.get("what"))}</p>'
                + (f'<p class="rev-q">&ldquo;{esc(n.get("q"))}&rdquo;</p>' if n.get("q") else "")
                + f'<a class="rev-src" href="{esc(n.get("url"))}" target="_blank" rel="noopener">{esc(n.get("src"))} ↗</a>'
                + f'<div class="rev-why">Opus: {esc(it.get("reason"))}</div>'
                f'</div>')
        cards += "</div>"

    page = f"""<style>
.rev{{font-family:var(--font-primary,system-ui,sans-serif);color:var(--color-text,#eef2f6);max-width:820px;margin:0 auto}}
.rev .lede{{color:var(--color-text-muted,#8b94a0);font-size:1rem;line-height:1.6}}
.rev h2{{font-size:1.15rem;margin:26px 0 4px;display:flex;align-items:center;gap:10px}}
.rev .rev-count{{font-family:ui-monospace,monospace;font-size:.72rem;color:var(--color-primary,#34a58e);
  border:1px solid var(--color-border,#2a2f36);border-radius:999px;padding:2px 9px}}
.rev .rev-cmd{{font-family:ui-monospace,monospace;font-size:.78rem;color:var(--color-text-muted,#8b94a0);margin:0 0 10px}}
.rev .rev-cmd code{{color:var(--color-primary,#34a58e)}}
.rev .rev-card{{border:1px solid var(--color-border,#2a2f36);border-left:3px solid var(--pc);border-radius:12px;
  padding:13px 15px;margin:0 0 10px;background:var(--color-bg-card,#1c1f24)}}
.rev .rev-top{{display:flex;align-items:center;gap:10px;margin-bottom:4px}}
.rev .rev-when{{font-family:ui-monospace,monospace;font-size:.72rem;font-weight:700;color:var(--color-accent,#e0741c)}}
.rev .rev-pol{{font-family:ui-monospace,monospace;font-size:.62rem;font-weight:800;letter-spacing:.05em}}
.rev .rev-id{{margin-left:auto;font-family:ui-monospace,monospace;font-size:.66rem;color:var(--color-text-muted,#8b94a0)}}
.rev .rev-t{{font-weight:700;font-size:1rem;line-height:1.3}}
.rev .rev-what{{margin:4px 0 6px;font-size:.9rem;line-height:1.55;color:var(--color-text-muted,#8b94a0)}}
.rev .rev-q{{margin:0 0 6px;font-size:.85rem;font-style:italic;color:var(--color-text-muted,#8b94a0);border-left:2px solid var(--color-border,#2a2f36);padding-left:9px}}
.rev .rev-src{{font-family:ui-monospace,monospace;font-size:.76rem;color:var(--color-primary,#34a58e);text-decoration:none}}
.rev .rev-why{{margin-top:6px;font-size:.72rem;color:var(--color-text-muted,#8b94a0)}}
</style>
<div class="rev">
  <p class="lede"><b>News-ingester review queue.</b> {len(rows)} Opus-approved candidates across {len(by)} risks,
  awaiting your confirm. Each is shown as it would appear on the timeline. To publish a risk's batch, run its
  <code>apply</code> command. Nothing here is live yet.</p>
  {cards}
</div>"""

    # publish the review page (school role)
    tag = "$revq$"
    sql = ("\\set ON_ERROR_STOP on\nBEGIN;\nDELETE FROM pages WHERE slug='ai-atlas-review';\n"
           "INSERT INTO pages (slug,title,content_html,page_type,status,renderer,published_at,created_at,updated_at) "
           f"VALUES ('ai-atlas-review','AI Atlas — review queue',{tag}{page}{tag},'landing','published','html',now(),now(),now());\nCOMMIT;\n")
    import subprocess
    r = subprocess.run(["ssh", SSH, f"docker exec -i {PGC} psql -U {PAGES_ROLE} -d {DB} -q"],
                       input=sql, capture_output=True, text=True)
    if r.returncode != 0:
        print("publish FAILED:", r.stderr[:300]); return
    print(f"✓ review queue published: https://themultiverse.school/x/ai-atlas-review  ({len(rows)} items, {len(by)} risks)")
    for rid, items in sorted(by.items()):
        print(f"    {rid}: {len(items)}  → python3 ingest/apply.py {','.join(str(i['id']) for i in items)}")

if __name__ == "__main__":
    run()
