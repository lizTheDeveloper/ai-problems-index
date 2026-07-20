#!/usr/bin/env python3
"""DB-driven "Who's working on what" — the alignment/safety org directory.

Reads orgs_dump.json (alignment_orgs) + atlas_issues.json (risk vectors) and emits
orgs_content.html for the `ai-alignment-orgs` page slug.

The directory and the research feed are two views of ONE dataset: an org row carries both
its public description and its feed_url, so adding an org here starts ingesting its research.
The coverage section is the bridge to the scorecard — a risk vector with few orgs on it is a
finding about the field, not a gap in our data.

  python3 build_orgs.py   →  orgs_content.html
"""
import json, html, re
from collections import Counter, defaultdict

orgs = json.load(open('orgs_dump.json'))
issues = {i['id']: i for i in json.load(open('atlas_issues.json'))}
NAV = open('nav_block.html').read()

def esc(s): return html.escape(s or '')

TYPE_META = {
 'technical-lab':    ('Technical lab',    'fa-flask',            '#34a58e'),
 'academic-center':  ('Academic center',  'fa-graduation-cap',   '#7aa2f7'),
 'policy-thinktank': ('Policy & governance','fa-landmark-dome',  '#e0741c'),
 'government':       ('Government body',  'fa-building-columns', '#d9902b'),
 'advocacy':         ('Advocacy',         'fa-bullhorn',         '#e5484d'),
 'funder':           ('Funder',           'fa-hand-holding-dollar','#2ea043'),
 'field-building':   ('Field-building',   'fa-seedling',         '#8b5cf6'),
 'community':        ('Community & media','fa-comments',         '#3a9dc4'),
}
def tmeta(t): return TYPE_META.get(t or '', ('Other', 'fa-circle-dot', '#8b94a0'))

# ---------------------------------------------------------------- coverage
cov = defaultdict(list)
for o in orgs:
    for rv in (o.get('risk_vectors') or []):
        if rv in issues:
            cov[rv].append(o)

def slugify(s): return re.sub(r'[^a-z0-9]+', '-', (s or '').lower()).strip('-')

n_feed = sum(1 for o in orgs if (o.get('feed_kind') == 'rss'))
countries = sorted({(o.get('country') or '').strip() for o in orgs if (o.get('country') or '').strip()})
types_present = [t for t in TYPE_META if any(o.get('org_type') == t for o in orgs)]

# risks ranked by how many orgs work on them
ranked = sorted(issues.values(), key=lambda i: (len(cov.get(i['id'], [])), i['title']))
undercovered = [i for i in ranked if len(cov.get(i['id'], [])) <= 2]

