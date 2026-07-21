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
        "SELECT slug||E'\\t'||name||E'\\t'||coalesce(feed_url,'')||E'\\t'||coalesce(org_type,'') "
        "FROM alignment_orgs WHERE feed_kind='rss' AND coalesce(feed_url,'')<>'' "
        "ORDER BY slug").splitlines() if r]
    if limit:
        rows = rows[:limit]
    out, health = [], []
    for row in rows:
        parts = row.split("\t")
        if len(parts) < 3:
            continue
        slug, name, feed_url = parts[0], parts[1], parts[2]
        otype = parts[3] if len(parts) > 3 else ""
        status, n = "ok", 0
        try:
            items = parse_feed(_get(feed_url), name, f"org:{slug}")
            for it in items:
                it["org_type"] = otype
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


# ------------------------------------------------------- 1b. listing-page scrape
# Most modern lab sites (Webflow / Framer / Next.js) publish no RSS at all — Apollo Research,
# FAR.AI, Transluce, Goodfire, Timaeus and ~140 others. Ignoring them would silently exclude a
# large share of the most relevant labs, so for feed_kind='page' we scrape the listing page for
# same-site article links. Recall-oriented and noisy by design; Qwen + the Opus gate are the
# precision stages. Anchor text is the title, which is usually exactly the paper/post name.
_HREF = re.compile(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.I | re.S)
_SKIP_PATH = re.compile(
    r'/(tag|tags|category|categories|author|page|search|login|signin|subscribe|privacy|terms|'
    r'cookie|contact|about|team|careers|jobs|donate|rss|feed)(/|$)', re.I)
_ASSET = re.compile(r'\.(png|jpe?g|gif|svg|webp|zip|mp4|mp3|css|js|ico)(\?|$)', re.I)
# Venues that ARE the publication for many labs, not third-party citations.
_CONTENT_PATH = re.compile(
    r'/(publications?|blog|news|posts?|reports?|articles?|research|papers?|work|writing)/', re.I)
_DATE_PATH = re.compile(r'/(19|20)\d{2}[/-]')
_PUB_HOST = re.compile(
    r'^(arxiv\.org|ar5iv\.org|aclanthology\.org|openreview\.net|proceedings\.neurips\.cc|'
    r'proceedings\.mlr\.press|.*\.substack\.com|lesswrong\.com|www\.lesswrong\.com|'
    r'alignmentforum\.org|www\.alignmentforum\.org|distill\.pub|biorxiv\.org|www\.biorxiv\.org|'
    r'transformer-circuits\.pub|arxiv\.org)$', re.I)


def _registrable(host):
    """Crude eTLD+1: enough to treat blog.example.com and example.com as one site."""
    parts = [p for p in (host or '').split('.') if p]
    if len(parts) < 2:
        return host
    # handle common two-part suffixes (co.uk, ac.uk, org.uk, gov.uk, com.au…)
    if len(parts) >= 3 and parts[-2] in ('co', 'ac', 'org', 'gov', 'com', 'net') and len(parts[-1]) == 2:
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])


def _same_site(a, b):
    return _registrable(a) == _registrable(b)


