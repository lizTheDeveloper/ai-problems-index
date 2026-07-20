#!/usr/bin/env python3
"""Alignment-RESEARCH feeds — a sibling source to feeds.py (which does news).

Same contract as feeds.py: `collect_all()` -> [{title,url,blurb,source,published,feed}, ...]
so it drops straight into the existing pipeline with no edits to pipeline.py:

    import pipeline, research_feeds
    pipeline.feeds     = research_feeds          # swap the source module
    pipeline.prefilter = research_feeds.prefilter # research-appropriate gate
    pipeline.run()

(That is exactly what research_pipeline.py does.)

Sources, in order of value:
  1. The org registry itself — every alignment_orgs row with feed_kind='rss'.
     Add an org to the directory and its research starts flowing in. One spine.
  2. arXiv, restricted to alignment/safety-relevant queries (not whole categories).
  3. The community venues where a lot of alignment work is actually published first
     (Alignment Forum / LessWrong).

No API keys required. Feed health is written back to alignment_orgs so the directory
page can show which orgs we can actually track.
"""
import os, re, sys, json, time, subprocess, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (AI Problems Index research ingester; +https://themultiverse.school)"
HERE = os.path.dirname(os.path.abspath(__file__))


def _load_env():
    for p in (os.path.join(HERE, "..", ".aipi.env"), os.path.join(HERE, ".aipi.env")):
        if os.path.exists(p):
            for ln in open(p):
                ln = ln.strip()
                if ln and not ln.startswith("#") and "=" in ln:
                    k, v = ln.split("=", 1)
                    os.environ.setdefault(k, v.strip().strip('"'))


_load_env()
SSH = os.environ.get("AIPI_SSH_HOST", "hetzner")
PGC = os.environ.get("AIPI_PG_CONTAINER", "")
DB = os.environ.get("AIPI_DB", "")
# NB: ownership was consolidated onto `school`; campus still works (superuser) but school is correct.
KB_ROLE = os.environ.get("AIPI_KB_ROLE", "school")


def psql(sql):
    r = subprocess.run(["ssh", SSH, f'docker exec -i {PGC} psql -U {KB_ROLE} -d {DB} -At -c "{sql}"'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def psql_stdin(sql):
    r = subprocess.run(["ssh", SSH, f"docker exec -i {PGC} psql -U {KB_ROLE} -d {DB} -q"],
                       input=sql, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _clean(t):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t or "")).strip()


# ---------------------------------------------------------------- feed parsing
def parse_feed(xml_text, source, feed_label):
    """Parse RSS 2.0 or Atom. Returns the standard item dicts.

    Tolerant of two things real feeds do that ElementTree refuses outright:
      * a BOM or leading whitespace/newline before `<?xml` — ET raises
        "XML or text declaration not at start of entity" and you silently lose the
        whole feed (this cost us PAX and several other WordPress feeds in testing);
      * junk (HTML comments, stray text) before the root element.
    """
    out = []
    if not xml_text:
        return out
    txt = xml_text.lstrip("﻿ \t\r\n")
    try:
        root = ET.fromstring(txt)
    except ET.ParseError:
        # last resort: start at the first tag that looks like a feed root
        m = re.search(r"<(?:rss|feed|rdf:RDF)\b", txt)
        if not m:
            return out
        try:
            root = ET.fromstring(txt[m.start():])
        except ET.ParseError:
            return out
    ns = {"a": "http://www.w3.org/2005/Atom"}

    for item in root.iter("item"):  # RSS
        title = _clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        desc = _clean(item.findtext("description"))
        pub = (item.findtext("pubDate") or "").strip()
        if title and link:
            out.append(dict(title=title, url=link, blurb=desc[:600],
                            source=source, published=pub, feed=feed_label))
    if out:
        return out

    for e in root.findall("a:entry", ns):  # Atom
        title = _clean(e.findtext("a:title", default="", namespaces=ns))
        link = ""
        for l in e.findall("a:link", ns):
            if l.get("rel", "alternate") == "alternate":
                link = (l.get("href") or "").strip()
                break
        if not link:
            link = (e.findtext("a:id", default="", namespaces=ns) or "").strip()
        summ = _clean(e.findtext("a:summary", default="", namespaces=ns)) or \
               _clean(e.findtext("a:content", default="", namespaces=ns))
        pub = (e.findtext("a:published", default="", namespaces=ns) or
               e.findtext("a:updated", default="", namespaces=ns) or "").strip()
        if title and link:
            out.append(dict(title=title, url=link, blurb=summ[:600],
                            source=source, published=pub, feed=feed_label))
    return out


# ---------------------------------------------------------------- 1. org feeds
def org_feeds(limit=None):
    """Pull every alignment_orgs row with an RSS feed. Writes feed health back."""
    rows = [r for r in psql(
        "SELECT slug||E'\\t'||name||E'\\t'||coalesce(feed_url,'') FROM alignment_orgs "
        "WHERE feed_kind='rss' AND coalesce(feed_url,'')<>'' ORDER BY slug").splitlines() if r]
    if limit:
        rows = rows[:limit]
    out, health = [], []
    for row in rows:
        parts = row.split("\t")
        if len(parts) < 3:
            continue
        slug, name, feed_url = parts[0], parts[1], parts[2]
        status, n = "ok", 0
        try:
            items = parse_feed(_get(feed_url), name, f"org:{slug}")
            n = len(items)
            if n == 0:
                status = "empty"
            out += items
        except urllib.error.HTTPError as e:
            status = f"http_{e.code}"
        except Exception:
            status = "fetch_error"
        health.append((slug, status, n))
        time.sleep(0.3)

    if health:
        vals = ",".join("('%s','%s',%d)" % (s.replace("'", "''"), st, n) for s, st, n in health)
        psql_stdin(
            "BEGIN;\nUPDATE alignment_orgs o SET feed_status=v.st, feed_items_seen=v.n, "
            "feed_checked_at=now(), updated_at=now() FROM (VALUES %s) AS v(slug,st,n) "
            "WHERE o.slug=v.slug;\nCOMMIT;\n" % vals)
    return out


# ---------------------------------------------------------------- 2. arXiv
# Targeted queries, NOT whole categories — whole-category pulls are ~99% irrelevant.
ARXIV_QUERIES = [
    'all:"AI alignment"', 'all:"AI safety"', 'all:"scalable oversight"',
    'all:"reward hacking"', 'all:"deceptive alignment"', 'all:"mechanistic interpretability"',
    'all:"AI control"', 'all:"model evaluation" AND all:"dangerous capabilities"',
    'all:"jailbreak" AND all:"language model"', 'all:"prompt injection"',
    'all:"sycophancy"', 'all:"goal misgeneralization"', 'all:"situational awareness" AND all:"language model"',
    'all:"chain-of-thought" AND all:"faithfulness"', 'all:"sandbagging"',
    'all:"data poisoning" AND all:"language model"', 'all:"agentic" AND all:"safety"',
    'all:"red teaming" AND all:"language model"', 'all:"unlearning" AND all:"language model"',
    'all:"constitutional AI"', 'all:"RLHF" AND all:"failure"', 'all:"emergent capabilities"',
]


def arxiv(days=21, per_query=25):
    out = []
    for q in ARXIV_QUERIES:
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode({
            "search_query": q, "sortBy": "submittedDate", "sortOrder": "descending",
            "max_results": str(per_query)})
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
            if pub and days:
                try:
                    if (time.time() - time.mktime(time.strptime(pub[:10], "%Y-%m-%d"))) > days * 86400:
                        continue
                except Exception:
                    pass
            if title and link:
                out.append(dict(title=title, url=link, blurb=summ[:600], source="arXiv",
                                published=pub, feed=f"arxiv:{q[:30]}"))
        time.sleep(0.5)  # arXiv asks for >=3s between calls for heavy use; 0.5 is fine at this volume
    return out


# ---------------------------------------------------------------- 3. community
COMMUNITY_FEEDS = [
    ("Alignment Forum", "https://www.alignmentforum.org/feed.xml", "af"),
    ("LessWrong", "https://www.lesswrong.com/feed.xml?view=curated-rss", "lw"),
]


def community():
    out = []
    for name, url, tag in COMMUNITY_FEEDS:
        try:
            out += parse_feed(_get(url), name, f"community:{tag}")
        except Exception:
            pass
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------- prefilter
# The news prefilter in pipeline.py requires a harm/incident word, which would throw away
# most legitimate alignment research ("scalable oversight", "interpretability"...).
# This gate is tuned for research instead: require a real research/safety signal.
RESEARCH_SIGNAL = re.compile(
    r"\b(alignment|misalign|interpretab|oversight|eval(uation)?s?|red[- ]team|jailbreak|"
    r"prompt injection|deceptive|deception|scheming|sycophan|reward hack|specification gaming|"
    r"goal misgeneral|corrigib|control|unlearn|steering|probe|activation|sparse autoencoder|"
    r"chain[- ]of[- ]thought|faithful|situational awareness|sandbag|dangerous capab|"
    r"safety case|governance|policy|risk|threat model|robustness|adversarial|poison|backdoor|"
    r"watermark|provenance|bias|fairness|privacy|surveillance|autonom|agentic|CBRN|bioweapon|"
    r"cyber|welfare|moral status|catastroph|existential)\b", re.I)
# NB: every multi-word term needs an explicit plural. `\blanguage model\b` does NOT match
# "language models" — the trailing \b fails against the 's' — which silently dropped most real
# paper abstracts, since they overwhelmingly use plurals. Keep the s? on anything countable.
AI_SIGNAL = re.compile(
    r"\b(ai|a\.i\.|artificial intelligence|llms?|language models?|foundation models?|"
    r"frontier models?|machine learning|deep learning|neural networks?|neural|transformers?|"
    r"agents?|agentic|chatbots?|gpt|claude|gemini|llama|mistral|qwen|deepseek|"
    r"reinforcement learning|rlhf|diffusion models?|generative)\b", re.I)
RESEARCH_NOISE = re.compile(
    r"\b(webinar|newsletter signup|we're hiring|job opening|apply now|donate|"
    r"annual gala|conference registration|save the date)\b", re.I)

# Hiring / admin / event chatter. Org RSS feeds carry a lot of this, and every item that gets
# through costs the downstream CPU-bound Qwen classifier ~75s — so it is worth dropping here.
JOBS_ADMIN = re.compile(
    r"\b(we are hiring|now hiring|join our team|open roles?|job description|"
    r"phd (student|researcher|position|programme|program)|post-?doc(toral)?|"
    r"vacanc(y|ies)|call for (applications|papers|proposals|nominations)|"
    r"applications? (are )?(now )?open|apply (by|now|here|today)|deadline to apply|"
    r"internships?|summer fellowship applications|recruiting|"
    r"register (now|here|today)|registration (is )?open|rsvp|"
    r"press release: appointment|welcome to (our|the) newsletter|"
    r"we're looking for|join us as)\b", re.I)

# Bare site-furniture titles that some CMS feeds (notably Hugo) emit as if they were posts.
NAV_TITLES = {
    'mission', 'about', 'about us', 'contact', 'contact us', 'team', 'our team', 'people',
    'home', 'homepage', 'events', 'news', 'blog', 'publications', 'research', 'papers',
    'careers', 'jobs', 'donate', 'support us', 'newsletter', 'privacy policy', 'terms',
    'resources', 'library', 'projects', 'our work', 'work', 'media', 'press', 'faq',
}


def prefilter(item):
    title = (item.get('title') or '').strip()
    text = f"{title} {item.get('blurb','')}"
    # site furniture: an exact nav-word title with nothing else to it
    if re.sub(r'[^a-z ]', '', title.lower()).strip() in NAV_TITLES:
        return False
    if RESEARCH_NOISE.search(text) or JOBS_ADMIN.search(text):
        return False
    return bool(AI_SIGNAL.search(text) and RESEARCH_SIGNAL.search(text))


# ---------------------------------------------------------------- collect
def collect_all():
    items = []
    for fn in (org_feeds, arxiv, community):
        try:
            got = fn()
            items += got
            print(f"  {fn.__name__}: {len(got)}")
        except Exception as e:
            print(f"  {fn.__name__}: FAILED {e}")
    return items


if __name__ == "__main__":
    if "--health" in sys.argv:
        org_feeds()
        print(psql("SELECT feed_status||'  '||count(*) FROM alignment_orgs "
                   "WHERE feed_kind='rss' GROUP BY feed_status ORDER BY 1"))
    else:
        its = collect_all()
        print("total raw:", len(its))
        kept = [i for i in its if prefilter(i)]
        print("after research prefilter:", len(kept))