STYLE = r"""<style>
.aoi{--l:var(--color-border,#2a2f36);--mut:var(--color-text-muted,#8b94a0);--panel:var(--color-bg-card,#1c1f24);
 --ink:var(--color-text,#eef2f6);--pri:var(--color-primary,#34a58e);--acc:var(--color-accent,#e0741c);--bg:var(--color-bg,#0c0d10);
 font-family:var(--font-primary,system-ui,sans-serif);color:var(--ink)}
.aoi *{box-sizing:border-box}
.aoi .lede{font-size:1.04rem;color:var(--mut);max-width:74ch;line-height:1.6}
.aoi em{font-style:normal;color:var(--ink);border-bottom:1.5px solid color-mix(in srgb,var(--pri) 55%,transparent)}
.aoi .tally{display:flex;gap:7px;flex-wrap:wrap;margin:16px 0 10px}
.aoi .tpill{display:inline-flex;align-items:center;gap:7px;font-size:.78rem;font-weight:700;font-family:ui-monospace,monospace;
 border:1px solid var(--l);border-radius:999px;padding:5px 11px;color:var(--ink);background:var(--panel)}
.aoi .dot{width:9px;height:9px;border-radius:50%;flex:0 0 auto;display:inline-block}
.aoi .ctrl{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:12px 0;position:sticky;top:0;z-index:5;
 background:color-mix(in srgb,var(--bg) 90%,transparent);padding:9px 0;backdrop-filter:blur(6px)}
.aoi .fbtn{display:inline-flex;align-items:center;gap:7px;font-size:.8rem;font-weight:600;color:var(--mut);background:transparent;
 border:1px solid var(--l);border-radius:999px;padding:6px 13px;cursor:pointer;font-family:inherit}
.aoi .fbtn.on{color:var(--bg);background:var(--pri);border-color:var(--pri)}
.aoi select.rv{font-family:inherit;font-size:.82rem;color:var(--ink);background:var(--panel);border:1px solid var(--l);
 border-radius:999px;padding:7px 12px;cursor:pointer;max-width:280px}
.aoi input.q{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--l);border-radius:999px;padding:8px 15px;
 color:var(--ink);font-family:inherit;font-size:.86rem}
.aoi .count{font-size:.78rem;color:var(--mut);font-family:ui-monospace,monospace}
.aoi .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:11px;margin-top:8px}
.aoi .card{border:1px solid var(--l);border-left:3px solid var(--tc);border-radius:13px;background:var(--panel);
 padding:14px 16px;display:flex;flex-direction:column;gap:9px;min-width:0}
.aoi .card:hover{border-color:color-mix(in srgb,var(--tc) 55%,var(--l))}
.aoi .chead{display:flex;align-items:flex-start;gap:11px;min-width:0}
.aoi .cic{flex:0 0 auto;width:34px;height:34px;border-radius:9px;display:grid;place-items:center;font-size:.92rem;
 background:color-mix(in srgb,var(--tc) 16%,transparent);color:var(--tc)}
.aoi .cname{font-weight:700;font-size:.97rem;line-height:1.25;margin:0;min-width:0;overflow-wrap:anywhere}
.aoi .cname a{color:inherit;text-decoration:none;border-bottom:1px solid color-mix(in srgb,var(--pri) 45%,transparent)}
.aoi .cname a:hover{color:var(--pri)}
.aoi .cmeta{font-size:.7rem;color:var(--mut);font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.05em;
 display:flex;gap:8px;flex-wrap:wrap;margin-top:3px}
.aoi .cfocus{font-size:.87rem;color:var(--mut);line-height:1.55;margin:0}
.aoi .rvs{display:flex;gap:5px;flex-wrap:wrap}
.aoi .rv-tag{font-size:.68rem;font-family:ui-monospace,monospace;border:1px solid var(--l);border-radius:999px;
 padding:2px 8px;color:var(--mut);background:var(--bg);text-decoration:none}
.aoi .rv-tag:hover{color:var(--ink);border-color:var(--pri)}
.aoi .feedbadge{font-size:.63rem;font-family:ui-monospace,monospace;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
 border-radius:999px;padding:2px 7px;border:1px solid}
.aoi .fb-rss{color:#2ea043;border-color:color-mix(in srgb,#2ea043 45%,transparent);background:color-mix(in srgb,#2ea043 10%,transparent)}
.aoi .fb-page{color:#d9902b;border-color:color-mix(in srgb,#d9902b 45%,transparent);background:color-mix(in srgb,#d9902b 10%,transparent)}
.aoi .fb-none{color:var(--mut);border-color:var(--l)}
.aoi .unconf{font-size:.63rem;font-family:ui-monospace,monospace;color:#e5484d;border:1px solid color-mix(in srgb,#e5484d 45%,transparent);
 border-radius:999px;padding:2px 7px}
.aoi h2.sec{font-size:1.12rem;margin:34px 0 4px;display:flex;align-items:center;gap:9px}
.aoi h2.sec i{color:var(--pri)}
.aoi .covgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px;margin-top:10px}
.aoi .covrow{display:flex;align-items:center;gap:10px;border:1px solid var(--l);border-radius:10px;background:var(--panel);
 padding:9px 12px;font-size:.84rem;min-width:0}
.aoi .covrow .n{font-family:ui-monospace,monospace;font-weight:700;font-size:.95rem;flex:0 0 auto;width:26px;text-align:right}
.aoi .covrow .t{flex:1;min-width:0;overflow-wrap:anywhere;color:var(--ink);text-decoration:none}
.aoi .covrow .t:hover{color:var(--pri)}
.aoi .covrow.zero{border-color:color-mix(in srgb,#e5484d 45%,transparent)}
.aoi .covrow.zero .n{color:#e5484d}
.aoi .note{border:1px solid var(--l);border-left:3px solid var(--acc);border-radius:11px;background:var(--panel);
 padding:13px 16px;margin:18px 0;font-size:.88rem;color:var(--mut);line-height:1.6}
.aoi .note b{color:var(--ink)}
.aoi .caaac{border:1px dashed color-mix(in srgb,var(--acc) 55%,var(--l));border-radius:12px;background:var(--panel);
 padding:14px 17px;margin:22px 0 6px;font-size:.88rem;color:var(--mut);line-height:1.6}
.aoi .caaac b{color:var(--ink)}
.aoi .caaac a{color:var(--acc)}
.aoi .empty{color:var(--mut);font-size:.9rem;padding:22px;text-align:center;border:1px dashed var(--l);border-radius:12px}
@media(max-width:560px){.aoi .grid{grid-template-columns:minmax(0,1fr)}}
</style>"""

