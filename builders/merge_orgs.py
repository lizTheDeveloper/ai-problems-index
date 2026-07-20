#!/usr/bin/env python3
"""Merge the discovery slices into one deduped org registry, then emit SQL.

Slices overlap heavily by design (FLI, CSET, CSIS, FAR.AI turn up in several). Dedupe on
registrable domain first (most reliable), then normalized name. When two slices disagree,
prefer the richer record: confirmed > unconfirmed, rss > page > none, longer focus, and
UNION the risk_vectors (different slices legitimately see different facets of an org).
"""
import json, re, os, sys, glob
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SLICES = ['caaac', 'technical', 'academic', 'policy', 'gov', 'field', 'harms']
VALID_TYPES = {'technical-lab', 'academic-center', 'policy-thinktank', 'government',
               'advocacy', 'funder', 'field-building', 'community'}

risk_ids = {ln.split(' :: ')[0].strip()
            for ln in open(os.path.join(HERE, 'risk_ids.txt')) if ' :: ' in ln}

def domain(u):
    m = re.match(r'https?://([^/]+)', (u or '').strip(), re.I)
    if not m:
        return ''
    d = m.group(1).lower().replace('www.', '')
    # collapse obvious subdomain variants of the same institution
    return d

def normname(n):
    n = re.sub(r'\b(the|inc|ltd|llc|foundation|institute|center|centre)\b', '', (n or '').lower())
    return re.sub(r'[^a-z0-9]', '', n)

def slugify(n):
    return re.sub(r'[^a-z0-9]+', '-', (n or '').lower()).strip('-')[:60]

def feedrank(k): return {'rss': 2, 'page': 1}.get(k or 'none', 0)

records, dropped = [], []
for s in SLICES:
    p = os.path.join(HERE, f'orgs_{s}.json')
    if not os.path.exists(p):
        print(f"  (missing slice: {s})")
        continue
    try:
        data = json.load(open(p))
    except Exception as e:
        print(f"  !! {s}: unparseable ({e})")
        continue
    n_bad = 0
    for o in data:
        if not isinstance(o, dict) or not (o.get('name') or '').strip():
            n_bad += 1
            continue
        o['discovered_by'] = s
        # clamp risk_vectors to ids that actually exist
        rv = [r for r in (o.get('risk_vectors') or []) if r in risk_ids]
        bad = [r for r in (o.get('risk_vectors') or []) if r not in risk_ids]
        if bad:
            dropped.append((o['name'], bad))
        o['risk_vectors'] = sorted(set(rv))
        if o.get('org_type') not in VALID_TYPES:
            o['org_type'] = 'community'
        records.append(o)
    print(f"  {s}: {len(data)} entries" + (f" ({n_bad} malformed)" if n_bad else ""))

# ---- dedupe
by_key = {}
for o in records:
    d = domain(o.get('url'))
    key = ('d', d) if d else ('n', normname(o['name']))
    if key not in by_key:
        by_key[key] = o
        continue
    a = by_key[key]
    # merge: keep the better record, union the risk vectors + provenance
    merged_rv = sorted(set(a.get('risk_vectors', [])) | set(o.get('risk_vectors', [])))
    better = o if (
        (bool(o.get('confirmed')), feedrank(o.get('feed_kind')), len(o.get('focus') or ''))
        > (bool(a.get('confirmed')), feedrank(a.get('feed_kind')), len(a.get('focus') or ''))
    ) else a
    other = a if better is o else o
    better = dict(better)
    better['risk_vectors'] = merged_rv
    better['discovered_by'] = '+'.join(sorted({a.get('discovered_by',''), o.get('discovered_by','')} - {''}))
    # take a feed from the loser if the winner has none
    if feedrank(better.get('feed_kind')) < feedrank(other.get('feed_kind')):
        better['feed_url'], better['feed_kind'] = other.get('feed_url'), other.get('feed_kind')
    by_key[key] = better

orgs = list(by_key.values())
# unique slugs
seen = {}
for o in orgs:
    base = slugify(o.get('acronym') or o['name']) or slugify(o['name'])
    slug, i = base, 2
    while slug in seen:
        slug = f"{base}-{i}"; i += 1
    seen[slug] = 1
    o['slug'] = slug

orgs.sort(key=lambda x: (x.get('name') or '').lower())
json.dump(orgs, open(os.path.join(HERE, 'orgs_merged.json'), 'w'), indent=1)

# ---- report
from collections import Counter
print(f"\nmerged: {len(records)} raw -> {len(orgs)} unique orgs")
print("  by type: ", dict(Counter(o['org_type'] for o in orgs)))
print("  by feed: ", dict(Counter(o.get('feed_kind') or 'none' for o in orgs)))
print("  confirmed:", sum(1 for o in orgs if o.get('confirmed')), "/", len(orgs))
print("  countries:", len({(o.get('country') or '').strip() for o in orgs if (o.get('country') or '').strip()}))
cov = Counter(rv for o in orgs for rv in o['risk_vectors'])
print(f"  risk vectors covered: {len(cov)}/{len(risk_ids)}")
if dropped:
    print(f"\n  !! {len(dropped)} entries had invalid risk ids (clamped):")
    for n, b in dropped[:10]:
        print(f"     {n}: {b}")

# ---- SQL
def q(s):
    return "NULL" if s is None or s == '' else "'" + str(s).replace("'", "''") + "'"
def arr(xs):
    return "ARRAY[" + ",".join(q(x) for x in xs) + "]::text[]" if xs else "'{}'::text[]"

out = ["\\set ON_ERROR_STOP on", "BEGIN;", "TRUNCATE alignment_orgs;"]
for o in orgs:
    out.append(
        "INSERT INTO alignment_orgs (slug,name,acronym,url,feed_url,feed_kind,country,org_type,"
        "founded,focus,risk_vectors,confirmed,notes,discovered_by) VALUES ("
        f"{q(o['slug'])},{q(o['name'])},{q(o.get('acronym'))},{q(o.get('url'))},{q(o.get('feed_url'))},"
        f"{q(o.get('feed_kind') or 'none')},{q(o.get('country'))},{q(o['org_type'])},"
        f"{q(str(o.get('founded')) if o.get('founded') else None)},{q(o.get('focus'))},"
        f"{arr(o['risk_vectors'])},{'true' if o.get('confirmed') else 'false'},"
        f"{q(o.get('notes'))},{q(o.get('discovered_by'))});")
out += ["SELECT count(*) AS orgs FROM alignment_orgs;", "COMMIT;"]
open(os.path.join(HERE, 'apply_orgs.sql'), 'w').write("\n".join(out) + "\n")
print(f"\nwrote orgs_merged.json + apply_orgs.sql ({len(orgs)} inserts)")
