#!/usr/bin/env python3
"""DB-driven Research Library builder. Reads research_lib_dump.json (dump of research_library),
emits theme-native, filterable content_html. Rerun after any research_library change."""
import json, html

recs = json.load(open('research_lib_dump.json'))
def esc(s): return html.escape(s or '')

ORG_CLASS = {'Anthropic':'anth','Apollo Research':'apollo','METR':'metr','Liberation Labs / THCoalition':'lib'}
def oc(o): return ORG_CLASS.get(o, 'other')

orgs = {}
for r in recs: orgs[r['org']] = orgs.get(r['org'], 0) + 1
org_order = sorted(orgs, key=lambda o: -orgs[o])

cards = []
for r in recs:
    du = f'<div class="rl-du"><b>dual-use</b> {esc(r["dual_use_note"])}</div>' if r.get('dual_use_note') else ''
    auth = f'<span class="rl-auth">{esc(r["authors"])}</span>' if r.get('authors') else ''
    meta = ' · '.join(x for x in [esc(r.get('year')), esc(r.get('type'))] if x)
    cards.append(
        f'<div class="rl-card {oc(r["org"])}" data-org="{esc(r["org"])}" '
        f'data-text="{esc((r["title"]+" "+(r.get("topic") or "")+" "+(r.get("key_finding") or "")+" "+(r.get("authors") or "")).lower())}">'
        f'<div class="rl-top"><span class="rl-org {oc(r["org"])}">{esc(r["org"])}</span>'
        f'<span class="rl-meta">{meta}</span></div>'
        f'<a class="rl-title" href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])} ↗</a>'
        + (f'<div class="rl-topic">{esc(r["topic"])}</div>' if r.get('topic') else '')
        + (f'<div class="rl-find">{esc(r["key_finding"])}</div>' if r.get('key_finding') else '')
        + auth + du + '</div>')

STYLE = """<style>
.rlib{--l:var(--color-border,#2a2f36);--mut:var(--color-text-muted,#8b94a0);--panel:var(--color-bg-card,#1c1f24);
 --ink:var(--color-text,#eef2f6);--pri:var(--color-primary,#34a58e);--acc:var(--color-accent,#e0741c);--bg:var(--color-bg,#0c0d10);
 --anth:#d0703c;--apollo:#8b5cf6;--metr:#3b9ede;--lib:#3fae6b;
 font-family:var(--font-primary,system-ui,sans-serif);color:var(--ink)}
.rlib *{box-sizing:border-box}
.rlib .lede{font-size:1.04rem;color:var(--mut);max-width:70ch;line-height:1.6}
.rlib em{font-style:normal;color:var(--ink);border-bottom:1.5px solid color-mix(in srgb,var(--pri) 55%,transparent)}
.rlib .ctrl{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:16px 0;position:sticky;top:0;z-index:5;
 background:color-mix(in srgb,var(--bg) 90%,transparent);padding:8px 0;backdrop-filter:blur(6px)}
.rlib .fbtn{font-size:.8rem;font-weight:600;color:var(--mut);background:transparent;border:1px solid var(--l);border-radius:999px;
 padding:6px 13px;cursor:pointer;font-family:inherit}.rlib .fbtn.on{color:var(--bg);background:var(--pri);border-color:var(--pri)}
.rlib input.q{flex:1;min-width:170px;background:var(--panel);border:1px solid var(--l);border-radius:999px;padding:8px 15px;
 color:var(--ink);font-family:inherit;font-size:.86rem}
.rlib .count{font-size:.78rem;color:var(--mut);font-family:ui-monospace,monospace}
.rlib .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:12px}
@media(max-width:560px){.rlib .grid{grid-template-columns:1fr}}
.rlib .rl-card{border:1px solid var(--l);border-left-width:3px;border-radius:0 13px 13px 0;padding:14px 16px;background:var(--panel);
 display:flex;flex-direction:column;gap:7px}
.rlib .rl-card.anth{border-left-color:var(--anth)}.rlib .rl-card.apollo{border-left-color:var(--apollo)}
.rlib .rl-card.metr{border-left-color:var(--metr)}.rlib .rl-card.lib{border-left-color:var(--lib)}
.rlib .rl-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.rlib .rl-org{font-family:ui-monospace,monospace;font-size:.62rem;font-weight:700;padding:2px 7px;border-radius:5px;white-space:nowrap}
.rlib .rl-org.anth{background:color-mix(in srgb,var(--anth) 20%,transparent);color:var(--anth)}
.rlib .rl-org.apollo{background:color-mix(in srgb,var(--apollo) 22%,transparent);color:var(--apollo)}
.rlib .rl-org.metr{background:color-mix(in srgb,var(--metr) 20%,transparent);color:var(--metr)}
.rlib .rl-org.lib{background:color-mix(in srgb,var(--lib) 20%,transparent);color:var(--lib)}
.rlib .rl-meta{font-size:.7rem;color:var(--mut);font-family:ui-monospace,monospace;text-align:right}
.rlib a.rl-title{font-weight:700;font-size:.98rem;line-height:1.3;color:var(--ink);text-decoration:none}
.rlib a.rl-title:hover{color:var(--pri)}
.rlib .rl-topic{font-size:.72rem;color:var(--pri);font-family:ui-monospace,monospace}
.rlib .rl-find{font-size:.86rem;line-height:1.5;color:var(--mut)}
.rlib .rl-auth{font-size:.72rem;color:var(--mut);font-style:italic}
.rlib .rl-du{font-size:.74rem;color:var(--acc);line-height:1.45;border-top:1px dashed var(--l);padding-top:6px}
.rlib .rl-du b{font-family:ui-monospace,monospace;font-size:.62rem;text-transform:uppercase;letter-spacing:.04em}
.rlib .none{color:var(--mut);padding:30px;text-align:center}
</style>"""