# ---------------------------------------------------------------- cards
cards = []
for o in sorted(orgs, key=lambda x: (x.get('name') or '').lower()):
    label, ic, col = tmeta(o.get('org_type'))
    rvs = [rv for rv in (o.get('risk_vectors') or []) if rv in issues]
    rv_html = ''.join(
        f'<a class="rv-tag" href="/x/ai-problems-index#atlas/{esc(rv)}" title="{esc(issues[rv]["title"])}">'
        f'{esc(issues[rv]["title"][:34])}</a>' for rv in rvs[:6])
    fk = o.get('feed_kind') or 'none'
    fb = {'rss': ('fb-rss', 'tracked'), 'page': ('fb-page', 'page only')}.get(fk, ('fb-none', 'no feed'))
    meta = [m for m in (o.get('country'), o.get('founded')) if m]
    name_html = (f'<a href="{esc(o["url"])}" target="_blank" rel="noopener">{esc(o["name"])}</a>'
                 if o.get('url') else esc(o['name']))
    acro = f' <span style="color:var(--mut);font-weight:600">({esc(o["acronym"])})</span>' if o.get('acronym') else ''
    unconf = '' if o.get('confirmed') else '<span class="unconf">unverified</span>'
    cards.append(
        f'<article class="card" style="--tc:{col}" data-type="{esc(o.get("org_type") or "")}" '
        f'data-rv="{esc("|".join(rvs))}" data-feed="{esc(fk)}" '
        f'data-s="{esc((o.get("name","")+" "+(o.get("acronym") or "")+" "+(o.get("focus") or "")+" "+(o.get("country") or "")).lower())}">'
        f'<div class="chead"><div class="cic"><i class="fa-solid {ic}"></i></div>'
        f'<div style="min-width:0"><p class="cname">{name_html}{acro}</p>'
        f'<div class="cmeta"><span>{esc(label)}</span>'
        + ''.join(f'<span>{esc(m)}</span>' for m in meta)
        + f'<span class="feedbadge {fb[0]}">{fb[1]}</span>{unconf}</div></div></div>'
        f'<p class="cfocus">{esc(o.get("focus"))}</p>'
        + (f'<div class="rvs">{rv_html}</div>' if rv_html else '')
        + '</article>')

# ---------------------------------------------------------------- coverage rows
covrows = []
for i in ranked:
    n = len(cov.get(i['id'], []))
    covrows.append(
        f'<div class="covrow{" zero" if n == 0 else ""}"><span class="n">{n}</span>'
        f'<a class="t" href="/x/ai-problems-index#atlas/{esc(i["id"])}">{esc(i["title"])}</a></div>')

type_btns = ''.join(
    f'<button class="fbtn" data-f="type" data-v="{t}"><span class="dot" style="background:{TYPE_META[t][2]}"></span>'
    f'{TYPE_META[t][0]} <span style="opacity:.6">{sum(1 for o in orgs if o.get("org_type")==t)}</span></button>'
    for t in types_present)

rv_opts = ''.join(
    f'<option value="{esc(i["id"])}">{esc(i["title"])} ({len(cov.get(i["id"],[]))})</option>'
    for i in sorted(issues.values(), key=lambda x: x['title']))

