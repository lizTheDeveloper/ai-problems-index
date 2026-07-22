#!/usr/bin/env python3
"""On-box local-Qwen classifier (the free first pass). Runs ON the llm-inference host
(or anywhere that can reach the Ollama endpoint). Pulls news_queue rows with status='new',
asks Qwen to route each to a risk id (or 'none') + polarity, and marks them 'classified'
(or 'dropped' if none/irrelevant). Slow-but-async: it just churns between ingest cycles.

Env: AIPI_SSH_HOST / AIPI_PG_CONTAINER / AIPI_DB (DB access, via ssh docker exec like pipeline.py),
     AIPI_OLLAMA_URL (default http://localhost:11434), AIPI_QWEN_MODEL (default qwen3:4b).
Run:  python3 classify_daemon.py            # process all 'new'
      python3 classify_daemon.py --limit 20 # process a slice
"""
import os, sys, json, re, time, subprocess, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from pipeline import psql, psql_stdin, sq, _load_env  # reuse DB helpers
_load_env()

OLLAMA = os.environ.get("AIPI_OLLAMA_URL", "http://localhost:11434")
MODEL  = os.environ.get("AIPI_QWEN_MODEL", "qwen3:4b")
MAX_TOKENS = int(os.environ.get("AIPI_MAX_TOKENS", "160"))
# Qwen3 is a reasoning model; leave thinking ON and it never emits content. Default OFF.
NO_THINK = os.environ.get("AIPI_NO_THINK", "1") not in ("0", "false", "no")
RISKS  = json.load(open(os.path.join(os.path.dirname(__file__), "risks.json")))
RISK_IDS = [r["id"] for r in RISKS]
RISK_MENU = "\n".join(f"- {r['id']}: {r['title']}" for r in RISKS)

SYS = (f"""You triage AI-related news for a risk atlas. Given a headline and blurb, decide which SINGLE risk it best belongs to, or "none" if it is not clearly about a concrete AI risk/harm/incident (e.g. product launches, funding, generic hype, or only tangentially AI).

Risks:
{RISK_MENU}

Also judge polarity for that risk:
- "worse": bad news — a harm/incident, offensive capability advancing, new attack surface, deployment outpacing safeguards, a rollback of protections.
- "better": good news — a defensive win, a working mitigation/safeguard, an incident caught/disrupted, regulation that bites, evidence the risk is smaller than feared.
- "neutral": genuinely mixed / context.

Also produce a DEDUP KEY. Read this GOAL first, or the key will be useless:
Our pipeline pulls the SAME news story from many different sources — one incident written up by
several outlets, one company announcement reposted and rewritten. The key exists ONLY to catch
those duplicates so we keep a single copy. Two items about the SAME news event MUST get the
IDENTICAL key, even when the headlines are worded completely differently.

ONLY news events get a key. A news event is a dated thing that happened: an incident, breach,
lawsuit, ruling, fine, product launch, company/policy announcement, partnership. A research paper,
preprint, technical report, benchmark, or academic blog post is NOT a news event — it is a unique
work, there is nothing to deduplicate, so its key MUST be "". When in doubt (is this a paper or a
news story?), leave the key "".

For a news event, key = "<YYYY-MM> <entities> <action>":
- begin with the year-month from the DATE line below (e.g. 2026-07)
- then the named entities (companies/models/people/countries), lowercased, sorted alphabetically
- then ONE normalized action verb: hack/breach/compromise->breach, sue/lawsuit->lawsuit,
  ban/restrict->ban, launch/release/introduce/unveil->release, fine/penalize->fine,
  partner/deal->partnership, investigate/probe->probe
Example: "OpenAI model hacks Hugging Face" and "Hugging Face hacked by rogue AI model" (both dated
July 2026) BOTH -> "2026-07 huggingface openai breach". Two outlets, one event, one key.

You will be shown recent keys; if THIS item is the same news event as one of them, REUSE that key
verbatim. Never invent a topic/field key like "ai safety" or a publisher key like "center long
risk term" — those are not events.

Reply ONLY compact JSON:
{{"risk":"<id or none>","pol":"better|worse|neutral","why":"<=8 words","event_key":"<news key or '' for papers>"}}""")