def fbtns():
    b = ['<button class="fbtn on" data-o="all">All</button>']
    for o in org_order:
        b.append(f'<button class="fbtn" data-o="{esc(o)}">{esc(o)} ({orgs[o]})</button>')
    return ''.join(b)

BODY = f"""{STYLE}
<div class="rlib">
  <p class="lede">The research this index leans on — <em>{len(recs)} papers</em> from the labs doing the most rigorous work on
  interpretability, scheming/deception, autonomy evaluations, and model welfare: Anthropic, Apollo Research, METR, and
  Liberation Labs. Filterable by lab; search titles, topics and findings. Every entry links to the primary source.</p>
  <div class="ctrl" id="rl-ctrl">
    {fbtns()}
    <input class="q" id="rl-q" type="search" placeholder="search papers…" aria-label="search papers">
    <span class="count" id="rl-count"></span>
  </div>
  <div class="grid" id="rl-grid">
    {''.join(cards)}
  </div>
  <p class="none" id="rl-none" style="display:none">No papers match.</p>
  <p style="font-size:.8rem;color:var(--mut);margin-top:22px">Part of the <a href="/x/ai-problems-index">AI Problems Index</a>.
  Live from the knowledge base. Dual-use findings carry a note; nothing here is operational guidance.</p>
</div>
<script>
(function(){{
  var root=document.querySelector('.rlib'); if(!root) return;
  var cards=[].slice.call(root.querySelectorAll('.rl-card'));
  var ctrl=root.querySelector('#rl-ctrl'), q=root.querySelector('#rl-q'),
      countEl=root.querySelector('#rl-count'), none=root.querySelector('#rl-none');
  var org='all', term='';
  function apply(){{
    var shown=0;
    cards.forEach(function(c){{
      var ok=(org==='all'||c.dataset.org===org)&&(!term||c.dataset.text.indexOf(term)>=0);
      c.style.display=ok?'':'none'; if(ok)shown++;
    }});
    countEl.textContent=shown+' shown'; none.style.display=shown?'none':'';
  }}
  ctrl.querySelectorAll('.fbtn').forEach(function(b){{b.onclick=function(){{org=b.dataset.o;
    ctrl.querySelectorAll('.fbtn').forEach(function(x){{x.classList.toggle('on',x===b);}});apply();}};}});
  q.addEventListener('input',function(){{term=q.value.trim().toLowerCase();apply();}});
  apply();
}})();
</script>"""

open('research_content.html','w').write(BODY)
print("research content bytes:", len(BODY), "| cards:", len(cards))
