#!/usr/bin/env python3
"""Source-integrity enrichment. For each Qwen-classified candidate, resolve its URL to the
real primary, resolve-check it, and capture a short VERBATIM quote from the article body —
so autonomously-added cases meet the same "measured, sourced" bar as every hand-curated one
(resolved primary URL + quote-on-hover). Also gives Opus the real body to normalize from.

classified → enriched  (final_url + qwen_quote set)   |   dead/unresolvable → dropped

Google-News redirect URLs (news.google.com/rss/articles/…) don't resolve via curl; items
that can't be resolved to a real outlet are dropped here (they'd fail the source bar).

Run:  python3 enrich.py [--limit N]
"""
import os, sys, re, json, urllib.request, urllib.parse, html
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import psql, psql_stdin, sq, _load_env
_load_env()
UA = "Mozilla/5.0 (AI Problems Index ingester)"

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        final = r.geturl()
        ct = r.headers.get("Content-Type", "")
        body = r.read(600000).decode("utf-8", "replace") if "html" in ct or "xml" in ct or ct == "" else ""
        return final, body, r.status

def visible_text(body):
    body = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", body)
    txt = re.sub(r"<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", html.unescape(txt)).strip()

def meta_desc(body):
    m = re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']{40,400})', body, re.I)
    return html.unescape(m.group(1)).strip() if m else ""

_BOILER = re.compile(
    r"sign in|sign up|subscribe|newsletter|cookie|advertisement|getty images|view image|"
    r"in fullscreen|photograph:|illustration:|reuters|shutterstock|all rights reserved|"
    r"pdt|pst|gmt|·|read more|share this|follow us|^\W*\d{1,2}:\d{2}|webinars|resources intelligence",
    re.I)
def pick_quote(body, title):
    """A short verbatim quote from the article BODY — skips nav/bylines/captions/boilerplate.
    Prefers a real sentence; falls back to the meta description (usually the clean dek)."""
    # meta description first — it's the clean article summary, not page chrome
    md = meta_desc(body)
    text = visible_text(body)
    sig = re.compile(r"\b(said|found|reported|according|study|researchers?|attack|breach|exploit|"
                     r"vulnerab|lawsuit|court|regulator|banned?|percent|deepfake|model|agent|AI)\b", re.I)
    best = ""
    for sent in re.split(r"(?<=[.!?])\s+", text):
        s = sent.strip()
        if not (55 <= len(s) <= 240): continue
        if _BOILER.search(s): continue
        if s.count(" ") < 7: continue           # too few words → likely a label
        letters = sum(c.isalpha() or c == ' ' for c in s)
        if letters / max(len(s), 1) < 0.75: continue   # too much punctuation/markup
        if sig.search(s):
            best = s; break
    if best: return best
    if md and not _BOILER.search(md): return md[:240]
    return ""

def run(limit=None):
    lim = f" LIMIT {int(limit)}" if limit else ""
    raw = psql(f"SELECT coalesce(json_agg(json_build_object('id',id,'url',url,'title',title) ORDER BY id),'[]') "
               f"FROM (SELECT * FROM news_queue WHERE status='classified'{lim}) t")
    rows = json.loads(raw or "[]")
    print(f"to enrich: {len(rows)}")
    ok = dropped = 0
    for r in rows:
        rid, url, title = r["id"], r["url"], r["title"]
        try:
            final, body, code = fetch(url)
        except Exception as e:
            print(f"  #{rid} FETCH-FAIL ({str(e)[:40]}) → drop")
            psql_stdin(f"UPDATE news_queue SET status='dropped', opus_reason='unfetchable', updated_at=now() WHERE id={rid};\n")
            dropped += 1; continue
        dom = urllib.parse.urlsplit(final).netloc.lower()
        # unresolved google-news redirect, or non-200 → drop (fails source bar)
        if "news.google.com" in dom or code >= 400 or not dom:
            print(f"  #{rid} UNRESOLVED/{code} ({dom[:30]}) → drop")
            psql_stdin(f"UPDATE news_queue SET status='dropped', opus_reason='unresolved source url', updated_at=now() WHERE id={rid};\n")
            dropped += 1; continue
        q = pick_quote(body, title)
        psql_stdin("BEGIN;\nUPDATE news_queue SET final_url='{}', qwen_quote='{}', status='enriched', updated_at=now() "
                   "WHERE id={};\nCOMMIT;\n".format(sq(final), sq(q[:400]), rid))
        ok += 1
        print(f"  #{rid} ✓ {dom[:28]}  q='{q[:50]}…'")
    print(f"✓ enriched={ok}  dropped={dropped}")

if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit")+1]) if "--limit" in sys.argv else None
    run(lim)