def classify(title, blurb, date_ym="", recent_keys=None):
    ctx = ""
    if recent_keys:
        ctx = ("RECENT NEWS KEYS (reuse one verbatim if this is the same news event):\n"
               + "\n".join(f"- {k}" for k in recent_keys) + "\n\n")
    datel = f"DATE: {date_ym}\n" if date_ym else "DATE: (unknown)\n"
    payload = {"model": MODEL, "stream": False,
               "options": {"temperature": 0, "num_predict": 120},   # Ollama
               "temperature": 0, "max_tokens": MAX_TOKENS,          # OpenAI-compatible (MLX, vLLM)
               "messages": [{"role": "system", "content": SYS},
                            {"role": "user", "content": f"{ctx}{datel}Headline: {title}\nBlurb: {blurb or '(none)'}"}]}
    # Qwen3 is a REASONING model: left in thinking mode it spends the whole budget on <think>
    # and returns a message with a `reasoning` key and EMPTY `content` (finish_reason='length'),
    # so every classification silently comes back None. Turning thinking off yields clean JSON
    # in ~35 tokens. Ollama ignores this field; MLX/vLLM honour it.
    if NO_THINK:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    body = json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        msg = json.load(r)["choices"][0]["message"]
    # some servers put the answer in `reasoning`/`reasoning_content` when thinking is on
    content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
    m = re.search(r"\{.*\}", content, re.S)
    if not m: return None
    try:
        d = json.loads(m.group())
    except Exception:
        return None
    risk = d.get("risk", "none")
    if risk not in RISK_IDS: risk = "none"
    pol = d.get("pol", "worse")
    if pol not in ("better", "worse", "neutral"): pol = "worse"
    # canonicalize the news key: keep a leading YYYY-MM date prefix in place, then lowercase +
    # sort the remaining entity/action tokens so two orderings compare equal. Empty for papers.
    raw = (d.get("event_key") or "").strip().lower()
    dm = re.match(r"\s*((?:19|20)\d{2}-\d{2})\b(.*)", raw)
    prefix, rest = (dm.group(1), dm.group(2)) if dm else ("", raw)
    rest = re.sub(r"[^a-z0-9 ]", " ", rest)
    body_toks = " ".join(sorted(set(t for t in rest.split() if len(t) > 1)))
    ek = (f"{prefix} {body_toks}".strip() if prefix else body_toks)[:200]
    return {"risk": risk, "pol": pol, "why": (d.get("why") or "")[:120], "event_key": ek}

RECENT_KEYS_N = int(os.environ.get("AIPI_RECENT_KEYS", "100"))

_MON = {m: f"{i:02d}" for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
def _year_month(published):
    """Normalize a freeform feed date to 'YYYY-MM' for the news key prefix, else ''."""
    s = (published or "").strip()
    if not s:
        return ""
    m = re.search(r"\b((?:19|20)\d{2})-(\d{2})", s)             # ISO 2026-07-...
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"\b(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+((?:19|20)\d{2})", s)   # 15 Jul 2026 / RFC822
    if m:
        return f"{m.group(3)}-{_MON.get(m.group(2).lower(), '01')}"
    m = re.search(r"\b([A-Za-z]{3})[a-z]*\s+\d{1,2},?\s+((?:19|20)\d{2})", s)   # Jul 15, 2026
    if m:
        return f"{m.group(2)}-{_MON.get(m.group(1).lower(), '01')}"
    m = re.search(r"\b((?:19|20)\d{2})\b", s)                   # bare year fallback
    return f"{m.group(1)}-01" if m else ""

def run(limit=None):
    from collections import deque
    lim = f" LIMIT {int(limit)}" if limit else ""
    rows = psql(f"SELECT id, replace(title,'|',' '), replace(coalesce(blurb,''),'|',' '), "
                f"replace(coalesce(published,''),'|',' ') "
                f"FROM news_queue WHERE status='new' ORDER BY id{lim}").splitlines()
    print(f"to classify: {len(rows)} (model={MODEL})")

    # Rolling window of recent event keys, shown to the model so it REUSES an existing key when a
    # new story is the same event (dedup at classification time, not just post-hoc clustering).
    # Seed from keys already in the queue so a fresh run still sees prior events.
    seed = [k for k in psql(
        "SELECT DISTINCT qwen_event_key FROM news_queue WHERE coalesce(qwen_event_key,'')<>'' "
        f"ORDER BY qwen_event_key DESC LIMIT {RECENT_KEYS_N}").splitlines() if k]
    recent = deque(seed, maxlen=RECENT_KEYS_N)

    done = dropped = 0
    for ln in rows:
        parts = ln.split("|", 3)
        if len(parts) < 2: continue
        rid, title = parts[0], parts[1]
        blurb = parts[2] if len(parts) > 2 else ""
        date_ym = _year_month(parts[3]) if len(parts) > 3 else ""
        t0 = time.time()
        try:
            res = classify(title, blurb, date_ym=date_ym, recent_keys=list(recent))
        except Exception as e:
            print(f"  #{rid} ERROR {e}"); continue
        if not res:
            print(f"  #{rid} unparseable, skip"); continue
        ek = res.get("event_key", "")
        if ek and ek not in recent:
            recent.append(ek)
        status = "classified" if res["risk"] != "none" else "dropped"
        if status == "classified": done += 1
        else: dropped += 1
        psql_stdin(
            "BEGIN;\nUPDATE news_queue SET qwen_risk='{}', qwen_pol='{}', qwen_why='{}', qwen_event_key='{}', "
            "qwen_model='{}', status='{}', updated_at=now() WHERE id={};\nCOMMIT;\n".format(
                sq(res["risk"]), sq(res["pol"]), sq(res["why"]), sq(res.get("event_key","")),
                sq(MODEL), status, int(rid)))
        print(f"  #{rid} [{int(time.time()-t0)}s] {res['risk']} / {res['pol']}  ← {title[:60]}")
    print(f"✓ classified={done} dropped(none)={dropped}")

if __name__ == "__main__":
    lim = None
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    run(lim)