def scrape_listing(page_url, source, feed_label, limit=25):
    """Pull plausible article links out of a publications/blog listing page."""
    out, seen = [], set()
    try:
        html_text = _get(page_url)
    except Exception:
        return out
    base = re.match(r'(https?://[^/]+)', page_url)
    if not base:
        return out
    root = base.group(1)
    host = root.split('//', 1)[1].lower().replace('www.', '')
    listing_path = urllib.parse.urlsplit(page_url).path.rstrip('/')

    for href, inner in _HREF.findall(html_text):
        title = _clean(inner)
        # Nav words are short; whole paragraphs are long. The upper bound is generous because
        # card-style links wrap the title AND its summary in one <a>.
        if not (18 <= len(title) <= 400):
            continue
        # Resolve every form of href, including bare relative ones ("2026/some-post/").
        # Handling only "/..." and "http..." silently skipped every link on sites that use
        # relative paths — which is how Anthropic's Alignment Science index is built.
        if href.startswith(('mailto:', 'javascript:', 'tel:')):
            continue
        full = urllib.parse.urljoin(page_url, href)
        if not full.startswith('http'):
            continue
        h = urllib.parse.urlsplit(full)
        link_host = h.netloc.lower().replace('www.', '')
        # Accept the org's own domain INCLUDING subdomains (blog.tilderesearch.com belongs to
        # tilderesearch.com) and the venues labs actually publish to. A strict same-host rule
        # dropped everything for orgs that host their writing on arXiv, LessWrong or a blog
        # subdomain — Cadenza Labs, Tilde Research and AE Studio all scraped to zero because of it.
        if not (_same_site(link_host, host) or _PUB_HOST.search(link_host)):
            continue
        path = h.path.rstrip('/')
        if not path or path == listing_path:               # self / index links
            continue
        if _SKIP_PATH.search(path) or _ASSET.search(path):
            continue
        if full in seen:
            continue
        seen.add(full)
        # Rank rather than take-the-first-N. Nav and menu links appear FIRST in the DOM, so a
        # plain cap returned "Cookie notice / About us / Our Team" and never reached the actual
        # publications (this emptied the Alan Turing Institute's list entirely). Links whose path
        # looks like content — /publications/, /blog/, /news/, or a /2026/ date segment — win.
        score = (2 if _CONTENT_PATH.search(path + '/') else 0) \
              + (2 if _DATE_PATH.search(path + '/') else 0) \
              + (1 if path.count('/') >= 2 else 0)
        out.append((score, dict(title=title, url=full, blurb="", source=source,
                                published="", feed=feed_label)))

    out.sort(key=lambda x: -x[0])
    return [d for s, d in out if s > 0][:limit] or [d for s, d in out][:limit]


_SITEMAP_CONTENT = re.compile(r'/(blog|research|news|posts?|publications?|papers?|articles?|work)/', re.I)


def sitemap_urls(root, max_urls=25):
    """Fallback for fully client-rendered sites (Webflow/Next/Framer) whose listing pages contain
    no anchors in the served HTML — Apollo Research and friends. Sitemaps are static XML and list
    every post. Follows one level of <sitemapindex>. Titles are derived from the URL slug, which is
    crude but adequate: the downstream enrich step fetches the real page and quotes it."""
    out = []
    try:
        body = _get(root.rstrip('/') + '/sitemap.xml', timeout=15)
    except Exception:
        return out
    locs = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', body)
    # follow nested sitemap indexes (post-sitemap.xml etc.), skipping tag/category maps
    nested = [l for l in locs if l.endswith('.xml')]
    if nested:
        for n in nested[:4]:
            if re.search(r'(tag|category|author)', n, re.I):
                continue
            try:
                locs += re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', _get(n, timeout=15))
            except Exception:
                pass
            time.sleep(0.2)
    seen = set()
    for u in locs:
        if u.endswith('.xml') or u in seen:
            continue
        if not _SITEMAP_CONTENT.search(u):
            continue
        path = urllib.parse.urlsplit(u).path.rstrip('/')
        slug = path.rsplit('/', 1)[-1]
        if not slug or len(slug) < 8:
            continue
        seen.add(u)
        title = re.sub(r'[-_]+', ' ', slug).strip()
        title = title[:1].upper() + title[1:]
        out.append(dict(title=title, url=u, blurb="", source="", published="", feed=""))
        if len(out) >= max_urls:
            break
    return out


