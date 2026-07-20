#!/usr/bin/env python3
"""DB-driven Risk Atlas builder → a SCORECARD that is also a mini-SPA.
List view = filterable grid of navigational tiles. Clicking a tile routes to that
risk's own full page (hash #atlas/<id> embedded, #<id> standalone) with its own
timeline built from the dated case studies. Browser back + deep-links work.

Rerun after any real_issues change:
  1) re-dump atlas_issues.json (score_* + score_markers/threat/kind/cases + sources)
  2) python3 build_atlas.py
  3) publish atlas_content.html to pages slug 'ai-risk-atlas' as -U school
"""
import json, html, re
from collections import Counter

issues = json.load(open('atlas_issues.json'))
NAV = open('nav_block.html').read()
SUBMIT = open('submit_widget.html').read()

EXCLUDE = {'ai-environmental-footprint'}  # has its own Environment tab
issues = [i for i in issues if i['id'] not in EXCLUDE]

FA = {
 'alert-triangle':'fa-triangle-exclamation','alert-octagon':'fa-triangle-exclamation','alert':'fa-triangle-exclamation',
 'shield-alert':'fa-shield-halved','shield':'fa-shield','brain':'fa-brain','cctv':'fa-video','clock':'fa-clock',
 'eye':'fa-eye','file-question':'fa-circle-question','filter':'fa-filter','megaphone':'fa-bullhorn','target':'fa-crosshairs',
 'users':'fa-users','user-x':'fa-user-slash','vote':'fa-check-to-slot','zap':'fa-bolt'}
def icon(n): return FA.get(n or '', 'fa-circle-dot')
def esc(s): return html.escape(s or '')
def paras(t):
    t = t or ''
    return ''.join(f'<p>{esc(p.strip())}</p>' for p in t.split('\n\n') if p.strip())

STATE = {
 'contained':{'label':'Contained','c':'#2ea043'}, 'holding':{'label':'Holding','c':'#3a9dc4'},
 'slipping':{'label':'Slipping','c':'#d9902b'}, 'losing':{'label':'Losing ground','c':'#e5484d'},
 'unknown':{'label':'Unknown','c':'#8b94a0'}}
TREND = {
 'up':{'a':'↑','t':'improving','c':'#2ea043'}, 'flat':{'a':'→','t':'steady','c':'#8b94a0'},
 'down':{'a':'↓','t':'worsening','c':'#e5484d'}, 'q':{'a':'?','t':'unmeasured','c':'#8b94a0'}}
STATE_ORDER = ['losing','slipping','holding','contained','unknown']
THREAT = {'Severe':'#e5484d','High':'#d9902b','Moderate':'#3a9dc4','Low':'#8b94a0'}
KIND_ICON = {
 'Child safety':'fa-child-reaching','CBRN & bioweapons':'fa-biohazard','Cyber & misuse':'fa-bug',
 'Surveillance & rights':'fa-eye','Information & democracy':'fa-comments','Loss of control':'fa-robot',
 'Military & autonomous weapons':'fa-crosshairs','Governance & accountability':'fa-landmark-dome',
 'Economic & labor':'fa-briefcase','Psychological & social':'fa-brain','Rights & inclusion':'fa-users',
 'Epistemic & evaluation':'fa-flask-vial'}

