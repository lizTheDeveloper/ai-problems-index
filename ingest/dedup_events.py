#!/usr/bin/env python3
"""Collapse same-event duplicates after classification, using the qwen_event_key.

The classifier already reuses an existing key when it recognizes the same event (see
classify_daemon.py's rolling recent-keys window), so most duplicates ALREADY share a key
exactly. This pass is the safety net for the ones it split anyway: it clusters keys by token
containment, then keeps one representative per cluster and marks the rest status='duplicate'.

Nothing is deleted; 'duplicate' rows stay in news_queue for audit and can be revived.

  python3 dedup_events.py --dry     # report clusters, change nothing
  python3 dedup_events.py           # mark duplicates

Which item survives a cluster: prefer status='enriched' > 'classified', then a real primary
URL over an aggregator, then the longest title, then the lowest id (earliest seen).
"""
import os, sys, re, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline import psql, psql_stdin, sq

MIN_SHARED = 2          # clusters must share at least this many tokens
CONTAINMENT = 0.6       # |A∩B| / min(|A|,|B|) >= this → same event
AGG = re.compile(r"(news\.google|bing\.com|/rss/|feedproxy|flipboard|msn\.com)", re.I)


def load():
    rows = psql(
        "SELECT id||E'\\t'||coalesce(qwen_event_key,'')||E'\\t'||coalesce(qwen_risk,'')||E'\\t'||"
        "status||E'\\t'||coalesce(url,'')||E'\\t'||replace(coalesce(title,''),E'\\t',' ') "
        "FROM news_queue WHERE status IN ('classified','enriched') "
        "AND coalesce(qwen_event_key,'')<>'' AND qwen_risk<>'none'").splitlines()
    out = []
    for r in rows:
        p = r.split("\t")
        if len(p) < 6:
            continue
        out.append(dict(id=int(p[0]), key=p[1], risk=p[2], status=p[3], url=p[4], title=p[5],
                        toks=frozenset(t for t in p[1].split() if len(t) > 1)))
    return out


def cluster(items):
    """Union-find over items whose keys are containment-similar. Confined to the same risk:
    two stories on different risks are, for timeline purposes, different entries even if related."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(a)] = find(b)

    # exact-key matches first (cheap, and the common case thanks to reuse-at-classification)
    by_key = {}
    for idx, it in enumerate(items):
        by_key.setdefault((it["risk"], it["key"]), []).append(idx)
    for group in by_key.values():
        for j in group[1:]:
            union(group[0], j)

    # then fuzzy: containment within the same risk
    by_risk = {}
    for idx, it in enumerate(items):
        by_risk.setdefault(it["risk"], []).append(idx)
    for idxs in by_risk.values():
        for a in range(len(idxs)):
            ta = items[idxs[a]]["toks"]
            for b in range(a + 1, len(idxs)):
                tb = items[idxs[b]]["toks"]
                inter = len(ta & tb)
                if inter >= MIN_SHARED and inter / max(1, min(len(ta), len(tb))) >= CONTAINMENT:
                    union(idxs[a], idxs[b])

    clusters = {}
    for idx in range(len(items)):
        clusters.setdefault(find(idx), []).append(idx)
    return [c for c in clusters.values() if len(c) > 1]


def rank(it):
    # higher is better → survives
    return (1 if it["status"] == "enriched" else 0,
            0 if AGG.search(it["url"]) else 1,
            len(it["title"]),
            -it["id"])


def main():
    dry = "--dry" in sys.argv
    items = load()
    clusters = cluster(items)
    dupes, kept_preview = [], []
    for c in clusters:
        members = sorted((items[i] for i in c), key=rank, reverse=True)
        keep, drop = members[0], members[1:]
        kept_preview.append((keep, drop))
        dupes += [d["id"] for d in drop]

    print(f"classified items: {len(items)} | clusters with dups: {len(clusters)} | "
          f"rows to mark duplicate: {len(dupes)}")
    for keep, drop in kept_preview[:20]:
        print(f"\n  [{keep['risk']}] KEEP #{keep['id']}: {keep['title'][:76]}")
        for d in drop:
            print(f"        dup #{d['id']}: {d['title'][:72]}")

    if dry or not dupes:
        print("\n[dry] nothing changed" if dry else "\nno duplicates found")
        return
    ids = ",".join(str(i) for i in dupes)
    psql_stdin("BEGIN;\nUPDATE news_queue SET status='duplicate', updated_at=now() "
               f"WHERE id IN ({ids});\nCOMMIT;\n")
    print(f"\n✓ marked {len(dupes)} rows status='duplicate' "
          f"({len(items)-len(dupes)} distinct events remain)")


if __name__ == "__main__":
    main()