HTML = f"""{NAV}
{STYLE}
<div class="aoi">
<p class="lede">Who is actually working on each AI risk. {len(orgs)} organizations across
{len(countries)} countries &mdash; technical labs, academic centers, government safety institutes,
policy shops, advocacy groups and funders &mdash; each mapped to the <em>specific risk vectors they
actually publish on</em>, not the ones they mention in a mission statement.</p>

<div class="tally">
  <span class="tpill">{len(orgs)} orgs</span>
  <span class="tpill">{len(countries)} countries</span>
  <span class="tpill">{len(types_present)} kinds</span>
  <span class="tpill"><span class="dot" style="background:#2ea043"></span>{n_feed} with trackable feeds</span>
  <span class="tpill">{sum(1 for i in issues if cov.get(i))} / {len(issues)} risks covered</span>
</div>

<div class="note"><b>How to read this.</b> An organization is listed against a risk vector only if
its <em>published work</em> addresses that vector. &ldquo;Tracked&rdquo; means the org publishes a
machine-readable feed, so new research from them flows into the per-risk scorecard automatically.
&ldquo;Unverified&rdquo; means our discovery pass could not confirm the organization from its own
site &mdash; treat those entries with suspicion.</div>

<div class="ctrl">
  <button class="fbtn on" data-f="type" data-v="">All</button>
  {type_btns}
  <select class="rv" id="rvsel"><option value="">Any risk vector&hellip;</option>{rv_opts}</select>
  <input class="q" id="q" placeholder="Search organizations, focus, country&hellip;" aria-label="Search organizations">
  <span class="count" id="count"></span>
</div>

<div class="grid" id="grid">{''.join(cards)}</div>
<div class="empty" id="empty" style="display:none">No organizations match those filters.</div>

<h2 class="sec"><i class="fa-solid fa-chart-simple"></i> Coverage by risk vector</h2>
<p class="lede">How many organizations we can find working on each risk.
{len(undercovered)} of {len(issues)} risk vectors have two or fewer organizations on them, while
governance and evaluations have dozens. Read a thin row carefully: it can mean almost nobody is
working on the problem, <em>or</em> that our framing is unusual enough that no organization
describes its work that way &mdash; &ldquo;AI denialism&rdquo; and &ldquo;latent data erasure&rdquo;
are ours, not the field's. Those are different claims and this chart does not distinguish them.</p>
<div class="covgrid">{''.join(covrows)}</div>

<div class="caaac">
<b>Credit where it is due.</b> The seed list for this directory came from the logo wall of the
<a href="https://alignmentalignment.ai/" target="_blank" rel="noopener">Center for the Alignment of AI
Alignment Centers</a> (CAAAC), who are &ldquo;completely unaffiliated with these AI alignment
organizations&mdash;but our design agency said their logos would look good on our site.&rdquo;
CAAAC remains the field's only known body working on the alignment of AI alignment centers, and to
our knowledge still maintains the single most complete public listing of them &mdash; a bar the
non-satirical parts of the field have not cleared. We thank them for their hard work aligning
the aligners, and note that we have now recursed one level further by aligning their alignment
of the aligners.
</div>
</div>

<script>
(function(){{
  var g=document.getElementById('grid'), cards=[].slice.call(g.children);
  var q=document.getElementById('q'), rv=document.getElementById('rvsel');
  var cnt=document.getElementById('count'), empty=document.getElementById('empty');
  var fType='';
  function apply(){{
    var term=(q.value||'').toLowerCase().trim(), vec=rv.value, n=0;
    cards.forEach(function(c){{
      var ok = (!fType || c.dataset.type===fType)
            && (!vec || (c.dataset.rv||'').split('|').indexOf(vec)>=0)
            && (!term || (c.dataset.s||'').indexOf(term)>=0);
      c.style.display = ok ? '' : 'none'; if(ok) n++;
    }});
    cnt.textContent = n + ' of ' + cards.length;
    empty.style.display = n ? 'none' : '';
  }}
  [].slice.call(document.querySelectorAll('.fbtn[data-f=type]')).forEach(function(b){{
    b.addEventListener('click',function(){{
      fType=b.dataset.v;
      [].slice.call(document.querySelectorAll('.fbtn[data-f=type]')).forEach(function(x){{x.classList.remove('on');}});
      b.classList.add('on'); apply();
    }});
  }});
  q.addEventListener('input',apply); rv.addEventListener('change',apply);
  apply();
}})();
</script>
"""

open('orgs_content.html', 'w').write(HTML)
print(f"orgs: {len(orgs)} | countries: {len(countries)} | rss feeds: {n_feed} | "
      f"risks covered: {sum(1 for i in issues if cov.get(i))}/{len(issues)} | "
      f"undercovered(<=2): {len(undercovered)} | bytes: {len(HTML)}")
