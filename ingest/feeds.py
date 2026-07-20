#!/usr/bin/env python3
"""Free news feeds for the AI-risk ingester. No API keys required.
Broad AI-incident / safety / security queries → a pool the classifier routes per risk."""
import urllib.request, urllib.parse, json, re, time, xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (AI Problems Index ingester)"

# Broad queries — cast wide; the Qwen first-pass assigns each article to a risk (or drops it).
GOOGLE_NEWS_QUERIES = [
    "AI incident harm", "AI safety report", "AI cyberattack", "AI hacking agent",
    "prompt injection vulnerability", "AI deepfake election", "AI deepfake scam",
    "AI facial recognition surveillance", "autonomous weapon military AI",
    "AI bioweapon biosecurity", "AI chatbot lawsuit", "AI psychosis chatbot",
    "AI jobs layoffs displacement", "AI regulation policy", "frontier AI model safety",
    "autonomous AI agent risk", "AI misuse abuse", "AI alignment deception",
    "AI copyright training data", "AI child safety CSAM investigation",
]
HN_QUERIES = ["AI security", "AI safety", "prompt injection", "AI agent", "deepfake"]
ARXIV_CATEGORIES = ["cs.CR", "cs.CY"]  # security, computers & society

def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def _clean(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()

def google_news():
    out = []
    for q in GOOGLE_NEWS_QUERIES:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": q + " when:14d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        try:
            root = ET.fromstring(_get(url))
        except Exception:
            continue
        for item in root.iter("item"):
            title = _clean(item.findtext("title"))
            link = (item.findtext("link") or "").strip()
            desc = _clean(item.findtext("description"))
            pub = (item.findtext("pubDate") or "").strip()
            src_el = item.find("{http://news.google.com/}source") or item.find("source")
            src = _clean(src_el.text) if src_el is not None and src_el.text else "Google News"
            if title and link:
                out.append(dict(title=title, url=link, blurb=desc[:400], source=src, published=pub, feed=f"gnews:{q}"))
        time.sleep(0.4)
    return out

def gdelt():
    out = []
    url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode({
        "query": '(artificial intelligence) (incident OR misuse OR deepfake OR cyberattack OR surveillance OR autonomous)',
        "mode": "artlist", "maxrecords": "75", "format": "json", "timespan": "14d", "sort": "datedesc"})
    try:
        data = json.loads(_get(url))
    except Exception:
        return out
    for a in data.get("articles", []):
        out.append(dict(title=_clean(a.get("title")), url=(a.get("url") or "").strip(),
                        blurb="", source=a.get("domain") or "GDELT",
                        published=a.get("seendate", ""), feed="gdelt"))
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
            {"search_query": f"cat:{cat}", "sortBy": "submittedDate", "sortOrder": "descending", "max_results": "40"}))
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
            # arXiv cats are broad; keep only clearly AI-related
            if link and any(k in low for k in ("language model", "llm", " ai ", "artificial intelligence",
                                               "generative", "agent", "jailbreak", "prompt injection", "deepfake")):
                out.append(dict(title=title, url=link, blurb=summ[:400], source="arXiv", published=pub, feed=f"arxiv:{cat}"))
        time.sleep(0.5)
    return out

def collect_all():
    items = []
    for fn in (google_news, gdelt, hackernews, arxiv):
        try:
            got = fn()
            items += got
            print(f"  {fn.__name__}: {len(got)}")
        except Exception as e:
            print(f"  {fn.__name__}: FAILED {e}")
    return items

if __name__ == "__main__":
    its = collect_all()
    print("total raw:", len(its))
