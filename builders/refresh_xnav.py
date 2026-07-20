#!/usr/bin/env python3
"""Swap the shared cross-nav block into every page that carries it (DB + local sources).

The nav is a single self-contained <nav class="xnav">…</nav> element (style + script inside),
with no nested <nav>, so a non-greedy match to the first </nav> is exact.
"""
import re, os, subprocess, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
NAV = open(os.path.join(HERE, 'nav_block.html')).read().rstrip('\n')
PAT = re.compile(r'<nav class="xnav".*?</nav>', re.S)

for k, v in (l.strip().split('=', 1) for l in open('/Users/annhoward/SRC/ai-problems-index/.aipi.env')
             if '=' in l and not l.strip().startswith('#')):
    os.environ.setdefault(k, v.strip().strip('"'))
SSH, PGC, DB = os.environ['AIPI_SSH_HOST'], os.environ['AIPI_PG_CONTAINER'], os.environ['AIPI_DB']

def psql(sql, stdin=None):
    cmd = f'docker exec -i {PGC} psql -U school -d {DB} -At' + ('' if stdin else f' -c "{sql}"')
    r = subprocess.run(["ssh", SSH, cmd], input=stdin, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr.strip())
    return r.stdout

# 1. local canonical sources
local = 0
for fn in ('env7_content.html', 'moral_content.html', 'dca_content_v2.html'):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p): continue
    s = open(p).read()
    if PAT.search(s):
        new = PAT.sub(lambda m: NAV, s, count=1)
        if new != s:
            open(p, 'w').write(new); local += 1
print(f"local files updated: {local}")

# 2. DB pages
slugs = [s for s in psql("SELECT slug FROM pages WHERE content_html LIKE '%class=\\\"xnav\\\"%' ORDER BY slug").split() if s]
print(f"db pages with xnav: {len(slugs)}")
done, skipped = [], []
for slug in slugs:
    html = psql(f"SELECT content_html FROM pages WHERE slug='{slug}'")
    if not PAT.search(html):
        skipped.append((slug, 'no match')); continue
    new = PAT.sub(lambda m: NAV, html, count=1)
    if new == html:
        skipped.append((slug, 'already current')); continue
    tag = next((t for t in ('nv1','nv2','nv3','nv9') if f'${t}$' not in new), None)
    if not tag: skipped.append((slug, 'no safe dollar tag')); continue
    sql = ("\\set ON_ERROR_STOP on\nBEGIN;\n"
           f"UPDATE pages SET content_html=${tag}${new}${tag}$, updated_at=now() WHERE slug='{slug}';\nCOMMIT;\n")
    psql(None, stdin=sql)
    done.append(slug)
print(f"updated: {len(done)}")
for s in done: print("   ✓", s)
for s, why in skipped: print("   -", s, "(", why, ")")