def page_feeds(limit=None):
    """Scrape listing pages for orgs that publish no RSS.

    Covers feed_kind='page' AND feed_kind='none'. The 'none' bucket was originally skipped
    entirely, on the assumption those sites were unreachable — but most of them are perfectly
    fetchable and simply have no RSS (SafeAI ETH alone yields 30 papers). For those we fall back
    to the homepage URL as the listing page.
    """
    rows = [r for r in psql(
        "SELECT slug||E'\\t'||name||E'\\t'||coalesce(nullif(feed_url,''),url)||E'\\t'||coalesce(org_type,'') "
        "FROM alignment_orgs WHERE feed_kind IN ('page','none') "
        "AND coalesce(nullif(feed_url,''),url) IS NOT NULL ORDER BY slug").splitlines() if r]
    if limit:
        rows = rows[:limit]
    out, health = [], []
    for row in rows:
        parts = row.split("\t")
        if len(parts) < 3:
            continue
        slug, name, page_url = parts[0], parts[1], parts[2]
        otype = parts[3] if len(parts) > 3 else ""
        try:
            items = scrape_listing(page_url, name, f"page:{slug}")
            status = "ok"
            if not items:  # client-rendered listing → fall back to the sitemap
                base = re.match(r'(https?://[^/]+)', page_url)
                if base:
                    items = sitemap_urls(base.group(1))
                    for it in items:
                        it["source"], it["feed"] = name, f"sitemap:{slug}"
                    status = "sitemap" if items else "empty"
                else:
                    status = "empty"
            for it in items:
                it["org_type"] = otype
            out += items
            health.append((slug, status, len(items)))
        except Exception:
            health.append((slug, "fetch_error", 0))
        time.sleep(0.25)
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
    r"reinforcement learning|rlhf|diffusion models?|generative|"
    # the vocabulary advocacy/policy orgs actually use for AI systems — without these,
    # "Facial recognition surveillance expands in UK policing" reads as non-AI
    r"facial recognition|face recognition|biometrics?|algorithmic|automated decision|"
    r"predictive policing|deepfakes?|synthetic media|recommender systems?|"
    r"autonomous weapons?|automated systems?)\b", re.I)
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
    """Two gates, because the sources differ in how much we already know.

    CURATED (feed label org:/page:/sitemap:) — the item came from an organization we verified
    is an alignment/safety body. Requiring an AI keyword on top of that is redundant and costs
    real recall: 'Cluster-Norm for Unsupervised Probing of Knowledge' (Cadenza Labs) and
    'Parallax: Parameterized Local Linear Attention' (Tilde) name no AI term at all yet are
    exactly what we want. For these, drop only boilerplate, hiring and admin chatter.

    UNCURATED (arXiv queries, LessWrong/AF firehose) — anything can appear, so keep the full
    AI-signal AND research-signal requirement.
    """
    title = (item.get('title') or '').strip()
    text = f"{title} {item.get('blurb','')}"

    if re.sub(r'[^a-z ]', '', title.lower()).strip() in NAV_TITLES:
        return False
    if RESEARCH_NOISE.search(text) or JOBS_ADMIN.search(text):
        return False

    feed = item.get('feed') or ''
    curated = feed.startswith(('org:', 'page:', 'sitemap:'))
    otype = item.get('org_type') or ''

    # Relax the AI-keyword requirement ONLY for orgs whose entire output is AI research —
    # technical labs and academic centers, whose paper titles are often terse and domain-specific
    # ("Cluster-Norm for Unsupervised Probing of Knowledge").
    #
    # Broad-mandate organizations get no such pass. Coefficient Giving (ex-Open Philanthropy)
    # funds farm-animal welfare, lead paint and TB testing alongside AI; Brookings, HRW, Amnesty
    # and the UN are similar. Waving those through on "it came from a vetted org" would inject
    # chickens and vaccines into an AI-risk queue.
    if curated and otype in ('technical-lab', 'academic-center'):
        return len(title) >= 18

    if curated:
        return bool(AI_SIGNAL.search(text))

    return bool(AI_SIGNAL.search(text) and RESEARCH_SIGNAL.search(text))


# ---------------------------------------------------------------- collect
def collect_all():
    items = []
    for fn in (org_feeds, page_feeds, arxiv, community):
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
