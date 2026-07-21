#!/usr/bin/env python3
"""Free news feeds for the AI-risk ingester — REAL primary URLs only (no key required).

Google News RSS is deliberately NOT used: its links are opaque news.google.com redirects that
don't resolve to the real outlet, which would fail the atlas source-integrity bar (resolved
primary URL + verbatim quote). Instead: curated outlet RSS/Atom + Hacker News + arXiv + GDELT
(spaced, best-effort). The keyword pre-filter (pipeline.py) then cuts these to AI-risk signal.
"""
import urllib.request, urllib.parse, json, re, time, html, xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (AI Problems Index ingester)"

# Curated outlet feeds that publish real article URLs. Security + AI + tech-policy leaning.
OUTLET_RSS = {
    "The Register (security)": "https://www.theregister.com/security/headlines.atom",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Guardian (AI)": "https://www.theguardian.com/technology/artificialintelligenceai/rss",
    "The Verge (AI)": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "MIT Tech Review": "https://www.technologyreview.com/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "Wired": "https://www.wired.com/feed/tag/ai/latest/rss",
    "The Record (cyber)": "https://therecord.media/feed",
    "Schneier on Security": "https://www.schneier.com/feed/atom/",
}
HN_QUERIES = ["AI security", "AI safety", "prompt injection", "AI agent", "deepfake", "LLM vulnerability"]
ARXIV_CATEGORIES = ["cs.CR", "cs.CY"]

def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def _clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t or ""))).strip()

def _tag(el):  # local tag name w/o namespace
    return el.tag.rsplit("}", 1)[-1]

def outlet_rss():
    out = []
    for name, url in OUTLET_RSS.items():
        try:
            root = ET.fromstring(_get(url))
        except Exception:
            continue
        # handle both RSS <item> and Atom <entry>
        for it in root.iter():
            if _tag(it) not in ("item", "entry"):
                continue
            title = link = desc = pub = ""
            for ch in it:
                tag = _tag(ch)
                if tag == "title" and ch.text: title = _clean(ch.text)
                elif tag == "link":
                    href = ch.get("href")
                    if href and ch.get("rel", "alternate") != "self": link = href.strip()
                    elif ch.text and ch.text.strip().startswith("http"): link = ch.text.strip()
                elif tag in ("description", "summary", "content") and ch.text and not desc:
                    desc = _clean(ch.text)
                elif tag in ("pubDate", "published", "updated") and ch.text and not pub:
                    pub = ch.text.strip()
            if title and link and link.startswith("http"):
                out.append(dict(title=title, url=link, blurb=desc[:400], source=name, published=pub, feed=f"rss:{name}"))
        time.sleep(0.3)
    return out

def hackernews():
    out = []
    for q in HN_QUERIES:
        url = "https://hn.algolia.com/api/v1/search_by_date?" + urllib.parse.urlencode(
            {"query": q, "tags": "story", "numericFilters": f"created_at_i>{int(time.time())-14*86400}", "hitsPerPage": "25"})
        try:
            data = json.loads(_get(url))
        except Exception:
            continue
        for h in data.get("hits", []):
            link = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
            title = _clean(h.get("title"))
            if title and link:
                out.append(dict(title=title, url=link.strip(), blurb="", source="Hacker News",
                                published=h.get("created_at", ""), feed=f"hn:{q}"))
        time.sleep(0.3)
    return out

def arxiv():
    out = []
    for cat in ARXIV_CATEGORIES:
        url = ("http://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"search_query": f"cat:{cat}", "sortBy": "submittedDate", "sortOrder": "descending", "max_results": "50"}))
        try:
            root = ET.fromstring(_get(url))
        except Exception:
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for e in root.findall("a:entry", ns):
            title = _clean(e.findtext("a:title", default="", namespaces=ns))
            summ = _clean(e.findtext("a:summary", default="", namespaces=ns))
            link = (e.findtext("a:id", default="", namespaces=ns) or "").strip()
            pub = (e.findtext("a:published", default="", namespaces=ns) or "").strip()
            low = (title + " " + summ).lower()
            if link and any(k in low for k in ("language model", "llm", " ai ", "artificial intelligence",
                                               "generative", "agent", "jailbreak", "prompt injection", "deepfake")):
                out.append(dict(title=title, url=link, blurb=summ[:400], source="arXiv", published=pub, feed=f"arxiv:{cat}"))
        time.sleep(0.5)
    return out

def gdelt():
    """Broad global news with real outlet URLs. Rate-limited to 1 req / 5s — space it."""
    out = []
    queries = ['"artificial intelligence" (cyberattack OR deepfake OR surveillance)',
               '"AI" (lawsuit OR investigation OR banned OR misuse)']
    for i, qy in enumerate(queries):
        if i: time.sleep(6)
        url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(
            {"query": qy, "mode": "artlist", "maxrecords": "50", "format": "json",
             "timespan": "14d", "sort": "datedesc"})
        try:
            data = json.loads(_get(url, timeout=30))
        except Exception:
            continue
        for a in data.get("articles", []):
            u = (a.get("url") or "").strip()
            if u and "news.google" not in u:
                out.append(dict(title=_clean(a.get("title")), url=u, blurb="",
                                source=a.get("domain") or "GDELT", published=a.get("seendate", ""), feed="gdelt"))
    return out

def collect_all():
    items = []
    for fn in (outlet_rss, hackernews, arxiv, gdelt):
        try:
            got = fn(); items += got
            print(f"  {fn.__name__}: {len(got)}")
        except Exception as e:
            print(f"  {fn.__name__}: FAILED {e}")
    return items

if __name__ == "__main__":
    its = collect_all()
    print("total raw:", len(its))
