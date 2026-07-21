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

Reply ONLY compact JSON: {{"risk":"<id or none>","pol":"better|worse|neutral","why":"<=8 words"}}""")

def classify(title, blurb):
    payload = {"model": MODEL, "stream": False,
               "options": {"temperature": 0, "num_predict": 120},   # Ollama
               "temperature": 0, "max_tokens": MAX_TOKENS,          # OpenAI-compatible (MLX, vLLM)
               "messages": [{"role": "system", "content": SYS},
                            {"role": "user", "content": f"Headline: {title}\nBlurb: {blurb or '(none)'}"}]}
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
    return {"risk": risk, "pol": pol, "why": (d.get("why") or "")[:120]}

def run(limit=None):
    lim = f" LIMIT {int(limit)}" if limit else ""
    rows = psql(f"SELECT id, replace(title,'|',' '), replace(coalesce(blurb,''),'|',' ') "
                f"FROM news_queue WHERE status='new' ORDER BY id{lim}").splitlines()
    print(f"to classify: {len(rows)} (model={MODEL})")
    done = dropped = 0
    for ln in rows:
        parts = ln.split("|", 2)
        if len(parts) < 2: continue
        rid, title = parts[0], parts[1]
        blurb = parts[2] if len(parts) > 2 else ""
        t0 = time.time()
        try:
            res = classify(title, blurb)
        except Exception as e:
            print(f"  #{rid} ERROR {e}"); continue
        if not res:
            print(f"  #{rid} unparseable, skip"); continue
        status = "classified" if res["risk"] != "none" else "dropped"
        if status == "classified": done += 1
        else: dropped += 1
        psql_stdin(
            "BEGIN;\nUPDATE news_queue SET qwen_risk='{}', qwen_pol='{}', qwen_why='{}', qwen_model='{}', "
            "status='{}', updated_at=now() WHERE id={};\nCOMMIT;\n".format(
                sq(res["risk"]), sq(res["pol"]), sq(res["why"]), sq(MODEL), status, int(rid)))
        print(f"  #{rid} [{int(time.time()-t0)}s] {res['risk']} / {res['pol']}  ← {title[:60]}")
    print(f"✓ classified={done} dropped(none)={dropped}")

if __name__ == "__main__":
    lim = None
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    run(lim)
