#!/usr/bin/env python3
"""AI-risk news ingester — staging pipeline.

Stages (nothing goes live here; everything lands in the news_queue table):
  1. ingest   — pull broad AI-incident feeds (feeds.py)
  2. dedupe   — canonicalize+hash URLs; drop ones already seen (queue) or already a case
  3. prefilter— cheap keyword gate: keep only items with real AI-risk signal (free, instant)
  4. stage    — insert survivors into news_queue (status='new')

The slow part — local-Qwen risk routing — is a SEPARATE on-box daemon (classify_daemon.py)
that reads status='new' rows and fills qwen_risk/pol/why. Opus relevance-gating and the
human review queue are later stages. This module only does the free, fast, safe part.

Config via env or a local .aipi.env (gitignored): AIPI_SSH_HOST, AIPI_PG_CONTAINER, AIPI_DB.
"""
import os, re, sys, json, hashlib, subprocess, urllib.parse
sys.path.insert(0, os.path.dirname(__file__))
import feeds

HERE = os.path.dirname(os.path.abspath(__file__))
def _load_env():
    for p in (os.path.join(HERE, "..", ".aipi.env"), os.path.join(HERE, ".aipi.env")):
        if os.path.exists(p):
            for ln in open(p):
                ln = ln.strip()
                if ln and not ln.startswith("#") and "=" in ln:
                    k, v = ln.split("=", 1); os.environ.setdefault(k, v.strip().strip('"'))
_load_env()
SSH = os.environ.get("AIPI_SSH_HOST", "hetzner")   # 'local'/'' → run docker exec here (no ssh)
PGC = os.environ.get("AIPI_PG_CONTAINER", "")
DB  = os.environ.get("AIPI_DB", "")
KB_ROLE = os.environ.get("AIPI_KB_ROLE", "school")
_LOCAL = SSH in ("", "local", "localhost")

def psql(sql, want_out=True):
    if _LOCAL:  # docker exec here, sql passed as a single argv element (no shell quoting)
        run = ["docker", "exec", "-i", PGC, "psql", "-U", KB_ROLE, "-d", DB, "-At", "-c", sql]
    else:       # one shell command sent over ssh
        run = ["ssh", SSH, f'docker exec -i {PGC} psql -U {KB_ROLE} -d {DB} -At -c "{sql}"']
    r = subprocess.run(run, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip() if want_out else ""

def psql_stdin(sql):
    if _LOCAL:
        run = ["docker", "exec", "-i", PGC, "psql", "-U", KB_ROLE, "-d", DB, "-q"]
    else:
        run = ["ssh", SSH, f"docker exec -i {PGC} psql -U {KB_ROLE} -d {DB} -q"]
    r = subprocess.run(run, input=sql, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout

# ---- 2. dedupe helpers -----------------------------------------------------
TRACKING = re.compile(r"^(utm_|fbclid|gclid|ref|cmp|cb|ncid|__)")
def canonical(url):
    try:
        u = urllib.parse.urlsplit(url)
        q = [(k, v) for k, v in urllib.parse.parse_qsl(u.query) if not TRACKING.match(k)]
        netloc = u.netloc.lower().replace("www.", "")
        path = u.path.rstrip("/")
        return urllib.parse.urlunsplit((u.scheme or "https", netloc, path,
                                        urllib.parse.urlencode(sorted(q)), ""))
    except Exception:
        return url
def uhash(url):
    return hashlib.sha1(canonical(url).encode()).hexdigest()

# ---- 3. keyword pre-filter (free, instant) ---------------------------------
# Must contain an AI signal AND a risk/harm signal; and must NOT be pure business/product noise.
AI = re.compile(r"\b(ai|a\.i\.|artificial intelligence|llm|chatbot|gpt|claude|gemini|grok|"
                r"deepfake|generative|machine learning|neural|model|agent)\b", re.I)
RISK = re.compile(r"\b(hack|breach|exploit|malware|ransomware|cyberattack|vulnerab|jailbreak|"
                  r"prompt injection|deepfake|surveillance|facial recognition|weapon|drone|autonomous|"
                  r"bioweapon|biosecurity|csam|abuse|nonconsensual|psychosis|suicide|delusion|"
                  r"lawsuit|sued|investigation|probe|regulat|ban|misinform|disinform|manipulat|"
                  r"scam|fraud|impersonat|poison|backdoor|sabotage|scheming|deception|misalign|"
                  r"layoff|job loss|displace|bias|discriminat|harm|incident|leak|expos|"
                  r"safety|misuse|threat|attack|risk)\b", re.I)
NOISE = re.compile(r"\b(stock|shares|earnings|ipo|valuation|funding round|raises \$|market cap|"
                   r"buy now|deal|discount|coupon|review roundup|best (laptops|phones|deals)|"
                   r"how to invest|price prediction|quarterly)\b", re.I)
def prefilter(item):
    text = f"{item.get('title','')} {item.get('blurb','')}"
    if NOISE.search(text): return False
    return bool(AI.search(text) and RISK.search(text))

# ---- pipeline --------------------------------------------------------------
def sq(s): return (s or "").replace("'", "''")

def run(stage_only=False):
    print("• ingesting feeds")
    raw = feeds.collect_all()
    print(f"  raw items: {len(raw)}")

    # dedupe within batch
    seen_local, uniq = set(), []
    for it in raw:
        h = uhash(it["url"])
        if h in seen_local: continue
        seen_local.add(h); it["_h"] = h; uniq.append(it)
    print(f"  unique urls: {len(uniq)}")

    # pre-filter
    cand = [it for it in uniq if prefilter(it)]
    print(f"  after keyword pre-filter: {len(cand)}")

    # dedupe against already-seen (queue) and existing case/source urls
    known = set(x for x in psql("SELECT url_hash FROM news_queue").splitlines() if x)
    existing_urls = psql(
        "SELECT c->>'url' FROM real_issues, jsonb_array_elements(coalesce(score_cases,'[]'::jsonb)) c WHERE c->>'url' IS NOT NULL "
        "UNION SELECT url FROM real_issues_sources").splitlines()
    known |= {uhash(u) for u in existing_urls if u}
    fresh = [it for it in cand if it["_h"] not in known]
    print(f"  new (not seen / not already a case): {len(fresh)}")

    if stage_only or not fresh:
        return fresh

    # stage into news_queue
    rows = []
    for it in fresh:
        rows.append("('{}','{}','{}','{}','{}','{}','new')".format(
            sq(it["url"]), it["_h"], sq(it["title"])[:500], sq(it.get("blurb",""))[:800],
            sq(it.get("source","")), sq(it.get("published",""))))
    sql = ("\\set ON_ERROR_STOP on\nBEGIN;\nINSERT INTO news_queue "
           "(url,url_hash,title,blurb,source,published,status) VALUES\n"
           + ",\n".join(rows)
           + "\nON CONFLICT (url_hash) DO NOTHING;\nCOMMIT;\n")
    psql_stdin(sql)
    staged = psql("SELECT count(*) FROM news_queue WHERE status='new'")
    print(f"✓ staged {len(fresh)} new items | news_queue status=new: {staged}")
    return fresh

if __name__ == "__main__":
    run(stage_only="--dry" in sys.argv)