def norm_state(s): return s if s in STATE else 'unknown'
def norm_trend(t): return t if t in TREND else 'q'
_MONTHS = {m:i for i,m in enumerate(
    ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'], start=1)}
def case_sortkey(when):
    """(year, month) best-effort chronological key; undated → far future."""
    w = (when or '').lower()
    ym = re.search(r'(19|20)\d{2}', w)
    year = int(ym.group()) if ym else 9999
    month = 0
    mm = re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', w)
    if mm: month = _MONTHS[mm.group(1)]
    else:
        q = re.search(r'\bq([1-4])\b', w)
        if q: month = (int(q.group(1)) - 1) * 3 + 1
    return (year, month)

def tags_html(threat, kind):
    if not (threat or kind): return ''
    parts = ''
    if threat:
        tc = THREAT.get(threat, '#8b94a0')
        parts += (f'<span class="rx-th" style="color:{tc};border-color:color-mix(in srgb,{tc} 45%,transparent);'
                  f'background:color-mix(in srgb,{tc} 13%,transparent)"><span class="thk">Threat</span> {esc(threat)}</span>')
    if kind:
        parts += f'<span class="rx-kind"><i class="fas {KIND_ICON.get(kind,"fa-tag")}"></i>{esc(kind)}</span>'
    return f'<span class="rx-tags">{parts}</span>'

def scoreline_html(st, tr, conf):
    sinfo, tinfo = STATE[st], TREND[tr]
    return (f'<span class="rx-score">'
            f'<span class="v"><span class="vk">State</span>'
            f'<span class="rx-state" style="color:{sinfo["c"]}"><span class="dot" style="background:{sinfo["c"]}"></span>{sinfo["label"]}</span></span>'
            f'<span class="v"><span class="vk">Trend</span>'
            f'<span class="rx-trend" style="color:{tinfo["c"]}">{tinfo["a"]} {tinfo["t"]}</span></span>'
            f'<span class="v"><span class="vk">Evidence</span>'
            f'<span class="rx-conf{" rx-confirmed" if conf=="confirmed" else ""}">{esc(conf)}</span></span>'
            f'</span>')

tiles, pages = [], []
for it in sorted(issues, key=lambda x: (STATE_ORDER.index(norm_state(x.get('score_state'))), x['title'])):
    rid = it['id']
    st = norm_state(it.get('score_state')); tr = norm_trend(it.get('score_trend'))
    conf = it.get('score_conf') or 'estimated'; note = it.get('score_note') or ''
    sinfo = STATE[st]; threat = it.get('score_threat'); kind = it.get('score_kind')
    tg = tags_html(threat, kind); score = scoreline_html(st, tr, conf)

    # --- list tile (navigational) ---
    tiles.append(
        f'<button class="rx-tile" data-go="{esc(rid)}" data-state="{st}" data-kind="{esc(kind or "")}" '
        f'data-text="{esc((it["title"]+" "+(it.get("summary") or "")).lower())}" style="--sc:{sinfo["c"]}">'
        f'<span class="rx-ic" style="background:color-mix(in srgb,{sinfo["c"]} 16%,transparent);color:{sinfo["c"]}">'
        f'<i class="fas {icon(it["icon"])}"></i></span>'
        f'<span class="rx-head"><span class="rx-title">{esc(it["title"])}</span>'
        f'<span class="rx-sum">{esc(it.get("summary"))}</span>{tg}</span>'
        f'{score}'
        f'<span class="rx-goarrow"><i class="fas fa-chevron-right"></i></span>'
        f'</button>')

    # --- detail page pieces ---
    srcs = it.get('sources') or []
    src_html = ''.join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="noopener">{esc(s["title"])} ↗</a></li>' for s in srcs)

    mk = it.get('score_markers') or {}
    def marker_list(items):
        return ''.join(
            f'<li>{esc(m.get("m"))}'
            + (f' <a href="{esc(m["url"])}" target="_blank" rel="noopener" class="mk-src"'
               + (f' title="{esc(m["q"])}"' if m.get("q") else '') + f'>{esc(m.get("src") or "source")} ↗</a>' if m.get("url")
               else (f' <span class="mk-src">{esc(m.get("src"))}</span>' if m.get("src") else '')) + '</li>'
            for m in (items or []))
    better = mk.get('better') or []; worse = mk.get('worse') or []
    markers_html = ''
    if better or worse:
        cols = ''
        if better:
            cols += (f'<div class="mk-col mk-up"><div class="mk-h"><i class="fas fa-arrow-trend-up"></i> Getting better</div>'
                     f'<ul>{marker_list(better)}</ul></div>')
        if worse:
            cols += (f'<div class="mk-col mk-down"><div class="mk-h"><i class="fas fa-arrow-trend-down"></i> Getting worse</div>'
                     f'<ul>{marker_list(worse)}</ul></div>')
        markers_html = f'<div class="rx-sub"><b>Which way it&rsquo;s moving &mdash; the markers</b><div class="mk-grid">{cols}</div></div>'

    # cases → a chronological timeline for this risk
    cases = sorted(it.get('score_cases') or [], key=lambda c: case_sortkey(c.get('when')))
    timeline_html = ''
    if cases:
        evs = ''
        for c in cases:
            evs += (f'<div class="ctl-item"><div class="ctl-dot"></div>'
                    + (f'<div class="ctl-when">{esc(c.get("when"))}</div>' if c.get("when") else '<div class="ctl-when"></div>')
                    + f'<div class="ctl-body"><div class="ctl-t">{esc(c.get("title"))}</div>'
                    + f'<p>{esc(c.get("what"))}</p>'
                    + (f'<a href="{esc(c["url"])}" target="_blank" rel="noopener" class="ctl-src"'
                       + (f' title="{esc(c["q"])}"' if c.get("q") else '')
                       + f'><i class="fas fa-arrow-up-right-from-square"></i>{esc(c.get("src") or "source")}</a>' if c.get("url") else '')
                    + '</div></div>')
        timeline_html = (f'<div class="rx-sub"><b>Timeline &mdash; it actually happening</b>'
                         f'<div class="ctl-track">{evs}</div></div>')

    body = (
        (f'<div class="rx-assess"><span class="rx-al">Assessment</span>{esc(note)}</div>' if note else '')
        + paras(it.get("description"))
        + markers_html
        + timeline_html
        + (f'<div class="rx-sub"><b>Why it matters</b>{paras(it.get("why_it_matters"))}</div>' if it.get('why_it_matters') else '')
        + (f'<div class="rx-sub"><b>What&rsquo;s being done</b>{paras(it.get("what_being_done"))}</div>' if it.get('what_being_done') else '')
        + (f'<div class="rx-sub"><b>Sources</b><ul class="rx-src">{src_html}</ul></div>' if src_html else ''))

    pages.append(
        f'<article class="rx-page" id="p-{esc(rid)}" data-page="{esc(rid)}" style="--sc:{sinfo["c"]}">'
        f'<button class="rx-back" type="button"><i class="fas fa-arrow-left"></i> All risks</button>'
        f'<div class="rx-phero">'
        f'<span class="rx-ic rx-icbig" style="background:color-mix(in srgb,{sinfo["c"]} 16%,transparent);color:{sinfo["c"]}">'
        f'<i class="fas {icon(it["icon"])}"></i></span>'
        f'<div class="rx-pht"><h2 class="rx-ptitle">{esc(it["title"])}</h2>'
        f'<p class="rx-psum">{esc(it.get("summary"))}</p>{tg}</div></div>'
        f'<div class="rx-pscore">{score}</div>'
        f'<div class="rx-pbody">{body}</div>'
        f'<div class="airx-sub" data-target-type="risk" data-target-id="{esc(rid)}" data-target-label="{esc(it["title"])}"></div>'
        f'<button class="rx-back rx-back2" type="button"><i class="fas fa-arrow-left"></i> Back to all risks</button>'
        f'</article>')

# tallies + filters
sc = Counter(norm_state(i.get('score_state')) for i in issues)
tally = ''.join(f'<span class="tpill"><span class="dot" style="background:{STATE[k]["c"]}"></span>{sc[k]} {STATE[k]["label"]}</span>'
                for k in STATE_ORDER if sc[k])
fbtns = '<button class="fbtn on" data-s="all">All ('+str(len(issues))+')</button>' + ''.join(
    f'<button class="fbtn" data-s="{k}"><span class="dot" style="background:{STATE[k]["c"]}"></span>{STATE[k]["label"]} ({sc[k]})</button>'
    for k in STATE_ORDER if sc[k])
kc = Counter(i.get('score_kind') for i in issues if i.get('score_kind'))
kind_opts = '<option value="all">All danger types</option>' + ''.join(
    f'<option value="{esc(k)}">{esc(k)} ({kc[k]})</option>' for k in sorted(kc))
kind_select = f'<label class="kindsel"><span>Kind</span><select id="rx-kind">{kind_opts}</select></label>'

ids_js = json.dumps([it['id'] for it in issues])

STYLE = r"""<style>
.rax{--l:var(--color-border,#2a2f36);--mut:var(--color-text-muted,#8b94a0);--panel:var(--color-bg-card,#1c1f24);
 --ink:var(--color-text,#eef2f6);--pri:var(--color-primary,#34a58e);--acc:var(--color-accent,#e0741c);--bg:var(--color-bg,#0c0d10);
 font-family:var(--font-primary,system-ui,sans-serif);color:var(--ink)}
.rax *{box-sizing:border-box}
.rax .lede{font-size:1.04rem;color:var(--mut);max-width:72ch;line-height:1.6}
.rax em{font-style:normal;color:var(--ink);border-bottom:1.5px solid color-mix(in srgb,var(--pri) 55%,transparent)}
.rax .tally{display:flex;gap:7px;flex-wrap:wrap;margin:16px 0 10px}
.rax .tpill{display:inline-flex;align-items:center;gap:7px;font-size:.78rem;font-weight:700;font-family:ui-monospace,monospace;
 border:1px solid var(--l);border-radius:999px;padding:5px 11px;color:var(--ink);background:var(--panel)}
.rax .dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;display:inline-block}
.rax .legend{display:flex;gap:8px 18px;flex-wrap:wrap;font-size:.74rem;color:var(--mut);margin:2px 0 6px}
.rax .legend b{color:var(--ink);font-weight:700}
.rax .ctrl{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0;position:sticky;top:0;z-index:5;
 background:color-mix(in srgb,var(--bg) 90%,transparent);padding:9px 0;backdrop-filter:blur(6px)}
.rax .fbtn{display:inline-flex;align-items:center;gap:7px;font-size:.8rem;font-weight:600;color:var(--mut);background:transparent;
 border:1px solid var(--l);border-radius:999px;padding:6px 13px;cursor:pointer;font-family:inherit}
.rax .fbtn.on{color:var(--bg);background:var(--pri);border-color:var(--pri)}
.rax .fbtn.on .dot{outline:1px solid color-mix(in srgb,var(--bg) 60%,transparent)}
.rax .kindsel{display:inline-flex;align-items:center;gap:7px;font-size:.78rem;color:var(--mut)}
.rax .kindsel span{font-family:ui-monospace,monospace;font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em}
.rax .kindsel select{font-family:inherit;font-size:.82rem;color:var(--ink);background:var(--panel);border:1px solid var(--l);
 border-radius:999px;padding:7px 12px;cursor:pointer;max-width:220px}
.rax input.q{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--l);border-radius:999px;padding:8px 15px;
 color:var(--ink);font-family:inherit;font-size:.86rem}
.rax .count{font-size:.78rem;color:var(--mut);font-family:ui-monospace,monospace}
.rax .grid{display:grid;grid-template-columns:minmax(0,1fr);gap:10px;margin-top:6px}
/* ---- list tile ---- */
.rax .rx-tile{display:flex;align-items:flex-start;gap:13px;width:100%;text-align:left;font-family:inherit;cursor:pointer;
 border:1px solid var(--l);border-left:3px solid var(--sc);border-radius:13px;background:var(--panel);padding:14px 16px;
 color:inherit;transition:border-color .12s,transform .12s,box-shadow .12s}
.rax .rx-tile:hover{border-color:color-mix(in srgb,var(--sc) 60%,var(--l));transform:translateY(-1px);
 box-shadow:0 8px 22px -14px color-mix(in srgb,var(--sc) 70%,transparent)}
.rax .rx-tile:focus-visible{outline:2px solid var(--pri);outline-offset:2px}
.rax .rx-ic{flex:0 0 auto;width:38px;height:38px;border-radius:10px;display:grid;place-items:center;font-size:1rem}
.rax .rx-head{flex:1;min-width:0}
.rax .rx-title{display:block;font-weight:700;font-size:1rem;letter-spacing:-.01em;line-height:1.25}
.rax .rx-sum{display:block;font-size:.85rem;color:var(--mut);line-height:1.4;margin-top:3px}
.rax .rx-tags{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px;align-items:center}
.rax .rx-th{display:inline-flex;align-items:center;gap:6px;font-size:.72rem;font-weight:800;border:1px solid;border-radius:7px;padding:3px 9px}
.rax .rx-th .thk{font-family:ui-monospace,monospace;font-size:.58rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;opacity:.7}
.rax .rx-kind{display:inline-flex;align-items:center;gap:6px;font-size:.72rem;font-weight:600;color:var(--mut);
 border:1px solid var(--l);border-radius:7px;padding:3px 9px;background:var(--bg)}
.rax .rx-kind i{font-size:.82em;opacity:.8}
.rax .rx-score{flex:0 0 auto;display:flex;flex-direction:column;align-items:flex-end;gap:6px;white-space:nowrap}
.rax .rx-score .v{display:flex;align-items:center;gap:8px;justify-content:flex-end}
.rax .rx-score .vk{font-family:ui-monospace,monospace;font-size:.56rem;font-weight:700;text-transform:uppercase;
 letter-spacing:.07em;color:var(--mut);min-width:54px;text-align:right;flex:0 0 auto}
.rax .rx-state{font-size:.84rem;font-weight:800;display:inline-flex;align-items:center;gap:7px}
.rax .rx-trend{font-size:.78rem;font-weight:700}
.rax .rx-conf{font-size:.64rem;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.rax .rx-conf.rx-confirmed{color:#2ea043;font-weight:800;display:inline-flex;align-items:center;gap:5px}
.rax .rx-conf.rx-confirmed::before{content:"\f058";font-family:"Font Awesome 6 Free";font-weight:900;font-size:.9em}
.rax .rx-goarrow{flex:0 0 auto;align-self:center;color:var(--mut);font-size:.85rem;opacity:.6;transition:transform .12s,opacity .12s}
.rax .rx-tile:hover .rx-goarrow{opacity:1;color:var(--sc);transform:translateX(3px)}
.rax .none{color:var(--mut);padding:30px;text-align:center;font-size:.9rem}
.rax .rx-spin{display:flex;align-items:center;justify-content:center;gap:11px;padding:70px 20px;color:var(--mut);font-size:.92rem}
.rax .rx-spin i{color:var(--pri);font-size:1.2rem}
.rax .rx-spin a{color:var(--pri)}
/* ---- detail page ---- */
.rax #rx-detail{display:none}
.rax.detail #rx-list{display:none}
.rax.detail #rx-detail{display:block}
.rax .rx-back{display:inline-flex;align-items:center;gap:8px;font-family:inherit;font-size:.82rem;font-weight:700;cursor:pointer;
 color:var(--pri);background:transparent;border:1px solid var(--l);border-radius:10px;padding:8px 14px;transition:all .12s}
.rax .rx-back:hover{border-color:var(--pri);background:color-mix(in srgb,var(--pri) 10%,transparent)}
.rax .rx-back2{margin-top:24px}
.rax .rx-phero{display:flex;align-items:flex-start;gap:15px;margin:18px 0 4px}
.rax .rx-icbig{width:52px;height:52px;font-size:1.4rem;border-radius:13px}
.rax .rx-ptitle{margin:0;font-size:clamp(1.4rem,3.5vw,1.9rem);letter-spacing:-.02em;line-height:1.15;color:var(--ink);border:none;padding:0}
.rax .rx-psum{margin:6px 0 0;font-size:1rem;color:var(--mut);line-height:1.5;max-width:72ch}
.rax .rx-phero .rx-tags{margin-top:11px}
.rax .rx-pscore{display:flex;justify-content:flex-start;padding:14px 0;margin:8px 0 4px;border-top:1px solid var(--l);border-bottom:1px solid var(--l)}
.rax .rx-pscore .rx-score{flex-direction:row;align-items:center;gap:22px}
.rax .rx-pscore .v{flex-direction:column;align-items:flex-start;gap:3px}
.rax .rx-pscore .vk{text-align:left}
.rax .rx-pbody{margin-top:16px}
.rax .rx-pbody>p{font-size:.94rem;line-height:1.65;color:var(--ink);margin:0 0 11px;max-width:74ch}
.rax .rx-assess{background:color-mix(in srgb,var(--sc) 9%,transparent);border:1px solid color-mix(in srgb,var(--sc) 30%,transparent);
 border-radius:11px;padding:12px 15px;font-size:.95rem;line-height:1.6;color:var(--ink);margin:0 0 16px}
.rax .rx-assess .rx-al{display:block;font-family:ui-monospace,monospace;font-size:.62rem;text-transform:uppercase;
 letter-spacing:.07em;color:var(--sc);font-weight:700;margin-bottom:4px}
.rax .rx-sub{margin-top:20px;border-top:1px dashed var(--l);padding-top:13px}
.rax .rx-sub>b{display:block;font-family:ui-monospace,monospace;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--pri);margin-bottom:8px}
.rax .rx-sub p{font-size:.9rem;color:var(--mut);line-height:1.6}
.rax ul.rx-src{margin:0;padding-left:18px;font-size:.85rem}.rax ul.rx-src li{margin:4px 0}.rax ul.rx-src a{color:var(--pri)}
/* markers */
.rax .mk-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.rax .mk-col{border:1px solid var(--l);border-radius:11px;padding:11px 13px;background:color-mix(in srgb,var(--panel) 60%,transparent)}
.rax .mk-up{border-left:3px solid #2ea043}.rax .mk-down{border-left:3px solid #e5484d}
.rax .mk-h{font-family:ui-monospace,monospace;font-size:.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;
 display:flex;align-items:center;gap:7px;margin-bottom:7px}
.rax .mk-up .mk-h{color:#2ea043}.rax .mk-down .mk-h{color:#e5484d}
.rax .mk-col ul{margin:0;padding-left:16px}
.rax .mk-col li{font-size:.86rem;line-height:1.55;color:var(--ink);margin:0 0 7px}
.rax .mk-col li:last-child{margin-bottom:0}
.rax .mk-src{display:inline-block;font-size:.74rem;color:var(--pri);text-decoration:none}
.rax .mk-src:hover{text-decoration:underline}
/* per-risk timeline */
.rax .ctl-track{position:relative;margin-top:4px}
.rax .ctl-item{display:grid;grid-template-columns:112px 16px 1fr;gap:0 12px;position:relative;padding-bottom:20px}
.rax .ctl-item::before{content:"";position:absolute;left:119px;top:16px;bottom:-4px;width:2px;background:var(--l)}
.rax .ctl-item:last-child::before{display:none}
.rax .ctl-when{grid-column:1;text-align:right;font-family:ui-monospace,monospace;font-size:.72rem;font-weight:700;color:var(--acc);padding-top:1px;line-height:1.35;overflow-wrap:anywhere}
.rax .ctl-dot{grid-column:2;width:13px;height:13px;border-radius:50%;margin-top:3px;background:var(--bg);border:2px solid var(--acc);z-index:1}
.rax .ctl-body{grid-column:3}
.rax .ctl-t{font-weight:700;font-size:.95rem;color:var(--ink);line-height:1.3;margin-bottom:3px}
.rax .ctl-body p{margin:0 0 6px;font-size:.87rem;line-height:1.55;color:var(--mut);max-width:70ch}
.rax a.ctl-src{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;color:var(--pri);text-decoration:none;font-family:ui-monospace,monospace}
.rax a.ctl-src:hover{text-decoration:underline}
@media(max-width:600px){
 .rax .rx-tile{flex-wrap:wrap}
 .rax .rx-score{flex-direction:row;align-items:center;flex-wrap:wrap;gap:8px 12px;width:100%;margin-top:6px;padding-left:51px}
 .rax .rx-goarrow{display:none}
 .rax .mk-grid{grid-template-columns:1fr}
 .rax .rx-pscore .rx-score{flex-direction:column;align-items:flex-start;gap:10px}
 .rax .ctl-item{grid-template-columns:14px 1fr;gap:0 10px}
 .rax .ctl-item::before{left:6px;top:16px}
 .rax .ctl-when{grid-column:2;text-align:left;grid-row:1;padding:0 0 3px}
 .rax .ctl-dot{grid-column:1;grid-row:1}
 .rax .ctl-body{grid-column:2;grid-row:2}
}
</style>"""

BODY = NAV + SUBMIT + f"""{STYLE}
<div class="rax" id="rax">
  <div id="rx-list">
  <p class="lede">A scorecard for the AI Problems Index's risk catalog — <em>{len(issues)} real, sourced issues</em>,
  each graded on <b style="color:var(--ink)">where it stands</b>, <b style="color:var(--ink)">which way it's moving</b>, and
  <b style="color:var(--ink)">how firm the evidence is</b>. Tap any risk to open its own page — the full breakdown, timeline, and receipts.</p>
  <div class="tally">{tally}</div>
  <div class="legend">
    <span><b>State</b> &mdash; where it stands: contained &rarr; holding &rarr; slipping &rarr; losing ground (best&rarr;worst)</span>
    <span><b>Trend</b> &mdash; which way it's moving: &uarr; improving &middot; &rarr; steady &middot; &darr; worsening &middot; ? unmeasured</span>
    <span><b>Evidence</b> &mdash; how firm: <span style="color:#2ea043;font-weight:700">confirmed</span> (documented cases) &middot; measured &middot; estimated &middot; contested</span>
  </div>
  <div class="ctrl" id="rx-ctrl">
    {fbtns}
    {kind_select}
    <input class="q" id="rx-q" type="search" placeholder="search issues&hellip;" aria-label="search issues">
    <span class="count" id="rx-count"></span>
  </div>
  <div class="grid" id="rx-grid">
    {''.join(tiles)}
  </div>
  <p class="none" id="rx-none" style="display:none">No issues match.</p>
  <p style="font-size:.8rem;color:var(--mut);margin-top:22px">Part of the <a href="/x/ai-problems-index">AI Problems Index</a>.
  Live from the knowledge base; allegations are labeled as such in each entry.</p>
  </div>
  <div id="rx-detail"></div>
</div>
<script>
(function(){{
  var root=document.getElementById('rax'); if(!root) return;
  var tiles=[].slice.call(root.querySelectorAll('.rx-tile'));
  var detailEl=root.querySelector('#rx-detail');
  var ctrl=root.querySelector('#rx-ctrl'), q=root.querySelector('#rx-q'),
      countEl=root.querySelector('#rx-count'), none=root.querySelector('#rx-none'),
      kindSel=root.querySelector('#rx-kind');
  var IDS={ids_js};
  var idset={{}}; IDS.forEach(function(i){{idset[i]=1;}});

  // ---- list filtering ----
  var st='all', term='', kind='all';
  function applyFilter(){{
    var shown=0;
    tiles.forEach(function(c){{
      var ok=(st==='all'||c.dataset.state===st)&&(kind==='all'||c.dataset.kind===kind)&&(!term||c.dataset.text.indexOf(term)>=0);
      c.style.display=ok?'':'none'; if(ok)shown++;
    }});
    countEl.textContent=shown+' shown'; none.style.display=shown?'none':'';
  }}
  ctrl.querySelectorAll('.fbtn').forEach(function(b){{b.onclick=function(){{st=b.dataset.s;
    ctrl.querySelectorAll('.fbtn').forEach(function(x){{x.classList.toggle('on',x===b);}});applyFilter();}};}});
  if(kindSel) kindSel.addEventListener('change',function(){{kind=kindSel.value;applyFilter();}});
  q.addEventListener('input',function(){{term=q.value.trim().toLowerCase();applyFilter();}});
  applyFilter();

  // ---- detail bundle: fetched in the background, rendered on demand ----
  // Detail pages live in a separate lightweight bundle so this list loads fast; we
  // fetch it once (warm in the background) and inject just the opened risk's page.
  var bundle=null, bstate='idle', waiters=[];
  function loadBundle(){{
    if(bstate==='done'||bstate==='loading') return;
    bstate='loading';
    fetch('/x/ai-risk-atlas-detail',{{credentials:'same-origin'}}).then(function(r){{
      if(!r.ok) throw new Error(r.status); return r.text();
    }}).then(function(html){{
      var doc=new DOMParser().parseFromString(html,'text/html');
      var scope=doc.querySelector('main.page-wrapper')||doc.body;
      bundle={{}};
      [].slice.call(scope.querySelectorAll('.rx-page')).forEach(function(a){{ bundle[a.dataset.page]=a.outerHTML; }});
      bstate='done';
    }}).catch(function(){{ bstate='error'; }}).then(function(){{
      var w=waiters.splice(0); w.forEach(function(f){{f();}});
    }});
  }}
  function whenReady(cb){{ if(bstate==='done'||bstate==='error') cb(); else {{ waiters.push(cb); loadBundle(); }} }}

  // ---- routing (pure function of location.hash) ----
  // embedded in hub → "#atlas/<id>"; standalone → "#<id>". Read the LAST segment either way.
  function embedded(){{ return !!document.querySelector('.apx'); }}
  function base(){{ return embedded() ? 'atlas' : ''; }}
  function currentId(){{
    var parts=(location.hash||'').replace(/^#/,'').split('/');
    var last=parts[parts.length-1];
    return idset[last] ? last : null;
  }}
  function showList(){{ root.classList.remove('detail'); detailEl.innerHTML=''; window.scrollTo({{top:0,behavior:'auto'}}); }}
  function inject(id){{
    if(bstate==='done' && bundle && bundle[id]){{ detailEl.innerHTML=bundle[id]; }}
    else {{ detailEl.innerHTML='<div class="rx-spin">Couldn\\'t load this page. <a href="#'+base()+'">Back to all risks</a></div>'; }}
    window.scrollTo({{top:0,behavior:'auto'}});
  }}
  function showDetail(id){{
    root.classList.add('detail');
    if(bstate==='done'){{ inject(id); return; }}
    detailEl.innerHTML='<div class="rx-spin"><i class="fas fa-circle-notch fa-spin"></i> loading&hellip;</div>';
    window.scrollTo({{top:0,behavior:'auto'}});
    whenReady(function(){{ if(currentId()===id) inject(id); }});
  }}
  function render(){{ var id=currentId(); if(id) showDetail(id); else showList(); }}
  function goTo(id){{ location.hash='#'+(base()?base()+'/':'')+id; }}
  function goList(){{ location.hash='#'+base(); }}
  tiles.forEach(function(t){{ t.addEventListener('click',function(){{ goTo(t.dataset.go); }}); }});
  root.addEventListener('click',function(e){{ var b=e.target.closest?e.target.closest('.rx-back'):null; if(b){{ e.preventDefault(); goList(); }} }});
  window.addEventListener('hashchange', render);
  render();
  loadBundle();  // warm the bundle in the background even on the list view
}})();
</script>"""

# --- detail bundle (a separate lightweight page, fetched on demand / in background) ---
DETAIL = (SUBMIT + f"{STYLE}\n<div class=\"rax\" id=\"rax-detail-bundle\">\n"
          + ''.join(pages)
          + "\n</div>")

open('atlas_content.html','w').write(BODY)
open('atlas_detail.html','w').write(DETAIL)
print("list bytes:", len(BODY), "| detail bytes:", len(DETAIL), "| tiles:", len(tiles), "| pages:", len(pages), "| states:", dict(sc))
